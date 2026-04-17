# Trade Dangerous Schema Batch A Specification

Date: 2026-03-23
Status: Verified and closed for rebuild-only rollout on 2026-04-17
Audience: TD maintainers and downstream consumers of the TD database schema
Companion documents:
- `docs/schema_impact_matrix.md`
- `docs/performance_optimization_plan.md`
- `docs/performance_tactical_backlog.md`
- `docs/REFACTOR_PROGRESS.md`

## Purpose

This document defines the first and intentionally narrow schema batch for the performance program.

Batch A is designed to be:

- additive only
- low risk
- fair to downstream consumers
- sufficient to unblock resolver-first optimization work
- followed by a schema freeze while most of the remaining optimization work happens in code

## Batch A Summary

### Shipped payload

1. `idx_system_by_name` is present in the public TD schema on both SQLite and MariaDB through the supported rebuild/reset flows.
2. `idx_station_by_system_name` is also part of the shipped Batch A schema.
3. Runtime verification shows exact `System.name = ?` lookups use `idx_system_by_name`, and exact `system/station` joins use the station composite index.

## Hard Constraints

Batch A must not change:

- table set
- column set
- column types
- primary keys
- foreign keys
- row semantics
- importer payload format

In plain English: this is an additive index release, not a data-shape release.

## Why Batch A Exists

The performance roadmap depends on moving valid command resolution away from full `TradeDB` preload. That only makes sense if the database can answer exact name lookups cheaply.

Current repo/runtime reality is now:

- ORM metadata already declares `idx_system_by_name`
- the canonical SQLite schema template already creates it
- the station composite index is already present in both ORM metadata and the SQLite template as inherited preparatory baseline

Relevant files:

- [TradeDangerous.sql](/D:/Git/Trade-Dangerous/tradedangerous/templates/TradeDangerous.sql)
- [orm_models.py](/D:/Git/Trade-Dangerous/tradedangerous/db/orm_models.py)
- [lifecycle.py](/D:/Git/Trade-Dangerous/tradedangerous/db/lifecycle.py)
- [tradedb.py](/D:/Git/Trade-Dangerous/tradedangerous/tradedb.py)

## Public Schema Contract For Batch A

For downstream communication, the public schema contract after Batch A is:

### Guaranteed

- `System` has an index named `idx_system_by_name` on `(name)`
- `Station` has an index named `idx_station_by_system_name` on `(system_id, name)`

### Explicitly not part of Batch A

- new columns
- new tables
- normalized search columns
- search helper tables
- staging/export tables on SQLite
- cosmetic index-name reconciliation unrelated to the resolver speed path
- additive in-place upgrade of existing databases

## Backend Policy

Batch A is not a SQLite-only change and not a MariaDB-only change.

The correct policy is:

- one logical TD public schema
- two source-of-truth creation/reset paths
- one public index contract that both backends must satisfy after rebuild/reset

### SQLite

Source of truth for fresh builds:

- [TradeDangerous.sql](/D:/Git/Trade-Dangerous/tradedangerous/templates/TradeDangerous.sql)

### MariaDB

Source of truth for fresh resets:

- [orm_models.py](/D:/Git/Trade-Dangerous/tradedangerous/db/orm_models.py)
- reset path in [lifecycle.py](/D:/Git/Trade-Dangerous/tradedangerous/db/lifecycle.py)

### Existing databases

Existing databases are **not** upgraded in place under the current Batch A rollout policy.

Supported rollout is rebuild/reset via the clean import path already announced to users.

That policy is acceptable here because later refactor stages will introduce a breaking schema change that will require rebuild anyway.

## Exact Batch A DDL

### SQLite

```sql
CREATE INDEX IF NOT EXISTS idx_system_by_name ON System (name);
CREATE INDEX IF NOT EXISTS idx_station_by_system_name ON Station (system_id, name);
```

### MariaDB / ORM metadata outcome

After metadata-driven reset, the resulting public schema must include:

```sql
CREATE INDEX idx_system_by_name ON System (name);
CREATE INDEX idx_station_by_system_name ON Station (system_id, name);
```

## Files That Define Batch A Reality

### Required source-of-truth files

1. [TradeDangerous.sql](/D:/Git/Trade-Dangerous/tradedangerous/templates/TradeDangerous.sql)
   Canonical SQLite rebuild schema.

2. [orm_models.py](/D:/Git/Trade-Dangerous/tradedangerous/db/orm_models.py)
   Canonical ORM/metadata reset schema for MariaDB.

3. [lifecycle.py](/D:/Git/Trade-Dangerous/tradedangerous/db/lifecycle.py)
   Reset path used to recreate schema from the backend-specific source of truth.

