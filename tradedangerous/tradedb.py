"""
Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
Copyright (C) Bernd 'Gazelle' Gollesch 2016, 2017
Copyright (C) Stefan 'Tromador' Morrell 2025
Copyright (C) Jonathan 'eyeonus' Jones 2018 - 2025

You are free to use, redistribute, or even print and eat a copy of
this software so long as you include this copyright notice.

I guarantee there is at least one bug neither of us knew about. -- Oliver
--------------------------------------------------------------------
TradeDangerous :: Modules :: Database Module

Provides the primary classes used within TradeDangerous:

TradeDB, System, Station, Ship, Item, and Trade.

These classes are primarily for describing the database.

Simplistic use might be:
    
    import tradedb
    
    # Create an instance: You can specify a debug level as a
    # parameter, for more advanced configuration, see the
    # tradeenv.TradeEnv() class.
    tdb = tradedb.TradeDB()
    
    # look up a System by name
    sol = tdb.lookupSystem("SOL")
    ibootis = tdb.lookupSystem("i BootiS")
    ibootis = tdb.lookupSystem("ibootis")
    
    # look up a Station by name
    abe = tdb.lookupStation("Abraham Lincoln")
    abe = tdb.lookupStation("Abraham Lincoln", sol)
    abe = tdb.lookupStation("hamlinc")
    
    # look up something that could be a system or station,
    # where 'place' syntax can be:
    #  SYS, STN, SYS/STN, @SYS, /STN or @SYS/STN
    abe = tdb.lookupPlace("Abraham Lincoln")
    abe = tdb.lookupPlace("HamLinc")
    abe = tdb.lookupPlace("@SOL/HamLinc")
    abe = tdb.lookupPlace("so/haml")
    abe = tdb.lookupPlace("sol/abraham lincoln")
    abe = tdb.lookupPlace("@sol/abrahamlincoln")
    james = tdb.lookupPlace("shin/jamesmem")
"""

######################################################################
# Imports
from __future__ import annotations

from collections import namedtuple
from functools import lru_cache
from math import sqrt as math_sqrt
from pathlib import Path
from typing import NamedTuple
import heapq
import itertools
import locale
import os
import pickle
import re
import sys
import time
import typing

from .tradeenv import TradeEnv
from .tradeexcept import TradeException, AmbiguityError, SystemNotStationError
from . import cache, fs

from sqlalchemy import func, select, text
from sqlalchemy.exc import NoResultFound
from .db import make_engine_from_config, get_session_factory  # type: ignore
from .db.lifecycle import ensure_fresh_db  # type: ignore
from .db.utils import age_in_days  # type: ignore

# --------------------------------------------------------------------
# SQLAlchemy ORM imports (aliased to avoid clashing with legacy wrappers).
# These map to the actual database tables via SQLAlchemy and are used
# internally in loaders/writers to replace raw sqlite3 queries.
#
# NOTE: We still instantiate and use legacy wrapper classes defined in
# this file (System, Station, Item, etc.) to maintain API compatibility
# across the rest of the codebase (Pass 1 migration).
#
# In a possible future cleanup (Pass 2), the wrappers may be removed
# entirely, and code updated to use ORM models directly.
# --------------------------------------------------------------------

from .db.orm_models import (  # noqa: F401  # pylint: disable=unused-import
    Added              as SA_Added,
    System             as SA_System,
    Station            as SA_Station,
    Item               as SA_Item,
    Category           as SA_Category,
    StationItem        as SA_StationItem,
    RareItem           as SA_RareItem,
    Ship               as SA_Ship,
    ShipVendor         as SA_ShipVendor,
    Upgrade            as SA_Upgrade,
    UpgradeVendor      as SA_UpgradeVendor,
    ExportControl      as SA_ExportControl,
    StationItemStaging as SA_StationItemStaging,
)


locale.setlocale(locale.LC_ALL, '')


if typing.TYPE_CHECKING:
    from typing import Any, Callable, Generator, Optional


# We should probably just use the trade-dangerous version number
# otherwise this is a value that someone has to keep changing.
# Ultimately it just needs to be something that tells us we can't
# reasonably reconstitute the same data when running this version
# against that file.
PERSIST_FORMAT = 3

# Names for the fields in the persist header.
PERSIST_FORMAT_FIELD = "fmtv"
PERSIST_TIMESTAMP_FIELD = "dbts"
PERSIST_SIZE_FIELD = "dbsz"


######################################################################
# Classes

######################################################################


def make_stellar_grid_key(x: float, y: float, z: float) -> tuple[int, int, int]:
    """
    The Stellar Grid is a map of systems based on their Stellar
    co-ordinates rounded down to 32lys. This makes it much easier
    to find stars within rectangular volumes.
    """
    return int(x) >> 5, int(y) >> 5, int(z) >> 5


class System:
    """
    Describes a star system which may contain one or more Station objects.
    
    Caution: Do not use _rangeCache directly, use TradeDB.genSystemsInRange.
    """
    
    __slots__ = (
        'ID',
        'dbname', 'posX', 'posY', 'posZ', 'pos', 'stations',
        'addedID',
        '_rangeCache'
    )
    
    class RangeCache:
        """
        Lazily populated cache of neighboring systems.
        """
        def __init__(self):
            self.systems = []
            self.probed_ly = 0.
    
    def __init__(self, ID: int, dbname: str, posX: float, posY: float, posZ: float, addedID: int|None) -> None:
        self.ID = ID
        self.dbname = dbname
        self.posX, self.posY, self.posZ = posX, posY, posZ
        self.addedID = addedID or 0
        self.stations: list['Station'] = []
        self._rangeCache = None
    
    @property
    def system(self) -> 'System':
        """ Returns self for compatibility with the undefined 'Positional' interface. """
        return self
    
    def distanceTo(self, other: 'System') -> float:
        """
        Returns the distance (in ly) between two systems.
        
        NOTE: If you are primarily testing/comparing
        distances, consider using "distToSq" for the test.
        
        Returns:
            Distance in light years.
        
        Example:
            print("{} -> {}: {} ly".format(
                lhs.name(), rhs.name(),
                lhs.distanceTo(rhs),
            ))
        """
        dx, dy, dz = self.posX - other.posX, self.posY - other.posY, self.posZ - other.posZ
        return math_sqrt(dx * dx + dy * dy + dz * dz)
    
    def getStation(self, name: str) -> 'Optional[Station]':
        """
        Quick case-insensitive lookup of a station name within the
        stations in this system.
        
        Returns:
            Station() object if a match is found,
            otherwise None.
        """
        name = name.upper()
        for station in self.stations:
            if station.name == name:
                return station
        return None
    
    def name(self, detail: int = 0) -> str:     # pylint: disable=unused-argument
        """ Returns the display name for this System."""
        return self.dbname
    
    def text(self) -> str:
        return self.dbname

######################################################################

class Destination(NamedTuple):
    system: 'System'
    station: 'Station'
    via: list['System']
    distLy: float


class DestinationNode(NamedTuple):
    system: 'System'
    via: list['System']
    distLy: float

class Station:
    """
    Describes a station (trading or otherwise) in a system.
    
    For obtaining trade information for a given station see one of:
        TradeCalc.getTrades        (fast and cheap)
    """
    __slots__ = (
        'ID', 'system', 'dbname',
        'lsFromStar', 'market', 'blackMarket', 'shipyard', 'maxPadSize',
        'outfitting', 'rearm', 'refuel', 'repair', 'planetary','fleet',
        'odyssey', 'itemCount', 'dataAge',
    )
    
    def __init__(
            self, ID: int, system: 'System', dbname: str,
            lsFromStar: float, market: str, blackMarket: str, shipyard: str, maxPadSize: str,
            outfitting: str, rearm: str, refuel: str, repair: str, planetary: str, fleet: str, odyssey: str,
            itemCount: int = 0, dataAge: float | int | None = None,
            ):
        self.ID, self.system, self.dbname = ID, system, dbname  # type: ignore
        self.lsFromStar = int(lsFromStar)
        self.market = market if itemCount == 0 else 'Y'
        self.blackMarket = blackMarket
        self.shipyard = shipyard
        self.maxPadSize = maxPadSize
        self.outfitting = outfitting
        self.rearm = rearm
        self.refuel = refuel
        self.repair = repair
        self.planetary = planetary
        self.fleet = fleet
        self.odyssey = odyssey
        self.itemCount = itemCount
        self.dataAge = dataAge
        system.stations += [self]
    
    def name(self, detail: int = 0) -> str:  # pylint: disable=unused-argument
        return f"{self.system.dbname}/{self.dbname}"
    
    def checkPadSize(self, maxPadSize: str) -> bool:
        """
        Tests if the Station's max pad size matches one of the
        values in 'maxPadSize'.
        
        Args:
            maxPadSize
                A string of one or more max pad size values that
                you want to match against.
        
        Returns:
            True
                If self.maxPadSize is None or empty, or matches a
                member of maxPadSize
            False
                If maxPadSize was not empty but self.maxPadSize
                did not match it.
        
        Examples:
            # Require a medium max pad size - not small or large
            station.checkPadSize("M")
            # Require medium or unknown
            station.checkPadSize("M?")
            # Require small, large or unknown
            station.checkPadSize("SL?")
        """
        return (not maxPadSize or self.maxPadSize in maxPadSize)
    
    def checkPlanetary(self, planetary: str) -> bool:
        """
        Tests if the Station's planetary matches one of the
        values in 'planetary'.
        
        Args:
            planetary
                A string of one or more planetary values that
                you want to match against.
        
        Returns:
            True
                If self.planetary is None or empty, or matches a
                member of planetary
            False
                If planetary was not empty but self.planetary
                did not match it.
        
        Examples:
            # Require a planetary station
            station.checkPlanetary("Y")
            # Require planetary or unknown
            station.checkPlanetary("Y?")
            # Require no planetary station
            station.checkPlanetary("N")
        """
        return (not planetary or self.planetary in planetary)
    
    def checkFleet(self, fleet: str) -> bool:
        """
        Same as checkPlanetary, but for fleet carriers.
        """
        return (not fleet or self.fleet in fleet)


    def checkOdyssey(self, odyssey: str) -> bool:
        """
        Same as checkPlanetary, but for Odyssey.
        """
        return (not odyssey or self.odyssey in odyssey)


    def distFromStar(self, addSuffix: bool = False) -> str:
        """
        Returns a textual description of the distance from this
        Station to the parent star.
        
        Args:
            addSuffix[=False]:
                Always add a unit suffix (ls, Kls, ly)
        """
        ls = self.lsFromStar
        if not ls:
            return "Unk" if addSuffix else "?"
        
        suffix = "ls" if addSuffix else ""
        
        if ls < 1000:
            return f"{ls:n}{suffix}"
        if ls < 10000:
            return f"{ls / 1000:.2f}K{suffix}"
        if ls < 1000000:
            return f"{int(ls / 1000):n}K{suffix}"
        return f'{ls / (365*24*60*60):.2f}ly'
    
    @property
    def isTrading(self) -> bool:
        """
        True if the station is thought to be trading.
        
        A station is considered 'trading' if it has an item count > 0 or
        if it's "market" column is flagged 'Y'.
        """
        return (self.itemCount > 0 or self.market == 'Y')
    
    @property
    def itemDataAgeStr(self):
        """ Returns the age in days of item data if present, else "-". """
        if self.itemCount and self.dataAge:
            return f"{self.dataAge:7.2f}"
        return "-"
    
    def text(self) -> str:
        return f"{self.system.dbname}/{self.dbname}"

