from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

from commands.exceptions import *
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from itertools import chain
from pathlib import Path

import cache
import math
import plugins
import re
import transfers

try:
    import tkinter
    import tkinter.filedialog as tkfd
    hasTkInter = True
except ImportError:
    hasTkInter = False

######################################################################
# Parser config

help=(
    "Imports price data from a '.prices' format file. "
    "Previous data for the stations included in the file "
    "is removed, but other stations are not affected."
)
name='import'
epilog=(
    "This sub-command provides a plugin infrastructure, and comes "
    "with a module to import data from Maddavo's Market Share "
    "(http://www.davek.com.au/td/).\n"
    "See \"import --plug=maddavo --opt=help\" for more help."
)
wantsTradeDB=False
arguments = [
]
switches = [
    MutuallyExclusiveGroup(
        ParseArgument('filename',
            help='Name of the file to read.',
            type=str,
            default=None,
        ),
        ParseArgument('--plug',
                help="Use the specified import plugin.",
                type=str,
                default=None,
        ),
    ),
    ParseArgument('--url',
        help='Name of the file to read.',
        type=str,
        default=None,
    ),
    ParseArgument('--download',
        help='Stop after downloading.',
        action='store_true',
        default=False,
    ),
    ParseArgument(
        '--ignore-unknown', '-i',
        default=False, action='store_true',
        dest='ignoreUnknown',
        help=(
            "Data for systems, stations and items that are not "
            "recognized is reported as warning but skipped."
        ),
    ),
    ParseArgument(
        '--option', '-O',
        default=[], action='append',
        dest='pluginOptions',
        help=(
            "Provides a way to pass additional arguments to plugins."
        ),
    ),
    ParseArgument('--reset',
        help='Clear the database before importing.',
        action='store_true',
        default=False,
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
            raise CommandLineError("Plugin Error: "+str(e))

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
                    title="Select the file to import",
                    initialfile="TradeDangerous.prices",
                    filetypes=filetypes,
                    initialdir='.',
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

    cache.importDataFromFile(tdb, cmdenv, filePath, pricesFh=fh, reset=cmdenv.reset)

    return None
    
