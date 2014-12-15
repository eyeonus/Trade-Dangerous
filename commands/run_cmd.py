from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from commands.exceptions import *
from tradedb import System, Station

######################################################################
# Parser config

help='Calculate best trade run.'
name='run'
epilog=None
arguments = [
    ParseArgument('--capacity',
            help='Maximum capacity of cargo hold.',
            metavar='N',
            type=int,
        ),
    ParseArgument('--credits',
            help='Starting credits.',
            metavar='CR',
            type=int,
        ),
    ParseArgument('--ly-per',
            help='Maximum light years per jump.',
            dest='maxLyPer',
            metavar='N.NN',
            type=float,
        ),
]
switches = [
    ParseArgument('--from',
            help='Starting system/station.',
            dest='starting',
            metavar='STATION',
        ),
    ParseArgument('--to',
            help='Final system/station.',
            dest='ending',
            metavar='PLACE',
        ),
    ParseArgument('--via',
            help='Require specified systems/stations to be en-route.',
            action='append',
            metavar='PLACE[,PLACE,...]',
        ),
    ParseArgument('--avoid',
            help='Exclude an item, system or station from trading. '
                    'Partial matches allowed, '
                    'e.g. "dom.App" or "domap" matches "Dom. Appliances".',
            action='append',
        ),
    ParseArgument('--hops',
            help='Number of hops (station-to-station) to run.',
            default=2,
            type=int,
            metavar='N',
        ),
    ParseArgument('--jumps-per',
            help='Maximum number of jumps (system-to-system) per hop.',
            default=2,
            dest='maxJumpsPer',
            metavar='N',
            type=int,
        ),
    ParseArgument('--empty-ly',
            help='Maximum light years ship can jump when empty.',
            dest='emptyLyPer',
            metavar='N.NN',
            type=float,
            default=None,
        ),
    ParseArgument('--start-jumps', '-s',
            help='Allow this many jumps before loading up.',
            dest='startJumps',
            default=0,
            type=int,
        ),
    ParseArgument('--limit',
            help='Maximum units of any one cargo item to buy (0: unlimited).',
            metavar='N',
            type=int,
        ),
    ParseArgument('--max-days-old', '-MD',
            help='Maximum age (in days) of trade data to use.',
            metavar='DAYS',
            type=float,
            dest='maxAge',
        ),
    ParseArgument('--unique',
            help='Only visit each station once.',
            action='store_true',
            default=False,
        ),
    ParseArgument('--margin',
            help='Reduce gains made on each hop to provide a margin of error '
                    'for market fluctuations (e.g: 0.25 reduces gains by 1/4). '
                    '0<: N<: 0.25.',
            default=0.00,
            metavar='N.NN',
            type=float,
        ),
    ParseArgument('--insurance',
            help='Reserve at least this many credits to cover insurance.',
            default=0,
            metavar='CR',
            type=int,
        ),
    ParseArgument('--routes',
            help='Maximum number of routes to show. DEFAULT: 1',
            default=1,
            metavar='N',
            type=int,
        ),
    ParseArgument('--checklist',
            help='Provide a checklist flow for the route.',
            action='store_true',
            default=False,
        ),
    ParseArgument('--x52-pro',
            help='Enable experimental X52 Pro MFD output.',
            action='store_true',
            default=False,
            dest='x52pro',
        ),
]

######################################################################
# Helpers

