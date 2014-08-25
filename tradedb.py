#!/usr/bin/env python
# TradeDangerous :: Modules :: Database Module
# TradeDangerous Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#   You are free to use, redistribute, or even print and eat a copy of this
#   software so long as you include this copyright notice. I guarantee that
#   there is at least one bug neither of us knew about.
#
# Provides classes that load and describe the TradeDangerous data set.
# Currently depends on pypyodbc and Microsoft Access 2010+ drivers,
# but I'll switch to a more portable format soon.

######################################################################
# Imports

import re                   # Because irregular expressions are dull
import pypyodbc             # Because its documentation was better
import sys
from queue import Queue     # Because we're British.
from collections import namedtuple

######################################################################
# Classes

class AmbiguityError(Exception):
    """
        Raised when a search key could match multiple entities.
        Attributes:
            searchKey - the key given to the search routine,
            first     - the first potential match
            second    - the alternate match
    """
    def __init__(self, lookupType, searchKey, first, second):
        self.lookupType, self.searchKey, self.first, self.second = lookupType, searchKey, first, second
    def __str__(self):
        return '%s lookup: "%s" could match either "%s" or "%s"' % (self.lookupType, str(self.searchKey), str(self.first), str(self.second))


class Trade(object):
    """
        Describes what it would cost and how much you would gain
        when selling an item between two specific stations.
    """
    # TODO: Replace with a class within Station that describes asking and paying.
    def __init__(self, item, itemID, costCr, gainCr):
        self.item = item
        self.itemID = itemID
        self.costCr = costCr
        self.gainCr = gainCr

    def describe(self):
        print(self.item, self.itemID, self.costCr, self.gainCr)

    def __repr__(self):
        return "%s (%dcr)" % (self.item, self.costCr)


class System(object):
    """
        Describes a star system, which may contain one or more Station objects,
        and lists which stars it has a direct connection to.
    """
    # TODO: Build the links from an SQL query, it'll save a lot of
    # expensive python dictionary lookups.

    def __init__(self, ID, system, posX, posY, posZ):
        self.ID, self.system, self.posX, self.posY, self.posZ = ID, system, posX, posY, posZ
        self.links = {}
        self.stations = []

    def addLink(self, dest, dist):
        self.links[dest] = dist

    def links(self):
        return list(self.links.keys())

    def addStation(self, station):
        if not station in self.stations:
            self.stations.append(station)

    def name(self):
        return self.system.upper()

    def str(self):
        return self.system

    def __repr__(self):
        return "<System: {}, {}, {}, {}, {}>".format(self.ID, self.system, self.posX, self.posY, self.posZ)


class Station(object):
    """
        Describes a station within a given system along with what trade
        opportunities it presents.
    """

    def __init__(self, ID, system, station, lsFromStar=0.0):
        self.ID, self.system, self.station, self.lsFromStar = ID, system, station, lsFromStar
        self.trades = {}
        self.stations = []
        system.addStation(self)

    def name(self):
        return self.station

    def addTrade(self, dest, item, itemID, costCr, gainCr):
        """
            Add an entry reflecting that an item can be bought at this
            station and sold for a gain at another.
        """
        # TODO: Something smarter.
        dstID = dest.ID
        if not dstID in self.trades:
            self.trades[dstID] = []
            self.stations.append(dest)
        trade = Trade(item, itemID, costCr, gainCr)
        self.trades[dstID].append(trade)

    def organizeTrades(self):
        """
            Process the trades-to-destination lists: sort the list into by-gain order.
        """
        # TODO: Read them from the DB in this order.
        for tradeList in self.trades.values():
            # sort the list in descending gain order - so the mostprofitable item is listed first.
            tradeList.sort(key=lambda trade: trade.gainCr, reverse=True)

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

        Node = namedtuple('Node', [ 'system', 'via', 'dist' ])

        openList = [ OpenNode(self.system, [], 0) ]
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
                (nodeSys, nodeVia, nodeDist) = (node.system, node.via, node.dist)
                for (destSys, destDist) in sys.links.items():
                    # Range check
                    dist = nodeDist + destDist
                    if dist > maxLyPer: continue
                    try:
                        prevNode = pathList[destSys.ID]
                        # If we already have a shorter path, do nothing
                        if dist >= prevNode.dist: continue
                    except KeyError: pass
                    # Add to the path list
                    pathList[destSys.ID] = Node(dest, nodeVia, dist)
                    # Add to the open list but also include node to the via
                    # list so that it serves as the via list for all next-hops.
                    openList += Node(dest, nodeVia + [dest], dist)

        DestNode = namedtuple('DestNode', [ 'system', 'station', 'via', 'dist' ])

        destStations = []
        # always include the local stations, unless the user has indicated they are
        # avoiding this system. E.g. if you're in Chango but you've specified you
        # want to avoid Chango...
        if not self.system in avoiding:
            for station in self.stations:
                if not station in avoiding:
                    destStations += Node(self, station, [], 0.0)

        avoidStations = [ station for station in avoiding if isinstance(station, Station) ]
        epsiol = sys.float_info.epsilon
        for node in pathList.values():
            if node.dist > epsilon:         # Values indistinguishable from zero are avoidances
                for station in node.system.stations:
                    destStations += Node(node.system, station, node.via, node.dist)

        return destStations

    def name(self):
        return self.station

    def str(self):
        return '%s %s' % (self.system.name(), self.station)

    def __repr__(self):
        return '<Station: {}, {}, {}>'.format(self.ID, self.system.name(), self.name())

