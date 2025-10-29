from ..csvexport import exportTableToFile
from .parsing import ParseArgument, MutuallyExclusiveGroup
from .exceptions import CommandLineError
from pathlib import Path

######################################################################
# TradeDangerous :: Commands :: Export
#
# Generate the CSV files for the master data of the database.
#
######################################################################
# CAUTION: If the database structure gets changed this script might
#          need some corrections.
######################################################################

######################################################################
# Parser config

help='CSV exporter for TradeDangerous database.'
name='export'
epilog=(
        "CAUTION: If you don't specify a different path, the current "
        "CSV files in the data directory will be overwritten with "
        "the current content of the database.\n "
        "If you have changed any CSV file and didn't rebuild the "
        "database, they will be lost.\n "
        "Use the 'buildcache' command first to rebuild the database."
)
wantsTradeDB=False           # because we don't want the DB to be rebuild
arguments = [
]
switches = [
    ParseArgument('--path',
            help="Specify a different save location of the CSV files than the default.",
            type=str,
            default=None
        ),
    MutuallyExclusiveGroup(
        ParseArgument('--tables', "-T",
                help='Specify comma separated tablenames to export.',
                metavar='TABLE[,TABLE,...]',
                type=str,
                default=None
            ),
        ParseArgument('--all-tables',
                help='Include the price tables for export.',
                dest='allTables',
                action='store_true',
                default=False
            ),
        ),
    ParseArgument('--delete-empty',
            help='Delete CSV files without content.',
            dest='deleteEmpty',
            action='store_true',
            default=False
        ),
]

######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    """
    Backend-neutral export of DB tables to CSV.
    
    Changes:
      * Use tradedangerous.db.lifecycle.ensure_fresh_db(rebuild=False) to verify a usable DB
        without rebuilding (works for SQLite and MariaDB).
      * Backend-aware announcement of the source DB (file path for SQLite, DSN for others).
      * Table enumeration via SQLAlchemy inspector (no sqlite_master, no COLLATE quirks).
    """
    # --- Sanity check the database without rebuilding (works for both backends) ---
    from tradedangerous.db.lifecycle import ensure_fresh_db  # local import avoids import-time tangles
    summary = ensure_fresh_db(
        backend=getattr(tdb.engine, "dialect", None).name if getattr(tdb, "engine", None) else "unknown",
        engine=getattr(tdb, "engine", None),
        data_dir=tdb.dataPath,
        metadata=None,
        mode="auto",
        rebuild=False,   # IMPORTANT: never rebuild from here; just report health
    )
    if summary.get("sane") != "Y":
        reason = summary.get("reason", "unknown")
        raise CommandLineError(
            f"Database is not initialized/healthy (reason: {reason}). "
            "Use 'buildcache' or an importer to (re)build it."
        )
    
    # --- Determine export target directory (same behavior as before) ---
    from pathlib import Path
    exportPath = Path(cmdenv.path) if cmdenv.path else Path(tdb.dataDir)
    if not exportPath.is_dir():
        raise CommandLineError("Save location '{}' not found.".format(str(exportPath)))
    
    # --- Announce which DB we will read from, backend-aware ---
    try:
        dialect = tdb.engine.dialect.name
        if dialect == "sqlite":
            source_label = f"SQLite file '{tdb.dbPath}'"
        else:
            # Hide password in DSN
            source_label = f"{dialect} @ {tdb.engine.url.render_as_string(hide_password=True)}"
    except Exception:
        source_label = str(getattr(tdb, "dbPath", "Unknown DB"))
    cmdenv.NOTE("Using database {}", source_label)
    
    # --- Enumerate tables using SQLAlchemy inspector (backend-neutral) ---
    from sqlalchemy import inspect
    inspector = inspect(tdb.engine)
    all_tables = inspector.get_table_names()  # current schema / database
    
    # Optional ignore list (preserve legacy default: skip StationItem unless --all-tables)
    ignoreList = []
    if not getattr(cmdenv, "allTables", False):
        ignoreList.append("StationItem")
    
    # --tables filtering (case-insensitive, like old COLLATE NOCASE)
    if getattr(cmdenv, "tables", None):
        requested = [t.strip() for t in cmdenv.tables.split(",") if t.strip()]
        lower_map = {t.lower(): t for t in all_tables}
        resolved = []
        for name in requested:
            found = lower_map.get(name.lower())
            if found:
                resolved.append(found)
            else:
                cmdenv.NOTE("Requested table '{}' not found; skipping", name)
        table_list = sorted(set(resolved))
    else:
        table_list = sorted(set(all_tables))
    
    # --- Export each table via csvexport (already refactored elsewhere) ---
    for tableName in table_list:
        if tableName in ignoreList:
            cmdenv.NOTE("Ignore Table '{table}'", table=tableName)
            continue
        
        cmdenv.NOTE("Export Table '{table}'", table=tableName)
        
        lineCount, filePath = exportTableToFile(tdb, cmdenv, tableName, exportPath)
        
        # Optionally delete empty CSVs
        if getattr(cmdenv, "deleteEmpty", False) and lineCount == 0:
            try:
                filePath.unlink(missing_ok=True)
                cmdenv.DEBUG0("Delete empty file {file}", file=filePath)
            except Exception as e:
                cmdenv.DEBUG0("Failed to delete empty file {file}: {err}", file=filePath, err=e)
    
    return None
