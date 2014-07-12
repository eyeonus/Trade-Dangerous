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
from pprint import pprint, pformat
import itertools
from collections import deque
from math import ceil, floor

# Forward decls
args = None
profitCache = dict()
originID, finalStationID, viaStationID = None, None, None
originName, destName, viaName = "Any", "Any", "Any"
origins = []

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
    def __init__(self, route, hops, gainCr):
        self.route = list(route)
        self.hops = hops
        self.gainCr = gainCr

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
    global args, origins, originID, finalStationID, viaStationID, originName, destName, viaName

    parser = argparse.ArgumentParser(description='Trade run calculator')
    parser.add_argument('--from', dest='origin', metavar='<Origin>', help='Specifies starting system/station', required=False)
    parser.add_argument('--to', dest='dest', metavar='<Destination>', help='Specifies final system/station', required=False)
    parser.add_argument('--via', dest='via', metavar='<ViaStation>', help='Require specified station to be en-route', required=False)
    parser.add_argument('--credits', metavar='<Balance>', help='Number of credits to start with', type=int, required=True)
    parser.add_argument('--hops', metavar="<Hops>", help="Number of hops to run", type=int, default=2, required=False)
    parser.add_argument('--capacity', metavar="<Capactiy>", help="Maximum capacity of cargo hold", type=int, default=4, required=False)
    parser.add_argument('--insurance', metavar="<Credits>", help="Reserve at least this many credits", type=int, default=0, required=False)
    parser.add_argument('--margin', metavar="<Error Margin>", help="Reduce gains by this much to provide a margin of error for market fluctuations (e.g. 0.25 reduces gains by 1/4). 0<=m<=0.25. Default: 0.02", default=0.02, type=float, required=False)
    parser.add_argument('--debug', help="Enable verbose output", default=False, required=False, action='store_true')
    parser.add_argument('--routes', metavar="<MaxRoutes>", help="Maximum number of routes to show", type=int, default=1, required=False)

    args = parser.parse_args()

    if args.hops < 1:
        raise ValueError("Minimum of 1 hop required")
    if args.hops > 10:
        raise ValueError("Too many hops without more optimization")

    if args.origin:
        originName = args.origin
        originID = tdb.get_station_id(originName)
        origins = [ tdb.stations[originID] ]
    else:
        origins = [ station for station in tdb.stations.values() ]

    if args.dest:
        destName = args.dest
        finalStationID = tdb.get_station_id(destName)
        if args.hops == 1 and originID and finalStationID and originID == finalStationID:
            raise ValueError("More than one hop required to use same from/to destination")

    if args.via:
        if args.hops < 2:
            raise ValueError("Minimum of 2 hops required for a 'via' route")
        viaName = args.via
        viaStationID = tdb.get_station_id(viaName)
        if args.hops == 2:
            if viaStationID == originID:
                raise ValueError("3+ hops required to go 'via' the origin station")
            if viaStationID == finalStationID:
                raise ValueError("3+ hops required to go 'via' the destination station")
        if args.hops <= 3:
            if viaStationID == originID and viaStationID == finalStationID:
                raise ValueError("4+ hops required to go 'via' the same station as you start and end at")

    if args.credits < 0:
        raise ValueError("Invalid (negative) value for initial credits")

    if args.capacity < 0:
        raise ValueError("Invalid (negative) cargo capacity")

    if args.insurance and args.insurance >= (args.credits + 30):
        raise ValueError("Insurance leaves no margin for trade")

    if args.routes < 1:
        raise ValueError("Maximum routes has to be 1 or higher")

    return args

######################################################################
# Processing functions

def try_combinations(capacity, credits, tradeList):
    best, bestCr = [], 0
    for idx, trade in enumerate(tradeList):
        itemCostCr = trade.costCr
        maximum = min(capacity, credits // itemCostCr)
        if maximum > 0 :
            best.append([trade, maximum])
            capacity -= maximum
            credits -= maximum * itemCostCr
            bestCr += maximum * trade.gainCr
            if not capacity or not credits:
                break
    return [ best, bestCr ]


def get_profits(src, dst, startCr):
    if args.debug: print("%s -> %s with %dcr" % (src, dst, startCr))

    # Get a list of what we can buy
    trades = src.links[dst.ID]
    return try_combinations(args.capacity, startCr, trades)


def generate_routes():
    q = deque([[origin] for origin in origins])
    hops = args.hops
    while q:
        # get the most recent partial route
        route = q.pop()
        # furthest station on the route
        lastStation = route[-1]
        if len(route) >= hops: # destination
            # upsize the array so we can reuse the slot.
            route.append(0)
            for dest in lastStation.stations:
                route[-1] = dest
                yield route
        else:
            for dest in lastStation.stations:
                q.append(route + [dest])

def main():
    parse_command_line()

    print("From %s via %s to %s with %d credits for %d hops" % (originName, viaName, destName, args.credits, args.hops))

    startCr = args.credits - args.insurance
    routes = []
    for route in generate_routes():
        # Do we have a specific destination requirement?
        if finalStationID and route[-1] != finalStationID:
            continue
        # Do we have a travel-via requirement?
        if viaStationID and not viaStationID in route[1:-2]:
            continue
        credits = startCr
        gainCr = 0
        hops = []
        for i in range(0, len(route) - 1):
            src, dst = route[i], route[i + 1]
            if args.debug: print("hop %d: %s -> %s" % (i, src, dst))
            bestTrade = get_profits(src, dst, credits + gainCr)
            if not bestTrade:
                break
            hops.append(bestTrade)
            gainCr += int(bestTrade[1] * (1.0 - args.margin))
        if len(hops) + 1 < len(route):
            continue
        routes.append(Route(route, hops, gainCr))
        assert credits + gainCr > startCr

    if not routes:
        print("No routes match your selected criteria.")
        return

    routes.sort()
    for i in range(0, min(len(routes), args.routes)):
        print(routes[i])


if __name__ == "__main__":
    main()
