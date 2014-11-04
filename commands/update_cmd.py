from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from tradeexcept import TradeException
from commands.exceptions import CommandLineError
import prices
import buildcache
import subprocess
import os
import pathlib

######################################################################
# Parser config

help='Update prices for a station.'
name='update'
epilog=("Generates a human-readable version of the price list for a given station "
            "and opens it in the specified text editor.\n"
            "The format is intended to closely resemble the presentation of the "
            "market in-game. If you change the order items are listed in, "
            "the order will be kept for future edits, making it easier to quickly "
            "check for changes.")
wantsTradeDB=True
arguments = [
    ParseArgument('origin', help='Name of the station to update.', type=str)
]
switches = [
    ParseArgument('--editor',
            help='Generates a text file containing the prices for the station and '
                    'loads it into the specified editor for you.',
            default=None,
            type=str,
        ),
    ParseArgument('--supply', '-S', 
            help='Includes demand and stock (supply) values in the update.',
            action='store_true',
            default=False,
        ),
    ParseArgument('--timestamps', '-T', 
            help='Includes timestamps in the update.',
            action='store_true',
            default=False,
        ),
    ParseArgument('--force-na', '-0', 
            help="Forces 'unk' supply to become 'n/a' by default",
            action='store_true',
            default=False,
            dest='forceNa',
        ),
    MutuallyExclusiveGroup(
        ParseArgument('--sublime', 
                help='Like --editor but uses Sublime Text (2 or 3), which is nice.',
                action='store_const', const='sublime', dest='editing',
            ),
        ParseArgument('--notepad', 
                help='Like --editor but uses Notepad.',
                action='store_const', const='notepad', dest='editing',
            ),
        ParseArgument('--npp',     
                help='Like --editor but uses Notepad++.',
                action='store_const', const='npp', dest='editing',
            ),
        ParseArgument('--vim',     
                help='Like --editor but uses vim.',
                action='store_const', const='vim', dest='editing',
            ),
    )
]

######################################################################
# Helpers

class TemporaryFileExistsError(TradeException):
    pass


def getEditorPaths(cmdenv, editorName, envVar, windowsFolders, winExe, nixExe):
    cmdenv.DEBUG(0, "Locating {} editor", editorName)
    try:
        return os.environ[envVar]
    except KeyError: pass

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
    except KeyError: pass

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


def importDataFromFile(cmdenv, tdb, path, stationID, dbFilename):
    buildcache.processPricesFile(cmdenv,
                     db=tdb.getDB(),
                     pricesPath=path,
                     stationID=stationID,
                     defaultZero=cmdenv.forceNa
            )

    # If everything worked, we need to re-build the prices file.
    cmdenv.DEBUG(0, "Update complete, regenerating .prices file")

    with tdb.pricesPath.open("w") as pricesFile:
        prices.dumpPrices(dbFilename, prices.Element.full, file=pricesFile, debug=cmdenv.debug)

        # Update the DB file so we don't regenerate it.
        pathlib.Path(dbFilename).touch()


def editUpdate(tdb, cmdenv, stationID):
    """
        Dump the price data for a specific station to a file and
        launch the user's text editor to let them make changes
        to the file.

        If the user makes changes, re-load the file, update the
        database and regenerate the master .prices file.
    """

    cmdenv.DEBUG(0, "'update' mode with editor. editor:{} station:{}",
                    cmdenv.editor, cmdenv.origin)

    editor, editorArgs = cmdenv.editor, []
    if cmdenv.editing == 'sublime':
        cmdenv.DEBUG(0, "Sublime mode")
        editor = editor or getEditorPaths(cmdenv, 
                            "sublime", "SUBLIME_EDITOR",
                            ["Sublime Text 3", "Sublime Text 2"], "sublime_text.exe", "subl")
        editorArgs += [ "--wait" ]
    elif cmdenv.editing == 'npp':
        cmdenv.DEBUG(0, "Notepad++ mode")
        editor = editor or getEditorPaths(cmdenv,
                            "notepad++", "NOTEPADPP_EDITOR",
                            ["Notepad++"], "notepad++.exe", "notepad++")
        if not cmdenv.quiet:
            print("NOTE: You'll need to exit Notepad++ to return control back to trade.py")
    elif cmdenv.editing == "vim":
        cmdenv.DEBUG(0, "VI iMproved mode")
        if not editor:
            # Hack... Hackity hack, hack, hack.
            # This has a disadvantage in that: we don't check for just "vim" (no .exe) under Windows
            vimDirs = [ "Git\\share\\vim\\vim{}".format(vimVer) for vimVer in range(70,75) ]
            editor = getEditorPaths(cmdenv, "vim", "EDITOR", vimDirs, "vim.exe", "vim")
    elif cmdenv.editing == "notepad":
        cmdenv.DEBUG(0, "Notepad mode")
        editor = editor or "notepad.exe"  # herp

    try:
        envArgs = os.environ["EDITOR_ARGS"]
        if envArgs:
            editorArgs += envArgs.split(' ')
    except KeyError:
        pass

    # Create a temporary text file with a list of the price data.
    tmpPath = pathlib.Path("prices.tmp")
    if tmpPath.exists():
        raise TemporaryFileExistsError(
                "Temporary file already exists: {}\n"
                "(Check you aren't already editing in another window"
                    .format(tmpPath)
                )

    absoluteFilename = None
    dbFilename = cmdenv.dbFilename or tdb.defaultDB
    try:
        elementMask = prices.Element.basic
        if cmdenv.supply: elementMask |= prices.Element.supply
        if cmdenv.timestamps: elementMask |= prices.Element.timestamp
        # Open the file and dump data to it.
        with tmpPath.open("w") as tmpFile:
            # Remember the filename so we know we need to delete it.
            absoluteFilename = str(tmpPath.resolve())
            prices.dumpPrices(dbFilename, elementMask,
                                file=tmpFile,
                                stationID=stationID,
                                defaultZero=cmdenv.forceNa,
                                debug=cmdenv.debug)

        # Stat the file so we can determine if the user writes to it.
        # Use the most recent create/modified timestamp.
        preStat = tmpPath.stat()
        preStamp = max(preStat.st_mtime, preStat.st_ctime)

        # Launch the editor
        editorCommandLine = [ editor ] + editorArgs + [ absoluteFilename ]
        cmdenv.DEBUG(0, "Invoking [{}]", ' '.join(editorCommandLine))
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
            print("- No changes detected - doing nothing. {}".format(random.choice([
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
        else:
            cmdenv.DEBUG(0, "File changed - importing data.")
            importDataFromFile(cmdenv, tdb, tmpPath, stationID, dbFilename)

        tmpPath.unlink()
        tmpPath = None

    finally:
        # Save a copy
        if absoluteFilename and tmpPath:
            lastPath = pathlib.Path("prices.last")
            if lastPath.exists():
                lastPath.unlink()
            tmpPath.rename(lastPath)


def guidedUpdate(cmdenv, tdb):
    raise CommandLineError("Guided update mode not implemented yet. See -h for help.")


######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    if not cmdenv.editor and not cmdenv.editing:
        guidedUpdate(tdb, cmdenv)

    # User specified one of the options to use an editor.
    editUpdate(tdb, cmdenv, cmdenv.startStation.ID)

    return None

