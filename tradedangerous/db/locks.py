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

    Resilience improvement:
      - If no transaction is active on the Session, this helper will OPEN ONE,
        so the lock is taken on the same physical connection the ensuing DML uses.
        In that case, it will COMMIT on normal exit, or ROLLBACK if an exception
        bubbles out of the context block.
      - If a transaction is already active, this helper does NOT touch txn
        boundaries; caller remains responsible for commit/rollback.

    Yields:
        acquired (bool): True if acquired within retry policy;
                         True immediately on unsupported dialects (NO-OP);
                         False if not acquired on supported backends.
    """
    # Fast-path NO-OP for SQLite/unsupported dialects
    if not _is_lock_supported(session):
        try:
            yield True
        finally:
            pass
        return

    # If we can still influence the next txn, prefer READ COMMITTED for shorter waits.
    _ensure_read_committed(session)

    # Pin a connection if caller hasn't already begun a transaction.
    started_txn = False
    txn_ctx = None
    if not session.in_transaction():
        txn_ctx = session.begin()
        started_txn = True

    got = False
    try:
        # Attempt with bounded retries + exponential backoff.
        attempt = 0
        while attempt < max_retries:
            if acquire_station_lock(session, station_id, timeout_seconds):
                got = True
                break
            time.sleep(backoff_start_seconds * (2 ** attempt))
            attempt += 1

        # Hand control to caller
        yield got

        # If we created the transaction and no exception occurred, commit it.
        if started_txn and got:
            try:
                session.commit()
            except Exception:
                # If commit fails, make sure to roll back so we don't leak an open txn.
                session.rollback()
                raise
    except Exception:
        # If we created the transaction and an exception escaped the block, roll it back.
        if started_txn and session.in_transaction():
            try:
                session.rollback()
            except Exception:
                # Swallow secondary rollback failures; original exception should propagate.
                pass
        raise
    finally:
        # Always release the advisory lock if we acquired it.
        if got:
            try:
                release_station_lock(session, station_id)
            except Exception:
                # Lock releases are best-effort; don't mask user exceptions.
                pass

        # If we opened a txn context object (older SA versions), ensure it's closed.
        # (Harmless if already committed/rolled back above.)
        if started_txn and txn_ctx is not None:
            try:
                txn_ctx.close()
            except Exception:
                pass
