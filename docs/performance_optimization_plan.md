# Trade Dangerous Performance Optimization Plan

Date: 2026-03-23
Status: Draft working plan
Audience: Maintainers and future contributors

## Purpose

This document lays out a step by step plan to improve the user-visible speed of Trade Dangerous without breaking the behavior that existing users, scripts, and workflows depend on.

The plan assumes the current live SQLite database can be larger than 2GB, so all findings from the shipped fixture database must be treated as shape-of-cost evidence, not production timing truth.

## Executive Summary

The main speed problem is not one bug. It is a stack of repeated setup costs:

1. Many commands still build a full legacy `TradeDB` object graph every run.
2. `TradeDB.load()` hydrates more data than many commands need.
3. `_loadStations()` performs a second pass over `StationItem` just to compute station summary data.
4. `TradeCalc.__init__()` performs another full market scan and rebuilds Python-side buy/sell maps every run.
5. The ORM migration path exists, but it is not yet the default execution path for most commands.
6. Name lookup and search are not yet strong enough to replace `TradeDB` broadly, and at least one important supporting index appears to be missing from the shipped SQLite schema.
7. The GUI currently inherits the same cold-start behavior as the CLI.

Bottom line:

- The route math in `tradecalc.py` is real work and some of it will always be expensive.
- The larger problem is repeated full-dataset reshaping before the route math even starts.
- The highest-value work is therefore to remove repeated preload and scan work, not to start by micro-optimizing the route scoring logic.

## Scope

This plan covers:

- CLI startup and command execution speed
- GUI execution speed
- legacy `TradeDB` preload behavior
- resolver and lookup design
- `TradeCalc` data preload behavior
- schema and indexing work that directly supports faster reads

This plan does not primarily cover:

- listener/server ingestion
- journal integration
- web deployment
- cosmetic GUI improvements

## Constraints

1. Behavior parity matters.
   Existing lookup semantics, ambiguity handling, partial matching, and script compatibility are not optional nice-to-haves.

2. SQLite remains important.
   Even though MariaDB support now exists, many end users will continue using SQLite locally.

3. Performance work must be measured on realistic data.
   The shipped fixture DB is useful for identifying scaling paths, but not for accepting or rejecting changes for production use.

4. Big-bang rewrites should be avoided.
   The safest path is staged replacement behind compatibility shims.

## Observed Bottlenecks

### 1. Full `TradeDB` construction is still the default command path

In the CLI, a `TradeDB` object is always constructed. If a command sets `wantsTradeDB=True`, a full legacy load follows.

Relevant code:

- `tradedangerous/cli.py`
- `tradedangerous/commands/commandenv.py`
- `tradedangerous/tradedb.py`

Observed shape:

- `trade` avoids full `TradeDB.load()` and is therefore materially leaner.
- `local`, `market`, `buy`, `sell`, `nav`, `olddata`, and `rares` still sit on the full-load path.

Impact:

- Cold start dominates commands whose actual business logic is otherwise fairly small.
- Commands that already query SQL still pay a large Python object preload cost first.

### 2. `TradeDB.load()` hydrates the entire legacy world even when not needed

`TradeDB.load()` always loads:

1. systems
2. stations
3. categories
4. items

That is appropriate for old code that expects a fully populated in-memory mirror. It is excessive for commands that only need:

- a system lookup
- station metadata
- a small SQL query over one table

Impact:

- User pays for categories and items even when the command never uses them.
- User pays for station summary hydration even when the command only needs routing geometry.

### 3. `_loadStations()` has a hidden second cost: station trade summaries

Station shell load is only part of `_loadStations()`. It also aggregates `StationItem` to compute `itemCount` and average item age per station.

Why this matters:

- That second pass scales with the size of market data.
- On a 2GB SQLite DB, this is likely a substantial part of startup.

This is especially important because many commands only need one of:

- station shell data
- trading summary data

