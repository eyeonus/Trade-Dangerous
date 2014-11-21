from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from commands.exceptions import CommandLineError

######################################################################
# Parser config

help='Build TradeDangerous cache file from sources'
name='buildcache'
epilog=(
        'TD will normally do this for you automatically whenever '
        'it detects changes to one or more source file; most end-'
        'users will never need to use this command.\n'
        'N.B. This process is destructive: '
        'any data in the .db that is not reflected in the '
        'source files will be lost.'
)
wantsTradeDB=False      # Cause we're about to frak with it.
arguments = [
]
switches = [
    ParseArgument(
        '--sql', default=None, dest='sqlFilename',
        help='Specify SQL script to execute.',
    ),
    ParseArgument(
        '--prices', default=None, dest='pricesFilename',
        help='Specify the prices file to load.',
    ),
    ParseArgument(
        '-f', '--force', default=False, action='store_true',
        dest='force',
        help='Overwite existing file',
    ),
]

######################################################################
# Helpers

######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    from tradedb import TradeDB

    # Check that the file doesn't already exist.
    dbFilename = cmdenv.dbFilename or TradeDB.defaultDB
    sqlFilename = cmdenv.sqlFilename or TradeDB.defaultSQL
    pricesFilename = cmdenv.pricesFilename or TradeDB.defaultPrices
    importTables = TradeDB.defaultTables

    from pathlib import Path
    dbPath = Path(dbFilename)
    sqlPath = Path(sqlFilename)
    pricesPath = Path(pricesFilename)
    if not cmdenv.force:
        if dbPath.exists():
            raise CommandLineError(
                    "SQLite3 database '{}' already exists. "
                     "Either remove the file first or use the '-f' option."
                        .format(dbFilename))

    if not sqlPath.exists():
        raise CommandLineError(
                    "SQL File does not exist: {}".format(sqlFilename))

    if not pricesPath.exists():
        raise CommandLineError(
                    "Prices file does not exist: {}".format(pricesFilename))

    from cache import buildCache
    buildCache(cmdenv, dbPath, sqlPath, pricesPath, importTables)

    return None

