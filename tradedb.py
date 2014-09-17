#!/usr/bin/env python
#---------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
#---------------------------------------------------------------------
# TradeDangerous :: Modules :: Database Module
#
#  Containers for describing the current TradeDangerous database
#  and loading it from the SQLite database cache.

######################################################################
# Imports

import re                   # Because irregular expressions are dull
import sys
from collections import namedtuple
import itertools
import math
from pathlib import Path

######################################################################
# Classes

class AmbiguityError(Exception):
    """
        Raised when a search key could match multiple entities.
        Attributes:
            lookupType - description of what was being queried,
            searchKey  - the key given to the search routine,
            first      - the first potential match,
            second     - the alternate match
    """
    def __init__(self, lookupType, searchKey, first, second):
        self.lookupType, self.searchKey, self.first, self.second = lookupType, searchKey, first, second


    def __str__(self):
        return '%s lookup: "%s" could match either "%s" or "%s"' % (self.lookupType, str(self.searchKey), str(self.first), str(self.second))


class SystemNotStationError(ValueError):
    """
        Raised when a station lookup matched a System but
        could not be automatically reduced to a Station.
    """
    pass

######################################################################


class System(object):
    """
        Describes a star system, which may contain one or more Station objects,
        and lists which stars it has a direct connection to.
    """
    __slots__ = ('ID', 'dbname', 'posX', 'posY', 'posZ', 'links', 'stations')

    def __init__(self, ID, dbname, posX, posY, posZ):
        self.ID, self.dbname, self.posX, self.posY, self.posZ = ID, dbname, posX, posY, posZ
        self.links = {}
        self.stations = []


    @staticmethod
    def linkSystems(lhs, rhs, distSq):
        lhs.links[rhs] = rhs.links[lhs] = math.sqrt(distSq)


    def addStation(self, station):
        if not station in self.stations:
            self.stations.append(station)


    def name(self):
        return self.dbname.upper()


    def str(self):
        return self.dbname


    def __repr__(self):
        return "System(ID={}, dbname='{}', posX={}, posY={}, posZ={})".format(self.ID, re.escape(self.dbname), self.posX, self.posY, self.posZ)


######################################################################


class Station(object):
    """
        Describes a station within a given system along with what trade
        opportunities it presents.
    """
    __slots__ = ('ID', 'system', 'dbname', 'lsFromStar', 'tradingWith')

    def __init__(self, ID, system, dbname, lsFromStar=0.0):
        self.ID, self.system, self.dbname, self.lsFromStar = ID, system, dbname, lsFromStar
        self.tradingWith = {}       # dict[tradingPartnerStation] -> [ available trades ]
        system.addStation(self)


    def name(self):
        return self.dbname


    def addTrade(self, dest, trade):
        """
            Add an entry reflecting that an item can be bought at this
            station and sold for a gain at another.
        """
        # TODO: Something smarter.
        if not dest in self.tradingWith:
            self.tradingWith[dest] = []
        self.tradingWith[dest].append(trade)


    def getDestinations(self, maxJumps=None, maxLyPer=None, avoiding=None):
        """
            Gets a list of the Station destinations that can be reached
            from this Station within the specified constraints.
        """

        avoiding = avoiding or []
        maxJumps = maxJumps or sys.maxsize
        maxLyPer = maxLyPer or float("inf")

        # The open list is the list of nodes we should consider next for
        # potential destinations.
        # The path list is a list of the destinations we've found and the
        # shortest path to them. It doubles as the "closed list".
        # The closed list is the list of nodes we've already been to (so
        # that we don't create loops A->B->C->A->B->C->...)

        Node = namedtuple('Node', [ 'system', 'via', 'distLy' ])

        openList = [ Node(self.system, [], 0) ]
        pathList = { system.ID: Node(system, None, 0.0)
                            # include avoids so we only have
                            # to consult one place for exclusions
                        for system in avoiding + [ self ]
                            # the avoid list may contain stations,
                            # which affects destinations but not vias
                        if isinstance(system, System) }

        # As long as the open list is not empty, keep iterating.
        jumps = 0
        while openList and jumps < maxJumps:
            # Expand the search domain by one jump; grab the list of
            # nodes that are this many hops out and then clear the list.
            ring, openList = openList, []
            # All of the destinations we are about to consider will
            # either be on the closed list or they will be +1 jump away.
            jumps += 1

            for node in ring:
                for (destSys, destDist) in node.system.links.items():
                    if destDist > maxLyPer: continue
                    dist = node.distLy + destDist
                    # If we already have a shorter path, do nothing
                    try:
                        if dist >= pathList[destSys.ID].distLy: continue
                    except KeyError: pass
                    # Add to the path list
                    pathList[destSys.ID] = Node(destSys, node.via, dist)
                    # Add to the open list but also include node to the via
                    # list so that it serves as the via list for all next-hops.
                    openList += [ Node(destSys, node.via + [destSys], dist) ]

        Destination = namedtuple('Destination', [ 'system', 'station', 'via', 'distLy' ])

        destStations = []
        # always include the local stations, unless the user has indicated they are
        # avoiding this system. E.g. if you're in Chango but you've specified you
        # want to avoid Chango...
        if not self.system in avoiding:
            for station in self.system.stations:
                if station in self.tradingWith and not station in avoiding:
                    destStations += [ Destination(self, station, [], 0.0) ]

        avoidStations = [ station for station in avoiding if isinstance(station, Station) ]
        epsilon = sys.float_info.epsilon
        for node in pathList.values():
            if node.distLy > epsilon:       # Values indistinguishable from zero are avoidances
                for station in node.system.stations:
                    if not station in avoidStations:
                        destStations += [ Destination(node.system, station, [self.system] + node.via + [station.system], node.distLy) ]

        return destStations


    def name(self):
        return self.dbname


    def str(self):
        return '%s/%s' % (self.system.name(), self.dbname)


    def __repr__(self):
        return "Station(ID={}, system='{}', dbname='{}', lsFromStar={})".format(self.ID, re.escape(self.system.dbname), re.escape(self.dbname), self.lsFromStar)