class Checklist(object):
    """
        Class for encapsulating display of a route as a series of
        steps to be 'checked off' as the user passes through them.
    """

    def __init__(self, tdb, cmdenv):
        self.tdb = tdb
        self.cmdenv = cmdenv
        self.mfd = cmdenv.mfd


    def doStep(self, action, detail=None, extra=None):
        self.stepNo += 1
        try:
            self.mfd.display("#{} {}".format(self.stepNo, action), detail or "", extra or "")
        except AttributeError: pass
        input("   {:<3}: {}: ".format(self.stepNo, " ".join([item for item in [action, detail, extra] if item])))


    def note(self, str, addBreak=True):
        print("(i) {} (i){}".format(str, "\n" if addBreak else ""))


    def run(self, route, credits):
        tdb, mfd = self.tdb, self.mfd
        stations, hops, jumps = route.route, route.hops, route.jumps
        lastHopIdx = len(stations) - 1
        gainCr = 0
        self.stepNo = 0

        heading = "(i) BEGINNING CHECKLIST FOR {} (i)".format(route.str())
        print(heading, "\n", '-' * len(heading), "\n\n", sep='')

        cmdenv = self.cmdenv
        if cmdenv.detail:
            print(route.summary())
            print()

        for idx in range(lastHopIdx):
            hopNo = idx + 1
            cur, nxt, hop = stations[idx], stations[idx + 1], hops[idx]
            sortedTradeOptions = sorted(hop[0], key=lambda tradeOption: tradeOption[1] * tradeOption[0].gainCr, reverse=True)

            # Tell them what they need to buy.
            if cmdenv.detail:
                self.note("HOP {} of {}".format(hopNo, lastHopIdx))

            self.note("Buy at {}".format(cur.name()))
            for (trade, qty) in sortedTradeOptions:
                self.doStep('Buy {:n} x'.format(qty), trade.name(), '@ {}cr'.format(trade.costCr))
            if cmdenv.detail:
                self.doStep('Refuel')
            print()

            # If there is a next hop, describe how to get there.
            self.note("Fly {}".format(" -> ".join([ jump.name() for jump in jumps[idx] ])))
            if idx < len(hops) and jumps[idx]:
                for jump in jumps[idx][1:]:
                    self.doStep('Jump to', jump.name())
            if cmdenv.detail:
                self.doStep('Dock at', nxt.str())
            print()

            self.note("Sell at {}".format(nxt.name()))
            for (trade, qty) in sortedTradeOptions:
                self.doStep('Sell {:n} x'.format(qty),
                            trade.name(), '@ {:n}cr'.format(
                                trade.costCr + trade.gainCr))
            print()

            gainCr += hop[1]
            if cmdenv.detail and gainCr > 0:
                self.note("GAINED: {:n}cr, CREDITS: {:n}cr".format(
                            gainCr, credits + gainCr))

            if hopNo < lastHopIdx:
                print("\n--------------------------------------\n")

        if mfd:
            mfd.display('FINISHED',
                        "+{:n}cr".format(gainCr),
                        "={:n}cr".format(credits + gainCr))
            mfd.attention(3)
            from time import sleep
            sleep(1.5)


def extendOriginsForStartJumps(tdb, cmdenv):
    """
    Find all the stations you could reach if you made a given
    number of jumps away from the origin list.
    """

    startJumps = cmdenv.startJumps
    if not startJumps:
        return cmdenv.origins

    origSys = [o.system for o in cmdenv.origins]
    maxLyPer = cmdenv.emptyLyPer or cmdenv.maxLyPer
    avoidPlaces = cmdenv.avoidPlaces
    if cmdenv.debug:
        cmdenv.DEBUG0(
                "Checking start stations "
                "{} jumps at "
                "{}ly per jump "
                "from {}",
                    startJumps,
                    maxLyPer,
                    [sys.dbname for sys in origSys]
                )

    origSys = set(origSys)
    nextJump = set(origSys)
    for jump in range(0, startJumps):
        if not nextJump:
            break
        thisJump, nextJump = nextJump, set()
        if cmdenv.debug:
            cmdenv.DEBUG1(
                    "Ring {}: {}",
                    jump,
                    [sys.dbname for sys in thisJump]
                    )
        for sys in thisJump:
            for dest, dist in tdb.genSystemsInRange(sys, maxLyPer):
                if dest not in avoidPlaces:
                    origSys.add(dest)
                    nextJump.add(dest)

    if cmdenv.debug:
        cmdenv.DEBUG0(
                "Extended start systems: {}",
                [sys.dbname for sys in origSys]
                )

    # Filter down to stations with trade data
    origins = []
    for sys in origSys:
        for stn in sys.stations:
            if stn.itemCount and stn not in avoidPlaces:
                origins.append(stn) 

    if cmdenv.debug:
        cmdenv.DEBUG0(
                "Extended start stations: {}",
                [sys.name() for sys in origins]
                )

    return origins


