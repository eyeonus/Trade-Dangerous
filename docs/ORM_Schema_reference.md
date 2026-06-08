# TradeDangerous ORM & Schema (SQLite-canonical)

**Canonical source:** `TradeDangerous.sql` (SQLite).  
**Goal:** Keep SQLite as the authoritative shape (tables, keys, checks, index *intent*), while the ORM ensures behavior is consistent on stricter backends (MySQL/MariaDB).

> **Removed (overall refactor, alongside Checkpoint K):** the outfitting tables
> `Upgrade`, `UpgradeVendor`, and the `FDevOutfitting` EDCD bridge were dropped —
> no command ever queried them (a 2014 `dbimport` placeholder for a `buy --upgrade`
> mode that was never built), and `UpgradeVendor` alone was ~3.6 GiB / hours of
> import time. Ships (`Ship`, `ShipVendor`, `FDevShipyard`) and the
> `Station.outfitting` Y/N service flag are retained. The unused
> `StationBuying` / `StationSelling` views were dropped in the same pass. See
> `docs/REFACTOR_PROGRESS.md` (Checkpoint K).

---

## At a Glance

| Concern | SQLite (canonical) | ORM / MySQL-MariaDB (effective) |
|---|---|---|
| Text “name” fields | `VARCHAR(128) COLLATE nocase` | `CIString(128)` (utf8mb4, case-insensitive collation) |
| TriState / Pad | `TEXT(1)` + `CHECK` | SQLAlchemy `Enum` → DB `CHECK` + Python validation |
| Timestamps | `DEFAULT CURRENT_TIMESTAMP` (where present) | `DateTime(6)` with `now6()` defaults where applicable |
| StationItem price indexes | Partial (`WHERE price > 0`) | Same column order; use `> 0` predicates in queries |
| `WITHOUT ROWID` | `Station`, `ShipVendor`, `StationItem` | SQLite only; ORM uses `sqlite_with_rowid=False` to match template |

**Domain sets (enforced everywhere)**
- `TriState ∈ {'Y','N','?'}`
- `PadSize ∈ {'S','M','L','?'}`

---

## Conventions & Utilities

- **Naming convention:** deterministic `ix_/uq_/ck_/fk_/pk_` names for constraints/indexes.
- **Case-insensitive strings:** `CIString` → `NOCASE` on SQLite; `utf8mb4_unicode_ci` on MySQL/MariaDB.
- **Partial-name lookup key:** `System.lookup_name` / `Station.lookup_name` hold a normalised copy of `name` (uppercased; punctuation, spaces and apostrophes stripped), populated via `corrections.normalize_str`. Nullable, no index — only ever queried with a leading wildcard.
- **Time helpers:**  
  - `now6()` → `CURRENT_TIMESTAMP(6)` on MySQL/MariaDB, `CURRENT_TIMESTAMP` elsewhere.  
  - `DateTime6` → `DATETIME(6)` on MySQL/MariaDB; generic `DateTime` elsewhere.

---

## Tables

### System
- **Columns:** `system_id` PK; `name` (CI); `lookup_name` (CI, nullable — partial-name key); `pos_x/pos_y/pos_z` (float); `modified` (default timestamp).
- **Indexes:** `idx_system_by_pos (pos_x,pos_y,pos_z,system_id)`, `idx_system_by_name (name)`.

### Station
- **Columns:** `station_id` PK; `name` (CI); `lookup_name` (CI, nullable — partial-name key); `system_id` FK (DELETE CASCADE); `ls_from_star` (default 0, CHECK ≥ 0 on both backends); service flags (`TriState`), including `outfitting`; `max_pad_size` (`PadSize`); `type_id` default 0; `modified` default timestamp.
- **Indexes:** `idx_station_by_system (system_id)`, `idx_station_by_name (name)`, `idx_station_by_system_name (system_id, name)`.
- **Storage:** `WITHOUT ROWID` on SQLite.

### Category
- **Columns:** `category_id` PK; `name` (CI).
- **Indexes:** `idx_category_by_name (name)`.

### Item
- **Columns:** `item_id` PK; `name` (CI); `category_id` FK (update/delete cascade); `ui_order` default 0; `avg_price` nullable; `fdev_id` nullable; `rare_station_id` nullable BIGINT FK → `Station.station_id` (update CASCADE, delete RESTRICT).
- **Indexes:** `idx_item_by_fdev_id (fdev_id)`; `idx_item_by_category (category_id)`.
- **Rarity model:** `rare_station_id IS NOT NULL` means the item is rare and identifies its canonical source station. Most items have `NULL`.

### StationItem
- **Columns:** composite PK `(station_id, item_id)`; demand_* and supply_* (**price/units/level**, ints); `modified` default timestamp; `from_live` default 0.
- **FKs:** to `Station` and `Item` (update/delete cascade).
- **Indexes (intent):**
  - `si_mod_stn_itm (modified, station_id, item_id)` — recent changes.
  - `si_itm_dmdpr (item_id, demand_price) WHERE demand_price > 0`.
  - `si_itm_suppr (item_id, supply_price) WHERE supply_price > 0`.
- **Query rule:** Always include `> 0` predicates for price-side scans to preserve planner behavior across backends.
- **Storage:** `WITHOUT ROWID` on SQLite.

### Ship
- **Columns:** `ship_id` PK; `name` (CI); `cost` nullable.

### ShipVendor
- **Columns:** composite PK `(ship_id, station_id)`; `modified` default timestamp.
- **FKs:** to `Ship` and `Station` (update/delete cascade).
- **Indexes:** `idx_shipvendor_by_station (station_id)`.
- **Storage:** `WITHOUT ROWID` on SQLite.

---

## EDCD Mirror Tables

### FDevShipyard
- **Columns:** `id` PK; `symbol` (CI); `name` (CI); `entitlement`.

---

## Behavioral Guarantees
- **Case-insensitive lookups** for all names on all backends.
- **Domain integrity** for TriState/Pad everywhere.
- **Consistent price-side semantics** (`> 0` filters) and index intent across backends.
- **Timestamps:** defaulted where SQLite does.

---
