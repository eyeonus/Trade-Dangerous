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
from data import corrections

######################################################################
# Regular expression patterns. Here be draegons.
# If you add new patterns:
# - use fragments and re.VERBOSE (see itemPriceRe)
# - use named captures (?P<name> ...)
# - include comments

## Find the non-comment part of a string
noCommentRe = re.compile(r'^\s*(?P<text>(?:[^\\#]|\\.)*)\s*(#|$)')

## Match the '@ SYSTEM/Station' line
systemStationRe = re.compile(r'^\@\s*(.*)\s*/\s*(.*)')

## Match the '+ Category' line
categoryRe = re.compile(r'^\+\s*(.*?)\s*$')

## Price Line matching

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

# pre-4.6.0 extended format
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

# new format:
# <name> <sell> <buy> [ <demand> <stock> [ <time> | now ] ]
qtyLevelFrag = r"""
    unk                 # You can just write 'unknown'
|   \?                  # alias for unknown
|   n/a                 # alias for 0L0
|   -                   # alias for 0L0
|   \d+[\?LMH]          # Or <number><level> where level is L(ow), M(ed) or H(igh)
|   0                   # alias for n/a
|   bug
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
""".format(base_f=itemPriceFrag, qtylvl_f=qtyLevelFrag, time_f=timeFrag),
            re.IGNORECASE + re.VERBOSE)


######################################################################
# Exception classes

class BuildCacheBaseException(TradeException):
    """
        Baseclass for BuildCache exceptions
        Attributes:
            fileName    Name of file being processedStations
            lineNo      Line the error occurred on
            error       Description of the error
    """
    def __init__(self, fromFile, lineNo, error=None):
        self.fileName = fromFile.name
        self.lineNo = lineNo
        self.error = error or "UNKNOWN ERROR"

    def __str__(self):
        return "{}:{} {}".format(self.fileName, self.lineNo, self.error)


class UnknownStationError(BuildCacheBaseException):
    """
        Raised when the file contains an unknown star/station name.
    """
    def __init__(self, fromFile, lineNo, key):
        error = "Unrecognized STAR/Station, '{}'.".format(key)
        super().__init__(fromFile, lineNo, error)

class UnknownItemError(BuildCacheBaseException):
    """
        Raised in the case of an item name that we don't know.
        Attributes:
            itemName   Key we tried to look up.
    """
    def __init__(self, fromFile, lineNo, itemName):
        error = "Unrecognized item name, '{}'.".format(itemName)
        super().__init__(fromFile, lineNo, error)


class MultipleStationEntriesError(BuildCacheBaseException):
    """
        Raised when one station appears multiple times in the same file.
        Attributes:
            facility    Facility name that was repeated
            prevLineNo  Where the original entry was
    """
    def __init__(self, fromFile, lineNo, facility, prevLineNo):
        error = "Second entry for station '{}', previous at line {}.". \
                    format(facility, prevLineNo)
        super().__init__(fromFile, lineNo, error)


class MultipleItemEntriesError(BuildCacheBaseException):
    """
        Raised when one item appears multiple times in the same station.
        Attributes:
            item        Name of the item that was repeated
            prevLineNo  Where the original entry was
    """
    def __init__(self, fromFile, lineNo, item, prevLineNo):
        error = "Second entry for item '{}', previous at line {}.". \
                    format(item, prevLineNo)
        super().__init__(fromFile, lineNo, error)


class SyntaxError(BuildCacheBaseException):
    """
        Raised when an invalid line is read.
        Attributes:
            problem     The problem that occurred
            text        Offending text
    """
    def __init__(self, fromFile, lineNo, problem, text):
        error = "{},\ngot: '{}'.".format(problem, text.strip())
        super().__init__(fromFile, lineNo, error)


class SupplyError(BuildCacheBaseException):
    """
        Raised when a supply field is incorrectly formatted.
    """
    def __init__(self, fromFile, lineNo, category, problem, value):
        error = "Invalid {} supply value: {}. Got: {}". \
                    format(category, problem, value)
        super().__init__(fromFile, lineNo, error)


