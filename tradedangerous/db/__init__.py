"""TradeDangerous SQLAlchemy bootstrap package (Stage 3A, Part 1).

Side-effect free on import. Provides a minimal, cross-platform API
for config loading, path resolution, and engine/session bootstrap.

Usage:
    from tradedangerous.db import (
        load_config, resolve_data_dir, resolve_tmp_dir, ensure_dir, resolve_db_config_path,
        make_engine_from_config, get_session_factory, healthcheck,
    )
"""
from .config import load_config
from .paths import resolve_data_dir, resolve_tmp_dir, ensure_dir, resolve_db_config_path
from .engine import make_engine_from_config, get_session_factory, healthcheck
from .lifecycle import ensure_fresh_db

__all__ = [
    "load_config",
    "resolve_data_dir",
    "resolve_tmp_dir",
    "ensure_dir",
    "resolve_db_config_path",
    "make_engine_from_config",
    "get_session_factory",
    "healthcheck",
    "ensure_fresh_db",
]
