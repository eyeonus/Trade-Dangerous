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

import json
import os
import time
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import text
from sqlalchemy.orm import Session

__all__ = [
    "station_advisory_lock",
    "acquire_station_lock",
    "release_station_lock",
    "station_lock_key",
]

# Precompiled SQL (MySQL/MariaDB only)
_SQL_GET_LOCK       = text("SELECT GET_LOCK(:k, :t)")
_SQL_RELEASE_LOCK   = text("SELECT RELEASE_LOCK(:k)")
_SQL_CONN_ID        = text("SELECT CONNECTION_ID()")
_SQL_IS_USED_LOCK   = text("SELECT IS_USED_LOCK(:k)")
_SQL_PROC_ROW       = text(
    "SELECT ID, USER, HOST, DB, COMMAND, TIME, STATE, INFO "
    "FROM information_schema.PROCESSLIST "
    "WHERE ID = :id"
)

_DIAG_ENABLED = str(os.environ.get("TD_LOCK_DIAG", "")).strip().lower() in ("1", "true", "yes", "on")
_DIAG_PATH = os.environ.get("TD_LOCK_DIAG_PATH", "")

_diag_fh = None  # type: ignore[assignment]


def _diag_write(event: dict[str, Any]) -> None:
    """
    Best-effort JSONL diagnostics for lock lifecycle.
    Enabled via TD_LOCK_DIAG=1.

    Notes:
      - Writes are append-only and flushed each line.
      - Intended for testbed use; may interleave if multiple processes write to same path.
    """
    global _diag_fh

    if not _DIAG_ENABLED:
        return

    now_epoch = time.time()
    event.setdefault("ts_epoch", now_epoch)
    event.setdefault(
        "ts_utc",
        datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    )
    event.setdefault("pid", os.getpid())
    event.setdefault("thread", threading.current_thread().name)

    try:
        if _diag_fh is None:
            if _DIAG_PATH:
                p = Path(_DIAG_PATH)
                # If TD_LOCK_DIAG_PATH is a directory, append filename
                if p.exists() and p.is_dir():
                    p = p / "lock_diag.jsonl"
            else:
                base = Path(os.environ.get("TD_TMP", "."))
                p = base / "lock_diag.jsonl"

            try:
                p.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

            _diag_fh = open(p, "a", encoding="utf-8")

        _diag_fh.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        _diag_fh.flush()
    except Exception:
        # diagnostics must never break lock behaviour
        pass


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


def _dialect_name(session: Session) -> str:
    try:
        return (session.get_bind().dialect.name or "").lower()
    except Exception:
        return ""


def _connection_id(session: Session) -> int | None:
    if not _is_lock_supported(session):
        return None
    try:
        row = session.execute(_SQL_CONN_ID).first()
        if row and row[0] is not None:
            return int(row[0])
    except Exception:
        pass
    return None


def _is_used_lock(session: Session, key: str) -> int | None:
    if not _is_lock_supported(session):
        return None
    try:
        row = session.execute(_SQL_IS_USED_LOCK, {"k": key}).first()
        if row and row[0] is not None:
            return int(row[0])
    except Exception:
        pass
    return None


