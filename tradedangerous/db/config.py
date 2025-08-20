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
        "driver": "mariadbconnector",
        "charset": "utf8mb4",
    },
    "sqlite": {
        "sqlite_filename": "trade.sqlite3",
    },
    "paths": {
        "data_dir": "./data",
        "tmp_dir": "./tmp",
    },
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

def _parse_bool(s: str) -> bool:
    return str(s).strip().lower() in {"1","true","yes","on"}

def _as_int(s: str, default: int | None = None) -> int | None:
    try:
        return int(str(s).strip())
    except (TypeError, ValueError):
        return default

def _merge_into(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _merge_into(dst[k], v)
        else:
            dst[k] = v

def _coerce_types(d: Dict[str, Any]) -> Dict[str, Any]:
    # Coerce known bool/int fields
    eng = d.get("engine", {})
    if "echo" in eng:
        eng["echo"] = _parse_bool(eng["echo"]) if isinstance(eng["echo"], str) else bool(eng["echo"])
    for key in ("pool_size","max_overflow","pool_timeout","pool_recycle","connect_timeout"):
        if key in eng:
            eng[key] = _as_int(eng[key], DEFAULTS["engine"][key])
    if "mariadb" in d:
        md = d["mariadb"]
        if "port" in md:
            md["port"] = _as_int(md["port"], DEFAULTS["mariadb"]["port"])
    return d

def load_config(path: str | Path | None = None) -> Dict[str, Any]:
    """Load configuration as a plain dict with typed values.

    Search order:
      1) explicit *path* if provided
      2) ./db_config.ini (current working directory)
      3) ./db_config.sample.ini (current working directory)
      4) fall back to in-code DEFAULTS

    Notes:
      - Environment overrides for directories are applied in paths.py.
      - This loader has no side effects (does not create directories).
    """
    cfg_path = None
    if path is not None:
        p = Path(path)
        if p.exists():
            cfg_path = p
    else:
        for candidate in ("db_config.ini", "db_config.sample.ini"):
            p = Path.cwd() / candidate
            if p.exists():
                cfg_path = p
                break

    # Start with defaults
    result: Dict[str, Any] = {k: v.copy() if isinstance(v, dict) else v for k, v in DEFAULTS.items()}

    if cfg_path:
        parser = configparser.ConfigParser()
        with cfg_path.open("r", encoding="utf-8") as fh:
            parser.read_file(fh)

        # Transfer sections/keys into dict (case-sensitive keys preserved)
        for section in parser.sections():
            if section not in result:
                result[section] = {}
            for key, val in parser.items(section):
                # Keep as string for now; coerce later
                result[section][key] = val

    return _coerce_types(result)