######################################################################


class Ship(namedtuple('Ship', ('ID', 'dbname', 'cost', 'stations'))):
    """
    Ship description.
    
    Attributes:
        ID          -- FDevID as provided by the companion API.
        dbname      -- The name as present in the database
        cost        -- How many credits to buy
        stations    -- List of Stations ship is sold at.
    """
    
    def name(self, _detail: int = 0) -> str:
        return self.dbname

######################################################################


class Category(namedtuple('Category', ('ID', 'dbname', 'items'))):
    """
    Item Category
    
    Items are organized into categories (Food, Drugs, Metals, etc).
    Category object describes a category's ID, name and list of items.
    
    Attributes:
        ID
            The database ID
        dbname
            The name as present in the database.
        items
            List of Item objects within this category.
    
    Member Functions:
        name()
            Returns the display name for this Category.
    """
    
    def name(self, _detail: int = 0) -> str:
        return self.dbname.upper()

######################################################################


class Item:
    """
    A product that can be bought/sold in the game.
    
    Attributes:
        ID       -- Database ID.
        dbname   -- Name as it appears in-game and in the DB.
        category -- Reference to the category.
        fullname -- Combined category/dbname for lookups.
        avgPrice -- Galactic average as shown in game.
        fdevID   -- FDevID as provided by the companion API.
    """
    __slots__ = ('ID', 'dbname', 'category', 'fullname', 'avgPrice', 'fdevID')
    
    def __init__(self, ID: int, dbname: str, category: 'Category', fullname: str, avgPrice: int | None = None, fdevID: int | None = None) -> None:
        self.ID = ID
        self.dbname = dbname
        self.category = category
        self.fullname = fullname
        self.avgPrice = avgPrice
        self.fdevID   = fdevID
    
    def name(self, detail: int = 0):
        return self.fullname if detail > 0 else self.dbname


######################################################################


class Trade(namedtuple('Trade', (
        'item',
        'costCr', 'gainCr',
        'supply', 'supplyLevel',
        'demand', 'demandLevel',
        'srcAge', 'dstAge'
        ))):
    """
    Describes what it would cost and how much you would gain
    when selling an item between two specific stations.
    """
    def name(self, detail: int = 0) -> str:
        return self.item.name(detail=detail)

######################################################################


