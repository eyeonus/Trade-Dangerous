#!/usr/bin/env python
# TradeDangerousDB
# Loads system, station, item and trade-price data from the db

######################################################################
# Imports

import sys
import pypyodbc
from queue import Queue

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
        print(self.item, self.itemID, self.costCr, self.gainCr, self.value)

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
        self.ID, self.system, self.station = ID, system, station.replace(' ', '')
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

    def getDestinations(self, maxJumps=None, maxLy=None, maxLyPer=None):
        openList, closedList, destStations = Queue(), dict(), []
        openList.put([self.system, [], 0])
        maxJumpDist = float(maxLyPer or sys.maxint)
        while not openList.empty():
            (sys, jumps, dist) = openList.get()
            if maxJumps and len(jumps) - 1 > maxJumps:
                continue
            if maxLy and dist > maxLy:
                continue
            jumps = list(jumps + [sys])
            for stn in sys.stations:
                if stn != self:
                    destStations.append([sys, stn, jumps, dist])
            if (maxJumps and len(jumps) >= maxJumps):
                continue
            for (destSys, destDist) in sys.links.items():
                if destDist > maxJumpDist:
                    continue
                if maxLy and dist + destDist > maxLy:
                    continue
                if destSys in closedList:
                    continue
                openList.put([destSys, jumps, dist + destDist])
                closedList[destSys] = 1
        return destStations

    def str(self):
        return self.system.str().upper() + " " + self.station

    def __repr__(self):
        return str()


class TradeDB(object):
    def __init__(self, path=r'.\TradeDangerous.accdb', debug=0):
        self.path = "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + path
        self.debug = debug
        self.load()

    def load(self, avoiding=[], ignoreLinks=False):
        # Connect to the database
        conn = pypyodbc.connect(self.path)
        cur = conn.cursor()

        cur.execute('SELECT system FROM Stations GROUP BY system')
        self.systems = { row[0]: System(row[0]) for row in cur }
        if self.debug:
            print(self.systems)
        cur.execute("""SELECT frmSys.system, toSys.system, Links.distLy
                     FROM Stations AS frmSys, Links, Stations as toSys
                     WHERE frmSys.ID = Links.from AND toSys.ID = Links.to""")
        for row in cur:
            self.systems[row[0]].addLink(self.systems[row[1]], float(row[2] or 5))

        cur.execute('SELECT id, system, station FROM Stations')
        # Station lookup by ID
        self.stations = { row[0]: Station(row[0], self.systems[row[1]], row[2]) for row in cur }
        # StationID lookup by System Name
        self.systemIDs = { value.system.str().upper(): key for (key, value) in self.stations.items() }
        # StationID lookup by Station Name
        self.stationIDs = { value.station.upper(): key for (key, value) in self.stations.items() }

        """ Populate 'items' from the database """
        cur.execute('SELECT id, item FROM Items')
        self.items = { row[0]: row[1] for row in cur }
        self.itemIDs = { name: itemID for (itemID, name) in self.items.items() }

        stations, items = self.stations, self.items

        """ Populate the station list with the profitable trades between stations """
        cur.execute('SELECT src.station_id, dst.station_id, src.item_id, src.buy_cr, dst.sell_cr - src.buy_cr'
                    ' FROM Prices AS src INNER JOIN Prices AS dst ON src.item_id = dst.item_id'
                    ' WHERE src.buy_cr > 0 AND dst.sell_cr > src.buy_cr'
                    ' AND src.ui_order > 0 AND dst.ui_order > 0'
                    )
        for row in cur:
            if not (items[row[2]] in avoiding):
                stations[row[0]].addTrade(stations[row[1]], items[row[2]], row[2], row[3], row[4])

        for station in stations.values():
            station.organizeTrades()

        if self.debug:
            self.validate()

    def validate(self):
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
        """ Look up a system by it's name. """
        if isinstance(name, System):
            return name
        if isinstance(name, Station):
            return name.system

        system = self.list_search("System", name, self.systems.keys())
        return self.systems[system]

    def getStation(self, name):
        """ Look up a station by it's station or system name. """
        if isinstance(name, Station):
            return name
        if isinstance(name, System):
            # If they provide a system and it only has one station, return that.
            if len(name.stations) != 1:
                raise ValueError("System '%s' has %d stations, please specify a station instead." % (name.str(), len(name.stations)))
            return name.stations[0]

        stationID, systemID = None, None
        try:
            systemID = self.list_search("System", name, self.systems.keys())
        except LookupError:
            pass
        try:
            station = self.list_search("Station", name, self.stationIDs.keys())
            stationID = self.stationIDs[station]
        except LookupError:
            pass
        # If neither matched, we have a lookup error.
        if not (stationID or systemID):
            raise LookupError("'%s' did not match any station or system." % (name))

        # If we matched both a station and a system, make sure they resovle to the
        # the same station otherwise we have an ambiguity. Some stations have the
        # same name as their star system (Aulin/Aulin Enterprise)
        if systemID and stationID and systemID != stationID:
            raise ValueError("Ambiguity: '%s' could be '%s' or '%s'")

        if stationID:
            return self.stations[stationID]

        # If we only matched a system name, ensure that it's a single station system
        # otherwise they need to specify a station name.
        system = self.systems[systemID]
        if len(system.stations) != 1:
            raise ValueError("System '%s' has %d stations, please specify a station instead." % (name, len(system.stations)))
        return system.stations[0]


    def query(self, sql):
        conn = pypyodbc.connect(self.path)
        cur = conn.cursor()
        cur.execute(sql)
        return cur


    def fetch_all(self, sql):
        for row in self.query(sql):
            yield row


    def list_search(self, listType, lookup, values):
        match = None
        needle = lookup.casefold().replace(" ", "").casefold()
        for val in values:
            if val.casefold().replace(" ", "").find(needle) > -1:
                if match:
                    raise ValueError("Ambiguity: %s '%s' could match %s or %s" % (
                                        listType, lookup, match, val))
                match = val
        if not match:
            raise LookupError("Error: '%s' doesn't match any %s" % (lookup, listType))
        return match
