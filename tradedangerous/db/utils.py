# tradedangerous/db/utils.py


# tradedangerous/db/utils.py
# -----------------------------------------------------------------------------
# Utility helpers for DB/dialect-specific behaviour used by the Spansh plugin.
#
# IMPORTANT: The project already provides `parse_ts(value) -> datetime|None`.
# Per your note, DO NOT duplicate it here. Append the existing `parse_ts`
# implementation after this block when integrating.
#
# This module centralises:
#   - Session construction (engine-bound)
#   - Backend-sensitive defaults (e.g., batching)
#   - Efficient MAX(modified) lookups
#   - Optional bulk upsert helpers (MariaDB/MySQL, SQLite), with a safe fallback
#   - Category name → id cache construction
#   - Bootstrap shim
#
# All functions are written to be safe on both SQLite and MariaDB. When a
# backend lacks native UPSERT convenience, we fall back to row-wise logic.
# -----------------------------------------------------------------------------

from __future__ import annotations

from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

from datetime import datetime
import math

from sqlalchemy import select, func, and_, literal_column
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import TableClause
from sqlalchemy.schema import Table

# Dialect-specific INSERT for true bulk upserts (when available)
try:
    from sqlalchemy.dialects.mysql import insert as mysql_insert  # MariaDB/MySQL
except Exception:  # pragma: no cover
    mysql_insert = None  # type: ignore[assignment]

try:
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert  # SQLite
except Exception:  # pragma: no cover
    sqlite_insert = None  # type: ignore[assignment]

__all__ = [
    "get_session",
    "default_batch_size",
    "max_modified_for_station",
    "bulk_upsert",
    "category_lookup_cache",
    "ensure_bootstrap",
    # parse_ts is provided elsewhere in the project; not exported here.
]


# ------------------------------
# Session / batching
# ------------------------------

def get_session(engine: Engine) -> Session:
    """
    Create a short-lived Session bound to `engine`.
    - expire_on_commit=False avoids heavy refresh churn during batch imports
    - autoflush=True keeps INSERT/UPDATE ordering sane without explicit flush()
    """
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=True)
    return factory()


def default_batch_size(engine: Engine) -> int:
    """
    Backend-sensitive default commit batch size when TD_LISTINGS_BATCH is unset.
    Tuned for update-heavy workloads.
    """
    name = (engine.dialect.name or "").lower()
    if name in ("mysql", "mariadb"):
        # Row-by-row upserts are cheap, network RTT dominates; bigger batches help.
        # Also tolerant of large transactions, but avoid gargantuan ones.
        return 20000
    if name == "sqlite":
        # SQLite benefits from moderate batches due to page locks and journaling.
        return 5000
    # Reasonable middle ground for other backends
    return 8000


# ------------------------------
# Targeted helpers
# ------------------------------

def max_modified_for_station(session: Session, table: Table, station_id: int) -> Optional[datetime]:
    """
    Return MAX(modified) for a given station_id in vendor/price link tables.
    Used to short-circuit unnecessary churn when inbound service timestamps
    are not newer than what we already have.
    """
    row = session.execute(
        select(func.max(table.c.modified)).where(table.c.station_id == station_id)
    ).first()
    return row[0] if row and row[0] is not None else None


def category_lookup_cache(session: Session, t_category: Table) -> Dict[str, int]:
    """
    Build a case-insensitive Category name → category_id mapping.
    Normalises keys to lower-case strings.
    """
    rows = session.execute(select(t_category.c.category_id, t_category.c.name)).all()
    return {str(name).lower(): int(cat_id) for (cat_id, name) in rows}


def ensure_bootstrap(tdb: Any) -> None:
    """
    Thin shim to invoke project bootstrap if available.
    Keeps plugin code DB-agnostic at call sites.
    """
    if hasattr(tdb, "bootstrap") and callable(tdb.bootstrap):
        tdb.bootstrap()


# ------------------------------
# Bulk upsert (optional acceleration)
# ------------------------------

