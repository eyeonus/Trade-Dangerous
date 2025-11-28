# tradedangerous/commands/import_cmd.py
# DEPRECATED: The legacy “.prices” import path is deprecated.
# Prefer supported import plugins:
#   - trade import -P spansh      (authoritative bulk dump)
#   - trade import -P eddblink    (server listings pipeline)
# Solo / offline players: use the TradeDangerous DB-Update plugin for EDMC:
#   https://github.com/bgol/UpdateTD
#
# This module remains available for compatibility with old “.prices” files,
# but the format is being phased out and may be removed in a future release.

from __future__ import annotations

from .exceptions import CommandLineError
from .parsing import ParseArgument, MutuallyExclusiveGroup
from itertools import chain
from pathlib import Path

from .. import cache, plugins, transfers
import re
import sys
import typing

try:
    import tkinter
    import tkinter.filedialog as tkfd
    hasTkInter = True
except ImportError:
    hasTkInter = False

if typing.TYPE_CHECKING:
    from ..tradedb import TradeDB
    from ..tradeenv import TradeEnv


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
    "with a module to import data from Tromador's Trading Dangerously server"
    "(https://elite.tromador.com/).\n"
    "See \"trade import -P eddblink -O help\" for more help."
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


def run(results, cmdenv: TradeEnv, tdb: TradeDB):
    """
    Dispatch import work:
      • If a plugin (-P) is specified: load it and run it (no deprecation banner).
      • Otherwise: proceed with legacy .prices/.url flow and show a deprecation notice.
    """
    
    # --- Plugin path (preferred; no banner) ---
    if cmdenv.plug:
        if cmdenv.pluginOptions:
            cmdenv.pluginOptions = chain.from_iterable(
                opt.split(',') for opt in cmdenv.pluginOptions
            )
        try:
            pluginClass = plugins.load(cmdenv.plug, "ImportPlugin")
        except plugins.PluginException as e:
            raise CommandLineError("Plugin Error: " + str(e))
        
        plugin = pluginClass(tdb, cmdenv)
        
        # If plugin returns False, it fully handled the run → stop here.
        if not plugin.run():
            return None
        
        # If plugin returns True, it’s handing control back to legacy flow below.
        # Fall through intentionally (still no banner, as user invoked a plugin).
    
    # --- Legacy .prices path (deprecated; show banner once) ---
    # Only warn when the user is *not* using a plugin. Keep functionality intact.
    if not cmdenv.plug:
        print(
            "NOTE:\n"
            "=== DEPRECATION NOTICE ============================================\n"
            "The legacy '.prices' import is deprecated.\n"
            "Use a supported plugin instead:\n"
            "  • trade import -P spansh\n"
            "  • trade import -P eddblink\n"
            "Solo/offline: TradeDangerous DB-Update for EDMC → https://github.com/bgol/UpdateTD\n"
            "===================================================================\n"
        )
    
    # Refresh/close any cached handles before file ops (kept from original)
    tdb.reloadCache()
    tdb.close()
    tdb.removePerist()
    
    # Treat a bare http(s) string in 'filename' as a URL
    if cmdenv.filename:
        if re.match(r"^https?://", cmdenv.filename, re.IGNORECASE):
            cmdenv.url, cmdenv.filename = cmdenv.filename, None
    
    # Optional download step
    if cmdenv.url:
        cmdenv.filename = cmdenv.filename or "import.prices"
        transfers.download(cmdenv, cmdenv.url, cmdenv.filename)
        if cmdenv.download:
            return None
    
    # No filename? If Tk is available, prompt user (legacy behavior)
    fh = None
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
    
    # Validate path or use stdin
    if cmdenv.filename != "-":
        filePath = Path(cmdenv.filename)
        if not filePath.is_file():
            raise CommandLineError(f"File not found: {str(filePath)}")
    else:
        filePath = "stdin"
        fh = sys.stdin
    
    # If a plugin was also involved and wants to finish with default flow,
    # honour that (unchanged behavior).
    if cmdenv.plug:
        # Plugins returning True above chose to hand control back.
        # finish() may return False to suppress default regeneration.
        if not plugin.finish():
            cache.regeneratePricesFile()
            return None
    
    # Legacy .prices import
    cache.importDataFromFile(tdb, cmdenv, filePath, pricesFh=fh, reset=cmdenv.reset)
    return None
