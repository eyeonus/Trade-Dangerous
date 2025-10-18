# tradedangerous/db/locks.py
# -----------------------------------------------------------------------------
# Advisory lock helpers (MariaDB/MySQL) — per-station serialization
#
# Usage (both writers must use the SAME key format):
#   from tradedangerous.db.locks import station_advisory_lock
#
#   with sa_session_local(session_factory) as s:
#       # (optional) set isolation once per process elsewhere:
#       # s.execute(text("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")); s.commit()
#       with station_advisory_lock(s, station_id, timeout_seconds=0.2, max_retries=4) as got:
#           if not got:
#               # processor: defer/requeue work for this station and continue
#               return
#           with s.begin():
#               # do per-station writes here...
#               pass
# -----------------------------------------------------------------------------

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import text
from sqlalchemy.orm import Session

__all__ = [
    "station_advisory_lock",
    "acquire_station_lock",
    "release_station_lock",
    "station_lock_key",
]

# Precompiled SQL
_SQL_GET_LOCK     = text("SELECT GET_LOCK(:k, :t)")
_SQL_RELEASE_LOCK = text("SELECT RELEASE_LOCK(:k)")

def station_lock_key(station_id: int) -> str:
    """
    Return the advisory lock key used by both writers for the same station.
    Keep this format identical in all writers (processor + Spansh).
    """
    return f"td.station.{int(station_id)}"

def acquire_station_lock(session: Session, station_id: int, timeout_seconds: float) -> bool:
    """
    Try to acquire the advisory lock for a station on THIS DB connection.

    Returns:
        True  -> acquired within timeout
        False -> timed out (lock held elsewhere)

    Notes:
        - Advisory locks are per-connection. Use the same Session for acquire,
          the critical section, and release.
        - GET_LOCK returns 1 (acquired), 0 (timeout), or NULL (error).
    """
    key = station_lock_key(station_id)
    row = session.execute(_SQL_GET_LOCK, {"k": key, "t": float(timeout_seconds)}).first()
    return bool(row and row[0] == 1)

def release_station_lock(session: Session, station_id: int) -> None:
    """
    Release the advisory lock for a station on THIS DB connection.
    Safe to call in finally; releasing a non-held lock is harmless.
    """
    key = station_lock_key(station_id)
    try:
        session.execute(_SQL_RELEASE_LOCK, {"k": key})
    except Exception:
        # Intentionally swallow — RELEASE_LOCK may return 0/NULL if not held.
        pass

@contextmanager
def station_advisory_lock(
    session: Session,
    station_id: int,
    timeout_seconds: float = 0.2,
    max_retries: int = 4,
    backoff_start_seconds: float = 0.05,
) -> Iterator[bool]:
    """
    Context manager to acquire/retry/release a per-station advisory lock.

    Yields:
        acquired (bool): True if acquired within retry policy; False if not.

    Typical policies:
        - ZMQ processor (avoid head-of-line blocking):
            timeout_seconds=0.0, max_retries=4, backoff_start_seconds=0.05
            If not acquired -> defer/requeue station and continue.

        - Spansh importer (prefer to wait briefly):
            timeout_seconds=2.0, max_retries=4, backoff_start_seconds=0.05
            If not acquired -> retry that station later in the importer loop.

    IMPORTANT:
        - Use the SAME Session for acquire + critical section + release.
        - COMMIT/ROLLBACK do NOT release advisory locks; closing the connection does.
        - Always release in 'finally' (handled by this context manager when acquired).
    """
    got = False
    try:
        attempt = 0
        while attempt < max_retries:
            if acquire_station_lock(session, station_id, timeout_seconds):
                got = True
                break
            # Timed out — brief exponential backoff before retry
            time.sleep(backoff_start_seconds * (2 ** attempt))
            attempt += 1
        yield got
    finally:
        if got:
            release_station_lock(session, station_id)
