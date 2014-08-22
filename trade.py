#!/usr/bin/env python
# TradeDangerous :: Command Line App :: Main Module
# TradeDangerous Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#   You are free to use, redistribute, or even print and eat a copy of this
#   software so long as you include this copyright notice. I guarantee that
#   there is at least one bug neither of us knew about.
#
# We can easily predict the best run from A->B, but the return trip from B->A might
# not give us the best profit.
# The goal here, then, is to find the best multi-hop route.
#
# TODO:

######################################################################
# Imports

import argparse             # For parsing command line args.
import sys                  # Inevitably.

######################################################################
# The thing I hate most about Python is the global lock. What kind
# of idiot puts globals in their programs?

args = None
originStation, finalStation, viaStation = None, None, None
# Things not to do, places not to go, people not to see.
avoidItems, avoidSystems, avoidStations = [], [], []
originName, destName, viaName = "Any", "Any", "Any"
origins = []
maxUnits = 0
mfd = None

######################################################################
# Database and calculator modules.

from tradedb import TradeDB, AmbiguityError
from tradecalc import Route, TradeCalc, localedNo

tdb = TradeDB('.\\TradeDangerous.accdb')

######################################################################
# Classes

# Multi-Function Display wrappers

class DummyMFD(object):
    """
        Base class for the MFD drivers, implemented as no-ops so that
        you can always use all MFD functions without conditionals.
    """
    hopNo = None

    def __init__(self):
        pass

    def finish(self):
        """
            Close down the driver.
        """
        pass

    def display(self, line1, line2="", line3="", delay=None):
        """
            Display data to the MFD.
            Arguments: 1-3 lines of text plus optional pause in seconds.
        """
        pass


class X52ProMFD(DummyMFD):
    """
        Wrapper for the Saitek X52 Pro MFD.
    """
    def __init__(self):
        try:
            import saitek.X52Pro
            self.doObj = saitek.X52Pro.SaitekX52Pro()
        except:
            raise Exception('Unable to initialize the X52 Pro module. Make sure your X52 is plugged in and you have the drivers installed.')

        self.page = self.doObj.add_page('TD')
        self.display('TradeDangerous', 'INITIALIZING', delay=0.25)

    def finish(self):
        self.doObj.finish()

    def display(self, line1, line2="", line3="", delay=None):
        self.page[0], self.page[1], self.page[2] = line1, line2, line3
        if delay: import time; time.sleep(delay)

######################################################################
# Functions

class CommandLineError(Exception):
    """
        Raised when you provide invalid input on the command line.
        Attributes:
            errorstr       What to tell the user.
    """
    def __init__(self, errorStr):
        self.errorStr = errorStr
    def __str__(self):
        return 'Error in command line: %s' % (self.errorStr)

def parse_avoids(avoidances):
    global avoidItems, avoidSystems, avoidStations

    # You can use --avoid to specify an item, system or station.
    for avoid in avoidances:
        # Is it an item?
        item, system, station = None, None, None
        try:
            item = tdb.list_search('Item', avoid, tdb.items.values())
            avoidItems.append(item)
        except LookupError:
            pass
        # Is it a system perhaps?
        try:
            system = tdb.getSystem(avoid)
            avoidSystems.append(system)
        except LookupError:
            pass
        # Or perhaps it is a station
        try:
            station = tdb.getStation(avoid)
            if not (system and station.system is system):
                avoidStations.append(station)
        except LookupError as e:
            pass
        # If it was none of the above, whine about it
        if not (item or system or station):
            raise CommandLineError("Unknown item/system/station: %s" % avoid)

        # But if it matched more than once, whine about ambiguity
        if item and system: raise AmbiguityError('Avoidance', avoid, item, system.str())
        if item and station: raise AmbiguityError('Avoidance', avoid, item, station.str())
        if system and station and station.system != system: raise AmbiguityError('Avoidance', avoid, system.str(), station.str())

    if args.debug: print("Avoiding items %s, systems %s, stations %s" % (avoidItems, avoidSystems, avoidStations))

