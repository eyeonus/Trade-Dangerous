# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
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


from collections import namedtuple, defaultdict
from pathlib import Path
from tradeenv import TradeEnv
from tradeexcept import TradeException

import cache
import heapq
import itertools
import locale
import math
import re
import sqlite3
import sys

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
            opportunities = ", ".join([
                key(c) for c in anyMatch[0:-1]
            ])
            opportunities += " or " + key(anyMatch[-1])
        return '{} "{}" could match {}'.format(
            self.lookupType, str(self.searchKey),
            opportunities
        )


class SystemNotStationError(TradeException):
    """
        Raised when a station lookup matched a System but
        could not be automatically reduced to a Station.
    """
    pass


######################################################################


def makeStellarGridKey(x, y, z):
    """
    The Stellar Grid is a map of systems based on their Stellar
    co-ordinates rounded down to 32lys. This makes it much easier
    to find stars within rectangular volumes.
    """
    return (int(x) >> 5, int(y) >> 5, int(z) >> 5)


class System(object):
    """
    Describes a star system which may contain one or more Station objects.

    Caution: Do not use _rangeCache directly, use TradeDB.genSystemsInRange.
    """

    __slots__ = (
        'ID',
        'dbname', 'posX', 'posY', 'posZ', 'stations',
        'addedID',
        '_rangeCache'
    )

    class RangeCache(object):
        """
        Lazily populated cache of neighboring systems.
        """
        def __init__(self):
            self.systems = []
            self.probedLy = 0.

    def __init__(self, ID, dbname, posX, posY, posZ, addedID):
        self.ID = ID
        self.dbname = dbname
        self.posX, self.posY, self.posZ = posX, posY, posZ
        self.addedID = addedID or 0
        self.stations = []
        self._rangeCache = None

    @property
    def system(self):
        return self

    def distToSq(self, other):
        """
        Returns the square of the distance between two systems.

        It is slightly cheaper to calculate the square of the
        distance between two points, so when you are primarily
        doing distance checks you can use this less expensive
        distance query and only perform a sqrt (** 0.5) on the
        distances that fall within your constraint.

        Args:
            other:
                The other System to measure the distance between.

        Returns:
            Distance in light years to the power of 2 (i.e. squared).

        Example:
            # Calculate which of [systems] is within 12 ly
            # of System "target".
            maxLySq = 12 ** 2   # Maximum of 12 ly.
            inRange = []
            for sys in systems:
                if sys.distToSq(target) <= maxLySq:
                    inRange.append(sys)
        """

        dx2 = (self.posX - other.posX) ** 2
        dy2 = (self.posY - other.posY) ** 2
        dz2 = (self.posZ - other.posZ) ** 2

        return (dx2 + dy2 + dz2)

    def distanceTo(self, other):
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

        dx2 = (self.posX - other.posX) ** 2
        dy2 = (self.posY - other.posY) ** 2
        dz2 = (self.posZ - other.posZ) ** 2

        distSq = (dx2 + dy2 + dz2)

        return distSq ** 0.5

    def getStation(self, stationName):
        """
        Quick case-insensitive lookup of a station name within the
        stations in this system.

        Returns:
            Station() object if a match is found,
            otherwise None.
        """
        upperName = stationName.upper()
        for station in self.stations:
            if station.dbname.upper() == upperName:
                return station
        return None

    def name(self):
        return self.dbname

    def str(self):
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