4. [tradedb.py](/D:/Git/Trade-Dangerous/tradedangerous/tradedb.py)
   Central lifecycle entry that decides whether a DB is kept or rebuilt.

### Not required for Batch A under current policy

- additive in-place reconciliation helper for existing DBs
- central index backfill code in normal startup path

## Verification Evidence Recorded On 2026-04-17

### SQLite runtime verification

Verified against the packaged SQLite database under `%LOCALAPPDATA%\TradeDangerous\data\TradeDangerous.db` after the supported rebuild/reset path.

Recorded outcomes:

- `PRAGMA index_list('System')` showed `idx_system_by_name`
- `PRAGMA index_list('Station')` showed `idx_station_by_system_name`
- `EXPLAIN QUERY PLAN SELECT system_id FROM System WHERE name = 'Sol'` used `idx_system_by_name`
- exact `system/station` join lookup used `idx_system_by_name` and covering `idx_station_by_system_name`

### MariaDB runtime/schema verification

Verified from the live `td_live` MariaDB schema.

Recorded outcomes:

- `System` contains `idx_system_by_name`
- `Station` contains `idx_station_by_system_name`, `idx_station_by_name`, and `idx_station_by_system`
- the composite station index shape is `(system_id, name)` as intended

## Important Note About `orm_models.py`

For `idx_system_by_name` and `idx_station_by_system_name`, ORM metadata is already aligned with the intended public schema outcome.

That means current Batch A work was not about adding these indexes to metadata. It was about verifying that the supported rebuild/reset paths produce the expected schema and documenting the release policy honestly.

## Verification Rules

Batch A is complete because all of the following are now true.

### SQLite rebuild/reset outcome

Verified:

- `idx_system_by_name` exists after the supported packaged rebuild/reset flow
- `idx_station_by_system_name` exists after the same flow
- exact system lookup does not show a full table scan

### MariaDB reset/schema outcome

Verified:

- the live MariaDB schema exposes the same public index set for `System` and `Station`

### Cross-backend parity check

For Batch A, parity now means:

- both backends expose `idx_system_by_name`
- both backends expose `idx_station_by_system_name`
- neither backend gets extra Batch A public schema items that the other lacks in the shipped contract

## Release Packaging Recommendation

Batch A should be released as one deliberately boring schema update.

Release contents:

1. aligned schema source-of-truth paths
2. rebuild/reset verification evidence
3. release notes for downstream consumers that explicitly describe rebuild/reset support

Do not mix Batch A with:

- resolver rollout
- command migration
- `TradeCalc` optimization
- unrelated ORM/schema cleanup

## Final Release Note Text For Downstream Developers

### Short version

> This release includes a small additive schema update for read performance. No tables or columns change. The shipped Batch A schema includes `idx_system_by_name` on `System(name)` and `idx_station_by_system_name` on `Station(system_id, name)`. Supported rollout is via rebuild/reset (`clean` import), not in-place upgrade of existing databases.

### Longer version

> This release performs a narrow additive schema update intended to improve lookup performance without changing the underlying data shape. No tables, columns, primary keys, or foreign keys are changed. The public schema now includes `idx_system_by_name` on `System(name)` and `idx_station_by_system_name` on `Station(system_id, name)`. Supported rollout is via rebuild/reset (`clean` import). Existing databases are not upgraded in place as part of this release, and later refactor stages will introduce a breaking schema change that will require rebuild anyway.

## Maintainer Checklist Outcome

### Before cut

- [x] confirm the Batch A public index set to be shipped
- [x] verify fresh-build/reset behavior on SQLite
- [x] verify fresh-reset/schema outcome on MariaDB
- [x] capture query-plan evidence for exact system lookup on live SQLite after rebuild/reset
- [x] ensure release communication does not promise in-place upgrade support

### At cut

- [x] publish release note with the full Batch A index list
- [x] tell downstream consumers the supported path is rebuild/reset (`clean` import)

### After cut

- freeze schema again while resolver and command migration work proceeds in code

## Explicit Non-Goals For Batch A

Batch A is not the place to:

- reconcile all ORM/template drift
- introduce search tables or normalized search columns
- rework import schema
- change public data shape
- make opportunistic schema tweaks one by one after release
- add in-place upgrade logic for existing databases

## Final Recommendation

Ship Batch A as one additive read-performance schema release through the supported rebuild/reset path, with the public index set that is actually present in the aligned source-of-truth files and verified in runtime/schema evidence:

- `idx_system_by_name`
- `idx_station_by_system_name`

Everything else stays out.

That gives downstream consumers the clearest truthful promise:

- one early schema batch
- minimal data-shape impact
- rebuild/reset required rather than in-place upgrade
- most of the real optimization work follows in code, not schema
