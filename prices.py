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
    blanks    = (1 <<31)


######################################################################
# Main

def dumpPrices(
            dbPath,             # Path() or str
            elementMask,        # which columns to output
            stationID=None,     # limits to one station
            file=None,          # file handle to write to
            defaultZero=False,
            debug=0
    ):
    """
        Generate a prices list using data from the DB.
        If stationID is not none, only the specified station is dumped.
        If file is not none, outputs to the given file handle.
    """

    withTimes  = (elementMask & Element.timestamp)
    getBlanks  = (elementMask & Element.blanks)

    conn = sqlite3.connect(str(dbPath))
    conn.execute("PRAGMA foreign_keys=ON")
    cur  = conn.cursor()

    systems = { ID: name for (ID, name) in cur.execute("SELECT system_id, name FROM System") }
    stations = {
            ID: [ name, systems[sysID] ]
                for (ID, name, sysID)
                in cur.execute("SELECT station_id, name, system_id FROM Station")
    }
    categories = { ID: name for (ID, name) in cur.execute("SELECT category_id, name FROM Category") }
    items = {
            ID: [ name, catID, categories[catID] ]
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
        if not cur.fetchone()[0]:
            getBlanks = True

    defaultDemandVal = 0 if defaultZero else -1
    if stationID:
        stationWhere = "WHERE stn.station_id = {}".format(stationID)
    else:
        stationWhere = ""

    if getBlanks:
        itemJoin = "LEFT OUTER"
        ordering = "itm.name"
    else:
        itemJoin = "INNER"
        ordering = "si.ui_order, itm.name"

    cur.execute("SELECT CURRENT_TIMESTAMP")
    now = cur.fetchone()[0]

    stmt = """
        SELECT  stn.station_id, itm.item_id
                , IFNULL(sb.price, 0)
                , IFNULL(ss.price, 0)
                , si.modified
                , IFNULL(sb.units, {defDemand})
                , IFNULL(sb.level, {defDemand})
                , IFNULL(ss.units, {defDemand})
                , IFNULL(ss.level, {defDemand})
          FROM  Station stn,
                Category AS cat
                INNER JOIN Item AS itm USING (category_id)
                {itemJoin} JOIN StationItem AS si
                    ON (si.station_id = stn.station_id
                        AND si.item_id = itm.item_id)
                LEFT OUTER JOIN StationBuying AS sb
                    ON (si.station_id = sb.station_id
                        AND si.item_id = sb.item_id)
                LEFT OUTER JOIN StationSelling AS ss
                    ON (si.station_id = ss.station_id
                        AND si.item_id = ss.item_id)
                {stationWhere}
         ORDER  BY stn.station_id, cat.name, {ordering}
    """

    sql = stmt.format(
            stationWhere=stationWhere,
            defDemand=defaultDemandVal,
            itemJoin=itemJoin,
            ordering=ordering,
            )
    if debug:
        print(sql)
    cur.execute(sql)

    lastSys, lastStn, lastCat = None, None, None

    if not file: file = sys.stdout

    if stationID:
        stationSet = str(stations[stationID])
    else:
        stationSet = "ALL Systems/Stations"

    file.write(
            "# TradeDangerous prices for {}\n"
            "\n"
            "# REMOVE ITEMS THAT DON'T APPEAR IN THE UI\n"
            "# ORDER IS REMEMBERED: Move items around within categories "
                "to match the game UI\n"
            "\n"
            "# File syntax:\n"
            "# <item name> <sell> <buy> [<demand> <stock> [<timestamp>]]\n"
            "#   Use '?' for demand/stock when you don't know/care,\n"
            "#   Use '-' for demand/stock to indicate unavailable,\n"
            "#   Otherwise use a number followed by L, M or H, e.g.\n"
            "#     1L, 23M or 30000H\n"
            "# If you omit the timestamp, the current time will be used when "
                "the file is loaded.\n"
            "\n".format(
                stationSet
            ))

    levelDesc = "?0LMH"
    maxCrWidth = 7
    levelWidth = 9

    outFmt = (
                "      {{:<{width}}}"
                " {{:>{crwidth}}}"
                " {{:>{crwidth}}}"
                "  {{:>{lvlwidth}}}"
                " {{:>{lvlwidth}}}".format(
                    width=longestNameLen,
                    crwidth=maxCrWidth,
                    lvlwidth=levelWidth,
                )
            )
    if withTimes:
        outFmt += "  {}"
    outFmt += "\n"
    output = outFmt.format(
                "Item Name",
                "SellCr", "BuyCr",
                "Demand", "Stock",
                "Timestamp",
            )
    file.write('#' + output[1:])

    naIQL = "-"
    unkIQL = "?"
    defIQL = "?" if not defaultZero else "-"

    output = ""
    for (stnID, itemID, fromStn, toStn, modified, demand, demandLevel, stock, stockLevel) in cur:
        modified = modified or now
        station, system = stations[stnID]
        item, catID, category = items[itemID]
        if stnID != lastStn:
            file.write(output)
            output = "\n\n@ {}/{}\n".format(system.upper(), station)
            lastStn = stnID
            lastCat = None

        if catID is not lastCat:
            output += "   + {}\n".format(category)
            lastCat = catID

        # Is this item on sale?
        if toStn > 0:
            # Zero demand-price gets default demand, which will
            # be either unknown or zero depending on -0.
            # If there is a price, always default to unknown
            # because it can be sold here but the demand is just
            # not useful as data.
            demandStr = defIQL if fromStn <= 0 else unkIQL
            if stockLevel == 0:
                stockStr = naIQL
            elif stockLevel < 0 and stock <= 0:
                stockStr = defIQL
            else:
                units = "?" if stock < 0 else str(stock)
                level = levelDesc[stockLevel + 1]
                stockStr = units + level
        else:
            if demandLevel == 0:
                demandStr = naIQL
            elif demandLevel < 0 and demand <= 0:
                demandStr = defIQL
            else:
                units = "?" if demand < 0 else str(demand)
                level = levelDesc[demandLevel + 1]
                demandStr = units + level
            stockStr = naIQL
        output += outFmt.format(
                    item,
                    fromStn, toStn,
                    demandStr, stockStr,
                    modified
                )

    file.write(output)

if __name__ == "__main__":
    from tradedb import TradeDB
    dumpPrices(TradeDB.defaultDB, elementMask=Element.full)
