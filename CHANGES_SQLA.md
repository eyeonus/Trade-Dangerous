# TradeDangerous Refactor — `tradedb.py` 

This summarises the sqlite3 → SQLAlchemy migration applied to `tradedb.py`.  
Wrappers remain in place for API compatibility; a potential Pass 2 could streamline or remove them.

---

## sqlite3 Removal
- `import sqlite3` removed.
- All direct `sqlite3.connect` usage eliminated.
- PRAGMAs (`foreign_keys`, `synchronous`, `temp_store`, `auto_vacuum`) now applied automatically via `make_engine_from_config`.
- `getDB`, `query`, and `queryColumn` refactored to use SQLAlchemy `Engine`/`Session`.

---

## Refactored Loaders
- **Added**: `_loadAdded` → ORM query on `SA_Added`.
- **Systems**: `_loadSystems` → ORM query on `SA_System`, legacy `System` wrappers preserved.
- **Stations**: `_loadStations` → ORM query on `SA_Station` + trading stats from `SA_StationItem`.
- **Ships**: `_loadShips` → ORM query on `SA_Ship`.
- **Categories**: `_loadCategories` → ORM query on `SA_Category`.
- **Items**: `_loadItems` → ORM query on `SA_Item`.
- **Rare Items**: `_loadRareItems` → ORM query on `SA_RareItem`.

---

## CRUD Operations
- **Systems**
  - `addLocalSystem`, `updateLocalSystem`, `removeLocalSystem` → rewritten to SQLAlchemy ORM.
- **Stations**
  - `addLocalStation`, `updateLocalStation`, `removeLocalStation` → rewritten to SQLAlchemy ORM.

---

## Aggregate Queries
- `getAverageSelling` → SQLAlchemy aggregate across `SA_Item` + `SA_StationItem`.
- `getAverageBuying` → SQLAlchemy aggregate across `SA_Item` + `SA_StationItem`.

---

## Unchanged (No DB Access)
- Lookup helpers: `lookupSystem`, `lookupStation`, `lookupPlace`, `lookupCategory`, etc.
- Pathfinding & stellar grid: `__buildStellarGrid`, `genStellarGrid`, `genSystemsInRange`, `getRoute`.
- These continue to consume wrapper caches, no DB changes needed.

---

## Wrapper Strategy
- All caches (`systemByID`, `stationByID`, `itemByID`, etc.) continue to store **legacy wrapper objects**.
- ORM models imported with `SA_*` aliases to avoid naming conflicts.
- **Pass 2 (optional future)**: wrappers can be reduced or removed entirely once migration stabilises.

---

## Status
`tradedb.py` is now free of sqlite3.  
All database interactions flow through SQLAlchemy’s engine and ORM.  
Wrappers guarantee API compatibility with existing code.

---

## tradecalc.py — SQLAlchemy migration & preload contract restoration

### Summary
- **Preload rewritten to SQLAlchemy Core (tuples only).**
  The front-load no longer iterates ORM entities or opens a `Session`. It executes a Core SQL text against the engine and streams rows directly, selecting **only the 9 legacy columns** required to build the in-memory maps. This avoids ORM identity-map growth and restores the legacy memory profile.

- **Station reachability gating removed from preload.**
  The candidate-station `IN (…)` filter added during refactor was deleted. Preload now applies **only** age and optional item filters, matching legacy; reachability and other suitability checks run later.

- **Legacy tuple shapes and keep rules preserved.**
  - `stationsSelling[station_id]` → `(item_id, supply_price, supply_units, supply_level, ageS)` when `supply_price > 0` and `supply_units > 0` and (if configured) `supply_units >= tdenv.supply`.
  - `stationsBuying[station_id]` → `(item_id, demand_price, demand_units, demand_level, ageS)` when `demand_price > 0` and (if configured) `demand_units >= tdenv.demand`.
  Field order is unchanged.

- **Age semantics match legacy.**
  `ageS` is computed in Python from `parse_ts(modified).timestamp()` (seconds since epoch). A dialect cutoff is applied **only** to reduce scan size when `tdenv.maxAge` is set (`strftime('%s', modified)` on SQLite; `UNIX_TIMESTAMP(modified)` on MySQL/MariaDB).

