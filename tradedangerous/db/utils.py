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
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from sqlalchemy import text

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
from datetime import datetime, timezone
from typing import Optional
import re

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