######################################################################
# Helpers

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
    splitLRe = re.compile(r'^(?P<units>\d+)L(?P<level>-?\d+)$')
    # Split a <units><level> reading
    splitAtRe = re.compile(r'^(?P<units>\d+)(?P<level>[\?LMH])$', re.IGNORECASE)

    def __init__(self, pricesFile, lineNo, category, reading):
        ucReading = reading.upper()
        if ucReading in ("UNK", "?", "-1L-1", "-1L0", "0L-1"):
            self.units, self.level = -1, -1
        elif ucReading in ("-", "-L-", "N/A", "0"):
            self.units, self.level = 0, 0
        else:
            matches = self.splitLRe.match(ucReading) or \
                        self.splitAtRe.match(ucReading)
            if not matches:
                raise SupplyError(
                        pricesFile, lineNo, category,
                        "Expected 'unk', <units>L<level> or <units>[?LMH]",
                        reading
                        )
            units, level = matches.group('units', 'level')
            try:
                self.units, self.level = int(units), UnitsAndLevel.levels[level]
            except KeyError:
                raise SupplyError(pricesFile, lineNo, category,
                        "Invalid level value", reading)
            if self.units < 0:
                raise SupplyError(pricesFile, lineNo, category,
                        "Negative unit quantity. Please use 'unk' for unknown",
                        reading)


class PriceEntry(namedtuple('PriceEntry', [
                                'stationID', 'itemID', 
                                'asking', 'paying',
                                'uiOrder', 'modified',
                                'demand', 'demandLevel',
                                'stock', 'stockLevel'
                            ])):
    pass


######################################################################
# Code
######################################################################

def getSystemByNameIndex(cur):
    """ Build station index in STAR/Station notation """
    cur.execute("""
            SELECT station_id, system.name, station.name
              FROM System
                   INNER JOIN Station
                      ON System.system_id = Station.system_id
        """)
    return {
        "{}/{}".format(sysName.upper(), stnName): ID
            for (ID, sysName, stnName)
            in cur
    }


def getCategoriesByNameIndex(cur):
    """ Build category name => id index """
    cur.execute("SELECT category_id, name FROM category")
    return {
        name: ID
            for (ID, name)
            in cur
    }


def testItemNamesUniqueAcrossCategories(cur):
    """
        Return True if no single item name appears twice.
        In previous betas we had some items which appeared
        in more than one category.
    """
    cur.execute("""
            SELECT COUNT(*)
              FROM (
                SELECT name
                  FROM Item
                 GROUP BY name
                HAVING COUNT(*) > 1
              )
        """)
    nonUniqueItemCount = cur.fetchone()[0]
    return (nonUniqueItemCount == 0)


def getItemByNameIndex(cur, itemNamesAreUnique):
    """
        Generate item name index. If item names are not
        unique, prefix the name with the category id.
    """
    if itemNamesAreUnique:
        cur.execute("SELECT item_id, name FROM item")
        return {
            name: itemID
                for (itemID, name)
                in cur
        }
    else:
        cur.execute("SELECT category_id, item_id, name FROM item")
        return {
            "{}:{}".format(catID, name): itemID
                for (catID, itemID, name)
                 in cur
        }


