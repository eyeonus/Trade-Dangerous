# TradeDangerous ORM & Schema (SQLite-canonical)

**Canonical source:** `TradeDangerous.sql` (SQLite).  
**Goal:** Keep SQLite as the authoritative shape (tables, keys, checks, views, index *intent*), while the ORM ensures behavior is consistent on stricter backends (MySQL/MariaDB).

---

## At a Glance

| Concern | SQLite (canonical) | ORM / MySQL-MariaDB (effective) |
|---|---|---|
| Text “name” fields | `VARCHAR(40) COLLATE nocase` | `CIString(128)` (utf8mb4, case-insensitive collation) |
| TriState / Pad | `TEXT(1)` + `CHECK` | SQLAlchemy `Enum` → DB `CHECK` + Python validation |
| Timestamps | `DEFAULT CURRENT_TIMESTAMP` (where present) | `DateTime(6)` with `now6()` defaults where applicable |
| StationItem price indexes | Partial (`WHERE price > 0`) | Same column order; use `> 0` predicates in queries |
| UpgradeVendor.modified | `NOT NULL`, **no default** | App must set value explicitly (unchanged) |
| Views | `StationBuying`, `StationSelling` | Not modeled; mirror predicates in queries |

**Domain sets (enforced everywhere)**
- `TriState ∈ {'Y','N','?'}`
- `PadSize ∈ {'S','M','L','?'}`
- `FDevOutfitting`:
  - `category ∈ {'hardpoint','internal','standard','utility'}`
  - `mount ∈ {NULL,'Fixed','Gimballed','Turreted'}`
  - `guidance ∈ {NULL,'Dumbfire','Seeker','Swarm'}`

---

## Conventions & Utilities

- **Naming convention:** deterministic `ix_/uq_/ck_/fk_/pk_` names for constraints/indexes.
- **Case-insensitive strings:** `CIString` → `NOCASE` on SQLite; `utf8mb4_unicode_ci` on MySQL/MariaDB.
- **Time helpers:**  
  - `now6()` → `CURRENT_TIMESTAMP(6)` on MySQL/MariaDB, `CURRENT_TIMESTAMP` elsewhere.  
  - `DateTime6` → `DATETIME(6)` on MySQL/MariaDB; generic `DateTime` elsewhere.

---

## Tables

### Added
- **Columns:** `added_id` PK (autoinc); `name` (CI, unique).
- **Relations:** `Added 1→* System`.

### System
- **Columns:** `system_id` PK; `name` (CI); `pos_x/pos_y/pos_z` (float); `added_id` FK (update/delete cascade); `modified` (default timestamp).
- **Indexes (canonical):** `idx_system_by_pos (pos_x,pos_y,pos_z,system_id)`.
- **Notes:** An ORM index on `name` may exist for perf (not in legacy SQLite DDL).

### Station
- **Columns:** `station_id` PK; `name` (CI); `system_id` FK (DELETE CASCADE); `ls_from_star ≥ 0` (default 0); service flags (`TriState`); `max_pad_size` (`PadSize`); `type_id` default 0; `modified` default timestamp.
- **Indexes:** `idx_station_by_system (system_id)`, `idx_station_by_name (name)`.

### Category
- **Columns:** `category_id` PK; `name` (CI).
- **Indexes:** none in SQLite DDL; ORM may add one for perf.

### Item
- **Columns:** `item_id` PK; `name` (CI); `category_id` FK (update/delete cascade); `ui_order` default 0; `avg_price` nullable; `fdev_id` nullable.
- **Indexes:** `idx_item_by_fdev_id (fdev_id)`.

### StationItem
- **Columns:** composite PK `(station_id, item_id)`; demand_* and supply_* (**price/units/level**, ints); `modified` default timestamp; `from_live` default 0.
- **FKs:** to `Station` and `Item` (update/delete cascade).
- **Indexes (intent):**
  - `si_mod_stn_itm (modified, station_id, item_id)` — recent changes.
  - `si_itm_dmdpr (item_id, demand_price) WHERE demand_price > 0`.
  - `si_itm_suppr (item_id, supply_price) WHERE supply_price > 0`.
- **Query rule:** Always include `> 0` predicates for price-side scans to preserve planner behavior across backends.

### Ship
- **Columns:** `ship_id` PK; `name` (CI); `cost` nullable.

### ShipVendor
- **Columns:** composite PK `(ship_id, station_id)`; `modified` default timestamp.
- **FKs:** to `Ship` and `Station` (update/delete cascade).

### Upgrade
- **Columns:** `upgrade_id` PK; `name` (CI); `class` (int/number); `rating` `CHAR(1)`; `ship` (CI, nullable).

### UpgradeVendor
- **Columns:** composite PK `(upgrade_id, station_id)`; `modified` **NOT NULL** (no default; application must set).
- **FKs:** to `Upgrade` and `Station` (update/delete cascade).

### RareItem
- **Columns:** `rare_id` PK; `station_id` FK (cascade); `category_id` FK (cascade); `name` (CI, unique); `cost`, `max_allocation` optional; `illegal`, `suppressed` (`TriState`).

---

## EDCD Mirror Tables

### FDevShipyard
- **Columns:** `id` unique (treated as PK in ORM); `symbol` (CI); `name` (CI); `entitlement`.

### FDevOutfitting
- **Columns:** `id` unique (treated as PK in ORM); `symbol` (CI); `category` (CHECK set); `name` (CI); `mount` (CHECK or NULL); `guidance` (CHECK or NULL); `ship` (CI); `class` `CHAR(1)`; `rating` `CHAR(1)`; `entitlement`.

---

## Views (SQLite only)
- **StationSelling:** supply rows (`supply_price > 0`).
- **StationBuying:** demand rows (`demand_price > 0`).
- *ORM:* not modeled; replicate predicates in queries.

---

## Behavioral Guarantees
- **Case-insensitive lookups** for all names on all backends.
- **Domain integrity** for TriState/Pad and `FDevOutfitting` categoricals everywhere.
- **Consistent price-side semantics** (`> 0` filters) and index intent across backends.
- **Timestamps:** defaulted where SQLite does; `UpgradeVendor.modified` must be set by the application.

---