def validateRunArguments(tdb, cmdenv):
    """
        Process arguments to the 'run' option.
    """

    if cmdenv.credits < 0:
        raise CommandLineError("Invalid (negative) value for initial credits")
    # I'm going to allow 0 credits as a future way of saying "just fly"

    if cmdenv.routes < 1:
        raise CommandLineError("Maximum routes has to be 1 or higher")
    if cmdenv.routes > 1 and cmdenv.checklist:
        raise CommandLineError("Checklist can only be applied to a single route.")

    if cmdenv.hops < 1:
        raise CommandLineError("Minimum of 1 hop required")
    if cmdenv.hops > 64:
        raise CommandLineError("Too many hops without more optimization")

    if cmdenv.maxJumpsPer < 0:
        raise CommandLineError("Negative jumps: you're already there?")

    if cmdenv.origPlace:
        if isinstance(cmdenv.origPlace, System):
            cmdenv.origins = list(cmdenv.origPlace.stations)
            if not cmdenv.origins:
                raise CommandLineError(
                        "No stations at origin system, {}"
                            .format(cmdenv.origPlace.name())
                        )
        else:
            cmdenv.origins = [ cmdenv.origPlace ]
            cmdenv.startStation = cmdenv.origPlace
        cmdenv.origins = extendOriginsForStartJumps(tdb, cmdenv)
    else:
        cmdenv.origins = [ station for station in tdb.stationByID.values() ]

    cmdenv.stopStation = None
    if cmdenv.destPlace:
        if isinstance(cmdenv.destPlace, Station):
            cmdenv.stopStation = cmdenv.destPlace
        elif isinstance(cmdenv.destPlace, System):
            if not cmdenv.destPlace.stations:
                raise CommandLineError(
                        "No known/trading stations in {}.".format(
                            cmdenv.destPlace.name()
                ))

    if cmdenv.stopStation:
        if cmdenv.hops == 1 and cmdenv.startStation:
            if cmdenv.startStation == cmdenv.stopStation:
                raise CommandLineError("Same to/from; more than one hop required.")

    viaSet = cmdenv.viaSet = set(cmdenv.viaPlaces)
    viaSystems = set()
    for place in viaSet:
        if isinstance(place, Station):
            if not place.itemCount:
                raise NoDataError(
                            "No price data available for via station {}.".format(
                                place.name()
                        ))
            viaSystems.add(place.system)
        else:
            viaSystems.add(place)

    # How many of the hops do not have pre-determined stations. For example,
    # when the user uses "--from", they pre-determine the starting station.
    fixedRoutePoints = 0
    if cmdenv.origPlace:
        fixedRoutePoints += 1
    if cmdenv.destPlace:
        fixedRoutePoints += 1
    totalRoutePoints = cmdenv.hops + 1
    adhocRoutePoints = totalRoutePoints - fixedRoutePoints
    if len(viaSystems) > adhocRoutePoints:
        raise CommandLineError(
                "Route is not long enough for the list of '--via' "
                "destinations you gave. Reduce the vias or try again "
                "with '--hops {}' or greater.\n".format(
                    len(viaSet) + fixedRoutePoints - 1
                ))
    cmdenv.adhocHops = adhocRoutePoints - 1

    if cmdenv.capacity is None:
        raise CommandLineError("Missing '--capacity'")
    if cmdenv.maxLyPer is None:
        raise CommandLineError("Missing '--ly-per'")
    if cmdenv.capacity < 0:
        raise CommandLineError("Invalid (negative) cargo capacity")
    if cmdenv.capacity > 1000:
        raise CommandLineError("Capacity > 1000 not supported (you specified {})".format(
                                cmdenv.capacity))

    if cmdenv.limit and cmdenv.limit > cmdenv.capacity:
        raise CommandLineError("'limit' must be <= capacity")
    if cmdenv.limit and cmdenv.limit < 0:
        raise CommandLineError("'limit' can't be negative, silly")
    cmdenv.maxUnits = cmdenv.limit if cmdenv.limit else cmdenv.capacity

    arbitraryInsuranceBuffer = 42
    if cmdenv.insurance and cmdenv.insurance >= (cmdenv.credits + arbitraryInsuranceBuffer):
        raise CommandLineError("Insurance leaves no margin for trade")

    startStn, stopStn = cmdenv.startStation, cmdenv.stopStation
    if cmdenv.unique and cmdenv.hops >= len(tdb.stationByID):
        raise CommandLineError("Requested unique trip with more hops than there are stations...")
    if cmdenv.unique:
        startConflict = (startStn and (startStn == stopStn or startStn in viaSet))
        stopConflict  = (stopStn and stopStn in viaSet)
        if startConflict or stopConflict:
            raise CommandLineError("from/to/via repeat conflicts with --unique")

    if cmdenv.mfd:
        cmdenv.mfd.display("Loading Trades")

    if startStn and startStn.itemCount == 0:
        raise NoDataError("Start station {} doesn't have any price data.".format(
                            startStn.name()))
    if stopStn and stopStn.itemCount == 0:
        raise NoDataError("End station {} doesn't have any price data.".format(
                            stopStn.name()))
    if cmdenv.origins:
        tradingOrigins = [
                stn for stn in cmdenv.origins
                if stn.itemCount > 0
        ]
        if not tradingOrigins:
            raise NoDataError("No price data at origin stations.")
        cmdenv.origins = tradingOrigins

    if startStn:
        tdb.loadStationTrades([startStn.ID])
        if stopStn and cmdenv.hops == 1 and not stopStn in startStn.tradingWith:
            raise CommandLineError("No profitable items found between {} and {}".format(
                                startStn.name(), stopStn.name()))
        if len(startStn.tradingWith) == 0:
            raise NoDataError("No data found for potential buyers for items from {}.".format(
                                startStn.name()))


