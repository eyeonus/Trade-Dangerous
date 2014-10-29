#! /usr/bin/env python
#---------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
#---------------------------------------------------------------------
# TradeDangerous :: Modules :: Generate TradeDangerous.prices

import sys
import os
import re
import sqlite3


class Element(object):
    basic     = (1 << 0)
    supply    = (1 << 1)
    timestamp = (1 << 2)
    full      = (basic | supply | timestamp)


######################################################################
# Main

def dumpPrices(dbFilename, elementMask, stationID=None, file=None, defaultZero=False, debug=0):
    """ Generate a 'prices' list for the given list of stations using data from the DB. """

    withSupply = (elementMask & Element.supply)
    withTimes  = (elementMask & Element.timestamp)

    conn = sqlite3.connect(str(dbFilename))     # so we can handle a Path object too
    cur  = conn.cursor()

    systems = { ID: name for (ID, name) in cur.execute("SELECT system_id, name FROM system") }
    stations = { ID: name for (ID, name) in cur.execute("SELECT station_id, name FROM station") }
    categories = { ID: name for (ID, name) in cur.execute("SELECT category_id, name FROM category") }
    items = { ID: name for (ID, name) in cur.execute("SELECT item_id, name FROM item") }

    # find longest item name
    longestName = max(items.values(), key=lambda name: len(name))
    longestNameLen = len(longestName)

    if stationID:
        # check if there are prices for the station
        cur.execute("SELECT COUNT(*) FROM Price WHERE Price.station_id = {}".format(stationID))
        priceCount = cur.fetchone()[0]
    else:
        # no station, no check
        priceCount = 1

    stationClause = "1" if not stationID else "Station.station_id = {}".format(stationID)
    defaultDemandVal = 0 if defaultZero else -1
    if priceCount == 0:
        # no prices, generate an emtpy one with all items
        cur.execute("""
            SELECT  Station.system_id, Station.station_id, Item.category_id, Item.item_id,
                    0, 0, NULL,
                    {defDemand}, {defDemand}, {defDemand}, {defDemand}
               FROM Item LEFT OUTER JOIN Station, Category
              WHERE {stationClause}
                AND Item.category_id = Category.category_id
              ORDER BY Station.system_id, Station.station_id, Category.name, Item.name
        """.format(stationClause=stationClause, defDemand=defaultDemandVal))
    else:
        cur.execute("""
            SELECT  Station.system_id
                    , Price.station_id
                    , Item.category_id
                    , Price.item_id
                    , Price.sell_to
                    , Price.buy_from
                    , Price.modified
                    , IFNULL(Price.demand, {defDemand})
                    , IFNULL(Price.demand_level, {defDemand})
                    , IFNULL(Price.stock, {defDemand})
                    , IFNULL(Price.stock_level, {defDemand})
              FROM  Station, Item, Category, Price
             WHERE  {stationClause}  -- station clause
                    AND Station.station_id = Price.station_id
                    AND (Item.category_id = Category.category_id) AND Item.item_id = Price.item_id
             ORDER  BY Station.system_id, Station.station_id, Category.name, Price.ui_order, Item.name
        """.format(stationClause=stationClause, defDemand=defaultDemandVal))

    lastSys, lastStn, lastCat = None, None, None

    if not file: file = sys.stdout

    if stationID:
        file.write("# TradeDangerous prices for {}\n".format(stations[stationID]))
    else:
        file.write("# TradeDangerous prices for ALL Systems/Stations\n")
    file.write("\n")

    file.write("# REMOVE ITEMS THAT DON'T APPEAR IN THE UI\n")
    file.write("# ORDER IS REMEMBERED: Move items around within categories to match the game UI\n")
    file.write("\n")

    file.write("# File syntax:\n")
    file.write("# <item name> <sell> <buy> [ <demand units><level> <stock units><level> [<timestamp>] ]\n")
    file.write("#   '?' or 'unk' indicates unknown values (don't care),\n")
    file.write("#   '-' or 'n/a' indicates 'not available' item,\n")
    file.write("#   Level can be '?', 'L', 'M' or 'H'\n")
    file.write("# If you omit the timestamp, the current time will be used when the file is loaded.\n")

    file.write("\n")

    levelDescriptions = {
        -1: "?",
         0: "0",
         1: "L",
         2: "M",
         3: "H"
    }
    def itemQtyAndLevel(quantity, level):
        if defaultZero and quantity == -1 and level == -1:
            quantity, level = 0, 0
        if quantity < 0 and level < 0:
            return "?"
        if quantity == 0 and level == 0:
            return "-"
        # Quantity of -1 indicates 'unknown'
        quantityDesc = '?' if quantity < 0 else str(quantity)
        # try to use a descriptive for the level
        try:
            levelDesc = levelDescriptions[int(level)]
        except (KeyError, ValueError):
            levelDesc = str(level)
        return "{}{}".format(quantityDesc, levelDesc)


    maxCrWidth = 7
    levelWidth = 8

    file.write("#     {:<{width}} {:>{crwidth}} {:>{crwidth}}".format("Item Name", "Sell Cr", "Buy Cr", width=longestNameLen, crwidth=maxCrWidth))
    if withSupply:
        file.write("  {:>{lvlwidth}} {:>{lvlwidth}}".format("Demand", "Stock", lvlwidth=levelWidth))
    if withTimes:
        file.write("  {}".format("Timestamp"))
    file.write("\n\n")

    for (sysID, stnID, catID, itemID, fromStn, toStn, modified, demand, demandLevel, stock, stockLevel) in cur:
        system = systems[sysID]
        if system is not lastSys:
            if lastStn: file.write("\n\n")
            lastStn, lastCat = None, None
            lastSys = system

        station = stations[stnID]
        if station is not lastStn:
            if lastStn: file.write("\n")
            lastCat = None
            file.write("@ {}/{}\n".format(system.upper(), station))
            lastStn = station

        category = categories[catID]
        if category is not lastCat:
            file.write("   + {}\n".format(category))
            lastCat = category

        file.write("      {:<{width}} {:{crwidth}d} {:{crwidth}d}".format(items[itemID], fromStn, toStn, width=longestNameLen, crwidth=maxCrWidth))
        if withSupply:
            # Is this item on sale?
            if toStn > 0:
                demandStr = itemQtyAndLevel(-2, -2)
                stockStr  = itemQtyAndLevel(stock, stockLevel)
            else:
                demandStr = itemQtyAndLevel(demand, demandLevel)
                stockStr = itemQtyAndLevel(0, 0)
            file.write("  {:>{lvlwidth}} {:>{lvlwidth}}".format(
                        demandStr,
                        stockStr,
                        lvlwidth=levelWidth,
                    ))
        if withTimes:
            file.write("  {}".format(modified or 'now'))
        file.write("\n")


if __name__ == "__main__":
    from tradedb import TradeDB
    dumpPrices(TradeDB.defaultDB, elementMask=Element.full)
