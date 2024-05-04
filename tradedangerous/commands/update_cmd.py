# Deprecated
from .parsing import MutuallyExclusiveGroup, ParseArgument
from ..tradeexcept import TradeException
from .exceptions import CommandLineError
from ..tradedb import System
from .. import prices, cache
import subprocess
import os
import sys
import pathlib

######################################################################
# Parser config

help = 'Update prices for a station.'
name = 'update'
epilog = ("Generates a human-readable version of the price list for a given station "
            "and opens it in the specified text editor.\n"
            "The format is intended to closely resemble the presentation of the "
            "market in-game. If you change the order items are listed in, "
            "the order will be kept for future edits, making it easier to quickly "
            "check for changes.")
wantsTradeDB = True
arguments = [
    ParseArgument('starting', help = 'Name of the station to update.', type = str)
]
switches = [
    ParseArgument('--timestamps', '-T',
            help = '[Text editing] Includes timestamps in the update.',
            action = 'store_true',
            default = False,
    ),
    ParseArgument('--all', '-A',
            help = 'List all known items.',
            action = 'store_true',
            default = False,
    ),
    ParseArgument('--use-demand', '-D',
            help = 'Unlock the "Demand" column in the GUI.',
            action = 'store_true',
            dest = 'useDemand',
            default = False,
    ),
    ParseArgument('--force-na', '-0',
            help = "Forces 'unk' supply to become 'n/a' by default",
            action = 'store_true',
            default = False,
            dest = 'forceNa',
    ),
    ParseArgument('--height', '-H',
            help = "[GUI] Specify height of the window",
            type = int,
            default = 800,
    ),
    ParseArgument('--front', '-F',
            help = (
                "[GUI] Keep the GUI infront of other windows; "
                "this allows you to put the window infront of "
                "the game UI if you run the game in windowed mode."
                ),
            action = 'store_true',
            default = False,
            dest = 'alwaysOnTop',
    ),
    ParseArgument('--window-x', '-wx',
            help = (
                "[GUI] Specify the window X position "
                "Use a negative value for a right-of-screen relative offset"
                ),
            default = -1,
            dest = 'windowX',
            type = int,
    ),
    ParseArgument('--window-y', '-wy',
            help = (
                "[GUI] Specify the window U position "
                "Use a negative value for a bottom-of-screen relative offset"
                ),
            default = 1,
            dest = 'windowY',
            type = int,
    ),
    MutuallyExclusiveGroup(
        ParseArgument('--gui', '-G',
                help = "Use the experimental built-in GUI",
                action = 'store_true',
                default = False,
                dest = 'gui',
        ),
        ParseArgument('--editor',
                help = 'Generates a text file containing the prices for '
                        'the station and loads it into the specified '
                        'text editor for you.',
                default = None,
                type = str,
        ),
        ParseArgument('--sublime',
                help = 'Like --editor but uses Sublime Text (2 or 3).',
                action = 'store_const', const = 'sublime', dest = 'editing',
        ),
        ParseArgument('--notepad',
                help = 'Like --editor but uses Notepad.',
                action = 'store_const', const = 'notepad', dest = 'editing',
        ),
        ParseArgument('--npp',
                help = 'Like --editor but uses Notepad++.',
                action = 'store_const', const = 'npp', dest = 'editing',
        ),
        ParseArgument('--vim',
                help = 'Like --editor but uses vim.',
                action = 'store_const', const = 'vim', dest = 'editing',
        ),
    )
]

######################################################################
# Helpers


class TemporaryFileExistsError(TradeException):
    pass


def getTemporaryPath(cmdenv):
    tmpPath = pathlib.Path("prices.tmp")
    if tmpPath.exists():
        if not cmdenv.force:
            raise TemporaryFileExistsError(
                    "Temporary file already exists: {}\n"
                    "(Check you aren't already editing in another window"
                        .format(tmpPath)
            )
        tmpPath.unlink()
    return tmpPath


def saveTemporaryFile(tmpPath):
    if tmpPath.exists():
        lastPath = pathlib.Path("prices.last")
        if lastPath.exists():
            lastPath.unlink()
        tmpPath.rename(lastPath)


