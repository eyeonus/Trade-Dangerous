#!/usr/bin/env python
#---------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
#---------------------------------------------------------------------
#
# This is a work-in-progress script that allows you to use some of
# TDs functionality from inside a python interpreter such as IDLE or
# just python itself.


from tradedb import *
from tradecalc import *

tdb = TradeDB(".\\TradeDangerous.accdb")
calc = TradeCalc(tdb, capacity=16, margin=0.01, unique=False)
curStation = None
curCredits = 1000

def at(station):
    global curStation
    curStation = tdb.lookupStation(station)

def cr(n):
    global curCredits
    curCredits = int(n)

def cap(n):
    global calc
    calc.capacity = int(n)

def run(dst=None, stn=None, cr=None, cap=None, maxJumps=None, maxLy=None):
    global calc
    srcStn = stn if stn else curStation
    withCr = cr if cr else curCredits
    if not dst:
        return calc.getBestHopFrom(srcStn, withCr, capacity=cap, maxJumps=None, maxLy=None)
    dstStn = dst if isinstance(dst, Station) else tdb.lookupStation(dst)
    print(srcStn, dstStn, withCr, cap)
    return calc.getBestTrade(srcStn, dstStn, withCr, capacity=cap, maxJumps=maxJumps, maxLy=maxLy)

def links(stn=None, maxJumps=None, maxLy=None):
    srcStn = stn if stn else curStation
    if not srcStn:
        print("You don't have a station selected. Use at('name') or links(stn='name')")
        return None
    if isinstance(srcStn, str):
        srcStn = tdb.lookupStation(srcStn)
    return srcStn.stations.getDestinations(maxJumps=maxJumps, maxLy=maxLy)

def routes(maxHops=2, stn=None, cr=None, maxJumps=None, maxLy=None, maxRoutes=1, maxJumpsPer=None, maxLyPer=8):
    global calc
    srcStn = stn if stn else curStation
    withCr = cr if cr else curCredits
    routes = [ Route([srcStn], [], withCr, 0, 0) ]

    print("From %s via %s to %s with %d credits for %d hops" % (srcStn, "None", "Any", withCr, maxHops))

    for hopNo in range(maxHops):
        if calc.debug: print("# Hop %d" % hopNo)
        restrictTo = None
        # if hopNo == 0 and viaStation:
        #     restrictTo = viaStation
        # elif hopNo == lastHop:
        #     restrictTo = finalStation
        #     if viaStation:
        #         # Cull to routes that include the viaStation
        #         routes = [ route for route in routes if viaStation in route.route[1:] ]
        routes = calc.getBestHops(routes, withCr, restrictTo=restrictTo, maxJumps=maxJumps, maxJumpsPer=maxJumpsPer, maxLy=maxLy, maxLyPer=maxLyPer)

    if not routes:
        print("No routes match your selected criteria.")
        return

    routes.sort()

    for i in range(0, min(len(routes), maxRoutes)):
        print(routes[i])

def find(item, stn=None):
    srcStn = tdb.lookupStation(stn if stn else curStation)
    qry = """
        SELECT  p.station_id, p.buy_cr
          FROM  Items AS i
                INNER JOIN Prices AS p
                    ON i.ID = P.item_id
         WHERE  i.item LIKE '%%%s%%'
                AND p.buy_cr > 0 
                AND p.ui_order > 0
         ORDER  BY buy_cr ASC
         """ % item
    prices = [ row for row in tdb.fetch_all(qry) ]
    if not prices:
        raise ValueError("No items match '%s'" % item)
    dests = { dest[1].ID: dest for dest in srcStn.getDestinations() }
    if not prices[0][0] in dests:
        raise ValueError("No connecting stations found")
    cheapest = dests[prices[0][0]]
    print("Cheapest: %s: %dcr, %djumps, %dly" % (cheapest[1], prices[0][1], cheapest[2], cheapest[3]))
    best, bestCr, bestJumps, bestLy = None, 0, 0, 0
    for price in prices:
        stnID = price[0]
        if not stnID in dests:
            continue
        dest = dests[stnID]
        if not best or (price[1] < bestCr or (price[1] >= bestCr - 16 and dest[2] < bestJumps)):
            best, bestCr, bestJumps, bestLy = dest[1], price[1], dest[2], dest[3]
    if best:
        print("Closest: %s: %dcr, %djumps, %dly" % (best, bestCr, bestJumps, bestLy))

def sql(sqlQuery, formatStr):
    lines = map(lambda row: formatStr.format(*row), tdb.fetch_all(sqlQuery))
    print("\n".join(lines))

def avgSale(*args):
    whereClause = ' OR '.join(["i.item LIKE '%%%s%%'" % item for item in args])
    sql('SELECT i.item, avg(p.sell_cr)'
            ' FROM Items AS i'
                ' INNER JOIN Prices as p'
                    ' ON i.id = p.item_id'
            ' WHERE %s'
            ' GROUP BY i.item'
            ' ORDER BY 2 DESC'
                 % whereClause
        , "{:.<50} {:9.0f}"
            )

def bestSale(*args):
    whereClause = ' OR '.join(["i.item LIKE '%%%s%%'" % item for item in args])
    sql('SELECT i.item & \' @ \' & s.system & \'/\' & s.station, p.sell_cr'
            ' FROM ((Items AS i'
                ' INNER JOIN Prices as p'
                    ' ON i.id = p.item_id)'
                    ' INNER JOIN Stations as s'
                        ' ON s.id = p.station_id)'
            ' WHERE (%s) AND p.sell_cr = (SELECT MAX(ip.sell_cr) FROM Prices ip WHERE ip.item_id = p.item_id)'
            ' ORDER BY 2 DESC'
                 % whereClause
        , "{:.<50} {:9.0f}cr"
            )

def avgCost(*args):
    whereClause = ' OR '.join(["i.item LIKE '%%%s%%'" % item for item in args])
    sql('SELECT i.item, avg(p.buy_cr)'
            ' FROM Items AS i'
                ' INNER JOIN Prices as p'
                    ' ON i.id = p.item_id'
            ' WHERE %s'
            ' GROUP BY i.item'
            ' ORDER BY 2 DESC'
                 % whereClause
        , "{:.<50} {:9.0f}"
            )

def bestCost(*args):
    whereClause = ' OR '.join(["i.item LIKE '%%%s%%'" % item for item in args])
    sql('SELECT i.item & \' @ \' & s.system & \'/\' & s.station, p.buy_cr'
            ' FROM ((Items AS i'
                ' INNER JOIN Prices as p'
                    ' ON i.id = p.item_id)'
                    ' INNER JOIN Stations as s'
                        ' ON s.id = p.station_id)'
            ' WHERE (%s) AND p.buy_cr = (SELECT MAX(ip.buy_cr) FROM Prices ip WHERE ip.item_id = p.item_id)'
            ' ORDER BY 2 DESC'
                 % whereClause
        , "{:.<50} {:9.0f}cr"
            )
