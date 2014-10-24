#!/usr/bin/env python
#---------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
#---------------------------------------------------------------------
# TradeDangerous :: Modules :: Cache loader
#
#  TD works primarily from an SQLite3 database, but the data in that
#  is sourced from text files.
#   data/TradeDangerous.sql contains the less volatile data - systems,
#   ships, etc
#   data/TradeDangerous.prices contains a description of the price
#   database that is intended to be easily editable and commitable to
#   a source repository.
#
#  TODO: Split prices into per-system or per-station files so that
#  we can tell how old data for a specific system is.

import re
import sqlite3
import sys
import os
import csv
from pathlib import Path
from collections import namedtuple
from tradeexcept import TradeException

# Find the non-comment part of a string
noCommentRe = re.compile(r'^\s*(?P<text>(?:[^\\#]|\\.)*)\s*(#|$)')
systemStationRe = re.compile(r'^\@\s*(.*)\s*/\s*(.*)')
categoryRe = re.compile(r'^\+\s*(.*?)\s*$')

# first part of any prices line is the item name and paying/asking price
itemPriceFrag = r"""
    # match item name, allowing spaces in the name
    (?P<item> .*?)
\s+
    # price station is buying the item for
    (?P<paying> \d+)
\s+
    # price station is selling item for
    (?P<asking> \d+)
"""

# time formats per https://www.sqlite.org/lang_datefunc.html
# YYYY-MM-DD HH:MM:SS
# YYYY-MM-DDTHH:MM:SS
# HH:MM:SS
# 'now'
timeFrag = r'(?P<time>(\d{4}-\d{2}-\d{2}[T ])?\d{2}:\d{2}:\d{2}|now)'

# format used with --full and in TradeDangerous.prices
# <item name> <paying> <asking> [ <time> [ demand <units>L<level> stock <units>L<level> ] ]
itemPriceRe = re.compile(r"""
^
    # name, prices
    {base_f}
    # extended section with time and possibly demand+stock info
    (?:
    \s+
        {time_f}
        # optional demand/stock after time
        (?:
            \s+ demand \s+ (?P<demand> -?\d+L-?\d+ | n/a | -L-)
            \s+ stock \s+ (?P<stock> -?\d+L-?\d+ | n/a | -L-)
        )?
    )?
\s*
$
""".format(base_f=itemPriceFrag, time_f=timeFrag), re.IGNORECASE + re.VERBOSE)

# new format: <name> <paying> <asking> [ <demUnits><demLevel> <stockUnits><stockLevel> [ <time> | now ] ]
qtyLevelFrag = r"""
    unk                         # You can just write 'unknown'
|   n/a                         # alias for 0L0
|   -                           # alias for 0L0
|   \d+[\?LMH]                  # Or <number><level> where level is L(ow), M(ed) or H(igh)
|   0                           # alias for n/a
"""
newItemPriceRe = re.compile(r"""
^
    {base_f}
\s+ 
    # demand units and level
    (?P<demand> {qtylvl_f})
\s+
    # stock units and level
    (?P<stock> {qtylvl_f})
    # time is optional
    (?:
    \s+
        {time_f}
    )?
\s*
$
""".format(base_f=itemPriceFrag, qtylvl_f=qtyLevelFrag, time_f=timeFrag), re.IGNORECASE + re.VERBOSE)