def saveCopyOfChanges(cmdenv, dbFilename, stationID):
    if "APPEND_PRICES" in os.environ:
        mode = "a"
    else:
        mode = "w"
    dumpPath = pathlib.Path("updated.prices")
    with dumpPath.open(mode, encoding = 'utf-8') as dumpFile:
        # Remember the filename so we know we need to delete it.
        prices.dumpPrices(dbFilename,
                prices.Element.full | prices.Element.blanks,
                file = dumpFile,
                stationID = stationID,
                defaultZero = False,
                debug = cmdenv.debug,
        )
    if not cmdenv.quiet:
        print("- Copy of changes saved as '{}'".format(
                str(dumpPath)
        ))


def getEditorPaths(cmdenv, editorName, envVar, windowsFolders, winExe, nixExe):
    cmdenv.DEBUG0("Locating {} editor", editorName)
    try:
        return os.environ[envVar]
    except KeyError:
        pass
    
    paths = []
    
    import platform
    system = platform.system()
    if system == 'Windows':
        binary = winExe
        for folder in ["Program Files", "Program Files (x86)"]:
            for version in windowsFolders:
                paths.append("{}\\{}\\{}".format(os.environ['SystemDrive'], folder, version))
    else:
        binary = nixExe
    
    try:
        paths += os.environ['PATH'].split(os.pathsep)
    except KeyError:
        pass
    
    for path in paths:
        candidate = os.path.join(path, binary)
        try:
            if pathlib.Path(candidate).exists():
                return candidate
        except OSError:
            pass
    
    raise CommandLineError(
        "ERROR: Unable to locate {} editor.\n"
        "Either specify the path to your editor with --editor "
        "or set the {} environment variable to point to it."
            .format(editorName, envVar)
    )


def editUpdate(tdb, cmdenv, stationID):
    """
        Dump the price data for a specific station to a file and
        launch the user's text editor to let them make changes
        to the file.
        
        If the user makes changes, re-load the file, update the
        database and regenerate the master .prices file.
    """
    
    cmdenv.DEBUG0("'update' mode with editor. editor:{} station:{}",
                    cmdenv.editor, cmdenv.origin)
    
    editor, editorArgs = cmdenv.editor, []
    if cmdenv.editing == 'sublime':
        cmdenv.DEBUG0("Sublime mode")
        editor = editor or \
                getEditorPaths(cmdenv,
                        "sublime", "SUBLIME_EDITOR",
                        ["Sublime Text 3", "Sublime Text 2"],
                        "sublime_text.exe",
                        "subl"
                )
        editorArgs += [ "--wait" ]
    elif cmdenv.editing == 'npp':
        cmdenv.DEBUG0("Notepad++ mode")
        editor = editor or \
                getEditorPaths(cmdenv,
                        "notepad++", "NOTEPADPP_EDITOR",
                        ["Notepad++"],
                        "notepad++.exe",
                        "notepad++"
                )
        if not cmdenv.quiet:
            print("NOTE: "
                    "You'll need to exit Notepad++ when you are done.")
    elif cmdenv.editing == "vim":
        cmdenv.DEBUG0("VI iMproved mode")
        if not editor:
            # Hack... Hackity hack, hack, hack.
            # This has a disadvantage in that: we don't check for just "vim" (no .exe) under Windows
            vimDirs = [
                    "Git\\share\\vim\\vim{}".format(vimVer)
                    for vimVer in range(70, 75)
            ]
            editor = getEditorPaths(cmdenv,
                    "vim",
                    "EDITOR",
                    vimDirs,
                    "vim.exe",
                    "vim"
            )
    elif cmdenv.editing == "notepad":
        cmdenv.DEBUG0("Notepad mode")
        editor = editor or "notepad.exe"  # herp
    
    try:
        envArgs = os.environ["EDITOR_ARGS"]
        if envArgs:
            editorArgs += envArgs.split(' ')
    except KeyError:
        pass
    
    # Create a temporary text file with a list of the price data.
    tmpPath = getTemporaryPath(cmdenv)
    
    absoluteFilename = None
    dbFilename = tdb.dbFilename
    try:
        elementMask = prices.Element.basic | prices.Element.supply
        if cmdenv.timestamps:
            elementMask |= prices.Element.timestamp
        if cmdenv.all:
            elementMask |= prices.Element.blanks
        # Open the file and dump data to it.
        with tmpPath.open("w", encoding = 'utf-8') as tmpFile:
            # Remember the filename so we know we need to delete it.
            absoluteFilename = str(tmpPath.resolve())
            prices.dumpPrices(dbFilename, elementMask,
                    file = tmpFile,
                    stationID = stationID,
                    defaultZero = cmdenv.forceNa,
                    debug = cmdenv.debug
            )
        
        # Stat the file so we can determine if the user writes to it.
        # Use the most recent create/modified timestamp.
        preStat = tmpPath.stat()
        preStamp = max(preStat.st_mtime, preStat.st_ctime)
        
        # Launch the editor
        editorCommandLine = [ editor ] + editorArgs + [ absoluteFilename ]
        cmdenv.DEBUG0("Invoking [{}]", ' '.join(editorCommandLine))
        try:
            result = subprocess.call(editorCommandLine)
        except FileNotFoundError:
            raise CommandLineError(
                        "Unable to launch requested editor: {}"
                            .format(editorCommandLine)
            )
        if result != 0:
            raise CommandLineError(
                    "NO DATA IMPORTED: "
                    "Your editor exited with a 'failed' exit code ({})"
                        .format(result)
            )
        
        # Did they update the file? Some editors destroy the file and rewrite it,
        # other files just write back to it, and some OSes do weird things with
        # these timestamps. That's why we have to use both mtime and ctime.
        postStat = tmpPath.stat()
        postStamp = max(postStat.st_mtime, postStat.st_ctime)
        
        if postStamp == preStamp:
            import random
            print("- No changes detected - doing nothing. {}".format(
                    random.choice([
                        "Brilliant!",
                        "I'll get my coat.",
                        "I ain't seen you.",
                        "You ain't seen me",
                        "... which was nice",
                        "Bingo!",
                        "Scorchio!",
                        "Boutros, boutros, ghali!",
                        "I'm Ed Winchester!",
                        "Suit you, sir! Oh!"
                    ])
            ))
        else:
            cache.importDataFromFile(tdb, cmdenv, tmpPath)
            saveCopyOfChanges(cmdenv, dbFilename, stationID)
        
        tmpPath.unlink()
        tmpPath = None
    
    except Exception as e:
        print("ERROR:", e)
        print()
        print("*** YOUR UPDATES WILL BE SAVED AS {} ***".format(
                "prices.last"
        ))
        # Save a copy
        if absoluteFilename and tmpPath:
            saveTemporaryFile(tmpPath)
        if "EXCEPTIONS" in os.environ:
            raise e


