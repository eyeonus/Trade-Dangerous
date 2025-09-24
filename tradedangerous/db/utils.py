# tradedangerous/db/utils.py
# -----------------------------------------------------------------------------
# Minimal utilities required by Spansh and other plugins
#
# Retained:
#   - parse_ts: Parse timestamps to UTC-naive datetime
#   - get_import_batch_size: Decide batch commit size based on dialect/env
# -----------------------------------------------------------------------------

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session


# -----------------------------------------------------------------------------
# Timestamp parsing
# -----------------------------------------------------------------------------
def parse_ts(value) -> Optional[datetime]:
    """
    Parse timestamp values into UTC-naive datetime (microseconds=0).

    - Accepts datetime, float (epoch), or str.
    - Returns None if parsing fails.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None, microsecond=0)
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value).replace(microsecond=0)
    if isinstance(value, str):
        try:
            # Try ISO-like formats
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
                tz=None
            ).replace(tzinfo=None, microsecond=0)
        except Exception:
            pass
        try:
            # Try legacy formats
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(microsecond=0)
        except Exception:
            return None
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
        * Postgres → 25k rows per commit.
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
    if dialect == "postgresql":
        return 25000
    if profile == "spansh":
        return 5000

    return None
