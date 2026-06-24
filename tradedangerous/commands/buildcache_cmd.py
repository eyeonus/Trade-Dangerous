from __future__ import annotations
from pathlib import Path
import typing

from .exceptions import CommandLineError
from .parsing import ParseArgument
from .commandenv import Needs

from tradedangerous.db import get_session_factory
from tradedangerous.db.lifecycle import reset_db
from tradedangerous.db.import_csv import processImportFile
from tradedangerous.fs import file_line_count
from tradedangerous.misc.progress import Progress, CountingBar

if typing.TYPE_CHECKING:
    from tradedangerous import CommandEnv, CommandResults
    from tradedangerous.tradeorm import TradeORM


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
needs = Needs.RESOLVER
# buildcache builds the database from the CSV sources, creating the .db file
# if it does not exist, so its handle is constructed tolerant of a missing DB.
allowMissingDB = True
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

# The standard TD tables and their CSV files, in dependency order (System
# before Station, etc.). A destructive rebuild loads these from the CSV data
# directory.
_STANDARD_TABLES = (
    ("System.csv", "System"),
    ("Station.csv", "Station"),
    ("Ship.csv", "Ship"),
    ("ShipVendor.csv", "ShipVendor"),
    ("Category.csv", "Category"),
    ("Item.csv", "Item"),
    ("StationItem.csv", "StationItem"),
    ("FDevShipyard.csv", "FDevShipyard"),
)


def _rebuild_database(engine, data_dir, tdenv) -> None:
    """
    Destructive rebuild of the database from the standard CSV source files.

    Resets the schema (SQLite from TradeDangerous.sql; MariaDB via ORM metadata)
    then upserts the standard tables from the CSV data directory. Engine-centric:
    it owns its rebuild session and needs no legacy db handle. The ".prices"
    pathway is separate (import_prices.py) and is not part of a rebuild.

    This is the whole of buildcache's data-load behaviour, kept here so the
    command's future can be decided in one place.
    """
    tdenv.NOTE("(Re)building database: this may take a few moments.", stderr=True)

    # Resolve the on-disk path for the schema reset (SQLite only; MariaDB ignores it).
    if engine.dialect.name == "sqlite" and engine.url.database:
        db_path = Path(engine.url.database)
    else:
        db_path = Path(data_dir) / "TradeDangerous.db"

    # Step 1: reset the schema before opening a session.
    reset_db(engine, db_path=db_path)

    # Step 2: load the standard tables on a fresh session.
    csv_dir = Path(tdenv.csvDir)
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        with Progress(
            max_value=len(_STANDARD_TABLES) + 1,
            prefix="Importing",
            width=25,
            style=CountingBar,
        ) as prog:
            for fname, table in _STANDARD_TABLES:
                import_path = csv_dir / fname
                import_lines = file_line_count(import_path, missing_ok=True)
                with prog.sub_task(max_value=import_lines, description=table) as child:
                    prog.increment(value=1)
                    call_args = {"task": child, "advance": 1}
                    try:
                        processImportFile(
                            tdenv,
                            session,
                            import_path,
                            table,
                            line_callback=prog.update_task,
                            call_args=call_args,
                        )
                        session.commit()
                    except FileNotFoundError:
                        tdenv.DEBUG0("WARNING: processImportFile found no {} file", import_path)
                    except StopIteration:
                        tdenv.NOTE(
                            "{} exists but is empty. "
                            "Remove it or add the column definition line.",
                            import_path,
                        )
            prog.increment(1)
            with prog.sub_task(description="Save DB"):
                session.commit()

    tdenv.NOTE("Database build completed.", stderr=True)


######################################################################
# Perform query and populate result set


def run(results: CommandResults, cmdenv: CommandEnv, tdb: TradeORM) -> bool:
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
    if not cmdenv.force and tdb.db_path.exists():
        raise CommandLineError(
            f"SQLite3 database '{tdb.db_path}' already exists.\n"
            "Either remove the file first or use the '-f/--force' option."
        )

    # Ensure the SQL source exists (the rebuild relies on it).
    if not tdb.sql_path.exists():
        raise CommandLineError(f"SQL File does not exist: {tdb.sql_path}")

    # Force a destructive rebuild from the local CSV source files.
    _rebuild_database(tdb.engine, tdb.data_dir, cmdenv)
    
    # We've done everything, there is no work for the caller to do.
    return False
