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
    """Execute a multi-statement SQL script using exec_driver_sql per statement."""
    # naive splitter: handles semicolon-terminated statements and strips comments/empty lines
    stmts: list[str] = []
    current: list[str] = []
    for raw_line in script.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("--"):
            continue
        current.append(raw_line)
        if line.endswith(";"):
            stmts.append("\n".join(current))
            current = []
    if current:
        stmts.append("\n".join(current))
    with engine.begin() as conn:
        for stmt in stmts:
            conn.exec_driver_sql(stmt)

def _create_sqlite_from_legacy(engine: Engine) -> None:
    """Create the SQLite schema by executing the legacy SQL file."""
    sql = _read_legacy_sql()
    _execute_sql_script(engine, sql)

# ---------- public resets ----------

def reset_sqlite(engine: Engine, metadata: MetaData | None = None) -> None:
    """Drop all user tables and recreate schema from the legacy SQLite SQL."""
    # Drop via Inspector (robust to partial schemas)
    insp = inspect(engine)
    with engine.begin() as conn:
        for tname in _user_tables(engine):
            conn.exec_driver_sql(f'DROP TABLE IF EXISTS "{tname}"')
        # Also drop views if present
        for v in getattr(insp, "get_view_names", lambda: [])() or []:  # type: ignore[attr-defined]
            conn.exec_driver_sql(f'DROP VIEW IF EXISTS "{v}"')
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
