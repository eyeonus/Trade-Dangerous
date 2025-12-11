# tradedangerous/db/engine.py
from __future__ import annotations
import os, time
from pathlib import Path
from typing import Any, Dict, Mapping
import configparser

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.orm import sessionmaker, Session  # type: ignore
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import OperationalError

from .paths import resolve_data_dir, resolve_tmp_dir, resolve_db_config_path

# ---------- config normalization & helpers ----------

def _ensure_default_config_file(target_path: Path | None) -> Path | None:
    """
    If *target_path* is provided and no file exists there, write a minimal db_config.ini
    built from in-code DEFAULTS. Returns the path if created, else None.
    """
    if not target_path:
        return None
    if target_path.exists():
        return target_path
    # Build from DEFAULTS
    from .config import DEFAULTS  # typed defaults live here
    target_path.parent.mkdir(parents=True, exist_ok=True)
    cp = configparser.ConfigParser()
    for section, mapping in DEFAULTS.items():
        cp[section] = {}
        if isinstance(mapping, Mapping):
            for k, v in mapping.items():
                cp[section][k] = str(v)
    with target_path.open("w", encoding="utf-8") as fh:
        cp.write(fh)
    return target_path


def _cfg_to_dict(cfg: configparser.ConfigParser | Mapping[str, Any] | str | os.PathLike) -> Dict[str, Dict[str, Any]]:
    """
    Normalise configuration input into a dict-of-sections.
    
    Accepted inputs:
      * dict-like mapping → returned as {section: {key: value}}
      * ConfigParser       → converted to nested dict (sections overlay DEFAULT section)
      * str/Path           → if file exists, read it; if missing, fall back to load_config()
    
    NOTE:
    - We do NOT raise on a missing path; we delegate to load_config() to honour the
      documented resolution order (ENV → CWD → DEFAULTS).
    """
    if isinstance(cfg, (str, os.PathLike)):
        p = Path(cfg)
        if p.exists():
            cp = configparser.ConfigParser()
            with p.open("r", encoding="utf-8") as fh:
                cp.read_file(fh)
            return _cfg_to_dict(cp)
        # Missing provided path → use canonical loader with fallbacks
        from .config import load_config
        return load_config(None)
    
    if isinstance(cfg, configparser.ConfigParser):
        out: Dict[str, Dict[str, Any]] = {}
        defaults = dict(cfg.defaults())
        for sec in cfg.sections():
            d = dict(defaults)
            d.update({k: v for k, v in cfg.items(sec)})
            out[sec] = d
        for sec in ("database", "engine", "sqlite", "mariadb", "paths"):
            out.setdefault(sec, dict(defaults))
        return out
    
    # Already a dict-like mapping of sections
    return {k: dict(v) if isinstance(v, Mapping) else dict() for k, v in cfg.items()}  # type: ignore[arg-type]


def _get(cfg: Dict[str, Any], section: str, key: str, default=None):
    if section in cfg and key in cfg[section]:
        return cfg[section][key]
    if "database" in cfg and key in cfg["database"]:
        return cfg["database"][key]
    return default

def _get_int(cfg: Dict[str, Any], section: str, key: str, default=None):
    try:
        return int(_get(cfg, section, key, default))
    except (TypeError, ValueError):
        return default

def _get_bool(cfg: Dict[str, Any], section: str, key: str, default=None):
    v = _get(cfg, section, key, default)
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "on"}
    return default

# ---------- URL builders ----------

def _redact(url: str) -> str:
    if "://" not in url:
        return url
    head, rest = url.split("://", 1)
    if "@" in rest and ":" in rest.split("@", 1)[0]:
        user_pass, host = rest.split("@", 1)
        user = user_pass.split(":", 1)[0]
        return f"{head}://{user}:***@{host}"
    return f"{head}://{rest}"

def _make_mariadb_url(cfg: Dict[str, Any]) -> URL:
    driver = str(_get(cfg, "mariadb", "driver", "mariadbconnector")).strip().lower()
    drivername = "mariadb+" + driver if driver == "mariadbconnector" else "mysql+" + driver
    return URL.create(
        drivername=drivername,
        username=str(_get(cfg, "mariadb", "user", "")),
        password=str(_get(cfg, "mariadb", "password", "")),
        host=str(_get(cfg, "mariadb", "host", "127.0.0.1")),
        port=int(_get(cfg, "mariadb", "port", 3306)),
        database=str(_get(cfg, "mariadb", "name", "tradedangerous")),
        query={"charset": str(_get(cfg, "mariadb", "charset", "utf8mb4"))},
    )

