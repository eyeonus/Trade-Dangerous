# Trade Dangerous Schema Batch A Specification

Date: 2026-03-23
Status: Proposed implementation spec
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

1. Add `idx_system_by_name` to the public TD schema on both SQLite and MariaDB.
2. Ensure existing databases on both backends gain that index in place if it is missing.
3. Verify that exact `System.name = ?` lookups use the index after rollout.

### Optional payload, only if proven before the batch is cut

1. Add a composite index on `Station(system_id, name)`.

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

Right now the codebase shows a mismatch:

- ORM metadata already declares `idx_system_by_name`
- the canonical SQLite schema template does not create it

Relevant files:

- [TradeDangerous.sql](/D:/Git/Trade-Dangerous/tradedangerous/templates/TradeDangerous.sql)
- [orm_models.py](/D:/Git/Trade-Dangerous/tradedangerous/db/orm_models.py)
- [lifecycle.py](/D:/Git/Trade-Dangerous/tradedangerous/db/lifecycle.py)
- [tradedb.py](/D:/Git/Trade-Dangerous/tradedangerous/tradedb.py)

## Public Schema Contract For Batch A

For the purposes of downstream communication, the public schema contract after Batch A is:

### Guaranteed

- `System` has an index named `idx_system_by_name` on `(name)`

### Possibly included if measured and announced before release

- `Station` has an index named `idx_station_by_system_name` on `(system_id, name)`

### Explicitly not part of Batch A

- new columns
- new tables
- normalized search columns
- search helper tables
- staging/export tables on SQLite
- cosmetic index-name reconciliation unrelated to the resolver speed path

## Backend Policy

Batch A is not a SQLite-only change and not a MariaDB-only change.

The correct policy is:

- one logical TD public schema
- two creation/update paths
- one index contract that both backends must satisfy

### SQLite

Source of truth for fresh builds:

- [TradeDangerous.sql](/D:/Git/Trade-Dangerous/tradedangerous/templates/TradeDangerous.sql)

### MariaDB

Source of truth for fresh resets:

- [orm_models.py](/D:/Git/Trade-Dangerous/tradedangerous/db/orm_models.py)
- reset path in [lifecycle.py](/D:/Git/Trade-Dangerous/tradedangerous/db/lifecycle.py)

### Existing databases

Fresh-build parity is not enough. Existing live databases must also be reconciled in place.

That means Batch A needs an additive index-upgrade path, not merely source-of-truth edits.

## Exact Batch A DDL

## Required DDL

### SQLite

```sql
CREATE INDEX IF NOT EXISTS idx_system_by_name ON System (name);
```

### MariaDB

```sql
CREATE INDEX idx_system_by_name ON System (name);
```

For MariaDB, the statement should only be executed after checking whether the index already exists.

## Optional DDL, only if benchmark-proven before release

### SQLite

```sql
CREATE INDEX IF NOT EXISTS idx_station_by_system_name ON Station (system_id, name);
```

### MariaDB

```sql
CREATE INDEX idx_station_by_system_name ON Station (system_id, name);
```

This optional index must be announced as part of the same Batch A release if included. It must not be added later as an unadvertised straggler.

## Files To Touch For Batch A

### Required

1. [TradeDangerous.sql](/D:/Git/Trade-Dangerous/tradedangerous/templates/TradeDangerous.sql)
   Add `idx_system_by_name` to the canonical SQLite schema.

2. [lifecycle.py](/D:/Git/Trade-Dangerous/tradedangerous/db/lifecycle.py)
   Add a schema reconciliation helper for additive public indexes on existing databases.

3. [tradedb.py](/D:/Git/Trade-Dangerous/tradedangerous/tradedb.py)
   Call the reconciliation helper during central DB refresh so both normal runs and import/update flows get the same behavior.

### Required only if optional composite index is approved before cut

4. [orm_models.py](/D:/Git/Trade-Dangerous/tradedangerous/db/orm_models.py)
   Add `idx_station_by_system_name` to ORM metadata so MariaDB resets and metadata-driven paths stay aligned.

### Nice to have

5. Tests or verification helpers under `tests/`
   Add checks for expected indexes on both backends, or at least for SQLite plus a MariaDB smoke path if that environment exists.

## Important Note About `orm_models.py`

For the definite `idx_system_by_name` item, ORM metadata already declares the index on `System`.

That means Batch A does not need to add it to `orm_models.py`; it needs to make the public schema contract and upgrade path match what the metadata already says.

This is useful because it keeps Batch A smaller.

## Recommended Implementation Shape

## Step 1: Define the public index set in code

Add one central helper in [lifecycle.py](/D:/Git/Trade-Dangerous/tradedangerous/db/lifecycle.py) that knows which additive public indexes must exist.

Suggested scope for Batch A:

- always require `idx_system_by_name`
- optionally require `idx_station_by_system_name` only if the batch decision says yes before release

Do not let this helper silently become a general "fix all schema drift" routine.

## Step 2: Add the index to the canonical SQLite template

Update [TradeDangerous.sql](/D:/Git/Trade-Dangerous/tradedangerous/templates/TradeDangerous.sql) so fresh SQLite rebuilds include the index automatically.

