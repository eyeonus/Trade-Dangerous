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
4. Remove dependent data manually in dependency order
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

In Notepad++, open Find & Replace (`Ctrl+H`) and enable **Regular expression** mode.

**Find:**

```
^[ \t](.?)[ \t]+[+-]?\d+(?:.\d+)?[ \t]*$
```

**Replace with:**

```
\1
```

---

## Step 4 – Crop the Database

Open the database:

```bash
sqlite3 data/TradeDangerous.db
```

### 4.1 Import system list

Create a temporary table and import the cleaned list:

```sql
CREATE TABLE keep_systems(name TEXT);
```

```
.mode csv
.import sol25ly.txt keep_systems
```

### 4.2 Delete unwanted systems

FK cascade is not configured on all tables, so delete in dependency order
with FK enforcement off:

```sql
PRAGMA foreign_keys = OFF;

DELETE FROM System
WHERE name NOT IN (SELECT name FROM keep_systems);

DELETE FROM Station
WHERE system_id NOT IN (SELECT system_id FROM System);

DELETE FROM StationItem
WHERE station_id NOT IN (SELECT station_id FROM Station);

DELETE FROM ShipVendor
WHERE station_id NOT IN (SELECT station_id FROM Station);

DELETE FROM UpgradeVendor
WHERE station_id NOT IN (SELECT station_id FROM Station);

-- Item.rare_station_id is a nullable FK to Station; NULL out orphaned links
UPDATE Item
SET rare_station_id = NULL
WHERE rare_station_id IS NOT NULL
  AND rare_station_id NOT IN (SELECT station_id FROM Station);

PRAGMA foreign_keys = ON;
```

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

If regenerating from old v12 fixtures, also delete these files which no longer exist in the schema:
  - `RareItem.csv`
  - `Added.csv`

Verify required files exist:
- System.csv
- Station.csv
- StationItem.csv
- Item.csv
- Category.csv
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