class Ship(namedtuple('Ship', [ 'name', 'capacity', 'maxJump', 'maxJumpFull', 'stations' ])):
    pass

class TradeDB(object):
    """
        Encapsulation for the database layer.

        Attributes:
            debug       -   Debugging level for this instance
            dbmodule    -   Reference to the database layer we're using (e.g. sqlite3 or pypyodbc)
            path        -   The URI to the database
            conn        -   The database connection
    """
    normalizeRe = re.compile(r'[ \t\'\"\.\-_]')

    def __init__(self, path='.\\TradeDangerous.sq3', debug=0):
        self.debug = debug
        if re.search("\.(accdb|mdb)", path, flags=re.IGNORECASE):
            try:
                import pypyodbc
                self.dbmodule = pypyodbc
                self.path = "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + path
                self.conn = self.dbmodule.connect(self.path)
            except ImportError as e:
                print("ERROR: Using a Microsoft Access database file for the backend (%s) requires the 'pypyodbc' module. Try 'pip pypyodbc'" % path)
                raise e
            except pypyodbc.Error as e:
                print("ERROR: You're trying to use the Microsoft Access back end for TradeDB which requires that you have the 'Microsoft Access Database Engine 2010 Redistributable' installed (just having Access apparently isn't good enough, because ... Microsoft logic).\n"
                        "Please install the driver from Microsoft's site: http://www.microsoft.com/en-us/download/details.aspx?id=13255")
                raise e
        elif re.search("\.sq3", path, flags=re.IGNORECASE):
            # Ensure the file exists, otherwise sqlite will create a new database.
            try:
                with open(path): pass
            except IOError as e:
                print("%s: error: The database file, '%s', appears to be missing or inaccessible." % (__name__, path))
                raise e
            try:
                import sqlite3
                self.dbmodule = sqlite3
                self.path = path
                self.conn = self.dbmodule.connect(self.path)
            except ImportError as e:
                print("ERROR: You don't appear to have the Python sqlite3 module installed. Impressive. No, wait, the other one: crazy.")
                raise e
        else:
            raise Exception("ERROR: '%s': Unrecognized database type (expecting .sq3 or if you're MSochistic, .accdb or .mdb)." % path)

        self.load()

    def load(self):
        """ Populate/re-populate this instance with data from the TradeDB layer. """
        # Create a cursor.
        cur = self.conn.cursor()

        # Fetch a list of systems.
        cur.execute('SELECT system FROM Stations GROUP BY system')
        systems = self.systems = { row[0]: System(row[0]) for row in cur }

        # Fetch a list of links between systems.
        # TODO: Store positions, calculate distances on demand
        cur.execute("""SELECT frmSys.system, toSys.system, Links.distLy
                     FROM Stations AS frmSys, Links, Stations as toSys
                     WHERE frmSys.ID = Links.from AND toSys.ID = Links.to""")
        for (srcSysID, dstSysID, distLy) in cur:
            srcSys, dstSys = systems[srcSysID], systems[dstSysID]
            srcSys.addLink(dstSys, float(distLy))

        # Fetch the list of stations
        cur.execute('SELECT id, system, station FROM Stations')
        # Station lookup by ID
        self.stations = { row[0]: Station(row[0], self.systems[row[1]], row[2]) for row in cur }
        # StationID lookup by System Name
        self.systemIDs = { value.system.str().upper(): key for (key, value) in self.stations.items() }
        # StationID lookup by Station Name
        self.stationIDs = { value.station.upper(): key for (key, value) in self.stations.items() }

        # Populate 'items' from the database
        cur.execute('SELECT id, item FROM Items')
        self.items = { row[0]: row[1] for row in cur }
        self.itemIDs = { name: itemID for (itemID, name) in self.items.items() }

        stations, items = self.stations, self.items

        # Populate the station list with the profitable trades between stations
        # Ignore items that have a ui_order of 0 in the prices table (my way of marking an item as defunct or illegal)
        cur.execute('SELECT src.station_id, dst.station_id, src.item_id, src.buy_cr, dst.sell_cr'
                    ' FROM Prices AS src INNER JOIN Prices AS dst ON src.item_id = dst.item_id'
                    ' WHERE src.buy_cr > 0 AND dst.sell_cr > src.buy_cr'
                    ' AND src.ui_order > 0 AND dst.ui_order > 0'
                    )
        for (srcID, dstID, itemID, srcCostCr, dstValueCr) in cur:
            srcStn = stations[srcID]
            dstStn = stations[dstID]
            item   = items[itemID]
            srcStn.addTrade(dstStn, item, itemID, srcCostCr, dstValueCr - srcCostCr)

        # Post-process the trades and sort them into whatever order we want them in.
        for station in stations.values():
            station.organizeTrades()

        # In debug mode, check that everything looks sane.
        if self.debug:
            self._validate()

    def _validate(self):
        # Check that things correctly reference themselves.
        for (stnID, stn) in self.stations.items():
            if self.stations[stn.ID] != stn:
                raise ValueError("Station not pointing to self correctly" % stn.station)
        for (stnName, stnID) in self.stationIDs.items():
            if self.stations[stnID].station.upper() != stnName:
                raise ValueError("Station name not pointing to self correctly" % stnName)
        for (itemID, item) in self.items.items():
            if self.itemIDs[item] != itemID:
                raise ValueError("Item %s not pointing to itself correctly" % item, itemID, item, self.itemIDs[item])
        # Check that system links are bi-directional
        for (name, sys) in self.systems.items():
            if not sys.links:
                raise ValueError("System %s has no links" % name)
            if sys in sys.links:
                raise ValueError("System %s has a link to itself!" % name)
            if name in sys.links:
                raise ValueError("System %s's name occurs in sys.links" % name)
            for link in sys.links:
                if not sys in link.links:
                    raise ValueError("System %s does not have a reciprocal link in %s's links" % (name, link.str()))

    def getSystem(self, name):
        """ Look up a System object by it's name. """
        if isinstance(name, System):
            return name
        if isinstance(name, Station):
            return name.system

        system = TradeDB.list_search("System", name, self.systems.keys())
        return self.systems[system]

    def getStation(self, name):
        """ Look up a Station object by it's name or system. """
        if isinstance(name, Station):
            return name
        if isinstance(name, System):
            # If they provide a system and it only has one station, return that.
            if len(name.stations) != 1:
                raise ValueError("System '%s' has %d stations, please specify a station instead." % (name.str(), len(name.stations)))
            return name.stations[0]

        stationID, station, systemID, system = None, None, None, None
        try:
            systemID = TradeDB.list_search("System", name, self.systems.keys())
            system = self.systems[systemID]
        except LookupError:
            pass
        try:
            stationName = TradeDB.list_search("Station", name, self.stationIDs.keys())
            stationID = self.stationIDs[stationName]
            station = self.stations[stationID]
        except LookupError:
            pass
        # If neither matched, we have a lookup error.
        if not (stationID or systemID):
            raise LookupError("'%s' did not match any station or system." % (name))

        # If we matched both a station and a system, make sure they resovle to the
        # the same station otherwise we have an ambiguity. Some stations have the
        # same name as their star system (Aulin/Aulin Enterprise)
        if systemID and stationID and system != station.system:
            raise AmbiguityError('Station', name, system.str(), station.str())

        if stationID:
            return self.stations[stationID]

        # If we only matched a system name, ensure that it's a single station system
        # otherwise they need to specify a station name.
        system = self.systems[systemID]
        if len(system.stations) != 1:
            raise ValueError("System '%s' has %d stations, please specify a station instead." % (name, len(system.stations)))
        return system.stations[0]

    def getShip(self, name):
        """ Look up a ship by name """
        return TradeDB.list_search("Ship", name, self.ships, key=lambda item: item.name)

    def getTrade(self, src, dst, item):
        """ Returns a Trade object describing purchase of item from src for sale at dst. """
        srcStn = self.getStation(src)
        dstStn = self.getStation(dst)
        trades = srcStn.trades[dstStn.ID]
        return trades[item]

    @staticmethod
    def getDistanceSq(lhsX, lhsY, lhsZ, rhsX, rhsY, rhsZ):
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
                distSq = getDistanceSq(lhs.x, lhs.y, lhs.z, rhs.x, rhs.y, rhs.z)
                if distSq <= maxDistSq:
                    inRange += [[lhs, rhs]]
        """
        return ((rhsX - lhsX) ** 2) + ((rhsY - lhsY) ** 2) + ((rhsZ - lhsZ) ** 2)

    def query(self, *args):
        """ Perform an SQL query on the DB and return the cursor. """
        conn = pypyodbc.connect(self.path)
        cur = conn.cursor()
        cur.execute(*args)
        return cur

    def fetch_all(self, sql):
        """ Perform an SQL query on the DB and iterate across the rows. """
        for row in self.query(sql):
            yield row

    @staticmethod
    def list_search(listType, lookup, values, key=lambda item: item):
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

        needle = TradeDB.normalized_str(lookup)
        match = None
        for val in values:
            normVal = TradeDB.normalized_str(key(val))
            if normVal.find(needle) > -1:
                # If this is an exact match, ignore ambiguities.
                if normVal == needle:
                    return val
                if match:
                    raise AmbiguityError(listType, lookup, match, val)
                match = val
        if not match:
            raise LookupError("Error: '%s' doesn't match any %s" % (lookup, listType))
        return match

    @staticmethod
    def normalized_str(str):
        """
            Returns a case folded, sanitized version of 'str' suitable for
            performing simple and partial matches against. Removes whitespace,
            hyphens, underscores, periods and apostrophes.
        """
        return TradeDB.normalizeRe.sub('', str).casefold()
