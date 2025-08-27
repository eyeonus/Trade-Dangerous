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
