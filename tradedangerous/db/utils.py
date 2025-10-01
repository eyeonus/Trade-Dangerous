# tradedangerous/db/utils.py
# -----------------------------------------------------------------------------
# Minimal utilities required by Spansh and other plugins which require dialect
# specific code.
#
# Retained:
#   - parse_ts: Parse timestamps to UTC-naive datetime
#   - get_import_batch_size: Decide batch commit size based on dialect/env
# -----------------------------------------------------------------------------

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional, Iterable, Mapping, Sequence
import re

from sqlalchemy import Table, text, func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.mysql import insert as mysql_insert

# -----------------------------------------------------------------------------
# spansh helpers (db specific upserts)
# -----------------------------------------------------------------------------

# --- Dialect checks (unchanged) ---
def is_sqlite(session: Session) -> bool:
    try:
        return session.get_bind().dialect.name.lower() == "sqlite"
    except Exception:
        return False

def is_mysql(session: Session) -> bool:
    try:
        name = session.get_bind().dialect.name.lower()
        return name in ("mysql", "mariadb")
    except Exception:
        return False
        
def sqlite_set_bulk_pragmas(session: Session) -> None:
    """
    Apply connection-local PRAGMAs to speed up bulk imports.
    Safe defaults for an import session; durability is still acceptable with WAL.
    """
    conn = session.connection()
    # WAL gives better concurrency; synchronous=NORMAL keeps some safety at high speed.
    conn.execute(text("PRAGMA journal_mode=WAL"))
    conn.execute(text("PRAGMA synchronous=NORMAL"))
    # Keep temp structures in memory; increase page cache.
    conn.execute(text("PRAGMA temp_store=MEMORY"))
    # Negative cache_size is KiB; -65536 ≈ 64 MiB page cache
    conn.execute(text("PRAGMA cache_size=-65536"))
    
def sqlite_upsert_modified(
    session: Session,
    table: Table,
    rows: Iterable[Mapping[str, object]],
    *,
    key_cols: Sequence[str],
    modified_col: str,
    update_cols: Sequence[str],
) -> None:
    """
    SQLite ON CONFLICT fast-path with timestamp guard using the dialect insert():
      INSERT .. ON CONFLICT(<keys>) DO UPDATE SET <cols...>, modified=excluded.modified
      WHERE excluded.modified > table.modified OR table.modified IS NULL
    """
    rows = list(rows)
    if not rows:
        return

    stmt = sqlite_insert(table)
    excluded = stmt.excluded  # "excluded" namespace

    # Build set_ mapping for update columns + modified
    set_map = {c: getattr(excluded, c) for c in update_cols}
    set_map[modified_col] = getattr(excluded, modified_col)

    # WHERE guard: only update if incoming is newer (or DB NULL)
    where_guard = (getattr(excluded, modified_col) > getattr(table.c, modified_col)) | (
        getattr(table.c, modified_col).is_(None)
    )

    stmt = stmt.on_conflict_do_update(
        index_elements=list(key_cols),
        set_=set_map,
        where=where_guard,
    )

    session.execute(stmt, rows)

def sqlite_upsert_simple(
    session: Session,
    table: Table,
    rows: Iterable[Mapping[str, object]],
    *,
    key_cols: Sequence[str],
    update_cols: Sequence[str],
) -> None:
    """
    SQLite INSERT .. ON CONFLICT(<keys>) DO UPDATE SET <update_cols>
    (no timestamp guard) using dialect insert() so types are adapted correctly.
    """
    rows = list(rows)
    if not rows:
        return

    stmt = sqlite_insert(table)
    excluded = stmt.excluded
    set_map = {c: getattr(excluded, c) for c in update_cols}

    stmt = stmt.on_conflict_do_update(
        index_elements=list(key_cols),
        set_=set_map,
    )

    session.execute(stmt, rows)


