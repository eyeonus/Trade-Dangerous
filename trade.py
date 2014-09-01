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
        print("Temporary file ({}) already exists.".format(tmpPath))
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
        if args.debug: print("# Invoking [{}]".format('::'.join(editorCommandLine)))
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

        buildcache.processPricesFile(db=tdb.conn, pricesPath=tmpPath, stationID=stationID, debug=args.debug)

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

    if args.debug: print("# 'update' mode editor:{} station:{}".format(args.editor, args.station))

    station = tdb.lookupStation(args.station)
    stationID = station.ID

    if args.editor or args.sublime or args.notepad:
        return editUpdate(args, stationID)

    print("Guided mode not implemented yet. Try using --editor or --sublime.")


######################################################################
# main entry point

def main():
    global args, tdb

    parser = argparse.ArgumentParser(description='Trade run calculator', add_help=False)

    # Arguments common to all subparsers.
    commonArgs = parser.add_argument_group('Common Arguments')
    commonArgs.add_argument('-h', '--help', help='Show this help message and exit.', action=HelpAction, nargs=0)
    commonArgs.add_argument('--debug', '-w', help='Enable diagnostic output.', default=0, required=False, action='count')
    commonArgs.add_argument('--db', help='Specify location of the SQLite database. Default: {}'.format(TradeDB.defaultDB), type=existing_file_arg, default=TradeDB.defaultDB)

    # Split operations up in to several sub-commands.
    subparsers = parser.add_subparsers(dest='subparser', title='Commands')

    # "run" calculates a trade run.
    runParser = subparsers.add_parser('run', help='Calculate best trade run with a given set of constraints.', add_help=False)
    runReqArgs = runParser.add_argument_group('Required Arguments')
    runReqArgs.add_argument('--credits', metavar='CR', help='Number of credits to start with.', type=int, required=True)
    runOptArgs = runParser.add_argument_group('Optional Arguments')
    runOptArgs.add_argument('-h', '--help', help='Show this help message and exit.', action=HelpAction, nargs=0)
    runOptArgs.add_argument('--ship', metavar='name', help='Set capacity and max-ly-per from ship type.', type=str, required=False, default=None)
    runOptArgs.add_argument('--capacity', metavar='N', help='Maximum capacity of cargo hold.', type=int, required=False)
    runOptArgs.add_argument('--from', dest='origin', metavar='STATION', help='Specifies starting system/station.', required=False)
    runOptArgs.add_argument('--to', dest='dest', metavar='STATION', help='Specifies final system/station.', required=False)
    runOptArgs.add_argument('--via', dest='via', metavar='STATION', help='Require specified station to be en-route.', required=False)
    runOptArgs.add_argument('--avoid', dest='avoid', metavar='NAME', help='Exclude an item, system or station from the database. Partial matches allowed, e.g. "dom.ap" matches "Dom. Appliance".', required=False, action='append')
    runOptArgs.add_argument('--hops', metavar='N', help='Number of hops (station-to-station) to run. DEFAULT: 2', type=int, default=2, required=False)
    runOptArgs.add_argument('--jumps-per', metavar='N', dest='maxJumpsPer', help='Maximum jumps (system-to-system) per hop (station-to-station). DEFAULT: 2', type=int, default=2, required=False)
    runOptArgs.add_argument('--ly-per', metavar='N.NN', dest='maxLyPer', help='Maximum light years per individual jump.', type=float, default=None, required=False)
    runOptArgs.add_argument('--limit', metavar='N', help='Maximum units of any one cargo item to buy. DEFAULT: 0 (unlimited)', type=int, default=0, required=False)
    runOptArgs.add_argument('--unique', help='Only visit each station once.', default=False, required=False, action='store_true')
    runOptArgs.add_argument('--margin', metavar='N.NN', help='Reduce gains by this much to provide a margin of error for market fluctuations (e.g. 0.25 reduces gains by 1/4). 0<=m<=0.25. DEFAULT: 0.01', default=0.01, type=float, required=False)
    runOptArgs.add_argument('--insurance', metavar='CR', help='Reserve at least this many credits to cover insurance.', type=int, default=0, required=False)
    runOptArgs.add_argument('--routes', metavar='N', help='Maximum number of routes to show. DEFAULT: 1', type=int, default=1, required=False)
    runOptArgs.add_argument('--checklist', help='Provide a checklist flow for the route.', action='store_true', required=False, default=False)
    runOptArgs.add_argument('--x52-pro', dest='x52pro', help='Enable experimental X52 Pro MFD output.', action='store_true', required=False, default=False)
    runOptArgs.add_argument('--detail', '-v', help='Give detailed jump information for multi-jump hops.', default=0, required=False, action='count')
    runParser.set_defaults(proc=runCommand)

    # Provide the user a way to edit prices.
    updateParser = subparsers.add_parser('update', help='Provides a way to update the prices for a particular station.', add_help=False)
    updtReqArgs = updateParser.add_argument_group('Required Arguments')
    updtReqArgs.add_argument('station', type=str, help='Name of the station to update prices for.')
    updtOptArgs = updateParser.add_argument_group('Optional Arguments')
    updtOptArgs.add_argument('-h', '--help', help='Show this help message and exit.', action=HelpAction, nargs=0)
    updtOptArgs.add_argument('--editor', help='Generates a text file containing the prices for the station and loads it into the specified editor.', required=False, default=None, type=str)
    editorGroup = updateParser.add_mutually_exclusive_group()
    editorGroup.add_argument('--sublime', help='Like --editor but uses Sublime Text 3, which is nice.', required=False, default=False, action='store_true')
    editorGroup.add_argument('--notepad', help='Like --editor but uses Notepad.', required=False, default=False, action='store_true')
    updateParser.set_defaults(proc=updateCommand)

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
