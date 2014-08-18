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
from queue import Queue     # Because we're British.

######################################################################
# Classes

class Trade(object):
    """ Describes what it would cost and how much you would gain
        when selling an item between two specific stations. """
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
    """ Describes a star system, which may contain one or more Station objects,
        and lists which stars it has a direct connection to. """

    def __init__(self, system):
        self.system = system
        self.links = {}
        self.stations = []


    def addLink(self, dest, dist):
        self.links[dest] = dist


    def links(self):
        return list(self.links.keys())


    def addStation(self, station):
        if not station in self.stations:
            self.stations.append(station)


    def str(self):
        return self.system


class Station(object):
    """ Describes a station within a given system along with what trade
        opportunities it presents. """

    def __init__(self, ID, system, station):
        self.ID, self.system, self.station = ID, system, station
        self.trades = {}
        self.stations = []
        system.addStation(self)


    def addTrade(self, dest, item, itemID, costCr, gainCr):
        """ Add a Trade entry from this to a destination station. """
        dstID = dest.ID
        if not dstID in self.trades:
            self.trades[dstID] = []
            self.stations.append(dest)
        trade = Trade(item, itemID, costCr, gainCr)
        self.trades[dstID].append(trade)


    def organizeTrades(self):
        """ Process the trades-to-destination lists: If there are multiple items
            with the same gain for a given link, only keep the cheapest. Then
            sort the list into by-gain order. """
        for dstID in self.trades:
            items = self.trades[dstID]
            # Find the cheapest item
            cheapest = min(items, key=lambda item: item.costCr)
            cheapestGain = cheapest.gainCr
            # Pick the cheapest item for each gain.
            gains = dict()
            for item in items:
                itemGainCr = item.gainCr
                if itemGainCr >= cheapestGain:
                    if (not itemGainCr in gains) or (gains[itemGainCr].costCr <= item.costCr):
                        gains[itemGainCr] = item
            # Now sort the list in descending gain order - so the most
            # profitable item is listed first.
            self.trades[dstID] = sorted([item for item in gains.values()], key=lambda trade: trade.gainCr, reverse=True)


    def getDestinations(self, maxJumps=None, maxLy=None, maxLyPer=None, avoiding=None):
        """ Gets a list of the Station destinations that can be reached
            from this Station within the specified constraints.
            If no constraints are specified, you get a list of everywhere
            that this station has a link to in the db where something
            the station sells is bought.
            """

        if not avoiding: avoiding = []

        openList, closedList, destStations = Queue(), [sys for sys in avoiding if isinstance(sys, System)] + [self], []
        openList.put([self.system, [], 0])
        # Sys is always available, so we don't need to import it. maxint was deprecated in favour of maxsize.
        maxJumpDist = float(maxLyPer or sys.maxsize)
        while not openList.empty():
            (sys, jumps, dist) = openList.get()
            if maxJumps and len(jumps) > maxJumps:
                continue
            if maxLy and dist > maxLy:
                continue
            jumps = list(jumps + [sys])
            for stn in sys.stations:
                if not stn in avoiding:
                    destStations.append([sys, stn, jumps, dist])
            if (maxJumps and len(jumps) > maxJumps):
                continue
            for (destSys, destDist) in sys.links.items():
                if destDist > maxJumpDist:
                    continue
                if maxLy and dist + destDist > maxLy:
                    continue
                if destSys in closedList:
                    continue
                openList.put([destSys, jumps, dist + destDist])
                closedList.append(destSys)
        return destStations


    def str(self):
        return self.system.str().upper() + " " + self.station


    def __repr__(self):
        return self.str()


