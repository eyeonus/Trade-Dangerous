# --------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
# Copyright (C) Bernd 'Gazelle' Gollesch 2016, 2017
# Copyright (C) Stefan 'Tromador' Morrell 2025
# Copyright (C) Jonathan 'eyeonus' Jones 2018-2025
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
#   a source repository. -- DEPRECATED [eyeonus]
#

from __future__ import annotations

from pathlib import Path
import csv
import os
import re
import typing


from functools import partial as partial_fn
from sqlalchemy import func, tuple_
from sqlalchemy.orm import Session
from tradedangerous.db import orm_models as SA
from tradedangerous.db import lifecycle
from tradedangerous.db.utils import parse_ts

from .fs import file_line_count
from .tradeexcept import TradeException
from tradedangerous.misc.progress import Progress, CountingBar
from . import corrections, utils



# For mypy/pylint type checking
if typing.TYPE_CHECKING:
    from typing import Any, Callable, Optional, TextIO
    
    from .tradedb import TradeDB
    from .tradeenv import TradeEnv


######################################################################
# Regular expression patterns. Here be draegons.
# If you add new patterns:
# - use fragments and re.VERBOSE (see itemPriceRe)
# - use named captures (?P<name> ...)
# - include comments

# # Match the '@ SYSTEM/Station' line
systemStationRe = re.compile(r'^\@\s*(.*)/(.*)')

