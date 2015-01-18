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

from collections import namedtuple
from pathlib import Path
from tradeexcept import TradeException

import corrections
import csv
import math
import os
import prices
import re
import sqlite3
import sys
import tradedb

######################################################################
# Regular expression patterns. Here be draegons.
# If you add new patterns:
# - use fragments and re.VERBOSE (see itemPriceRe)
# - use named captures (?P<name> ...)
# - include comments

## Match the '@ SYSTEM/Station' line
systemStationRe = re.compile(r'^\@\s*(.*)/(.*)')

## Match the '+ Category' line
categoryRe = re.compile(r'^\+\s*(.*)')

## Price Line matching

# first part of any prices line is the item name and paying/asking price
itemPriceFrag = r"""
    # match item name, allowing spaces in the name
    (?P<item> .*?)
\s+
    # price station is buying the item for
    (?P<sell> \d+)
\s+
    # price station is selling item for
    (?P<buy> \d+)
"""

# time formats per https://www.sqlite.org/lang_datefunc.html
# YYYY-MM-DD HH:MM:SS
# YYYY-MM-DDTHH:MM:SS
# HH:MM:SS
# 'now'
timeFrag = r'(?P<time>(\d{4}-\d{2}-\d{2}[T ])?\d{2}:\d{2}:\d{2}|now)'

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
    (
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
        self.category = "ERROR"
        self.error = error or "UNKNOWN ERROR"

    def __str__(self):
        return "{}:{} {} {}".format(
                self.fileName, self.lineNo,
                self.category,
                self.error,
        )


class UnknownStationError(BuildCacheBaseException):
    """
        Raised when the file contains an unknown star/station name.
    """
    def __init__(self, fromFile, lineNo, key):
        error = 'Unrecognized STAR/Station: "{}"'.format(key)
        super().__init__(fromFile, lineNo, error)

class UnknownItemError(BuildCacheBaseException):
    """
        Raised in the case of an item name that we don't know.
        Attributes:
            itemName   Key we tried to look up.
    """
    def __init__(self, fromFile, lineNo, itemName):
        error = 'Unrecognized item name: "{}"'.format(itemName)
        super().__init__(fromFile, lineNo, error)

class UnknownCategoryError(BuildCacheBaseException):
    """
        Raised in the case of a categrory name that we don't know.
        Attributes:
            categoryName   Key we tried to look up.
    """
    def __init__(self, fromFile, lineNo, categoryName):
        error = 'Unrecognized category name: "{}"'.format(categoryName)
        super().__init__(fromFile, lineNo, error)


class DuplicateKeyError(BuildCacheBaseException):
    """
        Raised when an item is being redefined.
    """
    def __init__(self, fromFile, lineNo, keyType, keyValue, prevLineNo):
        super().__init__(fromFile, lineNo,
                "Second occurrance of {keytype} \"{keyval}\", "
                "previous entry at line {prev}.".format(
                    keytype=keyType,
                    keyval=keyValue,
                    prev=prevLineNo
                ))


class DeletedKeyError(BuildCacheBaseException):
    """
    Raised when a key value in a .csv file is marked as DELETED in the
    corrections file.
    """
    def __init__(self, fromFile, lineNo, keyType, keyValue):
        super().__init__(fromFile, lineNo,
                "{} '{}' is marked as DELETED and should not be used.".format(
                    keyType, keyValue
        ))


class DeprecatedKeyError(BuildCacheBaseException):
    """
    Raised when a key value in a .csv file has a correction; the old
    name should not appear in the .csv file.
    """
    def __init__(self, fromFile, lineNo, keyType, keyValue, newValue):
        super().__init__(fromFile, lineNo,
                "{} '{}' is deprecated and should be replaced with '{}'.".format(
                    keyType, keyValue, newValue
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

def parseSupply(pricesFile, lineNo, category, reading):
    units, level = reading[0:-1], reading[-1]
    levelNo = "??LMH".find(level.upper()) -1
    if levelNo < -1:
        raise SupplyError(
                    pricesFile, lineNo, category, reading,
                    'Unrecognized level suffix: "{}": '
                    "expected one of 'L', 'M', 'H' or '?'".format(
                        level
                ))
    try:
        unitsNo = int(units)
        if unitsNo < 0:
            raise ValueError("unsigned unit count")
        if unitsNo == 0:
            return 0, 0
        return unitsNo, levelNo
    except ValueError:
        pass

    raise SupplyError(
                pricesFile, lineNo, category, reading,
                'Unrecognized units/level value: "{}": '
                "expected '-', '?', or a number followed "
                "by a level (L, M, H or ?).".format(
                    level
            ))


######################################################################
# Code
######################################################################

def getSystemByNameIndex(cur):
    """ Build station index in STAR/Station notation """
    cur.execute("""
            SELECT system_id, UPPER(system.name)
              FROM System
        """)
    return { name: ID for (ID, name) in cur }


def getStationByNameIndex(cur):
    """ Build station index in STAR/Station notation """
    cur.execute("""
            SELECT station_id,
                    UPPER(system.name) || '/' || UPPER(station.name)
              FROM System
                   INNER JOIN Station
                      USING (system_id)
        """)
    return { name: ID for (ID, name) in cur }


def getCategoriesByNameIndex(cur):
    """ Build category name => id index """
    cur.execute("SELECT category_id, name FROM category")
    return { name: ID for (ID, name) in cur }


def getItemByNameIndex(cur):
    """
        Generate item name index.
        unique, prefix the name with the category id.
    """
    cur.execute("SELECT item_id, name FROM item")
    return { name: itemID for (itemID, name) in cur }


def processPrices(tdenv, priceFile, db, defaultZero):
    """
        Yields SQL for populating the database with prices
        by reading the file handle for price lines.
    """

    stationID, categoryID = None, None

    cur = db.cursor()
    ignoreUnknown = tdenv.ignoreUnknown
    quiet = tdenv.quiet

    systemByName = getSystemByNameIndex(cur)
    stationByName = getStationByNameIndex(cur)
    categoriesByName = getCategoriesByNameIndex(cur)

    itemByName = getItemByNameIndex(cur)

    defaultUnits = -1 if not defaultZero else 0
    defaultLevel = -1 if not defaultZero else 0

    lineNo = 0

    categoryName = None
    facility = None
    processedStations = {}
    processedSystems = set()
    processedItems = {}
    itemPrefix = ""
    DELETED = corrections.DELETED
    items, buys, sells = [], [], []

    warnings = 0

    def ignoreOrWarn(error):
        nonlocal warnings
        if not ignoreUnknown:
            raise error
        if not quiet:
            error.category = "WARNING"
            print(error)
        warnings += 1


    def changeStation(matches):
        nonlocal categoryID, facility, stationID
        nonlocal processedStations, processedItems

        ### Change current station
        categoryID = None
        systemNameIn, stationNameIn = matches.group(1, 2)
        systemName, stationName = systemNameIn.upper(), stationNameIn.upper()
        corrected = False
        facility = systemName + '/' + stationName

        tdenv.DEBUG0("NEW STATION: {}", facility)

        # Make sure it's valid.
        try:
            stationID = stationByName[facility]
        except KeyError:
            stationID = -1

        if stationID < 0:
            corrected = True
            try:
                correctName = corrections.systems[systemName]
                if correctName == DELETED:
                    tdenv.DEBUG1("DELETED: {}", systemName)
                    stationID = DELETED
                    return
                systemName = correctName.upper()
            except KeyError:
                pass
            try:
                key = systemName + '/' + stationName
                correctName = corrections.stations[key]
                if correctName == DELETED:
                    tdenv.DEBUG1("DELETED: {}", key)
                    stationID = DELETED
                    return
                stationName = correctName.upper()
            except KeyError:
                pass
            facility = systemName + '/' + stationName
            try:
                stationID = stationByName[facility]
                tdenv.DEBUG1("Renamed: {}/{} -> {}", 
                        systemNameIn, stationNameIn,
                        facility
                )
            except KeyError:
                stationID = -1

        if stationID < 0 and ignoreUnknown:
            try:
                systemID = systemByName[systemName]
            except KeyError:
                pass
            else:
                name = tradedb.TradeDB.titleFixup(stationName)
                inscur = db.cursor()
                inscur.execute("""
                    INSERT INTO Station (
                        system_id, name, ls_from_star, blackmarket, max_pad_size
                    ) VALUES (
                        ?, ?, 0, '?', '?'
                    )
                """, [systemID, name])
                stationID = inscur.lastrowid
                stationByName[facility] = stationID
                db.commit()
                tdenv.NOTE("Added local station placeholder for {} (#{})",
                        facility, stationID
                )

        if stationID < 0:
            stationID = DELETED
            ignoreOrWarn(
                    UnknownStationError(priceFile, lineNo, facility)
            )
            return

        # Check for duplicates
        if stationID in processedStations:
            if corrected:
                # This is probably the old entry.
                stationID = DELETED
                return
            raise MultipleStationEntriesError(
                        priceFile, lineNo, facility,
                        processedStations[stationID]
                    )

        processedSystems.add(systemName)
        processedStations[stationID] = lineNo
        processedItems = {}

        # Clear old entries for this station.
        db.execute(
            "DELETE FROM StationItem WHERE station_id = ?",
                [stationID]
        )


    def changeCategory(matches):
        nonlocal categoryID, categoryName

        categoryName = matches.group(1)

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
            categoryID = DELETED
            ignoreOrWarn(
                UnknownCategoryError(priceFile, lineNo, categoryName)
            )
            return


    def processItemLine(matches):
        nonlocal processedItems
        nonlocal items, buys, sells
        itemName, modified = matches.group('item', 'time')

        # Look up the item ID.
        try:
            itemID = itemByName[itemName]
        except KeyError:
            itemID = -1
        if itemID < 0:
            oldName = itemName
            itemName = corrections.correctItem(itemName)
            if itemName == DELETED:
                tdenv.DEBUG1("DELETED {}", oldName)
                return
            try:
                itemID = itemByName[itemName]
                tdenv.DEBUG1("Renamed {} -> {}", oldName, itemName)
            except KeyError:
                ignoreOrWarn(
                    UnknownItemError(priceFile, lineNo, itemName)
                )
                return

        # Check for duplicate items within the station.
        if itemID in processedItems:
            raise MultipleItemEntriesError(
                        priceFile, lineNo,
                        "{}/{}".format(categoryName, itemName),
                        processedItems[itemID]
                    )

        sellTo, buyFrom = matches.group('sell', 'buy')
        sellTo, buyFrom = int(sellTo), int(buyFrom)
        demandString, stockString = matches.group('demand', 'stock')
        if demandString and stockString:
            if demandString == "?":
                demandUnits, demandLevel = -1, -1
            elif demandString == "-":
                demandUnits, demandLevel = 0, 0
            else:
                demandUnits, demandLevel = parseSupply(
                        priceFile, lineNo, 'demand', demandString
                )
            if stockString == "?":
                stockUnits, stockLevel = -1, -1
            elif stockString == "-":
                stockUnits, stockLevel = 0, 0
            else:
                stockUnits, stockLevel = parseSupply(
                        priceFile, lineNo, 'stock',  stockString
                )
        else:
            demandUnits, demandLevel = defaultUnits, defaultLevel
            stockUnits, stockLevel = defaultUnits, defaultLevel

        if modified == 'now':
            modified = None         # Use CURRENT_FILESTAMP

        processedItems[itemID] = lineNo

        items.append([ stationID, itemID, modified ])
        if sellTo > 0 and demandUnits != 0 and demandLevel != 0:
            buys.append([
                        stationID, itemID,
                        sellTo, demandUnits, demandLevel,
                        modified
                    ])
        if buyFrom > 0 and stockUnits != 0 and stockLevel != 0:
            sells.append([
                        stationID, itemID,
                        buyFrom, stockUnits, stockLevel,
                        modified
                    ])

    for line in priceFile:
        lineNo += 1
        commentPos = line.find("#")
        if commentPos >= 0:
            if commentPos == 0:
                continue
            line = line[:commentPos]
        text = line.strip()

        if not text:
            continue

        # replace whitespace with single spaces
        if text.find("  "):
            text = ' '.join(text.split())      # http://stackoverflow.com/questions/2077897

        ########################################
        ### "@ STAR/Station" lines.
        if text.startswith('@'):
            matches = systemStationRe.match(text)
            if not matches:
                raise SyntaxError("Unrecognized '@' line: {}".format(
                            text
                        ))
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
        if text.startswith('+'):
            matches = categoryRe.match(text)
            if not matches:
                    raise SyntaxError("Unrecognized '+' line: {}".format(
                                text
                            ))
            changeCategory(matches)
            continue
        if not categoryID:
            # Need a category to process any other type of line.
            raise SyntaxError(priceFile, lineNo,
                                "Expecting '+ Category Name' line", text)

        if categoryID == DELETED:
            continue

        ########################################
        ### "Item sell buy ..." lines.
        matches = newItemPriceRe.match(text)
        if not matches:
            raise SyntaxError(priceFile, lineNo,
                        "Unrecognized line/syntax", text)

        processItemLine(matches)


    numSys = len(processedSystems)
    numStn = len(processedStations)

    return warnings, items, buys, sells, numSys, numStn


######################################################################

def processPricesFile(tdenv, db, pricesPath, pricesFh=None, defaultZero=False):
    tdenv.DEBUG0("Processing Prices file '{}'", pricesPath)

    with pricesFh or pricesPath.open('rU') as pricesFh:
        warnings, items, buys, sells, numSys, numStn = processPrices(
                tdenv, pricesFh, db, defaultZero
        )
 
    if items:
        db.executemany("""
                    INSERT INTO StationItem
                        (station_id, item_id, modified)
                    VALUES (?, ?, IFNULL(?, CURRENT_TIMESTAMP))
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

    tdenv.NOTE(
            "Import complete: "
                "{:n} items ({:n} buyers, {:n} sellers) "
                "for {:n} stations "
                "in {:n} systems",
                    len(items),
                    len(buys), len(sells),
                    numStn,
                    numSys,
    )


######################################################################


def depCheck(importPath, lineNo, depType, key, correctKey):
    if correctKey == key:
        return
    if correctKey == corrections.DELETED:
        raise DeletedKeyError(importPath, lineNo, depType, key)
    raise DeprecatedKeyError(importPath, lineNo, depType, key, correctKey)


def deprecationCheckSystem(importPath, lineNo, line):
    depCheck(
        importPath, lineNo, 'System',
        line[0], corrections.correctSystem(line[0]),
    )


def deprecationCheckStation(importPath, lineNo, line):
    depCheck(
        importPath, lineNo, 'System',
        line[0], corrections.correctSystem(line[0]),
    )
    depCheck(
        importPath, lineNo, 'Station',
        line[1], corrections.correctStation(line[0], line[1]),
    )


def deprecationCheckCategory(importPath, lineNo, line):
    depCheck(
        importPath, lineNo, 'Category',
        line[0], corrections.correctCategory(line[0]),
    )


def deprecationCheckItem(importPath, lineNo, line):
    depCheck(
        importPath, lineNo, 'Category',
        line[0], corrections.correctCategory(line[0]),
    )
    depCheck(
        importPath, lineNo, 'Item',
        line[1], corrections.correctItem(line[1]),
    )


def processImportFile(tdenv, db, importPath, tableName):
    tdenv.DEBUG0("Processing import file '{}' for table '{}'", str(importPath), tableName)

    fkeySelectStr = ("("
            "SELECT {newValue}"
            " FROM {table}"
            " WHERE {stmt}"
            ")"
    )
    uniquePfx = "unq:"
    ignorePfx = "!"

    with importPath.open('rU', encoding='utf-8') as importFile:
        csvin = csv.reader(importFile, delimiter=',', quotechar="'", doublequote=True)
        # first line must be the column names
        columnDefs = next(csvin)
        columnCount = len(columnDefs)

        # split up columns and values
        # this is necessqary because the insert might use a foreign key
        bindColumns = []
        bindValues  = []
        joinHelper  = []
        uniqueIndexes = []
        for (cIndex, cName) in enumerate(columnDefs):
            splitNames = cName.split('@')
            # is this a unique index?
            colName = splitNames[0]
            if colName.startswith(uniquePfx):
                uniqueIndexes += [ cIndex ]
                colName = colName[len(uniquePfx):]
            if colName.startswith(ignorePfx):
                # this column is only used to resolve an FK
                colName = colName[len(ignorePfx):]
                joinHelper.append( "{}@{}".format(colName, splitNames[1]) )
                continue

            if len(splitNames) == 1:
                # no foreign key, straight insert
                bindColumns.append(colName)
                bindValues.append('?')
            else:
                # foreign key, we need to make a select
                splitJoin = splitNames[1].split('.')
                joinTable = [ splitJoin[0] ]
                joinStmt  = []
                for joinRow in joinHelper:
                    helperNames = joinRow.split('@')
                    helperJoin = helperNames[1].split('.')
                    joinTable.append( "INNER JOIN {} USING({})".format(helperJoin[0], helperJoin[1]) )
                    joinStmt.append( "{}.{} = ?".format(helperJoin[0], helperNames[0]) )
                joinHelper = []
                joinStmt.append("{}.{} = ?".format(splitJoin[0], colName))
                bindColumns.append(splitJoin[1])
                bindValues.append(
                    fkeySelectStr.format(
                        newValue=splitNames[1],
                        table=" ".join(joinTable),
                        stmt=" AND ".join(joinStmt),
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
        uniqueIndex = dict()

        for linein in csvin:
            if not linein:
                continue
            lineNo = csvin.line_num
            if len(linein) == columnCount:
                tdenv.DEBUG1("       Values: {}", ', '.join(linein))
                if deprecationFn:
                    try:
                        deprecationFn(importPath, lineNo, linein)
                    except (DeprecatedKeyError, DeletedKeyError) as e:
                        if not tdenv.ignoreUnknown:
                            raise e
                        e.category = "WARNING"
                        tdenv.NOTE("{}", e)
                        continue
                if uniqueIndexes:
                    # Need to construct the actual unique index key as
                    # something less likely to collide with manmade
                    # values when it's a compound.
                    keyValues = [
                            str(linein[col]).upper()
                            for col in uniqueIndexes
                            ]
                    key = ":!:".join(keyValues)
                    try:
                        prevLineNo = uniqueIndex[key]
                    except KeyError:
                        prevLineNo = 0
                    if prevLineNo:
                        # Make a human-readable key
                        key = "/".join(keyValues)
                        raise DuplicateKeyError(
                                importPath, lineNo,
                                "entry", key,
                                prevLineNo
                                )
                    uniqueIndex[key] = lineNo

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
            else:
                tdenv.NOTE(
                        "Wrong number of columns ({}:{}): {}",
                            importPath,
                            lineNo,
                            ', '.join(linein)
                )
        db.commit()
        tdenv.DEBUG0("{count} {table}s imported",
                            count=importCount,
                            table=tableName)



######################################################################

def buildCache(tdb, tdenv):
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

    tdenv.NOTE(
            "Rebuilding cache file: this may take a moment.",
            file=sys.stderr
    )

    dbPath = tdb.dbPath
    sqlPath = tdb.sqlPath
    pricesPath = tdb.pricesPath

    # Create an in-memory database to populate with our data.
    tempPath = dbPath.with_suffix(".new")
    backupPath = dbPath.with_suffix(".prev")

    if tempPath.exists():
        tempPath.unlink()

    tempDB = sqlite3.connect(str(tempPath))
    tempDB.execute("PRAGMA foreign_keys=ON")
    # Read the SQL script so we are ready to populate structure, etc.
    tdenv.DEBUG0("Executing SQL Script '{}' from '{}'", sqlPath, os.getcwd())
    with sqlPath.open('rU') as sqlFile:
        sqlScript = sqlFile.read()
        tempDB.executescript(sqlScript)

    # import standard tables
    for (importName, importTable) in tdb.importTables:
        try:
            processImportFile(tdenv, tempDB, Path(importName), importTable)
        except FileNotFoundError:
            tdenv.DEBUG0("WARNING: processImportFile found no {} file", importName)
        except StopIteration:
            tdenv.NOTE("{} exists but is empty. Remove it or add the column definition line.", importName)

    # Parse the prices file
    if pricesPath.exists():
        processPricesFile(tdenv, tempDB, pricesPath)
    else:
        tdenv.NOTE(
                "Missing \"{}\" file - no price data.",
                    pricesPath,
                    file=sys.stderr,
        )

    tempDB.commit()
    tempDB.close()

    tdenv.DEBUG0("Swapping out db files")

    if dbPath.exists():
        if backupPath.exists():
            backupPath.unlink()
        dbPath.rename(backupPath)
    tempPath.rename(dbPath)

    tdenv.DEBUG0("Finished")

######################################################################

def regeneratePricesFile(tdb, tdenv):
    tdenv.DEBUG0("Regenerating .prices file")

    with tdb.pricesPath.open("w") as pricesFile:
        prices.dumpPrices(
                tdb.dbFilename,
                prices.Element.full,
                file=pricesFile,
                debug=tdenv.debug)

    # Update the DB file so we don't regenerate it.
    os.utime(tdb.dbFilename)

######################################################################

def importDataFromFile(tdb, tdenv, path, pricesFh=None, reset=False):
    """
        Import price data from a file on a per-station basis,
        that is when a new station is encountered, delete any
        existing records for that station in the database.
    """

    if not pricesFh and not path.exists():
        raise TradeException("No such file: {}".format(
                    str(path)
                ))

    if reset:
        tdenv.DEBUG0("Resetting price data")
        tdb.getDB().execute("DELETE FROM StationItem")

    tdenv.DEBUG0("Importing data from {}".format(str(path)))
    processPricesFile(tdenv,
            db=tdb.getDB(),
            pricesPath=path,
            pricesFh=pricesFh,
            )

    # If everything worked, we may need to re-build the prices file.
    if path != tdb.pricesPath:
        regeneratePricesFile(tdb, tdenv)
