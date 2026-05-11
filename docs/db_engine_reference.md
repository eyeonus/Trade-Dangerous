# TradeDangerous Database Engine — Definitive Reference

This document consolidates all database-related modules, configuration, and models
for the TradeDangerous project. It is the authoritative reference for DB engine usage,
paths, config, lifecycle, ORM schema, and adapter surface.

---

# Database Engine (`tradedangerous/db/engine.py`)

## Purpose
Central module for creating and managing the SQLAlchemy database engine in TradeDangerous.  
Supports **MariaDB** and **SQLite** backends with unified configuration and helper utilities.

---

## Configuration
- **Accepted formats:**  
  - Path to INI file  
  - `ConfigParser` object  
  - Dict-like mapping `{section: {key: value}}`

- **Sections recognised:** `database`, `engine`, `sqlite`, `mariadb`, `paths`  
- **Environment overrides:** handled by `resolve_data_dir`, `resolve_tmp_dir` (imported from `.paths`).

---

## Key Functions

### Config helpers
- `_cfg_to_dict(cfg)` → normalises INI or dict into `{section: {key: value}}`.  
- `_get`, `_get_int`, `_get_bool` → retrieve values with fallbacks.

### URL Builders
- `_make_mariadb_url(cfg)` → builds `URL` for MariaDB/MySQL.  
- `_make_sqlite_url(cfg)` → builds SQLite DSN (`sqlite+pysqlite:///<data_dir>/<filename>`).  
- `_redact(url)` → masks password for safe logging.

### Engine Factory
- `make_engine_from_config(cfg_or_path) -> Engine`  
  - **MariaDB:** pooled engine (`pool_pre_ping`, configurable pool size/recycle, `READ COMMITTED` isolation).  
  - **SQLite:** `NullPool`, `check_same_thread=False`.  
    - On connect: applies PRAGMAs (`foreign_keys=ON`, `synchronous=OFF`, `temp_store=MEMORY`, `auto_vacuum=INCREMENTAL`).  
  - Adds `_td_redacted_url` attribute for safe URL logging.

### Sessions
- `get_session_factory(engine)` → returns `sessionmaker(bind=engine, expire_on_commit=False, autoflush=True)`.

### Health / Diagnostics
- `healthcheck(engine, retries=0) -> bool`  
  Executes `SELECT 1` with optional retries on `OperationalError`.  
- `read_sqlite_pragmas(engine) -> Dict[str, Any]`  
  Returns current SQLite pragma settings; no-op for non-SQLite engines.

---

## Usage Example
```python
from tradedangerous.db.engine import make_engine_from_config, get_session_factory, healthcheck

engine = make_engine_from_config("db_config.ini")
assert healthcheck(engine, retries=2)

Session = get_session_factory(engine)
with Session.begin() as s:
    # ORM or Core DB work here
    ...
```

---


---

# Database Package Init (`tradedangerous/db/__init__.py`)

## Purpose
This is the bootstrap module for the TradeDangerous SQLAlchemy integration.  
It is **side-effect free** on import and exposes a minimal, cross-platform API for:

- Configuration loading  
- Path resolution  
- Engine/session bootstrap  
- Database lifecycle management

---

## Exposed API

The following functions and helpers are imported and re-exported:

- `load_config` — from `.config`  
- `resolve_data_dir` — from `.paths`  
- `resolve_tmp_dir` — from `.paths`  
- `ensure_dir` — from `.paths`  
- `resolve_db_config_path` — from `.paths`  
- `make_engine_from_config` — from `.engine`  
- `get_session_factory` — from `.engine`  
- `ensure_fresh_db` — from `.lifecycle`  
- `Category`, `Item`, `Station`, `System` — from `.orm_models`  

They are made available via the `__all__` list for clean imports.

---

## Usage

```python
from tradedangerous.db import (
    load_config, resolve_data_dir, resolve_tmp_dir, ensure_dir, resolve_db_config_path,
    make_engine_from_config, get_session_factory, ensure_fresh_db,
    Category, Item, Station, System,
)
```

Importing this module does not perform any I/O or side effects — it only re-exports the supported API surface.


---

# Database Config (`tradedangerous/db/config.py`)

## Purpose
Provides configuration loading for the TradeDangerous database layer.  
Defines defaults, applies type coercion, and supports multiple search paths.

---

## Defaults
The module includes a `DEFAULTS` dictionary with baseline values for all sections:

- **database** → `{ backend: "sqlite" }`  
- **mariadb** → host, port=3306, user, password, name, driver (`mariadbconnector`), charset (`utf8mb4`)  
- **sqlite** → `sqlite_filename = trade.sqlite3`  
- **paths** → `data_dir=./data`, `tmp_dir=./tmp`  
- **engine** → pool sizing, recycle, timeouts, isolation level, echo flag, connect timeout  