class Station(object):
    """
    Describes a station (trading or otherwise) in a system.

    For obtaining trade information for a given station see one of:
        TradeDB.loadStationTrades  (very slow and expensive)
        TradeDB.loadDirectTrades   (can be expensive)
        TradeCalc.getTrades        (fast and cheap)
    """
    __slots__ = (
        'ID', 'system', 'dbname',
        'lsFromStar', 'market', 'blackMarket', 'shipyard', 'maxPadSize',
        'tradingWith', 'itemCount',
        'dataAge',
    )

    def __init__(
            self, ID, system, dbname,
            lsFromStar, market, blackMarket, shipyard, maxPadSize,
            itemCount, dataAge,
            ):
        self.ID, self.system, self.dbname = ID, system, dbname
        self.lsFromStar = int(lsFromStar)
        self.market = market
        self.blackMarket = blackMarket
        self.shipyard = shipyard
        self.maxPadSize = maxPadSize
        self.itemCount = itemCount
        # dict[tradingPartnerStation] -> [ available trades ]
        self.tradingWith = None
        self.dataAge = dataAge
        system.stations.append(self)

    def name(self):
        return '%s/%s' % (self.system.name(), self.dbname)

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

    def distFromStar(self, addSuffix=False):
        """
        Returns a textual description of the distance from this
        Station to the parent star.

        Args:
            addSuffix[=False]:
                Always add a unit suffix (ls, Kls, ly)
        """
        ls = self.lsFromStar
        if not ls:
            if addSuffix:
                return "Unk"
            else:
                return '?'
        if ls < 1000:
            suffix = 'ls' if addSuffix else ''
            return '{:n}'.format(ls)+suffix
        if ls < 10000:
            suffix = 'ls' if addSuffix else ''
            return '{:.2f}K'.format(ls / 1000)+suffix
        if ls < 100000:
            suffix = 'ls' if addSuffix else ''
            return '{:n}K'.format(int(ls / 1000))+suffix
        return '{:.2f}ly'.format(ls / (365*24*60*60))

    def str(self):
        return self.dbname


######################################################################


class Ship(namedtuple('Ship', [
        'ID', 'dbname', 'cost', 'stations'
        ])):
    """
    Ship description.

    Attributes:
        ID          -- The database ID
        dbname      -- The name as present in the database
        cost        -- How many credits to buy
        stations    -- List of Stations ship is sold at.
    """

    def name(self):
        return self.dbname


######################################################################


class Category(namedtuple('Category', [
        'ID', 'dbname', 'items'
        ])):
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

    def name(self):
        return self.dbname.upper()


######################################################################


class Item(object):
    """
    A product that can be bought/sold in the game.

    Attributes:
        ID       -- Database ID.
        dbname   -- Name as it appears in-game and in the DB.
        category -- Reference to the category.
        fullname -- Combined category/dbname for lookups.
        altname  -- The internal name used by the game.
    """
    __slots__ = ('ID', 'dbname', 'category', 'fullname', 'altname')

    def __init__(self, ID, dbname, category, fullname, altname=None):
        self.ID = ID
        self.dbname = dbname
        self.category = category
        self.fullname = fullname
        self.altname = altname

    def name(self):
        return self.dbname


######################################################################


class RareItem(namedtuple('RareItem', [
        'ID', 'station', 'dbname', 'costCr', 'maxAlloc',
        ])):
    """
    Describes a RareItem from the database.

    Attributes:
        ID       -- Database ID,
        station  -- Which Station this is bought from,
        dbname   -- The name are presented in the database,
        costCr   -- Buying price
        maxAlloc -- How many the player can carry at a time,
    """

    def name(self):
        return self.dbname


######################################################################


class Trade(namedtuple('Trade', [
        'item', 'itemID',
        'costCr', 'gainCr',
        'stock', 'stockLevel',
        'demand', 'demandLevel',
        'srcAge', 'dstAge'
        ])):
    """
    Describes what it would cost and how much you would gain
    when selling an item between two specific stations.
    """
    def name(self):
        return self.item.name()


######################################################################