def genSQLFromPriceLines(priceFile, db, defaultZero, debug=0):
    """
        Yields SQL for populating the database with prices
        by reading the file handle for price lines.
    """

    stationID, categoryID, uiOrder = None, None, 0

    cur = db.cursor()

    systemByName = getSystemByNameIndex(cur)
    categoriesByName = getCategoriesByNameIndex(cur)

    itemNamesAreUnique = testItemNamesUniqueAcrossCategories(cur)
    itemByName = getItemByNameIndex(cur, itemNamesAreUnique)

    defaultUnits = -1 if not defaultZero else 0
    defaultLevel = -1 if not defaultZero else 0

    lineNo = 0

    processedStations = {}
    processedItems = {}
    itemPrefix = ""
    DELETED = corrections.DELETED

    for line in priceFile:
        lineNo += 1
        text = noCommentRe.match(line).group('text').strip()
        # replace whitespace with single spaces
        text = ' '.join(text.split())      # http://stackoverflow.com/questions/2077897
        if not text:
            continue

        ########################################
        ### "@ STAR/Station" lines.
        matches = systemStationRe.match(text)
        if matches:
            ### Change current station
            categoryID, uiOrder = None, 0
            systemName, stationName = matches.group(1, 2)
            facility = systemName.upper() + '/' + stationName

            if debug > 1:
                print("NEW STATION: {}".format(facility))

            # Make sure it's valid.
            try:
                stationID = systemByName[facility]
            except KeyError:
                systemName = corrections.correctSystem(systemName)
                stationName = corrections.correctStation(stationName)
                if systemName == DELETED or stationName == DELETED:
                    if debug > 1:
                        print("- DELETED: {}".format(facility))
                    stationID = DELETED
                    continue
                facility = systemName.upper() + '/' + stationName
                try:
                    stationID = systemByName[facility]
                    if debug > 1:
                        print("- Renamed: {}".format(facility))
                except KeyError:
                    raise UnknownStationError(priceFile, lineNo, facility)

            # Check for duplicates
            if stationID in processedStations:
                raise MultipleStationEntriesError(
                            priceFile, lineNo, facility,
                            processedStations[stationID]
                        )

            processedStations[stationID] = lineNo
            processedItems = {}

            continue
        if not stationID:
            # Need a station to process any other type of line.
            raise SyntaxError(priceFile, lineNo,
                                "Expecting '@ SYSTEM / Station' line", text)
        if stationID == DELETED:
            # Ignore all values from a deleted station/system.
            continue

        ########################################
        ### "+ Category" lines.
        matches = categoryRe.match(text)
        if matches:
            uiOrder = 0
            categoryName = matches.group(1)
            if debug > 1:
                print("NEW CATEGORY: {}".format(categoryName))

            try:
                categoryID = categoriesByName[categoryName]
            except KeyError:
                categoryName = corrections.correctCategory(categoryName)
                if categoryName == DELETED:
                    ### TODO: Determine correct way to handle this.
                    raise SyntaxError("Category has been deleted.")
                try:
                    categoryID = categoriesByName[categoryName]
                    if debug > 1:
                        print("- Renamed: {}".format(categoryName))
                except KeyError:
                    raise UnknownCategoryError(priceFile, lineNo, facility)

            continue
        if not categoryID:
            # Need a category to process any other type of line.
            raise SyntaxError(priceFile, lineNo,
                                "Expecting '+ Category Name' line", text)

        ########################################
        ### "Item sell buy ..." lines.
        matches = itemPriceRe.match(text)
        if not matches:
            matches = newItemPriceRe.match(text)
            if not matches:
                raise SyntaxError(priceFile, lineNo,
                                    "Unrecognized line/syntax", text)

        itemName, modified = matches.group('item', 'time')
        stationPaying = int(matches.group('paying'))
        stationAsking = int(matches.group('asking'))
        demandString, stockString = matches.group('demand', 'stock')
        if demandString and stockString:
            demand = UnitsAndLevel(priceFile, lineNo, 'demand', demandString)
            stock  = UnitsAndLevel(priceFile, lineNo, 'stock',  stockString)
            demandUnits, demandLevel = demand.units, demand.level
            stockUnits, stockLevel = stock.units, stock.level
        else:
            demandUnits, demandLevel = defaultUnits, defaultLevel
            stockUnits, stockLevel = defaultUnits, defaultLevel

        if modified == 'now':
            modified = None         # Use CURRENT_FILESTAMP

        # Look up the item ID.
        itemPrefix = "" if itemNamesAreUnique else "{}:".format(categoryID)
        try:
            itemID = itemByName[itemPrefix + itemName]
        except KeyError:
            oldName = itemName
            itemName = corrections.correctItem(itemName)
            if itemName == DELETED:
                if debug > 1:
                    print("- DELETED {}".format(oldName))
                continue
            try:
                itemID = itemByName[itemPrefix + itemName]
                if debug > 1:
                    print("- Renamed {} -> {}".format(oldName, itemName))
            except KeyError:
                raise UnknownItemError(priceFile, lineNo, itemName)

        # Check for duplicate items within the station.
        if itemID in processedItems:
            raise MultipleItemEntriesError(
                        priceFile, lineNo,
                        "{}/{}".format(categoryName, itemName),
                        processedItems[itemID]
                    )

        processedItems[itemID] = lineNo
        uiOrder += 1

        yield PriceEntry(stationID, itemID, 
                            stationPaying, stationAsking,
                            uiOrder, modified,
                            demandUnits, demandLevel,
                            stockUnits, stockLevel
                        )


######################################################################

def processPricesFile(db, pricesPath, stationID=None, defaultZero=False, debug=0):
    if debug: print("* Processing Prices file '{}'".format(str(pricesPath)))

    if stationID:
        if debug:
            print("* Deleting stale entries for {}".format(stationID))
        db.execute(
            "DELETE FROM Price WHERE station_id = ?",
                [stationID]
        )

    with pricesPath.open() as pricesFile:
        bindValues = []
        for price in genSQLFromPriceLines(pricesFile, db, defaultZero, debug):
            if debug > 2: print(price)
            bindValues += [ price ]
        stmt = """
           INSERT OR REPLACE INTO Price (
                station_id, item_id,
                sell_to, buy_from,
                ui_order, modified,
                demand, demand_level,
                stock, stock_level
            )
           VALUES (
                ?, ?,
                ?, ?,
                ?, IFNULL(?, CURRENT_TIMESTAMP),
                ?, ?,
                ?, ?
            )
        """
        db.executemany(stmt, bindValues)
        db.commit()


######################################################################