def _make_sqlite_url(cfg: Dict[str, Any]) -> str:
    data_dir = resolve_data_dir(cfg)
    # Honour legacy filename
    filename = str(_get(cfg, "sqlite", "sqlite_filename", "TradeDangerous.db"))
    db_path = (data_dir / filename).resolve()
    return f"sqlite+pysqlite:///{db_path.as_posix()}"

# ---------- Engine construction ----------

def make_engine_from_config(cfg_or_path: configparser.ConfigParser | Mapping[str, Any] | str | os.PathLike | None = None) -> Engine:
    """
    Build a SQLAlchemy Engine for either MariaDB or SQLite.
    
    Accepts: ConfigParser, dict-like {section:{k:v}}, path to INI file, or None.
    First-run behaviour:
      - If a path is provided but missing, or if no path is provided and no config is found,
        a default db_config.ini is CREATED in the resolved default location (CWD unless TD_DB_CONFIG
        points elsewhere), then loaded.
    """
    ini_target: Path | None = None
    
    # If caller gave a specific path, prefer to materialise a default file there.
    if isinstance(cfg_or_path, (str, os.PathLike)):
        ini_target = Path(cfg_or_path)
        _ensure_default_config_file(ini_target)
    else:
        # No specific path: create (if missing) at the standard location
        # (CWD/db_config.ini by default, or the file pointed to by TD_DB_CONFIG).
        ini_target = resolve_db_config_path("db_config.ini")
        _ensure_default_config_file(ini_target)
    
    cfg = _cfg_to_dict(cfg_or_path if cfg_or_path is not None else str(ini_target))
    
    # Ensure dirs exist (used by various parts of the app)
    _ = resolve_data_dir(cfg)
    _ = resolve_tmp_dir(cfg)
    
    backend = str(_get(cfg, "database", "backend", "sqlite")).strip().lower()
    echo = bool(_get_bool(cfg, "engine", "echo", False))
    isolation = _get(cfg, "engine", "isolation_level", None)
    
    if backend == "mariadb":
        url = _make_mariadb_url(cfg)
        connect_timeout = _get_int(cfg, "engine", "connect_timeout", 10) or 10
        pool_size    = _get_int(cfg, "engine", "pool_size", 10) or 10
        max_overflow = _get_int(cfg, "engine", "max_overflow", 20) or 20
        pool_timeout = _get_int(cfg, "engine", "pool_timeout", 30) or 30
        pool_recycle = _get_int(cfg, "engine", "pool_recycle", 1800) or 1800
        engine = create_engine(
            url,
            echo=echo,
            pool_pre_ping=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            isolation_level=isolation or "READ COMMITTED",
            connect_args={"connect_timeout": connect_timeout},
        )
    elif backend == "sqlite":
        url = _make_sqlite_url(cfg)
        engine = create_engine(
            url,
            echo=echo,
            poolclass=NullPool,
            connect_args={"check_same_thread": False},
        )
        
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA synchronous=OFF")
            cur.execute("PRAGMA temp_store=MEMORY")
            cur.execute("PRAGMA auto_vacuum=INCREMENTAL")
            cur.close()
    else:
        raise ValueError(f"Unsupported backend: {backend}")
    
    try:
        engine._td_redacted_url = _redact(str(url))  # type: ignore[attr-defined]
    except Exception:
        pass
    return engine
# ---------- Session factory ----------

def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=True)

# ---------- Health helpers ----------

def healthcheck(engine: Engine, retries: int = 0) -> bool:
    attempt = 0
    delay = 0.25
    while True:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except OperationalError:
            attempt += 1
            if attempt > retries:
                return False
            time.sleep(delay)
            delay *= 2

def read_sqlite_pragmas(engine: Engine) -> Dict[str, Any]:
    """
    Return active PRAGMA values (SQLite only). Safe no-op for non-sqlite engines.
    """
    out: Dict[str, Any] = {}
    with engine.connect() as conn:
        if conn.dialect.name != "sqlite":
            return out
        def one(q: str) -> Any:
            return conn.execute(text(q)).scalar()
        out["foreign_keys"] = one("PRAGMA foreign_keys")
        out["synchronous"]  = one("PRAGMA synchronous")
        out["temp_store"]   = one("PRAGMA temp_store")
        out["auto_vacuum"]  = one("PRAGMA auto_vacuum")
    return out
