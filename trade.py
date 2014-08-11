#!/usr/bin/env python
#
# We can easily predict the best run from A->B, but the return trip from B->A might
# not give us the best profit.
# The goal here, then, is to find the best multi-hop route.

# Potential Optimization: Two routes with the same dest at the same hop,
# eliminate the one with the lowest score at that hop

######################################################################
# Imports

import argparse

# Forward decls
args = None
originStation, finalStation, viaStation = None, None, None
originName, destName, viaName = "Any", "Any", "Any"
origins = []
maxUnits = 0

######################################################################
# TradeDB and TradeCalc

from tradedb import TradeDB, Trade, Station
from tradecalc import Route, TradeCalc

tdb = TradeDB("C:\\Dev\\trade\\TradeDangerous.accdb")

######################################################################
# Classes

######################################################################

def parse_command_line():
    global args, origins, originStation, finalStation, viaStation, maxUnits, originName, destName, viaName

    parser = argparse.ArgumentParser(description='Trade run calculator')
    parser.add_argument('--from', dest='origin', metavar='<Origin>', help='Specifies starting system/station', required=False)
    parser.add_argument('--to', dest='dest', metavar='<Destination>', help='Specifies final system/station', required=False)
    parser.add_argument('--via', dest='via', metavar='<ViaStation>', help='Require specified station to be en-route', required=False)
    parser.add_argument('--avoid', dest='avoid', metavar='<Item>', help='Exclude this item from trading', required=False, action='append')
    parser.add_argument('--credits', metavar='<Balance>', help='Number of credits to start with', type=int, required=True)
    parser.add_argument('--hops', metavar="<Hops>", help="Number of hops to run", type=int, default=2, required=False)
    parser.add_argument('--jumps', dest='maxJumps', metavar="<Jumps>", help="Maximum total jumps", type=int, default=None, required=False)
    parser.add_argument('--jumps-per', dest='maxJumpsPer', metavar="<Jumps>", help="Maximum jumps per hop", type=int, default=3, required=False)
    parser.add_argument('--ly-per', dest='maxLyPer', metavar='<LY>', help="Maximum light years per jump", type=int, default=8, required=False)
    parser.add_argument('--capacity', metavar="<Capactiy>", help="Maximum capacity of cargo hold", type=int, default=4, required=False)
    parser.add_argument('--limit', help='Maximum units of any one cargo item to buy', type=int, default=0, required=False)
    parser.add_argument('--unique', help='Only visit each station once', default=False, required=False, action='store_true')
    parser.add_argument('--insurance', metavar="<Credits>", help="Reserve at least this many credits", type=int, default=0, required=False)
    parser.add_argument('--margin', metavar="<Error Margin>", help="Reduce gains by this much to provide a margin of error for market fluctuations (e.g. 0.25 reduces gains by 1/4). 0<=m<=0.25. Default: 0.02", default=0.02, type=float, required=False)
    parser.add_argument('--debug', help="Enable verbose output", default=False, required=False, action='store_true')
    parser.add_argument('--routes', metavar="<MaxRoutes>", help="Maximum number of routes to show", type=int, default=1, required=False)

    args = parser.parse_args()

    if args.hops < 1:
        raise ValueError("Minimum of 1 hop required")
    if args.hops > 64:
        raise ValueError("Too many hops without more optimization")

    avoidItems = []
    if args.avoid:
        for avoid in args.avoid:
            if not avoid in tdb.items.values():
                raise ValueError("Unknown item: %s" % avoid)   
            avoidItems.append(avoid)
        if avoidItems:
            if args.debug: print("Avoiding %s" % avoidItems)
            tdb.load(avoiding=avoidItems)

    if args.origin:
        originName = args.origin
        originStation = tdb.getStation(originName)
        origins = [ originStation ]
    else:
        origins = [ station for station in tdb.stations.values() ]

    if args.dest:
        destName = args.dest
        finalStation = tdb.getStation(destName)
        if args.hops == 1 and originStation and finalStation and originStation == finalStation:
            raise ValueError("More than one hop required to use same from/to destination")

    if args.via:
        if args.hops < 2:
            raise ValueError("Minimum of 2 hops required for a 'via' route")
        viaName = args.via
        viaStation = tdb.getStation(viaName)
        if args.hops == 2:
            if viaStation == originStation:
                raise ValueError("3+ hops required to go 'via' the origin station")
            if viaStation == finalStation:
                raise ValueError("3+ hops required to go 'via' the destination station")
        if args.hops <= 3:
            if viaStation == originStation and viaStation == finalStation:
                raise ValueError("4+ hops required to go 'via' the same station as you start and end at")

    if args.credits < 0:
        raise ValueError("Invalid (negative) value for initial credits")

    if args.capacity < 0:
        raise ValueError("Invalid (negative) cargo capacity")

    if args.limit and args.limit > args.capacity:
        raise ValueError("'limit' must be <= capacity")
    if args.limit and args.limit < 0:
        raise ValueError("'limit' can't be negative, silly")
    maxUnits = args.limit if args.limit else args.capacity

    if args.insurance and args.insurance >= (args.credits + 30):
        raise ValueError("Insurance leaves no margin for trade")

    if args.routes < 1:
        raise ValueError("Maximum routes has to be 1 or higher")

    if args.unique and args.hops >= len(tdb.stations):
        raise ValueError("Requested unique trip with more hops than there are stations...")
    if args.unique and (    \
            (originStation and originStation == finalStation) or \
            (originStation and originStation == viaStation) or \
            (viaStation and viaStation == finalStation)):
        raise ValueError("from/to/via repeat conflicts with --unique")

    return args

######################################################################
# Processing functions

def main():
    global tdb
    parse_command_line()

    startCr = args.credits - args.insurance
    routes = [ Route([src], [], startCr, 0, 0) for src in origins ]
    numHops =  args.hops
    lastHop = numHops - 1

    print("From %s via %s to %s with %d credits for %d hops" % (originName, viaName, destName, startCr, numHops))

    calc = TradeCalc(tdb, debug=args.debug, capacity=args.capacity, maxUnits=maxUnits, margin=args.margin, unique=args.unique)
    for hopNo in range(numHops):
        if calc.debug: print("# Hop %d" % hopNo)
        restrictTo = None
        if hopNo == 0 and numHops == 2 and viaStation:
            restrictTo = viaStation
        elif hopNo == lastHop:
            restrictTo = finalStation
            if viaStation:
                # Cull to routes that include the viaStation
                routes = [ route for route in routes if viaStation in route.route[1:] ]
        routes = calc.getBestHops(routes, startCr, restrictTo=restrictTo, maxJumps=args.maxJumps, maxJumpsPer=args.maxJumpsPer, maxLyPer=args.maxLyPer)

    if not routes:
        print("No routes match your selected criteria.")
        return

    routes.sort()
    for i in range(0, min(len(routes), args.routes)):
        print(routes[i])


if __name__ == "__main__":
    main()