######################################################################


class Ship(namedtuple('Ship', [ 'ID', 'dbname', 'capacity', 'mass', 'driveRating', 'maxLyEmpty', 'maxLyFull', 'maxSpeed', 'boostSpeed', 'stations' ])):
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


class Trade(object):
    """
        Describes what it would cost and how much you would gain
        when selling an item between two specific stations.
    """
    __slots__ = ('item', 'itemID', 'costCr', 'gainCr', 'stock', 'stockLevel', 'demand', 'demandLevel', 'srcAge', 'dstAge')
    # TODO: Replace with a class within Station that describes asking and paying.
    def __init__(self, item, itemID, costCr, gainCr, stock, stockLevel, demand, demandLevel, srcAge, dstAge):
        self.item, self.itemID = item, itemID
        self.costCr, self.gainCr = costCr, gainCr
        self.stock, self.stockLevel = stock, stockLevel
        self.demand, self.demandLevel = demand, demandLevel
        self.srcAge, self.dstAge = srcAge, dstAge


    def name(self):
        return self.item.name()


    def describe(self):
        print(self.item, self.itemID, self.costCr, self.gainCr)


    def __repr__(self):
        return "Trade(item={}, itemID={}, costCr={}, gainCr={})".format(repr(self.item()), self.itemID, self.costCr, self.gainCr)


######################################################################