but not both.

### 4. `TradeCalc.__init__()` appears to be the major `run` setup cost

The route algorithm itself is not the only cost in `run`.

Before serious route evaluation begins, `TradeCalc.__init__()`:

1. scans `StationItem`
2. applies demand and supply filters
3. parses timestamps row by row in Python
4. builds `stationsBuying` and `stationsSelling`
5. builds helper sets and maps used later by route evaluation

This is a linear scan and reshape pass over market data.

That is not fake work, but it is setup work, and it happens every run.

### 5. The resolver/search path is not yet good enough to become the universal front door

`TradeORM` is the right architectural direction, but the current lookup implementation still has three weaknesses:

1. it falls back to wildcard `%term%` searches
2. it materializes all matches with `.all()`
3. its performance depends heavily on schema/index quality

This means the resolver is promising but not yet strong enough to replace `TradeDB` everywhere without care.

### 6. Missing or mismatched index support is likely hurting lookup performance

The ORM model defines `idx_system_by_name`, but the shipped SQL template appears not to create it.

Implication:

- Exact `System.name = ?` lookups may still be table scans on SQLite.
- Any future ORM-first resolver path is handicapped until schema reality matches the intended model.

### 7. GUI execution currently inherits the same backend costs

The NiceGUI adapter still constructs `TradeDB` for each command execution.

Implication:

- A more pleasant interface does not by itself improve backend response time.
- GUI users can still feel the same repeated cold-start tax.

## Evidence Snapshot

### Code-path evidence

The following files are the key hotspots:

- `tradedangerous/cli.py`
- `tradedangerous/commands/commandenv.py`
- `tradedangerous/tradedb.py`
- `tradedangerous/tradecalc.py`
- `tradedangerous/tradeorm.py`
- `tradedangerous/guiapp/td_exec.py`

### Fixture-only timing evidence

The shipped fixture DB is tiny compared to production, but it still reveals which paths scale with data.

Fixture size observed locally:

- `System`: 96 rows
- `Station`: 458 rows
- `Item`: 218 rows
- `Category`: 16 rows
- `StationItem`: 37,562 rows

Representative timings on that fixture:

- `TradeDB(load=True)`: about 30ms average
- `TradeORM()`: about 2ms average
- `trade` command: about 10ms average
- sample `run`: about 156ms total

Isolated breakdown from the sample `run` on the fixture:

- `TradeDB.load`: about 32ms
- `TradeCalc.__init__`: about 102ms
- `TradeCalc.getBestHops` across the calls made in that case: less than 1ms

Important caveat:

- Do not over-read those numbers.
- The production DB is orders of magnitude larger.
- The value is not the absolute milliseconds. The value is that the expensive parts are the data preload and reshape phases.

## Guiding Principles

1. Remove repeated full-dataset setup before touching complex route math.
2. Preserve user-facing lookup behavior while changing internals.
3. Prefer staged replacement over heroic rewrites.
4. Measure cold and warm behavior separately.
5. Optimize by capability, not by command name alone.
6. Let the database do indexed lookups and filtering wherever practical.
7. Keep the legacy compatibility layer until all critical callers have migrated.

## Work Plan

## Phase 0: Establish Production-Relevant Baselines

This phase should happen before any major rewrite work lands.

### Goal

Build a trustworthy before/after measurement harness on a live-sized database.

### Steps

1. Add timing probes around the major stages of command execution.
   Measure:
   - command parse
   - preflight
   - `TradeDB` construction
   - `TradeDB.load`
   - `_loadSystems`
   - `_loadStations`
   - `_loadCategories`
   - `_loadItems`
   - `TradeCalc.__init__`
   - `TradeCalc.getBestHops`
   - total command time

2. Record cold and warm timings separately.
   Cold means a fresh process and no useful OS page cache assumption.
   Warm means repeated command execution where file cache may help.

