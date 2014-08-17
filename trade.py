#!/usr/bin/env python
#
# We can easily predict the best run from A->B, but the return trip from B->A might
# not give us the best profit.
# The goal here, then, is to find the best multi-hop route.

######################################################################
# Imports

import argparse
import locale

# Forward decls
args = None
originStation, finalStation, viaStation = None, None, None
originName, destName, viaName = "Any", "Any", "Any"
origins = []
maxUnits = 0

######################################################################
# TradeDB and TradeCalc

from tradedb import TradeDB, Trade, Station
from tradecalc import Route, TradeCalc, localedNo

tdb = TradeDB("C:\\Users\\Admin\\PycharmProjects\\tradedangerous\\TradeDangerous.accdb")

######################################################################
# Classes

# Yeah, I moved most of those into modules. See TradeDB.py and TradeCalc.py

######################################################################
# Functions

def parse_avoids(avoidances):
    avoidItems, avoidSystems, avoidStations = [], [], []

    for avoid in args.avoid:
        # Is it an item?
        item, system, station = None, None, None
        try:
            item = tdb.list_search("Item", avoid, tdb.items.values())
            avoidItems.append(tdb.normalized_str(item))
        except LookupError:
            pass
        try:
            system = tdb.getSystem(avoid)
            avoidSystems.append(tdb.normalized_str(system.str()))
        except LookupError:
            pass
        try:
            station = tdb.getStation(avoid)
            avoidStations.append(tdb.normalized_str(station.station))
        except LookupError as e:
            pass

        if not (item or system or station):
            raise LookupError("Unknown item/system/station: %s" % avoid)

        if item and system: raise ValueError("Ambiguity error: avoidance '%s' could be item %s or system %s" % (avoid, item, system.str()))
        if item and station: raise ValueError("Ambiguity error: avoidance '%s' could be item %s or station %s" % (avoid, item, station.str()))
        if system and station and station.system != system: raise ValueError("Ambiguity error: avoidance '%s' could be system %s or station %s" % (avoid, system.str(), station.str()))

    if args.debug: print("Avoiding items %s, systems %s, stations %s" % (avoidItems, avoidSystems, avoidStations))
    tdb.load(avoidItems=avoidItems, avoidSystems=avoidSystems, avoidStations=avoidStations)


def parse_command_line():
    global args, origins, originStation, finalStation, viaStation, maxUnits, originName, destName, viaName

    parser = argparse.ArgumentParser(description='Trade run calculator')
    parser.add_argument('--from', dest='origin', metavar='STATION', help='Specifies starting system/station', required=False)
    parser.add_argument('--to', dest='dest', metavar='STATION', help='Specifies final system/station', required=False)
    parser.add_argument('--via', dest='via', metavar='STATION', help='Require specified station to be en-route', required=False)
    parser.add_argument('--avoid', dest='avoid', metavar='NAME', help='Exclude an item, system or station from the database. Partial matches allowed, e.g. "dom.ap" matches "Dom. Appliance"', required=False, action='append')
    parser.add_argument('--credits', metavar='CR', help='Number of credits to start with', type=int, required=True)
    parser.add_argument('--hops', metavar='N', help="Number of hops (station-to-station) to run. DEFAULT: 2", type=int, default=2, required=False)
    parser.add_argument('--jumps', metavar='N', dest='maxJumps', help="Maximum total jumps (system-to-system)", type=int, default=None, required=False)
    parser.add_argument('--jumps-per', metavar='N', dest='maxJumpsPer', help="Maximum jumps (system-to-system) per hop (station-to-station). DEFAULT: 3", type=int, default=3, required=False)
    parser.add_argument('--ly-per', metavar='N.NN', dest='maxLyPer', help="Maximum light years per individual jump. DEFAULT: 5.2", type=float, default=5.2, required=False)
    parser.add_argument('--capacity', metavar='N', help="Maximum capacity of cargo hold. DEFAULT: 4", type=int, default=4, required=False)
    parser.add_argument('--limit', metavar='N', help='Maximum units of any one cargo item to buy. DEFAULT: 0 (unlimited)', type=int, default=0, required=False)
    parser.add_argument('--unique', help='Only visit each station once', default=False, required=False, action='store_true')
    parser.add_argument('--margin', metavar='N.NN', help="Reduce gains by this much to provide a margin of error for market fluctuations (e.g. 0.25 reduces gains by 1/4). 0<=m<=0.25. DEFAULT: 0.01", default=0.01, type=float, required=False)
    parser.add_argument('--insurance', metavar="CR", help="Reserve at least this many credits to cover insurance", type=int, default=0, required=False)
    parser.add_argument('--detail', help="Give detailed jump information for multi-jump hops", default=False, required=False, action='store_true')
    parser.add_argument('--debug', help="Enable diagnostic output", default=False, required=False, action='store_true')
    parser.add_argument('--routes', metavar="N", help="Maximum number of routes to show. DEFAULT: 1", type=int, default=1, required=False)
    parser.add_argument('--checklist', help='Provide a checklist flow for the route', action='store_true', required=False, default=False, )

    args = parser.parse_args()

    if args.hops < 1:
        raise ValueError("Minimum of 1 hop required")
    if args.hops > 64:
        raise ValueError("Too many hops without more optimization")

    if args.avoid:
        parse_avoids(args.avoid)

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

    if args.checklist and args.routes > 1:
        raise ValueError("Checklist can only be applied to a single route.")

    return args

