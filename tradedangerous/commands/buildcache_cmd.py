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
    """
    BRUTE-FORCE rebuild of the cache/database.
    
    Semantics preserved:
      - If DB exists and --force not given => error
      - SQL file must exist
      - Performs a full destructive rebuild
    
    Implementation change:
      - Delegates to tradedangerous.db.lifecycle.ensure_fresh_db with mode='force'
        so all backend-specific checks and rebuild steps run via the central path.
    """
    # Deprecation note: keep short and visible but non-fatal.
    print("NOTE: 'buildcache' is deprecated. Prefer 'update' or importer plugins. "
          "Proceeding with a forced rebuild via db.lifecycle.ensure_fresh_db().")
    
    # Honor legacy safety: require --force to overwrite an existing DB file.
    if not cmdenv.force and tdb.dbPath.exists():
        raise CommandLineError(
            f"SQLite3 database '{tdb.dbFilename}' already exists.\n"
            "Either remove the file first or use the '-f/--force' option."
        )
    
    # Ensure the SQL source exists (buildCache ultimately relies on this path).
    if not tdb.sqlPath.exists():
        raise CommandLineError(f"SQL File does not exist: {tdb.sqlFilename}")
    
    # Force a rebuild through the lifecycle helper (works for both backends).
    from tradedangerous.db.lifecycle import ensure_fresh_db
    
    ensure_fresh_db(
        backend=tdb.engine.dialect.name if getattr(tdb, "engine", None) else "sqlite",
        engine=getattr(tdb, "engine", None),
        data_dir=tdb.dataPath,
        metadata=None,
        mode="force",
        tdb=tdb,
        tdenv=cmdenv,
        rebuild=True,
    )
    
    return None

