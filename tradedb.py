#!/usr/bin/env python
# TradeDangerousDB
# Loads system, station, item and trade-price data from the db

######################################################################
# Imports

import pypyodbc

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


class Station(object):
    """ Describes a station and which stations it links to, the links themselves
        also describe what products can be sold to the destination and how much
        profit can be earned by doing so. These are stored in gain order so that
        we can easily tell if we can afford to fill up on the most expensive
        item. """
    def __init__(self, ID, system, station):
        self.ID, self.system, self.station = ID, system.replace(' ', ''), station.replace(' ', '')
        self.links = {}
        self.stations = []

    def addTrade(self, dest, item, itemID, costCr, gainCr):
        """ Add a Trade entry from this to a destination station. """
        dstID = dest.ID
        if not dstID in self.links:
            self.links[dstID] = []
            self.stations.append(dest)
        trade = Trade(item, itemID, costCr, gainCr)
        self.links[dstID].append(trade)

    def organizeTrades(self):
        """ Process the trades-to-destination lists: If there are multiple items
            with the same gain for a given link, only keep the cheapest. Then
            sort the list into by-gain order. """
        for dstID in self.links:
            items = self.links[dstID]
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
            self.links[dstID] = sorted([item for item in gains.values()], key=lambda trade: trade.gainCr, reverse=True)

    def __repr__(self):
        str = self.system + " " + self.station
        return str


class TradeDB(object):
    def __init__(self, path="TradeDangerous.accdb"):
        self.path = "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + path
        self.load()

    def load(self, avoiding=[], ignoreLinks=False):
        # Connect to the database
        conn = pypyodbc.connect(self.path)
        cur = conn.cursor()

        cur.execute('SELECT id, system, station FROM Stations')
        # Station lookup by ID
        self.stations = { row[0]: Station(row[0], row[1], row[2]) for row in cur}
        # StationID lookup by System Name
        self.systemIDs = { value.system.upper(): key for (key, value) in self.stations.items() }
        # StationID lookup by Station Name
        self.stationIDs = { value.station.upper(): key for (key, value) in self.stations.items() }

        """ Populate 'items' from the database """
        cur.execute('SELECT id, item FROM Items')
        self.items = { row[0]: row[1] for row in cur }
        self.itemIDs = { self.items[name]: name for name in self.items }

        stations, items = self.stations, self.items

        """ Populate the station list with the profitable trades between stations """
        if not ignoreLinks:
            cur.execute('SELECT src.station_id, dst.station_id, src.item_id, src.buy_cr, dst.sell_cr - src.buy_cr'
                        ' FROM Links AS l, Prices AS src, Prices AS dst'
                        ' WHERE l.from = src.station_id AND l.to = dst.station_id AND src.item_id = dst.item_id'
                        ' AND src.buy_cr > 0 AND dst.sell_cr > src.buy_cr'
                        ' AND src.ui_order > 0 AND dst.ui_order > 0'
                        ' ORDER BY (dst.sell_cr - src.buy_cr) DESC')
        else:
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