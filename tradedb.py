# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
#---------------------------------------------------------------------
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

from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

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
    def __init__(self, lookupType, searchKey, anyMatch, key=lambda item:item):
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

    __slots__ = ('ID', 'dbname', 'posX', 'posY', 'posZ', 'stations', '_rangeCache')

    class RangeCache(object):
        """
        Lazily populated cache of neighboring systems.
        """
        def __init__(self):
            self.systems = []
            self.probedLy = 0.


    def __init__(self, ID, dbname, posX, posY, posZ):
        self.ID, self.dbname, self.posX, self.posY, self.posZ = ID, dbname, posX, posY, posZ
        self.stations = []
        self._rangeCache = None



    def distToSq(self, other):
        """
        Returns the square of the distance between two systems.

        Optimization Note:

        This function returns the SQUARE of the distance.

        For any given pair of numbers (n, m), if n > m then n^2 > m^2
        and if n < m then n^2 < m^2 and if n == m n^2 == m^2.

        The final step in a distance calculation is a sqrt() function,
        which is expensive.

        So when you only need distances for comparative purposes, such
        as comparing a set of points against a given distance, it is
        much more efficient to square the comparitor and test it
        against the un-rooted distances.

        Args:
            other:
                The other System to measure the distance between.

        Returns:
            Distance in light years (squared).

        Example:
            # Calculate which of [systems] is within 12 ly
            # of System "target".
            maxLySq = 12 ** 2   # Maximum of 12 ly.
            inRange = []
            for sys in systems:
                if sys.distToSq(target) <= maxLySq:
                    inRange.append(sys)

            # Print the distance between two systems
            print("{} -> {}: {}ly".format(
                    lhs.name(), rhs.name(),
                    math.sqrt(lhs.distToSq(rhs)),
            ))
        """

        dx2 = (self.posX - other.posX) ** 2
        dy2 = (self.posY - other.posY) ** 2
        dz2 = (self.posZ - other.posZ) ** 2

        return (dx2 + dy2 + dz2)


    def name(self):
        return self.dbname


    def str(self):
        return self.dbname


    def __repr__(self):
        return "System(ID={},dbname='{}',posX={},posY={},posZ={})".format(
                self.ID, re.escape(self.dbname), self.posX, self.posY, self.posZ
        )


######################################################################


class Destination(namedtuple('Destination', [
                    'system', 'station', 'via', 'distLy' ])):
    pass

class DestinationNode(namedtuple('DestinationNode', [
                    'system', 'via', 'distLy' ])):
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
            'lsFromStar', 'blackMarket', 'maxPadSize',
            'tradingWith', 'itemCount',
    )

    def __init__(
            self, ID, system, dbname,
            lsFromStar, blackMarket, maxPadSize,
            itemCount,
            ):
        self.ID, self.system, self.dbname = ID, system, dbname
        self.lsFromStar = lsFromStar
        self.blackMarket = blackMarket
        self.maxPadSize = maxPadSize
        self.itemCount = itemCount
        self.tradingWith = None       # dict[tradingPartnerStation] -> [ available trades ]
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
        if ls < 4000:
            suffix = 'ls' if addSuffix else ''
            return '{:n}'.format(ls)+suffix
        if ls < 40000:
            suffix = 'ls' if addSuffix else ''
            return '{:.1f}K'.format(ls / 1000)+suffix
        return '{:.2f}ly'.format(ls / (365*24*60*60))


    def str(self):
        return self.dbname


    def __repr__(self):
        return ("Station("
                    "ID={}, system='{}', dbname='{}', "
                    "lsFromStar={}, "
                    "blackMarket='{}', "
                    "maxPadSize='{}'"
                    ")".format(
                self.ID,
                re.escape(self.system.dbname),
                re.escape(self.dbname),
                self.lsFromStar,
                self.blackMarket,
                self.maxPadSize,
        ))


######################################################################


class Ship(namedtuple('Ship', [ 'ID', 'dbname', 'cost', 'stations' ])):
    def name(self):
        return self.dbname


######################################################################


