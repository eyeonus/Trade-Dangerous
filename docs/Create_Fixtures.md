# Trade Dangerous – Fixture Regeneration Procedure

## Purpose
Rebuild a **modern, internally consistent, reduced fixture dataset** for testing.

This procedure replaces the legacy fixture model and ensures:
- alignment with current schema (including FDev ID usage)
- deterministic test data
- fast, isolated test execution

---

## Overview

We:
1. Import a **fresh full database**
2. Select a **region of interest** (e.g. around Sol)
3. **Crop the database** to only those systems
4. Let FK cascades remove dependent data
5. Export the reduced dataset
6. Use that as the canonical fixture pack

---

## Prerequisites

- Working Trade Dangerous environment
- Access to current data import (eddblink / spansh / EDDN)
- SQLite CLI (`sqlite3`)
- Clean working directory

---

## Step 1 – Build a Fresh Database

Run a full data import:

```bash
trade import  # or your current eddblink/spansh workflow
```

Verify:
- Database builds successfully
- No schema errors
- Data looks sane

---

## Step 2 – Generate System Crop List

Choose a region that:
- is small enough for fast tests
- contains meaningful trade data
- includes multiple systems/stations

Example:

```bash
trade local Sol --ly 25 > sol25ly.txt
```

This produces a list of nearby systems.

---

## Step 3 – Convert to Usable List

Edit `sol25ly.txt` into a plain list or CSV of system names.

Example format:

```text
Sol
Alpha Centauri
Barnard's Star
...
```

Keep only the system names (no distances/columns).

---

## Step 4 – Crop the Database

Open the database:

```bash
sqlite3 data/TradeDangerous.db
```

### 4.1 Enable foreign keys

```sql
PRAGMA foreign_keys = ON;
```

### 4.2 Import system list

Create a temporary table:

```sql
CREATE TABLE keep_systems(name TEXT);
```

Import your system list:

```sql
.mode csv
.import sol25ly.csv keep_systems
```

### 4.3 Delete unwanted systems

```sql
DELETE FROM System
WHERE name NOT IN (SELECT name FROM keep_systems);
```

Because FK constraints are enabled:
- related rows in Station, StationItem, ShipVendor, etc.
  will be removed automatically

---

## Step 5 – Clean and Compact

```sql
VACUUM;
```

Optional but recommended:
- ensures DB is compact
- removes fragmentation from deletes

---

## Step 6 – Export Fixture Set

From the project root:

```bash
trade export --all-tables --path=tests/fixtures
```

This writes CSV files for all tables.

Then copy the database:

```bash
cp data/TradeDangerous.db tests/fixtures/
```

---

## Step 7 – Clean Fixture Pack

Remove unnecessary files:

- Delete header-only or unused tables (if present):
  - `StationDemand.csv`
  - `StationSupply.csv`

Verify required files exist:
- System.csv
- Station.csv
- StationItem.csv
- Item.csv
- Category.csv
- RareItem.csv
- Ship.csv
- ShipVendor.csv
- Upgrade.csv
- UpgradeVendor.csv
- FDevOutfitting.csv
- FDevShipyard.csv
- TradeDangerous.db

---

## Step 8 – Validate Fixtures

Run CLI commands directly against the new DB:

```bash
trade local Sol
trade buy --near=sol "hydrogen fuel"
trade sell --near=sol "hydrogen fuel"
trade market sol/abr
trade nav sol "Alpha Centauri"
```

Check:
- no crashes
- sensible output
- expected systems/stations present

---

## Step 9 – Validate Test Suite

Run:

```bash
pytest tests/test_trade.py
```

And (optionally):

```bash
uv run --active --group dev pytest
```

Confirm:
- all tests pass
- no reliance on ambient `./data`

---

## Notes & Design Decisions

### Why DB-Truth Fixtures
- faster test startup
- avoids rebuild complexity during smoke tests
- guarantees internal consistency

### Why Cropped Dataset
- reduces test runtime
- keeps meaningful relationships intact
- avoids “toy data” problems

### Why Not Raw CSV Only
- CSV-only rebuild depends on importer correctness
- better tested separately (future work)

---

## Future Improvements

- Add separate test module for **CSV rebuild validation**
- Possibly mark rebuild tests as `slow`
- Improve `export --all-tables` to avoid emitting empty tables

---

## Key Principle

> Fixtures must reflect **current schema + current data assumptions**,  
> or tests become misleading rather than protective.