def mysql_upsert_modified(
    session: Session,
    table: Table,
    rows: Iterable[Mapping[str, object]],
    *,
    key_cols: Sequence[str],      # present for interface symmetry
    modified_col: str,
    update_cols: Sequence[str],
) -> None:
    """
    MySQL/MariaDB ON DUPLICATE KEY fast-path using dialect insert().
    Only updates when incoming.modified > existing.modified OR existing is NULL.
    """
    rows = list(rows)
    if not rows:
        return

    ins = mysql_insert(table)
    inserted = ins.inserted  # alias to VALUES()/INSERTED

    # Guard: newer incoming timestamp or DB is NULL
    guard = (inserted[modified_col] > table.c[modified_col]) | (table.c[modified_col].is_(None))

    # For each update col, write: IF(guard, inserted.col, table.col)
    set_map = {
        c: func.if_(guard, inserted[c], table.c[c])
        for c in update_cols
    }
    # Always compute modified with the same guard
    set_map[modified_col] = func.if_(guard, inserted[modified_col], table.c[modified_col])

    stmt = ins.on_duplicate_key_update(**set_map)
    session.execute(stmt, rows)


def mysql_upsert_simple(
    session: Session,
    table: Table,
    rows: Iterable[Mapping[str, object]],
    *,
    key_cols: Sequence[str],      # present for interface symmetry
    update_cols: Sequence[str],
) -> None:
    """
    MySQL/MariaDB ON DUPLICATE KEY fast-path (no timestamp guard) using dialect insert().
    Updates the listed columns unconditionally to INSERTED/VALUES().
    """
    rows = list(rows)
    if not rows:
        return

    ins = mysql_insert(table)
    inserted = ins.inserted

    set_map = {c: inserted[c] for c in update_cols}

    stmt = ins.on_duplicate_key_update(**set_map)
    session.execute(stmt, rows)

# -----------------------------------------------------------------------------
# csvexport helpers (schema introspection)
# -----------------------------------------------------------------------------
# These functions are used by csvexport.exportTableToFile() to reconstruct
# headers (incl. unique columns and foreign-key references) in a backend-
# independent way.
#
# Implemented here in utils.py so that both SQLite (PRAGMA) and SQL backends
# (MariaDB/MySQL INFORMATION_SCHEMA, etc.) can share common logic.
#
# Notes:
#   * SQLite → PRAGMA index_list / index_info / foreign_key_list
#   * MySQL/MariaDB → INFORMATION_SCHEMA.STATISTICS / KEY_COLUMN_USAGE
#   * Other backends (e.g. PostgreSQL) would need catalog queries added here.
#
# These helpers are not intended for general ORM use — only to support
# correct CSV header reconstruction during exports.
# -----------------------------------------------------------------------------

def get_unique_columns(session, table_name: str) -> list[str]:
    """
    Return a list of unique column names for a table.
    Dialect-specific implementations:
      * SQLite → PRAGMA index_list + PRAGMA index_info
      * MariaDB/MySQL → INFORMATION_SCHEMA.STATISTICS
      * Other backends will require solutions in dialect e.g. Postgres catalogs
    """
    engine = session.get_bind()
    dialect = engine.dialect.name.lower()

    if dialect == "sqlite":
        conn = session.connection().connection
        cur = conn.cursor()
        uniques = []
        for idxRow in cur.execute(f"PRAGMA index_list('{table_name}')"):
            if idxRow[2]:  # 'unique' flag
                for unqRow in conn.execute(f"PRAGMA index_info('{idxRow[1]}')"):
                    col = unqRow[2]
                    if col not in uniques:
                        uniques.append(col)
        return uniques

    elif dialect in ("mysql", "mariadb"):
        sql = text("""
            SELECT DISTINCT COLUMN_NAME
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table
              AND NON_UNIQUE = 0
        """)
        rows = session.execute(sql, {"table": table_name}).fetchall()
        return [r[0] for r in rows]

    else:
        # Fallback: try SQLAlchemy inspector
        insp = session.get_bind().inspect(session.get_bind())
        cols = []
        try:
            pk = insp.get_pk_constraint(table_name) or {}
            cols.extend(pk.get("constrained_columns", []))
        except Exception:
            pass
        try:
            for uc in insp.get_unique_constraints(table_name) or []:
                cols.extend(uc.get("column_names", []))
        except Exception:
            pass
        return list(set(cols))


