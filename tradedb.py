#!/usr/bin/env python
# TradeDangerousDB
# Loads system, station, item and trade-price data from the db

######################################################################
# Imports

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

    def getDestinations(self, maxJumps=None, maxLy=None):
        openList, closedList, destStations = Queue(), dict(), []
        openList.put([self.system, 0, 0])
        while not openList.empty():
            (sys, jumps, dist) = openList.get()
            if (maxJumps and jumps > maxJumps) or (maxLy and dist > maxLy):
                continue
            for stn in sys.stations:
                if stn != self:
                    destStations.append([sys, stn, jumps, dist])
            jumps += 1
            if (maxJumps and jumps > maxJumps):
                continue
            for (destSys, destDist) in sys.links.items():
                if maxLy and dist + destDist > maxLy:
                    continue
                if destSys in closedList:
                    continue
                openList.put([destSys, jumps, dist + destDist])
                closedList[destSys] = 1
        return destStations

    def __repr__(self):
        str = self.system.str() + " " + self.station
        return str


class TradeDB(object):
    def __init__(self, path=r'.\TradeDangerous.accdb'):
        self.path = "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + path
        self.load()

    def load(self, avoiding=[], ignoreLinks=False):
        # Connect to the database
        conn = pypyodbc.connect(self.path)
        cur = conn.cursor()

        cur.execute('SELECT system FROM Stations GROUP BY system')
        self.systems = { row[0]: System(row[0]) for row in cur }
        cur.execute("""SELECT frmSys.system, toSys.system
                     FROM Stations AS frmSys, Links, Stations as toSys
                     WHERE frmSys.ID = Links.from AND toSys.ID = Links.to""")
        for row in cur:
            self.systems[row[0]].addLink(self.systems[row[1]], 1)

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
        self.itemIDs = { self.items[name]: name for name in self.items }

        stations, items = self.stations, self.items

        """ Populate the station list with the profitable trades between stations """
        cur.execute('SELECT src.station_id, dst.station_id, src.item_id, src.buy_cr, dst.sell_cr - src.buy_cr'
                    ' FROM Prices AS src INNER JOIN Prices AS dst ON src.item_id = dst.item_id'
                    ' WHERE src.buy_cr > 0 AND dst.sell_cr > src.buy_cr'
                    ' AND src.ui_order > 0 AND dst.ui_order > 0'
                    ' ORDER BY (dst.sell_cr - src.buy_cr) DESC')
        for row in cur:
            if not (items[row[2]] in avoiding):
                stations[row[0]].addTrade(stations[row[1]], items[row[2]], row[2], row[3], row[4])

        for station in stations.values():
            station.organizeTrades()

    def getStation(self, name):
        if isinstance(name, Station):
            return name
        upperName = name.upper()
        if upperName in self.systemIDs:
            return self.stations[self.systemIDs[upperName]]
        elif upperName in self.stationIDs:
            return self.stations[self.stationIDs[upperName]]
        raise ValueError("Unrecognized system/station name '%s'" % name)

    def query(self, sql):
        conn = pypyodbc.connect(self.path)
        cur = conn.cursor()
        cur.execute(sql)
        return cur

    def fetch_all(self, sql):
        for row in self.query(sql):
            yield row

    def list_search(listType, lookup, values):
        match = None
        needle = lookup.casefold()
        for val in values:
            if val.casefold().find(needle) > -1:
                if match:
                    raise ValueError("Ambiguity: %s '%s' could match %s or %s" % (
                                        listType, lookup, match, val))
                match = val
        if not match:
            raise ValueError("Error: '%s' doesn't match any %s" % (lookup, listType))
        return match
