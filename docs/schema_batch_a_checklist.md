# Trade Dangerous Schema Batch A Implementation Checklist

Date: 2026-03-23
Status: Execution checklist
Audience: Maintainers implementing the first schema batch
Companion documents:
- `docs/schema_batch_a_spec.md`
- `docs/schema_impact_matrix.md`
- `docs/performance_optimization_plan.md`

## Purpose

This document turns the Batch A schema specification into a concrete implementation checklist.

It is written to support real execution rather than policy discussion. The emphasis is on:

- execution order
- decision gates
- exact files to touch
- verification points
- safe stopping points
- release packaging

## Batch A In One Line

Ship one additive index release, with one guaranteed change:

- `idx_system_by_name` on `System(name)`

Only include this optional extra if it is measured and approved before the cut:

- `idx_station_by_system_name` on `Station(system_id, name)`

## Non-Negotiables

Before starting implementation, keep these constraints fixed:

- no new tables
- no new columns
- no changed column types
- no PK or FK changes
- no semantic data changes
- no sneaking in unrelated ORM/template cleanup

If any task starts to drift outside those rules, stop and reopen the scope decision explicitly.

## Execution Order

1. Freeze Batch A scope
2. Capture baseline evidence
3. Update fresh-build schema sources
4. Implement in-place index reconciliation
5. Wire reconciliation into the central lifecycle path
6. Verify SQLite fresh-build and upgrade behavior
7. Verify MariaDB fresh-reset and upgrade behavior
8. Run parity and query-plan checks
9. Package release notes for downstream consumers
10. Freeze schema again

## Decision Gate 0: Freeze Scope Before Coding

### Required decision

Confirm whether Batch A contains:

- only `idx_system_by_name`
- or `idx_system_by_name` plus `idx_station_by_system_name`

### Recommended default

Unless proven first, lock Batch A to:

- `idx_system_by_name` only

### Evidence needed to include the optional composite index

To include `idx_station_by_system_name`, capture all of the following first:

1. representative query shape for `system/station` resolver lookup
2. current query plan on the live SQLite DB
3. timing before index
4. timing after index on a test copy or scratch DB
5. judgment that the gain is meaningful enough to justify inclusion in the one schema batch

### Definition of done

- Batch A index list is written down and treated as fixed for the release

### Safe stop point

- no code changes yet, only release scope locked

## Task 1: Capture Baseline Evidence

### Goal

Have a before-state for the exact things Batch A is meant to fix.

### Actions

1. On a live or realistic SQLite DB, capture:
   - `PRAGMA index_list('System')`
   - `EXPLAIN QUERY PLAN SELECT system_id FROM System WHERE name = 'Sol';`

2. On a MariaDB database used in practice, capture:
   - `SHOW INDEX FROM System;`

3. If evaluating the optional composite index, also capture the relevant station lookup query plan and timing.

### Outputs

- one saved text or Markdown note with before-state evidence

### Definition of done

- you can prove whether `idx_system_by_name` is missing where it matters
- if the optional composite index is under consideration, you have before-state evidence for that too

### Safe stop point

- evidence saved, no code touched yet

## Task 2: Update Fresh-Build Schema Sources

### Goal

Make new databases come out right before worrying about upgrades.

### Required files

- [TradeDangerous.sql](/D:/Git/Trade-Dangerous/tradedangerous/templates/TradeDangerous.sql)

### Actions

1. Add `idx_system_by_name` to the `System` section of the SQLite template.
2. If the optional composite index is in scope, add it to the `Station` section too.

### Important note

For `idx_system_by_name`, [orm_models.py](/D:/Git/Trade-Dangerous/tradedangerous/db/orm_models.py) already declares the index, so this task is mostly about bringing the SQLite template up to the same public contract.

### Definition of done

- fresh SQLite rebuilds create the agreed Batch A indexes automatically

### Safe stop point

- fresh-build schema updated, no upgrade path yet

## Task 3: Implement Public Index Reconciliation Helper

### Goal

Upgrade existing databases in place without rebuilding them.

### Required files

- [lifecycle.py](/D:/Git/Trade-Dangerous/tradedangerous/db/lifecycle.py)

### Actions