3. Benchmark representative commands on the live SQLite DB.
   Minimum recommended set:
   - `local`
   - `market`
   - `buy`
   - `sell`
   - `nav`
   - `rares`
   - `trade`
   - at least three `run` command shapes:
     - short local route
     - typical user route
     - wide search / high-hop route

4. Capture memory usage as well as time.
   Suggested metrics:
   - resident set size after `TradeDB.load`
   - resident set size after `TradeCalc.__init__`
   - peak memory during a `run`

5. Capture SQL query plans for likely resolver queries.
   Minimum checks:
   - exact `System.name = ?`
   - exact `Station.name = ?`
   - system+station lookup
   - partial station lookup

6. Save baseline results in a machine-readable format.
   Suggested format:
   - JSON per benchmark run
   - one Markdown summary for humans

### Acceptance Criteria

- We can say with evidence which commands are preload-bound versus algorithm-bound.
- We can compare future changes against a stable baseline on the live DB.

## Phase 1: Low-Risk Schema and Measurement Hygiene

This phase aims for immediate structural wins without changing behavior.

### Goal

Fix obvious indexing deficits and make performance visible.

### Steps

1. Add a proper migration path for `idx_system_by_name`.
   This should exist in both:
   - the canonical SQLite SQL template
   - ORM metadata
   - any DB update path for existing users

2. Verify whether `Station(system_id, name)` needs a composite index.
   Why:
   - resolver lookups of `system/station`
   - station name lookup within a known system

3. Verify whether additional resolver-supporting indexes are needed.
   Candidates to evaluate:
   - normalized system name
   - normalized station name
   - `(system_id, name)` on `Station`

4. Confirm that current `StationItem` indexes are sufficient for:
   - item-centric reads
   - station-centric reads
   - age filtering

5. Add optional debug logging that prints stage timings.
   This must be cheap when disabled.

### Acceptance Criteria

- Exact system lookup is indexed on SQLite.
- We can inspect query plans and confirm expected index use.
- Developers can see where time is being spent without external profilers.

## Phase 2: Build a First-Class Resolver Layer

This is the most important architectural phase.

### Goal

Create a lightweight lookup service that can replace `TradeDB` for argument resolution and basic command setup.

### Resolver Responsibilities

The resolver must preserve behavior for:

- system lookup
- station lookup
- place lookup
- item lookup where needed
- ambiguity handling
- helpful candidate output
- duplicate system disambiguation with `@N`
- support for:
  - `SYS`
  - `STN`
  - `SYS/STN`
  - `/STN`

### Steps

1. Define a small resolver interface.
   Example responsibilities:
   - `lookup_system(name)`
   - `lookup_station(name)`
   - `lookup_place(name)`
   - `lookup_item(name)`
   - optional lightweight return mode:
     - IDs only
     - minimal dataclass
     - ORM entity

2. Decide how matching should work before implementation.
   Write down exact lookup precedence:
   - exact normalized match
   - exact raw match
   - prefix match
   - whole-word or token match
   - fallback fuzzy search only if still needed

3. Avoid `%term%` as the default lookup path.
   Leading-wildcard scans do not scale well.

4. Implement normalization once, not ad hoc in several layers.
   Candidate approaches:
   - normalized search columns
   - dedicated search helper table
   - backend-specific optional strategy if needed later

5. Add a parity test suite against current `TradeDB` behavior.
   Include:
   - exact matches
   - partial matches
   - ambiguous names
   - duplicate system names with `@N`
   - station-only and system+station forms
   - bad inputs

6. Make the resolver available to both CLI and GUI.

### Acceptance Criteria

- Valid argument resolution no longer requires full `TradeDB.load`.
- Resolver behavior matches legacy expectations closely enough to replace `TradeDB` for command setup.

## Phase 3: Change Execution Flow to Use Resolver Before Heavy Load

### Goal

Make valid command lines cheap to validate, not just invalid ones.

### Current State

