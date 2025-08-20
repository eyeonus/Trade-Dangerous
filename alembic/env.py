# alembic/env.py — Trade:Dangerous
from __future__ import annotations

import os
import sys
import configparser
from pathlib import Path
from alembic import context

# Ensure project imports resolve when running from repo root
sys.path.insert(0, str(Path.cwd()))

# Project models & engine builder
from tradedangerous.db.orm_models import Base
from tradedangerous.db.engine import make_engine_from_config  # your engine.py

config = context.config
target_metadata = Base.metadata

# Allow override via env var; default to repo-local file
CFG_PATH = Path(os.getenv("TD_DB_CONFIG") or "db_config.ini")

def _load_cfg_dict(path: Path) -> dict:
    """Read INI into dict-of-dicts expected by make_engine_from_config(...)."""
    cp = configparser.ConfigParser()
    if not cp.read(path):
        raise FileNotFoundError(f"Database config not found: {path}")
    return {section: dict(cp.items(section)) for section in cp.sections()}

def get_engine():
    """Build an Engine using your existing engine.py helper."""
    cfg = _load_cfg_dict(CFG_PATH)
    try:
        # Preferred: function accepts a dict
        return make_engine_from_config(cfg)
    except TypeError:
        # Fallback: some variants accept a filepath
        return make_engine_from_config(str(CFG_PATH))

def run_migrations_offline():
    """'Offline' mode: emit SQL without connecting."""
    # If a URL is provided in alembic.ini, use it; otherwise render from Engine
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        engine = get_engine()
        # Hide password if this gets logged
        url = engine.url.render_as_string(hide_password=True)

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,  # keeps SQLite alters workable during dev
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """'Online' mode: connect and apply migrations."""
    engine = get_engine()
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=True,  # harmless on MariaDB, required for SQLite alters
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