class TradeDB:
    """
    Encapsulation for the database layer.
    
    Attributes:
        dataPath
            Path() to the data directory
        dbPath
            Path() of the .db location
        tradingCount
            Number of "profitable trade" items processed
        tradingStationCount
            Number of stations trade data has been loaded for
        tdenv
            The TradeEnv associated with this TradeDB
        sqlPath
            Path() of the .sql file
        pricesPath
            Path() of the .prices file
        importTables
            List of the .csv files
    
    Static methods:
        calculateDistance2(lx, ly, lz, rx, ry, rz)
            Returns the square of the distance in ly between two points.
        
        calculateDistance(lx, ly, lz, rx, ry, rz)
            Returns the distance in ly between two points.
        
        listSearch(...)
            Performs partial and ambiguity matching of a word from a list
            of potential values.
        
        normalizedStr(text)
            Case and punctuation normalizes a string to make it easier
            to find approximate matches.
    """
    
    # Translation map for normalizing strings
    normalizeTrans = str.maketrans(
        'abcdefghijklmnopqrstuvwxyz',
        'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
        '[]()*+-.,{}:'
        )
    trimTrans = str.maketrans('', '', ' \'')
    
    # The DB cache
    defaultDB: str = 'TradeDangerous.db'
    # File containing SQL to build the DB cache from
    defaultSQL: str = 'TradeDangerous.sql'
    # The file we persist to. NOT INTENDED TO BE PERMANENT.
    # We should do the pickling into the database or something.
    persistFile: str = 'TradeDB.pj'  # "pickle jar"
    # # File containing text description of prices
    # defaultPrices = 'TradeDangerous.prices'
    # array containing standard tables, csvfilename and tablename
    # WARNING: order is important because of dependencies!
    defaultTables = (
        ('Added.csv', 'Added'),
        ('System.csv', 'System'),
        ('Station.csv', 'Station'),
        ('Ship.csv', 'Ship'),
        ('ShipVendor.csv', 'ShipVendor'),
        ('Upgrade.csv', 'Upgrade'),
        ('UpgradeVendor.csv', 'UpgradeVendor'),
        ('Category.csv', 'Category'),
        ('Item.csv', 'Item'),
        ('StationItem.csv', 'StationItem'),
        ('RareItem.csv', 'RareItem'),
        ('FDevShipyard.csv', 'FDevShipyard'),
        ('FDevOutfitting.csv', 'FDevOutfitting'),
    )
    
    # Translation matrixes for attributes -> common presentation
    marketStates = planetStates = fleetStates = odysseyStates = {'?': '?', 'Y': 'Yes', 'N': 'No'}
    marketStatesExt = planetStatesExt = fleetStatesExt = odysseyStatesExt = {'?': 'Unk', 'Y': 'Yes', 'N': 'No'}
    padSizes = {'?': '?', 'S': 'Sml', 'M': 'Med', 'L': 'Lrg'}
    padSizesExt = {'?': 'Unk', 'S': 'Sml', 'M': 'Med', 'L': 'Lrg'}
    
    def __init__(
            self,
            tdenv: TradeEnv | None = None,
            load:  bool            = True,
            debug: int | None      = None,
            ) -> None:
        # --- SQLAlchemy engine/session (replaces sqlite3.Connection) ---
        self.engine = None
        self.Session = None
        self.tradingCount = None
        
        # Environment
        tdenv = tdenv or TradeEnv(debug=(debug or 0))
        self.tdenv = tdenv
        
        # --- Path setup (unchanged) ---
        self.templatePath = Path(tdenv.templateDir).resolve()
        self.dataPath = dataPath = fs.ensurefolder(tdenv.dataDir)
        self.csvPath = fs.ensurefolder(tdenv.csvDir)
        
        fs.copy_if_newer(self.templatePath / "Added.csv",       self.csvPath / "Added.csv")
        fs.copy_if_newer(self.templatePath / "RareItem.csv",    self.csvPath / "RareItem.csv")
        fs.copy_if_newer(self.templatePath / "Category.csv",    self.csvPath / "Category.csv")
        fs.copy_if_newer(self.templatePath / "TradeDangerous.sql", self.dataPath / "TradeDangerous.sql")
        
        self.dbPath = Path(tdenv.dbFilename or dataPath / TradeDB.defaultDB)
        self.sqlPath = dataPath / Path(tdenv.sqlFilename or TradeDB.defaultSQL)
        # pricePath   = Path(tdenv.pricesFilename or TradeDB.defaultPrices)
        # self.pricesPath = dataPath / pricePath
        
        # If the database has been deleted, that invalidates any persist file.
        if not self.dbPath:
            self.removePersist()
        
        self.importTables = [
            (str(self.csvPath / Path(fn)), tn)
            for fn, tn in TradeDB.defaultTables
        ]
        self.importPaths = {tn: tp for tp, tn in self.importTables}
        
        self.dbFilename     = str(self.dbPath)
        self.sqlFilename    = str(self.sqlPath)
        # self.pricesFilename = str(self.pricesPath)
        
        # --- Cache attributes (unchanged) ---
        self.avgSelling, self.avgBuying = None, None
        self.tradingStationCount = 0
        self.systemByID     = None
        self.systemByName   = None
        self.stellarGrid    = None
        self.stationByID    = None
        self.categoryByID   = None
        self.itemByID       = None
        self.itemByName     = None
        self.itemByFDevID   = None
        
        # --- Engine bootstrap ---
        
        # Determine user's real invocation directory, not venv/bin
        user_cwd = Path(os.getenv("PWD", Path.cwd()))
        data_dir = user_cwd / "data"
        
        cfg = os.environ.get("TD_DB_CONFIG") or str(data_dir / "db_config.ini")
        
        self.engine = make_engine_from_config(cfg)
        self.Session = get_session_factory(self.engine)


        # --- Initial load ---
        if load:
            self.reloadCache()
            self.load(maxSystemLinkLy=tdenv.maxSystemLinkLy)
    
    # ------------------------------------------------------------------
    # Legacy compatibility dataPath shim
    # ------------------------------------------------------------------
    @property
    def dataDir(self) -> Path:
        """
        Legacy alias for self.dataPath (removed in SQLAlchemy refactor).
        Falls back to './data' if configuration not yet loaded.
        """
        # Try the modern attribute first
        if hasattr(self, "dataPath") and self.dataPath:
            return self.dataPath
        # If we have an environment object, use its dataDir
        if hasattr(self, "tdenv") and getattr(self.tdenv, "dataDir", None):
            return self.tdenv.dataDir
        # Final fallback (first run, pre-bootstrap)
        return Path("./data")
    
    
    @staticmethod
    def calculateDistance2(lx: float, ly: float, lz: float, rx: float, ry: float, rz: float) -> float:
        """ calculateDistance2 returns the *square* (^2) of the euclidean
            distance between two 3d coordinates. This is an optimization
            for when you need to compare many coordinate pairs but do
            not actually need to retain the distance value.
            
            That is:
                distance**2 <=> calculateDistance2(x,y,z, u,v,w)
            always returns the same results as
                distance    <=> calculateDistance (x,y,z, u,v,w)
            but is cheaper.
        """
        dx, dy, dz = lx - rx, ly - ry, lz - rz
        return (dx * dx) + (dy * dy) + (dz * dz)
    
    @staticmethod
    def calculateDistance(lx: float, ly: float, lz: float, rx: float, ry: float, rz: float) -> float:
        """
        calculateDistance returns the euclidean distance in ly between two points.
        @note When you are testing many pairs without retaining the calculated value
        beyond the comparison, consider using calculateDistance2 instead.
        """
        dx, dy, dz = lx - rx, ly - ry, lz - rz
        return math_sqrt((dx * dx) + (dy * dy) + (dz * dz))
    
    @staticmethod
    def _split_system_index(name: str) -> tuple[str, int | None]:
        """
        Split a trailing '@N' suffix from a system name, if present.

        Examples:
            'Lorionis-SOC 13@2' -> ('Lorionis-SOC 13', 2)
            'Shinrarta Dezhra'  -> ('Shinrarta Dezhra', None)
            '@SOL'              -> ('@SOL', None)  # leading @ is a different annotation

        Returns:
            (base_name, index) where index is 1-based, or None if no valid suffix.
        """
        # Ignore a leading '@' which is used as an explicit system/station annotation
        at = name.rfind('@')
        if at <= 0:
            return name, None

        idx_str = name[at + 1 :]
        if not idx_str or not idx_str.isdigit():
            return name, None

        base = name[:at]
        return base, int(idx_str)

    ############################################################
    # Access to the underlying database.
    
    def getDB(self):
        """
        Return a new SQLAlchemy Session bound to this TradeDB engine.
        """
        if not self.engine:
            raise TradeException("Database engine not initialised")
        return self.Session()
    
    def query(self, sql: str, *params):
        """
        Execute a SQL statement via the SQLAlchemy engine and return the result cursor.
        """
        with self.engine.connect() as conn:
            return conn.execute(text(sql), params)
    
    def queryColumn(self, sql: str, *params):
        """
        Execute a SQL statement and return the first column of the first row.
        """
        result = self.query(sql, *params).first()
        return result[0] if result else None
    
    
    def reloadCache(self) -> None:
        """
        Ensure DB is present and minimally populated using the central policy.
        
        Delegates sanity checks to lifecycle.ensure_fresh_db (seconds-only checks):
          - core tables exist (System, Station, Category, Item, StationItem)
          - each has a primary key
          - seed rows exist (Category > 0, System > 0)
          - cheap connectivity probe
        
        If checks fail (or lifecycle decides to force), it will call buildCache(self, self.tdenv)
        to reset/populate via the authoritative path. Otherwise it is a no-op.
        self.tdenv.DEBUG0("reloadCache: engine URL = {}", str(self.engine.url))
        """
        
        kept = False
        
        try:
            summary = ensure_fresh_db(
                backend=self.engine.dialect.name,
                engine=self.engine,
                data_dir=self.dataPath,
                metadata=None,
                mode="auto",
                tdb=self,
                tdenv=self.tdenv,
            )
            action = summary.get("action", "kept")
            if action == "kept":
                kept = True
            reason = summary.get("reason")
            if reason:
                self.tdenv.DEBUG0("reloadCache: ensure_fresh_db → {} (reason: {})", action, reason)
            else:
                self.tdenv.DEBUG0("reloadCache: ensure_fresh_db → {}", action)
        except Exception as e:
            self.tdenv.WARN("reloadCache: ensure_fresh_db failed: {}", e)
            self.tdenv.DEBUG0("reloadCache: Falling back to buildCache()")
            cache.buildCache(self, self.tdenv)
        
        if not kept:
            self.removePersist()
    
    ############################################################
    # [deprecated] "added" data.
    
    def lookupAdded(self, name):
        stmt = select(SA_Added.added_id).where(SA_Added.name == name)
        with self.Session() as session:
            try:
                return session.execute(stmt).scalar_one()
            except NoResultFound:
                raise KeyError(name) from None
    
    ############################################################
    # Star system data.
    
    # TODO: Defer to SA_System as much as possible
    def systems(self) -> Generator['System', Any, None]:
        """ Iterate through the list of systems. """
        yield from self.systemByID.values()
    
    def _loadSystems(self) -> None:
        """
        Initial load of the list of systems via SQLAlchemy.
        CAUTION: Will orphan previously loaded objects.
        """
        systemByID: dict[int, System] = {}
        systemByName: dict[str, list['System']] = {}
        started = time.time()
        with self.Session() as session:
            for row in session.query(
                SA_System.system_id,
                SA_System.name,
                SA_System.pos_x,
                SA_System.pos_y,
                SA_System.pos_z,
                SA_System.added_id,
            ):
                system = System(
                    row.system_id,
                    row.name,
                    row.pos_x,
                    row.pos_y,
                    row.pos_z,
                    row.added_id,
                )
                systemByID[row.system_id] = system
                key = system.dbname.upper()
                bucket = systemByName.get(key)
                if bucket is None:
                    systemByName[key] = [system]
                else:
                    bucket.append(system)

        # Ensure deterministic ordering for duplicate-name groups:
        # sort by posX, then posY, posZ, ID so @1 is lowest X, stable.
        for systems in systemByName.values():
            systems.sort(key=lambda s: (s.posX, s.posY, s.posZ, s.ID))

        self.systemByID = systemByID
        self.systemByName = systemByName
        self.tdenv.DEBUG1(
            "Loaded {:n} Systems in {:.3f}s",
            len(systemByID),
            time.time() - started,
        )
    
    
    def lookupSystem(self, name):
        """
        Lookup a system by name or return a System object unchanged.
        Accepts:
            - System instance  → returned directly
            - Station instance → return station.system
            - str              → resolve by name, with @N disambiguation
        """

        # NEW: accept already-resolved objects
        if isinstance(name, System):
            return name
        if isinstance(name, Station):
            return name.system

        if not isinstance(name, str):
            raise TypeError(
                f"lookupSystem expects str/System/Station, got {type(name)!r}"
            )

        # From here on, name is guaranteed a string.
        base_name, index = self._split_system_index(name)
        base_key = base_name.upper()

        try:
            systems_list = self.systemByName[base_key]
        except KeyError:
            # Fall back to original partial-match behaviour.
            return TradeDB.listSearch(
                "System",
                name,
                self.systems(),
                key=lambda system: system.dbname,
            )

        # No explicit index
        if index is None:
            if len(systems_list) == 1:
                return systems_list[0]
            if len(systems_list) > 1:
                anyMatch = [
                    (i + 1, system)
                    for i, system in enumerate(systems_list)
                ]
                raise AmbiguityError(
                    "System",
                    base_name,
                    anyMatch,
                    key=lambda entry: (
                        f"{entry[1].dbname}@{entry[0]} — "
                        f"({entry[1].posX:.1f}, {entry[1].posY:.1f}, {entry[1].posZ:.1f})"
                    ),
                )
            raise LookupError(f'Error: "{name}" doesn\'t match any known System')

        # Explicit @N index
        if 1 <= index <= len(systems_list):
            return systems_list[index - 1]

        # Out-of-range index
        count = len(systems_list)
        header = f'System "{base_name}" has {count} matching entries (@1..@{count}).'
        invalid_line = f'"{base_name}@{index}" is not a valid index.'
        lines = [header, invalid_line, "", "Use one of the available forms:", ""]
        for idx, system in enumerate(systems_list, start=1):
            lines.append(
                f"    {system.dbname}@{idx} — "
                f"({system.posX:.1f}, {system.posY:.1f}, {system.posZ:.1f})"
            )
        message = "\n".join(lines)
        raise TradeException(message)

    
    def addLocalSystem(
            self,
            name,
            x, y, z,
            modified='now',
            commit=True,
            ) -> System:
        """
        Add a system to the local cache and memory copy using SQLAlchemy.
        Note: 'added' field has been deprecated and is no longer populated.
        """
        with self.Session() as session:
            # Create ORM System row (added_id is deprecated → NULL)
            orm_system = SA_System(
                name=name,
                pos_x=x,
                pos_y=y,
                pos_z=z,
                added_id=None,
                modified=None if modified == 'now' else modified,
            )
            session.add(orm_system)
            if commit:
                session.commit()
            else:
                session.flush()
            
            ID = orm_system.system_id
        
        # Maintain legacy wrapper + caches (added_id always None now)
        system = System(ID, name.upper(), x, y, z, None)
        self.systemByID[ID] = system

        key = system.dbname.upper()
        bucket = self.systemByName.get(key)
        if bucket is None:
            self.systemByName[key] = [system]
        else:
            bucket.append(system)
            bucket.sort(key=lambda s: (s.posX, s.posY, s.posZ, s.ID))
        
        self.tdenv.NOTE(
            "Added new system #{}: {} [{},{},{}]",
            ID, name, x, y, z
        )
        
        return system
    
    
    def updateLocalSystem(
            self, system,
            name, x, y, z, added="Local", modified='now',
            force=False,
            commit=True,
            ) -> bool:
        """
        Update an entry for a local system using SQLAlchemy.
        """
        oldname = system.dbname
        dbname = name.upper()
        
        if not force:
            if (oldname == dbname and
                system.posX == x and
                system.posY == y and
                system.posZ == z):
                return False
        
        # Remove from old name bucket (if present)
        old_key = oldname.upper()
        bucket = self.systemByName.get(old_key)
        if bucket is not None:
            bucket = [s for s in bucket if s is not system]
            if bucket:
                self.systemByName[old_key] = bucket
            else:
                del self.systemByName[old_key]
        
        with self.Session() as session:
            # Find Added row for added_id
            added_row = session.query(SA_Added).filter(SA_Added.name == added).first()
            if not added_row:
                raise TradeException(f"Added entry not found: {added}")
            
            # Load ORM System row
            orm_system = session.get(SA_System, system.ID)
            if not orm_system:
                raise TradeException(f"System ID not found: {system.ID}")
            
            # Apply updates
            orm_system.name = dbname
            orm_system.pos_x = x
            orm_system.pos_y = y
            orm_system.pos_z = z
            orm_system.added_id = added_row.added_id
            orm_system.modified = None if modified == 'now' else modified
            
            if commit:
                session.commit()
            else:
                session.flush()
        
        self.tdenv.NOTE(
            "{} (#{}) updated in {}: {}, {}, {}, {}, {}, {}",
            oldname, system.ID,
            self.dbPath if self.tdenv.detail > 1 else "local db",
            dbname, x, y, z, added, modified,
        )
        
        # Update wrapper caches
        system.dbname = dbname
        system.posX, system.posY, system.posZ = x, y, z
        system.addedID = added_row.added_id

        # Add to new name bucket
        new_key = dbname.upper()
        bucket = self.systemByName.get(new_key)
        if bucket is None:
            self.systemByName[new_key] = [system]
        else:
            bucket.append(system)
            bucket.sort(key=lambda s: (s.posX, s.posY, s.posZ, s.ID))
        
        return True
    
    
    def removeLocalSystem(
            self, system,
            commit=True,
        ):
        """Remove a system and its stations from the local DB using SQLAlchemy."""
        # First remove stations attached to this system
        for stn in self.stations():
            if stn.system == system:
                self.removeLocalStation(stn, commit=False)
        
        with self.Session() as session:
            orm_system = session.get(SA_System, system.ID)
            if orm_system:
                session.delete(orm_system)
                if commit:
                    session.commit()
                else:
                    session.flush()
        
        # Update caches: remove from name bucket and ID map
        key = system.dbname.upper()
        bucket = self.systemByName.get(key)
        if bucket is not None:
            bucket = [s for s in bucket if s is not system]
            if bucket:
                self.systemByName[key] = bucket
            else:
                del self.systemByName[key]
        del self.systemByID[system.ID]
        
        self.tdenv.NOTE(
            "{} (#{}) deleted from {}",
            system.dbname, system.ID,
            self.dbPath if self.tdenv.detail > 1 else "local db",
        )
        
        system.dbname = "DELETED " + system.dbname
        del system
    
    
    def __buildStellarGrid(self) -> None:
        """
        Divides the galaxy into a fixed-sized grid allowing us to
        aggregate small numbers of stars by locality.
        """
        stellarGrid = self.stellarGrid = {}
        for system in self.systemByID.values():
            key = make_stellar_grid_key(system.posX, system.posY, system.posZ)
            try:
                grid = stellarGrid[key]
            except KeyError:
                grid = stellarGrid[key] = []
            grid.append(system)
    
    def genStellarGrid(self, system: 'System', ly: float):
        """
        Yields Systems within a given radius of a specified System.
        
        Args:
            system:
                The System to center the search on,
            ly:
                The radius of the search around system,
        
        Yields:
            (candidate, distLySq)
                candidate:
                    System that was found,
                distLySq:
                    The *SQUARE* of the distance in light-years
                    between system and candidate.
        """
        if self.stellarGrid is None:
            self.__buildStellarGrid()
        
        sysX, sysY, sysZ = system.posX, system.posY, system.posZ
        lwrBound = make_stellar_grid_key(sysX - ly, sysY - ly, sysZ - ly)
        uprBound = make_stellar_grid_key(sysX + ly, sysY + ly, sysZ + ly)
        lySq = ly * ly  # in 64-bit python, ** invokes a function call making it 4x expensive as *.
        stellarGrid = self.stellarGrid
        for x in range(lwrBound[0], uprBound[0]+1):
            for y in range(lwrBound[1], uprBound[1]+1):
                for z in range(lwrBound[2], uprBound[2]+1):
                    try:
                        grid = stellarGrid[(x, y, z)]
                    except KeyError:
                        continue
                    for candidate in grid:
                        delta = candidate.posX - sysX
                        distSq = delta * delta
                        if distSq > lySq:
                            continue
                        delta = candidate.posY - sysY
                        distSq += delta * delta
                        if distSq > lySq:
                            continue
                        delta = candidate.posZ - sysZ
                        distSq += delta * delta
                        if distSq > lySq:
                            continue
                        if candidate is not system:
                            yield candidate, math_sqrt(distSq)
    
    def genSystemsInRange(self, system: 'System', ly: float, includeSelf: bool = False)-> Generator[tuple[System, float], Any, None]:
        """
        Yields Systems within a given radius of a specified System.
        Results are sorted by distance and cached for subsequent
        queries in the same run.
        
        Args:
            system:
                The System to center the search on,
            ly:
                The radius of the search around system,
            includeSelf:
                Whether to include 'system' in the results or not.
        
        Yields:
            (candidate, distLy)
                candidate:
                    System that was found,
                distLy:
                    The distance in lightyears between system and candidate.
        """
        
        cur_cache = system._rangeCache  # pylint: disable=protected-access
        if not cur_cache:
            cur_cache = system._rangeCache = System.RangeCache()
        cached_systems = cur_cache.systems
        
        if ly > cur_cache.probed_ly:
            # Consult the database for stars we haven't seen.
            cached_systems = cur_cache.systems = list(
                self.genStellarGrid(system, ly)
            )
            cached_systems.sort(key=lambda ent: ent[1])
            cur_cache.probed_ly = ly
        
        if includeSelf:
            yield system, 0.
        
        if cur_cache.probed_ly > ly:
            # Cache may contain values outside our view
            for candidate, dist in cached_systems:
                if dist <= ly:
                    yield candidate, dist
        else:
            # No need to be conditional inside the loop
            yield from cached_systems
    
    def getRoute(self, origin, dest, maxJumpLy, avoiding=None, stationInterval=0):
        """
        Find a shortest route between two systems with an additional
        constraint that each system be a maximum of maxJumpLy from
        the previous system.
        
        Args:
            origin:
                System (or station) to start from,
            dest:
                System (or station) to terminate at,
            maxJumpLy:
                Maximum light years between systems,
            avoiding:
                List of systems being avoided
            stationInterval:
                If non-zero, require a station at least this many jumps,
            tdenv.padSize:
                Controls the pad size of stations for refuelling
        
        Returns:
            None
                No route was found
            
            [(origin, 0),...(dest, N)]
                A list of (system, distanceSoFar) values describing
                the route.
        
        Example:
            If there are systems A, B and C such
            that A->B is 7ly and B->C is 8ly then:
                
                origin = lookupPlace("A")
                dest = lookupPlace("C")
                route = tdb.getRoute(origin, dest, 9)
            
            The route should be:
                
                [(System(A), 0), (System(B), 7), System(C), 15)]
        
        """
        
        if avoiding is None:
            avoiding = []
        
        if isinstance(origin, Station):
            origin = origin.system
        if isinstance(dest, Station):
            dest = dest.system
        
        if origin == dest:
            return ((origin, 0), (dest, 0))
        
        # openSet is the list of nodes we want to visit, which will be
        # used as a priority queue (heapq).
        # Each element is a tuple of the 'priority' (the combination of
        # the total distance to the node and the distance left from the
        # node to the destination.
        openSet = [(0, 0, origin.ID, 0)]
        # Track predecessor nodes for everwhere we visit
        distances = {origin: (None, 0)}
        
        if avoiding:
            if dest in avoiding:
                raise ValueError("Destination is in avoidance list")
            for avoid in avoiding:
                if isinstance(avoid, System):
                    distances[avoid] = (None, -1)
        
        systemsInRange = self.genSystemsInRange
        heappop  = heapq.heappop
        heappush = heapq.heappush
        distTo = float("inf")
        defaultDist = (None, distTo)
        getDist  = distances.get
        
        destID = dest.ID
        sysByID = self.systemByID
        
        maxPadSize = self.tdenv.padSize
        if not maxPadSize:
            def checkStations(system: System) -> bool:  # pylint: disable=function-redefined, missing-docstring
                return bool(system.stations())
        else:
            def checkStations(system: System) -> bool:  # pylint: disable=function-redefined, missing-docstring
                return any(stn for stn in system.stations if stn.checkPadSize(maxPadSize))
        
        while openSet:
            weight, curDist, curSysID, stnDist = heappop(openSet)
            # If we reached 'goal' we've found the shortest path.
            if curSysID == destID:
                break
            if curDist >= distTo:
                continue
            curSys = sysByID[curSysID]
            # A node might wind up multiple times on the open list,
            # so check if we've already found a shorter distance to
            # the system and if so, ignore it this time.
            if curDist > distances[curSys][1]:
                continue
            
            system_iter = iter(systemsInRange(curSys, maxJumpLy))
            if stationInterval:
                if checkStations(curSys):
                    stnDist = 0
                else:
                    stnDist += 1
                    if stnDist >= stationInterval:
                        system_iter = iter(
                            v for v in system_iter if checkStations(v[0])
                        )
            
            distFn = curSys.distanceTo
            for nSys, nDist in system_iter:
                newDist = curDist + nDist
                if getDist(nSys, defaultDist)[1] <= newDist:
                    continue
                distances[nSys] = (curSys, newDist)
                weight = distFn(nSys)
                nID = nSys.ID
                heappush(openSet, (newDist + weight, newDist, nID, stnDist))
                if nID == destID:
                    distTo = newDist
        
        if dest not in distances:
            return None
        
        path = []
        
        while True:
            (prevSys, dist) = getDist(dest)
            path.append((dest, dist))
            if dest == origin:
                break
            dest = prevSys
        
        path.reverse()
        
        return path
    
    ############################################################
    # Station data.
    
    def stations(self) -> 'Generator[Station, None, None]':
        """ Iterate through the list of stations. """
        yield from self.stationByID.values()
    
    def _loadStations(self):
        """
        Populate the Station list using SQLAlchemy.
        Station constructor automatically adds itself to the System object.
        CAUTION: Will orphan previously loaded objects.
        """
        # NOTE: Requires module-level import:
        #   from tradedangerous.db.utils import age_in_days
        stationByID = {}
        systemByID = self.systemByID
        self.tradingStationCount = 0
        
        # Fleet Carriers are station type 24.
        # Odyssey settlements are station type 25.
        # Assume type 0 (Unknown) are also Fleet Carriers.
        carrier_types = (24, 0)
        odyssey_type  = 25
        cached_system = None
        cached_system_id = None
        
        started = time.time()
        with self.Session() as session:
            # Query all stations
            rows = session.query(
                SA_Station.station_id,
                SA_Station.system_id,
                SA_Station.name,
                SA_Station.ls_from_star,
                SA_Station.market,
                SA_Station.blackmarket,
                SA_Station.shipyard,
                SA_Station.max_pad_size,
                SA_Station.outfitting,
                SA_Station.rearm,
                SA_Station.refuel,
                SA_Station.repair,
                SA_Station.planetary,
                SA_Station.type_id,
            )
        
        for (
            ID, systemID, name,
            lsFromStar, market, blackMarket, shipyard,
            maxPadSize, outfitting, rearm, refuel, repair, planetary, type_id
        ) in rows:
            isFleet   = 'Y' if type_id in carrier_types else 'N'
            isOdyssey = 'Y' if type_id == odyssey_type  else 'N'
            if systemID != cached_system_id:
                cached_system_id = systemID
                cached_system = systemByID[cached_system_id]
            stationByID[ID] = Station(
                ID, cached_system, name,
                lsFromStar, market, blackMarket, shipyard,
                maxPadSize, outfitting, rearm, refuel, repair,
                planetary, isFleet, isOdyssey,
                0, None,
            )
        
        # Trading station info
        tradingCount = 0
        rows = (
            session.query(
                SA_StationItem.station_id,
                func.count().label("item_count"),
                # Dialect-safe average age in **days**
                func.avg(age_in_days(session, SA_StationItem.modified)).label("data_age_days"),
            )
            .group_by(SA_StationItem.station_id)
            .having(func.count() > 0)
        )
        
        for ID, itemCount, dataAge in rows:
            station = stationByID[ID]
            station.itemCount = itemCount
            station.dataAge = dataAge
            tradingCount += 1
        
        self.stationByID = stationByID
        self.tradingStationCount = tradingCount
        self.tdenv.DEBUG1("Loaded {:n} Stations in {:.3f}s", len(stationByID), (time.time() - started) * 1000)
        self.stellarGrid = None
    
    def addLocalStation(
            self,
            system,
            name,
            lsFromStar,
            market,
            blackMarket,
            shipyard,
            maxPadSize,
            outfitting,
            rearm,
            refuel,
            repair,
            planetary,
            fleet,
            odyssey,
            modified='now',
            commit=True,
            ):
        """
        Add a station to the local cache and memory copy using SQLAlchemy.
        """
        # Normalise/validate inputs
        market      = market.upper()
        blackMarket = blackMarket.upper()
        shipyard    = shipyard.upper()
        maxPadSize  = maxPadSize.upper()
        outfitting  = outfitting.upper()
        rearm       = rearm.upper()
        refuel      = refuel.upper()
        repair      = repair.upper()
        planetary   = planetary.upper()
        assert market in "?YN"
        assert blackMarket in "?YN"
        assert shipyard in "?YN"
        assert maxPadSize in "?SML"
        assert outfitting in "?YN"
        assert rearm in "?YN"
        assert refuel in "?YN"
        assert repair in "?YN"
        assert planetary in "?YN"
        assert fleet in "?YN"
        assert odyssey in "?YN"
        
        # Type mapping
        type_id = 0
        if fleet == 'Y':
            type_id = 24
        if odyssey == 'Y':
            type_id = 25
        
        with self.Session() as session:
            orm_station = SA_Station(
                name=name,
                system_id=system.ID,
                ls_from_star=lsFromStar,
                market=market,
                blackmarket=blackMarket,
                shipyard=shipyard,
                max_pad_size=maxPadSize,
                outfitting=outfitting,
                rearm=rearm,
                refuel=refuel,
                repair=repair,
                planetary=planetary,
                type_id=type_id,
                modified=None if modified == 'now' else modified,
            )
            session.add(orm_station)
            if commit:
                session.commit()
            else:
                session.flush()
            ID = orm_station.station_id
        
        # Legacy wrapper object
        station = Station(
            ID, system, name,
            lsFromStar=lsFromStar,
            market=market,
            blackMarket=blackMarket,
            shipyard=shipyard,
            maxPadSize=maxPadSize,
            outfitting=outfitting,
            rearm=rearm,
            refuel=refuel,
            repair=repair,
            planetary=planetary,
            fleet=fleet,
            odyssey=odyssey,
            itemCount=0,
            dataAge=0,
        )
        self.stationByID[ID] = station
        
        self.tdenv.NOTE(
            "{} (#{}) added to {}: "
            "ls={}, mkt={}, bm={}, yard={}, pad={}, "
            "out={}, arm={}, ref={}, rep={}, plt={}, "
            "mod={}",
            station.name(), station.ID,
            self.dbPath if self.tdenv.detail > 1 else "local db",
            lsFromStar, market, blackMarket, shipyard, maxPadSize,
            outfitting, rearm, refuel, repair, planetary,
            modified,
        )
        return station
    
    def updateLocalStation(
            self, station,
            name=None,
            lsFromStar=None,
            market=None,
            blackMarket=None,
            shipyard=None,
            maxPadSize=None,
            outfitting=None,
            rearm=None,
            refuel=None,
            repair=None,
            planetary=None,
            fleet=None,
            odyssey=None,
            modified='now',
            force=False,
            commit=True,
            ):
        """
        Alter the properties of a station in-memory and in the DB using SQLAlchemy.
        """
        changes = []
        
        def _changed(label, old, new):
            changes.append(f"{label}('{old}'=>'{new}')")
        
        # Mutate wrapper + record changes
        if name is not None:
            if force or name.upper() != station.dbname.upper():
                _changed("name", station.dbname, name)
                station.dbname = name
        
        if lsFromStar is not None:
            assert lsFromStar >= 0
            if lsFromStar != station.lsFromStar:
                if lsFromStar > 0 or force:
                    _changed("ls", station.lsFromStar, lsFromStar)
                    station.lsFromStar = lsFromStar
        
        def _check_setting(label, attr_name, newValue, allowed):
            if newValue is not None:
                newValue = newValue.upper()
                assert newValue in allowed
                oldValue = getattr(station, attr_name, '?')
                if newValue != oldValue and (force or newValue != '?'):
                    _changed(label, oldValue, newValue)
                    setattr(station, attr_name, newValue)
        
        _check_setting("pad", "maxPadSize", maxPadSize, TradeDB.padSizes)
        _check_setting("mkt", "market", market, TradeDB.marketStates)
        _check_setting("blk", "blackMarket", blackMarket, TradeDB.marketStates)
        _check_setting("shp", "shipyard", shipyard, TradeDB.marketStates)
        _check_setting("out", "outfitting", outfitting, TradeDB.marketStates)
        _check_setting("arm", "rearm", rearm, TradeDB.marketStates)
        _check_setting("ref", "refuel", refuel, TradeDB.marketStates)
        _check_setting("rep", "repair", repair, TradeDB.marketStates)
        _check_setting("plt", "planetary", planetary, TradeDB.planetStates)
        _check_setting("flc", "fleet", fleet, TradeDB.fleetStates)
        _check_setting("ody", "odyssey", odyssey, TradeDB.odysseyStates)
        
        if not changes:
            return False
        
        with self.Session() as session:
            orm_station = session.get(SA_Station, station.ID)
            if not orm_station:
                raise TradeException(f"Station ID not found: {station.ID}")
            
            orm_station.name         = station.dbname
            orm_station.system_id    = station.system.ID
            orm_station.ls_from_star = station.lsFromStar
            orm_station.market       = station.market
            orm_station.blackmarket  = station.blackMarket
            orm_station.shipyard     = station.shipyard
            orm_station.max_pad_size = station.maxPadSize
            orm_station.outfitting   = station.outfitting
            orm_station.rearm        = station.rearm
            orm_station.refuel       = station.refuel
            orm_station.repair       = station.repair
            orm_station.planetary    = station.planetary
            orm_station.type_id      = (
                24 if station.fleet == 'Y' else
                25 if station.odyssey == 'Y' else 0
            )
            orm_station.modified     = None if modified == 'now' else modified
            
            if commit:
                session.commit()
            else:
                session.flush()
        
        self.tdenv.NOTE(
            "{} (#{}) updated in {}: {}",
            station.name(), station.ID,
            self.dbPath if self.tdenv.detail > 1 else "local db",
            ", ".join(changes)
        )
        
        return True
    
    def removeLocalStation(self, station, commit=True):
        """
        Remove a station from the local database and memory image using SQLAlchemy.
        Be careful of any references to the station you may still have after this.
        """
        # Remove reference from parent system (wrapper-level)
        system = station.system
        if station in system.stations:
            system.stations.remove(station)
        
        # Remove from ID lookup cache
        if station.ID in self.stationByID:
            del self.stationByID[station.ID]
        
        # Delete from DB
        with self.Session() as session:
            orm_station = session.get(SA_Station, station.ID)
            if orm_station:
                session.delete(orm_station)
                if commit:
                    session.commit()
                else:
                    session.flush()
        
        self.tdenv.NOTE(
            "{} (#{}) deleted from {}",
            station.name(), station.ID,
            self.dbPath if self.tdenv.detail > 1 else "local db",
        )
        
        station.dbname = "DELETED " + station.dbname
        del station
    
    def lookupPlace(self, name):
        """
        Lookup the station/system specified by 'name' which can be the
        name of a System or Station or it can be "System/Station" when
        the user needs to disambiguate a station. In this case, both
        system and station can be partial matches.
        
        The system tries to allow partial matches as well as matches
        which omit whitespaces. In order to do this and still support
        the massive namespace of Stars and Systems, we rank the
        matches so that exact matches win, and only inferior close
        matches are looked at if no exacts are found.
        
        Legal annotations:
            system
            station
            @system    [explicitly a system name]
            /station   [explicitly a station name]
            system/station
            @system/station
        """
        # Pass-through for already-resolved objects
        if isinstance(name, (System, Station)):
            return name

        if not isinstance(name, str):
            raise TypeError(
                f"lookupPlace expects str/System/Station, got {type(name)!r}"
            )

        # ------------------------------------------------------------------
        # Fast path: queries that look like "just a system name"
        #
        # This path is where the new name-collision behaviour lives so that
        # lookupPlace honours:
        #   - multiple systems with the same name, and
        #   - the "@N" index notation (e.g. "Lorionis-SOC 13@2").
        #
        # We exclude:
        #   - leading "/" (explicit station)
        #   - any "/" or "\\" inside the string (system/station combos)
        # ------------------------------------------------------------------
        if not name.startswith("/") and "/" not in name and "\\" not in name:
            sys_key = name[1:] if name.startswith("@") else name
            try:
                return self.lookupSystem(sys_key)
            except AmbiguityError:
                # lookupSystem already produces the rich "@N" hint text for
                # ambiguous system names; preserve it unchanged.
                raise
            except TradeException:
                # e.g. "System@999" out of range – message is already correct.
                raise
            except LookupError:
                # Not a system (or no reasonable system match) – fall back to
                # the generic place logic below to search stations as well.
                pass

        # ------------------------------------------------------------------
        # Legacy combined system/station matching
        # ------------------------------------------------------------------

        # Determine whether the user specified a system, a station, or both.
        slash_pos = name.find("/")
        if slash_pos < 0:
            slash_pos = name.find("\\")  # support old "sys\stn" syntax too

        # Leading '@' indicates "this is a system name"
        name_off = 1 if name.startswith("@") else 0

        if slash_pos > name_off:
            # "sys/station" or "@sys/station"
            sys_name = name[name_off:slash_pos].upper()
            stn_name = name[slash_pos + 1 :]
        elif slash_pos == name_off:
            # "/station" — explicit station, no system
            sys_name, stn_name = None, name[name_off + 1 :]
        elif name_off:
            # "@system" — explicit system, no station
            sys_name, stn_name = name[name_off:].upper(), None
        else:
            # Bare name: treat as both potential system and station.
            stn_name = name
            sys_name = stn_name.upper()

        exact_match = []
        close_match = []
        word_match = []
        any_match = []

        def _lookup(token, candidates):
            """Populate the match lists for the given search token."""
            norm_trans = TradeDB.normalizeTrans
            trim_trans = TradeDB.trimTrans

            token_norm = token.translate(norm_trans)
            token_trim = token_norm.translate(trim_trans)

            token_len = len(token)
            token_norm_len = len(token_norm)
            token_trim_len = len(token_trim)

            for place in candidates:
                place_name = place.dbname
                place_norm = place_name.translate(norm_trans)
                place_norm_len = len(place_norm)

                # If the trimmed needle is longer than the target, it can't match
                if token_trim_len > place_norm_len:
                    continue

                # 1) Exact name + normalization match
                if len(place_name) == token_len and place_norm == token_norm:
                    exact_match.append(place)
                    continue

                # 2) Same normalized length and contents -> "close" match
                if place_norm_len == token_norm_len and place_norm == token_norm:
                    close_match.append(place)
                    continue

                # 3) Substring of the normalized name, with word-boundary checks
                if token_norm_len < place_norm_len:
                    pos = place_norm.find(token_norm)
                    if pos == 0:
                        # At the start of the name
                        if place_norm[token_norm_len:token_norm_len + 1] == " ":
                            word_match.append(place)
                        else:
                            any_match.append(place)
                        continue

                    if pos > 0:
                        before = place_norm[pos - 1:pos]
                        after = place_norm[pos + token_norm_len:pos + token_norm_len + 1]
                        if before == " " and after == " ":
                            word_match.append(place)
                        else:
                            any_match.append(place)
                        continue

                # 4) Compare with whitespace and punctuation stripped
                place_trim = place_norm.translate(trim_trans)
                place_trim_len = len(place_trim)
                if place_trim_len == place_norm_len:
                    # Normalization didn't change anything; nothing new to learn
                    continue

                # A fully-trimmed exact match is still "close"
                if place_trim_len == token_trim_len and place_trim == token_trim:
                    close_match.append(place)
                    continue

                # Otherwise, any occurrence inside the trimmed name is "any"
                if token_trim and place_trim.find(token_trim) >= 0:
                    any_match.append(place)

        # First, resolve the system side if we have one.
        if sys_name:
            systems_bucket = self.systemByName.get(sys_name)
            if systems_bucket:
                # In older caches, systemByName held a single System; in the
                # new collision-aware form it holds a list[System].
                if isinstance(systems_bucket, System):
                    exact_match.append(systems_bucket)
                else:
                    # Assume it's an iterable of System instances.
                    exact_match.extend(systems_bucket)
            else:
                _lookup(sys_name, self.systemByID.values())

        # Now resolve the station side, if requested.
        if stn_name:
            # If both system and station were provided (sys/station form), we
            # try to narrow the station search to the systems we just matched.
            if slash_pos > name_off + 1 and (exact_match or close_match or word_match or any_match):
                station_candidates = []
                for system in itertools.chain(
                    exact_match, close_match, word_match, any_match
                ):
                    station_candidates.extend(system.stations)

                # Reset the match tiers; from here on they refer to stations.
                exact_match = []
                close_match = []
                word_match = []
                any_match = []
            else:
                # No usable system context: search all stations.
                station_candidates = self.stationByID.values()

            _lookup(stn_name, station_candidates)

        # Consult the match tiers in order; any single-element tier is a winner.
        for tier in (exact_match, close_match, word_match, any_match):
            if len(tier) == 1:
                return tier[0]

        # No matches at all
        if not (exact_match or close_match or word_match or any_match):
            # NOTE: Historically this was a TradeException; it was changed to
            # LookupError so callers can distinguish "nothing matched" from
            # "ambiguous".
            raise LookupError(f"Unrecognized place: {name}")

        # Multiple matches – ambiguous. For mixed system/station cases we keep
        # the original "System/Station" label; pure system ambiguities should
        # already have been caught by lookupSystem above.
        raise AmbiguityError(
            "System/Station",
            name,
            exact_match + close_match + word_match + any_match,
            key=lambda place: place.name(),
        )

        
        def lookup(name, candidates):
            """ Search candidates for the given name """
            
            normTrans = TradeDB.normalizeTrans
            trimTrans = TradeDB.trimTrans
            
            nameNorm = name.translate(normTrans)
            nameTrimmed = nameNorm.translate(trimTrans)
            
            nameLen = len(name)
            nameNormLen = len(nameNorm)
            nameTrimmedLen = len(nameTrimmed)
            
            for place in candidates:
                placeName = place.dbname
                placeNameNorm = placeName.translate(normTrans)
                placeNameNormLen = len(placeNameNorm)
                
                if nameTrimmedLen > placeNameNormLen:
                    # The needle is bigger than this haystack.
                    continue
                
                # If the lengths match, do a direct comparison.
                if len(placeName) == nameLen:
                    if placeNameNorm == nameNorm:
                        exactMatch.append(place)
                    continue
                if placeNameNormLen == nameNormLen:
                    if placeNameNorm == nameNorm:
                        closeMatch.append(place)
                    continue
                
                if nameNormLen < placeNameNormLen:
                    subPos = placeNameNorm.find(nameNorm)
                    if subPos == 0:
                        if placeNameNorm[nameNormLen] == ' ':
                            # first word
                            wordMatch.append(place)
                        else:
                            anyMatch.append(place)
                        continue
                    
                    if subPos > 0:
                        if placeNameNorm[subPos] == ' ' and \
                                placeNameNorm[subPos + nameNormLen] == ' ':
                            wordMatch.append(place)
                        else:
                            anyMatch.append(place)
                        continue
                
                # Lets drop whitespace and remaining punctuation...
                placeNameTrimmed = placeNameNorm.translate(trimTrans)
                placeNameTrimmedLen = len(placeNameTrimmed)
                if placeNameTrimmedLen == placeNameNormLen:
                    # No change
                    continue
                
                # A match here is not exact but still fairly interesting
                if len(placeNameTrimmed) == nameTrimmedLen:
                    if placeNameTrimmed == nameTrimmed:
                        closeMatch.append(place)
                        continue
                elif placeNameTrimmedLen > nameTrimmedLen:
                    if placeNameTrimmed.find(nameTrimmed) >= 0:
                        anyMatch.append(place)
                        continue
                # Skip smaller names
        
        if sysName:
            systems = self.systemByName.get(sysName)
            if systems:
                # For now, treat the first system as the exact match.
                # Proper duplicate-name disambiguation comes in the next step.
                exactMatch = [systems[0]]
            else:
                lookup(sysName, self.systemByID.values())
        
        if stnName:
            # Are we considering the name as a station?
            # (we don't if they type, e,g '@aulin')
            # compare against nameOff to allow '@/station'
            if slashPos > nameOff + 1:
                # "sys/station"; the user should have specified a system
                # name and we should be able to narrow down which
                # stations we compare against. Check first if there are
                # any matches.
                stationCandidates = []
                for system in itertools.chain(
                        exactMatch, closeMatch, wordMatch, anyMatch
                        ):
                    stationCandidates += system.stations
                # Clear out the candidate lists
                exactMatch = []
                closeMatch = []
                wordMatch = []
                anyMatch = []
            else:
                # Consider against all station names
                stationCandidates = self.stationByID.values()
            lookup(stnName, stationCandidates)
        
        # consult the match sets in ranking order for a single
        # match, which denotes a win at that tier. For example,
        # if there is one exact match, we don't care how many
        # close matches there were.
        for matchSet in exactMatch, closeMatch, wordMatch, anyMatch:
            if len(matchSet) == 1:
                return matchSet[0]
        
        # Nothing matched
        if not any([exactMatch, closeMatch, wordMatch, anyMatch]):
            # Note: this was a TradeException and may need to be again,
            # but then we need to catch that error in commandenv
            # when we process avoids
            raise LookupError(f"Unrecognized place: {name}")
        
        # More than one match
        raise AmbiguityError(
            'System/Station', name,
            exactMatch + closeMatch + wordMatch + anyMatch,
            key=lambda place: place.name()
        )
    
    def lookupStation(self, name, system=None):
        """
        Look up a Station object by it's name or system.
        """
        if isinstance(name, Station):
            return name
        if isinstance(name, System):
            # When given a system with only one station, return the station.
            if len(name.stations) != 1:
                raise SystemNotStationError(f"System '{name}' has {len(name.stations)} stations, please specify a station instead.")
            return name.stations[0]
        
        if system:
            system = self.lookupSystem(system)
            return TradeDB.listSearch(
                "Station", name, system.stations,
                key=lambda system: system.dbname)
        
        station, system = None, None
        try:
            system = TradeDB.listSearch(
                "System", name, self.systemByID.values(),
                key=lambda system: system.dbname
            )
        except LookupError:
            pass
        try:
            station = TradeDB.listSearch(
                "Station", name, self.stationByID.values(),
                key=lambda station: station.dbname
            )
        except LookupError:
            pass
        # If neither matched, we have a lookup error.
        if not (station or system):
            raise LookupError(f"'{name}' did not match any station or system.")
        
        # If we matched both a station and a system, make sure they resovle to
        # the same station otherwise we have an ambiguity. Some stations have
        # the same name as their star system (Aulin/Aulin Enterprise)
        if system and station and system != station.system:
            raise AmbiguityError(
                'Station', name, [system.name(), station.name()]
            )
        
        if station:
            return station
        
        # If we only matched a system name, ensure that it's a single station
        # system otherwise they need to specify a station name.
        if len(system.stations) != 1:
            raise SystemNotStationError(
                f"System '{system.name()}' has {len(system.stations)} stations, please specify a station instead."
            )
        return system.stations[0]
    
    def getDestinations(
            self,
            origin,
            maxJumps=None,
            maxLyPer=None,
            avoidPlaces=None,
            maxPadSize=None,
            maxLsFromStar=0,
            noPlanet=False,
            planetary=None,
            fleet=None,
            odyssey=None,
            ):
        """
        Gets a list of the Station destinations that can be reached
        from this Station within the specified constraints.
        Limits to stations we are trading with if trading is True.
        """
        
        if maxJumps is None:
            maxJumps = sys.maxsize
        maxLyPer = maxLyPer or self.maxSystemLinkLy
        if avoidPlaces is None:
            avoidPlaces = ()
        
        # The open list is the list of nodes we should consider next for
        # potential destinations.
        # The path list is a list of the destinations we've found and the
        # shortest path to them. It doubles as the "closed list".
        # The closed list is the list of nodes we've already been to (so
        # that we don't create loops A->B->C->A->B->C->...)
        
        origSys = origin.system if isinstance(origin, Station) else origin
        openList = [DestinationNode(origSys, [origSys], 0)]
        # I don't want to have to consult both the pathList
        # AND the avoid list every time I'm considering a
        # station, so copy the avoid list into the pathList
        # with a negative distance so I can ignore them again
        # when I scrape the pathList.
        # Don't copy stations because those only affect our
        # termination points, and not the systems we can
        # pass through en-route.
        pathList = {
            system.ID: DestinationNode(system, None, -1.0)
            for system in avoidPlaces
            if isinstance(system, System)
        }
        if origSys.ID not in pathList:
            pathList[origSys.ID] = openList[0]
        
        # As long as the open list is not empty, keep iterating.
        jumps = 0
        while openList and jumps < maxJumps:
            # Expand the search domain by one jump; grab the list of
            # nodes that are this many hops out and then clear the list.
            ring, openList = openList, []
            # All of the destinations we are about to consider will
            # either be on the closed list or they will be +1 jump away.
            jumps += 1
            
            ring.sort(key=lambda dn: dn.distLy)
            
            for node in ring:
                for (destSys, destDist) in self.genSystemsInRange(
                        node.system, maxLyPer, False
                        ):
                    dist = node.distLy + destDist
                    # If we already have a shorter path, do nothing
                    try:
                        prevDist = pathList[destSys.ID].distLy
                    except KeyError:
                        pass
                    else:
                        if dist >= prevDist:
                            continue
                    # Add to the path list
                    destNode = DestinationNode(
                        destSys, node.via + [destSys], dist
                    )
                    pathList[destSys.ID] = destNode
                    # Add to the open list but also include node to the via
                    # list so that it serves as the via list for all next-hops.
                    openList.append(destNode)
        
        # We have a system-to-system path list, now we
        # need stations to terminate at.
        def path_iter_fn():
            for node in pathList.values():
                if node.distLy >= 0.0:
                    for station in node.system.stations:
                        yield node, station
        
        path_iter = iter(
          (node, station) for (node, station) in path_iter_fn()
          if (station.planetary == 'N' if noPlanet else True) and
            (station not in avoidPlaces if avoidPlaces else True) and
            (station.checkPadSize(maxPadSize) if maxPadSize else True) and
            (station.checkPlanetary(planetary) if planetary else True) and
            (station.checkFleet(fleet) if fleet else True) and
            (station.checkOdyssey(odyssey) if odyssey else True) and
            (station.lsFromStar > 0 and station.lsFromStar <= maxLsFromStar if maxLsFromStar else True)
        )
        for node, stn in path_iter:
            yield Destination(node.system, stn, node.via, node.distLy)
    
    ############################################################
    # Ship data.
    
    @lru_cache
    def lookupShip(self, name):
        """ Look up a ship by name. """
        stmt = select(SA_Ship.ship_id, SA_Ship.name, SA_Ship.cost)   \
                   .where(Ship.name == name)
        with self.Session() as session:
            try:
                row = session.execute(stmt).scalar_one()
                return Ship(row.ship_id, row.name, row.cost, stations=[])
            except NoResultFound:
                raise LookupError(f"Error: '{name}' doesn't match any Ship") from None
    
    ############################################################
    # Item data.
    
    # TODO: Defer to SA_Category directly; requires migrating
    # all item references to the SA_Item table too (since then
    # the database relationship handles inheritance anyway)
    def categories(self):
        """
        Iterate through the list of categories.
        key = category name, value = list of items.
        """
        yield from self.categoryByID.items()
    
    def _loadCategories(self):
        """
        Populate the list of item categories using SQLAlchemy.
        CAUTION: Will orphan previously loaded objects.
        """
        with self.Session() as session:
            rows = session.query(
                SA_Category.category_id,
                SA_Category.name,
            )
            self.categoryByID = {
                row.category_id: Category(row.category_id, row.name, [])
                for row in rows
            }
        
        self.tdenv.DEBUG1("Loaded {} Categories", len(self.categoryByID))
    
    def lookupCategory(self, name):
        """
        Look up a category by name
        """
        return TradeDB.listSearch(
            "Category", name,
            self.categoryByID.values(),
            key=lambda cat: cat.dbname
        )
    
    # TODO: Defer to SA_Item directly.
    def items(self):
        """ Iterate through the list of items. """
        yield from self.itemByID.values()
    
    def _loadItems(self):
        """
        Populate the Item list using SQLAlchemy.
        CAUTION: Will orphan previously loaded objects.
        """
        itemByID, itemByName, itemByFDevID = {}, {}, {}
        with self.Session() as session:
            rows = session.query(
                SA_Item.item_id,
                SA_Item.name,
                SA_Item.category_id,
                SA_Item.avg_price,
                SA_Item.fdev_id,
            )
            for ID, name, categoryID, avgPrice, fdevID in rows:
                category = self.categoryByID[categoryID]
                item = Item(
                    ID, name, category,
                    f"{category.dbname}/{name}",
                    avgPrice, fdevID
                )
                itemByID[ID] = item
                itemByName[name] = item
                if fdevID:
                    itemByFDevID[fdevID] = item
                category.items.append(item)
        
        self.itemByID = itemByID
        self.itemByName = itemByName
        self.itemByFDevID = itemByFDevID
        
        self.tdenv.DEBUG1("Loaded {:n} Items", len(self.itemByID))
    
    def lookupItem(self, name):
        """
            Look up an Item by name using "CATEGORY/Item"
        """
        return TradeDB.listSearch(
            "Item", name, self.itemByName.items(),
            key=lambda kvTup: kvTup[0],
            val=lambda kvTup: kvTup[1]
        )
    
    def getAverageSelling(self):
        """
        Query the database for average selling prices of all items using SQLAlchemy.
        """
        if not self.avgSelling:
            self.avgSelling = {itemID: 0 for itemID in self.itemByID}
            
            with self.Session() as session:
                rows = (
                    session.query(
                        SA_Item.item_id,
                        func.ifnull(func.avg(SA_StationItem.supply_price), 0),
                    )
                    .outerjoin(
                        SA_StationItem,
                        (SA_Item.item_id == SA_StationItem.item_id) &
                        (SA_StationItem.supply_price > 0),
                    )
                    .filter(SA_StationItem.supply_price > 0)
                    .group_by(SA_Item.item_id)
                )
                for ID, cr in rows:
                    self.avgSelling[ID] = int(cr)
        
        return self.avgSelling
    
    def getAverageBuying(self):
        """
        Query the database for average buying prices of all items using SQLAlchemy.
        """
        if not self.avgBuying:
            self.avgBuying = {itemID: 0 for itemID in self.itemByID}
            
            with self.Session() as session:
                rows = (
                    session.query(
                        SA_Item.item_id,
                        func.ifnull(func.avg(SA_StationItem.demand_price), 0),
                    )
                    .outerjoin(
                        SA_StationItem,
                        (SA_Item.item_id == SA_StationItem.item_id) &
                        (SA_StationItem.demand_price > 0),
                    )
                    .filter(SA_StationItem.demand_price > 0)
                    .group_by(SA_Item.item_id)
                )
                for ID, cr in rows:
                    self.avgBuying[ID] = int(cr)
        
        return self.avgBuying
    
    
    ############################################################
    # Price data.
    
    def close(self, *, final: bool = False) -> None:
        if self.Session and final:
            del self.Session
        if self.engine:
            self.engine.dispose()
        if final:
            engine, self.engine = self.engine, None
            del engine
        # Keep engine + Session references so reloadCache/buildCache can reuse them
    
    def load(self, maxSystemLinkLy=None):
        """
            Populate/re-populate this instance of TradeDB with data.
            WARNING: This will orphan existing records you have
            taken references to:
                tdb.load()
                x = tdb.lookupPlace("Aulin")
                tdb.load() # x now points to an orphan Aulin
        """
        
        self.tdenv.DEBUG1("Loading data")
        
        # Try and restore the data from the previous load.
        if not self.readPersist():
            started = time.time()
            self._loadSystems()
            self._loadStations()
            self._loadCategories()
            self._loadItems()
            self.tdenv.DEBUG0("Data load took {:.3f}s", time.time() - started)
            
            started = time.time()
            self.writePersist()
            self.tdenv.DEBUG1("Data persist took {:.3f}s", time.time() - started)
        
        # Calculate the maximum distance anyone can jump so we can constrain
        # the maximum "link" between any two stars.
        msll = maxSystemLinkLy or self.tdenv.maxSystemLinkLy or 30
        self.maxSystemLinkLy = msll
    
    def getPersistPath(self) -> Path:
        """ getPersistPath returns the filepath of the file used to store a snapshot
            of a previously constructed TradeDB object.
            kfsone: I felt "trade.pickle" would draw confused attention,
                    so I went with "pj" for 'pickle jar' because it actually
                    contains two pickles, not just one. """
        return Path(self.dataPath, TradeDB.persistFile)
    
    def readPersist(self) -> bool:
        """ readPersist will attempt to reconstitute the members of TradeDB
            that were persisted to disk from a previous session. """
        jarPath = self.getPersistPath()
        started = time.time()
        try:
            with open(jarPath, "rb") as jar:
                if self._readPickleFrom(jar):
                    self.tdenv.DEBUG0("Persist load took {:.3f}s", time.time() - started)
                    return True
        except FileNotFoundError as e:
            self.tdenv.DEBUG0("No persistence file to restore: {}: {}", jarPath, e)
        except pickle.UnpicklingError as e:
            self.tdenv.DEBUG0("Error restoring persistence data: {}: {}", jarPath, e)
        except PermissionError as e:
            self.tdenv.WARN("Unable to reconstitute TradeDB persistence: {}: {}", jarPath, e)
        except EOFError as e:
            self.tdenv.WARN("Persistence data appears truncated or corrupt, discarding it: {}: {}", jarPath, e)
            self.removePersist()
            self.tdenv.WARN("If this problem keeps happening, please report an issue")
        return False
    
    def _readPickleFrom(self, jar: typing.BinaryIO) -> bool:
        """ Inner implementation that performs the reading from the pickle. """
        # We pickle a header and then we pickle data.
        header = pickle.load(jar)
        if (header_fmt := header.get(PERSIST_FORMAT_FIELD)) != PERSIST_FORMAT:
            self.tdenv.DEBUG0("persist format mismatch: cur={}, file={}", PERSIST_FORMAT, header_fmt)
            return False
        
        # Find when the current database was last modified; if the file doesn't exist,
        # the caller will see this as a file-not-found exception voiding the read.
        cur_db_timestamp = self.dbPath.stat().st_mtime
        # Compare with the timestamp of the previous save.
        if (old_db_timestamp := header.get(PERSIST_TIMESTAMP_FIELD)) != cur_db_timestamp:
            self.tdenv.DEBUG0("persist data is stale by timestamp: cur={}, file={}", cur_db_timestamp, old_db_timestamp)
            return False
        cur_db_size = self.dbPath.stat().st_size
        if (old_db_size := header.get(PERSIST_SIZE_FIELD)) != cur_db_size:
            self.tdenv.DEBUG0("persist data is stale by size: cur={}, file={}", cur_db_size, old_db_size)
            return False
        self.tdenv.DEBUG1("persist data not expired by time (cur={}, file={}) or size (cur={}, file={})", cur_db_timestamp, old_db_timestamp, cur_db_size, old_db_size)
        
        data = pickle.load(jar)
        eof_marker = pickle.load(jar)
        if eof_marker != "fin":
            raise EOFError("missing eof marker in persistence data")
        
        # We have to repopulate some fields rather than pickle them
        self.systemByID, self.systemByName = data["system"]
        self.stationByID, self.tradingStationCount = data["station"]
        self.categoryByID = data["category"]
        self.itemByName = data["item"]
        self.itemByID = {i.ID: i for i in data["item"].values()}
        self.itemByFDevID = {i.fdevID: i for i in data["item"].values()}
        
        return True
    
    def writePersist(self) -> bool:
        """ Attempt to restore a snapshotted previous version of our data
            as long as all the stars align. """
        # Remove the file if it's already there.
        jarPath = self.getPersistPath()
        try:
            jarPath.unlink(missing_ok=True)
        except PermissionError as e:
            if not self.tdenv.persist:
                # user indicated they don't want to care about persist.
                return False
            if jarPath.exists():
                raise TradeException("Unable to remove old persistence data, the file is inaccssible or open by another program")
            raise e from e
        
        try:
            stat = self.dbPath.stat()
        except FileNotFoundError:
            # Can't persist what we don't have
            self.tdenv.DEBUG0("unable to persist: the db file is dead, Dave")
            return False
        cur_db_timestamp, cur_db_size = stat.st_mtime, stat.st_size
        
        header = {
            PERSIST_FORMAT_FIELD: PERSIST_FORMAT,
            PERSIST_TIMESTAMP_FIELD: cur_db_timestamp,
            PERSIST_SIZE_FIELD: cur_db_size,
        }
        data = {
            "system":   (self.systemByID, self.systemByName),
            "station":  (self.stationByID, self.tradingStationCount),
            "category": self.categoryByID,
            "item":     self.itemByName,
        }
        
        with jarPath.open("wb") as jar:
            pickle.dump(header, jar)
            pickle.dump(data, jar)
            pickle.dump("fin", jar)  # EOF marker incase user kills process mid-write.
        
        return True
    
    def removePersist(self):
        self.getPersistPath().unlink(missing_ok=True)
    
    
    ############################################################
    # General purpose static methods.
    
    @staticmethod
    def listSearch(
            listType, lookup, values,
            key=lambda item: item,
            val=lambda item: item
            ):
        """
        Searches [values] for 'lookup' for least-ambiguous matches,
        return the matching value as stored in [values].
        
        GIVEN [values] contains "bread", "water", "biscuits and "It",
        searching "ea" will return "bread", "WaT" will return "water"
        and "i" will return "biscuits".
        
        Searching for "a" would raise an AmbiguityError because "a" matches
        "bread" and "water", but searching for "it" will return "It"
        because it provides an exact match of a key.
        """
        
        class ListSearchMatch(namedtuple('Match', ['key', 'value'])):
            pass
        
        normTrans = TradeDB.normalizeTrans
        trimTrans = TradeDB.trimTrans
        needle = lookup.translate(normTrans).translate(trimTrans)
        partialMatch, wordMatch = [], []
        # make a regex to match whole words
        wordRe = re.compile(f"\\b{lookup}\\b", re.IGNORECASE)
        # describe a match
        for entry in values:
            entryKey = key(entry)
            normVal = entryKey.translate(normTrans).translate(trimTrans)
            if normVal.find(needle) > -1:
                # If this is an exact match, ignore ambiguities.
                if len(normVal) == len(needle):
                    return val(entry)
                match = ListSearchMatch(entryKey, val(entry))
                if wordRe.match(entryKey):
                    wordMatch.append(match)
                else:
                    partialMatch.append(match)
        # Whole word matches trump partial matches
        if wordMatch:
            if len(wordMatch) > 1:
                raise AmbiguityError(
                    listType, lookup, wordMatch,
                    key=lambda item: item.key,
                )
            return wordMatch[0].value
        # Fuzzy matches
        if partialMatch:
            if len(partialMatch) > 1:
                raise AmbiguityError(
                    listType, lookup, partialMatch,
                    key=lambda item: item.key,
                )
            return partialMatch[0].value
        # No matches
        raise LookupError(f"Error: '{lookup}' doesn't match any {listType}")
    
    @staticmethod
    def normalizedStr(text: str) -> str:
        """
            Returns a case folded, sanitized version of 'str' suitable for
            performing simple and partial matches against. Removes various
            punctuation characters that don't contribute to name uniqueness.
            NOTE: No-longer removes whitespaces or apostrophes.
        """
        return text.translate(
            TradeDB.normalizeTrans
        ).translate(
            TradeDB.trimTrans
        )

######################################################################
# Assorted helpers

def describeAge(ageInSeconds: float | int) -> str:
    """
    Turns an age (in seconds) into a text representation.
    """
    hours = int(ageInSeconds / 3600)
    if hours < 1:
        return "<1 hr"
    if hours == 1:
        return "1 hr"
    if hours < 48:
        return f"{hours} hrs"
    days = int(hours / 24)
    if days < 90:
        return f"{days} days"
    
    return f"{int(days / 31)} mths"
