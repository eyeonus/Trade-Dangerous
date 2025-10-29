# tradedangerous/db/paths.py
from __future__ import annotations

from pathlib import Path
import os
from typing import Any

try:
    import configparser
except Exception:  # pragma: no cover
    configparser = None  # type: ignore

__all__ = [
    "ensure_dir",
    "resolve_data_dir",
    "resolve_tmp_dir",
    "resolve_db_config_path",
    "get_sqlite_db_path",
]

# --------------------------
# Helpers that tolerate either ConfigParser or dict
# --------------------------

def _is_cfg(obj: Any) -> bool:
    return hasattr(obj, "has_option") and hasattr(obj, "get")

def _get_opt(cfg: Any, section: str, key: str, default: str | None = None) -> str | None:
    """Return option from either a ConfigParser-like object or a nested dict.
    Falls back to [database] overlay for convenience, matching legacy behaviour.
    Safe even if cfg is None.
    """
    if cfg is None:
        return default
    # ConfigParser branch
    if _is_cfg(cfg):
        try:
            if cfg.has_option(section, key):
                return cfg.get(section, key)  # type: ignore[arg-type]
            if cfg.has_option("database", key):
                return cfg.get("database", key)  # type: ignore[arg-type]
        except Exception:
            return default
        return default
    # Mapping/dict branch
    try:
        sec = (cfg or {}).get(section, {}) or {}
        if key in sec and sec[key] not in (None, ""):
            return sec[key]
        db = (cfg or {}).get("database", {}) or {}
        if key in db and db[key] not in (None, ""):
            return db[key]
    except Exception:
        pass
    return default

def _resolve_dir(default_rel: str, env_key: str, cfg_value: str | None) -> Path:
    cand = os.getenv(env_key) or (cfg_value or default_rel)
    p = Path(cand).expanduser()
    return p if p.is_absolute() else (Path.cwd() / p)

# --------------------------
# Public API
# --------------------------

def ensure_dir(pathlike: os.PathLike | str) -> Path:
    """Create directory if missing (idempotent) and return the Path."""
    p = Path(pathlike)
    p.mkdir(parents=True, exist_ok=True)
    return p

def resolve_data_dir(cfg: Any = None) -> Path:
    """Resolve the persistent data directory.
    
    Precedence: TD_DATA env > cfg[paths|database].data_dir > ./data
    Always creates the directory.
    """
    val = _get_opt(cfg, "paths", "data_dir") or _get_opt(cfg, "database", "data_dir")
    p = _resolve_dir("./data", "TD_DATA", val)
    return ensure_dir(p)

def resolve_tmp_dir(cfg: Any = None) -> Path:
    """Resolve the temporary directory.
    
    Precedence: TD_TMP env > cfg[paths|database].tmp_dir > ./tmp
    Always creates the directory.
    """
    val = _get_opt(cfg, "paths", "tmp_dir") or _get_opt(cfg, "database", "tmp_dir")
    p = _resolve_dir("./tmp", "TD_TMP", val)
    return ensure_dir(p)

def get_sqlite_db_path(cfg: Any = None) -> Path:
    """Return full path to the SQLite DB file (does not create the file).
    
    Data dir is resolved via resolve_data_dir(cfg). Filename comes from:
    cfg[sqlite].sqlite_filename or cfg[database].sqlite_filename or legacy default 'TradeDangerous.db'.
    """
    data_dir = resolve_data_dir(cfg)
    filename = (
        _get_opt(cfg, "sqlite", "sqlite_filename")
        or _get_opt(cfg, "database", "sqlite_filename")
        or "TradeDangerous.db"  # legacy default matches shipped tests/fixtures
    )
    return (data_dir / filename).resolve()

def resolve_db_config_path(default_name: str = "db_config.ini") -> Path:
    """Honor TD_DB_CONFIG env var for config file path, else default_name in CWD.
    Does not read or validate contents; just returns a Path.
    """
    cand = os.getenv("TD_DB_CONFIG") or default_name
    p = Path(cand).expanduser()
    return p if p.is_absolute() else (Path.cwd() / p)