class TradeDB(object):
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

        titleFixup(text)
            Case formats a proper noun.
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
    defaultTables = [
        ['Added.csv', 'Added'],
        ['System.csv', 'System'],
        ['Station.csv', 'Station'],
        ['Ship.csv', 'Ship'],
        ['ShipVendor.csv', 'ShipVendor'],
        ['Upgrade.csv', 'Upgrade'],
        ['UpgradeVendor.csv', 'UpgradeVendor'],
        ['Category.csv', 'Category'],
        ['Item.csv', 'Item'],
        ['AltItemNames.csv', 'AltItemNames'],
        ['RareItem.csv', 'RareItem'],
    ]

    # Translation matrixes for attributes -> common presentation
    marketStates = {'?': '?', 'Y': 'Yes', 'N': 'No'}
    marketStatesExt = {'?': 'Unk', 'Y': 'Yes', 'N': 'No'}
    padSizes = {'?': '?', 'S': 'Sml', 'M': 'Med', 'L': 'Lrg'}
    padSizesExt = {'?': 'Unk', 'S': 'Sml', 'M': 'Med', 'L': 'Lrg'}

    def __init__(
            self,
            tdenv=None,
            load=True,
            debug=None,
            ):
        self.conn = None
        self.cur = None
        self.tradingCount = None

        tdenv = tdenv or TradeEnv(debug=(debug or 0))
        self.tdenv = tdenv

        self.dataPath = dataPath = Path(tdenv.dataDir).resolve()

        self.dbPath = Path(tdenv.dbFilename or dataPath / TradeDB.defaultDB)
        self.sqlPath = dataPath / Path(tdenv.sqlFilename or TradeDB.defaultSQL)
        pricePath = Path(tdenv.pricesFilename or TradeDB.defaultPrices)
        self.pricesPath = dataPath / pricePath
        self.importTables = [
            (str(dataPath / Path(fn)), tn)
            for fn, tn in TradeDB.defaultTables
        ]
        self.importPaths = {tn: tp for tp, tn in self.importTables}

        self.dbFilename = str(self.dbPath)
        self.sqlFilename = str(self.sqlPath)
        self.pricesFilename = str(self.pricesPath)

        self.avgSelling, self.avgBuying = None, None
        self.tradingStationCount = 0

        if load:
            self.reloadCache()
            self.load(maxSystemLinkLy=tdenv.maxSystemLinkLy)

    @staticmethod
    def calculateDistance2(lx, ly, lz, rx, ry, rz):
        """
        Returns the distance in ly between two points.
        """
        dX = (lx - rx)
        dY = (ly - ry)
        dZ = (lz - rz)
        distSq = (dX ** 2) + (dY ** 2) + (dZ ** 2)
        return distSq

    @staticmethod
    def calculateDistance(lx, ly, lz, rx, ry, rz):
        """
        Returns the distance in ly between two points.
        """
        dX = (lx - rx)
        dY = (ly - ry)
        dZ = (lz - rz)
        distSq = (dX ** 2) + (dY ** 2) + (dZ ** 2)
        return distSq ** 0.5

    ############################################################
    # Access to the underlying database.

    def getDB(self):
        if self.conn:
            return self.conn
        self.tdenv.DEBUG1("Connecting to DB")
        conn = sqlite3.connect(self.dbFilename)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.create_function('dist2', 6, TradeDB.calculateDistance2)
        return conn

    def query(self, *args):
        """ Perform an SQL query on the DB and return the cursor. """
        conn = self.getDB()
        cur = conn.cursor()
        cur.execute(*args)
        return cur

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
        self.cur.execute(stmt)
        addedByID = {}
        for ID, name in self.cur:
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
        self.cur.execute(stmt)
        systemByID, systemByName = {}, {}
        for (ID, name, posX, posY, posZ, addedID) in self.cur:
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

    def addLocalSystem(self, name, x, y, z, added="Local", modified='now'):
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
        db.commit()
        self.tdenv.NOTE(
            "Added new system #{}: {} [{},{},{}]",
            ID, name, x, y, z
        )
        return system

    def updateLocalSystem(
            self, system,
            name, x, y, z, added="Local", modified='now',
            force=False,
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
                   x=?, y=?, z=?,
                   added=(SELECT added_id FROM Added WHERE name = ?),
                   modified=DATETIME(?)
        """, [
            dbname, x, y, z, added, modified
        ])
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

    def __buildStellarGrid(self):
        """
        Divides the galaxy into a fixed-sized grid allowing us to
        aggregate small numbers of stars by locality.
        """
        stellarGrid = self.stellarGrid = dict()
        for system in self.systemByID.values():
            key = makeStellarGridKey(system.posX, system.posY, system.posZ)
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
        lwrBound = makeStellarGridKey(sysX - ly, sysY - ly, sysZ - ly)
        uprBound = makeStellarGridKey(sysX + ly, sysY + ly, sysZ + ly)
        lySq = ly ** 2
        stellarGrid = self.stellarGrid
        for x in range(lwrBound[0], uprBound[0]+1):
            for y in range(lwrBound[1], uprBound[1]+1):
                for z in range(lwrBound[2], uprBound[2]+1):
                    try:
                        grid = stellarGrid[(x, y, z)]
                    except KeyError:
                        continue
                    for candidate in grid:
                        distSq = (candidate.posX - sysX) ** 2
                        if distSq > lySq:
                            continue
                        distSq += (candidate.posY - sysY) ** 2
                        if distSq > lySq:
                            continue
                        distSq += (candidate.posZ - sysZ) ** 2
                        if distSq <= lySq:
                            yield candidate, distSq

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

        if isinstance(system, Station):
            system = system.system
        elif not isinstance(system, System):
            place = self.lookupPlace(system)
            system = place.system if isinstance(system, Station) else place

        cache = system._rangeCache
        if not cache:
            cache = system._rangeCache = System.RangeCache()
        cachedSystems = cache.systems

        probedLy = cache.probedLy
        if ly > probedLy:
            # Consult the database for stars we haven't seen.
            cachedSystems = cache.systems = []
            for cand, distSq in self.genStellarGrid(system, ly):
                if cand is not system:
                    cachedSystems.append((
                        cand,
                        distSq ** 0.5,
                    ))

            cachedSystems.sort(key=lambda ent: ent[1])
            cache.probedLy = probedLy = ly

        if includeSelf:
            yield system, 0.

        if probedLy > ly:
            # Cache may contain values outside our view
            for sys, dist in cachedSystems:
                if dist <= ly:
                    yield sys, dist
        else:
            # No need to be conditional inside the loop
            yield from cachedSystems

    def getRoute(self, origin, dest, maxJumpLy, avoiding=[], stationInterval=0):
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

        if isinstance(origin, Station):
            origin = origin.system
        if isinstance(dest, Station):
            dest = dest.system

        if origin == dest:
            return [(origin, 0), (dest, 0)]

        # openSet is the list of nodes we want to visit, which will be
        # used as a priority queue (heapq).
        # Each element is a tuple of the 'priority' (the combination of
        # the total distance to the node and the distance left from the
        # node to the destination.
        openSet = [(0, 0, origin.ID, 0)]
        # Track predecessor nodes for everwhere we visit
        distances = {origin: (None, 0)}
        destID = dest.ID
        sysByID = self.systemByID
        distTo = float("inf")

        if avoiding:
            if dest in avoiding:
                raise ValueError("Destination is in avoidance list")
            for avoid in avoiding:
                if isinstance(avoid, System):
                    distances[avoid] = (None, -1)

        systemsInRange = self.genSystemsInRange

        while openSet:
            weight, curDist, curSysID, stnDist = heapq.heappop(openSet)
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

            if stationInterval:
                if curSys.stations:
                    stnDist = 0
                else:
                    stnDist += 1

            distFn = curSys.distanceTo
            heappush = heapq.heappush

            for (nSys, nDist) in systemsInRange(curSys, maxJumpLy):
                newDist = curDist + nDist
                try:
                    (prevSys, prevDist) = distances[nSys]
                    if prevDist <= newDist:
                        continue
                except KeyError:
                    pass
                if stationInterval and stnDist >= stationInterval and not curSys.stations:
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
            (prevSys, dist) = distances[dest]
            path.append((dest, dist))
            if dest == origin:
                break
            dest = prevSys

        path.reverse()

        return path

    ############################################################
    # Station data.

    def stations(self):
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
                    ls_from_star,
                    market,
                    blackmarket,
                    shipyard,
                    max_pad_size,
                    COUNT(StationItem.station_id) AS itemCount,
                    JULIANDAY('now') - JULIANDAY(MAX(StationItem.modified))
              FROM  Station
                    LEFT OUTER JOIN StationItem USING (station_id)
             GROUP  BY 1
        """
        self.cur.execute(stmt)
        stationByID = {}
        systemByID = self.systemByID
        self.tradingStationCount = 0
        for (
            ID, systemID, name,
            lsFromStar, market, blackMarket, shipyard, maxPadSize,
            itemCount, dataAge
        ) in self.cur:
            station = Station(
                ID, systemByID[systemID], name,
                lsFromStar, market, blackMarket, shipyard, maxPadSize,
                itemCount, dataAge
            )
            if itemCount > 0:
                self.tradingStationCount += 1
            stationByID[ID] = station

        self.stationByID = stationByID
        self.tdenv.DEBUG1("Loaded {:n} Stations", len(stationByID))
        self.stellarGrid = None

    def addLocalStation(
            self,
            system,
            name,
            lsFromStar=0,
            market='?',
            blackMarket='?',
            shipyard='?',
            maxPadSize='?',
            modified='now',
            ):
        """
        Add a station to the local cache and memory copy.
        """

        market = market.upper()
        blackMarket = blackMarket.upper()
        shipyard = shipyard.upper()
        maxPadSize = maxPadSize.upper()
        assert market in "?YN"
        assert blackMarket in "?YN"
        assert shipyard in "?YN"
        assert maxPadSize in "?SML"

        self.tdenv.DEBUG0(
            "Adding {}/{} ls={}, mkt={}, bm={}, yard={}, pad={}, mod={}",
            system.name(),
            name,
            lsFromStar,
            market,
            blackMarket,
            shipyard,
            maxPadSize,
            modified,
        )

        db = self.getDB()
        cur = db.cursor()
        cur.execute("""
            INSERT INTO Station (
                name, system_id,
                ls_from_star, market, blackmarket, shipyard, max_pad_size,
                modified
            ) VALUES (
                ?, ?,
                ?, ?, ?, ?, ?,
                DATETIME(?)
            )
        """, [
            name, system.ID,
            lsFromStar, market, blackMarket, shipyard, maxPadSize,
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
            itemCount=0, dataAge=0,
        )
        self.stationByID[ID] = station
        db.commit()
        self.tdenv.NOTE(
            "{} (#{}) added to {}: "
            "ls={}, mkt={}, bm={}, yard={}, pad={}, mod={}",
            station.name(), station.ID,
            self.dbPath if self.tdenv.detail > 1 else "local db",
            lsFromStar, market, blackMarket, shipyard, maxPadSize,
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
            modified='now',
            force=False,
            ):
        """
        Alter the properties of a station in-memory and in the DB.
        """
        changes = []

        def _changed(label, old, new):
            changes.append(
                "{}('{}'=>'{}')".format(label, old, new)
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

        if market is not None:
            market = market.upper()
            assert market in TradeDB.marketStates
            if market != station.market:
                if market != '?' or force:
                    _changed("mkt", station.market, market)
                    station.market = market

        if blackMarket is not None:
            blackMarket = blackMarket.upper()
            assert blackMarket in TradeDB.marketStates
            if blackMarket != station.blackMarket:
                if blackMarket != '?' or force:
                    _changed("blkmkt", station.blackMarket, blackMarket)
                    station.blackMarket = blackMarket

        if shipyard is not None:
            shipyard = shipyard.upper()
            assert shipyard in TradeDB.marketStates
            if shipyard != station.shipyard:
                if shipyard != '?' or force:
                    _changed("shipyd", station.shipyard, shipyard)
                    station.shipyard = shipyard

        if maxPadSize is not None:
            maxPadSize = maxPadSize.upper()
            assert maxPadSize in TradeDB.padSizes
            if maxPadSize != station.maxPadSize:
                if maxPadSize != '?' or force:
                    _changed("pad", station.maxPadSize, maxPadSize)
                    station.maxPadSize = maxPadSize

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
                   modified=DATETIME(?)
             WHERE station_id = ?
        """, [
            station.dbname,
            station.lsFromStar,
            station.market,
            station.blackMarket,
            station.shipyard,
            station.maxPadSize,
            modified,
            station.ID
        ])
        db.commit()

        self.tdenv.NOTE(
            "{} (#{}) updated in {}: {}",
            station.name(), station.ID,
            self.dbPath if self.tdenv.detail > 1 else "local db",
            ", ".join(changes)
        )

        return True

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

        if isinstance(name, System) or isinstance(name, Station):
            return name

        slashPos = name.find('/')
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
                    elif subPos > 0:
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
                sys = self.systemByName[sysName]
                exactMatch = [sys]
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
                for sys in itertools.chain(
                        exactMatch, closeMatch, wordMatch, anyMatch
                        ):
                    stationCandidates += sys.stations
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
            raise LookupError("Unrecognized place: {}".format(name))

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
                raise SystemNotStationError(
                    "System '%s' has %d stations, "
                    "please specify a station instead." % (
                        name.str(), len(name.stations)
                    )
                )
            return name.stations[0]

        if system:
            system = self.lookupSystem(system)
            return TradeDB.listSearch(
                "Station", name, system.stations,
                key=lambda system: system.dbname)

        stationID, station, systemID, system = None, None, None, None
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
            raise LookupError(
                "'%s' did not match any station or system." % (name)
            )

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
                "System '%s' has %d stations, "
                "please specify a station instead." % (
                    system.name(), len(system.stations)
                )
            )
        return system.stations[0]

    def getDestinations(
            self,
            origin,
            maxJumps=None,
            maxLyPer=None,
            avoidPlaces=None,
            trading=False,
            maxPadSize=None,
            maxLsFromStar=0,
            ):
        """
        Gets a list of the Station destinations that can be reached
        from this Station within the specified constraints.
        Limits to stations we are trading with if trading is True.
        """

        if trading:
            assert isinstance(origin, Station)
            if not origin.tradingWith:
                return []
            tradingWith = origin.tradingWith

        if maxJumps is None:
            maxJumps = sys.maxsize
        maxLyPer = maxLyPer or self.maxSystemLinkLy
        if avoidPlaces is None:
            avoidPlaces = []

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

        destStations = []

        # We have a system-to-system path list, now we
        # need stations to terminate at.
        for node in pathList.values():
            # negative values are avoidances
            if node.distLy < 0.0:
                continue
            for station in node.system.stations:
                if (trading and station not in tradingWith):
                    continue
                if station in avoidPlaces:
                    continue
                if (maxPadSize and not station.checkPadSize(maxPadSize)):
                    continue
                if maxLsFromStar:
                    stnLs = station.lsFromStar
                    if stnLs <= 0 or stnLs > maxLsFromStar:
                        continue
                destStations.append(
                    Destination(
                        node.system,
                        station,
                        node.via,
                        node.distLy
                    )
                )

        return destStations

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
        self.cur.execute(stmt)
        self.shipByID = {
            row[0]: Ship(*row, stations=[])
            for row in self.cur
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
        self.categoryByID = {
            ID: Category(ID, name, [])
            for (ID, name) in self.cur.execute(stmt)
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
            SELECT item_id, name, category_id
              FROM Item
        """
        itemByID, itemByName = {}, {}
        for (ID, name, categoryID) in self.cur.execute(stmt):
            category = self.categoryByID[categoryID]
            item = Item(
                ID, name, category,
                '{}/{}'.format(category.dbname, name),
                None
            )
            itemByID[ID] = item
            itemByName[name] = item
            category.items.append(item)

        # Some items have different actual names than display names.
        # Load the aliases.
        stmt = """
            SELECT alt_name, item_id
              FROM AltItemNames
        """
        aliases = 0
        for (altName, itemID) in self.cur.execute(stmt):
            assert altName not in itemByName
            aliases += 1
            item = itemByID[itemID]
            item.altname = altName
            itemByName[altName] = item
            self.tdenv.DEBUG1(
                "'{}' alias for #{} '{}'",
                altName, itemID, item.fullname
            )

        self.itemByID = itemByID
        self.itemByName = itemByName

        self.tdenv.DEBUG1(
            "Loaded {:n} Items, {:n} AltItemNames",
            len(self.itemByID), aliases
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
            self.avgSelling = {
                ID: int(cr)
                for ID, cr in self.getDB().execute("""
                    SELECT  Item.item_id, IFNULL(AVG(price), 0)
                      FROM  Item
                            LEFT OUTER JOIN StationSelling
                                USING (item_id)
                     GROUP  BY 1
                """)
            }
        return self.avgSelling

    def getAverageBuying(self):
        """
        Query the database for average buying prices of all items.
        """
        if not self.avgBuying:
            self.avgBuying = {
                ID: int(cr)
                for ID, cr in self.getDB().execute("""
                    SELECT  Item.item_id, IFNULL(AVG(price), 0)
                      FROM  Item
                            LEFT OUTER JOIN StationBuying
                                USING (item_id)
                     GROUP  BY 1
                """)
            }
        return self.avgBuying

    ############################################################
    # Rare Items

    def _loadRareItems(self):
        """
        Populate the RareItem list.
        """
        stmt = """
            SELECT  rare_id,
                    station_id,
                    name,
                    cost,
                    max_allocation
              FROM  RareItem
        """
        self.cur.execute(stmt)

        rareItemByID, rareItemByName = {}, {}
        stationByID = self.stationByID
        for (ID, stnID, name, cost, maxAlloc) in self.cur:
            station = stationByID[stnID]
            rare = RareItem(ID, station, name, cost, maxAlloc)
            rareItemByID[ID] = rareItemByName[name] = rare
        self.rareItemByID = rareItemByID
        self.rareItemByName = rareItemByName

        self.tdenv.DEBUG1(
            "Loaded {:n} RareItems",
            len(rareItemByID)
        )

    ############################################################
    # Price data.

    def loadStationTrades(self, fromStationIDs):
        """
        Loads all profitable trades that could be made from the
        specified list of stations.
        Does not take reachability into account.
        """

        if not fromStationIDs:
            return

        assert isinstance(fromStationIDs, list)
        assert isinstance(fromStationIDs[0], int)

        self.tdenv.DEBUG1("Loading trades for {}", fromStationIDs)

        stmt = """
            SELECT  *
              FROM  vProfits
             WHERE  src_station_id IN ({})
             ORDER  BY src_station_id, dst_station_id, gain DESC
            """.format(','.join(str(ID) for ID in fromStationIDs))
        self.tdenv.DEBUG2("SQL:\n{}\n", stmt)
        self.cur.execute(stmt)
        stations, items = self.stationByID, self.itemByID

        prevSrcStnID, prevDstStnID = None, None
        srcStn, dstStn = None, None
        tradingWith = None
        if self.tradingCount is None:
            self.tradingCount = 0

        for (
            itemID,
            srcStnID, dstStnID,
            srcPriceCr, profit,
            stock, stockLevel,
            demand, demandLevel,
            srcAge, dstAge
        ) in self.cur:
            if srcStnID != prevSrcStnID:
                srcStn = stations[srcStnID]
                prevSrcStnID = srcStnID
                prevDstStnID = None
                assert srcStn.tradingWith is None
                srcStn.tradingWith = {}
            if dstStnID != prevDstStnID:
                dstStn, prevDstStnID = stations[dstStnID], dstStnID
                tradingWith = srcStn.tradingWith[dstStn] = []
                self.tradingCount += 1
            tradingWith.append(Trade(
                items[itemID], itemID,
                srcPriceCr, profit,
                stock, stockLevel,
                demand, demandLevel,
                srcAge, dstAge
            ))

    def loadDirectTrades(self, fromStation, toStation):
        """
        Loads the profitable trades between two stations. Does not take
        reachability into account.
        """

        self.tdenv.DEBUG1(
            "Loading trades for {}->{}",
            fromStation.name(), toStation.name()
        )

        stmt = """
            SELECT  item_id,
                    cost, gain,
                    stock_units, stock_level,
                    demand_units, demand_level,
                    src_age, dst_age,
              FROM  vProfits
             WHERE  src_station_id = ? and dst_station_id = ?
             ORDER  gain DESC
        """
        self.tdenv.DEBUG2("SQL:\n{}\n", stmt)
        self.cur.execute(stmt, [fromStation.ID, toStation.ID])

        trading = []
        items = self.itemByID
        for (
            itemID,
            srcPriceCr, profit,
            stock, stockLevel,
            demand, demandLevel,
            srcAge, dstAge
        ) in self.cur:
            trading.append(Trade(
                items[itemID], itemID,
                srcPriceCr, profit,
                stock, stockLevel,
                demand, demandLevel,
                srcAge, dstAge
                ))

        if fromStation.tradingWith is None:
            fromStation.tradingWith = {}
        if trading:
            fromStation.tradingWith[toStation] = trading
        else:
            del fromStation.tradingWith[toStation]

    def close(self):
        self.cur = None
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

        self.conn = conn = self.getDB()
        self.cur = conn.cursor()

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
        wordRe = re.compile(r'\b{}\b'.format(lookup), re.IGNORECASE)
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
        raise LookupError(
            "Error: '%s' doesn't match any %s" % (lookup, listType)
        )

    @staticmethod
    def normalizedStr(text):
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

    @staticmethod
    def titleFixup(text):
        """
        Correct case in a word assuming the presence of titles/surnames,
        including 'McDonald', 'MacNair', 'McKilroy', and cases that
        python's title screws up such as "Smith's".
        """

        text = text.title()
        text = re.sub(
            r"\b(Mc)([a-z])",
            lambda match: match.group(1) + match.group(2).upper(),
            text
        )
        text = re.sub(
            r"\b(Mac)([bcdfgjklmnpqrstvwxyz])([a-z]{4,})",
            lambda m: m.group(1) + m.group(2).upper() + m.group(3),
            text
        )
        text = re.sub("\b(von|van|de|du|of)\b",
            lambda m: m.group(1).lower,
            text
        )
        text = re.sub(r"'S\b", "'s", text)
        text = text[0].upper() + text[1:]

        return text


######################################################################
# Assorted helpers


def describeAge(ageInSeconds):
    """
    Turns an age (in seconds) into a text representation.
    """
    hours = int(ageInSeconds / 3600)
    if hours < 1:
        return "<1 hr"
    if hours == 1:
        return "1 hr"
    if hours < 48:
        return str(hours) + " hrs"
    days = int(hours / 24)
    if days < 90:
        return str(days) + " days"

    months = int(days / 31)
    return str(months) + " mths"