class Category(namedtuple('Category', [ 'ID', 'dbname', 'items' ])):
    """
    Items are organized into categories (Food, Drugs, Metals, etc).
    Category object describes a category's ID, name and list of items.
    """
    def name(self):
        return self.dbname.upper()


    def __str__(self):
        return self.dbname


######################################################################


class Item(object):
    """
    Describes a product that can be bought/sold in the game.

    Attributes:
        ID       -- Database ID.
        dbname   -- Name as it appears in-game and in the DB.
        category -- Reference to the category.
        fullname -- Combined category/dbname for lookups.
        altname  -- The internal name used by the game.
    """
    __slots__ = ('ID', 'dbname', 'category', 'fullname', 'altname')

    def __init__(self, ID, dbname, category, fullname, altname=None):
        self.ID, self.dbname, self.category, self.fullname, self.altname = ID, dbname, category, fullname, altname


    def name(self):
        return self.dbname


    def __str__(self):
        return '{}/{}'.format(self.category.name, self.dbname)


    def __repr__(self):
        return "Item(ID={}, dbname='{}', category={}, fullname='{}', altName={})".format(
                self.ID, re.escape(self.dbname), repr(self.category), re.escape(self.fullname),
                "'{}'".format(re.escape(self.altname) if self.altname else 'None')
            )


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
            'item', 'itemID', 'costCr', 'gainCr', 'stock', 'stockLevel', 'demand', 'demandLevel', 'srcAge', 'dstAge'
        ])):
    """
    Describes what it would cost and how much you would gain
    when selling an item between two specific stations.
    """
    def name(self):
        return self.item.name()


    def str(self):
        return self.item.name()


    def __repr__(self):
        return ("Trade("
                "item={},itemID={},"
                "costCr={},gainCr={},"
                "stock={},stockLevel={},"
                "demand={},demandLevel={},"
                "srcAge={},dstAge={}"
                ")".format(
                    self.item.name(), self.itemID,
                    self.costCr, self.gainCr,
                    self.stock, self.stockLevel,
                    self.demand, self.demandLevel,
                    self.srcAge, self.dstAge,
                )
        )


######################################################################