class TradeDB(object):
    """
        Encapsulation for the database layer.

        Attributes:
            debug               -   Debugging level for this instance.
            dbPath              -   Path object describing the db location.
            dbURI               -   String representation of the db location (e.g. filename).
            conn                -   The database connection.

        Methods:
            load                -   Reloads entire database. CAUTION: Destructive - Orphans existing records you reference.
            loadTrades          -   Reloads just the price data. CAUTION: Destructive - Orphans existing records.
            lookupSystem        -   Return a system matching "name" with ambiguity detection.
            lookupStation       -   Return a station matching "name" with ambiguity detection.
            lookupShip          -   Return a ship matching "name" with ambiguity detection.
            getTrade            -   Look for a Trade object where item is sold from one stationi and bought at another.

            query               -   Executes the specified SQL on the db and returns a cursor.
            fetch_all           -   Generator that yields all the rows retrieved by an sql cursor.
            
        Static methods:
            distanceSq          -   Returns the square of the distance between two points.
            listSearch          -   Performs a partial-match search of a list for a value.
            normalizedStr       -   Normalizes a search index string.
    """

    normalizeRe = re.compile(r'[ \t\'\"\.\-_]')
    # The DB cache
    defaultDB = './data/TradeDangerous.db'
    # File containing SQL to build the DB cache from
    defaultSQL = './data/TradeDangerous.sql'
    # File containing text description of prices
    defaultPrices = './data/TradeDangerous.prices'


    def __init__(self, dbFilename=None, sqlFilename=None, pricesFilename=None, debug=0):
        self.dbPath = Path(dbFilename or TradeDB.defaultDB)
        self.dbURI = str(self.dbPath)
        self.sqlPath = Path(sqlFilename or TradeDB.defaultSQL)
        self.pricesPath = Path(pricesFilename or TradeDB.defaultPrices)
        self.debug = debug
        self.conn = None

        self.reloadCache()

        self.load()


    ############################################################
    # Access to the underlying database.

    def getDB(self):
        if self.conn: return self.conn
        try:
            if self.debug > 1: print("* Connecting to DB")
            import sqlite3
            return sqlite3.connect(self.dbURI)
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
            Checks if the .sql or .prices file is newer than the cache.
        """

        if self.dbPath.exists():
            # We're looking to see if the .sql file or .prices file
            # was modified or created more recently than the last time
            # we *created* the db file.
            dbFileCreatedTimestamp = self.dbPath.stat().st_mtime

            sqlStat, pricesStat = self.sqlPath.stat(), self.pricesPath.stat()
            sqlFileTimestamp = max(sqlStat.st_mtime, sqlStat.st_ctime)
            pricesFileTimestamp = max(pricesStat.st_mtime, pricesStat.st_ctime)

            if dbFileCreatedTimestamp > max(sqlFileTimestamp, pricesFileTimestamp):
                # db is newer.
                if self.debug > 1:
                    print("- SQLite is up to date")
                return

            if self.debug:
                print("* Rebuilding DB Cache [db:{}, sql:{}, prices:{}]".format(dbFileCreatedTimestamp, sqlFileTimestamp, pricesFileTimestamp))
        else:
            if self.debug:
                print("* Building DB cache")

        import data.buildcache
        data.buildcache.buildCache(dbPath=self.dbPath, sqlPath=self.sqlPath, pricesPath=self.pricesPath)


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
            systemByID[ID] = systemByName[name] = System(ID, name, posX, posY, posZ)

        self.systemByID, self.systemByName = systemByID, systemByName
        if self.debug > 1: print("# Loaded %d Systems" % len(systemByID))


    def buildLinks(self, longestJumpLy):
        """
            Populate the list of reachable systems for every star system.

            Not every system can reach every other, and we use the longest jump
            that can be made by a ship to limit how many connections we consider
            to be "links".
        """

        longestJumpSq = longestJumpLy ** 2  # So we don't have to sqrt every distance

        # Generate a series of symmetric pairs (A->B, A->C, A->D, B->C, B->D, C->D)
        # so we only calculate each distance once, and then add a link each way.
        # (A->B distance populates A->B and B->A, etc)
        numLinks = 0
        for (lhs, rhs) in itertools.combinations(self.systemByID.values(), 2):
            dX, dY, dZ = rhs.posX - lhs.posX, rhs.posY - lhs.posY, rhs.posZ - lhs.posZ
            distSq = (dX * dX) + (dY * dY) + (dZ * dZ)
            if distSq <= longestJumpSq:
                System.linkSystems(lhs, rhs, distSq)
                numLinks += 1

        if self.debug > 2: print("# Number of links between systems: %d" % numLinks)


    def lookupSystem(self, key):
        """
            Look up a System object by it's name.
        """
        if isinstance(key, System):
            return key
        if isinstance(key, Station):
            return key.system

        return TradeDB.listSearch("System", key, self.systems(), key=lambda system: system.dbname)


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
                SELECT station_id, system_id, name, ls_from_star
                  FROM Station
            """
        self.cur.execute(stmt)
        stationByID, stationByName = {}, {}
        systemByID = self.systemByID
        for (ID, systemID, name, lsFromStar) in self.cur:
            stationByID[ID] = stationByName[name] = Station(ID, systemByID[systemID], name, lsFromStar)

        self.stationByID, self.stationByName = stationByID, stationByName
        if self.debug > 1: print("# Loaded %d Stations" % len(stationByID))


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
            raise AmbiguityError('Station', name, system.name(), station.name())

        if station:
            return station

        # If we only matched a system name, ensure that it's a single station system
        # otherwise they need to specify a station name.
        if len(system.stations) != 1:
            raise SystemNotStationError("System '%s' has %d stations, please specify a station instead." % (name, len(system.stations)))
        return system.stations[0]


    def lookupStationExplicitly(self, name, system=None):
        """
            Look up a Station object by it's name.
        """
        if isinstance(name, Station):
            if system and name.system.ID != system.ID:
                raise LookupError("Station '{}' is not in System '{}'".format(name.dbname, system.dbname))
            return name

        nameList = system.stations if system else self.stationByID.values()
        return TradeDB.listSearch("Station", name, nameList, key=lambda entry: entry.dbname)


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
                SELECT ship_id, name, capacity, mass, drive_rating, max_ly_empty, max_ly_full, max_speed, boost_speed
                  FROM Ship
            """
        self.cur.execute(stmt)
        self.shipByID = { row[0]: Ship(*row, stations=[]) for row in self.cur }

        if self.debug > 1: print("# Loaded %d Ships" % len(self.shipByID))


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
        self.categoryByID = { ID: Category(ID, name, []) for (ID, name) in self.cur.execute(stmt) }

        if self.debug > 1: print("# Loaded %d Categories" % len(self.categoryByID))


    def lookupCategory(self, name):
        """
            Look up a category by name
        """
        return TradeDB.listSearch("Category", name, self.categoryByID.values(), key=lambda cat: cat.dbname)


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
            item = Item(ID, name, category, '{}/{}'.format(category.dbname, name), None)
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
            assert not altName in itemByName
            aliases += 1
            item = itemByID[itemID]
            item.altname = altName
            itemByName[altName] = item
            if self.debug > 1: print("# '{}' alias for #{} '{}'".format(altName, itemID, item.fullname))

        self.itemByID = itemByID
        self.itemByName = itemByName

        if self.debug > 1:
            print("# Loaded %d Items" % len(self.itemByID))
            print("# Loaded %d AltItemNames" % aliases)


    def lookupItem(self, name):
        """
            Look up an Item by name using "CATEGORY/Item"
        """
        return TradeDB.listSearch("Item", name, self.itemByName.items(), key=lambda kvTup: kvTup[0], val=lambda kvTup: kvTup[1])


    ############################################################
    # Price data.

    def loadTrades(self):
        """
            Populate the "Trades" table for stations.

            A trade is a connection between two stations where the SRC station

            Ignore items that have a ui_order of 0 (my way of indicating the item is
            either unavailable or black market).

            NOTE: Trades MUST be loaded such that they are populated into the
            lists in descending order of profit (highest profit first)
        """

        # I could make a view that does this, but then it makes it fiddly to
        # port this to another database that perhaps doesn't support views.
        stmt = """
                SELECT src.station_id, dst.station_id
                     , src.item_id
                     , src.buy_from
                     , dst.sell_to - src.buy_from AS profit
                     , src.stock, src.stock_level
                     , dst.demand, dst.demand_level
                     , strftime('%s', 'now') - strftime('%s', src.modified) AS src_age
                     , strftime('%s', 'now') - strftime('%s', dst.modified) AS dst_age
                  FROM Price AS src INNER JOIN Price as dst
                        ON src.item_id = dst.item_id
                 WHERE src.buy_from > 0
                        AND profit > 0
                        AND src.stock_level > 0
                        AND dst.demand_level > 0
                        AND src.ui_order > 0
                        AND dst.ui_order > 0
                 ORDER BY profit DESC
                """
        self.cur.execute(stmt)
        stations, items = self.stationByID, self.itemByID
        for (srcStnID, dstStnID, itemID, srcCostCr, profitCr, stock, stockLevel, demand, demandLevel, srcAge, dstAge) in self.cur:
            srcStn, dstStn, item = stations[srcStnID], stations[dstStnID], items[itemID]
            srcStn.addTrade(dstStn, Trade(item, itemID, srcCostCr, profitCr, stock, stockLevel, demand, demandLevel, srcAge, dstAge))


    def getTrade(self, src, dst, item):
        """ Returns a Trade object describing purchase of item from src for sale at dst. """

        # I could write this more compactly, but it makes errors less readable.
        srcStn = self.lookupStation(src)
        dstStn = self.lookupStation(dst)
        return srcStn.tradingWith[dstStn]


    def load(self, dbFilename=None):
        """
            Populate/re-populate this instance of TradeDB with data.
            WARNING: This will orphan existing records you have
            taken references to:
                tdb.load()
                x = tdb.lookupStation("Aulin")
                tdb.load() # x now points to an orphan Aulin
        """

        if self.debug > 1: print("* Loading data")

        conn = self.getDB()
        self.cur = conn.cursor()

        # Load raw tables. Stations will be linked to systems, but nothing else.
        # TODO: Make station -> system link a post-load action.
        self._loadSystems()
        self._loadStations()
        self._loadShips()
        self._loadCategories()
        self._loadItems()

        systems, stations, ships, items = self.systemByID, self.stationByID, self.shipByID, self.itemByID

        # Calculate the maximum distance anyone can jump so we can constrain
        # the maximum "link" between any two stars.
        longestJumper = max(ships.values(), key=lambda ship: ship.maxLyEmpty)
        self.maxSystemLinkLy = longestJumper.maxLyEmpty + 0.01
        if self.debug > 2: print("# Max ship jump distance: %s @ %f" % (longestJumper.name(), self.maxSystemLinkLy))

        self.buildLinks(self.maxSystemLinkLy)

        self.loadTrades()

        # In debug mode, check that everything looks sane.
        if self.debug:
            self._validate()


    def _validate(self):
        # Check that things correctly reference themselves.
        # Check that system links are bi-directional
        for (name, sys) in self.systemByName.items():
            if not sys.links:
                raise ValueError("System %s has no links" % name)
            if sys in sys.links:
                raise ValueError("System %s has a link to itself!" % name)
            if name in sys.links:
                raise ValueError("System %s's name occurs in sys.links" % name)
            for link in sys.links:
                if not sys in link.links:
                    raise ValueError("System %s does not have a reciprocal link in %s's links" % (name, link.str()))


    ############################################################
    # General purpose static methods.

    @staticmethod
    def distanceSq(lhsX, lhsY, lhsZ, rhsX, rhsY, rhsZ):
        """
            Calculate the square of the distance between two points.

            Pythagors theorem: distance = root( (x1-x2)^2 + (y1-y2)^2 + (z1-z2)^2 )

            But calculating square roots is not cheap and if you don't
            need the distance for display, etc, then returning the
            square saves an expensive calculation:

            IF   root(A^2 + B^2 + C^2) == root(D^2 + E^2 + F^2)
            THEN (A^2 + B^2 + C^2) == (D^2 + E^2 + F^2)

            So instead of having to sqrt all of our distances in a complex
            set, we can do this:

            maxDistSq = 300 ** 2   # check for items < 300ly
            inRange = []
            for (lhs, rhs) in items:
                distSq = distanceSq(lhs.x, lhs.y, lhs.z, rhs.x, rhs.y, rhs.z)
                if distSq <= maxDistSq:
                    inRange += [[lhs, rhs]]
        """
        return ((rhsX - lhsX) ** 2) + ((rhsY - lhsY) ** 2) + ((rhsZ - lhsZ) ** 2)


    @staticmethod
    def listSearch(listType, lookup, values, key=lambda item: item, val=lambda item: item):
        """
            Searches [values] for 'lookup' for least-ambiguous matches,
            return the matching value as stored in [values].
            If [values] contains "bread", "water", "biscuits and "It",
            searching "ea" will return "bread", "WaT" will return "water"
            and "i" will return "biscuits". Searching for "a" will raise
            a ValueError because "a" matches "bread" and "water", but
            searching for "it" will return "It" because it provides an
            exact match of a key.
        """

        needle = TradeDB.normalizedStr(lookup)
        matchKey, matchVal = None, None
        for entry in values:
            entryKey = key(entry)
            normVal = TradeDB.normalizedStr(entryKey)
            if normVal.find(needle) > -1:
                # If this is an exact match, ignore ambiguities.
                if normVal == needle:
                    return val(entry)
                if matchVal and matchVal != val(entry):
                    raise AmbiguityError(listType, lookup, matchKey, entryKey)
                matchKey, matchVal = entryKey, val(entry)
        if not matchKey:
            raise LookupError("Error: '%s' doesn't match any %s" % (lookup, listType))
        return matchVal


    @staticmethod
    def normalizedStr(str):
        """
            Returns a case folded, sanitized version of 'str' suitable for
            performing simple and partial matches against. Removes whitespace,
            hyphens, underscores, periods and apostrophes.
        """
        return TradeDB.normalizeRe.sub('', str).casefold()

