#!/usr/bin/env python
#---------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
#---------------------------------------------------------------------
# TradeDangerous :: Command Line App :: Main Module
#
# TradeDangerous is a powerful set of tools for traders in Frontier
# Development's game "Elite: Dangerous". It's main function is
# calculating the most profitable trades between either individual
# stations or working out "profit runs".
#
# I wrote TD because I realized that the best trade run - in terms
# of the "average profit per stop" was rarely as simple as going
# Chango -> Dahan -> Chango.
#
# E:D's economy is complex; sometimes you can make the most profit
# by trading one item A->B and flying a second item B->A.
# But more often you need to fly multiple stations, especially since
# as you are making money different trade options are coming into
# your affordable range.
#
# END USERS: If you are a user looking to find out how to use TD,
# please consult the file "README.txt".
#
# DEVELOPERS: If you are a programmer who wants TD to do something
# cool, please see the TradeDB and TradeCalc modules. TD is designed
# to empower other programmers to do cool stuff.


######################################################################
# Imports

import argparse             # For parsing command line args.
import sys                  # Inevitably.
import time
import pathlib              # For path

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

# Multi-function display, optional
mfd = None

######################################################################
# Database and calculator modules.

from tradedb import TradeDB, AmbiguityError
from tradecalc import Route, TradeCalc, localedNo

tdb = None

######################################################################
# Helpers

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