`preflight` catches obvious bad syntax and option relationships. That is useful, but it does not help valid commands.

### Steps

1. Introduce a capability-based execution model.
   Replace the coarse idea of `wantsTradeDB` with something closer to:
   - needs resolver
   - needs systems/stations shell
   - needs item catalog
   - needs full trade graph

2. Change `CommandEnv` to resolve `--from`, `--to`, `--near`, `--avoid`, and `--via` through the resolver when possible.

3. Ensure command validation and argument normalization happen before any full `TradeDB` hydration.

4. Keep `TradeDB(load=False)` as a temporary compatibility shim only where absolutely necessary.

5. Mirror the same flow in the GUI executor.

### Acceptance Criteria

- Valid commands that only need lookup no longer incur a full `TradeDB.load`.
- CLI and GUI follow the same resolver-first flow.

## Phase 4: Migrate Commands Off Full `TradeDB` in Descending ROI Order

This phase should be staged command by command.

### Migration Order

Recommended order:

1. `local`
2. `market`
3. `buy`
4. `sell`
5. `olddata`
6. `nav`
7. `rares`

### Why this order

- These commands have high user visibility.
- Several already do a good part of their work in SQL.
- Their dependency on full `TradeDB` is often lookup and rendering support, not true algorithmic necessity.

### Command Notes

#### `local`

Current pain:

- full `TradeDB` load
- then Python-side distance and station filtering over hydrated objects

Plan:

1. resolve origin system via resolver
2. do system range search in SQL or a lean geometry helper
3. filter station flags in SQL where practical
4. only hydrate minimal output rows

This command is one of the best near-term wins.

#### `market`

Current pain:

- still depends on `startStation` resolution through `TradeDB`
- uses `itemByID` and station wrappers for rendering

Plan:

1. resolve station via resolver
2. query station market rows directly
3. map item names via lean item catalog access or lightweight join
4. remove dependency on fully built `itemByID` where possible

#### `buy` and `sell`

Current pain:

- item lookup still tied to legacy item/category objects
- output still depends on `stationByID`

Plan:

1. move item/category lookup into resolver or item service
2. return only matching stations from SQL
3. attach minimal station metadata needed for render
4. keep sorting behavior identical

#### `olddata`

Current pain:

- already SQL-heavy, but still leans on `TradeDB` for station metadata

Plan:

1. keep SQL aggregation
2. resolve near-system through resolver
3. hydrate only minimal station metadata for rows returned

#### `nav`

Current pain:

- truly needs route geometry
- still benefits from system/station shell objects

Plan:

1. separate route geometry support from the rest of `TradeDB`
2. only load systems and station shell data
3. do not load item/category data for `nav`

#### `rares`

Current pain:

- small command, still full-load bound

Plan:

1. resolve near-system through resolver
2. query rare rows with direct joins
3. attach only minimal station shell data

### Acceptance Criteria

- Each migrated command demonstrates:
  - lower cold-start time
  - no behavior regression
  - no mandatory full `TradeDB` hydration

## Phase 5: Split `TradeDB` into Load Capabilities

### Goal

Turn `TradeDB` from "always preload the world" into "load only what the caller actually needs."

### Steps

1. Break `TradeDB.load()` into explicit components.
   Suggested split:
   - `load_systems()`
   - `load_station_shell()`
   - `load_station_summaries()`
   - `load_categories()`
   - `load_items()`

2. Make the stellar grid remain lazy.
   This is already partly true and should stay that way.

3. Separate station shell data from station trading summary data.
   This is important because:
   - `nav` needs shell data
   - `olddata` and `local --trading` may need summary data
   - not every command needs both

4. Audit wrapper dependencies.
   Identify callers that need:
   - only IDs
   - only names and coordinates
   - full wrapper objects

5. Keep `TradeDB` as a compatibility layer until migration is complete.

### Acceptance Criteria