class UnitsAndLevel(object):
    """
        Helper class for breaking a units-and-level reading (e.g. -1L-1 or 50@M)
        into units and level values or throwing diagnostic messages to help the
        user figure out what data error was made.
    """
    # Map textual representations of levels back into integer values
    levels = {
        '-1': -1, '?': -1,
        '0': 0, '-': 0,
        'L': 1, '1': 1,
        'M': 2, '2': 2,
        'H': 3, '3': 3,
    }
    # Split a <units>L<level> reading
    splitLRe = re.compile(r'^(?P<units>\d+)L(?P<level>-\d+)$')
    # Split a <units><level> reading
    splitAtRe = re.compile(r'^(?P<units>\d+)(?P<level>[\?LMH])$')

    def __init__(self, category, reading):
        if reading in (None, "unk", "-1L-1", "-1L0", "0L-1"):
            self.units, self.level = -1, -1
        elif reading in ("-", "-L-", "n/a", "0"):
            self.units, self.level = 0, 0
        else:
            matches = self.splitLRe.match(reading) or self.splitAtRe.match(reading)
            if not matches:
                raise ValueError("Invalid {} units/level value. Expected 'unk', <units>L<level> or <units>[\?LMH], got '{}'".format(category, reading))
            units, level = matches.group('units', 'level')
            try:
                self.units, self.level = int(units), UnitsAndLevel.levels[level]
            except KeyError:
                raise ValueError("Invalid {} level '{}' (expected 0 (or -) for unavailable, L (or 1) for low, M (or 2) for medium, H (or 3) for high)".format(category, level))
            if self.units < 0:
                raise ValueError("Negative {} quantity '{}' specified, please use 'unk' for unknown".format(category, self.units))


class UnknownItemError(TradeException):
    """
        Raised in the case of an item name that we don't know.
        Attributes:
            fileName   Name of the file being read
            lineNo     Line on which the error occurred
            itemName   Key we tried to look up.
    """
    def __init__(self, fromFile, lineNo, itemName):
        self.fileName, self.lineNo, self.itemName = fromFile.name, lineNo, itemName
    def __str__(self):
        return "{}:{}: Unrecognized item name, {}.".format(self.fileName, self.lineNo, str(self.itemName))


class PriceEntry(namedtuple('PriceEntry', [ 'stationID', 'itemID', 'asking', 'paying', 'uiOrder', 'modified', 'demand', 'demandLevel', 'stock', 'stockLevel' ])):
    pass


def priceLineNegotiator(priceFile, db, debug=0):
    """
        Yields SQL for populating the database with prices
        by reading the file handle for price lines.
    """

    stationID, categoryID, uiOrder = None, None, 0

    cur = db.cursor()

    cur.execute("""
            SELECT station_id, UPPER(system.name) || "/" || station.name
              FROM System INNER JOIN Station ON System.system_id = Station.system_id
        """)
    systemByName = { name: ID for (ID, name) in cur }

    categoriesByName = { name: ID for (ID, name) in cur.execute("SELECT category_id, name FROM category") }

    # Are there any item names which appear in two categories?
    qualityItemWithCategory = cur.execute("SELECT COUNT(*) FROM (SELECT name FROM Item GROUP BY 1 HAVING COUNT(*) > 1)").fetchone()[0]
    if qualityItemWithCategory:
        itemsByName = { "{}.{}".format(catID, name): itemID for (catID, itemID, name) in cur.execute("SELECT category_id, item_id, name FROM item") }
    else:
        itemsByName = { name: itemID for (itemID, name) in cur.execute("SELECT item_id, name FROM item") }

    lineNo = 0
    for line in priceFile:
        lineNo += 1
        try:
            text = noCommentRe.match(line).group('text').strip()
            # replace whitespace with single spaces
            text = ' '.join(text.split())      # http://stackoverflow.com/questions/2077897
            if not text: continue

            # Check for a station assignment
            matches = systemStationRe.match(text)
            if matches:
                # Change which station we're at
                stationName = "%s/%s" % (matches.group(1).upper(), matches.group(2))
                stationID, categoryID, uiOrder = systemByName[stationName], None, 0
                if debug > 1: print("NEW STATION: {}".format(stationName))
                continue
            if not stationID:
                print("Expecting: '@ SYSTEM / Station'.")
                print("Got: {}".format(line))
                sys.exit(1)

            # Check for a category assignment
            matches = categoryRe.match(text)
            if matches:
                categoryName = matches.group(1)
                categoryID, uiOrder = categoriesByName[categoryName], 0
                if debug > 1: print("NEW CATEGORY: {}".format(categoryName))
                continue
            if not categoryID:
                print("Expecting '+ Category Name'.")
                print("Got: {}".format(line))
                sys.exit(1)

            matches = itemPriceRe.match(text)
            if not matches:
                matches = newItemPriceRe.match(text)
                if not matches:
                    raise ValueError("Unrecognized line/syntax: {}".format(line))

            itemName, stationPaying, stationAsking, modified = matches.group('item'), int(matches.group('paying')), int(matches.group('asking')), matches.group('time')
            demand = UnitsAndLevel('demand', matches.group('demand'))
            stock  = UnitsAndLevel('stock',  matches.group('stock'))
            if modified and modified.lower() in ('now', '"now"', "'now'"):
                modified = None         # Use CURRENT_FILESTAMP

            try:
                itemID = itemsByName["{}:{}".format(categoryID, itemName)] if qualityItemWithCategory else itemsByName[itemName]
            except KeyError as key:
                raise UnknownItemError(priceFile, lineNo, key)

            uiOrder += 1
            yield PriceEntry(stationID, itemID, stationPaying, stationAsking, uiOrder, modified, demand.units, demand.level, stock.units, stock.level)
        except UnknownItemError:
            continue


