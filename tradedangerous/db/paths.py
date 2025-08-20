from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def _resolve_dir(default_rel: str, env_key: str, cfg_value: str | None) -> Path:
    candidate = os.getenv(env_key) or (cfg_value or default_rel)
    p = Path(candidate).expanduser()
    return p if p.is_absolute() else (Path.cwd() / p)

def resolve_data_dir(cfg: Dict[str, Any]) -> Path:
    paths = cfg.get("paths", {})
    p = _resolve_dir("./data", "TD_DATA", paths.get("data_dir"))
    return ensure_dir(p)

def resolve_tmp_dir(cfg: Dict[str, Any]) -> Path:
    paths = cfg.get("paths", {})
    p = _resolve_dir("./tmp", "TD_TMP", paths.get("tmp_dir"))
    return ensure_dir(p)
