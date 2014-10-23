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

def dumpPrices(dbFilename, withModified=False, stationID=None, file=None, defaultZero=False, debug=0):
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

    if stationID:
        # check if there are prices for the station
        cur.execute("SELECT COUNT(*) FROM Price WHERE Price.station_id = {}".format(stationID))
        priceCount = cur.fetchone()[0]
        # generate new timestamp in the select
        modifiedStamp = "CURRENT_TIMESTAMP"
    else:
        # no station, no check
        priceCount = 1
        # use old timestamp for the export
        modifiedStamp = "Price.modified"

    stationClause = "1" if not stationID else "Station.station_id = {}".format(stationID)
    defaultDemandVal = 0 if defaultZero else -1
    if priceCount == 0:
        # no prices, generate an emtpy one with all items
        cur.execute("""
            SELECT  Station.system_id, Station.station_id, Item.category_id, Item.item_id,
                    0, 0, CURRENT_TIMESTAMP,
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
                    , {modStamp}  -- real or current timestamp
                    , IFNULL(Price.demand, {defDemand})
                    , IFNULL(Price.demand_level, {defDemand})
                    , IFNULL(Price.stock, {defDemand})
                    , IFNULL(Price.stock_level, {defDemand})
              FROM  Station, Item, Category, Price
             WHERE  {stationClause}  -- station clause
                    AND Station.station_id = Price.station_id
                    AND (Item.category_id = Category.category_id) AND Item.item_id = Price.item_id
             ORDER  BY Station.system_id, Station.station_id, Category.name, Price.ui_order, Item.name
        """.format(modStamp=modifiedStamp, stationClause=stationClause, defDemand=defaultDemandVal))

    lastSys, lastStn, lastCat = None, None, None

    if not file: file = sys.stdout

    if stationID:
        file.write("# TradeDangerous prices for {}\n".format(stations[stationID]))
    else:
        file.write("# TradeDangerous prices for ALL Systems/Stations\n")
    file.write("\n")

    file.write("# The order items are listed in is saved to the DB,\n")
    file.write("# feel free to move items around within their categories.\n")
    file.write("\n")

    if not withModified:
        file.write("# <item name> <sell> <buy>\n")
    else:
        file.write("# <item name> <sell> <buy> <timestamp> demand <demand#>L<level> stock <stock#>L<level>\n")
        file.write("#  demand#/stock#: the quantity available or -1 for 'unknown'")
        file.write("#  level: 0 = None, 1 = Low, 2 = Medium, 3 = High, -1 = Unknown\n")
    file.write("\n")

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
            if defaultZero:
                if demand == -1 and demandLevel == -1:
                    demand      = 0
                    demandLevel = 0
                if stock == -1 and stockLevel == -1:
                    stock      = 0
                    stockLevel = 0
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