- Commands can ask for only the subset of legacy data they need.
- The old monolithic `load()` path becomes exceptional, not default.

## Phase 6: Reduce `TradeCalc` Setup Cost Before Touching Route Math

This is the highest-value `run` optimization phase.

### Goal

Make `TradeCalc.__init__()` cheaper by reducing the amount of market data it scans and reshapes.

### Observed Issue

`TradeCalc.__init__()` currently does a broad `StationItem` scan and Python-side transformation every run.

### Steps

1. Use `restrict_station_ids` for real.
   This hook already exists but does not appear to be used by `run`.

2. Derive candidate station sets before building `TradeCalc`.
   Candidate derivation can come from:
   - origin station
   - destination station or destination systems
   - `--start-jumps`
   - `--end-jumps`
   - `--via`
   - pad, planetary, fleet, odyssey, and max-ls constraints

3. Limit `StationItem` preload to only relevant stations when the command shape allows it.

4. Push more filtering into SQL before rows hit Python.
   Current examples already present:
   - supply threshold
   - demand threshold
   - age threshold
   - item filters

5. Stop parsing timestamps in Python if practical.
   Hypothesis:
   - computing epoch or age in SQL will be cheaper than calling `parse_ts` per row.
   This must be verified on both SQLite and MariaDB.

6. Consider chunked row processing if memory becomes a problem.
   SQLAlchemy guidance supports Core and streaming/chunking approaches for large result sets.

7. Re-measure after each narrowing change before attempting algorithm changes.

### Acceptance Criteria

- `TradeCalc.__init__()` time drops materially on the live DB.
- The amount of `StationItem` data scanned per run is reduced where the command allows it.

## Phase 7: Only Then Revisit Route Algorithm Internals

### Goal

Optimize route evaluation only after setup costs have been reduced enough that the remaining bottleneck is genuinely the route computation itself.

### Why this is later

The route algorithm does real work. It is allowed to be expensive. It should not be the first target while repeated setup scans dominate.

### Steps

1. Re-profile after Phase 6.
2. If `getBestHops()` is now dominant on production data, inspect:
   - destination iteration volume
   - repeated `distanceTo` calls
   - repeated station suitability checks
   - item fit function cost
   - route pruning effectiveness

3. Look for repeated work that can be memoized safely within one run.

4. Consider precomputed destination candidate lists for common constraint sets if profiling shows repeated graph traversal overhead.

5. Only introduce more aggressive changes if benchmarked wins are clear.

### Acceptance Criteria

- Any algorithmic optimization is justified by live-profile evidence, not instinct.

## Phase 8: Resolver/Search Improvements Beyond Parity

This is optional until the earlier phases are done.

### Goal

Improve lookup quality and speed beyond the current legacy behavior.

### Candidate Work

1. Add normalized search columns.
2. Support indexed prefix search.
3. Consider tokenized search support.
4. Evaluate a dedicated search module or table.
5. Only consider backend-specific full-text search later if absolutely needed.

### Important Constraint

Search enhancements must not break current user expectations unless they clearly improve them and are documented.

## Phase 9: GUI Session Optimization

### Goal

Recover some of the original "load once, answer many questions" intent inside the GUI process.

### Steps

1. Keep a long-lived resolver instance in the GUI process.
2. Optionally keep a long-lived lightweight station/system cache for GUI-driven commands.
3. Invalidate caches after:
   - import
   - update
   - explicit rebuild
   - database file change detection

4. Be conservative with stale data rules.

### Acceptance Criteria

- Repeated GUI actions feel faster than repeated CLI cold starts.
- Cache invalidation is explicit and reliable.

## Verification Strategy

Every phase should carry its own verification burden.

### Functional Verification

1. Existing tests must pass.
2. Add parity tests for resolver behavior.
3. Add regression tests for:
   - ambiguity output
   - duplicate system `@N`
   - station/system shortcut forms
   - command output ordering

