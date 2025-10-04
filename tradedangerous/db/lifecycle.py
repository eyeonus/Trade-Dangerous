# tradedangerous/db/lifecycle.py
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Tuple, Optional, Dict

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import MetaData


# --------------------------------------------------------------------
# Utilities
# --------------------------------------------------------------------

def is_sqlite(engine: Engine) -> bool:
    """Return True if the SQLAlchemy engine is using SQLite dialect."""
    return engine.dialect.name == "sqlite"


def _user_tables(engine: Engine) -> Iterable[str]:
    """List user (non-internal) tables present in the current database."""
    insp = inspect(engine)
    names = insp.get_table_names()
    if is_sqlite(engine):
        names = [n for n in names if not n.startswith("sqlite_")]
    return names


def is_empty(engine: Engine) -> bool:
    """True when no user tables exist (via SQLAlchemy Inspector)."""
    return len(list(_user_tables(engine))) == 0


def rotate_sqlite_db(
    data_dir: Path,
    filename: str = "TradeDangerous.db",
    old_name: str = "TradeDangerous.old",
) -> Path:
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


# --------------------------------------------------------------------
# (Re)creation helpers — prefer explicit paths; discovery is fallback
# --------------------------------------------------------------------

def _read_sql_file(sql_path: Path) -> str:
    """Read the provided SQL file (authoritative SQLite schema)."""
    if not sql_path.exists():
        raise FileNotFoundError(f"SQLite schema file not found: {sql_path}")
    return sql_path.read_text(encoding="utf-8")


