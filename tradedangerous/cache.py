# --------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
# Copyright (C) Bernd 'Gazelle' Gollesch 2016, 2017
# Copyright (C) Jonathan 'eyeonus' Jones 2018
#
# You are free to use, redistribute, or even print and eat a copy of
# this software so long as you include this copyright notice.
# I guarantee there is at least one bug neither of us knew about.
# --------------------------------------------------------------------
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

from collections import namedtuple
from pathlib import Path
from .tradeexcept import TradeException

from . import corrections, utils
import csv
import math
import os
from . import prices
import re
import sqlite3
import sys

######################################################################
# Regular expression patterns. Here be draegons.
# If you add new patterns:
# - use fragments and re.VERBOSE (see itemPriceRe)
# - use named captures (?P<name> ...)
# - include comments

## Match the '@ SYSTEM/Station' line
systemStationRe = re.compile(r'^\@\s*(.*)/(.*)')

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

# <name> <sell> <buy> [ <demand> <supply> [ <time> | now ] ]
qtyLevelFrag = r"""
    unk             # You can just write 'unknown'
|   \?              # alias for unknown
|   n/a             # alias for 0L0
|   -               # alias for 0L0
|   \d+[\?LMH]      # Or <number><level> where level is L(ow), M(ed) or H(igh)
|   0               # alias for n/a
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
        # supply units and level
        (?P<supply> {qtylvl_f})
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

class UnknownSystemError(BuildCacheBaseException):
    """
    Raised when the file contains an unknown star name.
    """
    def __init__(self, fromFile, lineNo, key):
        error = 'Unrecognized SYSTEM: "{}"'.format(key)
        super().__init__(fromFile, lineNo, error)

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
                "{} '{}' is deprecated "
                "and should be replaced with '{}'.".format(
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
            )
        )
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
        )
    )

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

def getItemByNameIndex(cur):
    """
        Generate item name index.
    """
    cur.execute("SELECT item_id, UPPER(name) FROM item")
    return { name: itemID for (itemID, name) in cur }

def processPrices(tdenv, priceFile, db, defaultZero):
    """
        Yields SQL for populating the database with prices
        by reading the file handle for price lines.
    """
    
    DEBUG0, DEBUG1 = tdenv.DEBUG0, tdenv.DEBUG1
    DEBUG0("Processing prices file: {}", priceFile)
    
    cur = db.cursor()
    ignoreUnknown = tdenv.ignoreUnknown
    quiet = tdenv.quiet
    merging = tdenv.mergeImport
    
    systemByName = getSystemByNameIndex(cur)
    stationByName = getStationByNameIndex(cur)
    stationByName.update(
        (sys, ID)
        for sys, ID in corrections.stations.items()
        if isinstance(ID, int)
    )
    sysCorrections = corrections.systems
    stnCorrections = {
        stn: alt
        for stn, alt in corrections.stations.items()
        if isinstance(alt, str)
    }
    
    itemByName = getItemByNameIndex(cur)
    
    defaultUnits = -1 if not defaultZero else 0
    defaultLevel = -1 if not defaultZero else 0
    
    stationID = None
    facility = None
    processedStations = {}
    processedSystems = set()
    processedItems = {}
    stationItemDates = {}
    itemPrefix = ""
    DELETED = corrections.DELETED
    items, zeros, buys, sells = [], [], [], []
    
    lineNo, localAdd = 0, 0
    if not ignoreUnknown:
        def ignoreOrWarn(error):
            raise error
    elif not quiet:
        ignoreOrWarn = tdenv.WARN
    
    def changeStation(matches):
        nonlocal facility, stationID
        nonlocal processedStations, processedItems, localAdd
        nonlocal stationItemDates
        
        ### Change current station
        stationItemDates = {}
        systemNameIn, stationNameIn = matches.group(1, 2)
        systemName, stationName = systemNameIn.upper(), stationNameIn.upper()
        corrected = False
        facility = "/".join((systemName, stationName))
        
        # Make sure it's valid.
        stationID = DELETED
        newID = stationByName.get(facility, -1)
        DEBUG0("Selected station: {}, ID={}", facility, newID)
        if newID is DELETED:
            DEBUG1("DELETED Station: {}", facility)
            return
        if newID < 0:
            if utils.checkForOcrDerp(tdenv, systemName, stationName):
                return
            corrected = True
            altName = sysCorrections.get(systemName, None)
            if altName is DELETED:
                DEBUG1("DELETED System: {}", facility)
                return
            if altName:
                DEBUG1("SYSTEM '{}' renamed '{}'", systemName, altName)
                systemName, facility = altName, "/".join((altName, stationName))
            
            systemID = systemByName.get(systemName, -1)
            if systemID < 0:
                ignoreOrWarn(
                    UnknownSystemError(priceFile, lineNo, facility)
                )
                return
            
            altStation = stnCorrections.get(facility, None)
            if altStation is DELETED:
                DEBUG1("DELETED Station: {}", facility)
                return
            if altStation:
                DEBUG1("Station '{}' renamed '{}'", facility, altStation)
                stationName = altStation.upper()
                facility = "/".join((systemName, stationName))
            
            newID = stationByName.get(facility, -1)
            if newID is DELETED:
                DEBUG1("Renamed station DELETED: {}", facility)
                return
            
        if newID < 0:
            if not ignoreUnknown:
                ignoreOrWarn(
                        UnknownStationError(priceFile, lineNo, facility)
                )
                return
            name = utils.titleFixup(stationName)
            inscur = db.cursor()
            inscur.execute("""
                INSERT INTO Station (
                    system_id, name,
                    ls_from_star,
                    blackmarket,
                    max_pad_size,
                    market,
                    shipyard,
                    modified
                ) VALUES (
                    ?, ?, 0, '?', '?', '?', '?',
                    DATETIME('now')
                )
            """, [systemID, name])
            newID = inscur.lastrowid
            stationByName[facility] = newID
            tdenv.NOTE("Added local station placeholder for {} (#{})",
                    facility, newID
            )
            localAdd += 1
        elif newID in processedStations:
            # Check for duplicates
            if not corrected:
                raise MultipleStationEntriesError(
                    priceFile, lineNo, facility,
                    processedStations[newID]
                )
        
        stationID = newID
        processedSystems.add(systemName)
        processedStations[stationID] = lineNo
        processedItems = {}
        
        cur = db.execute("""
            SELECT item_id, modified
              FROM StationItem
             WHERE station_id = ?
        """, [stationID])
        stationItemDates = {ID: modified for ID, modified in cur}
    
    addItem, addZero = items.append, zeros.append
    getItemID = itemByName.get
    newItems, updtItems, ignItems = 0, 0, 0
    
    def processItemLine(matches):
        nonlocal newItems, updtItems, ignItems
        itemName, modified = matches.group('item', 'time')
        itemName = itemName.upper()
        
        # Look up the item ID.
        itemID = getItemID(itemName, -1)
        if itemID < 0:
            oldName = itemName
            itemName = corrections.correctItem(itemName)
            if itemName == DELETED:
                DEBUG1("DELETED {}", oldName)
                return
            itemName = itemName.upper()
            itemID = getItemID(itemName, -1)
            if itemID < 0:
                ignoreOrWarn(
                    UnknownItemError(priceFile, lineNo, itemName)
                )
                return
            DEBUG1("Renamed {} -> {}", oldName, itemName)
        
        lastModified = stationItemDates.get(itemID, None)
        if lastModified and merging:
            if modified and modified != 'now' and modified <= lastModified:
                DEBUG1("Ignoring {} @ {}: {} <= {}".format(
                    itemName, facility,
                    modified, lastModified,
                ))
                if modified < lastModified:
                    ignItems += 1
                return
        
        # Check for duplicate items within the station.
        if itemID in processedItems:
            ignoreOrWarn(
                MultipleItemEntriesError(
                    priceFile, lineNo,
                    "{}".format(itemName),
                    processedItems[itemID]
                )
            )
            return
        
        demandCr, supplyCr = matches.group('sell', 'buy')
        demandCr, supplyCr = int(demandCr), int(supplyCr)
        demandString, supplyString = matches.group('demand', 'supply')
        
        if demandCr == 0 and supplyCr == 0:
            if lastModified:
                addZero((stationID, itemID))
        else:
            if lastModified:
                updtItems += 1
            else:
                newItems += 1
            if demandString:
                if demandString == "?":
                    demandUnits, demandLevel = -1, -1
                elif demandString == "-":
                    demandUnits, demandLevel = 0, 0
                else:
                    demandUnits, demandLevel = parseSupply(
                        priceFile, lineNo, 'demand', demandString
                    )
            else:
                demandUnits, demandLevel = defaultUnits, defaultLevel
            
            if demandString and supplyString:
                    if supplyString == "?":
                        supplyUnits, supplyLevel = -1, -1
                    elif supplyString == "-":
                        supplyUnits, supplyLevel = 0, 0
                    else:
                        supplyUnits, supplyLevel = parseSupply(
                            priceFile, lineNo, 'supply',  supplyString
                        )
            else:
                supplyUnits, supplyLevel = defaultUnits, defaultLevel
            
            if modified == 'now':
                modified = None         # Use CURRENT_FILESTAMP
            
            addItem((
                stationID, itemID, modified,
                demandCr, demandUnits, demandLevel,
                supplyCr, supplyUnits, supplyLevel,
            ))
        
        processedItems[itemID] = lineNo
    
    for line in priceFile:
        lineNo += 1
        text, _, comment = line.partition('#')
        text = text.strip()
        if not text:
            continue
        
        # replace whitespace with single spaces
        if text.find("  "):
            # http://stackoverflow.com/questions/2077897
            text = ' '.join(text.split())
        
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
        ### "+ Category" lines
        if text.startswith('+'):
            # we now ignore these.
            continue
        
        ########################################
        ### "Item sell buy ..." lines.
        matches = newItemPriceRe.match(text)
        if not matches:
            raise SyntaxError(priceFile, lineNo,
                        "Unrecognized line/syntax", text)
        
        processItemLine(matches)
    
    numSys = len(processedSystems)
    
    if localAdd > 0:
        tdenv.NOTE(
            "Placeholder stations are added to the local DB only "
            "(not the .CSV).\n"
            "Use 'trade.py export --table Station' "
            "if you /need/ to persist them."
        )
    
    stations = tuple((ID,) for ID in processedStations.keys())
    return stations, items, zeros, newItems, updtItems, ignItems, numSys

######################################################################

def processPricesFile(tdenv, db, pricesPath, pricesFh=None, defaultZero=False):
    tdenv.DEBUG0("Processing Prices file '{}'", pricesPath)
    
    with pricesFh or pricesPath.open('rU', encoding='utf-8') as pricesFh:
        stations, items, zeros, newItems, updtItems, ignItems, numSys = processPrices(
            tdenv, pricesFh, db, defaultZero
        )
    
    if not tdenv.mergeImport:
        db.executemany("""
            DELETE FROM StationItem
             WHERE station_id = ?
        """, stations)
    if zeros:
        db.executemany("""
            DELETE FROM StationItem
             WHERE station_id = ?
               AND item_id = ?
        """, zeros)
    removedItems = len(zeros)
    
    if items:
        db.executemany("""
            INSERT OR REPLACE INTO StationItem (
                station_id, item_id, modified,
                demand_price, demand_units, demand_level,
                supply_price, supply_units, supply_level
            ) VALUES (
                ?, ?, IFNULL(?, CURRENT_TIMESTAMP),
                ?, ?, ?,
                ?, ?, ?
            )
        """, items)
    updatedItems = len(items)
    
    tdenv.DEBUG0("Marking populated stations as having a market")
    db.execute(
        "UPDATE Station SET market = 'Y'"
        " WHERE EXISTS"
            " (SELECT station_id FROM StationItem"
              " WHERE StationItem.station_id = Station.station_id"
             ")"
    )
    
    db.commit()
    
    changes = " and ".join("{} {}".format(v, k) for k, v in {
        "new": newItems,
        "updated": updtItems,
        "removed": removedItems,
    }.items() if v) or "0"
    
    tdenv.NOTE(
        "Import complete: "
            "{:s} items "
            "over {:n} stations "
            "in {:n} systems",
                changes,
                len(stations),
                numSys,
    )
    
    if ignItems:
        tdenv.NOTE("Ignored {} items with old data", ignItems)

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
    tdenv.DEBUG0(
        "Processing import file '{}' for table '{}'",
        str(importPath), tableName
    )
    
    fkeySelectStr = ("("
            "SELECT {newValue}"
            " FROM {table}"
            " WHERE {stmt}"
            ")"
    )
    uniquePfx = "unq:"
    uniqueLen = len(uniquePfx)
    ignorePfx = "!"
    
    with importPath.open('rU', encoding='utf-8') as importFile:
        csvin = csv.reader(
            importFile, delimiter=',', quotechar="'", doublequote=True
        )
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
            colName, _, srcKey = cName.partition('@')
            # is this a unique index?
            if colName.startswith(uniquePfx):
                uniqueIndexes.append(cIndex)
                colName = colName[uniqueLen:]
            if not srcKey:
                # no foreign key, straight insert
                bindColumns.append(colName)
                bindValues.append('?')
                continue
            
            queryTab, _, queryCol = srcKey.partition('.')
            if colName.startswith(ignorePfx):
                # this column is only used to resolve an FK
                assert srcKey
                colName = colName[len(ignorePfx):]
                joinHelper.append((colName, queryTab, queryCol))
                continue
            
            # foreign key, we need to make a select
            joinTable = [ queryTab ]
            joinStmt  = []
            for nextCol, nextTab, nextJoin in joinHelper:
                joinTable.append(
                    "INNER JOIN {} USING({})".format(nextTab, nextJoin)
                )
                joinStmt.append(
                    "{}.{} = ?".format(nextTab, nextCol)
                )
            joinHelper = []
            joinStmt.append("{}.{} = ?".format(queryTab, colName))
            bindColumns.append(queryCol)
            bindValues.append(
                fkeySelectStr.format(
                    newValue=srcKey,
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
        deprecationFn = getattr(
            sys.modules[__name__],
            "deprecationCheck"+tableName,
            None
        )
        
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
                    prevLineNo = uniqueIndex.get(key, 0)
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
        "Rebuilding cache file: this may take a few moments.",
        file=sys.stderr
    )
    
    dbPath = tdb.dbPath
    sqlPath = tdb.sqlPath
    pricesPath = tdb.pricesPath
    
    # Create an in-memory database to populate with our data.
    tempPath = dbPath.with_suffix(".new")
    backupPath = dbPath.with_suffix(".old")
    
    if tempPath.exists():
        tempPath.unlink()
    
    tempDB = sqlite3.connect(str(tempPath))
    tempDB.execute("PRAGMA foreign_keys=ON")
    # Read the SQL script so we are ready to populate structure, etc.
    tdenv.DEBUG0("Executing SQL Script '{}' from '{}'", sqlPath, os.getcwd())
    with sqlPath.open('rU', encoding='utf-8') as sqlFile:
        sqlScript = sqlFile.read()
        tempDB.executescript(sqlScript)
    
    # import standard tables
    for (importName, importTable) in tdb.importTables:
        try:
            processImportFile(tdenv, tempDB, Path(importName), importTable)
        except FileNotFoundError:
            tdenv.DEBUG0(
                "WARNING: processImportFile found no {} file", importName
            )
        except StopIteration:
            tdenv.NOTE(
                "{} exists but is empty. "
                "Remove it or add the column definition line.",
                importName
            )
    
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
    
    with tdb.pricesPath.open("w", encoding='utf-8') as pricesFile:
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
        with tdb.getDB() as db:
            db.execute("DELETE FROM StationItem")
            db.commit()
    
    tdenv.DEBUG0("Importing data from {}".format(str(path)))
    processPricesFile(tdenv,
            db=tdb.getDB(),
            pricesPath=path,
            pricesFh=pricesFh,
            )
    
    # If everything worked, we may need to re-build the prices file.
    if path != tdb.pricesPath:
        regeneratePricesFile(tdb, tdenv)