### Removed / avoided
- No ORM `Session` in the preload path (no identity-map participation).
- No `.all()` materialisation; iterate the DB `Result` directly.
- No eager relationship loads or joins to `Station`/`System` during preload.
- No station/system gating (reachability, pad size, planetary, etc.) in preload; those remain in later suitability logic.

### Unchanged
- Route building, scoring, and cargo-fit algorithms (`simpleFit`, `fastFit`, `bruteForceFit`).
- Public methods used by `run_cmd.py` (`getTrades`, `getBestHops`), and text/summary renderers.
- Error signalling (`BadTimestampError`, `NoHopsError`).

### Operational notes
- **Logging:** preload emits a DEBUG line: *“Preload used Engine/Core (no ORM identity map)”* plus kept row counts for buys/sells.
- **Cutoff helper:** SQL-side age cutoff uses a tiny dialect switch; canonical `ageS` is always computed in Python via `parse_ts`.

### Rationale
Legacy front-load pulled station-item rows with **only age/item filtering**, then built the two maps; suitability (including reachability) ran afterwards. The refactor regressed by gating on candidate stations before preload, which could empty the maps and trigger origin-empty failures. This change restores the contract and eliminates ORM-map memory bloat by using Core tuples.

### Status
`tradecalc.py` now honours the legacy preload contract while using SQLAlchemy safely: **Core for preload, ORM for nothing in that path**. Peak RSS is dominated by the two Python dicts (as in legacy); routing remains correct.

---

# TradeDangerous Refactor — `prices.py`

This summarises the sqlite3 → SQLAlchemy migration applied to `prices.py`.  
Wrappers and output formats remain unchanged; only the DB access layer has been refactored.

---

## sqlite3 Removal
- `import sqlite3` removed.
- All direct `sqlite3.connect`, `cursor.execute`, and raw SQL string construction eliminated.
- No PRAGMAs — handled centrally in `engine.py`.

---

## Refactored Function

### `dumpPrices`
- **Signature**:  
  - Old: `dumpPrices(dbPath, elementMask, stationID=None, file=None, defaultZero=False, debug=0)`  
  - New: `dumpPrices(session: Session, elementMask, stationID=None, file=None, defaultZero=False, debug=0)`
  - Accepts a SQLAlchemy `Session` instead of a sqlite DB path.

- **System/Station/Category/Item lookups**:  
  - Old: multiple `cur.execute("SELECT …")`.  
  - New: ORM queries via `session.query(SA.System...)`, results built into dicts with same shapes.

- **Station filtering**:  
  - Old: manual `COUNT(*)` SQL string with `stationWhere`.  
  - New: ORM `.count()` to detect empty stations; join strategy determined with ORM `join`/`outerjoin`.  
  - No raw `stationWhere` string concatenation.

- **Main query**:  
  - Old: formatted SQL string with `IFNULL(...)`, `INNER/LEFT JOIN`, `ORDER BY`.  
  - New: ORM query with `func.ifnull`, conditional `join` vs `outerjoin`, and `.order_by(...)`.

- **Result iteration**:  
  - Old: `for … in cur:` streaming cursor rows.  
  - New: `rows = q.all()` and `for … in rows:` with tuple unpack matching the ORM projection.

- **Timestamp handling**:  
  - Old: `cur.execute("SELECT CURRENT_TIMESTAMP")`.  
  - New: `session.query(func.now()).scalar()`.

---

## Output Logic
- Output formatting (`outFmt`, headers, item rendering) unchanged.  
- Preserves same column layout, category/grouping rules, and demand/supply formatting.  
- Behaviour is identical to sqlite version.

---

## Status
- `prices.py` is now free of sqlite3.  
- All database interactions flow through SQLAlchemy’s ORM.  
- API and output formats are unchanged; existing consumers of `dumpPrices` can switch seamlessly to passing a `Session`.

# TradeDangerous Refactor — `cache.py`

This summarises the sqlite3 → SQLAlchemy migration applied to `cache.py`.  
Wrappers remain in place for API compatibility; existing return shapes and calling conventions are preserved.

---

## sqlite3 Removal
- `import sqlite3` removed.
- All direct `sqlite3.connect`, `cursor.execute`, `executemany`, `commit`, and `close` calls eliminated.
- PRAGMAs (`foreign_keys`, etc.) dropped — now applied centrally in `engine.py`.

