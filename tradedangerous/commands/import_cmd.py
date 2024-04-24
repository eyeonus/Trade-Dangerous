from .exceptions import CommandLineError
from .parsing import ParseArgument, MutuallyExclusiveGroup
from itertools import chain
from pathlib import Path

from .. import cache, plugins, transfers
import re
import sys

try:
    import tkinter
    import tkinter.filedialog as tkfd
    hasTkInter = True
except ImportError:
    hasTkInter = False

######################################################################
# Parser config

help = (
    "TD data import system. On its own, this command lets you "
    "merge station prices from a '.prices' file (entries in the "
    "file that are older than your local data are not loaded)."
)
name = 'import'
epilog = (
    "This sub-command provides a plugin infrastructure, and comes "
    "with a module to import data from Maddavo's Market Share "
    "(http://www.davek.com.au/td/).\n"
    "See \"import -P maddavo -O help\" for more help."
)
wantsTradeDB = False
arguments = [
]
switches = [
    MutuallyExclusiveGroup(
        ParseArgument('filename',
            help = (
                "Name of the file to read, or, used with '--url', "
                "will save the downloaded file as this name."
            ),
            type = str,
            default = None,
        ),
        ParseArgument('--plug', '-P',
                help = "Use the specified import plugin.",
                type = str,
                default = None,
        ),
    ),
    ParseArgument('--url',
        help = 'URL to download filename (default "import.prices") from.',
        type = str,
        default = None,
    ),
    ParseArgument('--download',
        help = 'Stop after downloading.',
        action = 'store_true',
        default = False,
    ),
    ParseArgument(
        '--ignore-unknown', '-i',
        default = False, action = 'store_true',
        dest = 'ignoreUnknown',
        help = (
            "Data for systems, stations and items that are not "
            "recognized is reported as warning but skipped."
        ),
    ),
    ParseArgument(
        '--option', '-O',
        default = [], action = 'append',
        dest = 'pluginOptions',
        help = (
            "Provides a way to pass additional arguments to plugins."
        ),
    ),
    MutuallyExclusiveGroup(
        ParseArgument('--reset-all',
            help = 'Clear the database before importing.',
            action = 'store_true',
            default = False,
        ),
        ParseArgument('--merge-import', '-M',
            help = (
                'Merge the import file with the existing local database: '
                'only loads values that have an explicit entry with a '
                'newer timestamp than the existing data. Local values '
                'are only removed if there is an explicit entry with a '
                '0/0 demand/supply price.'
            ),
            action = 'store_true',
            default = False,
            dest = 'mergeImport',
        ),
    ),
]

######################################################################
# Helpers

######################################################################
# Perform query and populate result set


def run(results, cmdenv, tdb):
    # If we're using a plugin, initialize that first.
    if cmdenv.plug:
        if cmdenv.pluginOptions:
            cmdenv.pluginOptions = chain.from_iterable(
                opt.split(',') for opt in cmdenv.pluginOptions
            )
        try:
            pluginClass = plugins.load(cmdenv.plug, "ImportPlugin")
        except plugins.PluginException as e:
            raise CommandLineError("Plugin Error: " + str(e))
        
        # Initialize the plugin
        plugin = pluginClass(tdb, cmdenv)
        
        # Run the plugin. If it returns False, then it did everything
        # that needs doing and we can stop now.
        # If it returns True, it is returning control to the module.
        if not plugin.run():
            return None
    
    tdb.reloadCache()
    tdb.close()
    
    if cmdenv.filename:
        if re.match(r"^https?://", cmdenv.filename, re.IGNORECASE):
            cmdenv.url, cmdenv.filename = cmdenv.filename, None
    
    if cmdenv.url:
        cmdenv.filename = cmdenv.filename or "import.prices"
        transfers.download(cmdenv, cmdenv.url, cmdenv.filename)
        if cmdenv.download:
            return None
    
    # If the filename specified was "-" or None, then go ahead
    # and present the user with an open file dialog.
    if not cmdenv.filename and hasTkInter:
        tk = tkinter.Tk()
        tk.withdraw()
        filetypes = (
                ("TradeDangerous '.prices' Files", "*.prices"),
                ("All Files", "*.*"),
                )
        filename = tkfd.askopenfilename(
                    title = "Select the file to import",
                    initialfile = "TradeDangerous.prices",
                    filetypes = filetypes,
                    initialdir = '.',
                )
        if not filename:
            raise SystemExit("Aborted")
        cmdenv.filename = filename
    
    # check the file exists.
    if cmdenv.filename != "-":
        fh = None
        filePath = Path(cmdenv.filename)
        if not filePath.is_file():
            raise CommandLineError("File not found: {}".format(
                        str(filePath)
                    ))
    else:
        filePath = "stdin"
        fh = sys.stdin
    
    if cmdenv.plug:
        if not plugin.finish():
            cache.regeneratePricesFile()
            return None
    
    cache.importDataFromFile(tdb, cmdenv, filePath, pricesFh = fh, reset = cmdenv.reset)
    
    return None
