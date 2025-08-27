# tradedangerous/db/lifecycle.py
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import MetaData

# Canonical imports from production paths module
try:
    from .paths import resolve_sqlite_db_path, resolve_data_dir
except Exception:  # pragma: no cover - minimal fallback for isolated runs
    def resolve_sqlite_db_path(cfg, filename=None):  # type: ignore[no-redef]
        from pathlib import Path
        return Path("./data/TradeDangerous.db").resolve()
    def resolve_data_dir(cfg):  # type: ignore[no-redef]
        p = Path("./data"); p.mkdir(parents=True, exist_ok=True); return p

# ---------- utilities ----------

def is_sqlite(engine: Engine) -> bool:
    """Return True if the SQLAlchemy engine is using SQLite dialect."""
    return engine.dialect.name == "sqlite"

def _user_tables(engine: Engine) -> Iterable[str]:
    insp = inspect(engine)
    names = insp.get_table_names()
    if is_sqlite(engine):
        names = [n for n in names if not n.startswith("sqlite_")]
    return names

def is_empty(engine: Engine) -> bool:
    """True when no user tables exist (via SQLAlchemy Inspector)."""
    return len(list(_user_tables(engine))) == 0

def rotate_sqlite_db(data_dir: Path, filename: str = "TradeDangerous.db", old_name: str = "TradeDangerous.old") -> Path:
    """Rename the SQLite DB file to .old (idempotent). Safe if file missing.
    If the target .old already exists it is replaced.
    """
    src = (data_dir / filename).resolve()
    dst = (data_dir / old_name).resolve()
    if not src.exists():
        return dst
    try:
        if dst.exists():
            dst.unlink()
        src.rename(dst)
    except OSError:
        # As a last resort on cross-device moves, copy then unlink
        import shutil
        shutil.copy2(src, dst)
        src.unlink()
    return dst

# ---------- (re)creation helpers ----------

def _read_legacy_sql() -> str:
    """Load the legacy SQLite schema SQL (authoritative for SQLite)."""
    # Look in package templates first (canonical), then fallback to local file.
    candidates = [
        Path(__file__).resolve().parents[1] / "templates" / "TradeDangerous.sql",
        Path.cwd() / "tradedangerous" / "templates" / "TradeDangerous.sql",
        Path.cwd() / "tradedangerous" / "templates" / "TradeDangerous.sql".lower(),
        Path.cwd() / "TradeDangerous.sql",
    ]
    for p in candidates:
        if p.exists():
            return p.read_text(encoding="utf-8")
    raise FileNotFoundError("TradeDangerous.sql not found in expected locations.")

def _execute_sql_script(engine: Engine, script: str) -> None:
    """Execute a multi-statement SQL script using sqlite3's executescript()."""
    with engine.begin() as conn:
        raw_conn = conn.connection  # DB-API connection (sqlite3.Connection)
        raw_conn.executescript(script)


def _create_sqlite_from_legacy(engine: Engine) -> None:
    """Create the SQLite schema by executing the legacy SQL file."""
    sql = _read_legacy_sql()
    _execute_sql_script(engine, sql)

# ---------- public resets ----------

def reset_sqlite(engine: Engine, db_path: Path | None = None) -> None:
    """Reset the SQLite schema by rotating the DB file and recreating from legacy SQL."""
    if db_path:
        # Rotate the existing DB file
        if db_path.exists():
            backup = db_path.with_suffix(".old")
            if backup.exists():
                backup.unlink()
            db_path.rename(backup)
        db_path.parent.mkdir(parents=True, exist_ok=True)

    # Recreate schema using the canonical SQL file
    _create_sqlite_from_legacy(engine)


def reset_mariadb(engine: Engine, metadata: MetaData) -> None:
    """Drop all tables and recreate using ORM metadata (MariaDB/InnoDB)."""
    # Use metadata DDL; assume metadata is authoritative for MariaDB
    metadata.drop_all(bind=engine)
    metadata.create_all(bind=engine)

# ---------- orchestration ----------

def ensure_fresh_db(backend: str, engine: Engine, data_dir: Path, metadata: MetaData | None, mode: str = "auto") -> dict:
    """Ensure the database exists and is fresh per backend policy.

    SQLite:
      - If DB file missing → create from legacy SQL.
      - If empty or mode='force' → rotate file and recreate.
    MariaDB:
      - If empty → create via metadata.
      - If mode='force' → drop & recreate via metadata.

    Returns a dict summary (for logging/testing).
    """
    backend = (backend or "").lower()
    summary: dict = {"backend": backend, "mode": mode, "action": "noop"}

    if backend == "sqlite" or is_sqlite(engine):
        db_path = resolve_sqlite_db_path({"paths": {"data_dir": str(data_dir)}, "sqlite": {}}, filename="TradeDangerous.db")
        exists = db_path.exists()
        if not exists:
            data_dir.mkdir(parents=True, exist_ok=True)
            _create_sqlite_from_legacy(engine)
            summary.update(action="created", path=str(db_path))
            return summary

        if mode == "force" or is_empty(engine):
            rotate_sqlite_db(data_dir, filename=db_path.name)
            _create_sqlite_from_legacy(engine)
            summary.update(action="rotated+recreated", path=str(db_path))
            return summary

        summary.update(action="kept", path=str(db_path))
        return summary

    # MariaDB / MySQL family
    if metadata is None:
        raise ValueError("metadata is required for MariaDB lifecycle operations")
    if is_empty(engine):
        metadata.create_all(bind=engine)
        summary.update(action="created")
    elif mode == "force":
        reset_mariadb(engine, metadata)
        summary.update(action="reset")
    else:
        summary.update(action="kept")
    return summary