---

## Helpers

### `_parse_bool(s: str) -> bool`
Recognises `1/true/yes/on` (case-insensitive).

### `_as_int(s: str, default=None) -> int | None`
Safely cast string to int, fallback to default.

### `_coerce_types(d: Dict[str, Any]) -> Dict[str, Any]`
Normalises types inside the loaded config:
- Converts `engine.echo` to `bool`  
- Ensures engine numeric fields are ints  
- Ensures `mariadb.port` is an int

---

## Main API

### `load_config(path: str | Path | None = None) -> Dict[str, Any]`
Loads configuration into a fully-typed dictionary.  

**Search order:**  
1. Explicit `path` argument (if provided and exists).  
2. `TD_DB_CONFIG` environment variable (via `resolve_db_config_path`) if file exists.  
3. `./db_config.ini` in current working directory (if present).  
4. Fallback to in-code `DEFAULTS`.  

**Parsing:**  
- Uses `configparser.ConfigParser` with hardened settings (`inline_comment_prefixes=(";", "#")`, no interpolation).  
- Merges file sections into defaults.  
- Returns coerced dict.

---

## Usage Example

```python
from tradedangerous.db.config import load_config

cfg = load_config()
print(cfg["database"]["backend"])  # "sqlite" (default) or overridden value
```

---


---

# Database Paths (`tradedangerous/db/paths.py`)

## Purpose
Provides cross-platform path resolution helpers for TradeDangerous database use.  
Supports **environment overrides**, **ConfigParser/dict configs**, and ensures directories exist.

---

## Public API

### `ensure_dir(pathlike) -> Path`
- Creates directory if missing (idempotent).  
- Returns `Path`.

### `resolve_data_dir(cfg=None) -> Path`
Resolve the **persistent data directory**.  
**Precedence:**  
1. `TD_DATA` environment variable  
2. `cfg['paths'].data_dir` or `cfg['database'].data_dir`  
3. Default: `./data`  

Ensures directory exists.

### `resolve_tmp_dir(cfg=None) -> Path`
Resolve the **temporary directory**.  
**Precedence:**  
1. `TD_TMP` environment variable  
2. `cfg['paths'].tmp_dir` or `cfg['database'].tmp_dir`  
3. Default: `./tmp`  

Ensures directory exists.

### `get_sqlite_db_path(cfg=None) -> Path`
Return the absolute path to the SQLite database file.  
- Directory resolved via `resolve_data_dir`.  
- Filename from `cfg['sqlite'].sqlite_filename`, `cfg['database'].sqlite_filename`, or legacy `"TradeDangerous.db"`.  
- Does **not** create the file.

### `resolve_db_config_path(default_name="db_config.ini") -> Path`
Locate the database configuration file.  
- Uses `TD_DB_CONFIG` environment variable if set.  
- Otherwise returns `<cwd>/<default_name>`.  
- Returns a `Path` only, does not validate or read contents.

---

## Internal Helpers

- `_is_cfg(obj)` → True if object looks like a `ConfigParser`.  
- `_get_opt(cfg, section, key, default)` → Unified getter across `ConfigParser` and dict configs.  
- `_resolve_dir(default_rel, env_key, cfg_value)` → Build absolute path from environment, config, or default.

---

## Usage Example

```python
from tradedangerous.db.paths import resolve_data_dir, resolve_tmp_dir, get_sqlite_db_path

data_dir = resolve_data_dir()
tmp_dir = resolve_tmp_dir()
sqlite_path = get_sqlite_db_path()

print(data_dir, tmp_dir, sqlite_path)
```

---


---

# Database Lifecycle (`tradedangerous/db/lifecycle.py`)

## Purpose
Manages **creation, reset, and lifecycle operations** for the TradeDangerous database.  
Supports both **SQLite** (legacy schema) and **MariaDB** (via ORM metadata).

---

## Utilities

### `is_sqlite(engine: Engine) -> bool`
Returns `True` if the engine dialect is SQLite.

### `_user_tables(engine: Engine) -> Iterable[str]`
Return list of user table names (filters out `sqlite_*` internals for SQLite).

### `is_empty(engine: Engine) -> bool`
True when no user tables exist.

### `rotate_sqlite_db(data_dir: Path, filename="TradeDangerous.db", old_name="TradeDangerous.old") -> Path`
Renames SQLite DB file to `.old` (idempotent).  
If `.old` already exists, it is replaced.  
Falls back to copy+unlink if rename fails.

---

## Legacy SQL Handling

### `_read_legacy_sql() -> str`
Load the legacy SQLite schema SQL (`TradeDangerous.sql`) from templates.  
Search order: package templates → cwd variants.

