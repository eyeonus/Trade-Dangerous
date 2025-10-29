from pathlib import Path
from sqlalchemy import inspect, text
from .tradeexcept import TradeException

from .db import utils as db_utils


import csv
import os

######################################################################
# TradeDangerous :: Modules :: CSV Exporter
#
# Generate CSV files for database tables.
#
# Assumptions:
#   * Each table has at most one UNIQUE index.
#   * Referenced tables also have a UNIQUE index.
#   * Only single-column foreign keys are supported.
#   * Single-column primary keys are inferred automatically by SQLAlchemy.
#
# CAUTION: If the schema changes this module may require updates.
######################################################################

######################################################################
# Default values

# For some tables the first two columns will be reversed
reverseList = []

######################################################################
# Helpers
######################################################################

def search_keyList(items, val):
    for row in items:
        if row['from'] == row['to'] == val:
            return row
    return None


def getUniqueIndex(session, tableName):
    """Return all unique columns via SQLAlchemy inspector."""
    inspector = inspect(session.get_bind())
    unqIndex = []
    for idx in inspector.get_indexes(tableName):
        if idx.get("unique"):
            unqIndex.extend(idx.get("column_names", []))
    return unqIndex


def getFKeyList(session, tableName):
    """Return all single-column foreign keys via SQLAlchemy inspector."""
    inspector = inspect(session.get_bind())
    keyList = []
    for fk in inspector.get_foreign_keys(tableName):
        cols = fk.get("constrained_columns", [])
        referred = fk.get("referred_columns", [])
        if len(cols) == 1 and len(referred) == 1:
            keyList.append({
                "table": fk.get("referred_table"),
                "from": cols[0],
                "to": referred[0],
            })
    return keyList


def buildFKeyStmt(session, tableName, key):
    """
    Resolve the FK constraint against the UNIQUE index of the
    referenced table.
    
    Multicolumn UNIQUEs are allowed, but only the last column
    may be treated as a single-column join target.
    """
    unqIndex = getUniqueIndex(session, key["table"])
    keyList = getFKeyList(session, key["table"])
    keyStmt = []
    
    for colName in unqIndex:
        # If this unique column is itself a foreign key, recurse
        keyKey = search_keyList(keyList, colName)
        if keyKey:
            keyStmt.extend(buildFKeyStmt(session, key["table"], keyKey))
        else:
            keyStmt.append({
                "table": tableName,
                "column": colName,
                "joinTable": key["table"],
                "joinColumn": key["to"],
            })
    
    return keyStmt


######################################################################
# Code
######################################################################

def exportTableToFile(tdb_or_session, tdenv, tableName, csvPath=None):
    """
    Generate the CSV file for tableName in csvPath.
    Returns (lineCount, exportPath).
    
    Behaviour:
    - Prefix unique columns with "unq:".
    - Foreign keys are exported as "<col>@<joinTable>.<uniqueCol>".
    - Datetime-like values for 'modified' columns are exported as
      "YYYY-MM-DD HH:MM:SS" (no microseconds).
    
    Compatible with either:
      * a SQLAlchemy Session
      * a TradeDB wrapper exposing .engine
    """
    from sqlalchemy.orm import Session
    
    # --- Resolve a SQLAlchemy session ---
    if hasattr(tdb_or_session, "engine"):
        # Likely a TradeDB instance
        engine = tdb_or_session.engine
        session = Session(engine)
    elif hasattr(tdb_or_session, "get_bind"):
        # Already a Session
        session = tdb_or_session
    else:
        raise TradeException(
            f"Unsupported DB object passed to exportTableToFile: {type(tdb_or_session)}"
        )
    
    csvPath = csvPath or Path(tdenv.csvDir)
    if not Path(csvPath).is_dir():
        raise TradeException(f"Save location '{csvPath}' not found.")
    
    uniquePfx = "unq:"
    exportPath = (Path(csvPath) / Path(tableName)).with_suffix(".csv")
    tdenv.DEBUG0(f"Export Table '{tableName}' to '{exportPath}'")
    
    def _fmt_ts(val):
        if hasattr(val, "strftime"):
            try:
                return val.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
        if isinstance(val, str):
            s = val
            if len(s) >= 19 and s[10] == "T":
                s = s[:10] + " " + s[11:]
            if len(s) >= 19 and s[4] == "-" and s[7] == "-" and s[10] == " " and s[13] == ":" and s[16] == ":":
                return s[:19]
        return val
    
    lineCount = 0
    with exportPath.open("w", encoding="utf-8", newline="\n") as exportFile:
        exportOut = csv.writer(
            exportFile,
            delimiter=",",
            quotechar="'",
            doublequote=True,
            quoting=csv.QUOTE_NONNUMERIC,
            lineterminator="\n",
        )
        
        bind = session.get_bind()
        inspector = inspect(bind)
        
        try:
            unique_cols = db_utils.get_unique_columns(session, tableName)
            fk_list = db_utils.get_foreign_keys(session, tableName)
        except Exception as e:
            raise TradeException(f"Failed to introspect table '{tableName}': {e!r}")
        
        csvHead = []
        stmtColumn = []
        stmtTable = [tableName]
        stmtOrder = []
        is_modified_col = []
        
        for col in inspector.get_columns(tableName):
            col_name = col["name"]
            fk = next((fk for fk in fk_list if fk["from"] == col_name), None)
            if fk:
                joinTable = fk["table"]
                joinColumn = fk["to"]
                join_unique_cols = db_utils.get_unique_columns(session, joinTable)
                if not join_unique_cols:
                    raise TradeException(
                        f"No unique column found in referenced table '{joinTable}'"
                    )
                export_col = join_unique_cols[0]
                csvPfx = uniquePfx if col_name in unique_cols else ""
                csvHead.append(f"{csvPfx}{col_name}@{joinTable}.{export_col}")
                stmtColumn.append(f"{joinTable}.{export_col}")
                is_modified_col.append(export_col == "modified")
                nullable = bool(col.get("nullable", True))
                join_type = "LEFT OUTER JOIN" if nullable else "INNER JOIN"
                stmtTable.append(
                    f"{join_type} {joinTable} ON {tableName}.{col_name} = {joinTable}.{joinColumn}"
                )
                stmtOrder.append(f"{joinTable}.{export_col}")
            else:
                if col_name in unique_cols:
                    csvHead.append(uniquePfx + col_name)
                    stmtOrder.append(f"{tableName}.{col_name}")
                else:
                    csvHead.append(col_name)
                stmtColumn.append(f"{tableName}.{col_name}")
                is_modified_col.append(col_name == "modified")
        
        sqlStmt = f"SELECT {','.join(stmtColumn)} FROM {' '.join(stmtTable)}"
        if stmtOrder:
            sqlStmt += f" ORDER BY {','.join(stmtOrder)}"
        tdenv.DEBUG1(f"SQL: {sqlStmt}")
        
        exportFile.write(f"{','.join(csvHead)}\n")
        
        for row in session.execute(text(sqlStmt)):
            lineCount += 1
            row_out = [
                _fmt_ts(val) if is_modified_col[i] else val
                for i, val in enumerate(row)
            ]
            tdenv.DEBUG2(f"{lineCount}: {row_out}")
            exportOut.writerow(row_out)
        
        tdenv.DEBUG1(f"{lineCount} {tableName}s exported")
    
    # Close session if we created it
    if hasattr(tdb_or_session, "engine"):
        session.close()
    
    return lineCount, exportPath