def bulk_upsert(
    session: Session,
    table: Table,
    rows: Sequence[Mapping[str, Any]],
    conflict_cols: Tuple[str, ...],
    update_cols: Tuple[str, ...],
    *,
    batch_size: Optional[int] = None,
) -> int:
    """
    Execute a dialect-appropriate bulk UPSERT.

    Parameters
    ----------
    session : Session
        Active SQLAlchemy session.
    table : Table
        Target table (SQLAlchemy Core Table).
    rows : Sequence[Mapping[str, Any]]
        Rows to insert/update. Keys must be valid column names.
    conflict_cols : Tuple[str, ...]
        Column names forming the natural key / conflict target.
        For MariaDB/MySQL this implies a UNIQUE/PRIMARY KEY on these cols.
        For SQLite this implies a UNIQUE/PRIMARY KEY or explicit ON CONFLICT target.
    update_cols : Tuple[str, ...]
        Columns to update on conflict (others stay as inserted).
    batch_size : Optional[int]
        Optional chunk size for very large `rows`. Defaults to a heuristic.

    Returns
    -------
    int
        Approximate number of affected rows (driver-dependent; best-effort).

    Notes
    -----
    - MariaDB/MySQL: INSERT … ON DUPLICATE KEY UPDATE …
    - SQLite:        INSERT … ON CONFLICT(col,…) DO UPDATE SET …
    - Fallback:      Row-wise upsert (SELECT → INSERT/UPDATE), slower but correct.
    """
    if not rows:
        return 0

    affected = 0
    name = (session.get_bind().dialect.name or "").lower()

    # Heuristic batch size if not provided
    if batch_size is None:
        batch_size = 10000 if name in ("mysql", "mariadb") else 2000

    # Split into chunks to control memory/packet sizes
    for chunk in _iter_chunks(rows, batch_size):
        if name in ("mysql", "mariadb") and mysql_insert is not None:
            stmt = mysql_insert(table).values(list(chunk))
            update_map = {col: stmt.inserted[col] for col in update_cols}
            # ON DUPLICATE KEY UPDATE works off table unique/primary keys
            stmt = stmt.on_duplicate_key_update(**update_map)
            res = session.execute(stmt)
            # rowcount semantics vary; treat as best-effort
            affected += getattr(res, "rowcount", 0) or 0
        elif name == "sqlite" and sqlite_insert is not None:
            stmt = sqlite_insert(table).values(list(chunk))
            update_map = {col: getattr(stmt.excluded, col) for col in update_cols}
            stmt = stmt.on_conflict_do_update(
                index_elements=list(conflict_cols),
                set_=update_map,
            )
            res = session.execute(stmt)
            affected += getattr(res, "rowcount", 0) or 0
        else:
            # Fallback: row-wise upsert (portable, slower)
            for row in chunk:
                _row_upsert_portable(session, table, row, conflict_cols, update_cols)
                affected += 1

    return affected


# ------------------------------
# Internal helpers
# ------------------------------

def _iter_chunks(seq: Sequence[Mapping[str, Any]], size: int) -> Iterator[Sequence[Mapping[str, Any]]]:
    n = len(seq)
    if n <= size:
        yield seq
        return
    for i in range(0, n, size):
        yield seq[i : i + size]


def _row_upsert_portable(
    session: Session,
    table: Table,
    row: Mapping[str, Any],
    conflict_cols: Tuple[str, ...],
    update_cols: Tuple[str, ...],
) -> None:
    """
    Slow, fully portable row-wise upsert:
      - SELECT by conflict_cols
      - INSERT if missing
      - UPDATE update_cols if present
    """
    where = [table.c[col] == row[col] for col in conflict_cols]
    existing = session.execute(select(*(table.c[col] for col in conflict_cols)).where(and_(*where))).first()

    if existing is None:
        session.execute(table.insert().values(**row))
        return

    # Only update requested columns; leave keys/others alone
    update_values = {col: row[col] for col in update_cols if col in row}
    if update_values:
        session.execute(table.update().where(and_(*where)).values(**update_values))

from datetime import datetime

def parse_ts(ts):
    """Normalise timestamps to datetime (UTC-naive, microsecond=0).
    Accepts str (with optional 'T'/'Z'/'+00[:00]'), datetime, int/float epoch, or None.
    """
    if ts is None:
        return None

    if isinstance(ts, datetime):
        return ts.replace(tzinfo=None, microsecond=0)

    if isinstance(ts, (int, float)):
        return datetime.utcfromtimestamp(ts).replace(microsecond=0)

    if isinstance(ts, str):
        s = ts.strip()
        # Common Elite/Spansh quirks
        if s.endswith('Z'):
            s = s[:-1]
        if s.endswith('+00:00'):
            s = s[:-6]
        elif s.endswith('+00'):
            s = s[:-3]
        # Allow 'T' separator
        s = s.replace('T', ' ')
        # Ensure fractional part exists to match %f parser path
        if '.' not in s:
            s += '.0'
        try:
            dt = datetime.strptime(s, '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            # Fallback if someone sends milliseconds without leading zero padding
            # or a shorter date; extend as needed for your data.
            dt = datetime.strptime(s.split('.')[0], '%Y-%m-%d %H:%M:%S')
        return dt.replace(microsecond=0)

    raise TypeError(f"Unsupported timestamp type: {type(ts)}")

def get_import_batch_size(session) -> int | None:
    """
    Return the recommended batch commit size for CSV/ORM imports.

    - Respects TD_LISTINGS_BATCH environment variable (int).
    - Defaults:
        * SQLite → None (commit once at end, no batching).
        * MySQL/MariaDB → 50k rows per commit.
    """
    import os

    env_batch = os.environ.get("TD_LISTINGS_BATCH")
    if env_batch:
        try:
            return int(env_batch)
        except ValueError:
            # fall through to backend defaults
            pass

    dialect = session.bind.dialect.name
    if dialect in ("mysql", "mariadb"):
        return 50 * 1024  # ~50k rows per commit
    else:
        # SQLite (and any other backend) → commit once at end
        return None