That keeps rebuilt databases and upgraded databases converging on the same state.

## Step 3: Add in-place reconciliation for existing databases

The reconciliation helper should:

1. inspect existing indexes on the relevant table
2. create missing Batch A indexes if absent
3. be idempotent
4. log what it created versus what already existed

### SQLite behavior

Use inspector or `PRAGMA index_list`-style inspection and `CREATE INDEX IF NOT EXISTS`.

### MariaDB behavior

Use SQLAlchemy inspection or `SHOW INDEX`-equivalent inspection and only run `CREATE INDEX` when the index is absent.

Do not assume an existing MariaDB database already has the index just because ORM metadata declares it.

## Step 4: Call reconciliation from the central refresh path

The safest integration point is the central DB lifecycle path used by normal runs and imports.

That points to [tradedb.py](/D:/Git/Trade-Dangerous/tradedangerous/tradedb.py) after `ensure_fresh_db(...)` in `reloadCache()`.

Reason:

- one entry point
- applies equally to CLI, GUI, import, and plugin-driven workflows that already converge there
- avoids backend-specific drift being fixed in one path but not another

## Step 5: Keep the helper narrowly scoped

The helper should only reconcile Batch A public indexes.

It should not, in this batch:

- create `ExportControl`
- create `StationItem_staging`
- reconcile every metadata/template mismatch in sight
- add speculative search columns or tables

That discipline is what keeps Batch A fair to downstream consumers.

## Verification Rules

Batch A is not complete until all of the following are true.

## Fresh SQLite rebuild

Verify:

- `idx_system_by_name` exists after a rebuild from [TradeDangerous.sql](/D:/Git/Trade-Dangerous/tradedangerous/templates/TradeDangerous.sql)

Suggested check:

```sql
PRAGMA index_list('System');
```

## Existing SQLite database upgrade

Verify:

- a database missing `idx_system_by_name` gains it in place
- no full destructive rebuild is required

Suggested checks:

```sql
PRAGMA index_list('System');
EXPLAIN QUERY PLAN SELECT system_id FROM System WHERE name = 'Sol';
```

Expected outcome:

- `idx_system_by_name` present
- exact system lookup no longer shows a full table scan

## Fresh MariaDB reset

Verify:

- a metadata-driven reset results in the same public index set

Suggested check:

```sql
SHOW INDEX FROM System;
```

## Existing MariaDB database upgrade

Verify:

- a MariaDB database missing `idx_system_by_name` gains it in place
- repeated runs do not attempt to recreate it

## Cross-backend parity check

For Batch A, parity means:

- both backends expose `idx_system_by_name`
- if the optional composite index is approved, both expose that too
- neither backend gets extra Batch A public schema items that the other lacks

## Benchmark confirmation

Before closing Batch A, re-run the exact-system lookup plan and timing checks on the live SQLite database.

The point is not heroic speedup. The point is proving the resolver-first path is no longer kneecapped by an avoidable scan.

## Release Packaging Recommendation

Batch A should be released as one deliberately boring schema update.

Suggested release contents:

1. schema template update
2. in-place index reconciliation code
3. verification checks/tests
4. release notes for downstream consumers

Do not mix Batch A with:

- resolver rollout
- command migration
- `TradeCalc` optimization
- unrelated ORM/schema cleanup

## Suggested Release Note Text For Downstream Developers

### Short version

> This release includes a small additive schema update for read performance. No tables or columns change. The primary addition is an index on `System(name)` to support faster name resolution. Existing databases are upgraded in place.

### Longer version

> This release performs a narrow additive schema update intended to improve lookup performance without changing the underlying data shape. No tables, columns, primary keys, or foreign keys are changed. The guaranteed addition is an index named `idx_system_by_name` on `System(name)`. Existing databases are upgraded in place. If any additional additive index is included in this release, it will be announced in the same release notes as part of the same schema batch rather than introduced piecemeal later.

## Suggested Maintainer Checklist

### Before cut

- confirm `idx_system_by_name` is the only guaranteed Batch A item
- decide whether `idx_station_by_system_name` has enough evidence to join Batch A
- update both source-of-truth paths as needed
- add index reconciliation helper
- verify fresh-build and in-place-upgrade behavior on SQLite
- verify fresh-reset and in-place-upgrade behavior on MariaDB
- capture before/after query plans for exact system lookup on live SQLite

### At cut

- publish release note with full Batch A index list
- tell downstream consumers this is the only planned early schema batch

### After cut

- freeze schema again while resolver and command migration work proceeds in code

## Explicit Non-Goals For Batch A

Batch A is not the place to:

- reconcile all ORM/template drift
- introduce search tables or normalized search columns
- rework import schema
- change public data shape
- make opportunistic schema tweaks one by one after release

## Final Recommendation

Ship Batch A as one additive read-performance index release with exactly one guaranteed change:

- `idx_system_by_name`

Treat `Station(system_id, name)` as the one and only optional extra, and only include it if it is proven before the batch is cut.

Everything else stays out.

That gives you the cleanest promise to downstream consumers:

- one early schema batch
- minimal impact
- no table-shape churn
- most of the real optimization work follows in code, not schema