### `_execute_sql_script(engine, script)`
Executes a multi-statement SQL script safely, stripping comments and empty lines.

### `_create_sqlite_from_legacy(engine)`
Recreate SQLite schema from legacy SQL file.

---

## Public Reset Functions

### `reset_sqlite(engine: Engine, metadata: MetaData | None = None)`
- Drops all user tables and views.  
- Recreates schema from legacy SQLite SQL.

### `reset_mariadb(engine: Engine, metadata: MetaData)`
- Drops all tables via ORM metadata.  
- Recreates using `metadata.create_all()`.  
- Assumes metadata is authoritative.

---

## Orchestration

### `ensure_fresh_db(backend: str, engine: Engine, data_dir: Path, metadata: MetaData | None, mode="auto") -> dict`
Ensures DB exists and is fresh according to backend policy.

**SQLite:**  
- If file missing → create from legacy SQL.  
- If empty or `mode="force"` → rotate + recreate from legacy SQL.  
- Else keep existing DB.

**MariaDB:**  
- If empty → `metadata.create_all()`.  
- If `mode="force"` → drop & recreate via metadata.  
- Else keep existing schema.

**Returns:** dict summary `{backend, mode, action, path?}`

---

## Usage Example

```python
from tradedangerous.db.lifecycle import ensure_fresh_db, reset_sqlite
from tradedangerous.db.engine import make_engine_from_config

engine = make_engine_from_config("db_config.ini")
summary = ensure_fresh_db("sqlite", engine, Path("./data"), None, mode="force")
print(summary)
```

---


---

# ORM Models (`tradedangerous/db/orm_models.py`)

## Purpose
Defines the **SQLAlchemy ORM models** for the TradeDangerous database schema.  
Covers systems, stations, items, prices, ships, and upgrades.

Includes dialect-aware timestamp helpers (`now6`, `DateTime6`) for consistent `DATETIME(6)` handling.

---

## Utilities

### `now6`
- SQL expression for `CURRENT_TIMESTAMP(6)` on MySQL/MariaDB.  
- Fallback to `CURRENT_TIMESTAMP` on other dialects.

### `DateTime6`
- Custom type: `DATETIME(6)` on MySQL/MariaDB, plain `DateTime` elsewhere.  
- Used across all `modified` columns.

---

## Naming Convention
Applies deterministic naming to constraints and indexes (ix, uq, ck, fk, pk).

---

## Enums
- **TriState**: `ENUM('Y','N','?')`  
- **PadSize**: `ENUM('S','M','L','?')`

---

## Exported API (`__all__`)
- `Base` + all models: `System`, `Station`, `Category`, `Item`, `StationItem`, `Ship`, `ShipVendor`, `Upgrade`, `UpgradeVendor`, `FDevShipyard`, `FDevOutfitting`

---

## Usage Example

```python
from tradedangerous.db.orm_models import Base, System, Station
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)

with Session(engine) as s:
    s.add(System(system_id=1, name="Sol", pos_x=0, pos_y=0, pos_z=0))
    s.commit()
```

---

# Sample Database Config (`db_config.sample.ini`)

## Purpose
Provides a reference configuration file for the TradeDangerous database layer.  
Supports both **MariaDB** and **SQLite** backends.

---

## Sections

### `[database]`
- `backend` → select database backend: `mariadb` or `sqlite`

### `[mariadb]`
Connection settings for MariaDB backend:
- `host` (default: 127.0.0.1)  
- `port` (default: 3306)  
- `user`  
- `password`  
- `name` (database name, default: tradedangerous)  
- `driver` (optional: `mariadbconnector` [default] or `pymysql`)  
- `charset` (default: utf8mb4)

### `[sqlite]`
SQLite backend settings:
- `sqlite_filename` → database filename (joined under `[paths].data_dir`)  
  Default: `trade.sqlite3`

### `[paths]`
Used by both backends:
- `data_dir` → persistent storage directory (default: ./data)  
- `tmp_dir` → temporary directory (default: ./tmp)

### `[engine]`
SQLAlchemy engine and pool settings (mainly for MariaDB):
- `pool_size` → default 10  
- `max_overflow` → default 20  
- `pool_timeout` → default 30  
- `pool_recycle` → default 1800  
- `isolation_level` → default `READ COMMITTED`  
- `echo` → SQL echo (true/false)  
- `connect_timeout` → default 10  

---

## Example
```ini
[database]
backend = mariadb

[mariadb]
host = 127.0.0.1
port = 3306
user = traded
password = secret
name = tradedangerous
driver = mariadbconnector
charset = utf8mb4

[paths]
data_dir = ./data
tmp_dir  = ./tmp
```

---