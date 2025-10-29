from __future__ import annotations
import configparser
from pathlib import Path
from typing import Any, Dict

DEFAULTS: Dict[str, Dict[str, Any]] = {
    "database": {"backend": "sqlite"},
    "mariadb": {
        "host": "127.0.0.1",
        "port": 3306,
        "user": "",
        "password": "",
        "name": "tradedangerous",
        "driver": "mariadbconnector",  # or 'pymysql'
        "charset": "utf8mb4",
    },
    "sqlite": {"sqlite_filename": "TradeDangerous.db"},
    "paths": {"data_dir": "./data", "tmp_dir": "./tmp"},
    "engine": {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "isolation_level": "READ COMMITTED",
        "echo": False,
        "connect_timeout": 10,
    },
}
# --- Runtime default path correction ----------------------------------------
# Convert relative defaults ("./data", "./tmp") into absolute paths under the
# current working directory. This prevents first-run installs from resolving
# relative to the package install directory or venv when no db_config.ini exists.
try:
    _cwd = Path.cwd()
    DEFAULTS["paths"]["data_dir"] = str((_cwd / "data").resolve())
    DEFAULTS["paths"]["tmp_dir"]  = str((_cwd / "tmp").resolve())
except Exception:
    # Best effort; fall back to shipped defaults if CWD is inaccessible
    pass
# ---------------------------------------------------------------------------

# Hardened parser: allow inline comments and disable interpolation
CFG_KW = dict(inline_comment_prefixes=(";", "#"), interpolation=None)

def _parse_bool(s: str) -> bool:
    return str(s).strip().lower() in {"1", "true", "yes", "on"}

def _as_int(s: str, default: int | None = None) -> int | None:
    try:
        return int(str(s).strip())
    except (TypeError, ValueError):
        return default

def _coerce_types(d: Dict[str, Any]) -> Dict[str, Any]:
    eng = d.get("engine", {})
    if "echo" in eng:
        eng["echo"] = _parse_bool(eng["echo"]) if isinstance(eng["echo"], str) else bool(eng["echo"])
    for k in ("pool_size", "max_overflow", "pool_timeout", "pool_recycle", "connect_timeout"):
        if k in eng:
            eng[k] = _as_int(eng[k], DEFAULTS["engine"][k])
    if "mariadb" in d and "port" in d["mariadb"]:
        d["mariadb"]["port"] = _as_int(d["mariadb"]["port"], DEFAULTS["mariadb"]["port"])
    return d

def load_config(path: str | Path | None = None) -> Dict[str, Any]:
    """Load configuration as a dict with typed values.
    Search order:
      1) explicit *path* if provided
      2) TD_DB_CONFIG env (if file exists)
      3) ./db_config.ini (cwd)
      4) in-code DEFAULTS
    """
    cfg_path: Path | None = None
    if path is not None:
        p = Path(path)
        if p.exists():
            cfg_path = p
    else:
        # Prefer environment variable if it points to an existing file
        try:
            from .paths import resolve_db_config_path
            env_candidate = resolve_db_config_path()
            if env_candidate.exists():
                cfg_path = env_candidate
        except Exception:
            # If anything goes wrong resolving the env, fall back to defaults below
            pass
        
        # Fall back to local file in CWD
        if cfg_path is None:
            p = Path.cwd() / "db_config.ini"
            if p.exists():
                cfg_path = p
    
    # start with defaults
    result: Dict[str, Any] = {k: (v.copy() if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
    
    if cfg_path:
        parser = configparser.ConfigParser(**CFG_KW)
        with cfg_path.open("r", encoding="utf-8") as fh:
            parser.read_file(fh)
        for section in parser.sections():
            result.setdefault(section, {})
            for key, val in parser.items(section):
                result[section][key] = val
    
    return _coerce_types(result)