---

## Refactored Functions

### `getSystemByNameIndex`, `getStationByNameIndex`, `getItemByNameIndex`
- Old: raw SQL queries via cursor.  
- New: ORM queries via `session.query(...)`.  
- Return dicts unchanged.

### `processPrices`
- Old: accepted `sqlite3.Connection`, used cursors for lookups and inserts.  
- New: accepts `Session`.  
- Placeholder stations inserted via `session.add` + `flush()` instead of `INSERT`.  
- Existing station items loaded with ORM query instead of `SELECT`.  
- Output contract unchanged (tuple of stations, items, zeros, counters).

### `processPricesFile`
- Old: executed raw `DELETE`, `INSERT OR REPLACE`, `UPDATE` via cursor.  
- New: ORM equivalents:  
  - Deletes via `.query(...).delete()`.  
  - Inserts/updates via `session.merge()`, preserving upsert semantics.  
  - Market flag update via ORM `.update()`.  
- Transaction wrapped with `session.begin()`.

### `processImportFile`
- Old: built raw `INSERT OR REPLACE` SQL string from CSV headers, executed row-by-row.  
- New:  
  - CSV headers parsed into **specs** (`direct`, `unique`, `fk`, `helper`, `skip`) via `_parse_headers`.  
  - Objects constructed row-by-row via `_process_row` and `_resolve_fk`.  
  - Foreign key resolution implemented in Python:
    - `!name@System.system_id` treated as **helper** (system name), used to disambiguate stations.  
    - `name@Station.station_id` resolved to numeric `station_id` by `(Station.name, System.name)`.  
    - `name@Category.category_id` resolved to numeric `category_id` by `Category.name` (with fallback to numeric IDs in Item.csv).  
  - RareItem rows now mirror sqlite3 semantics: helpers are discarded, FKs resolved, and the real Rare name from `unq:name` preserved.  
  - Uniqueness checks, deprecation logic, and type coercion retained.  
  - Chunked commits added (`TD_LISTINGS_BATCH`) to avoid giant transactions, with safe defaults (50k rows per commit on MariaDB, 250k on SQLite).

### `buildCache`
- Old: created temp sqlite file, ran `.executescript()`, imported data, swapped files.  
- New:  
  - Creates engine via `make_engine_from_config`.  
  - Recreates schema via `lifecycle.reset_sqlite` (SQLite) or `lifecycle.reset_mariadb` (MariaDB).  
  - Runs imports using ORM-based `processImportFile` and `processPricesFile`.  
  - File rotation retained for SQLite; skipped for MariaDB.  
  - Safe commit between files enforced.

### `regeneratePricesFile`
- Old: called `prices.dumpPrices(dbFilename, …)` with sqlite filename and touched DB file mtime.  
- New: passes an active `Session` into refactored `prices.dumpPrices`.  
- File timestamp hack removed.

### `importDataFromFile`
- Old: used `tdb.getDB()`, ran raw `DELETE FROM StationItem`, called sqlite-based import.  
- New:  
  - Uses session factory from `tdb.engine`.  
  - Resets via ORM `.delete()`.  
  - Calls ORM-based `processPricesFile`.  
  - Regenerates `.prices` file via refactored `regeneratePricesFile`.

---

## Unchanged
- Exception classes (`UnknownSystemError`, `DuplicateKeyError`, etc.) unchanged.  
- Helpers (`parseSupply`, regex patterns, deprecation checks) unchanged.  
- Output contracts of all functions preserved.

---

## Status
- `cache.py` is now completely free of sqlite3.  
- All database operations use SQLAlchemy ORM.  
- File is backend-agnostic (SQLite and MariaDB supported).  
- RareItem, Station, Item and Category CSVs confirmed to import with correct FK resolution.  
- Trailing blank lines in CSVs safely ignored.  
- API compatibility maintained for existing callers.


# TradeDangerous Refactor — `plugins/eddblink_plug.py`

This summarises the sqlite3 → SQLAlchemy migration applied to the **EDDBLink plugin**.  
The plugin API (`ImportPlugin`) remains unchanged; it still exposes the same options and behaviour.  
All database operations now use SQLAlchemy ORM and engine utilities.

---