def get_foreign_keys(session, table_name: str) -> list[dict]:
    """
    Return list of foreign key mappings:
      { "table": <ref_table>, "from": <local_col>, "to": <ref_col> }

    Dialect-specific implementations:
      * SQLite → PRAGMA foreign_key_list
      * MariaDB/MySQL → INFORMATION_SCHEMA.KEY_COLUMN_USAGE
      * Other backends will require solutions in dialect e.g. Postgres catalogs
    """
    engine = session.get_bind()
    dialect = engine.dialect.name.lower()

    if dialect == "sqlite":
        conn = session.connection().connection
        cur = conn.cursor()
        fkeys = []
        for row in cur.execute(f"PRAGMA foreign_key_list('{table_name}')"):
            fkeys.append({
                "table": row[2],
                "from": row[3],
                "to": row[4],
            })
        return fkeys

    elif dialect in ("mysql", "mariadb"):
        sql = text("""
            SELECT COLUMN_NAME AS `from`,
                   REFERENCED_TABLE_NAME AS `table`,
                   REFERENCED_COLUMN_NAME AS `to`
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table
              AND REFERENCED_TABLE_NAME IS NOT NULL
        """)
        rows = session.execute(sql, {"table": table_name}).fetchall()
        return [{"table": r[1], "from": r[0], "to": r[2]} for r in rows]

    else:
        # Fallback: use SQLAlchemy inspector
        insp = session.get_bind().inspect(session.get_bind())
        fkeys = []
        try:
            for fk in insp.get_foreign_keys(table_name) or []:
                if not fk.get("referred_table") or not fk.get("constrained_columns"):
                    continue
                fkeys.append({
                    "table": fk["referred_table"],
                    "from": fk["constrained_columns"][0],
                    "to": fk["referred_columns"][0],
                })
        except Exception:
            pass
        return fkeys


# -----------------------------------------------------------------------------
# Timestamp parsing
# -----------------------------------------------------------------------------


def parse_ts(value) -> Optional[datetime]:
    """
    Parse timestamp values into UTC-naive datetime (microsecond=0).

    Accepts:
      - None -> None
      - datetime (aware/naive)
      - int/float epoch seconds
      - str:
          * ISO-like with 'Z', '+HH', '+HHMM', or '+HH:MM'
          * Space-separated 'YYYY-MM-DD HH:MM:SS[ offset]'
          * Date-only 'YYYY-MM-DD'

    Rules:
      - 'Z' -> '+00:00'
      - '+HHMM' -> '+HH:MM'
      - '+HH' -> '+HH:00'
      - single space between date/time -> replaced with 'T'
      - Aware datetimes -> converted to UTC then made naive
    """
    if value is None:
        return None

    # datetime input
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt.replace(microsecond=0)

    # epoch seconds
    if isinstance(value, (int, float)):
        try:
            return datetime.utcfromtimestamp(float(value)).replace(microsecond=0)
        except Exception:
            return None

    # string input
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None

        # Normalise timezone notations
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        # ' ' -> 'T' to please fromisoformat
        if " " in s and "T" not in s:
            s = s.replace(" ", "T", 1)
        # +HHMM -> +HH:MM
        s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)
        # +HH -> +HH:00   (ensure we didn't just match +HH:MM)
        s = re.sub(r"([+-]\d{2})(?!:\d{2})$", r"\1:00", s)

        # Try ISO parse
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt.replace(microsecond=0)
        except Exception:
            pass

        # Legacy / naive formats (assume UTC)
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).replace(microsecond=0)
            except Exception:
                continue

    return None

# -----------------------------------------------------------------------------
# Batch size calculation
# -----------------------------------------------------------------------------
def get_import_batch_size(session: Session, profile: str | None = None) -> int | None:
    """
    Return the recommended batch commit size for imports.

    - Respects TD_LISTINGS_BATCH environment variable (int).
    - Defaults:
        * SQLite → None (commit once at end, no batching).
        * MySQL/MariaDB → 50k rows per commit.
        * Spansh profile → conservative 5k rows per commit if not otherwise set.
    """
    env_batch = os.environ.get("TD_LISTINGS_BATCH")
    if env_batch:
        try:
            return int(env_batch)
        except ValueError:
            # fall through to backend defaults
            pass

    dialect = session.bind.dialect.name

    if dialect == "sqlite":
        return None
    if dialect in ("mysql", "mariadb"):
        return 50000
    if profile == "spansh":
        return 5000

    return None