def guidedUpdate(tdb, cmdenv):
    dbFilename = tdb.dbFilename
    stationID = cmdenv.startStation.ID
    tmpPath = getTemporaryPath(cmdenv)
    
    cur = tdb.query("""
        SELECT  JULIANDAY('now') - JULIANDAY(MIN(modified)),
                JULIANDAY('now') - JULIANDAY(MAX(modified))
          FROM  StationItem
         WHERE  station_id = ?
    """, [stationID])
    oldest, newest = cur.fetchone()
    if oldest and newest:
        cmdenv.NOTE(
            "Current data {:.2f}-{:.2f} days old.",
            oldest, newest,
        )
    
    from .update_gui import render
    try:
        render(tdb, cmdenv, tmpPath)
        cmdenv.DEBUG0("Got results, importing")
        cache.importDataFromFile(tdb, cmdenv, tmpPath)
        
        saveCopyOfChanges(cmdenv, dbFilename, stationID)
        
        tmpPath.unlink()
        tmpPath = None
    
    except Exception as e:
        print("ERROR:", e)
        print()
        print("*** YOUR UPDATES WILL BE SAVED AS {} ***".format(
                "prices.last"
        ))
        
        if tmpPath:
            saveTemporaryFile(tmpPath)
        if "EXCEPTIONS" in os.environ:
            raise e

######################################################################
# Perform query and populate result set


def run(results, cmdenv, tdb):
    place = cmdenv.origPlace
    if isinstance(place, System):
        system = place
        if len(system.stations) != 1:
            raise CommandLineError(
                    "'{}' is a system, not a station.".format(
                        system.name()
            ))
        cmdenv.startStation = system.stations[0]
    else:
        cmdenv.startStation = place
    
    if cmdenv.gui or (not cmdenv.editor and not cmdenv.editing):
        if not cmdenv.quiet:
            print(
                    "NOTE:\n"
                    ". Press CTRL-C here to abort edit, otherwise "
                    "just close the update window to save.\n"
                    ". '-F' makes the window show in-front of the "
                    "E:D Window.\n"
                    ". '-A' forces all items to be listed.\n",
                    file = sys.stderr
            )
        guidedUpdate(tdb, cmdenv)
    else:
        # User specified one of the options to use an editor.
        editUpdate(tdb, cmdenv, cmdenv.startStation.ID)
    
    return None
