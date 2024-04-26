from __future__ import annotations
from .exceptions import CommandLineError
from .parsing import ParseArgument
from ..cache import buildCache
from ..tradedb import TradeDB

######################################################################
# Parser config

help = 'Build TradeDangerous cache file from sources'
name = 'buildcache'
epilog = (
        'TD will normally do this for you automatically whenever '
        'it detects changes to one or more source file; most end-'
        'users will never need to use this command.\n'
        'N.B. This process is destructive: '
        'any data in the .db that is not reflected in the '
        'source files will be lost.'
)
wantsTradeDB = False  # Cause we're about to frak with it.
arguments = [
]
switches = [
    ParseArgument(
        '--sql', default = None, dest = 'sqlFilename',
        help = 'Specify SQL script to execute.',
    ),
    ParseArgument(
        '--prices', default = None, dest = 'pricesFilename',
        help = 'Specify the prices file to load.',
    ),
    ParseArgument(
        '--force', '-f', default = False, action = 'store_true',
        dest = 'force',
        help = 'Overwrite existing file',
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
]

######################################################################
# Helpers

######################################################################
# Perform query and populate result set


def run(results, cmdenv, tdb: TradeDB):
    # Check that the file doesn't already exist.
    if not cmdenv.force:
        if tdb.dbPath.exists():
            raise CommandLineError(
                f"SQLite3 database '{tdb.dbFilename}' already exists.\n"
                "Either remove the file first or use the '-f' option.")
    
    if not tdb.sqlPath.exists():
        raise CommandLineError(f"SQL File does not exist: {tdb.sqlFilename}")
    
    buildCache(tdb, cmdenv)
    
    return None