# # Price Line matching

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
""".format(base_f = itemPriceFrag, qtylvl_f = qtyLevelFrag, time_f = timeFrag),
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
    
    def __init__(self, fromFile: Path, lineNo: int, error: str | None = None) -> None:
        self.fileName = fromFile.name
        self.lineNo = lineNo
        self.category = "ERROR"
        self.error = error or "UNKNOWN ERROR"
    
    def __str__(self) -> str:
        return f'{self.fileName}:{self.lineNo} {self.category} {self.error}'


class UnknownSystemError(BuildCacheBaseException):
    """
    Raised when the file contains an unknown star name.
    """
    
    def __init__(self, fromFile: Path, lineNo: int, key: str) -> None:
        super().__init__(fromFile, lineNo, f'Unrecognized SYSTEM: "{key}"')


class UnknownStationError(BuildCacheBaseException):
    """
    Raised when the file contains an unknown star/station name.
    """
    
    def __init__(self, fromFile: Path, lineNo: int, key: str) -> None:
        super().__init__(fromFile, lineNo, f'Unrecognized STAR/Station: "{key}"')


class UnknownItemError(BuildCacheBaseException):
    """
    Raised in the case of an item name that we don't know.
    Attributes:
        itemName   Key we tried to look up.
    """
    
    def __init__(self, fromFile: Path, lineNo: int, itemName: str) -> None:
        super().__init__(fromFile, lineNo, f'Unrecognized item name: "{itemName}"')


class DuplicateKeyError(BuildCacheBaseException):
    """
        Raised when an item is being redefined.
    """
    
    def __init__(self, fromFile: Path, lineNo: int, keyType: str, keyValue: str, prevLineNo: int) -> None:
        super().__init__(fromFile, lineNo,
                         f'Second occurrance of {keyType} "{keyValue}", previous entry at line {prevLineNo}.')


class DeletedKeyError(BuildCacheBaseException):
    """
    Raised when a key value in a .csv file is marked as DELETED in the
    corrections file.
    """
    
    def __init__(self, fromFile: Path, lineNo: int, keyType: str, keyValue: str) -> None:
        super().__init__(
            fromFile, lineNo,
            f'{keyType} "{keyValue}" is marked as DELETED and should not be used.'
        )


class DeprecatedKeyError(BuildCacheBaseException):
    """
    Raised when a key value in a .csv file has a correction; the old
    name should not appear in the .csv file.
    """
    
    def __init__(self, fromFile: Path, lineNo: int, keyType: str, keyValue: str, newValue: str) -> None:
        super().__init__(
            fromFile, lineNo,
            f'{keyType} "{keyValue}" is deprecated and should be replaced with "{newValue}".'
        )


class MultipleStationEntriesError(DuplicateKeyError):
    """ Raised when a station appears multiple times in the same file. """
    
    def __init__(self, fromFile: Path, lineNo: int, facility: str, prevLineNo: int) -> None:
        super().__init__(fromFile, lineNo, 'station', facility, prevLineNo)


class MultipleItemEntriesError(DuplicateKeyError):
    """ Raised when one item appears multiple times in the same station. """
    
    def __init__(self, fromFile: Path, lineNo: int, item: str, prevLineNo: int) -> None:
        super().__init__(fromFile, lineNo, 'item', item, prevLineNo)


class InvalidLineError(BuildCacheBaseException):
    """
    Raised when an invalid line is read.
    Attributes:
        problem     The problem that occurred
        text        Offending text
    """
    
    def __init__(self, fromFile: Path, lineNo: int, problem: str, text: str) -> None:
        super().__init__(fromFile, lineNo, f'{problem},\ngot: "{text.strip()}".')


class SupplyError(BuildCacheBaseException):
    """
    Raised when a supply field is incorrectly formatted.
    """
    
    def __init__(self, fromFile: Path, lineNo: int, category: str, problem: str, value: Any) -> None:
        super().__init__(fromFile, lineNo, f'Invalid {category} supply value: {problem}. Got: {value}')


######################################################################
# Helpers

# --- tiny FK lookup caches (per import run) ---
_fk_cache_system = {}
_fk_cache_station = {}
_fk_cache_category = {}
_fk_cache_added = {}

def _get_system_id(session, system_name):
    if system_name in _fk_cache_system:
        return _fk_cache_system[system_name]
    rid = session.query(SA.System.system_id).filter(SA.System.name == system_name).scalar()
    if rid is None:
        raise ValueError(f"Unknown System name: {system_name}")
    _fk_cache_system[system_name] = rid
    return rid

def _get_station_id(session, system_id, station_name):
    key = (system_id, station_name)
    if key in _fk_cache_station:
        return _fk_cache_station[key]
    rid = (
        session.query(SA.Station.station_id)
        .filter(SA.Station.system_id == system_id, SA.Station.name == station_name)
        .scalar()
    )
    if rid is None:
        raise ValueError(f"Unknown Station '{station_name}' in system_id={system_id}")
    _fk_cache_station[key] = rid
    return rid

def _get_category_id(session, cat_name):
    if cat_name in _fk_cache_category:
        return _fk_cache_category[cat_name]
    rid = session.query(SA.Category.category_id).filter(SA.Category.name == cat_name).scalar()
    if rid is None:
        raise ValueError(f"Unknown Category name: {cat_name}")
    _fk_cache_category[cat_name] = rid
    return rid

def _get_added_id(session, added_name):
    if added_name in _fk_cache_added:
        return _fk_cache_added[added_name]
    rid = session.query(SA.Added.added_id).filter(SA.Added.name == added_name).scalar()
    if rid is None:
        raise ValueError(f"Unknown Added name: {added_name}")
    _fk_cache_added[added_name] = rid
    return rid

# supply/demand levels are one of '?' for unknown, 'L', 'M' or 'H'
# for low, medium, or high. We turn these into integer values for
# ordering convenience, and we include both upper and lower-case
# so we don't have to sweat ordering.
#
SUPPLY_LEVEL_VALUES = {
    '?':   -1,
    'L':    1,      'l':    1,
    'M':    2,      'm':    2,
    'H':    3,      'h':    3,
}


def parseSupply(pricesFile: Path, lineNo: int, category: str, reading: str) -> tuple[int, int]:
    """ Parse a supply specifier which is expected to be in the <number><?, L, M, or H>, and
        returns the units as an integer and a numeric level value suitable for ordering,
        such that ? = -1, L/l = 0, M/m = 1, H/h = 2 """
    
    #   supply_level <- digit+ level;
    #   digit <- [0-9];
    #   level <- Unknown / Low / Medium / High;
    #   Unknown <- '?';
    #   Low <- 'L';
    #   Medium <- 'M';
    #   High <- 'H';
    if reading == '?':
        return -1, -1
    if reading == '-':
        return 0, 0
    
    # extract the left most digits into unit and the last character into the level reading.
    units, level = reading[0:-1], reading[-1]
    
    # Extract the right most character as the "level" and look up its numeric value.
    levelNo = SUPPLY_LEVEL_VALUES.get(level)
    if levelNo is None:
        raise SupplyError(
            pricesFile, lineNo, category, reading,
            f'Unrecognized level suffix: "{level}": expected one of "L", "M", "H" or "?"'
        )
    
    # Expecting a numeric value in units, e.g. 123? -> (units=123, level=?)
    try:
        unitsNo = int(units)
        if unitsNo < 0:
            # Use the same code-path as if the units fail to parse.
            raise ValueError('negative unit count')
    except ValueError:
        raise SupplyError(
            pricesFile, lineNo, category, reading,
            f'Unrecognized units/level value: "{level}": expected "-", "?", or a number followed by a level (L, M, H or ?).'
        ) from None  # don't forward the exception itself
    
    # Normalize the units and level when there are no units.
    if unitsNo == 0:
        return 0, 0
    
    return unitsNo, levelNo


######################################################################
# Code
######################################################################


def getSystemByNameIndex(session: Session) -> dict[str, int]:
    """Build system index by uppercase name → system_id."""
    rows = (
        session.query(SA.System.system_id, func.upper(SA.System.name))
        .all()
    )
    return {name: ID for (ID, name) in rows}


def getStationByNameIndex(session: Session) -> dict[str, int]:
    """Build station index in STAR/Station notation → station_id."""
    rows = (
        session.query(
            SA.Station.station_id,
            (SA.System.name + "/" + SA.Station.name)
        )
        .join(SA.System, SA.Station.system_id == SA.System.system_id)
        .all()
    )
    # normalise case like original
    return {name.upper(): ID for (ID, name) in rows}



def getItemByNameIndex(session: Session) -> dict[str, int]:
    """Generate item name index (uppercase item name → item_id)."""
    rows = (
        session.query(SA.Item.item_id, func.upper(SA.Item.name))
        .all()
    )
    return {name: itemID for (itemID, name) in rows}



# The return type of process prices is complicated, should probably have been a type
# in its own right. I'm going to define some aliases to try and persuade IDEs to be
# more helpful about what it is trying to return.
if typing.TYPE_CHECKING:
    # A list of the IDs of stations that were modified so they can be updated
    ProcessedStationIds= tuple[tuple[int]]
    ProcessedItem = tuple[
        int,                            # station ID
        int,                            # item ID
        Optional[int | float |str],     # modified
        int,                            # demandCR
        int,                            # demandUnits
        int,                            # demandLevel
        int,                            # supplyCr
        int,                            # supplyUnits
        int,                            # supplyLevel
    ]
    ProcessedItems = list[ProcessedItem]
    ZeroItems = list[tuple[int, int]]   # stationID, itemID


def processPrices(
    tdenv: TradeEnv,
    priceFile: Path,
    session: Session,
    defaultZero: bool
) -> tuple[ProcessedStationIds, ProcessedItems, ZeroItems, int, int, int, int]:
    """
    Populate the database with prices by reading the given file.
    
    :param tdenv:       The environment we're working in
    :param priceFile:   File to read
    :param session:     Active SQLAlchemy session
    :param defaultZero: Whether to create default zero-availability/-demand
                        records for missing data. For partial updates,
                        set False.
    """
    
    DEBUG0, DEBUG1 = tdenv.DEBUG0, tdenv.DEBUG1
    DEBUG0("Processing prices file: {}", priceFile)
    
    ignoreUnknown = tdenv.ignoreUnknown
    quiet = tdenv.quiet
    merging = tdenv.mergeImport
    
    # build lookup indexes from DB
    systemByName = getSystemByNameIndex(session)
    stationByName = getStationByNameIndex(session)
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
    
    itemByName = getItemByNameIndex(session)
    
    defaultUnits = -1 if not defaultZero else 0
    defaultLevel = -1 if not defaultZero else 0
    
    stationID = None
    facility = None
    processedStations = {}
    processedSystems = set()
    processedItems = {}
    stationItemDates = {}
    DELETED = corrections.DELETED
    items, zeros = [], []
    
    lineNo, localAdd = 0, 0
    
    if not ignoreUnknown:
        def ignoreOrWarn(error: Exception) -> None:
            raise error
    elif not quiet:
        def ignoreOrWarn(error: Exception) -> None:
            # Ensure exceptions are stringified before passing to WARN
            tdenv.WARN(str(error))
    
    def changeStation(matches: re.Match) -> None:
        nonlocal facility, stationID
        nonlocal processedStations, processedItems, localAdd
        nonlocal stationItemDates
        
        # ## Change current station
        stationItemDates = {}
        systemNameIn, stationNameIn = matches.group(1, 2)
        systemName, stationName = systemNameIn.upper(), stationNameIn.upper()
        corrected = False
        facility = f'{systemName}/{stationName}'
        
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
            altName = sysCorrections.get(systemName)
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
            
            altStation = stnCorrections.get(facility)
            if altStation:
                if altStation is DELETED:
                    DEBUG1("DELETED Station: {}", facility)
                    return
                
                DEBUG1("Station '{}' renamed '{}'", facility, altStation)
                stationName = altStation.upper()
                facility = f'{systemName}/{stationName}'
            
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
            # ORM insert: placeholder station
            station = SA.Station(
                system_id=systemID,
                name=name,
                ls_from_star=0,
                blackmarket='?',
                max_pad_size='?',
                market='?',
                shipyard='?',
            )
            session.add(station)
            session.flush()  # assign station_id
            newID = station.station_id
            
            stationByName[facility] = newID
            tdenv.NOTE(
                "Added local station placeholder for {} (#{})", facility, newID
            )
            localAdd += 1
        
        elif newID in processedStations:
            if not corrected:
                raise MultipleStationEntriesError(
                    priceFile, lineNo, facility,
                    processedStations[newID]
                )
        
        stationID = newID
        processedSystems.add(systemName)
        processedStations[stationID] = lineNo
        processedItems = {}
        
        # ORM query: load existing item → modified map
        rows = (
            session.query(SA.StationItem.item_id, SA.StationItem.modified)
            .filter(SA.StationItem.station_id == stationID)
            .all()
        )
        stationItemDates = dict(rows)
    
    addItem, addZero = items.append, zeros.append
    getItemID = itemByName.get
    newItems, updtItems, ignItems = 0, 0, 0   # <-- put this back


    def processItemLine(matches):
        nonlocal newItems, updtItems, ignItems
        itemName, modified = matches.group('item', 'time')
        itemName = itemName.upper()
        
        # Look up the item ID.
        itemID = getItemID(itemName, -1)
        if itemID < 0:
            oldName = itemName
            itemName = corrections.correctItem(itemName)
            
            # Silently skip DELETED items
            if itemName == corrections.DELETED:
                DEBUG1("DELETED {}", oldName)
                return
            
            # Retry with corrected name
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
                    f'{itemName}',
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
                demandUnits, demandLevel = parseSupply(
                    priceFile, lineNo, 'demand', demandString
                )
            else:
                demandUnits, demandLevel = defaultUnits, defaultLevel
            
            if demandString and supplyString:
                supplyUnits, supplyLevel = parseSupply(
                    priceFile, lineNo, 'supply', supplyString
                )
            else:
                supplyUnits, supplyLevel = defaultUnits, defaultLevel
            
            if modified == 'now':
                modified = None  # Use CURRENT_FILESTAMP
            
            addItem((
                stationID, itemID, modified,
                demandCr, demandUnits, demandLevel,
                supplyCr, supplyUnits, supplyLevel,
            ))
        
        processedItems[itemID] = lineNo
    
    space_cleanup = re.compile(r'\s{2,}').sub
    for line in priceFile:
        lineNo += 1
        
        text = line.split('#', 1)[0]                # Discard comments
        text = space_cleanup(' ', text).strip()     # Remove leading/trailing whitespace, reduce multi-spaces
        if not text:
            continue
        
        ########################################
        # ## "@ STAR/Station" lines.
        if text.startswith('@'):
            matches = systemStationRe.match(text)
            if not matches:
                raise InvalidLineError(priceFile, lineNo, "Unrecognized '@' line", text)
            changeStation(matches)
            continue
        
        if not stationID:
            # Need a station to process any other type of line.
            raise InvalidLineError(priceFile, lineNo, "Expecting '@ SYSTEM / Station' line", text)
        if stationID == DELETED:
            # Ignore all values from a deleted station/system.
            continue
        
        ########################################
        # ## "+ Category" lines
        if text.startswith('+'):
            # we now ignore these.
            continue
        
        ########################################
        # ## "Item sell buy ..." lines.
        matches = newItemPriceRe.match(text)
        if not matches:
            raise InvalidLineError(priceFile, lineNo, "Unrecognized line/syntax", text)
        
        processItemLine(matches)
    
    numSys = len(processedSystems)
    
    if localAdd > 0:
        tdenv.NOTE(
            "Placeholder stations are added to the local DB only "
            "(not the .CSV).\n"
            "Use 'trade.py export --table Station' "
            "if you /need/ to persist them."
        )
    
    stations = tuple((ID,) for ID in processedStations)
    return stations, items, zeros, newItems, updtItems, ignItems, numSys


######################################################################


def processPricesFile(
    tdenv: "TradeEnv",
    session: Session,
    pricesPath: Path,
    pricesFh: Optional[TextIO] = None,
    defaultZero: bool = False,
) -> None:
    """
    Process a .prices file and import data into the DB via ORM.
    """
    
    tdenv.DEBUG0("Processing Prices file '{}'", pricesPath)
    
    with (pricesFh or pricesPath.open("r", encoding="utf-8")) as fh:
        (
            stations,
            items,
            zeros,
            newItems,
            updtItems,
            ignItems,
            numSys,
        ) = processPrices(tdenv, fh, session, defaultZero)
    
    if not tdenv.mergeImport:
        # Delete all StationItems for these stations
        session.query(SA.StationItem).filter(
            SA.StationItem.station_id.in_([sid for (sid,) in stations])
        ).delete(synchronize_session=False)
    
    # Remove zeroed pairs
    removedItems = 0
    if zeros:
        session.query(SA.StationItem).filter(
            tuple_(SA.StationItem.station_id, SA.StationItem.item_id).in_(zeros)
        ).delete(synchronize_session=False)
        removedItems = len(zeros)
    
    # Upsert items
    if items:
        for (
            station_id,
            item_id,
            modified,
            demand_price,
            demand_units,
            demand_level,
            supply_price,
            supply_units,
            supply_level,
        ) in items:
            obj = SA.StationItem(
                station_id=station_id,
                item_id=item_id,
                modified=modified or None,
                demand_price=demand_price,
                demand_units=demand_units,
                demand_level=demand_level,
                supply_price=supply_price,
                supply_units=supply_units,
                supply_level=supply_level,
            )
            session.merge(obj)
    
    tdenv.DEBUG0("Marking populated stations as having a market")
    session.query(SA.Station).filter(
        SA.Station.station_id.in_([sid for (sid,) in stations])
    ).update({SA.Station.market: "Y"}, synchronize_session=False)
    
    changes = " and ".join(
        f"{v} {k}"
        for k, v in {
            "new": newItems,
            "updated": updtItems,
            "removed": removedItems,
        }.items()
        if v
    ) or "0"
    
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


# --- main importer ---
def processImportFile(
    tdenv,
    session,
    importPath,
    tableName,
    *,
    line_callback: Optional[Callable] = None,
    call_args: Optional[dict] = None,
):
    """
    Import a CSV file into the given table.
    
    Applies header parsing, uniqueness checks, foreign key lookups,
    in-row deprecation correction (warnings only at -vv via DEBUG1), and upserts via SQLAlchemy ORM.
    Commits in batches for large datasets.
    """
    
    tdenv.DEBUG0("Processing import file '{}' for table '{}'", str(importPath), tableName)
    
    call_args = call_args or {}
    if line_callback:
        line_callback = partial_fn(line_callback, **call_args)
    
    # --- batch size config from environment or fallback ---
    env_batch = os.environ.get("TD_LISTINGS_BATCH")
    if env_batch:
        try:
            max_transaction_items = int(env_batch)
        except ValueError:
            tdenv.WARN("Invalid TD_LISTINGS_BATCH value %r, falling back to defaults.", env_batch)
            max_transaction_items = None
    else:
        max_transaction_items = None
    
    if max_transaction_items is None:
        if session.bind.dialect.name in ("mysql", "mariadb"):
            max_transaction_items = 50 * 1024
        else:
            max_transaction_items = 250 * 1024
    
    transaction_items = 0  # track how many rows inserted before committing
    
    with importPath.open("r", encoding="utf-8") as importFile:
        csvin = csv.reader(importFile, delimiter=",", quotechar="'", doublequote=True)
        
        # Read header row
        columnDefs = next(csvin)
        columnCount = len(columnDefs)
        
        # --- Process headers: extract column names, track indices ---
        activeColumns: list[str] = []   # Final columns we'll use (after "unq:" stripping)
        kept_indices: list[int] = []    # Indices into CSV rows we keep (aligned to activeColumns)
        uniqueIndexes: list[int] = []   # Indexes (into activeColumns) of unique keys
        fk_col_indices: dict[str, int] = {}  # Special handling for FK resolution
        
        uniquePfx = "unq:"
        uniqueLen = len(uniquePfx)
        
        # map of header (without "unq:") -> original CSV index, for correction by name
        header_index: dict[str, int] = {}
        
        for cIndex, cName in enumerate(columnDefs):
            colName, _, srcKey = cName.partition("@")
            baseName = colName[uniqueLen:] if colName.startswith(uniquePfx) else colName
            header_index[baseName] = cIndex
            
            # Special-case: System-added
            if tableName == "System":
                if cName == "name":
                    srcKey = ""
                elif cName == "name@Added.added_id":
                    fk_col_indices["added"] = cIndex
                    continue
            
            # Foreign key columns for RareItem
            if tableName == "RareItem":
                if cName == "!name@System.system_id":
                    fk_col_indices["system"] = cIndex
                    continue
                if cName == "name@Station.station_id":
                    fk_col_indices["station"] = cIndex
                    continue
                if cName == "name@Category.category_id":
                    fk_col_indices["category"] = cIndex
                    continue
            
            # Handle unique constraint tracking
            if colName.startswith(uniquePfx):
                uniqueIndexes.append(len(activeColumns))
                colName = baseName
            
            activeColumns.append(colName)
            kept_indices.append(cIndex)
        
        importCount = 0
        uniqueIndex: dict[str, int] = {}
        
        # helpers for correction + visibility-gated warning
        DELETED = corrections.DELETED
        
        def _warn(line_no: int, msg: str) -> None:
            # Gate deprecation chatter to -vv (DEBUG1)
            tdenv.DEBUG1("{}:{} WARNING {}", importPath, line_no, msg)
        
        def _apply_row_corrections(table_name: str, row: list[str], line_no: int) -> bool:
            """
            Returns True if the row should be skipped (deleted in tolerant mode), False otherwise.
            Mutates 'row' in place with corrected values.
            """
            try:
                if table_name == "System":
                    idx = header_index.get("name")
                    if idx is not None:
                        orig = row[idx]
                        corr = corrections.correctSystem(orig)
                        if corr is DELETED:
                            if tdenv.ignoreUnknown:
                                _warn(line_no, f'System "{orig}" is marked as DELETED and should not be used.')
                                return True
                            raise DeletedKeyError(importPath, line_no, "System", orig)
                        if corr != orig:
                            _warn(line_no, f'System "{orig}" is deprecated and should be replaced with "{corr}".')
                            row[idx] = corr
                
                elif table_name == "Station":
                    s_idx = header_index.get("system")
                    n_idx = header_index.get("name")
                    if s_idx is not None and n_idx is not None:
                        s_orig = row[s_idx]
                        s_corr = corrections.correctSystem(s_orig)
                        if s_corr is DELETED:
                            if tdenv.ignoreUnknown:
                                _warn(line_no, f'System "{s_orig}" is marked as DELETED and should not be used.')
                                return True
                            raise DeletedKeyError(importPath, line_no, "System", s_orig)
                        if s_corr != s_orig:
                            _warn(line_no, f'System "{s_orig}" is deprecated and should be replaced with "{s_corr}".')
                            row[s_idx] = s_corr
                        n_orig = row[n_idx]
                        n_corr = corrections.correctStation(s_corr, n_orig)
                        if n_corr is DELETED:
                            if tdenv.ignoreUnknown:
                                _warn(line_no, f'Station "{n_orig}" is marked as DELETED and should not be used.')
                                return True
                            raise DeletedKeyError(importPath, line_no, "Station", n_orig)
                        if n_corr != n_orig:
                            _warn(line_no, f'Station "{n_orig}" is deprecated and should be replaced with "{n_corr}".')
                            row[n_idx] = n_corr
                
                elif table_name == "Category":
                    idx = header_index.get("name")
                    if idx is not None:
                        orig = row[idx]
                        corr = corrections.correctCategory(orig)
                        if corr is DELETED:
                            if tdenv.ignoreUnknown:
                                _warn(line_no, f'Category "{orig}" is marked as DELETED and should not be used.')
                                return True
                            raise DeletedKeyError(importPath, line_no, "Category", orig)
                        if corr != orig:
                            _warn(line_no, f'Category "{orig}" is deprecated and should be replaced with "{corr}".')
                            row[idx] = corr
                
                elif table_name == "Item":
                    cat_idx = header_index.get("category")
                    name_idx = header_index.get("name")
                    if cat_idx is not None:
                        c_orig = row[cat_idx]
                        c_corr = corrections.correctCategory(c_orig)
                        if c_corr is DELETED:
                            if tdenv.ignoreUnknown:
                                _warn(line_no, f'Category "{c_orig}" is marked as DELETED and should not be used.')
                                return True
                            raise DeletedKeyError(importPath, line_no, "Category", c_orig)
                        if c_corr != c_orig:
                            _warn(line_no, f'Category "{c_orig}" is deprecated and should be replaced with "{c_corr}".')
                            row[cat_idx] = c_corr
                    if name_idx is not None:
                        i_orig = row[name_idx]
                        i_corr = corrections.correctItem(i_orig)
                        if i_corr is DELETED:
                            if tdenv.ignoreUnknown:
                                _warn(line_no, f'Item "{i_orig}" is marked as DELETED and should not be used.')
                                return True
                            raise DeletedKeyError(importPath, line_no, "Item", i_orig)
                        if i_corr != i_orig:
                            _warn(line_no, f'Item "{i_orig}" is deprecated and should be replaced with "{i_corr}".')
                            row[name_idx] = i_corr
                
                # RareItem: we only correct category (FK lookup uses names) to improve hit rate.
                elif table_name == "RareItem":
                    cat_idx = header_index.get("category")
                    if cat_idx is not None:
                        c_orig = row[cat_idx]
                        c_corr = corrections.correctCategory(c_orig)
                        if c_corr is DELETED:
                            if tdenv.ignoreUnknown:
                                _warn(line_no, f'Category "{c_orig}" is marked as DELETED and should not be used.')
                                return True
                            raise DeletedKeyError(importPath, line_no, "Category", c_orig)
                        if c_corr != c_orig:
                            _warn(line_no, f'Category "{c_orig}" is deprecated and should be replaced with "{c_corr}".')
                            row[cat_idx] = c_corr
            
            except BuildCacheBaseException:
                # strict mode path bubbles up; caller will handle
                raise
            return False  # do not skip
        
        # --- Read data lines ---
        for linein in csvin:
            if line_callback:
                line_callback()
            if not linein:
                continue
            
            lineNo = csvin.line_num
            
            if len(linein) != columnCount:
                tdenv.NOTE("Wrong number of columns ({}:{}): {}", importPath, lineNo, ", ".join(linein))
                continue
            
            tdenv.DEBUG1("       Values: {}", ", ".join(linein))
            
            # --- Apply corrections BEFORE uniqueness; may skip if deleted in tolerant mode
            try:
                if _apply_row_corrections(tableName, linein, lineNo):
                    continue
            except DeletedKeyError:
                if not tdenv.ignoreUnknown:
                    # strict: fail hard
                    raise
                # tolerant: already warned in _apply_row_corrections; skip row
                continue
            
            # Extract and clean values to use (from corrected line)
            activeValues = [linein[i] for i in kept_indices]
            
            # --- Uniqueness check (after correction) ---
            try:
                if uniqueIndexes:
                    keyValues = [str(activeValues[i]).upper() for i in uniqueIndexes]
                    key = ":!:".join(keyValues)
                    prevLineNo = uniqueIndex.get(key, 0)
                    if prevLineNo:
                        key_disp = "/".join(keyValues)
                        if tdenv.ignoreUnknown:
                            e = DuplicateKeyError(importPath, lineNo, "entry", key_disp, prevLineNo)
                            e.category = "WARNING"
                            tdenv.NOTE("{}", e)
                            continue
                        raise DuplicateKeyError(importPath, lineNo, "entry", key_disp, prevLineNo)
                    uniqueIndex[key] = lineNo
            except Exception as e:
                # Keep processing the file, don’t tear down the loop
                tdenv.WARN(
                    "*** INTERNAL ERROR: {err}\n"
                    "CSV File: {file}:{line}\n"
                    "Table: {table}\n"
                    "Params: {params}\n".format(
                        err=str(e),
                        file=str(importPath),
                        line=lineNo,
                        table=tableName,
                        params=linein,
                    )
                )
                session.rollback()
                continue
            
            try:
                rowdict = dict(zip(activeColumns, activeValues))
                
                # Foreign key lookups — RareItem
                if tableName == "RareItem":
                    sys_id = None
                    if "system" in fk_col_indices:
                        sys_name = linein[fk_col_indices["system"]]
                        try:
                            sys_id = _get_system_id(session, sys_name)
                        except ValueError:
                            tdenv.WARN("Unknown System '{}' in {}", sys_name, importPath)
                    
                    if "station" in fk_col_indices:
                        stn_name = linein[fk_col_indices["station"]]
                        if sys_id is not None:
                            try:
                                rowdict["station_id"] = _get_station_id(session, sys_id, stn_name)
                            except ValueError:
                                tdenv.WARN("Unknown Station '{}' in {}", stn_name, importPath)
                        else:
                            tdenv.WARN("Station lookup skipped (no system_id) for '{}'", stn_name)
                    
                    if "category" in fk_col_indices:
                        cat_name = linein[fk_col_indices["category"]]
                        try:
                            rowdict["category_id"] = _get_category_id(session, cat_name)
                        except ValueError:
                            tdenv.WARN("Unknown Category '{}' in {}", cat_name, importPath)
                
                # Foreign key lookups — System.added
                if tableName == "System" and "added" in fk_col_indices:
                    added_val = linein[fk_col_indices["added"]] or "EDSM"
                    try:
                        rowdict["added_id"] = _get_added_id(session, added_val)
                    except ValueError:
                        rowdict["added_id"] = None
                        tdenv.WARN("Unknown Added value '{}' in {}", added_val, importPath)
                
                # --- Type coercion for common types ---
                for key, val in list(rowdict.items()):
                    if val in ("", None):
                        rowdict[key] = None
                        continue
                    if key.endswith("_id") or key.endswith("ID") or key in ("cost", "max_allocation"):
                        try:
                            rowdict[key] = int(val)
                        except ValueError:
                            rowdict[key] = None
                    elif key in ("pos_x", "pos_y", "pos_z", "ls_from_star"):
                        try:
                            rowdict[key] = float(val)
                        except ValueError:
                            rowdict[key] = None
                    elif "time" in key or key == "modified":
                        parsed = parse_ts(val)
                        if parsed:
                            rowdict[key] = parsed
                        else:
                            tdenv.WARN(
                                "Unparsable datetime in {} line {} col {}: {}",
                                importPath,
                                lineNo,
                                key,
                                val,
                            )
                            rowdict[key] = None
                
                # Special handling for SQL reserved word `class`
                if tableName == "Upgrade" and "class" in rowdict:
                    rowdict["class_"] = rowdict.pop("class")
                if tableName == "FDevOutfitting" and "class" in rowdict:
                    rowdict["class_"] = rowdict.pop("class")
                if tableName == "RareItem" and "system_id" in rowdict:
                    rowdict.pop("system_id", None)
                
                # ORM insert/merge
                Model = getattr(SA, tableName)
                obj = Model(**rowdict)
                session.merge(obj)
                importCount += 1
                
                # Batch commit
                if max_transaction_items:
                    transaction_items += 1
                    if transaction_items >= max_transaction_items:
                        session.commit()
                        session.begin()
                        transaction_items = 0
            
            except Exception as e:
                # Log all import errors — but keep going
                tdenv.WARN(
                    "*** INTERNAL ERROR: {err}\n"
                    "CSV File: {file}:{line}\n"
                    "Table: {table}\n"
                    "Params: {params}\n".format(
                        err=str(e),
                        file=str(importPath),
                        line=lineNo,
                        table=tableName,
                        params=rowdict if "rowdict" in locals() else linein,
                    )
                )
                session.rollback()
        
        # Final commit after file done
        session.commit()
        tdenv.DEBUG0("{count} {table}s imported", count=importCount, table=tableName)




def buildCache(tdb: TradeDB, tdenv: TradeEnv):
    """
    Rebuilds the database from source files.
    
    TD's data is either "stable" - information that rarely changes like Ship
    details, star systems etc - and "volatile" - pricing information, etc.
    
    The stable data starts out in data/TradeDangerous.sql while other data
    is stored in custom-formatted text files, e.g. ./TradeDangerous.prices.
    
    We load both sets of data into a database, after which we can
    avoid the text-processing overhead by simply checking if the text files
    are newer than the database.
    """
    
    tdenv.NOTE(
        "(Re)building database: this may take a few moments.",
        stderr=True,
    )
    
    dbPath = tdb.dbPath
    sqlPath = tdb.sqlPath
    # pricesPath = tdb.pricesPath
    engine = tdb.engine
    
    # --- Step 1: reset schema BEFORE opening a session/transaction ---
    # Single unified call; no dialect branching here.
    lifecycle.reset_db(engine, db_path=dbPath)
    
    # --- Step 2: open a new session for rebuild work ---
    with tdb.Session() as session:
        # Import standard tables on a plain session with progress
        with Progress(
            max_value=len(tdb.importTables) + 1,
            prefix="Importing",
            width=25,
            style=CountingBar,
        ) as prog:
            for importName, importTable in tdb.importTables:
                import_path = Path(importName)
                import_lines = file_line_count(import_path, missing_ok=True)
                with prog.sub_task(
                    max_value=import_lines, description=importTable
                ) as child:
                    prog.increment(value=1)
                    call_args = {"task": child, "advance": 1}
                    try:
                        processImportFile(
                            tdenv,
                            session,
                            import_path,
                            importTable,
                            line_callback=prog.update_task,
                            call_args=call_args,
                        )
                        # safety commit after each file
                        session.commit()
                    except FileNotFoundError:
                        tdenv.DEBUG0(
                            "WARNING: processImportFile found no {} file", importName
                        )
                    except StopIteration:
                        tdenv.NOTE(
                            "{} exists but is empty. "
                            "Remove it or add the column definition line.",
                            importName,
                        )
            prog.increment(1)
            
            with prog.sub_task(description="Save DB"):
                session.commit()
        
        # # --- Step 3: parse the prices file (still plain session) ---
        # if pricesPath.exists():
        #     with Progress(max_value=None, width=25, prefix="Processing prices file"):
        #         processPricesFile(tdenv, session, pricesPath)
        # else:
        #     tdenv.NOTE(
        #         f'Missing "{pricesPath}" file - no price data.',
        #         stderr=True,
        #     )
    
    tdb.close()
    tdenv.NOTE(
        "Database build completed.",
        stderr=True,
    )


######################################################################


def regeneratePricesFile(tdb: TradeDB, tdenv: TradeEnv) -> None:
    return
    # """
    # Regenerate the .prices file from the current DB contents.
    # Uses the ORM session rather than raw sqlite.
    # """
    # tdenv.DEBUG0("Regenerating .prices file")
    # 
    # with tdb.Session() as session:
    #     with tdb.pricesPath.open("w", encoding="utf-8") as pricesFile:
    #         prices.dumpPrices(
    #             session,
    #             prices.Element.full,
    #             file=pricesFile,
    #             debug=tdenv.debug,
    #         )
    # 
    # # Only touch the DB file on SQLite — MariaDB has no dbPath
    # if tdb.engine.dialect.name == "sqlite" and tdb.dbPath and os.path.exists(tdb.dbPath):
    #     os.utime(tdb.dbPath)

######################################################################


def importDataFromFile(tdb, tdenv, path, pricesFh=None, reset=False):
    """
    Import price data from a file on a per-station basis,
    that is when a new station is encountered, delete any
    existing records for that station in the database.
    """
    
    if not pricesFh and not path.exists():
        raise TradeException(f"No such file: {path}")
    
    if reset:
        tdenv.DEBUG0("Resetting price data")
        with tdb.Session.begin() as session:
            session.query(SA.StationItem).delete()
    
    tdenv.DEBUG0(f"Importing data from {path}")
    processPricesFile(
        tdenv,
        db=tdb.getDB(),      # still used for the incremental parsing logic
        pricesPath=path,
        pricesFh=pricesFh,
    )
    
    # # If everything worked, regenerate the canonical prices file if this wasn’t the main one
    # if path != tdb.pricesPath:
    #     regeneratePricesFile(tdb, tdenv)
