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
from typing import Optional, Iterable, Mapping, Sequence, Literal, Callable, Dict, Any
import re

from sqlalchemy import Table, text, func, and_, bindparam
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.sql.elements import ClauseElement


# --------------------------------------------------------
# eddblink helpers
# --------------------------------------------------------

def begin_bulk_mode(
    session: Session,
    *,
    profile: str = "default",
    phase: Literal["rebuild", "incremental"] = "incremental",
) -> dict[str, Any]:
    """
    Apply connection-local settings to speed up bulk operations.
    Returns an opaque token for symmetry with end_bulk_mode (currently a no-op).

    - SQLite: ensure WAL, temp_store, cache; set synchronous=OFF for raw speed.
    - MySQL/MariaDB: apply per-session import tunings (reduced fsync, lower waits).

    Notes:
      * Settings are connection-scoped and reset when the connection is returned
        to the pool or closed.
      * This is generic and safe for any plugin invoking long-running bulk writes.
    """
    token: dict[str, Any] = {"dialect": None, "profile": profile, "phase": phase}

    try:
        dialect = session.get_bind().dialect.name.lower()
    except Exception:
        return token  # best-effort, no-op if we can't detect

    token["dialect"] = dialect

    if dialect == "sqlite":
        try:
            conn = session.connection()
            # Speed-first defaults (align with schema PRAGMAs).
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=OFF"))
            conn.execute(text("PRAGMA temp_store=MEMORY"))
            # Negative cache_size is KiB; -65536 ≈ 64 MiB
            conn.execute(text("PRAGMA cache_size=-65536"))
            # File-level; harmless to set each time.
            conn.execute(text("PRAGMA auto_vacuum=INCREMENTAL"))
        except Exception:
            # Best-effort; keep going if PRAGMA adjustment fails.
            pass
        return token

    if dialect in ("mysql", "mariadb"):
        try:
            mysql_set_bulk_session(session)
        except Exception:
            pass
        return token

    # Other dialects: nothing applied
    return token


def end_bulk_mode(session: Session, token: Dict[str, Any] | None = None) -> None:
    """
    Placeholder symmetry for begin_bulk_mode. Currently a no-op because we only
    *set* per-session tunings that naturally revert when the connection returns
    to the pool. Kept for future extensibility.
    """
    return


