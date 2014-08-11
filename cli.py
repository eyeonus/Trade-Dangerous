#!/usr/bin/env python

from tradedb import *
from tradecalc import *

tdb = TradeDB(".\\TradeDangerous.accdb")
calc = TradeCalc(tdb, capacity=16, margin=0.01, unique=False)
curStation = None
curCredits = 1000

def at(station):
    global curStation
    curStation = tdb.getStation(station)

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
    dstStn = dst if isinstance(dst, Station) else tdb.getStation(dst)
    print(srcStn, dstStn, withCr, cap)
    return calc.getBestTrade(srcStn, dstStn, withCr, capacity=cap, maxJumps=maxJumps, maxLy=maxLy)

def links(stn=None, maxJumps=None, maxLy=None):
    srcStn = stn if stn else curStation
    if not srcStn:
        print("You don't have a station selected. Use at('name') or links(stn='name')")
        return None
    if isinstance(srcStn, str):
        srcStn = tdb.getStation(srcStn)
    return srcStn.stations.getDestinations(maxJumps=maxJumps, maxLy=maxLy)

def routes(maxHops=2, stn=None, cr=None, cap=None, maxJumps=None, maxLy=None, maxRoutes=1, maxJumpsPer=None):
    global calc
    srcStn = stn if stn else curStation
    withCr = cr if cr else curCredits
    routes = [ Route([srcStn], [], withCr, 0, 0) ]
    lastHop = numHops - 1

    print("From %s via %s to %s with %d credits for %d hops" % (srcStn, "None", "Any", withCr, numHops))

    for hopNo in range(numHops):
        if calc.debug: print("# Hop %d" % hopNo)
        restrictTo = None
        # if hopNo == 0 and viaStation:
        #     restrictTo = viaStation
        # elif hopNo == lastHop:
        #     restrictTo = finalStation
        #     if viaStation:
        #         # Cull to routes that include the viaStation
        #         routes = [ route for route in routes if viaStation in route.route[1:] ]
        routes = calc.getBestHops(routes, withCr, restrictTo=restrictTo, maxJumps=maxJumps, maxJumpsPer=maxJumpsPer, maxLy=maxLy)

    if not routes:
        print("No routes match your selected criteria.")
        return

    routes.sort()

    for i in range(0, min(len(routes), maxRoutes)):
        print(routes[i])
