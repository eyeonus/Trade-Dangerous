# Trade Dangerous Schema Batch A Specification

Date: 2026-03-23
Status: Historical planning note updated for rebuild-only rollout policy on 2026-04-17
Audience: TD maintainers and downstream consumers of the TD database schema
Companion documents:
- `docs/schema_impact_matrix.md`
- `docs/performance_optimization_plan.md`
- `docs/performance_tactical_backlog.md`

## Purpose

This document defines the first and intentionally narrow schema batch for the performance program.

Batch A is designed to be:

- additive only
- low risk
- fair to downstream consumers
- sufficient to unblock resolver-first optimization work
- followed by a schema freeze while most of the remaining optimization work happens in code

## Batch A Summary

### Definite payload

1. Ensure `idx_system_by_name` is present in the public TD schema on both SQLite and MariaDB through the supported rebuild/reset flows.
2. Verify that fresh SQLite rebuilds and fresh MariaDB resets produce the intended Batch A index set.
3. Verify that exact `System.name = ?` lookups use the index after rebuild/reset.

### Optional payload, only if proven before the batch is cut

1. Include a composite index on `Station(system_id, name)` in the same Batch A release.

That optional index must not be included by instinct. It only belongs in Batch A if live-database measurements show it materially improves the resolver path for `system/station` lookups.

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

For the purposes of downstream communication, the public schema contract after Batch A is:

### Guaranteed

- `System` has an index named `idx_system_by_name` on `(name)`
- `Station` has an index named `idx_station_by_system_name` on `(system_id, name)` as part of the inherited/prepared Batch A baseline actually being shipped

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

## Important Note About `orm_models.py`

For `idx_system_by_name` and `idx_station_by_system_name`, ORM metadata is already aligned with the intended public schema outcome.

That means current Batch A work is no longer about adding these indexes to metadata. It is about verifying that the supported rebuild/reset paths produce the expected schema and documenting the release policy honestly.

## Recommended Implementation Shape

## Step 1: Keep the source-of-truth paths aligned

Maintain:

- `TradeDangerous.sql` as the SQLite rebuild source of truth
- `orm_models.py` plus lifecycle reset as the MariaDB reset source of truth

## Step 2: Verify the supported rebuild/reset flows

Batch A verification should confirm that:

1. a fresh SQLite rebuild creates the intended indexes
2. a fresh MariaDB reset creates the same public index set
3. exact system lookup plans use `idx_system_by_name`

## Step 3: Keep scope narrow

Batch A should not, in this release:

- add additive in-place reconciliation helpers
- promise upgrade-in-place support for pre-existing databases
- reconcile every metadata/template mismatch in sight
- add speculative search columns or tables

That discipline is what keeps Batch A fair to downstream consumers and aligned with the declared rebuild-only rollout policy.

## Verification Rules

Batch A is not complete until all of the following are true.

## Fresh SQLite rebuild/reset

Verify:

- `idx_system_by_name` exists after a rebuild from [TradeDangerous.sql](/D:/Git/Trade-Dangerous/tradedangerous/templates/TradeDangerous.sql)
- `idx_station_by_system_name` exists after the same rebuild

Suggested checks:

```sql
PRAGMA index_list('System');
PRAGMA index_list('Station');
EXPLAIN QUERY PLAN SELECT system_id FROM System WHERE name = 'Sol';
```

Expected outcome:

- `idx_system_by_name` present
- `idx_station_by_system_name` present
- exact system lookup does not show a full table scan

## Fresh MariaDB reset

Verify:

- a metadata-driven reset results in the same public index set

Suggested checks:

```sql
SHOW INDEX FROM System;
SHOW INDEX FROM Station;
```

## Cross-backend parity check

For Batch A, parity means:

- both backends expose `idx_system_by_name`
- both backends expose `idx_station_by_system_name`
- neither backend gets extra Batch A public schema items that the other lacks

## Benchmark confirmation

Before closing Batch A, re-run the exact-system lookup plan and timing checks on the live SQLite database after rebuild/reset verification.

The point is not heroic speedup. The point is proving the resolver-first path is no longer kneecapped by an avoidable scan.

## Release Packaging Recommendation

Batch A should be released as one deliberately boring schema update.

Suggested release contents:

1. aligned schema source-of-truth paths
2. rebuild/reset verification evidence
3. release notes for downstream consumers that explicitly describe rebuild/reset support

Do not mix Batch A with:

- resolver rollout
- command migration
- `TradeCalc` optimization
- unrelated ORM/schema cleanup

## Suggested Release Note Text For Downstream Developers

### Short version

> This release includes a small additive schema update for read performance. No tables or columns change. The primary addition is an index on `System(name)`, and the shipped Batch A schema also includes `Station(system_id, name)`. Supported rollout is via rebuild/reset (`clean` import), not in-place upgrade of existing databases.

### Longer version

> This release performs a narrow additive schema update intended to improve lookup performance without changing the underlying data shape. No tables, columns, primary keys, or foreign keys are changed. The public schema now includes `idx_system_by_name` on `System(name)` and `idx_station_by_system_name` on `Station(system_id, name)`. Supported rollout is via rebuild/reset (`clean` import). Existing databases are not upgraded in place as part of this release, and later refactor stages will introduce a breaking schema change that will require rebuild anyway.

## Suggested Maintainer Checklist

### Before cut

- confirm the Batch A public index set to be shipped
- verify fresh-build/reset behavior on SQLite
- verify fresh-reset behavior on MariaDB
- capture query-plan evidence for exact system lookup on live SQLite after rebuild/reset
- ensure release communication does not promise in-place upgrade support

### At cut

- publish release note with the full Batch A index list
- tell downstream consumers the supported path is rebuild/reset (`clean` import)

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

Ship Batch A as one additive read-performance schema release through the supported rebuild/reset path, with the public index set that is actually present in the aligned source-of-truth files:

- `idx_system_by_name`
- `idx_station_by_system_name`

Everything else stays out.

That gives downstream consumers the clearest truthful promise:

- one early schema batch
- minimal data-shape impact
- rebuild/reset required rather than in-place upgrade
- most of the real optimization work follows in code, not schema
