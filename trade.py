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
import itertools
from math import ceil, floor

# Forward decls
args = None
profitCache = dict()
originStation, finalStation, viaStation = None, None, None
originName, destName, viaName = "Any", "Any", "Any"
origins = []
maxUnits = 0

######################################################################
# DB Setup

# Connect
from tradedb import TradeDB, Trade, Station
tdb = TradeDB("C:\\Dev\\trade\\TradeDangerous.accdb")

######################################################################
# Classes

class Route(object):
    """ Describes a series of CargoRuns, that is CargoLoads
        between several stations. E.g. Chango -> Gateway -> Enterprise
        """
    def __init__(self, stations, hops, gainCr):
        self.route = stations
        self.hops = hops
        self.gainCr = gainCr

    def plus(self, dst, hop):
        rvalue = Route(self.route + [dst], self.hops + [hop], self.gainCr + hop[1])
        return rvalue

    def __lt__(self, rhs):
        return rhs.gainCr < self.gainCr # reversed
    def __eq__(self, rhs):
        return self.gainCr == rhs.gainCr

    def __repr__(self):
        src = self.route[0]
        credits = args.credits
        gainCr = 0
        route = self.route

        str = "%s -> %s:\n" % (src, route[-1])
        for i in range(len(route) - 1):
            hop = self.hops[i]
            str += " @ %-20s Buy" % route[i]
            for item in hop[0]:
                str += " %d*%s," % (item[1], item[0])
            str += "\n"
            gainCr += hop[1]

        str += " $ %s %dcr + %dcr => %dcr total" % (route[-1], credits, gainCr, credits + gainCr)

        return str

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
    parser.add_argument('--capacity', metavar="<Capactiy>", help="Maximum capacity of cargo hold", type=int, default=4, required=False)
    parser.add_argument('--limit', help='Maximum units of any one cargo item to buy', type=int, default=0, required=False)
    parser.add_argument('--unique', help='Only visit each station once', default=False, required=False, action='store_true')
    parser.add_argument('--insurance', metavar="<Credits>", help="Reserve at least this many credits", type=int, default=0, required=False)
    parser.add_argument('--margin', metavar="<Error Margin>", help="Reduce gains by this much to provide a margin of error for market fluctuations (e.g. 0.25 reduces gains by 1/4). 0<=m<=0.25. Default: 0.02", default=0.02, type=float, required=False)
    parser.add_argument('--debug', help="Enable verbose output", default=False, required=False, action='store_true')
    parser.add_argument('--routes', metavar="<MaxRoutes>", help="Maximum number of routes to show", type=int, default=1, required=False)
    parser.add_argument('--links', dest='ignoreLinks', help="Ignore links (treat all stations as connected)", default=False, required=False, action='store_true')

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

    if args.ignoreLinks or avoidItems:
        tdb.load(avoiding=avoidItems, ignoreLinks=args.ignoreLinks)

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

def try_combinations(startCapacity, startCr, tradeList):
    firstTrade = tradeList[0]
    if maxUnits >= startCapacity and firstTrade.costCr * startCapacity <= startCr:
        return [ [ [ firstTrade, startCapacity ] ], firstTrade.gainCr * startCapacity ]
    best, bestGainCr, bestCap = [], 0, startCapacity
    tradeItems = len(tradeList)
    for handicap in range(startCapacity):
        for combo in itertools.combinations(tradeList, min(startCapacity, tradeItems)):
            cargo, credits, capacity, gainCr = [], startCr, startCapacity, 0
            myHandicap = handicap
            for trade in combo:
                itemCostCr = trade.costCr
                maximum = min(min(capacity, maxUnits), credits // itemCostCr)
                if maximum > 0:
                    deduction = min(maximum, myHandicap)
                    maximum -= deduction
                    myHandicap -= deduction
                if maximum > 0:
                    cargo.append([trade, maximum])
                    capacity -= maximum
                    credits -= maximum * itemCostCr
                    gainCr += maximum * trade.gainCr
                    if not capacity or not credits:
                        break
        if gainCr < bestGainCr:
            continue
        if gainCr == bestGainCr and capacity >= bestCap:
            continue
        best, bestGainCr, bestCap = cargo, gainCr, capacity

    return [ best, bestGainCr ]


def get_profits(src, dst, startCr):
    if args.debug: print("# %s -> %s with %dcr" % (src, dst, startCr))

    # Get a list of what we can buy
    return try_combinations(args.capacity, startCr, src.links[dst.ID])


def get_best_hops(routes, credits, restrictTo):
    """ Given a list of routes, try all available next hops from each
        route. Store the results by destination so that we pick the
        best route-to-point for each destination at each step. If we
        have two routes: A->B->D, A->C->D and A->B->D produces more
        profit, then there is no point in continuing the A->C->D path. """

    bestToDest = {}
    safetyMargin = 1.0 - args.margin
    for route in routes:
        src = route.route[-1]
        for dst in src.stations:
            if restrictTo and dst != restrictTo:
                continue
            if args.unique and dst in route.route:
                continue
            trade = get_profits(src, dst, credits + int(route.gainCr * safetyMargin))
            if not trade:
                continue
            dstID = dst.ID
            try:
                best = bestToDest[dstID]
                if best[1].gainCr + best[2][1] >= route.gainCr + trade[1]:
                    continue
            except: pass
            bestToDest[dstID] = [ dst, route, trade ]

    result = []
    for (dst, route, trade) in bestToDest.values():
        result.append(route.plus(dst, trade))

    return result

def main():
    parse_command_line()

    startCr = args.credits - args.insurance
    routes = [ Route([src], [], 0) for src in origins ]
    numHops =  args.hops
    lastHop = numHops - 1

    print("From %s via %s to %s with %d credits for %d hops" % (originName, viaName, destName, startCr, numHops))

    for hopNo in range(numHops):
        if args.debug: print("# Hop %d" % hopNo)
        restrictTo = None
        if hopNo == 0 and viaStation:
            restrictTo = viaStation
        elif hopNo == lastHop:
            restrictTo = finalStation
            if viaStation:
                # Cull to routes that include the viaStation
                routes = [ route for route in routes if viaStation in route.route[1:] ]
        routes = get_best_hops(routes, startCr, restrictTo)

    if not routes:
        print("No routes match your selected criteria.")
        return

    routes.sort()
    for i in range(0, min(len(routes), args.routes)):
        print(routes[i])


if __name__ == "__main__":
    main()
