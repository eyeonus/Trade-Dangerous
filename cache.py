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

from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

import re
import sqlite3
import sys
import os
import csv
import math
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
    (?P<sell_to> \d+)
\s+
    # price station is selling item for
    (?P<buy_from> \d+)
"""

# time formats per https://www.sqlite.org/lang_datefunc.html
# YYYY-MM-DD HH:MM:SS
# YYYY-MM-DDTHH:MM:SS
# HH:MM:SS
# 'now'
timeFrag = r'(?P<time>(\d{4}-\d{2}-\d{2}[T ])?\d{2}:\d{2}:\d{2}|now)'

# pre-4.6.0 extended format
# <item name> <sell_to> <buy_from> [ <time> [ demand <units>L<level> stock <units>L<level> ] ]
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


class DuplicateKeyError(BuildCacheBaseException):
    """
        Raised when an item is being redefined.
    """
    def __init__(self, fromFile, lineNo, keyType, keyValue, prevLineNo):
        super().__init__(fromFile, lineNo,
                "Second entry for {keytype} \"{keyval}\", "
                "previous entry at line {prev}.".format(
                    keytype=keyType,
                    keyval=keyValue,
                    prev=prevLineNo
                ))


class MultipleStationEntriesError(DuplicateKeyError):
    """ Raised when a station appears multiple times in the same file. """
    def __init__(self, fromFile, lineNo, facility, prevLineNo):
        super().__init__(fromFile, lineNo, 'station', facility, prevLineNo)


class MultipleItemEntriesError(DuplicateKeyError):
    """ Raised when one item appears multiple times in the same station. """
    def __init__(self, fromFile, lineNo, item, prevLineNo):
        super().__init__(fromFile, lineNo, 'item', item, prevLineNo)


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

class Supply(object):
    """
        Helper class for breaking a units-and-level reading (e.g. -1L-1 or 50@M)
        into units and level values or throwing diagnostic messages to help the
        user figure out what data error was made.
    """
    # Map textual representations of levels back into integer values
    levels = {
        '-1': -1, '?': -1,
        '0': 0, '-': 0,
        'l': 1, 'L': 1, '1': 1,
        'm': 2, 'M': 2, '2': 2,
        'h': 3, 'H': 3, '3': 3,
    }
    # Split a <units>L<level> reading
    splitLRe = re.compile(r'^(\d+)L(-?\d+)$', re.IGNORECASE)
    # Split a <units><level> reading
    splitAtRe = re.compile(r'^(\d+)([\?LMH])$', re.IGNORECASE)

def parseSupply(pricesFile, lineNo, category, reading):
        if reading in ("?", "unk", "UNK", "-1L-1", "-1L0", "0L-1"):
            return (-1, -1)
        elif reading in ("-", "0", "-L-", "n/a", "N/A"):
            return (0, 0)
        else:
            matches = Supply.splitAtRe.match(reading) or \
                        Supply.splitLRe.match(reading)
            if not matches:
                raise SupplyError(
                        pricesFile, lineNo, category,
                        "Expected 'unk', <units>L<level> or <units>[?LMH]",
                        reading
                        )
            units = int(matches.group(1))
            if units < 0:
                raise SupplyError(pricesFile, lineNo, category,
                        "Negative unit quantity. Please use 'unk' for unknown",
                        reading)
            try:
                level = Supply.levels[matches.group(2)]
            except KeyError:
                raise SupplyError(pricesFile, lineNo, category,
                        "Invalid level value", reading)

            return (units, level)


class PriceEntry(namedtuple('PriceEntry', [
                                'stationID', 'itemID',
                                'uiOrder', 'modified',
                                'sellTo', 'demand', 'demandLevel',
                                'buyFrom', 'stock', 'stockLevel',
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
        "{}/{}".format(sysName.upper(), stnName.upper()): ID
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


def genSQLFromPriceLines(tdenv, priceFile, db, defaultZero):
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

    facility = None
    processedStations = {}
    processedItems = {}
    itemPrefix = ""
    DELETED = corrections.DELETED


    def changeStation(matches):
        nonlocal categoryID, uiOrder, facility, stationID
        nonlocal processedStations, processedItems

        ### Change current station
        categoryID, uiOrder = None, 0
        systemName, stationName = matches.group(1, 2)
        facility = systemName.upper() + '/' + stationName.upper()

        tdenv.DEBUG1("NEW STATION: {}", facility)

        # Make sure it's valid.
        try:
            stationID = systemByName[facility]
        except KeyError:
            stationID = -1

        if stationID < 0:
            systemName = corrections.correctSystem(systemName)
            stationName = corrections.correctStation(stationName)
            if systemName == DELETED or stationName == DELETED:
                tdenv.DEBUG1("DELETED: {}", facility)
                stationID = DELETED
            facility = systemName.upper() + '/' + stationName.upper()
            try:
                stationID = systemByName[facility]
                tdenv.DEBUG0("Renamed: {}", facility)
            except KeyError:
                raise UnknownStationError(priceFile, lineNo, facility) from None

        # Check for duplicates
        if stationID in processedStations:
            raise MultipleStationEntriesError(
                        priceFile, lineNo, facility,
                        processedStations[stationID]
                    )

        processedStations[stationID] = lineNo
        processedItems = {}


    def changeCategory(matches):
        nonlocal uiOrder, categoryID

        categoryName, uiOrder = matches.group(1), 0

        tdenv.DEBUG1("NEW CATEGORY: {}", categoryName)

        try:
            categoryID = categoriesByName[categoryName]
            return
        except KeyError:
            pass

        categoryName = corrections.correctCategory(categoryName)
        if categoryName == DELETED:
            ### TODO: Determine correct way to handle this.
            raise SyntaxError("Category has been deleted.")
        try:
            categoryID = categoriesByName[categoryName]
            tdenv.DEBUG1("Renamed: {}", categoryName)
        except KeyError:
            raise UnknownCategoryError(priceFile, lineNo, facility)


    def processItemLine(matches):
        nonlocal uiOrder, processedItems
        itemName, modified = matches.group('item', 'time')
        sellTo = int(matches.group('sell_to'))
        buyFrom = int(matches.group('buy_from'))
        demandString, stockString = matches.group('demand', 'stock')
        if demandString and stockString:
            demandUnits, demandLevel = parseSupply(
                    priceFile, lineNo, 'demand', demandString
            )
            stockUnits, stockLevel = parseSupply(
                    priceFile, lineNo, 'stock',  stockString
            )
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
            itemID = -1
        if itemID < 0:
            print("correcting")
            oldName = itemName
            itemName = corrections.correctItem(itemName)
            if itemName == DELETED:
                tdenv.DEBUG1("DELETED {}", oldName)
                return
            try:
                itemID = itemByName[itemPrefix + itemName]
                tdenv.DEBUG1("Renamed {} -> {}", oldName, itemName)
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

        return PriceEntry(stationID, itemID,
                            uiOrder, modified,
                            sellTo, demandUnits, demandLevel,
                            buyFrom, stockUnits, stockLevel
                        )

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
            changeStation(matches)
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
            changeCategory(matches)
            continue
        if not categoryID:
            # Need a category to process any other type of line.
            raise SyntaxError(priceFile, lineNo,
                                "Expecting '+ Category Name' line", text)

        ########################################
        ### "Item sell buy ..." lines.
        matches = newItemPriceRe.match(text)
        if not matches:
            matches = itemPriceRe.match(text)
            if not matches:
                raise SyntaxError(priceFile, lineNo,
                                    "Unrecognized line/syntax", text)

        sql = processItemLine(matches)
        if sql:
            yield sql


######################################################################

def processPricesFile(tdenv, db, pricesPath, stationID=None, defaultZero=False):
    tdenv.DEBUG0("Processing Prices file '{}'", pricesPath)

    if stationID:
        tdenv.DEBUG0("Deleting stale entries for {}", stationID)
        db.execute(
            "DELETE FROM StationItem WHERE station_id = ?",
                [stationID]
        )

    with pricesPath.open() as pricesFile:
        items, buys, sells = [], [], []
        for price in genSQLFromPriceLines(tdenv, pricesFile, db, defaultZero):
            tdenv.DEBUG2(str(price))
            stnID, itemID = price.stationID, price.itemID
            uiOrder, modified = price.uiOrder, price.modified
            items.append([ stnID, itemID, uiOrder, modified ])
            if uiOrder > 0:
                cr, units, level = price.sellTo, price.demand, price.demandLevel
                if cr > 0 and units != 0 and level != 0:
                    buys.append([ stnID, itemID, cr, units, level, modified ])
                cr, units, level = price.buyFrom, price.stock, price.stockLevel
                if cr > 0 and units != 0 and level != 0:
                    sells.append([ stnID, itemID, cr, units, level, modified ])

        if items:
            db.executemany("""
                        INSERT INTO StationItem
                            (station_id, item_id, ui_order, modified)
                        VALUES (?, ?, ?, IFNULL(?, CURRENT_TIMESTAMP))
                    """, items)
        if sells:
            db.executemany("""
                        INSERT INTO StationSelling
                            (station_id, item_id, price, units, level, modified)
                        VALUES (?, ?, ?, ?, ?, IFNULL(?, CURRENT_TIMESTAMP))
                    """, sells)
        if buys:
            db.executemany("""
                        INSERT INTO StationBuying
                            (station_id, item_id, price, units, level, modified)
                        VALUES (?, ?, ?, ?, ?, IFNULL(?, CURRENT_TIMESTAMP))
                    """, buys)
        db.commit()


######################################################################

def deprecationCheckSystem(line, debug):
    correctSystem = corrections.correctSystem(line[0])
    if correctSystem != line[0]:
        if debug: print("! System.csv: deprecated system: {}".format(line[0]))
        line[0] = correctSystem


def deprecationCheckStation(line, debug):
    correctSystem = corrections.correctSystem(line[0])
    if correctSystem != line[0]:
        if debug: print("! Station.csv: deprecated system: {}".format(line[0]))
        line[0] = correctSystem

    correctStation = corrections.correctStation(line[1])
    if correctStation != line[1]:
        if debug: print("! Station.csv: deprecated station: {}".format(line[1]))
        line[1] = correctStation


def processImportFile(tdenv, db, importPath, tableName):
    tdenv.DEBUG0("Processing import file '{}' for table '{}'", str(importPath), tableName)

    fkeySelectStr = ("("
            "SELECT {newValue}"
            " FROM {table}"
            " WHERE {table}.{column} = ?"
            ")"
    )
    uniquePfx = "unq:"

    with importPath.open() as importFile:
        csvin = csv.reader(importFile, delimiter=',', quotechar="'", doublequote=True)
        # first line must be the column names
        columnDefs = next(csvin)
        columnCount = len(columnDefs)

        # split up columns and values
        # this is necessqary because the insert might use a foreign key
        columnNames = []
        bindColumns = []
        bindValues  = []
        uniqueIndexes = []
        for (cIndex, cName) in enumerate(columnDefs):
            splitNames = cName.split('@')
            # is this a unique index?
            colName = splitNames[0]
            if colName.startswith(uniquePfx):
                uniqueIndexes += [ (cIndex, dict()) ]
                colName = colName[len(uniquePfx):]
            columnNames.append(colName)

            if len(splitNames) == 1:
                # no foreign key, straight insert
                bindColumns.append(colName)
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
                        column=colName,
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
        tdenv.DEBUG0("SQL-Statement: {}", sql_stmt)

        # Check if there is a deprecation check for this table.
        deprecationFn = getattr(sys.modules[__name__],
                                "deprecationCheck"+tableName,
                                None)

        # import the data
        importCount = 0

        for linein in csvin:
            lineNo = csvin.line_num
            if len(linein) == columnCount:
                tdenv.DEBUG1("       Values: {}", ', '.join(linein))
                if deprecationFn: deprecationFn(linein, tdenv.debug)
                for (colNo, index) in uniqueIndexes:
                    colValue = linein[colNo].upper()
                    try:
                        prevLineNo = index[colValue]
                    except KeyError:
                        prevLineNo = 0
                    if prevLineNo:
                        raise DuplicateKeyError(
                                importPath, lineNo,
                                columnNames[colNo], colValue,
                                prevLineNo
                                )
                    index[colValue] = lineNo

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
        db.commit()
        tdenv.DEBUG0("{count} {table}s imported",
                            count=importCount,
                            table=tableName)


def generateStationLink(tdenv, db):
    tdenv.DEBUG0("Generating StationLink table")
    db.create_function("sqrt", 1, math.sqrt)
    db.execute("""
            INSERT INTO StationLink
            SELECT  lhs.system_id AS lhs_system_id,
                    lhs.station_id AS lhs_station_id,
                    rhs.system_id AS rhs_system_id,
                    rhs.station_id AS rhs_station_id,
                    sqrt(
                        ((lSys.pos_x - rSys.pos_x) * (lSys.pos_x - rSys.pos_x)) +
                        ((lSys.pos_y - rSys.pos_y) * (lSys.pos_y - rSys.pos_y)) +
                        ((lSys.pos_z - rSys.pos_z) * (lSys.pos_z - rSys.pos_z))
                        ) AS dist
              FROM  Station AS lhs
                    INNER JOIN System AS lSys
                        ON (lhs.system_id = lSys.system_id),
                    Station AS rhs
                    INNER JOIN System AS rSys
                        ON (rhs.system_id = rSys.system_id)
              WHERE
                    lhs.station_id != rhs.station_id
    """)
    db.commit()


######################################################################

def buildCache(tdenv, dbPath, sqlPath, pricesPath, importTables, defaultZero=False):
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

    dbFilename = str(dbPath)
    # Create an in-memory database to populate with our data.
    tdenv.DEBUG0("Creating temporary database in memory")
    tempDBName = dbFilename + ".new"
    backupDBName = dbFilename  + ".prev"
    tempPath, backupPath = Path(tempDBName), Path(backupDBName)

    if tempPath.exists():
        tempPath.unlink()

    tempDB = sqlite3.connect(tempDBName)
    tempDB.execute("PRAGMA foreign_keys=ON")
    # Read the SQL script so we are ready to populate structure, etc.
    tdenv.DEBUG0("Executing SQL Script '{}' from '{}'", sqlPath, os.getcwd())
    with sqlPath.open() as sqlFile:
        sqlScript = sqlFile.read()
        tempDB.executescript(sqlScript)

    # import standard tables
    for (importName, importTable) in importTables:
        try:
            processImportFile(tdenv, tempDB, Path(importName), importTable)
        except FileNotFoundError:
            tdenv.DEBUG0("WARNING: processImportFile found no {} file", importName)

    # Parse the prices file
    processPricesFile(tdenv, tempDB, pricesPath, defaultZero=defaultZero)

    generateStationLink(tdenv, tempDB)

    tempDB.close()

    tdenv.DEBUG0("Swapping out db files")

    if dbPath.exists():
        if backupPath.exists():
            backupPath.unlink()
        dbPath.rename(backupPath)
    tempPath.rename(dbPath)

    tdenv.DEBUG0("Finished")