def get_upsert_fn(
    session: Session,
    table: Table,
    *,
    key_cols: Sequence[str],
    update_cols: Sequence[str],
    modified_col: Optional[str] = None,
    always_update: Sequence[str] = (),
) -> Callable[[Iterable[Mapping[str, object]]], None]:
    """
    Return a callable that performs a batched upsert into `table` using the
    fastest dialect-specific path available (SQLAlchemy Core).

    - If `modified_col` is provided:
        * SQLite → INSERT .. ON CONFLICT DO UPDATE with WHERE guard using modified
        * MySQL  → INSERT .. ON DUPLICATE KEY UPDATE with IF(guard, inserted, table)
      Only the columns listed in `update_cols` are guarded by `modified_col`.

    - Columns listed in `always_update` are synchronized unconditionally even
      when modified timestamps are equal. This is implemented as a small,
      portable second-pass UPDATE keyed by `key_cols`.

    Usage example:
        upsert = get_upsert_fn(
            session,
            SA.StationItem.__table__,
            key_cols=("station_id","item_id"),
            update_cols=("demand_price","demand_units","demand_level",
                         "supply_price","supply_units","supply_level","from_live"),
            modified_col="modified",
            always_update=("from_live",),  # force-sync live flag even if modified equal
        )
        upsert(batch_of_row_dicts)
    """
    try:
        dialect = session.get_bind().dialect.name.lower()
    except Exception:
        dialect = "unknown"

    def _primary_upsert(rows: Iterable[Mapping[str, object]]) -> None:
        batch = list(rows)
        if not batch:
            return

        if modified_col:
            if dialect == "sqlite":
                sqlite_upsert_modified(
                    session,
                    table,
                    batch,
                    key_cols=key_cols,
                    modified_col=modified_col,
                    update_cols=update_cols,
                )
            elif dialect in ("mysql", "mariadb"):
                mysql_upsert_modified(
                    session,
                    table,
                    batch,
                    key_cols=key_cols,
                    modified_col=modified_col,
                    update_cols=update_cols,
                )
            else:
                # Fallback: simple upsert without guard
                if dialect == "sqlite":
                    sqlite_upsert_simple(session, table, batch, key_cols=key_cols, update_cols=update_cols)
                elif dialect in ("mysql", "mariadb"):
                    mysql_upsert_simple(session, table, batch, key_cols=key_cols, update_cols=update_cols)
                else:
                    raise RuntimeError(f"Unsupported dialect for modified upsert: {dialect}")
        else:
            if dialect == "sqlite":
                sqlite_upsert_simple(session, table, batch, key_cols=key_cols, update_cols=update_cols)
            elif dialect in ("mysql", "mariadb"):
                mysql_upsert_simple(session, table, batch, key_cols=key_cols, update_cols=update_cols)
            else:
                raise RuntimeError(f"Unsupported dialect for simple upsert: {dialect}")

    def _always_update_pass(rows: Iterable[Mapping[str, object]]) -> None:
        if not always_update:
            return
        batch = list(rows)
        if not batch:
            return

        # UPDATE table SET c1=:c1, ... WHERE k1=:__key__k1 AND k2=:__key__k2
        where_clause = and_(*[table.c[k] == bindparam(f"__key__{k}") for k in key_cols])
        upd = table.update().where(where_clause).values({c: bindparam(c) for c in always_update})

        params: list[Dict[str, object]] = []
        for row in batch:
            # Only issue an UPDATE if at least one always_update value is present
            p: Dict[str, object] = {}
            for k in key_cols:
                p[f"__key__{k}"] = row[k]
            present = False
            for c in always_update:
                if c in row:
                    p[c] = row[c]
                    present = True
            if present:
                params.append(p)

        if params:
            session.execute(upd, params)

    def _upsert(rows: Iterable[Mapping[str, object]]) -> None:
        batch = list(rows)
        if not batch:
            return
        _primary_upsert(batch)
        _always_update_pass(batch)

    return _upsert


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
    where_guard = (getattr(excluded, modified_col) >= getattr(table.c, modified_col)) | (
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

def mysql_set_bulk_session(session: Session) -> None:
    """
    Per-session tuning for bulk imports (MariaDB/MySQL).
    Session-scoped, resets when the connection closes/recycles.
    Conservative defaults for import workloads.
    """
    conn = session.connection()
    # Reduce fsyncs; lose up to ~1s of transactions on power loss (import-safe).
    conn.execute(text("SET SESSION innodb_flush_log_at_trx_commit=2"))
    # Amortize binlog fsync if binlog is enabled.
    conn.execute(text("SET SESSION sync_binlog=0"))
    # Reader-friendly concurrency and shorter lock waits.
    conn.execute(text("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED"))
    conn.execute(text("SET SESSION innodb_lock_wait_timeout=10"))
    # Optional micro-wins on constraint checking (safe for our import order).
    conn.execute(text("SET SESSION foreign_key_checks=0"))
    conn.execute(text("SET SESSION unique_checks=0"))
    # If permitted, skipping binlog on this session can be a big win (DEV ONLY).
    try:
        conn.execute(text("SET SESSION sql_log_bin=0"))
    except Exception:
        # Not always allowed; silently ignore.
        pass
        
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
    guard = (inserted[modified_col] >= table.c[modified_col]) | (table.c[modified_col].is_(None))

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
        uniques: list[str] = []
        # Pre-escape table name for PRAGMA
        esc_table = table_name.replace("'", "''")
        for idxRow in cur.execute(f"PRAGMA index_list('{esc_table}')"):
            # idxRow: (seq, name, unique, origin, partial) — unique is at index 2
            if idxRow[2]:  # 'unique' flag is truthy for UNIQUE indexes
                idx_name = idxRow[1]
                esc_idx = idx_name.replace("'", "''")
                for unqRow in conn.execute(f"PRAGMA index_info('{esc_idx}')"):
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
        fkeys: list[dict] = []
        esc_table = table_name.replace("'", "''")
        for row in cur.execute(f"PRAGMA foreign_key_list('{esc_table}')"):
            # row: (id, seq, table, from, to, on_update, on_delete, match)
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
        fkeys: list[dict] = []
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
# Timestamp Helpers
# -----------------------------------------------------------------------------

def age_in_days(session: Session, column: ClauseElement) -> ClauseElement:
    """
    Return a dialect-safe SQLAlchemy expression that yields the age of `column`
    (a DATETIME/TIMESTAMP) in **whole days** relative to the database's current date.

    Dialect mappings:
      * SQLite    →  julianday(CURRENT_DATE) - julianday(column)
      * MySQL/MariaDB → TIMESTAMPDIFF(DAY, column, CURRENT_DATE())
      * Others    →  DATE(NOW()) - DATE(column)   (best-effort integer days)

    Notes:
      - Designed for use in aggregates (e.g., func.avg(age_in_days(...))).
      - Leaves NULL handling to the caller (filter or COALESCE as needed).
    """
    engine = session.get_bind()
    dialect = engine.dialect.name.lower()

    if dialect == "sqlite":
        # julianday() returns a fractional day difference (FLOAT).
        return func.julianday() - func.julianday(column)

    if dialect in ("mysql", "mariadb"):
        # TIMESTAMPDIFF returns an integer number of DAY boundaries crossed.
        # Use CURRENT_DATE() to avoid time-of-day skew.
        return func.timestampdiff(text("DAY"), column, func.current_date())

    # Fallback (e.g., PostgreSQL, etc.): integer days between dates
    # DATE(NOW()) - DATE(column) yields an integer in many SQL dialects.
    return func.date(func.now()) - func.date(column)

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
