# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
#---------------------------------------------------------------------
# TradeDangerous :: Modules :: Generate TradeDangerous.prices

from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

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

    systems = { ID: name for (ID, name) in cur.execute("SELECT system_id, name FROM System") }
    stations = {
            ID: [ name, systems[sysID] ]
                for (ID, name, sysID)
                in cur.execute("SELECT station_id, name, system_id FROM Station")
    }
    categories = { ID: name for (ID, name) in cur.execute("SELECT category_id, name FROM Category") }
    items = {
            ID: [ name, categories[catID] ]
                for (ID, name, catID)
                in cur.execute("SELECT item_id, name, category_id FROM Item")
    }

    # find longest item name
    longestName = max(items.values(), key=lambda ent: len(ent[0]))
    longestNameLen = len(longestName[0])

    if stationID:
        # check if there are prices for the station
        cur.execute("""
            SELECT  COUNT(*)
              FROM  StationItem
             WHERE station_id = {}
            """.format(stationID))
        priceCount = cur.fetchone()[0]
    else:
        # no station, no check
        priceCount = 1

    defaultDemandVal = 0 if defaultZero else -1
    if stationID:
        stationWhere = "WHERE stn.station_id = {}".format(stationID)
    else:
        stationWhere = ""
    if priceCount == 0:
        # no prices, generate an emtpy one with all items
        stmt = """
            SELECT  stn.station_id, Item.item_id,
                    0, 0, NULL,
                    {defDemand}, {defDemand}, {defDemand}, {defDemand}
               FROM Station AS stn,
                    Item INNER JOIN Category
                        USING (category_id)
                    {stationWhere}
              ORDER BY Station.system_id, Station.station_id, Category.name, Item.name
        """
    else:
        stmt = """
            SELECT  si.station_id, si.item_id
                    , IFNULL(sb.price, 0)
                    , IFNULL(ss.price, 0)
                    , si.modified
                    , IFNULL(sb.units, {defDemand})
                    , IFNULL(sb.level, {defDemand})
                    , IFNULL(ss.units, {defDemand})
                    , IFNULL(ss.level, {defDemand})
              FROM  Station stn
                    INNER JOIN StationItem AS si USING (station_id)
                    INNER JOIN Item AS itm USING (item_id)
                    INNER JOIN Category AS cat USING (category_id)
                    LEFT OUTER JOIN StationBuying AS sb
                        ON (si.station_id = sb.station_id
                            AND si.item_id = sb.item_id)
                    LEFT OUTER JOIN StationSelling AS ss
                        ON (si.station_id = ss.station_id
                            AND si.item_id = ss.item_id)
                    {stationWhere}
             ORDER  BY stn.station_id, cat.name, si.ui_order, itm.name
        """

    sql = stmt.format(stationWhere=stationWhere, defDemand=defaultDemandVal)
    if debug:
        print(sql)
    cur.execute(sql)

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


    naIQL = itemQtyAndLevel(0, 0)
    unkIQL = itemQtyAndLevel(-2, -2)
    defIQL = itemQtyAndLevel(-1, -1)

    for (stnID, itemID, fromStn, toStn, modified, demand, demandLevel, stock, stockLevel) in cur:
        station, system = stations[stnID]
        if system is not lastSys:
            if lastStn: file.write("\n\n")
            lastStn, lastCat = None, None
            lastSys = system
        if station is not lastStn:
            if lastStn: file.write("\n")
            lastCat = None
            file.write("@ {}/{}\n".format(system.upper(), station))
            lastStn = station

        item, category = items[itemID]
        if category is not lastCat:
            file.write("   + {}\n".format(category))
            lastCat = category

        file.write("      {:<{width}} {:{crwidth}d} {:{crwidth}d}".format(
                item, fromStn, toStn,
                width=longestNameLen, crwidth=maxCrWidth
        ))
        if withSupply:
            # Is this item on sale?
            if toStn > 0:
                # Zero demand-price gets default demand, which will
                # be either unknown or zero depending on -0.
                # If there is a price, always default to unknown
                # because it can be sold here but the demand is just
                # not useful as data.
                demandStr = defIQL if fromStn <= 0 else unkIQL
                stockStr  = itemQtyAndLevel(stock, stockLevel)
            else:
                demandStr = itemQtyAndLevel(demand, demandLevel)
                stockStr = naIQL
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