def _read_legacy_sql() -> str:
    """Fallback: locate the legacy SQLite schema SQL if an explicit path was not provided."""
    candidates = [
        Path(__file__).resolve().parents[1] / "templates" / "TradeDangerous.sql",
        Path.cwd() / "tradedangerous" / "templates" / "TradeDangerous.sql",
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


def _create_sqlite_from_legacy(engine: Engine, sql_path: Optional[Path] = None) -> None:
    """Create the SQLite schema by executing the legacy SQL (explicit path preferred)."""
    if sql_path is not None:
        sql = _read_sql_file(sql_path)
    else:
        sql = _read_legacy_sql()
    _execute_sql_script(engine, sql)


# --------------------------------------------------------------------
# Public resets
# --------------------------------------------------------------------

def reset_sqlite(engine: Engine, db_path: Path, sql_path: Optional[Path] = None) -> None:
    """Reset the SQLite schema by rotating the DB file and recreating from legacy SQL."""
    # Rotate the existing DB file (if present) and ensure directory exists
    if db_path.exists():
        backup = db_path.with_suffix(".old")
        if backup.exists():
            backup.unlink()
        db_path.rename(backup)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Recreate schema using the provided canonical SQL file (or fallback discovery)
    _create_sqlite_from_legacy(engine, sql_path=sql_path)


def reset_mariadb(engine: Engine, metadata: MetaData) -> None:
    """Drop all tables and recreate using ORM metadata (MariaDB/InnoDB)."""
    metadata.drop_all(bind=engine)
    metadata.create_all(bind=engine)


# --------------------------------------------------------------------
# Unified reset entry point (dialect hidden from callers)
# --------------------------------------------------------------------

def reset_db(engine: Engine, *, db_path: Path, sql_path: Optional[Path] = None) -> str:
    """
    Reset the database schema for the given engine in a dialect-appropriate way.

    Caller MUST pass the canonical on-disk `db_path` for SQLite and SHOULD pass `sql_path`.
    (No path deduction is attempted here beyond optional SQL discovery.)

    Returns a short action string for logs/tests.
    """
    dialect = engine.dialect.name.lower()

    if dialect == "sqlite":
        reset_sqlite(engine, db_path=db_path, sql_path=sql_path)
        return "sqlite:rotated+recreated"

    if dialect in ("mysql", "mariadb"):
        # Resolve ORM metadata internally to avoid dialect branching at call sites.
        from tradedangerous.db import orm_models
        reset_mariadb(engine, orm_models.Base.metadata)
        return f"{dialect}:reset"

    raise RuntimeError(f"Unsupported database backend: {engine.dialect.name}")


# --------------------------------------------------------------------
# Sanity checks (seconds-only, no deep I/O)
# --------------------------------------------------------------------

# NOTE: 'Added' removed from core set (being deprecated)
_CORE_TABLES: Tuple[str, ...] = (
    "System",
    "Station",
    "Category",
    "Item",
    "StationItem",
)

def _core_tables_and_pks_ok(engine: Engine) -> Tuple[bool, List[str]]:
    """
    T1 + T2: Required core tables exist and have primary keys.
    Returns (ok, problems).
    """
    problems: List[str] = []
    insp = inspect(engine)

    existing = set(insp.get_table_names())
    missing = [t for t in _CORE_TABLES if t not in existing]
    if missing:
        problems.append(f"missing tables: {', '.join(missing)}")
        return False, problems

    for t in _CORE_TABLES:
        pk = insp.get_pk_constraint(t) or {}
        cols = pk.get("constrained_columns") or []
        if not cols:
            problems.append(f"missing primary key on {t}")

    return (len(problems) == 0), problems


def _seed_counts_ok(engine: Engine) -> Tuple[bool, List[str]]:
    """
    T4: Minimal seed/anchor rows must exist.
      - Category > 0
      - System   > 0
    """
    problems: List[str] = []
    with engine.connect() as conn:
        for tbl in ("Category", "System"):
            cnt = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar() or 0
            if cnt <= 0:
                problems.append(f"{tbl} is empty")

    return (len(problems) == 0), problems


def _connectivity_ok(engine: Engine) -> bool:
    """T0: Cheap connectivity probe (redundant if T4 runs, but negligible)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# --------------------------------------------------------------------
# Orchestration (policy) — may call buildCache
# --------------------------------------------------------------------

def ensure_fresh_db(
    backend: str,
    engine: Engine,
    data_dir: Path,
    metadata: MetaData | None,
    mode: str = "auto",
    *,
    tdb=None,
    tdenv=None,
) -> Dict[str, str]:
    """
    Ensure a *sane, populated* database exists (seconds-only checks).

      - T0: connectivity
      - T1: required core tables exist
      - T2: each core table has a PK
      - T4: seed rows exist in Category and System

    Actions:
      - mode == "force"                 → rebuild via buildCache(...)
      - mode == "auto" and not sane    → rebuild via buildCache(...)
      - else                           → kept

    NOTE: To rebuild/populate, we need `tdb` and `tdenv` so we can call buildCache.
          If missing in a rebuild-required branch, a ValueError is raised.
    """
    summary: Dict[str, str] = {
        "backend": (backend or engine.dialect.name).lower(),
        "mode": mode,
        "action": "kept",
    }

    # T0: cheap connectivity
    if not _connectivity_ok(engine):
        summary["reason"] = "connectivity-failed"
        if mode == "auto":
            mode = "force"

    # T1+T2: structure; T4: seeds
    structure_ok, struct_problems = _core_tables_and_pks_ok(engine)
    seeds_ok, seed_problems = (False, []) if not structure_ok else _seed_counts_ok(engine)
    sane = structure_ok and seeds_ok
    if not sane:
        summary["reason"] = "; ".join(struct_problems + seed_problems) or "not-sane"

    must_rebuild = (mode == "force") or (not sane)
    if not must_rebuild:
        summary["action"] = "kept"
        return summary

    if tdb is None or tdenv is None:
        raise ValueError("ensure_fresh_db needs `tdb` and `tdenv` to rebuild via buildCache")

    # Rebuild/populate using the authoritative path.
    from tradedangerous.cache import buildCache

    buildCache(tdb, tdenv)
    summary["action"] = "rebuilt"
    return summary
