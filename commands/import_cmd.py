from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

from commands.exceptions import *
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from pathlib import Path

import cache
import math
import plugins
import re
import transfers

######################################################################
# Parser config

help=(
    "Imports price data from a '.prices' format file. "
    "Previous data for the stations included in the file "
    "is removed, but other stations are not affected."
)
name='import'
epilog=None
wantsTradeDB=True
arguments = [
]
switches = [
    MutuallyExclusiveGroup(
        ParseArgument('filename',
            help='Name of the file to read.',
            type=str,
            default=None,
        ),
        ParseArgument('--maddavo',
            help='[Deprecated] Import prices from Maddavo\'s site. Use "--plug=madadvo" instead.',
            dest='plug',
            action='store_const',
            const='maddavo',
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
]

######################################################################
# Helpers


######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    if cmdenv.maddavo:
        raise CommandLineError(
                "--maddavo is deprecated: "
                "please use --plug=maddavo instead"
        )

    # If we're using a plugin, initialize that first.
    if cmdenv.plug:
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

    if re.match("^https?://", cmdenv.filename, re.IGNORECASE):
        cmdenv.url, cmdenv.filename = cmdenv.filename, None

    if cmdenv.url:
        cmdenv.filename = cmdenv.filename or "import.prices"
        transfers.download(cmdenv, cmdenv.url, cmdenv.filename)
        if cmdenv.download:
            return None

    # If the filename specified was "-" or None, then go ahead
    # and present the user with an open file dialog.
    if not cmdenv.filename:
        import tkinter
        from tkinter.filedialog import askopenfilename
        tk = tkinter.Tk()
        tk.withdraw()
        filetypes = (
                ("TradeDangerous '.prices' Files", "*.prices"),
                ("All Files", "*.*"),
                )
        filename = askopenfilename(
                    title="Select the file to import",
                    initialfile="TradeDangerous.prices",
                    filetypes=filetypes,
                    initialdir='.',
                )
        if not filename:
            raise SystemExit("Aborted")
        cmdenv.filename = filename

    # check the file exists.
    filePath = Path(cmdenv.filename)
    if not filePath.is_file():
        raise CommandLineError("File not found: {}".format(
                    str(filePath)
                ))

    if cmdenv.plug:
        if not plugin.finish():
            cache.regeneratePricesFile()
            return None

    cache.importDataFromFile(tdb, cmdenv, filePath)
    return None