## sqlite3 Removal
- `import sqlite3` removed.
- All direct `cursor.execute`, `BEGIN/COMMIT TRANSACTION`, `INSERT OR IGNORE`, `DELETE`, `UPDATE`, and `VACUUM` calls eliminated.
- Manual commit/rollback management replaced with `Session.begin()` context blocks.
- SQLite PRAGMAs remain handled centrally in `engine.py`.

---

## Refactored Helpers
- **`_make_item_id_lookup`**, **`_make_station_id_lookup`**  
  - Old: raw `SELECT` on `Item`/`Station`.  
  - New: ORM queries on `SA.Item` / `SA.Station`.  

- **`_collect_station_modified_times`**  
  - Old: `strftime('%s', MIN(modified))` to epoch.  
  - New: `func.min(SA.StationItem.modified)` via ORM, converted to epoch in Python.

---

## Refactored Methods

### `purgeSystems`
- Old: `DELETE FROM System WHERE NOT EXISTS (...)`.  
- New: ORM `delete(SA.System).where(~exists(...))`.

### `importListings`
- Old:  
  - Raw SQL statements: `UPDATE … SET from_live=0`, `DELETE FROM StationItem`,  
    `INSERT OR IGNORE INTO StationItem (…)`, manual `BEGIN/COMMIT`.  
  - SQLite-only datetime conversion (`datetime(?, 'unixepoch')`).  
- New:  
  - Fully ORM-driven:  
    - `update` to unliven station.  
    - `delete` to flush old station items.  
    - `session.add(StationItem(...))` for inserts.  
  - Listing timestamp converted via `datetime.utcfromtimestamp()`.  
  - Transactions handled by `Session.begin()`.  
  - Periodic `session.flush()` replaces manual WAL balancing.  
  - VACUUM preserved for SQLite backends using `session.execute(text("VACUUM"))`.  

### `run`
- Detects first-run:  
  - SQLite → check for DB file.  
  - MariaDB → `lifecycle.is_empty(engine)`.  
- **`clean` option**:  
  - Old: manual file deletes + `self.tdb.reloadCache()`.  
  - New: CSV/file cleanup preserved; schema reset via `lifecycle.ensure_fresh_db`; cache reload via existing `self.tdb.reloadCache()`.  
- Option resolution (`listings`, `all`, `solo`, etc.) unchanged.  
- File downloads unchanged.  
- Static-table rebuild still calls `reloadCache()` (API preserved).  
- Market data import calls new ORM-based `importListings`.  
- `.prices` regeneration continues via refactored `cache.regeneratePricesFile`.

---

## Unchanged (No DB Access)
- `DecodingError` exception.  
- `downloadFile` (HTTP freshness, timestamp sync).  
- Option parsing logic in `run`.  

---

## Status
- `eddblink_plug.py` is now completely free of sqlite3.  
- All database interactions flow through SQLAlchemy ORM and lifecycle helpers.  
- API compatibility preserved (`reloadCache`, plugin options, entrypoints unchanged).  
- VACUUM retained for SQLite, gated by dialect.  

# TradeDangerous Refactor — `plugins/spansh_plug.py`

## Overview
A from-scratch, high-throughput importer for the Spansh galaxy dump (`galaxy_stations.json`).  
Goals: **speed**, **idempotency**, **DB-agnostic plugin surface** (dialect specifics live in `tradedangerous/db/utils.py`).

## What it does
- Streams a multi-GiB top-level JSON array using **ijson** (C-backed) — constant memory footprint.
- Imports/updates: **System**, **Station**, **Item/StationItem**, **Ship/ShipVendor**, **Upgrade/UpgradeVendor**.
- Applies **per-service freshness gating** via `-O maxage=<days>`:
  - a station is processed iff *any* of its `market/outfitting/shipyard` sections has a fresh `updateTime`.
  - only fresh services for that station are written.
- Maintains **timestamp-guarded** upserts:
  - parent tables (`System`, `Station`) track `modified`.
  - link tables (`StationItem`, `ShipVendor`, `UpgradeVendor`) store service timestamps; **updates only if newer**.
- Enforces **`Item.ui_order`** once at the end (stable, alphabetic per category).
- Imports **RareItem** from template, but **only for (System, Station) pairs that already exist in the DB** (insensitive to the current run’s `maxage`). Rows are passed through **verbatim**.

