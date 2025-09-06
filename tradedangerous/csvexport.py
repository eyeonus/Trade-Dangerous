from pathlib import Path
from sqlalchemy import inspect, text
from .tradeexcept import TradeException

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

def exportTableToFile(session, tdenv, tableName, csvPath=None):
    """
    Generate a CSV file for `tableName` in `csvPath`.
    Returns: (lineCount, exportPath)
    """

    # Resolve path for CSV file
    csvPath = csvPath or getattr(tdenv, "csvPath", None)
    if csvPath is None:
        # Fallback: use dataDir if csvPath not set
        csvPath = getattr(tdenv, "dataDir", None)
        if csvPath is None:
            raise TradeException("No valid CSV path found (csvPath and dataDir are None).")
    csvPath = Path(csvPath)

    if not csvPath.is_dir():
        raise TradeException(f"Save location '{csvPath}' not found.")

    # Prefix for unique/ignore columns (used during header processing)
    uniquePfx = "unq:"
    ignorePfx = "!"

    # Prepare CSV output path
    exportPath = (csvPath / Path(tableName)).with_suffix(".csv")
    tdenv.DEBUG0(f"Export Table '{tableName}' to '{exportPath}'")
    lineCount = 0
    with exportPath.open("w", encoding="utf-8", newline="") as exportFile:
        exportOut = csv.writer(
            exportFile,
            delimiter=",",
            quotechar="'",
            doublequote=True,
            quoting=csv.QUOTE_NONNUMERIC,
            lineterminator="\n",
        )

        # Inspect table schema
        inspector = inspect(session.get_bind())
        cols = inspector.get_columns(tableName)

        # Build column list (all columns; PKs are retained)
        columnList = list(cols)

        if not columnList:
            raise TradeException(f"No columns to export for table '{tableName}'.")

        # Reverse the first two columns for certain tables
        if tableName in reverseList:
            columnList[0], columnList[1] = columnList[1], columnList[0]
            
        # Initialize helper lists
        csvHead    = []
        stmtColumn = []
        stmtTable  = [tableName]
        stmtOrder  = []

        unqIndex = getUniqueIndex(session, tableName)
        keyList  = getFKeyList(session, tableName)

        tdenv.DEBUG1("UNIQUE: " + ", ".join(unqIndex))

        # Iterate over all columns of the table
        for col in columnList:
            colName = col["name"]

            # Check if the column is a foreign key
            key = search_keyList(keyList, colName)
            if key:
                # Build join statement(s) recursively
                keyStmt = buildFKeyStmt(session, tableName, key)
                for keyRow in keyStmt:
                    tdenv.DEBUG1("FK-Stmt: {}".format(list(keyRow)))

                    # Always emit ANSI ON-style joins for portability
                    joinStmt = (
                        f"ON {keyRow['table']}.{keyRow['joinColumn']} = "
                        f"{keyRow['joinTable']}.{keyRow['joinColumn']}"
                    )
                    csvPfx = ""

                    if colName in unqIndex:
                        # Column is part of a unique index
                        csvPfx = uniquePfx + csvPfx

                    csvHead.append(
                        f"{csvPfx}{keyRow['column']}@{keyRow['joinTable']}.{keyRow['joinColumn']}"
                    )
                    stmtColumn.append(f"{keyRow['joinTable']}.{keyRow['column']}")
                    if col.get("nullable", True) is False:
                        stmtTable.append(f"INNER JOIN {keyRow['joinTable']} {joinStmt}")
                    else:
                        stmtTable.append(f"LEFT OUTER JOIN {keyRow['joinTable']} {joinStmt}")
                    stmtOrder.append(f"{keyRow['joinTable']}.{keyRow['column']}")

            else:
                # Ordinary column
                if colName in unqIndex:
                    csvHead.append(uniquePfx + colName)
                    stmtOrder.append(f"{tableName}.{colName}")
                else:
                    csvHead.append(colName)
                stmtColumn.append(f"{tableName}.{colName}")

        # Build the SQL statement for export
        sqlStmt = f"SELECT {','.join(stmtColumn)} FROM {' '.join(stmtTable)}"
        if stmtOrder:
            sqlStmt += f" ORDER BY {','.join(stmtOrder)}"
        tdenv.DEBUG1(f"SQL: {sqlStmt}")

        # Write header line (unquoted)
        exportFile.write(",".join(csvHead) + "\n")

        # Stream results with SQLAlchemy
        result = session.execute(
            text(sqlStmt).execution_options(stream_results=True)
        )
        for lineCount, row in enumerate(result, start=1):
            tdenv.DEBUG2(f"{lineCount}: {list(row)}")
            exportOut.writerow(list(row))

        tdenv.DEBUG1(f"{lineCount} {tableName}s exported")

    # Touch DB file for SQLite to prevent unnecessary regeneration
    if session.bind.dialect.name == "sqlite" and hasattr(tdenv, "dbPath") and tdenv.dbPath:
        os.utime(str(tdenv.dbPath))

    return lineCount, exportPath
