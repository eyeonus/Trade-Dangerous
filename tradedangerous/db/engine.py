from __future__ import annotations
import time
from typing import Any, Dict

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import OperationalError

from .paths import resolve_data_dir, resolve_tmp_dir

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
    filename = str(_get(cfg, "sqlite", "sqlite_filename", "trade.sqlite3"))
    db_path = (data_dir / filename).resolve()
    return f"sqlite+pysqlite:///{db_path.as_posix()}"

def make_engine_from_config(cfg: Dict[str, Any]) -> Engine:
    backend = str(_get(cfg, "database", "backend", "sqlite")).strip().lower()
    echo = bool(_get_bool(cfg, "engine", "echo", False))
    isolation = _get(cfg, "engine", "isolation_level", None)

    # Ensure dirs exist (plugins rely on them even under MariaDB)
    _ = resolve_data_dir(cfg)
    _ = resolve_tmp_dir(cfg)

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
    else:
        raise ValueError(f"Unsupported backend: {backend}")

    try:
        engine._td_redacted_url = _redact(str(url))
    except Exception:
        pass
    return engine

def get_session_factory(engine: Engine):
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=True)

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
