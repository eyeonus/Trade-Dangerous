# tradedangerous/db/locks.py
# -----------------------------------------------------------------------------
# Advisory lock helpers (MariaDB/MySQL) — per-station serialization
#
# SQLite compatibility:
#   - On SQLite (or any unsupported dialect), all helpers become NO-OPs and
#     behave as if the lock was immediately acquired (yield True). This lets
#     shared code run unchanged across backends.
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

# Precompiled SQL (MySQL/MariaDB only)
_SQL_GET_LOCK     = text("SELECT GET_LOCK(:k, :t)")
_SQL_RELEASE_LOCK = text("SELECT RELEASE_LOCK(:k)")

def _is_lock_supported(session: Session) -> bool:
    """
    Return True if the current SQLAlchemy session is bound to a backend that
    supports advisory locks via GET_LOCK/RELEASE_LOCK (MySQL/MariaDB).
    """
    try:
        name = (session.get_bind().dialect.name or "").lower()
    except Exception:
        name = ""
    return name in ("mysql", "mariadb")
    
def _ensure_read_committed(session: Session) -> None:
    """
    Ensure the session is using READ COMMITTED for subsequent transactions.
    - Applies only to MySQL/MariaDB.
    - No-ops on SQLite/others.
    - Only sets it if NOT already inside a transaction (affects next txn).
    """
    if not _is_lock_supported(session):
        return
    try:
        # Only set if we're not already in a transaction; otherwise it would
        # affect the next transaction, not the current one.
        if not session.in_transaction():
            session.execute(text("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED"))
            # No explicit commit needed; this is a session-level setting.
    except Exception:
        # Best-effort; if this fails we just proceed with the default isolation.
        pass

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
        True  -> acquired within timeout (or NO-OP True on unsupported dialects)
        False -> timed out (lock held elsewhere)

    Notes:
        - Advisory locks are per-connection. Use the same Session for acquire,
          the critical section, and release.
        - On SQLite/unsupported dialects, this is a NO-OP that returns True.
    """
    if not _is_lock_supported(session):
        return True  # NO-OP on SQLite/unsupported backends

    key = station_lock_key(station_id)
    row = session.execute(_SQL_GET_LOCK, {"k": key, "t": float(timeout_seconds)}).first()
    # MariaDB/MySQL GET_LOCK returns 1 (acquired), 0 (timeout), or NULL (error)
    return bool(row and row[0] == 1)

def release_station_lock(session: Session, station_id: int) -> None:
    """
    Release the advisory lock for a station on THIS DB connection.
    Safe to call in finally; releasing a non-held lock is harmless.

    On SQLite/unsupported dialects, this is a NO-OP.
    """
    if not _is_lock_supported(session):
        return  # NO-OP on SQLite/unsupported backends

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

    Deadlock-safety requirement:
      - Do NOT release the advisory lock before the station's writes are COMMITTED.
      - Previously we only committed when this helper created the transaction.
        If the Session already had an active transaction (SQLAlchemy autobegin),
        the lock could be released while row locks were still pending commit.

    Behaviour:
      - On MySQL/MariaDB: tries GET_LOCK() with bounded retries + exponential backoff.
      - If acquired (got=True): COMMIT on normal exit BEFORE releasing the advisory lock,
        regardless of whether this helper started the transaction.
      - If NOT acquired (got=False) and this helper started the transaction: ROLLBACK to
        avoid leaving an idle open transaction pinned to a connection.
      - If an exception escapes the caller's block: ROLLBACK (best-effort) then re-raise.
      - On unsupported dialects (e.g. SQLite): yields True and does nothing.

    WARNING:
      - Do not wrap this context manager inside an external transaction manager
        (e.g. `with session.begin():`) because it may COMMIT inside that scope.
    """
    # Fast-path NO-OP for SQLite/unsupported dialects
    if not _is_lock_supported(session):
        yield True
        return

    # Prefer READ COMMITTED to reduce lock contention (best-effort).
    _ensure_read_committed(session)

    started_txn = False
    txn_ctx = None
    if not session.in_transaction():
        # Pin lock + DML to the same connection by opening a txn.
        txn_ctx = session.begin()
        started_txn = True

    got = False
    try:
        attempt = 0
        while attempt < max_retries:
            if acquire_station_lock(session, station_id, timeout_seconds):
                got = True
                break
            time.sleep(backoff_start_seconds * (2 ** attempt))
            attempt += 1

        # Hand control to caller
        yield got

        if got:
            # Commit while the advisory lock is still held.
            if session.in_transaction():
                session.commit()
        else:
            # If we opened a txn just to attempt locking, close it out cleanly.
            if started_txn and session.in_transaction():
                session.rollback()

    except Exception:
        # Ensure we don't leak row locks / open txn on error.
        if session.in_transaction():
            try:
                session.rollback()
            except Exception:
                pass
        raise

    finally:
        # Release advisory lock after commit/rollback decisions above.
        if got:
            try:
                release_station_lock(session, station_id)
            except Exception:
                pass

        if started_txn and txn_ctx is not None:
            try:
                txn_ctx.close()
            except Exception:
                pass