######################################################################
# Processing functions

def doStep(stepNo, prompt):
    stepNo += 1
    input("   %3d: %s: " % (stepNo, prompt))
    return stepNo

def note(str, addBreak=True):
    print("(i) %s (i)" % str)
    if addBreak:
        print()

def doChecklist(route, credits):
    stepNo, gainCr = 0, 0
    stations, hops, jumps = route.route, route.hops, route.jumps
    lastHopIdx = len(stations) - 1

    title = "(i) BEGINNING CHECKLIST FOR %s (i)" % route.str()
    underline = '-' * len(title)

    print(title)
    print(underline)
    print()
    if args.detail:
        ttlGainCr = sum([hop[1] for hop in hops])
        note("Start CR: %10s" % localedNo(credits), False)
        note("Hops    : %10s" % localedNo(len(hops)), False)
        note("Jumps   : %10s" % localedNo(sum([len(hopJumps) for hopJumps in jumps])), False)
        note("Gain CR : %10s" % localedNo(ttlGainCr), False)
        note("Gain/Hop: %10s" % localedNo(ttlGainCr / len(hops)), False)
        note("Final CR: %10s" % localedNo(credits + ttlGainCr), False)
        print()

    for idx in range(lastHopIdx):
        cur, nxt, hop = stations[idx], stations[idx + 1], hops[idx]

        # Tell them what they need to buy.
        note("Buy [%s]" % cur)
        for item in sorted(hop[0], key=lambda item: item[1] * item[0].gainCr, reverse=True):
            stepNo = doStep(stepNo, "Buy %d x %s" % (item[1], item[0]))
        if args.detail:
            stepNo = doStep(stepNo, "Refuel")
        print()

        # If there is a next hop, describe how to get there.
        note("Fly [%s]" % " -> ".join([ jump.str() for jump in jumps[idx] ]))
        if idx < len(hops) and jumps[idx]:
            for jump in jumps[idx][1:]:
                stepNo = doStep(stepNo, "Jump to [%s]" % (jump.str()))
        if args.detail:
            stepNo = doStep(stepNo, "Dock at [%s]" % nxt)
        print()

        note("Sell [%s]" % nxt)
        for item in sorted(hop[0], key=lambda item: item[1] * item[0].gainCr, reverse=True):
            stepNo = doStep(stepNo, "Sell %s x %s" % (localedNo(item[1]), item[0].item))
        print()

        gainCr += hop[1]
        if args.detail and gainCr > 0:
            note("GAINED: %scr, CREDITS: %scr" % (localedNo(gainCr), localedNo(credits + gainCr)))

        if idx + 1 < lastHopIdx:
            print()
            print("--------------------------------------")
            print()

def main():
    global tdb
    parse_command_line()

    startCr = args.credits - args.insurance
    routes = [ Route(stations=[src], hops=[], jumps=[], startCr=startCr, gainCr=0) for src in origins ]
    numHops =  args.hops
    lastHop = numHops - 1
    viaStartPos = 1 if originStation else 0
    viaEndPos = -1 if finalStation else -1

    if args.debug:
        print("From %s via %s to %s with %d credits for %d hops" % (originName, viaName, destName, args.credits, numHops))

    calc = TradeCalc(tdb, debug=args.debug, capacity=args.capacity, maxUnits=maxUnits, margin=args.margin, unique=args.unique)
    for hopNo in range(numHops):
        if calc.debug: print("# Hop %d" % hopNo)
        restrictTo = None
        if hopNo == 0 and numHops == 2 and viaStation and finalStation:
            # If we're going TO someplace, the via station has to be in the middle.
            # but if we're not going someplace, it could be the last station.
            restrictTo = viaStation
        elif hopNo == lastHop:
            restrictTo = finalStation
            if viaStation and finalStation:
                # Cull to routes that include the viaStation
                routes = [ route for route in routes if viaStation in route.route[viaStartPos:] ]
        routes = calc.getBestHops(routes, startCr, restrictTo=restrictTo, maxJumps=args.maxJumps, maxJumpsPer=args.maxJumpsPer, maxLyPer=args.maxLyPer)

    if viaStation:
        # If the user doesn't specify start or end stations, expand the
        # search for "via" stations to encompass the first/last station
        # as well as the hops in-between
        routes = [ route for route in routes if viaStation in route.route[viaStartPos:viaEndPos] ]

    if not routes:
        print("No routes match your selected criteria.")
        return

    routes.sort()

    # User wants to be guided through the route.
    if args.checklist:
        assert len(routes) == 1
        doChecklist(routes[0], args.credits)

    # Just print the routes.
    for i in range(0, min(len(routes), args.routes)):
        print(routes[i].detail(args.detail))


if __name__ == "__main__":
    main()