class TradeDB(object):
    normalizeRe = re.compile(r'[ \t\'\"\.\-_]')

    def __init__(self, path=r'.\TradeDangerous.accdb', debug=0):
        self.path = "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + path
        self.debug = debug
        try:
            self.conn = pypyodbc.connect(self.path)
        except pypyodbc.Error as e:
            print("Do you have the requisite driver installed? See http://www.microsoft.com/en-us/download/details.aspx?id=13255")
            raise e
        self.load()

    def load(self, avoidItems=[], avoidSystems=[], avoidStations=[], ignoreLinks=False):
        """ Populate/re-populate this instance with data from the TradeDB layer. """

        # Create a cursor.
        cur = self.conn.cursor()

        # Fetch a list of systems.
        cur.execute('SELECT system FROM Stations GROUP BY system')
        self.systems = { row[0]: System(row[0]) for row in cur if not self.normalized_str(row[0]) in avoidSystems }
        if self.debug:
            print(self.systems)

        # Fetch a list of links between systems.
        # Rather than storing positions, I'm storing the links themselves, but
        # eventually I'll just store the positions instead and calculate the
        # distances as/when I need them.
        cur.execute("""SELECT frmSys.system, toSys.system, Links.distLy
                     FROM Stations AS frmSys, Links, Stations as toSys
                     WHERE frmSys.ID = Links.from AND toSys.ID = Links.to""")
        for row in cur:
            if row[0] in self.systems and row[1] in self.systems:
                self.systems[row[0]].addLink(self.systems[row[1]], float(row[2] or 5))

        # Fetch the list of stations
        cur.execute('SELECT id, system, station FROM Stations')
        # Station lookup by ID
        self.stations = { row[0]: Station(row[0], self.systems[row[1]], row[2]) for row in cur if row[1] in self.systems and not self.normalized_str(row[2]) in avoidStations }
        # StationID lookup by System Name
        self.systemIDs = { value.system.str().upper(): key for (key, value) in self.stations.items() }
        # StationID lookup by Station Name
        self.stationIDs = { value.station.upper(): key for (key, value) in self.stations.items() }

        # Populate 'items' from the database
        cur.execute('SELECT id, item FROM Items')
        self.items = { row[0]: row[1] for row in cur if not self.normalized_str(row[1]) in avoidItems }
        self.itemIDs = { name: itemID for (itemID, name) in self.items.items() }

        stations, items = self.stations, self.items

        # Populate the station list with the profitable trades between stations
        # The DB does a really good job of providing this information quickly and
        # spares us having to load ALL of the data in order to build this view.
        # Yes, the DB has to load it but it's designed to do that efficiently.
        cur.execute('SELECT src.station_id, dst.station_id, src.item_id, src.buy_cr, dst.sell_cr - src.buy_cr'
                    ' FROM Prices AS src INNER JOIN Prices AS dst ON src.item_id = dst.item_id'
                    ' WHERE src.buy_cr > 0 AND dst.sell_cr > src.buy_cr'
                    ' AND src.ui_order > 0 AND dst.ui_order > 0'
                    )
        for row in cur:
            if row[0] in stations and row[1] in stations and row[2] in items:
                stations[row[0]].addTrade(stations[row[1]], items[row[2]], row[2], row[3], row[4])

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

        system = self.list_search("System", name, self.systems.keys())
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
            systemID = self.list_search("System", name, self.systems.keys())
            system = self.systems[systemID]
        except LookupError:
            pass
        try:
            stationName = self.list_search("Station", name, self.stationIDs.keys())
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
            raise ValueError("Ambiguity: '%s' could be '%s' or '%s'" % (name, system.str(), station.str()))

        if stationID:
            return self.stations[stationID]

        # If we only matched a system name, ensure that it's a single station system
        # otherwise they need to specify a station name.
        system = self.systems[systemID]
        if len(system.stations) != 1:
            raise ValueError("System '%s' has %d stations, please specify a station instead." % (name, len(system.stations)))
        return system.stations[0]


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


    def list_search(self, listType, lookup, values):
        """ Seaches [values] for 'lookup' for least-ambiguous matches,
            return the matching value as stored in [values].
            If [values] contains "bread", "water", "biscuits and "It",
            searching "ea" will return "bread", "WaT" will return "water"
            and "i" will return "biscuits". Searching for "a" will raise
            a ValueError because "a" matches "bread" and "water", but
            searching for "it" will return "It" because it provides an
            exact match of a key. """

        match = None
        needle = self.normalized_str(lookup)
        for val in values:
            normVal = self.normalized_str(val)
            if normVal.find(needle) > -1:
                # If this is an exact match, ignore ambiguities.
                if normVal == needle:
                    return val
                if match:
                    raise ValueError("Ambiguity: %s '%s' could match %s or %s" % (
                                        listType, lookup, match, val))
                match = val
        if not match:
            raise LookupError("Error: '%s' doesn't match any %s" % (lookup, listType))
        return match


    def normalized_str(self, str):
        """ Returns a case folded, sanitized version of 'str' suitable for
            performing simple and partial matches against. Removes whitespace,
            hyphens, underscores, periods and apostrophes. """
        return self.normalizeRe.sub('', str).casefold()
