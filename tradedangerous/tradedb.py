# --------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
# Copyright (C) Bernd 'Gazelle' Gollesch 2016, 2017
# Copyright (C) Jonathan 'eyeonus' Jones 2018, 2019
#
# You are free to use, redistribute, or even print and eat a copy of
# this software so long as you include this copyright notice.
# I guarantee there is at least one bug neither of us knew about.
# --------------------------------------------------------------------
# TradeDangerous :: Modules :: Database Module

"""
Provides the primary classes used within TradeDangerous:

TradeDB, System, Station, Ship, Item, RareItem and Trade.

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
from contextlib import closing
from math import sqrt as math_sqrt
from pathlib import Path
import heapq
import itertools
import locale
import re
import sqlite3
import sys
import typing

from .tradeenv import TradeEnv
from .tradeexcept import TradeException
from . import cache, fs

if typing.TYPE_CHECKING:
    from typing import Generator
    from typing import Optional, Union


locale.setlocale(locale.LC_ALL, '')


######################################################################
# Classes

class AmbiguityError(TradeException):
    """
        Raised when a search key could match multiple entities.
        Attributes:
            lookupType - description of what was being queried,
            searchKey  - the key given to the search routine,
            anyMatch - list of anyMatch
            key        - retrieve the display string for a candidate
    """
    def __init__(
            self, lookupType, searchKey, anyMatch, key=lambda item: item
            ):
        self.lookupType = lookupType
        self.searchKey = searchKey
        self.anyMatch = anyMatch
        self.key = key
    
    def __str__(self):
        anyMatch, key = self.anyMatch, self.key
        if len(anyMatch) > 10:
            opportunities = ", ".join([
                key(c) for c in anyMatch[:10]
            ] + ["..."])
        else:
            opportunities = ", ".join(
                key(c) for c in anyMatch[0:-1]
            )
            opportunities += " or " + key(anyMatch[-1])
        return f'{self.lookupType} "{self.searchKey}" could match {opportunities}'

class SystemNotStationError(TradeException):
    """
        Raised when a station lookup matched a System but
        could not be automatically reduced to a Station.
    """
    pass  # pylint: disable=unnecessary-pass  # (it's not)


######################################################################


def make_stellar_grid_key(x: float, y: float, z: float) -> int:
    """
    The Stellar Grid is a map of systems based on their Stellar
    co-ordinates rounded down to 32lys. This makes it much easier
    to find stars within rectangular volumes.
    """
    return (int(x) >> 5, int(y) >> 5, int(z) >> 5)


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
    
    def __init__(self, ID, dbname, posX, posY, posZ, addedID) -> None:
        self.ID = ID
        self.dbname = dbname
        self.posX, self.posY, self.posZ = posX, posY, posZ
        self.addedID = addedID or 0
        self.stations = ()
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

class Destination(namedtuple('Destination', [
        'system', 'station', 'via', 'distLy'
        ])):
    pass

class DestinationNode(namedtuple('DestinationNode', [
        'system', 'via', 'distLy'
        ])):
    pass

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
            self, ID, system, dbname,
            lsFromStar, market, blackMarket, shipyard, maxPadSize,
            outfitting, rearm, refuel, repair, planetary, fleet, odyssey,
            itemCount=0, dataAge=None,
            ):
        self.ID, self.system, self.dbname = ID, system, dbname
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
        system.stations = system.stations + (self,)
    
    def name(self, detail: int = 0) -> str:  # pylint: disable=unused-argument
        return f"{self.system.dbname}/{self.dbname}"
    
    def checkPadSize(self, maxPadSize):
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
    
    def checkPlanetary(self, planetary):
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
    
    def checkFleet(self, fleet):
        """
        Same as checkPlanetary, but for fleet carriers.
        """
        return (not fleet or self.fleet in fleet)


    def checkOdyssey(self, odyssey):
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


class Ship(namedtuple('Ship', (
        'ID', 'dbname', 'cost', 'stations'
        ))):
    """
    Ship description.
    
    Attributes:
        ID          -- FDevID as provided by the companion API.
        dbname      -- The name as present in the database
        cost        -- How many credits to buy
        stations    -- List of Stations ship is sold at.
    """
    
    def name(self, detail=0):   # pylint: disable=unused-argument
        return self.dbname

######################################################################


class Category(namedtuple('Category', (
        'ID', 'dbname', 'items'
        ))):
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
    
    def name(self, detail=0):   # pylint: disable=unused-argument
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
    
    def __init__(self, ID, dbname, category, fullname, avgPrice=None, fdevID=None):
        self.ID = ID
        self.dbname = dbname
        self.category = category
        self.fullname = fullname
        self.avgPrice = avgPrice
        self.fdevID   = fdevID
    
    def name(self, detail=0):
        return self.fullname if detail > 0 else self.dbname

######################################################################


class RareItem(namedtuple('RareItem', (
        'ID', 'station', 'dbname', 'costCr', 'maxAlloc', 'illegal',
        'suppressed', 'category', 'fullname',
        ))):
    """
    Describes a RareItem from the database.
    
    Attributes:
        ID         -- Database ID,
        station    -- Which Station this is bought from,
        dbname     -- The name are presented in the database,
        costCr     -- Buying price.
        maxAlloc   -- How many the player can carry at a time,
        illegal    -- If the item may be considered illegal,
        suppressed -- The item is suppressed.
        category   -- Reference to the category.
        fullname   -- Combined category/dbname.
    """
    
    def name(self, detail=0):
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
    def name(self, detail=0):
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
    defaultDB = 'TradeDangerous.db'
    # File containing SQL to build the DB cache from
    defaultSQL = 'TradeDangerous.sql'
    # File containing text description of prices
    defaultPrices = 'TradeDangerous.prices'
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
            tdenv=None,
            load=True,
            debug=None,
            ):
        self.conn: sqlite3.Connection = None
        self.tradingCount = None
        
        tdenv = tdenv or TradeEnv(debug=(debug or 0))
        self.tdenv = tdenv
        
        self.templatePath = Path(tdenv.templateDir).resolve()
        self.dataPath = dataPath = fs.ensurefolder(tdenv.dataDir)
        self.csvPath = fs.ensurefolder(tdenv.csvDir)
        
        fs.copy_if_newer((self.templatePath / Path("Added.csv")), (self.csvPath / Path("Added.csv")))
        fs.copy_if_newer((self.templatePath / Path("RareItem.csv")), (self.csvPath / Path("RareItem.csv")))
        fs.copy_if_newer((self.templatePath / Path("Category.csv")), (self.csvPath / Path("Category.csv")))
        fs.copy_if_newer((self.templatePath / Path("TradeDangerous.sql")), (self.dataPath / Path("TradeDangerous.sql")))
        
        self.dbPath = Path(tdenv.dbFilename or dataPath / TradeDB.defaultDB)
        self.sqlPath = dataPath / Path(tdenv.sqlFilename or TradeDB.defaultSQL)
        pricePath = Path(tdenv.pricesFilename or TradeDB.defaultPrices)
        self.pricesPath = dataPath / pricePath
        self.importTables = [
            (str(self.csvPath / Path(fn)), tn)
            for fn, tn in TradeDB.defaultTables
        ]
        self.importPaths = {tn: tp for tp, tn in self.importTables}
        
        self.dbFilename = str(self.dbPath)
        self.sqlFilename = str(self.sqlPath)
        self.pricesFilename = str(self.pricesPath)
        
        self.avgSelling, self.avgBuying = None, None
        self.tradingStationCount = 0
        self.addedByID = None
        self.systemByID = None
        self.systemByName = None
        self.stellarGrid = None
        self.stationByID = None
        self.shipByID = None
        self.categoryByID = None
        self.itemByID = None
        self.itemByName = None
        self.itemByFDevID = None
        self.rareItemByID = None
        self.rareItemByName = None
        
        if load:
            self.reloadCache()
            self.load(maxSystemLinkLy=tdenv.maxSystemLinkLy)
    
    @staticmethod
    def calculateDistance2(lx, ly, lz, rx, ry, rz):
        """
        Returns the distance in ly between two points.
        """
        dx, dy, dz = lx - rx, ly - ry, lz - rz
        return (dx * dx) + (dy * dy) + (dz * dz)
    
    @staticmethod
    def calculateDistance(lx, ly, lz, rx, ry, rz):
        """
        Returns the distance in ly between two points.
        """
        dx, dy, dz = lx - rx, ly - ry, lz - rz
        return math_sqrt((dx * dx) + (dy * dy) + (dz * dz))
    
    ############################################################
    # Access to the underlying database.
    
    def getDB(self) -> sqlite3.Connection:
        if self.conn:
            return self.conn
        self.tdenv.DEBUG1("Connecting to DB")
        conn = sqlite3.connect(self.dbFilename)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
        
        conn.create_function('dist2', 6, TradeDB.calculateDistance2)
        self.conn = conn
        return conn
    
    def query(self, *args):
        """ Perform an SQL query on the DB and return the cursor. """
        return self.getDB().execute(*args)
    
    def queryColumn(self, *args):
        """ perform an SQL query and return a single column. """
        return self.query(args).fetchone()[0]
    
    def reloadCache(self):
        """
        Checks if the .sql, .prices or *.csv files are newer than the cache.
        """
        
        if self.dbPath.exists():
            dbFileStamp = self.dbPath.stat().st_mtime
            
            paths = [self.sqlPath]
            paths += [Path(f) for (f, _) in self.importTables]
            
            changedPaths = [
                [path, path.stat().st_mtime]
                for path in paths
                if path.exists() and path.stat().st_mtime > dbFileStamp
            ]
            
            if not changedPaths:
                # Do we need to reload the .prices file?
                if not self.pricesPath.exists():
                    self.tdenv.DEBUG1("No .prices file to load")
                    return
                
                pricesStamp = self.pricesPath.stat().st_mtime
                if pricesStamp <= dbFileStamp:
                    self.tdenv.DEBUG1("DB Cache is up to date.")
                    return
                
                self.tdenv.DEBUG0(".prices has changed: re-importing")
                cache.importDataFromFile(
                    self, self.tdenv, self.pricesPath, reset=True
                )
                return
            
            self.tdenv.DEBUG0("Rebuilding DB Cache [{}]", str(changedPaths))
        else:
            self.tdenv.DEBUG0("Building DB Cache")
        
        cache.buildCache(self, self.tdenv)
    
    ############################################################
    # Load "added" data.
    
    def _loadAdded(self):
        """
        Loads the Added table as a simple dictionary
        """
        stmt = """
            SELECT added_id, name
              FROM Added
        """
        addedByID = {}
        with closing(self.query(stmt)) as cur:
            for ID, name in cur:
                addedByID[ID] = name
        self.addedByID = addedByID
        self.tdenv.DEBUG1("Loaded {:n} Addeds", len(addedByID))
    
    def lookupAdded(self, name):
        name = name.lower()
        for ID, added in self.addedByID.items():
            if added.lower() == name:
                return ID
        raise KeyError(name)
    
    ############################################################
    # Star system data.
    
    def systems(self):
        """ Iterate through the list of systems. """
        yield from self.systemByID.values()
    
    def _loadSystems(self):
        """
        Initial load the (raw) list of systems.
        CAUTION: Will orphan previously loaded objects.
        """
        stmt = """
                SELECT system_id,
                       name, pos_x, pos_y, pos_z,
                       added_id
                  FROM System
            """
        
        systemByID, systemByName = {}, {}
        with closing(self.getDB().execute(stmt)) as cur:
            for (ID, name, posX, posY, posZ, addedID) in cur:
                system = System(ID, name, posX, posY, posZ, addedID)
                systemByID[ID] = systemByName[name.upper()] = system
        
        self.systemByID, self.systemByName = systemByID, systemByName
        self.tdenv.DEBUG1("Loaded {:n} Systems", len(systemByID))
    
    def lookupSystem(self, key):
        """
        Look up a System object by it's name.
        """
        if isinstance(key, System):
            return key
        if isinstance(key, Station):
            return key.system
        
        return TradeDB.listSearch(
            "System", key, self.systems(), key=lambda system: system.dbname
        )
    
    def addLocalSystem(
            self,
            name,
            x, y, z,
            added="Local",
            modified='now',
            commit=True,
            ):
        """
        Add a system to the local cache and memory copy.
        """
        
        db = self.getDB()
        cur = db.cursor()
        cur.execute("""
                INSERT INTO System (
                    name, pos_x, pos_y, pos_z, added_id, modified
                ) VALUES (
                    ?, ?, ?, ?,
                    (SELECT added_id FROM Added WHERE name = ?),
                    DATETIME(?)
                )
        """, [
            name, x, y, z, added, modified,
        ])
        ID = cur.lastrowid
        system = System(ID, name.upper(), x, y, z, 0)
        self.systemByID[ID] = system
        self.systemByName[system.dbname] = system
        if commit:
            db.commit()
        self.tdenv.NOTE(
            "Added new system #{}: {} [{},{},{}]",
            ID, name, x, y, z
        )
        # Invalidate the grid
        self.stellarGrid = None
        return system
    
    def updateLocalSystem(
            self, system,
            name, x, y, z, added="Local", modified='now',
            force=False,
            commit=True,
            ):
        """
        Updates an entry for a local system.
        """
        oldname = system.dbname
        dbname = name.upper()
        if not force:
            if oldname == dbname and \
                    system.posX == x and \
                    system.posY == y and \
                    system.posZ == z:
                return False
        del self.systemByName[oldname]
        db = self.getDB()
        db.execute("""
            UPDATE System
               SET name=?,
                   pos_x=?, pos_y=?, pos_z=?,
                   added_id=(SELECT added_id FROM Added WHERE name = ?),
                   modified=DATETIME(?)
             WHERE system_id = ?
        """, [
            dbname, x, y, z, added, modified,
            system.ID,
        ])
        if commit:
            db.commit()
        self.tdenv.NOTE(
            "{} (#{}) updated in {}: {}, {}, {}, {}, {}, {}",
            oldname, system.ID,
            self.dbPath if self.tdenv.detail > 1 else "local db",
            dbname,
            x, y, z,
            added, modified,
        )
        self.systemByName[dbname] = system
        
        return True
    
    def removeLocalSystem(
            self, system,
            commit=True,
        ):
        """ Removes a system and it's stations from the local DB. """
        for stn in self.stations():
            self.removeLocalStation(stn, commit=False)
        db = self.getDB()
        db.execute("""
            DELETE FROM System WHERE system_id = ?
        """, [
            system.ID
        ])
        if commit:
            db.commit()
        del self.systemByName[system.dbname]
        del self.systemByID[system.ID]
        
        self.tdenv.NOTE(
            "{} (#{}) deleted from {}",
            system.name(), system.ID,
            self.dbPath if self.tdenv.detail > 1 else "local db",
        )
        
        system.dbname = "DELETED " + system.dbname
        del system
    
    def __buildStellarGrid(self):
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
    
    def genStellarGrid(self, system, ly):
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
    
    def genSystemsInRange(self, system, ly, includeSelf=False):
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
        Populate the Station list.
        Station constructor automatically adds itself to the System object.
        CAUTION: Will orphan previously loaded objects.
        """
        stmt = """
            SELECT  station_id, system_id, name,
                    ls_from_star, market, blackmarket, shipyard,
                    max_pad_size, outfitting, rearm, refuel, repair, planetary, type_id
              FROM  Station
        """
        
        stationByID = {}
        systemByID = self.systemByID
        self.tradingStationCount = 0
        # Fleet Carriers are station type 24.
        # Odyssey settlements are station type 25.
        # Assume type 0 (Unknown) are also Fleet Carriers.
        # Storing as a list allows easy expansion if needed.
        types = {'fleet-carrier':[24, 0,],'odyssey':[25,],}
        with closing(self.query(stmt)) as cur:
            for (
                ID, systemID, name,
                lsFromStar, market, blackMarket, shipyard,
                maxPadSize, outfitting, rearm, refuel, repair, planetary, type_id
            ) in cur:
                isFleet = 'Y' if int(type_id) in types['fleet-carrier'] else 'N'
                isOdyssey = 'Y' if int(type_id) in types['odyssey'] else 'N'
                station = Station(
                    ID, systemByID[systemID], name,
                    lsFromStar, market, blackMarket, shipyard,
                    maxPadSize, outfitting, rearm, refuel, repair, planetary, isFleet, isOdyssey,
                    0, None,
                )
                stationByID[ID] = station
        
        tradingCount = 0
        stmt = """
            SELECT  station_id,
                    COUNT(*) AS item_count,
                    AVG(JULIANDAY('now') - JULIANDAY(modified))
              FROM  StationItem
             GROUP  BY 1
             HAVING item_count > 0
        """
        with closing(self.query(stmt)) as cur:
            for ID, itemCount, dataAge in cur:
                station = stationByID[ID]
                station.itemCount = itemCount
                station.dataAge = dataAge
                tradingCount += 1
        
        self.stationByID = stationByID
        self.tradingStationCount = tradingCount
        self.tdenv.DEBUG1("Loaded {:n} Stations", len(stationByID))
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
        Add a station to the local cache and memory copy.
        """
        
        market = market.upper()
        blackMarket = blackMarket.upper()
        shipyard = shipyard.upper()
        maxPadSize = maxPadSize.upper()
        outfitting = outfitting.upper()
        rearm = rearm.upper()
        refuel = refuel.upper()
        repair = repair.upper()
        planetary = planetary.upper()
        assert market in "?YN"
        assert blackMarket in "?YN"
        assert shipyard in "?YN"
        assert maxPadSize in "?SML"
        assert outfitting in "?YN"
        assert rearm in "?YN"
        assert refuel in "?YN"
        assert repair in "?YN"
        assert planetary in '?YN'
        assert fleet in '?YN'
        assert odyssey in '?YN'
        
        type_id = 0
        if fleet == 'Y':
            type_id = 24
        if odyssey == 'Y':
            type_id = 25
        
        db = self.getDB()
        cur = db.cursor()
        cur.execute("""
            INSERT INTO Station (
                name, system_id,
                ls_from_star, market, blackmarket, shipyard, max_pad_size,
                outfitting, rearm, refuel, repair, planetary, type_id,
                modified
            ) VALUES (
                ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                DATETIME(?)
            )
        """, [
            name, system.ID,
            lsFromStar, market, blackMarket, shipyard, maxPadSize,
            outfitting, rearm, refuel, repair, planetary, type_id,
            modified,
        ])
        ID = cur.lastrowid
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
            fleet='?',
            odyssey='?',
            itemCount=0, dataAge=0,
        )
        self.stationByID[ID] = station
        if commit:
            db.commit()
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
        Alter the properties of a station in-memory and in the DB.
        """
        changes = []
        
        def _changed(label, old, new):
            changes.append(
                f"{label}('{old}'=>'{new}')"
            )
        
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
        
        def _check_setting(label, name, newValue, allowed):
            if newValue is not None:
                newValue = newValue.upper()
                assert newValue in allowed
                oldValue = getattr(station, name, '?')
                if newValue != oldValue and (force or newValue != '?'):
                    _changed(label, oldValue, newValue)
                    setattr(station, name, newValue)
        
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
        
        db = self.getDB()
        db.execute("""
            UPDATE Station
               SET name=?,
                   ls_from_star=?,
                   market=?,
                   blackmarket=?,
                   shipyard=?,
                   max_pad_size=?,
                   outfitting=?,
                   rearm=?,
                   refuel=?,
                   repair=?,
                   planetary=?,
                   modified=DATETIME(?)
             WHERE station_id = ?
        """, [
            station.dbname,
            station.lsFromStar,
            station.market,
            station.blackMarket,
            station.shipyard,
            station.maxPadSize,
            station.outfitting,
            station.rearm,
            station.refuel,
            station.repair,
            station.planetary,
            modified,
            station.ID
        ])
        if commit:
            db.commit()
        
        self.tdenv.NOTE(
            "{} (#{}) updated in {}: {}",
            station.name(), station.ID,
            self.dbPath if self.tdenv.detail > 1 else "local db",
            ", ".join(changes)
        )
        
        return True
    
    def removeLocalStation(self, station, commit=True):
        """
        Removes a station from the local database and memory image.
        
        Becareful of any references to the station you may still have
        after this.
        """
        
        # Remove reference from my system
        system = station.system
        system.stations.remove(station)
        
        # Remove the ID lookup
        del self.stationByID[station.ID]
        
        # Delete database entry
        db = self.getDB()
        db.execute("""
            DELETE FROM Station
             WHERE system_id = ? AND station_id = ?
        """, [system.ID, station.ID]
        )
        if commit:
            db.commit()
        
        self.tdenv.NOTE(
            "{} (#{}) deleted from {}",
            station.name(), station.ID,
            self.dbPath if self.tdenv.detail > 1 else "local db",
        )
        
        station.dbname = "DELETED "+station.dbname
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
        
        if isinstance(name, (System, Station)):
            return name
        
        slashPos = name.find('/')
        if slashPos < 0:
            slashPos = name.find('\\')
        nameOff = 1 if name.startswith('@') else 0
        if slashPos > nameOff:
            # Slash indicates it's, e.g., AULIN/ENTERPRISE
            sysName = name[nameOff:slashPos].upper()
            stnName = name[slashPos+1:]
        elif slashPos == nameOff:
            sysName, stnName = None, name[nameOff+1:]
        elif nameOff:
            # It's explicitly a station
            sysName, stnName = name[nameOff:].upper(), None
        else:
            # It could be either, use the name for both.
            stnName = name[nameOff:]
            sysName = stnName.upper()
        
        exactMatch = []
        closeMatch = []
        wordMatch = []
        anyMatch = []
        
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
                if placeNameTrimmed.find(nameTrimmed) >= 0:
                    anyMatch.append(place)
        
        if sysName:
            try:
                system = self.systemByName[sysName]
                exactMatch = [system]
            except KeyError:
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
    
    def ships(self):
        """ Iterate through the list of ships. """
        yield from self.shipByID.values()
    
    def _loadShips(self):
        """
        Populate the Ship list.
        CAUTION: Will orphan previously loaded objects.
        """
        stmt = """
            SELECT ship_id, name, cost
              FROM Ship
        """
        self.shipByID = {
            row[0]: Ship(*row, stations=[])
            for row in self.query(stmt)
        }
        
        self.tdenv.DEBUG1("Loaded {} Ships", len(self.shipByID))
    
    def lookupShip(self, name):
        """
        Look up a ship by name
        """
        return TradeDB.listSearch(
            "Ship", name, self.shipByID.values(),
            key=lambda ship: ship.dbname
        )
    
    ############################################################
    # Item data.
    
    def categories(self):
        """
        Iterate through the list of categories.
        key = category name, value = list of items.
        """
        yield from self.categoryByID.items()
    
    def _loadCategories(self):
        """
        Populate the list of item categories.
        CAUTION: Will orphan previously loaded objects.
        """
        stmt = """
            SELECT category_id, name
              FROM Category
        """
        with closing(self.query(stmt)) as cur:
            self.categoryByID = {
                ID: Category(ID, name, [])
                for (ID, name) in cur
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
    
    def items(self):
        """ Iterate through the list of items. """
        yield from self.itemByID.values()
    
    def _loadItems(self):
        """
        Populate the Item list.
        CAUTION: Will orphan previously loaded objects.
        """
        stmt = """
            SELECT item_id, name, category_id, avg_price, fdev_id
              FROM Item
        """
        itemByID, itemByName, itemByFDevID = {}, {}, {}
        with closing(self.query(stmt)) as cur:
            for ID, name, categoryID, avgPrice, fdevID in cur:
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
        
        self.tdenv.DEBUG1(
            "Loaded {:n} Items",
            len(self.itemByID)
        )
    
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
        Query the database for average selling prices of all items.
        """
        if not self.avgSelling:
            self.avgSelling = {itemID: 0 for itemID in self.itemByID}
            self.avgSelling.update({
                ID: int(cr)
                for ID, cr in self.getDB().execute("""
                    SELECT  i.item_id, IFNULL(AVG(supply_price), 0)
                      FROM  Item AS i
                            LEFT OUTER JOIN StationItem AS si ON (
                                i.item_id = si.item_id AND si.supply_price > 0
                            )
                     WHERE  supply_price > 0
                     GROUP  BY 1
                """)
            })
        return self.avgSelling
    
    def getAverageBuying(self):
        """
        Query the database for average buying prices of all items.
        """
        if not self.avgBuying:
            self.avgBuying = {itemID: 0 for itemID in self.itemByID}
            self.avgBuying.update({
                ID: int(cr)
                for ID, cr in self.getDB().execute("""
                    SELECT  i.item_id, IFNULL(AVG(demand_price), 0)
                      FROM  Item AS i
                            LEFT OUTER JOIN StationItem AS si ON (
                                i.item_id = si.item_id AND si.demand_price > 0
                            )
                     WHERE  demand_price > 0
                     GROUP  BY 1
                """)
            })
        return self.avgBuying
    
    ############################################################
    # Rare Items
    
    def _loadRareItems(self):
        """
        Populate the RareItem list.
        """
        stmt = """
            SELECT  rare_id, station_id, category_id, name,
                    cost, max_allocation, illegal, suppressed
              FROM  RareItem
        """


        rareItemByID, rareItemByName = {}, {}
        stationByID = self.stationByID
        with closing(self.query(stmt)) as cur:
            for (
                ID, stnID, catID, name,
                cost, maxAlloc, illegal, suppressed
            ) in cur:
                station = stationByID[stnID]
                category = self.categoryByID[catID]
                rare = RareItem(
                    ID, station, name, cost, maxAlloc, illegal, suppressed,
                    category, f"{category.dbname}/{name}"
                )
                rareItemByID[ID] = rareItemByName[name] = rare
        self.rareItemByID = rareItemByID
        self.rareItemByName = rareItemByName
        
        self.tdenv.DEBUG1(
            "Loaded {:n} RareItems",
            len(rareItemByID)
        )
    
    ############################################################
    # Price data.
    
    def close(self):
        if self.conn:
            self.conn.close()
        self.conn = None
    
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


        
        self._loadAdded()
        self._loadSystems()
        self._loadStations()
        self._loadShips()
        self._loadCategories()
        self._loadItems()
        self._loadRareItems()
        
        # Calculate the maximum distance anyone can jump so we can constrain
        # the maximum "link" between any two stars.
        msll = maxSystemLinkLy or self.tdenv.maxSystemLinkLy or 30
        self.maxSystemLinkLy = msll
    
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

def describeAge(ageInSeconds: Union[float, int]) -> str:
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