class TradeDB(object):
    """
        Encapsulation for the database layer.

        Attributes:
            dbPath              -   Path object describing the db location.
            dbFilename          -   str(dbPath)
            conn                -   The database connection.

        Methods:
            load                -   Reloads entire database. CAUTION: Destructive - Orphans existing records you reference.
            lookupSystem        -   Return a system matching "name" with ambiguity detection.
            lookupStation       -   Return a station matching "name" with ambiguity detection.
            lookupShip          -   Return a ship matching "name" with ambiguity detection.
            getTrades           -   Returns the list of Trade objects between two stations.

            query               -   Executes the specified SQL on the db and returns a cursor.
            fetch_all           -   Generator that yields all the rows retrieved by an sql cursor.

        Static methods:
            listSearch          -   Performs a partial-match search of a list for a value.
            normalizedStr       -   Normalizes a search index string.
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
                      [ 'Added.csv', 'Added' ],
                      [ 'System.csv', 'System' ],
                      [ 'Station.csv', 'Station' ],
                      [ 'Ship.csv', 'Ship' ],
                      [ 'ShipVendor.csv', 'ShipVendor' ],
                      [ 'Upgrade.csv', 'Upgrade' ],
                      [ 'UpgradeVendor.csv', 'UpgradeVendor' ],
                      [ 'Category.csv', 'Category' ],
                      [ 'Item.csv', 'Item' ],
                      [ 'AltItemNames.csv', 'AltItemNames' ],
                      [ 'RareItem.csv', 'RareItem' ],
                    ]


    # Translation matrixes for attributes -> common presentation
    marketStates = { '?': '?', 'Y': 'Yes', 'N': 'No' }
    marketStatesExt = { '?': 'Unk', 'Y': 'Yes', 'N': 'No' }
    padSizes = { '?': '?', 'S': 'Sml', 'M': 'Med', 'L': 'Lrg' }
    padSizesExt = { '?': 'Unk', 'S': 'Sml', 'M': 'Med', 'L': 'Lrg' }


    def __init__(self,
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
        self.pricesPath = dataPath / Path(tdenv.pricesFilename or TradeDB.defaultPrices)
        self.importTables = [
                (str(dataPath / Path(fn)), tn)
                for fn, tn in TradeDB.defaultTables
        ]
        self.importPaths = { tn: tp for tp, tn in self.importTables }

        self.dbFilename = str(self.dbPath)
        self.sqlFilename = str(self.sqlPath)
        self.pricesFilename = str(self.pricesPath)

        self.avgSelling, self.avgBuying = None, None
        self.tradingStationCount = 0

        if load:
            self.reloadCache()
            self.load(
                    maxSystemLinkLy=tdenv.maxSystemLinkLy,
            )

    @staticmethod
    def calculateDistance2(lx, ly, lz, rx, ry, rz):
        """
        Returns the square of the distance between two points
        """
        dX = (lx - rx)
        dY = (ly - ry)
        dZ = (lz - rz)
        return (dX ** 2) + (dY ** 2) + (dZ ** 2)


    ############################################################
    # Access to the underlying database.

    def getDB(self):
        if self.conn: return self.conn
        try:
            self.tdenv.DEBUG1("Connecting to DB")
            import sqlite3
            conn = sqlite3.connect(self.dbFilename)
            conn.execute("PRAGMA foreign_keys=ON")
            conn.create_function('dist2', 6, TradeDB.calculateDistance2)
            return conn
        except ImportError as e:
            print("ERROR: You don't appear to have the Python sqlite3 module installed. Impressive. No, wait, the other one: crazy.")
            raise e


    def query(self, *args):
        """ Perform an SQL query on the DB and return the cursor. """
        conn = self.getDB()
        cur = conn.cursor()
        cur.execute(*args)
        return cur


    # following the convention of how fetch_all is written in python modules.
    def fetch_all(self, *args):
        """ Perform an SQL query on the DB and iterate across the rows. """
        for row in self.query(*args):
            yield row


    def reloadCache(self):
        """
            Checks if the .sql, .prices or *.csv files are newer than the cache.
        """

        if self.dbPath.exists():
            dbFileStamp = self.dbPath.stat().st_mtime

            paths = [ self.sqlPath ]
            paths += [ Path(f) for (f, _) in self.importTables ]

            changedPaths = [
                    [path, path.stat().st_mtime]
                        for path in paths
                        if path.exists() and
                            path.stat().st_mtime > dbFileStamp
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
                cache.importDataFromFile(self, self.tdenv, self.pricesPath, reset=True)
                return

            self.tdenv.DEBUG0("Rebuilding DB Cache [{}]", str(changedPaths))
        else:
            self.tdenv.DEBUG0("Building DB Cache")

        cache.buildCache(self, self.tdenv)


    ############################################################
    # Star system data.


    def systems(self):
        """ Iterate through the list of systems. """
        yield from self.systemByID.values()


    def _loadSystems(self):
        """
        Initial load the (raw) list of systems.
        If you have previously loaded Systems, this will orphan the old System objects.
        """
        stmt = """
                SELECT system_id, name, pos_x, pos_y, pos_z
                  FROM System
            """
        self.cur.execute(stmt)
        systemByID, systemByName = {}, {}
        for (ID, name, posX, posY, posZ) in self.cur:
            systemByID[ID] = systemByName[name.upper()] = System(ID, name, posX, posY, posZ)

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

        return TradeDB.listSearch("System", key, self.systems(), key=lambda system: system.dbname)


    def addLocalSystem(self, name, x, y, z):
        """
        Add a system to the local cache and memory copy.
        """

        db = self.getDB()
        cur = db.cursor()
        cur.execute("""
                INSERT INTO System (
                    name, pos_x, pos_y, pos_z, added_id
                ) VALUES (
                    ?, ?, ?, ?,
                    (SELECT added_id
                       FROM Added
                      WHERE name = ?)
                )
        """, [
                name, x, y, z, 'Local',
        ])
        ID = cur.lastrowid
        system = System(ID, name.upper(), x, y, z)
        self.systemByID[ID] = system
        self.systemByName[system.dbname] = system
        db.commit()
        if not self.tdenv.quiet:
            print("- Added new system #{}: {} [{},{},{}]".format(
                    ID, name, x, y, z
            ))
        return system


    def lookupSystemRelaxed(self, key):
        """
        Lookup a System object by it's name or by the name of any of it's stations.
        """
        try:
            place = self.lookupPlace(key)
            if isinstance(place, Station):
                return place.system
            else:
                return place
        except AmbiguityError as e:
            # See if the ambiguity resolves down to a single system.
            systems = set()
            for candidate in e.anyMatch:
                if isinstance(candidate, Station):
                    systems.add(candidate.system)
                else:
                    systems.add(candidate)
            if len(systems) == 1:
                return systems[0]
            # Nope, genuine ambiguity
            raise


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
                        grid = stellarGrid[(x,y,z)]
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
                    The distance in lightyears betwen system and candidate.
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
                            math.sqrt(distSq)
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


    def getRoute(self, origin, dest, maxJumpLy, avoiding=[]):
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
        openSet = [(0, 0, origin.ID)]
        # Track predecessor nodes for everwhere we visit
        distances = { origin: (None, 0) }
        destID = dest.ID
        sysByID = self.systemByID
        distTo = float("inf")

        if avoiding:
            if dest in avoiding:
                raise ValueError("Destination is in avoidance list")
            for avoid in avoiding:
                if isinstance(avoid, System):
                    distances[avoid] = (None, -1)

        while openSet:
            weight, curDist, curSysID = heapq.heappop(openSet)
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

            for (nSys, nDist) in self.genSystemsInRange(curSys, maxJumpLy):
                newDist = curDist + nDist
                try:
                    (prevSys, prevDist) = distances[nSys]
                    if prevDist <= newDist:
                        continue
                except KeyError:
                    pass
                distances[nSys] = (curSys, newDist)
                weight = math.sqrt(curSys.distToSq(nSys))
                nID = nSys.ID
                # + 1 adds a penalty per jump
                heapq.heappush(openSet, (newDist + weight + 1, newDist, nID))
                if nID == destID:
                    distTo = newDist

        if not dest in distances:
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
            If you have previously loaded Stations, this will orphan the old objects.
        """
        stmt = """
                SELECT  station_id, system_id, name,
                        ls_from_star, blackmarket, max_pad_size,
                        (SELECT COUNT(*)
                            FROM StationItem
                            WHERE station_id = Station.station_id) AS itemCount
                  FROM  Station
            """
        self.cur.execute(stmt)
        stationByID = {}
        systemByID = self.systemByID
        self.tradingStationCount = 0
        for (
            ID, systemID, name,
            lsFromStar, blackMarket, maxPadSize,
            itemCount
        ) in self.cur:
            station = Station(
                    ID, systemByID[systemID], name,
                    lsFromStar, blackMarket, maxPadSize,
                    itemCount
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
            lsFromStar,
            blackMarket,
            maxPadSize,
            ):
        """
        Add a station to the local cache and memory copy.
        """

        blackMarket = blackMarket.upper()
        maxPadSize = maxPadSize.upper()
        assert blackMarket in "?YN"
        assert maxPadSize in "?SML"

        self.tdenv.DEBUG0(
                "Adding {}/{} ls={}, bm={}, pad={}",
                system.name(),
                name,
                lsFromStar,
                blackMarket,
                maxPadSize
        )

        db = self.getDB()
        cur = db.cursor()
        cur.execute("""
                INSERT INTO Station (
                    name, system_id,
                    ls_from_star, blackmarket, max_pad_size
                ) VALUES (
                    ?, ?,
                    ?, ?, ?
                )
        """, [
                name, system.ID,
                lsFromStar, blackMarket.upper(), maxPadSize.upper(),
        ])
        ID = cur.lastrowid
        station = Station(
                ID, system, name,
                lsFromStar=lsFromStar,
                blackMarket=blackMarket,
                maxPadSize=maxPadSize,
                itemCount=0,
        )
        self.stationByID[ID] = station
        db.commit()
        self.tdenv.NOTE(
                "{} (#{}) added to {} db: "
                "ls={}, bm={}, pad={}",
                    station.name(), station.ID, self.dbPath,
                    lsFromStar, blackMarket, maxPadSize,
        )
        return station

    def updateLocalStation(
            self, station,
            lsFromStar=None,
            blackMarket=None,
            maxPadSize=None,
            force=False,
            ):
        """
        Alter the properties of a station in-memory and in the DB.
        """
        changes = False
        if lsFromStar is not None:
            assert lsFromStar >= 0
            if lsFromStar != station.lsFromStar:
                if lsFromStar > 0 or force:
                    station.lsFromStar = lsFromStar
                    changes = True
        if blackMarket is not None:
            blackMarket = blackMarket.upper()
            assert blackMarket in [ '?', 'Y', 'N' ]
            if blackMarket != station.blackMarket:
                if blackMarket != '?' or force:
                    station.blackMarket = blackMarket
                    changes = True
        if maxPadSize is not None:
            maxPadSize = maxPadSize.upper()
            assert maxPadSize in [ '?', 'S', 'M', 'L' ]
            if maxPadSize != station.maxPadSize:
                if maxPadSize != '?' or force:
                    station.maxPadSize = maxPadSize
                    changes = True
        if not changes:
            self.tdenv.NOTE("No changes")
            return False
        db = self.getDB()
        db.execute("""
            UPDATE Station
               SET ls_from_star=?,
                   blackmarket=?,
                   max_pad_size=?
             WHERE station_id = ?
        """, [
            station.lsFromStar,
            station.blackMarket,
            station.maxPadSize,
            station.ID
        ])
        db.commit()
        self.tdenv.NOTE(
                "{} (#{}) updated in {}: ls={}, bm={}, pad={}",
                station.name(), station.ID, self.dbPath,
                station.lsFromStar,
                station.blackMarket,
                station.maxPadSize,
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
            sysName, stnName = name[nameOff:slashPos].upper(), name[slashPos+1:]
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
                exactMatch = [ sys ]
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
                    key=lambda place: place.name())


    def lookupStation(self, name, system=None):
        """
            Look up a Station object by it's name or system.
        """
        if isinstance(name, Station):
            return name
        if isinstance(name, System):
            # If they provide a system and it only has one station, return that.
            if len(name.stations) != 1:
                raise SystemNotStationError("System '%s' has %d stations, please specify a station instead." % (name.str(), len(name.stations)))
            return name.stations[0]

        if system:
            system = self.lookupSystem(system)
            return TradeDB.listSearch("Station", name, system.stations, key=lambda system: system.dbname)

        stationID, station, systemID, system = None, None, None, None
        try:
            system = TradeDB.listSearch("System", name, self.systemByID.values(), key=lambda system: system.dbname)
        except LookupError:
            pass
        try:
            station = TradeDB.listSearch("Station", name, self.stationByID.values(), key=lambda station: station.dbname)
        except LookupError:
            pass
        # If neither matched, we have a lookup error.
        if not (station or system):
            raise LookupError("'%s' did not match any station or system." % (name))

        # If we matched both a station and a system, make sure they resovle to the
        # the same station otherwise we have an ambiguity. Some stations have the
        # same name as their star system (Aulin/Aulin Enterprise)
        if system and station and system != station.system:
            raise AmbiguityError('Station', name, [ system.name(), station.name() ])

        if station:
            return station

        # If we only matched a system name, ensure that it's a single station system
        # otherwise they need to specify a station name.
        if len(system.stations) != 1:
            raise SystemNotStationError("System '%s' has %d stations, please specify a station instead." % (system.name(), len(system.stations)))
        return system.stations[0]


    def getDestinations(self,
            origin,
            maxJumps=None,
            maxLyPer=None,
            avoidPlaces=None,
            trading=False,
            maxPadSize=None):
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
        openList = [ DestinationNode(origSys, [origSys], 0) ]
        # I don't want to have to consult both the pathList
        # AND the avoid list every time I'm considering a
        # station, so copy the avoid list into the pathList
        # with a negative distance so I can ignore them again
        # when I scrape the pathList.
        # Don't copy stations because those only affect our
        # termination points, and not the systems we can
        # pass through en-route.
        pathList = { system.ID: DestinationNode(system, None, -1.0)
                        for system in avoidPlaces
                        if isinstance(system, System) }
        if not origSys.ID in pathList:
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
                    destNode = DestinationNode(destSys, node.via + [destSys], dist)
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
                destStations.append(
                            Destination(node.system,
                                    station,
                                    node.via,
                                    node.distLy)
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
            If you have previously loaded Ships, this will orphan the old objects.
        """
        stmt = """
                SELECT ship_id, name, cost
                  FROM Ship
            """
        self.cur.execute(stmt)
        self.shipByID = { row[0]: Ship(*row, stations=[]) for row in self.cur }

        self.tdenv.DEBUG1("Loaded {} Ships", len(self.shipByID))


    def lookupShip(self, name):
        """
            Look up a ship by name
        """
        return TradeDB.listSearch("Ship", name, self.shipByID.values(), key=lambda ship: ship.dbname)


    ############################################################
    # Item data.

    def categories(self):
        """
            Iterate through the list of categories. key = category name, value = list of items.
        """
        yield from self.categoryByID.items()


    def _loadCategories(self):
        """
            Populate the list of item categories.
            If you have previously loaded Categories, this will orphan the old objects.
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


    # TODO: Provide CATEGORIES so that you can do an item lookup.
    def _loadItems(self):
        """
            Populate the Item list.
            If you have previously loaded Items, this will orphan the old objects.
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
            Loads all profitable trades that could be made
            from the specified list of stations. Does not
            take reachability into account.
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
                    srcAge, dstAge))


    def loadDirectTrades(self, fromStation, toStation):
        """
            Loads all profitable trades that could be made
            from the specified list of stations. Does not
            take reachability into account.
        """

        self.tdenv.DEBUG1("Loading trades for {}->{}",
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
        self.cur.execute(stmt, [ fromStation.ID, toStation.ID ])

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
                    srcAge, dstAge))

        if fromStation.tradingWith is None:
            fromStation.tradingWith = {}
        if trading:
            fromStation.tradingWith[toStation] = trading
        else:
            del fromStation.tradingWith[toStation]


    def getTrades(self, src, dst):
        """ Returns a list of the Trade objects between src and dst. """

        # I could write this more compactly, but it makes errors less readable.
        srcStn = self.lookupStation(src)
        dstStn = self.lookupStation(dst)
        return srcStn.tradingWith[dstStn]


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

        # Load raw tables. Stations will be linked to systems, but nothing else.
        # TODO: Make station -> system link a post-load action.
        self._loadSystems()
        self._loadStations()
        self._loadShips()
        self._loadCategories()
        self._loadItems()
        self._loadRareItems()

        systems, stations, ships, items = self.systemByID, self.stationByID, self.shipByID, self.itemByID

        # Calculate the maximum distance anyone can jump so we can constrain
        # the maximum "link" between any two stars.
        self.maxSystemLinkLy = maxSystemLinkLy or self.tdenv.maxSystemLinkLy or 30


    ############################################################
    # General purpose static methods.

    @staticmethod
    def listSearch(listType, lookup, values, key=lambda item: item, val=lambda item: item):
        """
            Searches [values] for 'lookup' for least-ambiguous matches,
            return the matching value as stored in [values].
            If [values] contains "bread", "water", "biscuits and "It",
            searching "ea" will return "bread", "WaT" will return "water"
            and "i" will return "biscuits". Searching for "a" will raise
            an AmbiguityError because "a" matches "bread" and "water", but
            searching for "it" will return "It" because it provides an
            exact match of a key.
        """

        class ListSearchMatch(namedtuple('Match', [ 'key', 'value' ])):
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
                raise AmbiguityError(listType, lookup, wordMatch, key=lambda item: item.key)
            return wordMatch[0].value
        # Fuzzy matches
        if partialMatch:
            if len(partialMatch) > 1:
                raise AmbiguityError(listType, lookup, partialMatch, key=lambda item: item.key)
            return partialMatch[0].value
        # No matches
        raise LookupError("Error: '%s' doesn't match any %s" % (lookup, listType))


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