def processImportFile(db, importPath, tableName, debug=0):
    if debug:
        print("* Processing import file '{}' for table '{}'". \
                format(str(importPath), tableName)
            )

    fkeySelectStr = "(SELECT {newValue} FROM {table} WHERE {table}.{column} = ?)"

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
                bindColumns.append(splitNames[0])
                bindValues.append('?')
            else:
                # foreign key, we need to make a select
                splitJoin    = splitNames[1].split('.')
                joinTable    = splitJoin[0]
                joinColumn   = splitJoin[1]
                bindColumns.append(joinColumn)
                bindValues.append(
                    fkeySelectStr.format(
                        newValue=splitNames[1],
                        table=joinTable,
                        column=splitNames[0]
                    )
                )
        # now we can make the sql statement
        sql_stmt = """
            INSERT INTO {table} ({columns}) VALUES({values})
        """.format(
                table=tableName,
                columns=','.join(bindColumns),
                values=','.join(bindValues)
            )
        if debug:
            print("* SQL-Statement: {}".format(sql_stmt))

        # import the data
        importCount = 0
        lineNo = 0
        for linein in csvin:
            if len(linein) == columnCount:
                if debug > 1:
                    print("-        Values: {}".format(', '.join(linein)))
                try:
                    db.execute(sql_stmt, linein)
                except Exception as e:
                    raise SystemExit(
                        "*** INTERNAL ERROR: {err}\n"
                        "CSV File: {file}:{line}\n"
                        "SQL Query: {query}\n"
                        "Params: {params}\n"
                        .format(
                            err=str(e),
                            file=str(importPath),
                            line=lineNo,
                            query=sql_stmt.strip(),
                            params=linein
                        )
                    ) from None
                importCount += 1
            ++lineNo
        db.commit()
        if debug:
            print("* {count} {table}s imported". \
                format(count=importCount, table=tableName))


######################################################################

def buildCache(dbPath, sqlPath, pricesPath, importTables, defaultZero=False, debug=0):
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
    if debug:
        print("* Creating temporary database in memory")
    tempDB = sqlite3.connect(':memory:')

    # Read the SQL script so we are ready to populate structure, etc.
    if debug:
        print("* Executing SQL Script '{}' from '{}'".format(sqlPath, os.getcwd()))
    with sqlPath.open() as sqlFile:
        sqlScript = sqlFile.read()
        tempDB.executescript(sqlScript)

    # import standard tables
    for (importName, importTable) in importTables:
        try:
            processImportFile(tempDB, Path(importName), importTable, debug=debug)
        except FileNotFoundError:
            if debug:
                print("WARNING: processImportFile found no {} file". \
                        format(importName))

    # Parse the prices file
    processPricesFile(tempDB, pricesPath, defaultZero=defaultZero, debug=debug)

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


######################################################################

def commandLineBuildCache():
    # Because it looks less sloppy that doing this in if __name__ == '__main__'...
    from tradedb import TradeDB
    dbFilename = TradeDB.defaultDB
    sqlFilename = TradeDB.defaultSQL
    pricesFilename = TradeDB.defaultPrices
    importTables = TradeDB.defaultTables

    # Check command line for -w/--debug inputs.
    import argparse
    parser = argparse.ArgumentParser(
        description='Build TradeDangerous cache file from source files'
    )

    parser.add_argument(
        '--db', default=dbFilename,
        help='Specify database file to build. Default: {}'.format(dbFilename), 
    )
    parser.add_argument(
        '--sql', default=sqlFilename,
        help='Specify SQL script to execute. Default: {}'.format(sqlFilename),
    )
    parser.add_argument(
        '--prices', default=pricesFilename,
        help='Specify the prices file to load. Default: {}'.format(pricesFilename),
    )
    parser.add_argument(
        '-f', '--force', default=False, action='store_true',
        dest='force',
        help='Overwite existing file',
    )
    parser.add_argument(
        '-w', '--debug', dest='debug', default=0, action='count',
        help='Increase level of diagnostic output',
    )
    args = parser.parse_args()

    import pathlib

    # Check that the file doesn't already exist.
    dbPath = pathlib.Path(args.db)
    sqlPath = pathlib.Path(args.sql)
    pricesPath = pathlib.Path(args.prices)
    if not args.force:
        if dbPath.exists():
            print("{}: ERROR: SQLite3 database '{}' already exists. Please remove it first.".format(sys.argv[0], args.db))
            sys.exit(1)

    if not sqlPath.exists():
        print("SQL file '{}' does not exist.".format(args.sql))
        sys.exit(1)

    if not pricesPath.exists():
        print("Prices file '{}' does not exist.".format(args.prices))

    buildCache(dbPath, sqlPath, pricesPath, importTables, debug=args.debug)


if __name__ == '__main__':
    commandLineBuildCache()