1. Add one narrowly scoped helper responsible only for Batch A public indexes.
2. Make it backend-aware but policy-light.
3. Inspect existing indexes before attempting creation.
4. Create missing Batch A indexes only.
5. Make it idempotent.
6. Return or log what it did.

### Suggested helper responsibilities

- determine current backend
- determine required Batch A index list
- inspect whether each required index exists
- create only missing ones
- report created versus already present

### Explicitly do not do this

- do not create unrelated ORM-only tables
- do not reconcile every metadata/template mismatch in the repo
- do not add speculative future search structures

### Definition of done

- helper can be called repeatedly with no duplicate-creation failure
- helper scope remains limited to Batch A public indexes

### Safe stop point

- helper exists and can be exercised directly in isolation

## Task 4: Wire Reconciliation Into The Central Lifecycle Path

### Goal

Ensure normal runs, GUI usage, and import/plugin flows all converge on the same schema reconciliation behavior.

### Required files

- [tradedb.py](/D:/Git/Trade-Dangerous/tradedangerous/tradedb.py)

### Actions

1. Call the reconciliation helper from `TradeDB.reloadCache()` after `ensure_fresh_db(...)` returns.
2. Make sure it runs for both SQLite and MariaDB.
3. Keep logging clear enough to show whether indexes were created or already present.

### Why here

This is the cleanest single choke point already used by normal application flows.

### Definition of done

- one central path reconciles Batch A indexes for both fresh and existing databases

### Safe stop point

- central call wired, but verification not yet complete

## Task 5: Handle Optional Composite Index If Approved

Skip this whole task if the optional composite index was not included in Batch A.

### Required files

- [TradeDangerous.sql](/D:/Git/Trade-Dangerous/tradedangerous/templates/TradeDangerous.sql)
- [orm_models.py](/D:/Git/Trade-Dangerous/tradedangerous/db/orm_models.py)
- [lifecycle.py](/D:/Git/Trade-Dangerous/tradedangerous/db/lifecycle.py)

### Actions

1. Add the index to the SQLite template.
2. Add the index to ORM metadata so MariaDB resets stay aligned.
3. Add the index to the reconciliation helper’s required public index set.
4. Re-run the same fresh-build and existing-DB checks for both backends.

### Definition of done

- both backends expose the same optional Batch A composite index
- inclusion is documented in release notes before release

## Task 6: Verify Fresh SQLite Build

### Goal

Prove a scratch SQLite DB built from the canonical template has the correct Batch A index set.

### Actions

1. Build or reset a scratch SQLite DB from the template.
2. Run:

```sql
PRAGMA index_list('System');
```

3. If optional composite index is included, also run:

```sql
PRAGMA index_list('Station');
```

### Expected result

- `idx_system_by_name` exists
- optional composite index exists only if it was approved

### Definition of done

- fresh SQLite build matches Batch A contract exactly

## Task 7: Verify Existing SQLite Upgrade

### Goal

Prove an existing SQLite DB missing the index is upgraded in place.

### Actions

1. Use a SQLite DB that predates the change or temporarily remove the target index on a scratch copy.
2. Run the normal app path that reaches `reloadCache()`.
3. Confirm the index appears afterward.
4. Run:

```sql
PRAGMA index_list('System');
EXPLAIN QUERY PLAN SELECT system_id FROM System WHERE name = 'Sol';
```

### Expected result

- index appears without full rebuild
- exact system lookup no longer uses a full table scan

### Definition of done

- existing SQLite upgrade path is proven and repeatable

## Task 8: Verify Fresh MariaDB Reset

### Goal

Prove a fresh metadata-driven MariaDB reset exposes the same public Batch A index contract.

### Actions

1. Reset a scratch MariaDB database through the normal reset path.
2. Run:

```sql
SHOW INDEX FROM System;
```

3. If optional composite index is included, also inspect `Station` indexes.

### Expected result

- MariaDB fresh reset includes all agreed Batch A indexes

### Definition of done

- fresh MariaDB reset aligns with Batch A contract

## Task 9: Verify Existing MariaDB Upgrade

### Goal

Prove existing MariaDB databases also gain the missing index in place.

### Actions