def processPricesFile(db, pricesPath, stationID=None, debug=0):
    global currentTimestamp

    if debug: print("* Processing Prices file '{}'".format(str(pricesPath)))

    if stationID:
        if debug: print("* Deleting stale entries for {}".format(stationID))
        db.execute("DELETE FROM Price WHERE station_id = {}".format(stationID))

    try:
        with pricesPath.open() as pricesFile:
            bindValues = []
            for price in priceLineNegotiator(pricesFile, db, debug):
                if debug > 2: print(price)
                bindValues += [ price ]
            stmt = """
                       INSERT OR REPLACE INTO Price (station_id, item_id, sell_to, buy_from, ui_order, modified, demand, demand_level, stock, stock_level)
                       VALUES (?, ?, ?, ?, ?, IFNULL(?, CURRENT_TIMESTAMP), ?, ?, ?, ?)
                    """
            db.executemany(stmt, bindValues)
        db.commit()
    except FileNotFoundError:
        if debug:
            print("WARNING: processPricesFile found no {} file".format(pricesPath))


def processImportFile(db, importPath, tableName, debug=0):

    if debug: print("* Processing import file '{}' for table '{}'".format(str(importPath), tableName))

    try:
        with importPath.open() as importFile:
            csvin = csv.reader(importFile, delimiter=',', quotechar="'", doublequote=True)
            # first line must be the column names
            columnNames = next(csvin)
            columnCount = len(columnNames)

            # split up columns and values
            # this is necessary because the insert might use a foreign key
            bindColumns = []
            bindValues  = []
            for cName in columnNames:
                splitNames = cName.split('@')
                if len(splitNames) == 1:
                    # no foreign key, straight insert
                    bindColumns += [ splitNames[0] ]
                    bindValues  += [ '?' ]
                else:
                    # foreign key, we need to make a select
                    splitJoin    = splitNames[1].split('.')
                    joinTable    = splitJoin[0]
                    joinColumn   = splitJoin[1]
                    bindColumns += [ joinColumn ]
                    bindValues  += [ "(SELECT {newValue} FROM {table} WHERE {table}.{column} = ?)".format(newValue=splitNames[1], table=joinTable, column=splitNames[0]) ]
            # now we can make the sql statement
            sql_stmt = "INSERT INTO {table}({columns}) VALUES({values})".format(table=tableName, columns=','.join(bindColumns), values=','.join(bindValues))
            if debug: print("* SQL-Statement: {}".format(sql_stmt))

            # import the data
            importCount = 0
            for linein in csvin:
                if len(linein) == columnCount:
                    if debug > 1: print("-        Values: {}".format(', '.join(linein)))
                    db.execute(sql_stmt, linein)
                    importCount += 1
            db.commit()
            if debug: print("* {count} {table}s imported".format(count=importCount, table=tableName))

    except FileNotFoundError:
        if debug:
            print("WARNING: processImportFile found no {} file".format(importPath))


