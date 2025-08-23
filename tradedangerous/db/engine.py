# tradedangerous/db/engine.py
from __future__ import annotations
import os, time
from pathlib import Path
from typing import Any, Dict, Mapping
import configparser

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import OperationalError

from .paths import resolve_data_dir, resolve_tmp_dir

# ---------- config normalization ----------

def _cfg_to_dict(cfg: configparser.ConfigParser | Mapping[str, Any] | str | os.PathLike) -> Dict[str, Dict[str, Any]]:
    if isinstance(cfg, (str, os.PathLike)):
        p = Path(cfg)
        cp = configparser.ConfigParser()
        with p.open("r", encoding="utf-8") as fh:
            cp.read_file(fh)
        return _cfg_to_dict(cp)

    if isinstance(cfg, configparser.ConfigParser):
        out: Dict[str, Dict[str, Any]] = {}
        # DEFAULT items first
        defaults = dict(cfg.defaults())
        # each section overlays defaults
        for sec in cfg.sections():
            d = dict(defaults)
            d.update({k: v for k, v in cfg.items(sec)})
            out[sec] = d
        # common sections that callers expect to exist
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

def make_engine_from_config(cfg_or_path: configparser.ConfigParser | Mapping[str, Any] | str | os.PathLike) -> Engine:
    """
    Build a SQLAlchemy Engine for either MariaDB or SQLite.
    Accepts: ConfigParser, dict-like {section:{k:v}}, or path to INI file.
    """
    cfg = _cfg_to_dict(cfg_or_path)

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

        # Apply PRAGMAs on every new connection
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

def get_session_factory(engine: Engine):
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
