# CSV table importer for TradeDangerous.
#
# processImportFile() upserts a single CSV table file into the database. Used by
# the eddblink importer and the buildcache command. Split out of the former
# cache.py during the TradeDB retirement; the ".prices" file pathway lives in
# tradedangerous/import_prices.py, and the database rebuild lives in
# tradedangerous/commands/buildcache_cmd.py.

from __future__ import annotations

import csv
import os
import typing

from functools import partial as partial_fn

from tradedangerous.db import orm_models as SA
from tradedangerous.db.utils import parse_ts
from tradedangerous import corrections
from tradedangerous.tradeexcept import DeletedKeyError, DuplicateKeyError

if typing.TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Optional


def processImportFile(
    tdenv,
    session,
    importPath,
    tableName,
    *,
    line_callback: Optional[Callable] = None,
    call_args: Optional[dict] = None,
):
    """
    Import a CSV file into the given table.
    
    Applies header parsing, uniqueness checks, foreign key lookups,
    in-row deprecation correction (warnings only at -vv via DEBUG1), and upserts via SQLAlchemy ORM.
    Commits in batches for large datasets.
    """
    
    tdenv.DEBUG0("Processing import file '{}' for table '{}'", str(importPath), tableName)
    
    call_args = call_args or {}
    if line_callback:
        line_callback = partial_fn(line_callback, **call_args)
    
    # --- batch size config from environment or fallback ---
    env_batch = os.environ.get("TD_LISTINGS_BATCH")
    if env_batch:
        try:
            max_transaction_items = int(env_batch)
        except ValueError:
            tdenv.WARN("Invalid TD_LISTINGS_BATCH value %r, falling back to defaults.", env_batch)
            max_transaction_items = None
    else:
        max_transaction_items = None
    
    if max_transaction_items is None:
        if session.bind.dialect.name in ("mysql", "mariadb"):
            max_transaction_items = 50 * 1024
        else:
            max_transaction_items = 250 * 1024
    
    transaction_items = 0  # track how many rows inserted before committing
    
    with importPath.open("r", encoding="utf-8") as importFile:
        csvin = csv.reader(importFile, delimiter=",", quotechar="'", doublequote=True)
        
        # Read header row
        columnDefs = next(csvin)
        columnCount = len(columnDefs)
        
        # --- Process headers: extract column names, track indices ---
        activeColumns: list[str] = []   # Final columns we'll use (after "unq:" stripping)
        kept_indices: list[int] = []    # Indices into CSV rows we keep (aligned to activeColumns)
        uniqueIndexes: list[int] = []   # Indexes (into activeColumns) of unique keys
        uniquePfx = "unq:"
        uniqueLen = len(uniquePfx)
        
        # map of header (without "unq:") -> original CSV index, for correction by name
        header_index: dict[str, int] = {}
        
        for cIndex, cName in enumerate(columnDefs):
            colName, _, _ = cName.partition("@")  # column name, @, source key
            baseName = colName[uniqueLen:] if colName.startswith(uniquePfx) else colName
            header_index[baseName] = cIndex
            
            # Handle unique constraint tracking
            if colName.startswith(uniquePfx):
                uniqueIndexes.append(len(activeColumns))
                colName = baseName
            
            activeColumns.append(colName)
            kept_indices.append(cIndex)
        
        importCount = 0
        uniqueIndex: dict[str, int] = {}
        
        # helpers for correction + visibility-gated warning
        DELETED = corrections.DELETED
        
        def _warn(line_no: int, msg: str) -> None:
            # Gate deprecation chatter to -vv (DEBUG1)
            tdenv.DEBUG1("{}:{} WARNING {}", importPath, line_no, msg)
        
        def _apply_row_corrections(table_name: str, row: list[str], line_no: int) -> bool:
            """
            Returns True if the row should be skipped (deleted in tolerant mode), False otherwise.
            Mutates 'row' in place with corrected values.
            """
            if table_name == "System":
                idx = header_index.get("name")
                if idx is not None:
                    orig = row[idx]
                    corr = corrections.correctSystem(orig)
                    if corr is DELETED:
                        if tdenv.ignoreUnknown:
                            _warn(line_no, f'System "{orig}" is marked as DELETED and should not be used.')
                            return True
                        raise DeletedKeyError(importPath, line_no, "System", orig)
                    if corr != orig:
                        _warn(line_no, f'System "{orig}" is deprecated and should be replaced with "{corr}".')
                        row[idx] = corr
            
            elif table_name == "Station":
                s_idx = header_index.get("system")
                n_idx = header_index.get("name")
                if s_idx is not None and n_idx is not None:
                    s_orig = row[s_idx]
                    s_corr = corrections.correctSystem(s_orig)
                    if s_corr is DELETED:
                        if tdenv.ignoreUnknown:
                            _warn(line_no, f'System "{s_orig}" is marked as DELETED and should not be used.')
                            return True
                        raise DeletedKeyError(importPath, line_no, "System", s_orig)
                    if s_corr != s_orig:
                        _warn(line_no, f'System "{s_orig}" is deprecated and should be replaced with "{s_corr}".')
                        row[s_idx] = s_corr
                    n_orig = row[n_idx]
                    n_corr = corrections.correctStation(s_corr, n_orig)
                    if n_corr is DELETED:
                        if tdenv.ignoreUnknown:
                            _warn(line_no, f'Station "{n_orig}" is marked as DELETED and should not be used.')
                            return True
                        raise DeletedKeyError(importPath, line_no, "Station", n_orig)
                    if n_corr != n_orig:
                        _warn(line_no, f'Station "{n_orig}" is deprecated and should be replaced with "{n_corr}".')
                        row[n_idx] = n_corr
            
            elif table_name == "Category":
                idx = header_index.get("name")
                if idx is not None:
                    orig = row[idx]
                    corr = corrections.correctCategory(orig)
                    if corr is DELETED:
                        if tdenv.ignoreUnknown:
                            _warn(line_no, f'Category "{orig}" is marked as DELETED and should not be used.')
                            return True
                        raise DeletedKeyError(importPath, line_no, "Category", orig)
                    if corr != orig:
                        _warn(line_no, f'Category "{orig}" is deprecated and should be replaced with "{corr}".')
                        row[idx] = corr
            
            elif table_name == "Item":
                cat_idx = header_index.get("category")
                name_idx = header_index.get("name")
                if cat_idx is not None:
                    c_orig = row[cat_idx]
                    c_corr = corrections.correctCategory(c_orig)
                    if c_corr is DELETED:
                        if tdenv.ignoreUnknown:
                            _warn(line_no, f'Category "{c_orig}" is marked as DELETED and should not be used.')
                            return True
                        raise DeletedKeyError(importPath, line_no, "Category", c_orig)
                    if c_corr != c_orig:
                        _warn(line_no, f'Category "{c_orig}" is deprecated and should be replaced with "{c_corr}".')
                        row[cat_idx] = c_corr
                if name_idx is not None:
                    i_orig = row[name_idx]
                    i_corr = corrections.correctItem(i_orig)
                    if i_corr is DELETED:
                        if tdenv.ignoreUnknown:
                            _warn(line_no, f'Item "{i_orig}" is marked as DELETED and should not be used.')
                            return True
                        raise DeletedKeyError(importPath, line_no, "Item", i_orig)
                    if i_corr != i_orig:
                        _warn(line_no, f'Item "{i_orig}" is deprecated and should be replaced with "{i_corr}".')
                        row[name_idx] = i_corr
            
            return False  # do not skip
        
        # --- Read data lines ---
        for linein in csvin:
            if line_callback:
                line_callback()
            if not linein:
                continue
            
            lineNo = csvin.line_num
            
            if len(linein) != columnCount:
                tdenv.NOTE("Wrong number of columns ({}:{}): {}", importPath, lineNo, ", ".join(linein))
                continue
            
            tdenv.DEBUG1("       Values: {}", ", ".join(linein))
            
            # --- Apply corrections BEFORE uniqueness; may skip if deleted in tolerant mode
            try:
                if _apply_row_corrections(tableName, linein, lineNo):
                    continue
            except DeletedKeyError:
                if not tdenv.ignoreUnknown:
                    raise  # strict, fail hard. resume the original fault with it's trace in-tact
                # tolerant: already warned in _apply_row_corrections; skip row
                continue
            
            # Extract and clean values to use (from corrected line)
            activeValues = [linein[i] for i in kept_indices]
            
            # --- Uniqueness check (after correction) ---
            try:
                if uniqueIndexes:
                    keyValues = [str(activeValues[i]).upper() for i in uniqueIndexes]
                    key = ":!:".join(keyValues)
                    prevLineNo = uniqueIndex.get(key, 0)
                    if prevLineNo:
                        key_disp = "/".join(keyValues)
                        if tdenv.ignoreUnknown:
                            e = DuplicateKeyError(importPath, lineNo, "entry", key_disp, prevLineNo)
                            e.category = "WARNING"
                            tdenv.NOTE("{}", e)
                            continue
                        raise DuplicateKeyError(importPath, lineNo, "entry", key_disp, prevLineNo)
                    uniqueIndex[key] = lineNo
            except Exception as e:
                # Keep processing the file, don’t tear down the loop
                tdenv.WARN(
                    "*** INTERNAL ERROR: {err}\n"
                    "CSV File: {file}:{line}\n"
                    "Table: {table}\n"
                    "Params: {params}\n".format(
                        err=str(e),
                        file=str(importPath),
                        line=lineNo,
                        table=tableName,
                        params=linein,
                    )
                )
                session.rollback()
                continue
            
            try:
                rowdict = dict(zip(activeColumns, activeValues))
                
                # --- Type coercion for common types ---
                for key, val in list(rowdict.items()):
                    if val in ("", None):
                        rowdict[key] = None
                        continue
                    if key.endswith("_id") or key.endswith("ID") or key in ("cost", "max_allocation"):
                        try:
                            rowdict[key] = int(val)
                        except ValueError:
                            rowdict[key] = None
                    elif key in ("pos_x", "pos_y", "pos_z", "ls_from_star"):
                        try:
                            rowdict[key] = float(val)
                        except ValueError:
                            rowdict[key] = None
                    elif "time" in key or key == "modified":
                        parsed = parse_ts(val)
                        if parsed:
                            rowdict[key] = parsed
                        else:
                            tdenv.WARN(
                                "Unparsable datetime in {} line {} col {}: {}",
                                importPath,
                                lineNo,
                                key,
                                val,
                            )
                            rowdict[key] = None
                
                # Derived lookup_name for System/Station: recompute from the
                # (already corrected) name so a rebuild always yields a correct
                # search key, overriding whatever the CSV carried. See
                # corrections.normalize_str.
                if tableName in ("System", "Station"):
                    nm = rowdict.get("name")
                    rowdict["lookup_name"] = corrections.normalize_str(nm) if isinstance(nm, str) else None
                # ORM insert/merge
                Model = getattr(SA, tableName)
                obj = Model(**rowdict)
                session.merge(obj)
                importCount += 1
                
                # Batch commit
                if max_transaction_items:
                    transaction_items += 1
                    if transaction_items >= max_transaction_items:
                        session.commit()
                        session.begin()
                        transaction_items = 0
            
            except Exception as e:
                # Log all import errors — but keep going
                tdenv.WARN(
                    "*** INTERNAL ERROR: {err}\n"
                    "CSV File: {file}:{line}\n"
                    "Table: {table}\n"
                    "Params: {params}\n".format(
                        err=str(e),
                        file=str(importPath),
                        line=lineNo,
                        table=tableName,
                        params=rowdict if "rowdict" in locals() else linein,
                    )
                )
                session.rollback()
        
        # Final commit after file done
        session.commit()
        tdenv.DEBUG0("{count} {table}s imported", count=importCount, table=tableName)