def buildCache(dbPath, sqlPath, pricesPath, importTables, debug=0):
    """
        Rebuilds the SQlite database from source files.

        TD's data is either "stable" - information that rarely changes like Ship
        details, star systems etc - and "volatile" - pricing information, etc.

        The stable data starts out in data/TradeDangerous.sql while other data
        is stored in custom-formatted text files, e.g. ./TradeDangerous.prices.

        We load both sets of data into an SQLite database, after which we can
        avoid the text-processing overhead by simply checking if the text files
        are newer than the database.
    """

    # Create an in-memory database to populate with our data.
    if debug: print("* Creating temporary database in memory")
    tempDB = sqlite3.connect(':memory:')

    # Read the SQL script so we are ready to populate structure, etc.
    if debug: print("* Executing SQL Script '{}' from '{}'".format(sqlPath, os.getcwd()))
    with sqlPath.open() as sqlFile:
        sqlScript = sqlFile.read()
        tempDB.executescript(sqlScript)

    # import standard tables
    for (importName, importTable) in importTables:
        processImportFile(tempDB, Path(importName), importTable, debug=debug)

    # Parse the prices file
    processPricesFile(tempDB, pricesPath, debug=debug)

    # Database is ready; copy it to a persistent store.
    if debug: print("* Populating SQLite database file '%s'" % dbPath)
    if dbPath.exists():
        if debug: print("- Removing old database file")
        dbPath.unlink()

    newDB = sqlite3.connect(str(dbPath))
    importScript = "".join(tempDB.iterdump())
    if debug > 3: print(importScript)
    newDB.executescript(importScript)
    newDB.commit()

    if debug: print("* Finished")


def commandLineBuildCache():
    # Because it looks less sloppy that doing this in if __name__ == '__main__'...
    from tradedb import TradeDB
    dbFilename = TradeDB.defaultDB
    sqlFilename = TradeDB.defaultSQL
    pricesFilename = TradeDB.defaultPrices

    # Check command line for -w/--debug inputs.
    import argparse
    parser = argparse.ArgumentParser(description='Build TradeDangerous cache file from source files')
    parser.add_argument('--db', help='Specify database file to build. Default: {}'.format(dbFilename), default=dbFilename, required=False)
    parser.add_argument('--sql', help='Specify SQL script to execute. Default: {}'.format(sqlFilename), default=sqlFilename, required=False)
    parser.add_argument('--prices', help='Specify the prices file to load. Default: {}'.format(pricesFilename), default=pricesFilename, required=False)
    parser.add_argument('-f', '--force', dest='force', help='Overwite existing file', default=False, required=False, action='store_true')
    parser.add_argument('-w', '--debug', dest='debug', help='Increase level of diagnostic output', default=0, required=False, action='count')
    args = parser.parse_args()

    import pathlib

    # Check that the file doesn't already exist.
    dbPath, sqlPath, pricesPath = pathlib.Path(args.db), pathlib.Path(args.sql), pathlib.Path(args.prices)
    if not args.force:
        if dbPath.exists():
            print("{}: ERROR: SQLite3 database '{}' already exists. Please remove it first.".format(sys.argv[0], args.db))
            sys.exit(1)

    if not sqlPath.exists():
        print("SQL file '{}' does not exist.".format(args.sql))
        sys.exit(1)

    if not pricesPath.exists():
        print("Prices file '{}' does not exist.".format(args.prices))

    buildCache(dbPath, sqlPath, pricesPath, args.debug)


if __name__ == '__main__':
    commandLineBuildCache()