class HelpAction(argparse.Action):
    """
        argparse action helper for printing the argument usage,
        because Python 3.4's argparse is ever so subtly very broken.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        parser.print_help()
        sys.exit(0)


class EditAction(argparse.Action):
    """
        argparse action that stores a value and also flags args._editing
    """
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, "_editing", True)
        setattr(namespace, self.dest, values or self.default)


class EditActionStoreTrue(argparse.Action):
    """
        argparse action that stores True but also flags args._editing
    """
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super(EditActionStoreTrue, self).__init__(option_strings, dest, nargs=0, **kwargs)
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, "_editing", True)
        setattr(namespace, self.dest, True)


def new_file_arg(string):
    """ argparse action handler for specifying a file that does not already exist. """

    path = pathlib.Path(string)
    if not path.exists(): return path
    sys.stderr.write("ERROR: Specified file, \"{}\", already exists.\n".format(path))
    sys.exit(errno.EEXIST)


def existing_file_arg(string):
    """ argparse action handler for selecting a file that already exists. """

    path = pathlib.Path(string)
    if path.exists(): return path
    import errno
    sys.stderr.write("ERROR: Specified file, \"{}\", does not exist.\n".format(path))
    sys.exit(errno.ENOENT)


######################################################################
# Checklist functions

def doStep(stepNo, action, detail=None, extra=None):
    stepNo += 1
    if mfd:
        mfd.display("#%d %s" % (stepNo, action), detail or "", extra or "")
    input("   %3d: %s: " % (stepNo, " ".join([item for item in [action, detail, extra] if item])))
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
        print(route.summary())
        print()

    for idx in range(lastHopIdx):
        hopNo = idx + 1
        if mfd: mfd.hopNo = hopNo
        cur, nxt, hop = stations[idx], stations[idx + 1], hops[idx]

        # Tell them what they need to buy.
        if args.detail:
            note("HOP %d of %d" % (hopNo, lastHopIdx))

        note("Buy at %s" % cur.str())
        for (item, qty) in sorted(hop[0], key=lambda item: item[1] * item[0].gainCr, reverse=True):
            stepNo = doStep(stepNo, 'Buy %d x' % qty, item.item[0], '@ %scr' % localedNo(item.costCr))
        if args.detail:
            stepNo = doStep(stepNo, 'Refuel')
        print()

        # If there is a next hop, describe how to get there.
        note("Fly %s" % " -> ".join([ jump.str() for jump in jumps[idx] ]))
        if idx < len(hops) and jumps[idx]:
            for jump in jumps[idx][1:]:
                stepNo = doStep(stepNo, 'Jump to', '%s' % (jump.str()))
        if args.detail:
            stepNo = doStep(stepNo, 'Dock at', '%s' % nxt.name())
        print()

        note("Sell at %s" % nxt.str())
        for (item, qty) in sorted(hop[0], key=lambda item: item[1] * item[0].gainCr, reverse=True):
            stepNo = doStep(stepNo, 'Sell %s x' % localedNo(qty), item.item[0], '@ %scr' % localedNo(item.costCr + item.gainCr))
        print()

        gainCr += hop[1]
        if args.detail and gainCr > 0:
            note("GAINED: %scr, CREDITS: %scr" % (localedNo(gainCr), localedNo(credits + gainCr)))

        if hopNo < lastHopIdx:
            print()
            print("--------------------------------------")
            print()

    if mfd:
        mfd.hopNo = None
        mfd.display('FINISHED', "+%scr" % localedNo(gainCr), "=%scr" % localedNo(credits + gainCr))
        mfd.attention(3)
        time.sleep(1.5)


######################################################################
# "run" command functionality.

def parseAvoids(avoidances):
    """
        Process a list of avoidances.
    """

    global avoidItems, avoidSystems, avoidStations

    # You can use --avoid to specify an item, system or station.
    for avoid in avoidances:
        # Is it an item?
        item, system, station = None, None, None
        try:
            item = tdb.listSearch('Item', avoid, tdb.items(), key=lambda item: item[0])
            avoidItems.append(item)
        except LookupError:
            pass
        # Is it a system perhaps?
        try:
            system = tdb.lookupSystem(avoid)
            avoidSystems.append(system)
        except LookupError:
            pass
        # Or perhaps it is a station
        try:
            station = tdb.lookupStation(avoid)
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

    if args.debug:
        print("Avoiding items %s, systems %s, stations %s" % (avoidItems, avoidSystems, avoidStations))


def processRunArguments(args):
    """
        Process arguments to the 'run' option.
    """

    global origins, originStation, finalStation, viaStation, maxUnits, originName, destName, viaName, mfd

    if args.hops < 1:
        raise CommandLineError("Minimum of 1 hop required")
    if args.hops > 64:
        raise CommandLineError("Too many hops without more optimization")

    if args.avoid:
        parseAvoids(args.avoid)

    if args.origin:
        originName = args.origin
        originStation = tdb.lookupStation(originName)
        origins = [ originStation ]
    else:
        origins = [ station for station in tdb.stationByID.values() ]

    if args.dest:
        destName = args.dest
        finalStation = tdb.lookupStation(destName)
        if args.hops == 1 and originStation and finalStation and originStation == finalStation:
            raise CommandLineError("More than one hop required to use same from/to destination")

    if args.via:
        if args.hops < 2:
            raise CommandLineError("Minimum of 2 hops required for a 'via' route")
        viaName = args.via
        viaStation = tdb.lookupStation(viaName)
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
        ship = tdb.lookupShip(args.ship)
        args.ship = ship
        if args.capacity is None: args.capacity = ship.capacity
        if args.maxLyPer is None: args.maxLyPer = ship.maxLyFull
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

    if args.unique and args.hops >= len(tdb.stationByID):
        raise CommandLineError("Requested unique trip with more hops than there are stations...")
    if args.unique:
        if ((originStation and originStation == finalStation) or
                (originStation and originStation == viaStation) or
                 (viaStation and viaStation == finalStation)):
            raise CommandLineError("from/to/via repeat conflicts with --unique")

    if args.checklist and args.routes > 1:
        raise CommandLineError("Checklist can only be applied to a single route.")

    if args.x52pro:
        from mfd import X52ProMFD
        mfd = X52ProMFD()

    if mfd:
        mfd.display('TradeDangerous', 'CALCULATING')


def runCommand(args):
    """ Calculate trade runs. """

    global tdb

    if args.debug: print("# 'run' mode")

    processRunArguments(args)

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
        print("%d cap, %d hops, max %d jumps/hop and max %0.2f ly/jump" % (args.capacity, numHops, args.maxJumpsPer, args.maxLyPer))
        print("--------------------------------------------------------")
        print()

    # Instantiate the calculator object
    calc = TradeCalc(tdb, debug=args.debug, capacity=args.capacity, maxUnits=maxUnits, margin=args.margin, unique=args.unique)

    # Build a single list of places we want to avoid
    # TODO: Keep these seperate because we wind up spending
    # time breaking the list down in getDestinations.
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
                                  maxJumpsPer=args.maxJumpsPer, maxLyPer=args.maxLyPer)

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


######################################################################
# "update" command functionality.

def editUpdate(args, stationID):
    """
        Dump the price data for a specific station to a file and
        launch the user's text editor to let them make changes
        to the file.

        If the user makes changes, re-load the file, update the
        database and regenerate the master .prices file.
    """

    if args.debug: print("# 'update' mode with editor. editor:{} station:{}".format(args.editor, args.station))

    from data import buildcache
    from data import prices
    import subprocess
    import os

    editor, editorArgs = args.editor, []
    if args.sublime:
        if args.debug: print("# Sublime mode")
        if not editor:
            if args.debug: print("# Locating sublime")
            if "SUBLIME_EDITOR" in os.environ:
                editor = os.environ["SUBLIME_EDITOR"]
            else:
                editor = "C:\\Program Files\\Sublime Text 3\\sublime_text.exe"
                if not pathlib.Path(editor).exists():
                    editor = "C:\\Program Files (x86)\\Sublime Text 3\\sublime_text.exe"
                    if not pathlib.Path(editor).exists():
                        print("ERROR: --sublime specified but could not find your Sublime Text 3 installation. Either specify the path to your editor with --editor or set the SUBLIME_EDITOR environment variable.")
        editorArgs += [ "--wait" ]
    elif args.notepad:
        if args.debug: print("# Notepad mode")
        editor = "notepad.exe"  # herp

    try:
        envArgs = os.environ["EDITOR_ARGS"]
        if envArgs: editorArgs += envArgs.split(' ')
    except KeyError: pass

    # Create a temporary text file with a list of the price data.
    tmpPath = pathlib.Path("prices.tmp")
    if tmpPath.exists():
        print("ERROR: Temporary file ({}) already exists.".format(tmpPath))
        sys.exit(1)
    absoluteFilename = None
    try:
        # Open the file and dump data to it.
        with tmpPath.open("w") as tmpFile:
            # Remember the filename so we know we need to delete it.
            absoluteFilename = str(tmpPath.resolve())
            prices.dumpPrices(args.db, file=tmpFile, stationID=stationID, debug=args.debug)

        # Stat the file so we can determine if the user writes to it.
        # Use the most recent create/modified timestamp.
        preStat = tmpPath.stat()
        preStamp = max(preStat.st_mtime, preStat.st_ctime)

        # Launch the editor
        editorCommandLine = [ editor ] + editorArgs + [ absoluteFilename ]
        if args.debug: print("# Invoking [{}]".format(str(editorCommandLine)))
        result = subprocess.call(editorCommandLine)
        if result != 0:
            print("NOTE: Edit failed ({}), nothing to import.".format(result))
            sys.exit(1)

        # Did they update the file? Some editors destroy the file and rewrite it,
        # other files just write back to it, and some OSes do weird things with
        # these timestamps. That's why we have to use both mtime and ctime.
        postStat = tmpPath.stat()
        postStamp = max(postStat.st_mtime, postStat.st_ctime)

        if postStamp == preStamp:
            import random
            print("- No changes detected - doing nothing. {}".format(random.choice([
                    "Brilliant!", "I'll get my coat.", "I ain't seen you.", "You ain't seen me", "... which was nice", "Bingo!", "Scorchio!", "Boutros, boutros, ghali!", "I'm Ed Winchester!", "Suit you, sir! Oh!"
                ])))
            sys.exit(0)

        if args.debug:
            print("# File changed - importing data.")

        buildcache.processPricesFile(db=tdb.getDB(), pricesPath=tmpPath, stationID=stationID, debug=args.debug)

        # If everything worked, we need to re-build the prices file.
        if args.debug:
            print("# Update complete, regenerating .prices file")

        with tdb.pricesPath.open("w") as pricesFile:
            prices.dumpPrices(args.db, withModified=True, file=pricesFile, debug=args.debug)

        # Update the DB file so we don't regenerate it.
        pathlib.Path(args.db).touch()

    finally:
        # If we created the file, we delete the file.
        if absoluteFilename: tmpPath.unlink()


def updateCommand(args):
    """
        Allow the user to update the prices database.
    """

    station = tdb.lookupStation(args.station)
    stationID = station.ID

    if args._editing:
        # User specified one of the options to use an editor.
        return editUpdate(args, stationID)

    if args.debug: print('# guided "update" mode station:{}'.format(args.station))


    print("Guided mode not implemented yet. Try using --editor, --sublime or --notepad")


######################################################################
# main entry point

class ParseArgument(object):
    """
        Provides argument forwarding so that 'makeSubParser' can take function-like arguments.
    """
    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs


def makeSubParser(subparsers, name, help, commandFunc, arguments=None, switches=None):
    """
        Provide a normalized sub-parser for a specific command. This helps to
        make it easier to keep the command lines consistent and makes the calls
        to build them easier to write/read.
    """

    subParser = subparsers.add_parser(name, help=help, add_help=False)

    def addArguments(group, options, required, topGroup=None):
        """
            Registers a list of options to the specified group. Nodes
            are either an instance of ParseArgument or a list of
            ParseArguments. The list form is considered to be a
            mutually exclusive group of arguments.
        """

        for option in options:
            # lists indicate mutually exclusive subgroups
            if isinstance(option, list):
                addArguments((topGroup or group).add_mutually_exclusive_group(), option, required, topGroup=group)
            else:
                assert not required in option.kwargs
                if option.args[0][0] == '-':
                    group.add_argument(*(option.args), required=required, **(option.kwargs))
                else:
                    group.add_argument(*(option.args), **(option.kwargs))

    if arguments:
        argParser = subParser.add_argument_group('Required Arguments')
        addArguments(argParser, arguments, True)

    switchParser = subParser.add_argument_group('Optional Switches')
    switchParser.add_argument('-h', '--help', help='Show this help message and exit.', action=HelpAction, nargs=0)
    addArguments(switchParser, switches, False)

    subParser.set_defaults(proc=commandFunc)

    return argParser


def main():
    global args, tdb

    parser = argparse.ArgumentParser(description='Trade run calculator', add_help=False, epilog='For help on a specific command, use the command followed by -h.')
    parser.set_defaults(_editing=False)

    # Arguments common to all subparsers.
    commonArgs = parser.add_argument_group('Common Switches')
    commonArgs.add_argument('-h', '--help', help='Show this help message and exit.', action=HelpAction, nargs=0)
    commonArgs.add_argument('--debug', '-w', help='Enable diagnostic output.', default=0, required=False, action='count')
    commonArgs.add_argument('--db', help='Specify location of the SQLite database. Default: {}'.format(TradeDB.defaultDB), type=existing_file_arg, default=TradeDB.defaultDB)

    subparsers = parser.add_subparsers(dest='subparser', title='Commands')

    # "run" calculates a trade run.
    runParser = makeSubParser(subparsers, 'run', 'Calculate best trade run.', runCommand,
        arguments = [
            ParseArgument('--credits', help='Starting credits.', metavar='CR', type=int)
        ],
        switches = [
            ParseArgument('--ship', help='Set capacity and ly-per from ship type.', metavar='name', type=str),
            ParseArgument('--capacity', help='Maximum capacity of cargo hold.', metavar='N', type=int),
            ParseArgument('--from', help='Starting system/station.', metavar='STATION', dest='origin'),
            ParseArgument('--to', help='Final system/station.', metavar='STATION', dest='dest'),
            ParseArgument('--via', help='Require specified station to en-route.', metavar='STATION'),
            ParseArgument('--avoid', help='Exclude an item, system or station from trading. Partial matches allowed, e.g. "dom.App" or "domap" matches "Dom. Appliances".', action='append'),
            ParseArgument('--hops', help='Number of hops (station-to-station) to run.', metavar='N', type=int, default=2),
            ParseArgument('--jumps-per', help='Maximum number of jumps (system-to-system) per hop.', metavar='N', dest='maxJumpsPer', type=int, default=2),
            ParseArgument('--ly-per', help='Maximum light years per jump.', metavar='N.NN', type=float, dest='maxLyPer'),
            ParseArgument('--limit', help='Maximum units of any one cargo item to buy (0: unlimited).', metavar='N', type=int),
            ParseArgument('--unique', help='Only visit each station once.', action='store_true', default=False),
            ParseArgument('--margin', help='Reduce gains made on each hop to provide a margin of error for market fluctuations (e.g: 0.25 reduces gains by 1/4). 0<: N<: 0.25.', metavar='N.NN', type=float, default=0.00),
            ParseArgument('--insurance', help='Reserve at least this many credits to cover insurance.', metavar='CR', type=int, default=0),
            ParseArgument('--routes', help='Maximum number of routes to show. DEFAULT: 1', metavar='N', type=int, default=1),
            ParseArgument('--checklist', help='Provide a checklist flow for the route.', action='store_true', default=False),
            ParseArgument('--x52-pro', help='Enable experimental X52 Pro MFD output.', action='store_true', dest='x52pro', default=False),
            ParseArgument('--detail', '-v', help='Give detailed jump information for multi-jump hops.', default=0, action='count')
        ]
    )

    # "update" provides the user a way to edit prices.
    updateParser = makeSubParser(subparsers, 'update', 'Provides a way to update the prices for a particular station.', updateCommand,
        arguments = [
            ParseArgument('station', help='Name of the station to update.', type=str)            
        ],
        switches = [
            ParseArgument('--editor', help='Generates a text file containing the prices for the station and loads it into the specified editor.', default=None, type=str, action=EditAction),
            [   # Mutually exclusive group:
                ParseArgument('--sublime', help='Like --editor but uses Sublime Text 3, which is nice.', action=EditActionStoreTrue),
                ParseArgument('--notepad', help='Like --editor but uses Notepad.', action=EditActionStoreTrue),
            ]
        ]
    )

    args = parser.parse_args()
    if not 'proc' in args:
        parser.print_help()
        print()
        print("As of TradeDangerous v3.01 you MUST specify a command from the list above.")
        import pprint
        print("For help on a specific command, type: %s {command} -h" % (parser.prog))
        sys.exit(1)

    # load the database
    tdb = TradeDB(debug=args.debug, dbFilename=args.db)

    # run the commands
    return args.proc(args)


if __name__ == "__main__":
    try:
        main()
    except (CommandLineError, AmbiguityError) as e:
        print("%s: error: %s" % (sys.argv[0], str(e)))
    if mfd:
        mfd.finish()