######################################################################


def filterByVia(routes, viaSet, viaStartPos):
    matchedRoutes = list(routes)
    for route in routes:
        met = 0
        for hop in route.route[viaStartPos:]:
            if hop in viaSet or hop.system in viaSet:
                met += 1
        if met >= len(viaSet):
            matchedRoutes.append(route)
    return matchedRoutes

######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    from commands.commandenv import ResultRow

    cmdenv.DEBUG1("loading trades")

    if tdb.tradingCount == 0:
        raise NoDataError("Database does not contain any profitable trades.")

    validateRunArguments(tdb, cmdenv)

    from tradecalc import TradeCalc, Route

    origPlace, viaSet = cmdenv.origPlace, cmdenv.viaSet

    avoidPlaces = cmdenv.avoidPlaces

    if cmdenv.destPlace:
        if isinstance(cmdenv.destPlace, System):
            stopStations = set(cmdenv.destPlace.stations)
        else:
            stopStations = set([cmdenv.destPlace])
    else:
        stopStations = set()

    startCr = cmdenv.credits - cmdenv.insurance

    # seed the route table with starting places
    routes = [
        Route(stations=[src], hops=[], jumps=[], startCr=startCr, gainCr=0)
            for src in cmdenv.origins
            if src not in avoidPlaces and src.system not in avoidPlaces
    ]
    numHops = cmdenv.hops
    lastHop = numHops - 1
    viaStartPos = 1 if origPlace else 0
    cmdenv.maxJumps = None

    cmdenv.DEBUG0(
                    "From {fromStn}, To {toStn}, Via {via}, "
                    "Cap {cap}, Credits {cr}, "
                    "Hops {hops}, Jumps/Hop {jumpsPer}, Ly/Jump {lyPer:.2f}"
                    "\n".format(
                        fromStn=origPlace.name() if origPlace else 'Anywhere',
                        toStn=str([s.name() for s in stopStations]) if stopStations else 'Anywhere',
                        via=';'.join([stn.name() for stn in viaSet]) or 'None',
                        cap=cmdenv.capacity,
                        cr=startCr,
                        hops=numHops,
                        jumpsPer=cmdenv.maxJumpsPer,
                        lyPer=cmdenv.maxLyPer,
                ))

    # Instantiate the calculator object
    calc = TradeCalc(tdb, cmdenv)

    cmdenv.DEBUG1("numHops {}, vias {}, adhocHops {}",
                numHops, len(viaSet), cmdenv.adhocHops)

    for hopNo in range(numHops):
        cmdenv.DEBUG1("Hop {}", hopNo)

        restrictTo = None
        if hopNo == lastHop and stopStations:
            restrictTo = stopStations
            ### TODO:
            ### if hopsLeft < len(viaSet):
            ###   ... only keep routes that include len(viaSet)-hopsLeft routes
            ### Thus: If you specify 5 hops via a,b,c and we are on hop 3, only keep
            ### routes that include a, b or c. On hop 4, only include routes that
            ### already include 2 of the vias, on hop 5, require all 3.
            if viaSet:
                routes = filterByVia(routes, viaSet, viaStartPos)
        elif len(viaSet) > cmdenv.adhocHops:
            restrictTo = viaSet

        routes = calc.getBestHops(routes, restrictTo=restrictTo)

    if viaSet:
        routes = filterByVia(routes, viaSet, viaStartPos)

    if not routes:
        raise NoDataError("No profitable trades matched your critera, or price data along the route is missing.")

    routes.sort()
    results.data = routes

    return results

######################################################################
# Transform result set into output

def render(results, cmdenv, tdb):
    from formatting import RowFormat, ColumnFormat

    routes = results.data

    for i in range(0, min(len(routes), cmdenv.routes)):
        print(routes[i].detail(detail=cmdenv.detail))

    # User wants to be guided through the route.
    if cmdenv.checklist:
        assert cmdenv.routes == 1
        cl = Checklist(tdb, cmdenv)
        cl.run(routes[0], cmdenv.credits)