1. Use an existing MariaDB database that lacks the index, or create a scratch copy in that state.
2. Run the normal app path that reaches `reloadCache()`.
3. Inspect indexes afterward.
4. Re-run the same path and confirm it is idempotent.

### Expected result

- index created once
- repeated runs do not try to recreate it

### Definition of done

- MariaDB existing-DB upgrade behavior is proven and idempotent

## Task 10: Add Verification Coverage

### Goal

Leave behind a repeatable check instead of relying on memory.

### Options

Pick whichever is realistic for the repo and your time:

1. add automated tests under `tests/`
2. add a narrow verification helper or script
3. add a documented manual verification checklist committed to `docs/`

### Minimum acceptable coverage

- fresh SQLite build shows expected indexes
- existing SQLite upgrade adds missing index in place
- MariaDB reset path exposes the same public index set

### Better coverage

- explicit cross-backend parity assertion for the Batch A index set

### Definition of done

- someone else can verify Batch A without reverse-engineering your intentions

## Task 11: Re-Capture After-State Evidence

### Goal
n
Prove Batch A delivered what it set out to do.

### Actions

1. Re-run the baseline checks from Task 1.
2. Save after-state outputs alongside the before-state outputs.
3. If the optional composite index was included, save its before/after evidence too.

### Definition of done

- there is a documented before/after record for the Batch A schema change

## Task 12: Prepare Downstream Release Packaging

### Goal

Make the release easy to consume for people depending on schema stability.

### Required outputs

1. short release note
2. longer release note
3. exact list of Batch A indexes included
4. explicit statement that no table or column shape changed
5. explicit statement that this is the planned early schema batch

### Definition of done

- downstream consumers know exactly what changed and what did not

## Suggested Commit / PR Slice Order

If you want to avoid one giant blob, this is a sensible order:

1. baseline evidence only
2. template update for fresh SQLite builds
3. lifecycle reconciliation helper
4. `reloadCache()` wiring
5. verification/test coverage
6. release note/docs update

If the optional composite index is approved, either:

- include it in slice 2 through 5 as part of the same branch and release
- or exclude it entirely from Batch A

Do not ship `idx_system_by_name` first and then drip out the optional composite index later unless you are willing to call that a second schema batch.

## Good Stop Points

These are safe places to pause without leaving the codebase conceptually muddled:

- after Task 1 baseline evidence
- after Task 2 fresh-build template update
- after Task 3 isolated reconciliation helper
- after Task 4 central lifecycle wiring
- after Task 7 SQLite verification
- after Task 9 MariaDB verification

## Stop And Reassess If

Pause if any of the following happens:

1. the reconciliation helper starts growing into a general schema-repair engine
2. MariaDB and SQLite cannot be made to expose the same Batch A public index set without unrelated cleanup
3. the optional composite index case is still ambiguous when you are otherwise ready to ship Batch A
4. someone starts trying to piggyback unrelated schema changes onto the release
5. the expected SQLite query plan does not improve after `idx_system_by_name` is present

## Definition Of Done For Batch A

Batch A is done only when all of the following are true:

1. Batch A scope is frozen and documented
2. fresh SQLite builds include the agreed index set
3. existing SQLite databases gain the agreed index set in place
4. fresh MariaDB resets expose the same agreed index set
5. existing MariaDB databases gain the agreed index set in place
6. exact system lookup on SQLite no longer shows a full table scan
7. release notes for downstream consumers are ready
8. schema is frozen again after release

## Recommended Immediate Next Five Actions

If you want the short version, do these next:

1. lock Batch A scope to `idx_system_by_name` only unless the optional index is already proven
2. capture the before-state query plan and index list on live SQLite
3. update [TradeDangerous.sql](/D:/Git/Trade-Dangerous/tradedangerous/templates/TradeDangerous.sql)
4. add the Batch A public-index reconciliation helper in [lifecycle.py](/D:/Git/Trade-Dangerous/tradedangerous/db/lifecycle.py)
5. call it from `TradeDB.reloadCache()` in [tradedb.py](/D:/Git/Trade-Dangerous/tradedangerous/tradedb.py)

That gets you from theory to real implementation with minimal wandering.

