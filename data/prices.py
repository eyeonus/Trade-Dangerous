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

######################################################################
# Main

def dumpPrices(dbFilename, withModified=False, stationID=None, file=None, debug=0):
    """ Generate a 'prices' list for the given list of stations using data from the DB. """
    conn = sqlite3.connect(str(dbFilename))     # so we can handle a Path object too
    cur  = conn.cursor()

    systems = { ID: name for (ID, name) in cur.execute("SELECT system_id, name FROM system") }
    stations = { ID: name for (ID, name) in cur.execute("SELECT station_id, name FROM station") }
    categories = { ID: name for (ID, name) in cur.execute("SELECT category_id, name FROM category") }
    items = { ID: name for (ID, name) in cur.execute("SELECT item_id, name FROM item") }

    # find longest item name
    longestName = max(items.values(), key=lambda name: len(name))
    longestNameLen = len(longestName)

    stationClause = "1" if not stationID else "Station.station_id = {}".format(stationID)
    cur.execute("""
        SELECT  Station.system_id
                , Price.station_id
                , Item.category_id
                , Price.item_id
                , Price.sell_to
                , Price.buy_from
                , Price.modified
                , IFNULL(Price.demand, -1)
                , IFNULL(Price.demand_level, -1)
                , IFNULL(Price.stock, -1)
                , IFNULL(Price.stock_level, -1)
          FROM  Station, Item, Category, Price
         WHERE  {}  -- station clause
                AND Station.station_id = Price.station_id
                AND (Item.category_id = Category.category_id) AND Item.item_id = Price.item_id
         ORDER  BY Station.system_id, Station.station_id, Category.name, Price.ui_order, Price.item_id
    """.format(stationClause))
    lastSys, lastStn, lastCat = None, None, None

    if not file: file = sys.stdout
    file.write("# Source for TradeDangerous' price database.\n\n")

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

        file.write("      {:<{width}} {:7d} {:6d}".format(items[itemID], fromStn, toStn, width=longestNameLen))
        if withModified and modified:
            file.write("   {} demand {:>7}L{} stock {:>7}L{}".format(
                        modified,
                        demand,
                        demandLevel,
                        stock,
                        stockLevel
                    ))
        file.write("\n")


if __name__ == "__main__":
    from tradedb import TradeDB
    dumpPrices(TradeDB.defaultDB, withModified=True)
