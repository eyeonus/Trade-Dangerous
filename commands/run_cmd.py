from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from commands.exceptions import *

######################################################################
# Parser config

help='Calculate best trade run.'
name='run'
epilog=None
arguments = [
    ParseArgument('--credits', help='Starting credits.', metavar='CR', type=int)
]
switches = [
    ParseArgument('--ship',
            help='Set capacity and ly-per from ship type.',
            metavar='shiptype',
            type=str,
        ),
    ParseArgument('--capacity',
            help='Maximum capacity of cargo hold.',
            metavar='N',
            type=int,
        ),
    ParseArgument('--from',
            help='Starting system/station.',
            dest='origin',
            metavar='STATION',
        ),
    ParseArgument('--to',
            help='Final system/station.',
            dest='dest',
            metavar='STATION',
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
    ParseArgument('--ly-per',
            help='Maximum light years per jump.',
            dest='maxLyPer',
            metavar='N.NN',
            type=float,
        ),
    ParseArgument('--limit',
            help='Maximum units of any one cargo item to buy (0: unlimited).',
            metavar='N',
            type=int,
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

        printHeading("(i) BEGINNING CHECKLIST FOR {} (i)".format(route.str()))
        print()

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
                self.doStep('Buy {} x'.format(qty), trade.name(), '@ {}cr'.format(localedNo(trade.costCr)))
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
                self.doStep('Sell {} x'.format(localedNo(qty)), trade.name(), '@ {}cr'.format(localedNo(trade.costCr + trade.gainCr)))
            print()

            gainCr += hop[1]
            if cmdenv.detail and gainCr > 0:
                self.note("GAINED: {}cr, CREDITS: {}cr".format(localedNo(gainCr), localedNo(credits + gainCr)))

            if hopNo < lastHopIdx:
                print("\n--------------------------------------\n")

        if mfd:
            mfd.display('FINISHED', "+{}cr".format(localedNo(gainCr)), "={}cr".format(localedNo(credits + gainCr)))
            mfd.attention(3)
            time.sleep(1.5)


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

    if cmdenv.startStation:
        cmdenv.origins = [ cmdenv.startStation ]
    else:
        cmdenv.origins = [ station for station in tdb.stationByID.values() ]

    if cmdenv.stopStation:
        if cmdenv.hops == 1 and cmdenv.startStation:
            if cmdenv.startStation == cmdenv.stopStation:
                raise CommandLineError("Same to/from; more than one hop required.")
    else:
        cmdenv.stopStation = None

    viaSet = cmdenv.viaSet = set(cmdenv.viaStations)
    for station in viaSet:
        if station.itemCount == 0:
            raise NoDataError("No price data available for via station {}.".format(
                                station.name()))

    unspecifiedHops = (
        cmdenv.hops +
            (0 if cmdenv.startStation else 1) -(1 if cmdenv.stopStation else 0)
    )
    if len(viaSet) > unspecifiedHops:
        raise CommandLineError("Too many vias: {} stations vs {} hops available.".format(
                len(viaSet), unspecifiedHops
        ))
    cmdenv.unspecifiedHops = unspecifiedHops

    if cmdenv.capacity is None:
        raise CommandLineError("Missing '--capacity' or '--ship' argument")
    if cmdenv.maxLyPer is None:
        raise CommandLineError("Missing '--ly-per' or '--ship' argument")
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
        startConflict = (startStn and (startStn == stop or startStn in viaSet))
        stopConflict  = (stop and stop in viaSet)
        if startConflict or stopConflict:
            raise CommandLineError("from/to/via repeat conflicts with --unique")

    if cmdenv.mfd:
        cmdenv.mfd.display("Loading Trades")
    tdb.loadTrades()

    if startStn and startStn.itemCount == 0:
        raise NoDataError("Start station {} doesn't have any price data.".format(
                            startStn.name()))
    if stopStn and stopStn.itemCount == 0:
        raise NoDataError("End station {} doesn't have any price data.".format(
                            stopStn.name()))
    if stopStn and cmdenv.hops == 1 and startStn and not stopStn in startStn.tradingWith:
        raise CommandLineError("No profitable items found between {} and {}".format(
                                startStn.name(), stopStn.name()))
    if startStn and len(startStn.tradingWith) == 0:
        raise NoDataError("No data found for potential buyers for items from {}.".format(
                            startStn.name()))

######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    from commands.commandenv import ResultRow

    cmdenv.DEBUG(1, "'run' mode")

    if tdb.tradingCount == 0:
        raise NoDataError("Database does not contain any profitable trades.")

    validateRunArguments(tdb, cmdenv)

    from tradecalc import TradeCalc, Route

    startStn, stopStn, viaSet = cmdenv.startStation, cmdenv.stopStation, cmdenv.viaSet
    avoidSystems = cmdenv.avoidSystems
    avoidStations = cmdenv.avoidStations

    startCr = cmdenv.credits - cmdenv.insurance
    routes = [
        Route(stations=[src], hops=[], jumps=[], startCr=startCr, gainCr=0)
            for src in cmdenv.origins
            if not (src in avoidStations or
                    src.system in avoidSystems)
    ]
    numHops = cmdenv.hops
    lastHop = numHops - 1
    viaStartPos = 1 if startStn else 0
    cmdenv.maxJumps = None

    if cmdenv.detail:
        print( "From {fromStn}, To {toStn}, Via {via}, "
                    "Cap {cap}, Credits {cr}, "
                    "Hops {hops}, Jumps/Hop {jumpsPer}, Ly/Jump {lyPer:.2f}"
                    "\n".format(
                        fromStn=startStn.name() if startStn else 'Anywhere',
                        toStn=stopStn.name() if stopStn else 'Anywhere',
                        via=';'.join([stn.name() for stn in viaSet]) or 'None',
                        cap=cmdenv.capacity,
                        cr=startCr,
                        hops=numHops,
                        jumpsPer=cmdenv.maxJumpsPer,
                        lyPer=cmdenv.maxLyPer,
                ))

    # Instantiate the calculator object
    calc = TradeCalc(tdb, cmdenv)

    cmdenv.DEBUG(1, "unspecified hops {}, numHops {}, viaSet {}",
                cmdenv.unspecifiedHops, numHops, len(viaSet))

    for hopNo in range(numHops):
        cmdenv.DEBUG(1, "Hop {}", hopNo)

        restrictTo = None
        if hopNo == lastHop and stopStn:
            restrictTo = set([stopStn])
            ### TODO:
            ### if hopsLeft < len(viaSet):
            ###   ... only keep routes that include len(viaSet)-hopsLeft routes
            ### Thus: If you specify 5 hops via a,b,c and we are on hop 3, only keep
            ### routes that include a, b or c. On hop 4, only include routes that
            ### already include 2 of the vias, on hop 5, require all 3.
            if viaSet:
                routes = [ route for route in routes if viaSet & set(route.route[viaStartPos:]) ]
        elif cmdenv.unspecifiedHops == len(viaSet):
            # Everywhere we're going is in the viaSet.
            restrictTo = viaSet

        routes = calc.getBestHops(routes, restrictTo=restrictTo)

    if viaSet:
        routes = [ route for route in routes if viaSet & set(route.route[viaStartPos:]) ]

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
        cl = Checklist(tdb, cmdenv.mfd)
        cl.run(routes[0], cmdenv.credits)