def _processlist_row(session: Session, conn_id: int) -> dict[str, Any] | None:
    """
    Best-effort lookup of the processlist row for a given connection id.
    May fail if the DB user lacks privileges; diagnostics must not raise.
    """
    if not _is_lock_supported(session):
        return None
    try:
        row = session.execute(_SQL_PROC_ROW, {"id": int(conn_id)}).mappings().first()
        if row:
            # Normalize keys to lower-case for JSON stability
            return {str(k).lower(): row[k] for k in row.keys()}
    except Exception as e:
        _diag_write({"event": "processlist_lookup_failed", "conn_id": conn_id, "error": repr(e)})
    return None


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
    bind: Any,
    station_id: int,
    timeout_seconds: float = 0.2,
    max_retries: int = 4,
    backoff_start_seconds: float = 0.05,
) -> Iterator[Session | None]:
    """
    Context manager that pins a physical DB connection for the lifetime of a per-station advisory lock.
    
    MariaDB/MySQL named locks (GET_LOCK/RELEASE_LOCK) are scoped to the server connection (thread).
    If acquisition and release are performed on different physical connections (e.g. due to session
    commit/pool churn), locks can leak and block other workers indefinitely.
    
    This helper prevents leakage by:
      - pinning a dedicated SQLAlchemy Connection for the entire lock lifetime,
      - creating a Session bound to that pinned connection,
      - ensuring COMMIT occurs while the advisory lock is still held,
      - releasing the lock on the same pinned connection,
      - closing Session and Connection on exit.
    
    Yield:
      - Session (bound to pinned connection) if lock acquired,
      - None if lock could not be acquired within retry budget.
    
    SQLite/unsupported dialects:
      - yields a Session bound to the normal Engine without named-lock calls.
        (Multiprocessing is not supported there, but this keeps code paths usable.)
    """
    dialect = ""
    try:
        dialect = (getattr(getattr(bind, "dialect", None), "name", "") or "").lower()
    except Exception:
        dialect = ""
    
    # No-op advisory lock on unsupported dialects: just provide a session.
    if dialect not in ("mysql", "mariadb"):
        with Session(bind=bind) as s:
            yield s
        return
    
    key = station_lock_key(station_id)
    
    conn = bind.connect()
    s = Session(bind=conn)
    
    got = False
    acquired_conn_id: int | None = None
    try:
        _ensure_read_committed(s)
        
        attempt = 0
        while attempt < max_retries:
            conn_id = _connection_id(s)
            used_by = _is_used_lock(s, key)
            
            _diag_write(
                {
                    "event": "station_lock_attempt",
                    "dialect": dialect,
                    "station_id": int(station_id),
                    "lock_key": key,
                    "attempt": int(attempt + 1),
                    "conn_id": conn_id,
                    "lock_used_by_conn_id": used_by,
                }
            )
            
            if acquire_station_lock(s, station_id, timeout_seconds):
                got = True
                acquired_conn_id = _connection_id(s) or conn_id
                _diag_write(
                    {
                        "event": "station_lock_acquired",
                        "dialect": dialect,
                        "station_id": int(station_id),
                        "lock_key": key,
                        "attempt": int(attempt + 1),
                        "conn_id": acquired_conn_id,
                    }
                )
                
                break
            
            time.sleep(backoff_start_seconds * (2 ** attempt))
            attempt += 1
        
        if not got:
            used_by = _is_used_lock(s, key)
            proc = _processlist_row(s, used_by) if used_by is not None else None
            _diag_write(
                {
                    "event": "station_lock_giveup",
                    "dialect": dialect,
                    "station_id": int(station_id),
                    "lock_key": key,
                    "attempts": int(max_retries),
                    "conn_id": _connection_id(s),
                    "lock_used_by_conn_id": used_by,
                    "lock_holder_processlist": proc,
                }
            )
            
            yield None
            return
        
        yield s
        
        # Commit while advisory lock is still held (same pinned connection).
        if s.in_transaction():
            s.commit()
        
        _diag_write(
            {
                "event": "station_lock_post_commit",
                "dialect": dialect,
                "station_id": int(station_id),
                "lock_key": key,
                "acquired_conn_id": acquired_conn_id,
                "conn_id_now": _connection_id(s),
                "lock_used_by_conn_id_now": _is_used_lock(s, key),
            }
        )
    
    except Exception as e:
        _diag_write(
            {
                "event": "station_lock_exception",
                "dialect": dialect,
                "station_id": int(station_id),
                "lock_key": key,
                "acquired_conn_id": acquired_conn_id,
                "conn_id_now": _connection_id(s),
                "lock_used_by_conn_id_now": _is_used_lock(s, key),
                "error": repr(e),
            }
        )
        
        if s.in_transaction():
            try:
                s.rollback()
            except Exception:
                pass
        raise
    
    finally:
        if got:
            release_conn_id = _connection_id(s)
            release_result = None
            try:
                row = s.execute(_SQL_RELEASE_LOCK, {"k": key}).first()
                if row:
                    release_result = row[0]
            except Exception as e:
                _diag_write(
                    {
                        "event": "station_lock_release_failed",
                        "dialect": dialect,
                        "station_id": int(station_id),
                        "lock_key": key,
                        "acquired_conn_id": acquired_conn_id,
                        "release_conn_id": release_conn_id,
                        "error": repr(e),
                    }
                )
            
            used_after = _is_used_lock(s, key)
            leak = used_after is not None
            proc = _processlist_row(s, used_after) if used_after is not None else None
            
            _diag_write(
                {
                    "event": "station_lock_release",
                    "dialect": dialect,
                    "station_id": int(station_id),
                    "lock_key": key,
                    "acquired_conn_id": acquired_conn_id,
                    "release_conn_id": release_conn_id,
                    "release_result": release_result,
                    "lock_used_by_conn_id_after": used_after,
                    "leaked": leak,
                    "lock_holder_processlist_after": proc,
                }
            )
        
        try:
            s.close()
        except Exception:
            pass
        
        try:
            conn.close()
        except Exception:
            pass
