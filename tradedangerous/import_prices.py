# --------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
# Copyright (C) Bernd 'Gazelle' Gollesch 2016, 2017
# Copyright (C) Stefan 'Tromador' Morrell 2025, 2026
# Copyright (C) Jonathan 'eyeonus' Jones 2018-2025
#
# You are free to use, redistribute, or even print and eat a copy of
# this software so long as you include this copyright notice.
# I guarantee there is at least one bug neither of us knew about.
# --------------------------------------------------------------------
# TradeDangerous :: Modules :: .prices file import
#
#  Reads TradeDangerous ".prices" files into the database. This is the legacy
#  hand-editable price format; the spansh and eddblink importers are preferred,
#  but the ".prices" pathway is retained. Split out of the former cache.py
#  during the TradeDB retirement; CSV table import and the database rebuild now
#  live in tradedangerous/db/import_csv.py.
#

from __future__ import annotations

from pathlib import Path
import re
import typing

from sqlalchemy import func, tuple_
from sqlalchemy.orm import Session
from tradedangerous.db import orm_models as SA

from .tradeexcept import (
    TradeException, SupplyError, MultipleStationEntriesError, InvalidLineError,
    UnknownSystemError, UnknownStationError, UnknownItemError, MultipleItemEntriesError,
)
from . import corrections, utils


# For mypy/pylint type checking
if typing.TYPE_CHECKING:
    from typing import Optional, TextIO

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
























######################################################################
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
    MISSING_STATION = object()
    items, zeros = [], []
    
    lineNo, localAdd = 0, 0
    
    # Local placeholder stations must not rely on DB-generated IDs.
    # Canonical SQLite uses an explicit Station.station_id and WITHOUT ROWID,
    # so rowid/lastrowid behaviour is not a portable contract.
    min_station_id = (
        session.query(func.min(SA.Station.station_id))
        .filter(SA.Station.station_id < 0)
        .scalar()
    )
    next_placeholder_station_id = (
        int(min_station_id) - 1
        if min_station_id is not None
        else -1
    )

    def allocate_placeholder_station_id() -> int:
        nonlocal next_placeholder_station_id

        station_id = next_placeholder_station_id
        while station_id == DELETED:
            station_id -= 1

        next_placeholder_station_id = station_id - 1
        return station_id
    if not ignoreUnknown:
        def ignoreOrWarn(error: Exception) -> None:
            raise error
    elif not quiet:
        def ignoreOrWarn(error: Exception) -> None:
            # Ensure exceptions are stringified before passing to WARN
            tdenv.WARN(str(error))
    else:
        def ignoreOrWarn(error: Exception) -> None:
            pass
    
    def changeStation(matches: re.Match) -> None:
        nonlocal facility, stationID
        nonlocal processedItems, localAdd
        nonlocal stationItemDates
        
        # Change current station
        stationItemDates = {}
        systemNameIn, stationNameIn = matches.group(1, 2)
        systemName, stationName = systemNameIn.upper(), stationNameIn.upper()
        corrected = False
        facility = f'{systemName}/{stationName}'
        
        stationID = DELETED
        newID = stationByName.get(facility, MISSING_STATION)
        DEBUG0("Selected station: {}, ID={}", facility, newID)
        
        if newID == DELETED:
            DEBUG1("DELETED Station: {}", facility)
            return
        
        if newID is MISSING_STATION:
            assert not utils.checkForOcrDerp(tdenv, systemName, stationName)

            corrected = True
            altName = sysCorrections.get(systemName)
            if altName == DELETED:
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
                if altStation == DELETED:
                    DEBUG1("DELETED Station: {}", facility)
                    return
                
                DEBUG1("Station '{}' renamed '{}'", facility, altStation)
                stationName = altStation.upper()
                facility = f'{systemName}/{stationName}'
            
            newID = stationByName.get(facility, MISSING_STATION)
            if newID == DELETED:
                DEBUG1("Renamed station DELETED: {}", facility)
                return
        
        if newID is MISSING_STATION:
            if not ignoreUnknown:
                ignoreOrWarn(
                    UnknownStationError(priceFile, lineNo, facility)
                )
                return
            
            name = utils.titleFixup(stationName)
            newID = allocate_placeholder_station_id()

            # ORM insert: local-only placeholder station.
            # Supply station_id explicitly; do not depend on backend
            # identity/autoincrement/rowid behaviour.
            station = SA.Station(
                station_id=newID,
                system_id=systemID,
                name=name,
                lookup_name=corrections.normalize_str(name),
                ls_from_star=0,
                blackmarket='?',
                max_pad_size='?',
                market='?',
                shipyard='?',
            )
            session.add(station)
            session.flush()
            
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




# --- main importer ---






######################################################################


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
        with tdb.session_maker.begin() as session:
            session.query(SA.StationItem).delete()
    
    tdenv.DEBUG0(f"Importing data from {path}")
    processPricesFile(
        tdenv,
        session=tdb.session_maker(),
        pricesPath=path,
        pricesFh=pricesFh,
    )