def parse_command_line():
    global args, origins, originStation, finalStation, viaStation, maxUnits, originName, destName, viaName, mfd

    parser = argparse.ArgumentParser(description='Trade run calculator')
    parser.add_argument('--from', dest='origin', metavar='STATION', help='Specifies starting system/station', required=False)
    parser.add_argument('--to', dest='dest', metavar='STATION', help='Specifies final system/station', required=False)
    parser.add_argument('--via', dest='via', metavar='STATION', help='Require specified station to be en-route', required=False)
    parser.add_argument('--avoid', dest='avoid', metavar='NAME', help='Exclude an item, system or station from the database. Partial matches allowed, e.g. "dom.ap" matches "Dom. Appliance"', required=False, action='append')
    parser.add_argument('--hops', metavar='N', help='Number of hops (station-to-station) to run. DEFAULT: 2', type=int, default=2, required=False)
    parser.add_argument('--jumps', metavar='N', dest='maxJumps', help='Maximum total jumps (system-to-system)', type=int, default=None, required=False)
    parser.add_argument('--jumps-per', metavar='N', dest='maxJumpsPer', help='Maximum jumps (system-to-system) per hop (station-to-station). DEFAULT: 2', type=int, default=2, required=False)
    parser.add_argument('--ly-per', metavar='N.NN', dest='maxLyPer', help='Maximum light years per individual jump.', type=float, default=None, required=False)
    parser.add_argument('--credits', metavar='CR', help='Number of credits to start with', type=int, required=True)
    parser.add_argument('--capacity', metavar='N', help='Maximum capacity of cargo hold. DEFAULT: 4', type=int, default=4, required=False)
    parser.add_argument('--ship', metavar='name', help='Set capacity and max-ly-per from ship type', type=str, required=False, default=None)
    parser.add_argument('--limit', metavar='N', help='Maximum units of any one cargo item to buy. DEFAULT: 0 (unlimited)', type=int, default=0, required=False)
    parser.add_argument('--unique', help='Only visit each station once', default=False, required=False, action='store_true')
    parser.add_argument('--margin', metavar='N.NN', help='Reduce gains by this much to provide a margin of error for market fluctuations (e.g. 0.25 reduces gains by 1/4). 0<=m<=0.25. DEFAULT: 0.01', default=0.01, type=float, required=False)
    parser.add_argument('--insurance', metavar='CR', help='Reserve at least this many credits to cover insurance', type=int, default=0, required=False)
    parser.add_argument('-v', '--detail', help='Give detailed jump information for multi-jump hops', default=0, required=False, action='count')
    parser.add_argument('--debug', help='Enable diagnostic output', default=0, required=False, action='count')
    parser.add_argument('--routes', metavar='N', help='Maximum number of routes to show. DEFAULT: 1', type=int, default=1, required=False)
    parser.add_argument('--checklist', help='Provide a checklist flow for the route', action='store_true', required=False, default=False)
    parser.add_argument('--x52-pro', dest='x52pro', help='Enable experimental X52 Pro MFD output', action='store_true', required=False, default=False)

    args = parser.parse_args()

    if args.hops < 1:
        raise CommandLineError("Minimum of 1 hop required")
    if args.hops > 64:
        raise CommandLineError("Too many hops without more optimization")

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
            raise CommandLineError("More than one hop required to use same from/to destination")

    if args.via:
        if args.hops < 2:
            raise CommandLineError("Minimum of 2 hops required for a 'via' route")
        viaName = args.via
        viaStation = tdb.getStation(viaName)
        if args.hops == 2:
            if viaStation == originStation:
                raise CommandLineError("3+ hops required to go 'via' the origin station")
            if viaStation == finalStation:
                raise CommandLineError("3+ hops required to go 'via' the destination station")
        if args.hops <= 3:
            if viaStation == originStation and viaStation == finalStation:
                raise CommandLineError("4+ hops required to go 'via' the same station as you start and end at")

    if args.credits < 0:
        raise CommandLineError("Invalid (negative) value for initial credits")

    # If the user specified a ship, use it to fill out details unless
    # the user has explicitly supplied them. E.g. if the user says
    # --ship sidewinder --capacity 2, use their capacity limit.
    if args.ship:
        ship = tdb.getShip(args.ship)
        args.ship = ship
        if args.capacity is None: args.capacity = ship.capacity
        if args.maxLyPer is None: args.maxLyPer = ship.maxJumpFull
    if args.capacity is None:
        raise CommandLineError("Missing '--capacity' or '--ship' argument")
    if args.maxLyPer is None:
        raise CommandLineError("Missing '--ly-per' or '--ship' argument")
    if args.capacity < 0:
        raise CommandLineError("Invalid (negative) cargo capacity")
    if args.capacity > 1000:
        raise CommandLineError("Capacity > 1000 not supported (you specified %s)" % args.capacity)

    if args.limit and args.limit > args.capacity:
        raise CommandLineError("'limit' must be <= capacity")
    if args.limit and args.limit < 0:
        raise CommandLineError("'limit' can't be negative, silly")
    maxUnits = args.limit if args.limit else args.capacity

    if args.insurance and args.insurance >= (args.credits + 30):
        raise CommandLineError("Insurance leaves no margin for trade")

    if args.routes < 1:
        raise CommandLineError("Maximum routes has to be 1 or higher")

    if args.unique and args.hops >= len(tdb.stations):
        raise CommandLineError("Requested unique trip with more hops than there are stations...")
    if args.unique:
        if ((originStation and originStation == finalStation) or
                (originStation and originStation == viaStation) or
                 (viaStation and viaStation == finalStation)):
            raise CommandLineError("from/to/via repeat conflicts with --unique")

    if args.checklist and args.routes > 1:
        raise CommandLineError("Checklist can only be applied to a single route.")

    mfd = DummyMFD()
    if args.x52pro:
        mfd = X52ProMFD()

    mfd.display('TradeDangerous', 'CALCULATING', delay=0.25)

    return args

