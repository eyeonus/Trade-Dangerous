# TradeDangerous Refactor — `tradedb.py` 

This document summarises the sqlite3 → SQLAlchemy migration applied to `tradedb.py`.  
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


# TradeDangerous Refactor — `prices.py`

This document summarises the sqlite3 → SQLAlchemy migration applied to `prices.py`.  
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

This document summarises the sqlite3 → SQLAlchemy migration applied to `cache.py`.  
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
  - CSV headers mapped directly to ORM model fields.  
  - Objects constructed as dicts (`dict(zip(...))`) and merged via `session.merge()`.  
  - Uniqueness checks and deprecation logic preserved.  
- No raw SQL string construction.

### `buildCache`
- Old: created temp sqlite file, ran `.executescript()`, imported data, swapped files.  
- New:  
  - Creates engine via `make_engine_from_config`.  
  - Recreates schema via `lifecycle.reset_sqlite` (SQLite) or `lifecycle.reset_mariadb` (MariaDB).  
  - Runs imports using ORM-based `processImportFile` and `processPricesFile`.  
  - File rotation retained for SQLite; skipped for MariaDB.  

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
- API compatibility maintained for existing callers.