## Behavior & Guarantees
- **Idempotent**: repeated runs/narrow `maxage` won’t regress data (timestamp guards).
- **FK-safe** ordering: upserts System → Station → Services; then “finalize” System.modified from imported stations.
- **`System.added` policy** (if column exists):
  - On **insert**: set to **20** (EDSM).
  - On **update**: never overwrite **unless NULL**, then set to **20**.
- **Counters in progress line** (TTY-friendly, width-capped; no wrap/scroll spam):
  - `systems` and `stations`: attempted upserts.
  - `kept: markets / outfitters / shipyards`: **count of stations** where that fresh service was processed.
- Emits a **final summary line** after streaming, then normal scrolling output for export.

## Performance
- **Streaming JSON** via `ijson.items(fh, 'item')`.
- **No pre-read short-circuits** (no `SELECT MAX(modified)` per station/service). The database resolves per-row upserts internally.
- **Batching/transactions** (resolved at runtime):
  - **SQLite**: single large transaction; connection PRAGMAs applied (`WAL`, `synchronous=NORMAL`, `temp_store=MEMORY`, larger cache).
  - **MySQL/MariaDB**: large batch commits by default (50k), using dialect `INSERT … ON DUPLICATE KEY UPDATE`.
- Achieves stable throughput on multi-GiB inputs; DB no longer dominates wall time.

## Options
- `-O url=<http(s)>` — download source (default if neither `url` nor `file` given).
- `-O file=<path>|-` — read local file or `stdin`.
- `-O maxage=<days>` — per-service freshness gate (float).
- `-O pricesonly=1` — **testing aid**: skip import; regenerate `TradeDangerous.prices` only.

## Files & Outputs
- Uses the configured directories from your environment/ini:
  - **tmp dir**: `tdenv.tmpDir` (fallback `tdb.tmpDir`, then `"tmp"`) for the JSON cache (with `Last-Modified` conditional fetch).
  - **data dir**: `tdenv.dataDir` (fallback `tdb.dataDir`, then `"data"`) for CSV exports.
  - **templates**: `tdenv.templateDir` (fallback package `templates/`) for `RareItem.csv`.
- CSVs are written via `csvexport.exportTableToFile`.
- `TradeDangerous.prices` is rebuilt via `cache.regeneratePricesFile(self.tdb, self.tdenv)` (kept for backward compatibility; slated for deprecation).

## DB Abstraction & Dialects
- The plugin remains DB-agnostic; **all dialect/sql fast paths are in** `tradedangerous/db/utils.py`:
  - SQLite: `dialects.sqlite.insert(...).on_conflict_do_update(...)`
  - MySQL/MariaDB: `dialects.mysql.insert(...).on_duplicate_key_update(...)`
  - Simple/modified upsert helpers and bulk PRAGMAs live there.
- Batch size policy:
  1. `db_utils.get_import_batch_size(session, profile="spansh")` if provided.
  2. `TD_LISTINGS_BATCH` env (`>0` size; `<=0` = single TX).
  3. Defaults: SQLite → single TX; MySQL → 50k; fallback → 5k.

## Logging & UX
- On TTY: single-line live status during import; width-capped; cleared on completion.
- After streaming: prints **“Import complete — …”** snapshot.
- Export stage prints each dataset on its own line and ends with “Cache export completed.”

## Error Handling
- Uses `CleanExit` for controlled early termination (download failures, empty/invalid JSON, RareItem template missing).
- Safe session handling with commit/rollback and close on all paths.
- RareItem rows for missing `(System, Station)` pairs are **skipped with a warning count** (prevents NOT NULL/ FK errors).

## Dependencies
- `ijson` for streaming parse.
- SQLAlchemy Core/ORM (dialect inserts).
- Existing project modules: `plugins`, `cache`, `csvexport`, `db.utils`.

## Typical Invocations
```bash
# Full import from cached/downloaded JSON, 30-day freshness:
python -m trade import -P spansh -O maxage=30

# Import from local file, narrow freshness for a fast update:
python -m trade import -P spansh -O file=tmp/galaxy_stations.json,maxage=2

# Prices-only smoke test (no import):
python -m trade import -P spansh -O pricesonly=1