######################################################################
# Processing functions

def doStep(stepNo, action, detail=""):
    stepNo += 1
    mfd.display("Step %d. Hop %d" % (stepNo, mfd.hopNo), action, detail)
    if detail:
        input("   %3d: %s %s: " % (stepNo, action, detail))
    else:
        input("   %3d: %s: " % (stepNo, action))
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
        print(route.summary(), "\n")

    for idx in range(lastHopIdx):
        mfd.hopNo = hopNo = idx + 1
        cur, nxt, hop = stations[idx], stations[idx + 1], hops[idx]

        # Tell them what they need to buy.
        if args.detail:
            note("HOP %d of %d" % (hopNo, lastHopIdx))

        note("Buy at %s" % cur)
        for (item, qty) in sorted(hop[0], key=lambda item: item[1] * item[0].gainCr, reverse=True):
            itemDesc = "%s @ %dcr" % (item.item, item.costCr)
            stepNo = doStep(stepNo, 'Buy %d x' % qty, itemDesc)
        if args.detail:
            stepNo = doStep(stepNo, 'Refuel')
        print()

        # If there is a next hop, describe how to get there.
        note("Fly %s" % " -> ".join([ jump.str() for jump in jumps[idx] ]))
        if idx < len(hops) and jumps[idx]:
            for jump in jumps[idx][1:]:
                stepNo = doStep(stepNo, 'Jump to', '%s' % (jump.str()))
        if args.detail:
            stepNo = doStep(stepNo, 'Dock at', '%s' % nxt)
        print()

        note("Sell at %s" % nxt)
        for (item, qty) in sorted(hop[0], key=lambda item: item[1] * item[0].gainCr, reverse=True):
            itemDesc = "%s @ %dcr" % (item.item, item.costCr + item.gainCr)
            stepNo = doStep(stepNo, 'Sell %s x' % localedNo(qty), itemDesc)
        print()

        gainCr += hop[1]
        if args.detail and gainCr > 0:
            note("GAINED: %scr, CREDITS: %scr" % (localedNo(gainCr), localedNo(credits + gainCr)))

        if hopNo < lastHopIdx:
            print()
            print("--------------------------------------")
            print()

    mfd.hopNo = None
    mfd.display('FINISHED', "+%scr" % localedNo(gainCr), "=%scr" % localedNo(credits + gainCr), delay=3)

def main():
    global tdb
    parse_command_line()

    startCr = args.credits - args.insurance
    routes = [
        Route(stations=[src], hops=[], jumps=[], startCr=startCr, gainCr=0)
        for src in origins
        if not (src in avoidStations or src.system in avoidSystems)
    ]
    numHops = args.hops
    lastHop = numHops - 1
    viaStartPos = 1 if originStation else 0

    if args.debug or args.detail:
        print("From %s via %s to %s with %s credits." % (originName, viaName, destName, localedNo(args.credits)))
        print("%d hops, max %d jumps/hop and max %dly/jump" % (numHops, args.maxJumpsPer, args.maxLyPer))
        print("--------------------------------------------------------")
        print()

    calc = TradeCalc(tdb, debug=args.debug, capacity=args.capacity, maxUnits=maxUnits, margin=args.margin, unique=args.unique)
    avoidPlaces = avoidSystems + avoidStations
    for hopNo in range(numHops):
        if calc.debug: print("# Hop %d" % hopNo)
        restrictTo = None
        if hopNo == 0 and numHops == 2 and viaStation and finalStation:
            # If we're going TO someplace, the via station has to be in the middle.
            # but if we're not going someplace, it could be the last station.
            restrictTo = viaStation
        elif hopNo == lastHop:
            restrictTo = finalStation
            if viaStation:
                # Cull to routes that include the viaStation, might save us some calculations
                routes = [ route for route in routes if viaStation in route.route[viaStartPos:] ]
        routes = calc.getBestHops(routes, startCr,
                                  restrictTo=restrictTo, avoidItems=avoidItems, avoidPlaces=avoidPlaces,
                                  maxJumps=args.maxJumps, maxJumpsPer=args.maxJumpsPer, maxLyPer=args.maxLyPer)

    if not routes:
        print("No routes match your selected criteria.")
        return

    routes.sort()

    for i in range(0, min(len(routes), args.routes)):
        print(routes[i].detail(detail=args.detail))

    # User wants to be guided through the route.
    if args.checklist:
        assert args.routes == 1
        doChecklist(routes[0], args.credits)
        return

if __name__ == "__main__":
    try:
        main()
    except (CommandLineError, AmbiguityError) as e:
        print("%s: error: %s" % (sys.argv[0], str(e)))
    finally:
        if mfd:
            mfd.finish()