### Performance Verification

1. Compare cold-start times before and after each phase.
2. Compare warm times separately.
3. Track memory alongside time.
4. Record rows scanned where possible.
5. Use live DB baselines, not only fixture DB.

### Rollout Safety

1. Land changes behind flags where sensible.
2. Migrate command by command.
3. Keep legacy path available until parity is proven.
4. Do not remove `TradeDB` as a compatibility shim prematurely.

## Recommended Implementation Order

If only one optimization stream can be worked at a time, do this:

1. Phase 0: production baselines and instrumentation
2. Phase 1: schema/index hygiene
3. Phase 2: resolver implementation
4. Phase 3: resolver-first execution flow
5. Phase 4: migrate `local`
6. Phase 4: migrate `market`, `buy`, `sell`
7. Phase 5: split `TradeDB` capabilities
8. Phase 6: reduce `TradeCalc.__init__` preload scope
9. Phase 4: migrate `nav`, `olddata`, `rares`
10. Phase 7: route algorithm optimization only if still warranted
11. Phase 9: GUI session caching

## First Concrete Deliverables

The best immediate engineering tasks are:

1. add timing instrumentation around CLI, `TradeDB.load`, and `TradeCalc`
2. add and migrate `idx_system_by_name`
3. write a resolver parity test matrix
4. implement a first resolver for system/station/place lookups
5. switch `local` to resolver plus direct-query execution
6. wire `restrict_station_ids` into `run`

That sequence should produce visible wins without needing a dangerous rewrite.

## Risks

### Risk 1: Behavior regressions in lookup semantics

Mitigation:

- resolver parity test suite
- staged rollout
- preserve ambiguity text where possible

### Risk 2: ORM migration that is slower than legacy behavior

Mitigation:

- fix indexes first
- prefer exact and prefix matching over wildcard scans
- profile query plans on SQLite and MariaDB

### Risk 3: Partial migration leaves the codebase in an awkward hybrid state

Mitigation:

- define clear interfaces
- migrate whole command execution paths, not isolated helper fragments

### Risk 4: Over-optimizing the route algorithm before setup costs are removed

Mitigation:

- keep Phase 7 after Phase 6
- require live-profile evidence

## Explicit Non-Recommendations

The following are not recommended as first moves:

1. rewriting `tradecalc.py` from scratch
2. trying to make every command fully async
3. replacing SQLite for end users as a prerequisite to better speed
4. removing `TradeDB` outright before compatibility seams exist
5. attempting one massive ORM conversion branch across all commands at once

## Appendix A: Specific Hypotheses To Verify

H1. On the live 2GB SQLite DB, `TradeCalc.__init__()` is one of the top two contributors to `run` latency.

H2. Exact system lookup is slower than it should be on SQLite because `idx_system_by_name` is missing from the shipped schema.

H3. `local` can be made significantly faster without touching `tradecalc.py`, simply by removing full `TradeDB` hydration.

H4. A command-by-command migration yields more user-visible benefit sooner than any early deep work inside route scoring.

H5. SQL-side timestamp handling will be measurably cheaper than Python-side `parse_ts` for large `StationItem` scans.

## Appendix B: Useful Reference Files

- `tradedangerous/cli.py`
- `tradedangerous/commands/commandenv.py`
- `tradedangerous/tradedb.py`
- `tradedangerous/tradecalc.py`
- `tradedangerous/tradeorm.py`
- `tradedangerous/commands/trade_cmd.py`
- `tradedangerous/guiapp/td_exec.py`
- `tradedangerous/templates/TradeDangerous.sql`
- `tradedangerous/db/orm_models.py`

## Appendix C: External Documentation Used As Sanity Checks

- SQLAlchemy performance FAQ
- SQLAlchemy large result set performance examples

These were used only as supporting reference for general ORM/Core performance guidance, not as a substitute for profiling Trade Dangerous itself.
