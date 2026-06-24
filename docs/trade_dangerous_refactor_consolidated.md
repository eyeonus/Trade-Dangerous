# Trade Dangerous Refactor — Consolidated Project Context and Execution Plan

> Status: superseded for live planning; see `REFACTOR_PROGRESS.md` for current state.

Status: canonical consolidated worker context  
Generated: 2026-05-07  
Scope: legacy cleanup, ORM-first performance refactor, and schema Batch A context  
Working repo: `Tromador/Trade-Dangerous`  
Working line: `release/v1` on the fork

This document condenses and supersedes the following planning documents for normal worker onboarding:

- `docs/final_implementation_plan.md`
- `docs/performance_optimization_plan.md`
- `docs/performance_tactical_backlog.md`
- `docs/schema_batch_a_checklist.md`
- `docs/schema_batch_a_spec.md`
- `docs/schema_impact_matrix.md`

The original files remain useful as audit/history, but this file should be the first-read document for new worker sessions.

## 0. Precedence Notes

Where the original documents disagree, use this precedence:

1. Later verified state beats earlier planning intent.
2. `schema_batch_a_spec.md` is authoritative for Batch A because it records the verified 2026-04-17 outcome.
3. Earlier Batch A checklist/matrix instructions about in-place upgrade are historical/superseded unless explicitly revived.
4. Repo state beats all documents if code and docs diverge; stop and report the divergence rather than guessing.

Important resolved conflict:

- Earlier docs planned or recommended an in-place index upgrade path for existing databases.
- The later verified Batch A policy is rebuild/reset only. Existing DBs are not upgraded in place for Batch A.
- Earlier docs treated `idx_station_by_system_name` as optional/prove-first. The later verified Batch A contract includes it.

## 1. One-Screen Summary For Workers

The project is a staged refactor of Trade Dangerous intended to improve user-visible performance without breaking existing CLI, GUI, script, and packaging behaviour.

The central diagnosis is that many commands pay repeated full-dataset setup costs before doing relatively small pieces of work. The worst pattern is full legacy `TradeDB` hydration, followed by additional scans and Python-side reshaping, even for commands that only need lookup, station metadata, or a small SQL query.

The strategy is:

1. Measure first: phase timings, benchmark commands, live-sized DB baselines, query plans.
2. Keep SQLite as the primary performance truth for end users, while retaining MariaDB support.
3. Use the ORM migration path incrementally, not as a big-bang rewrite.
4. Build a resolver layer that can perform argument lookup without full `TradeDB.load()`.
5. Move commands off full preload one at a time.
6. Shrink `TradeDB` into a compatibility shim, not a central always-load-the-world object.
7. Reduce `TradeCalc.__init__()` setup cost before touching route algorithm internals.
8. Use GUI session-scope reuse where appropriate; keep CLI execution short-lived and stateless.

Current Batch A schema state:

- Batch A is verified and closed as a narrow additive read-performance schema release.
- Public index set: `idx_system_by_name` on `System(name)` and `idx_station_by_system_name` on `Station(system_id, name)`.
- Supported rollout is rebuild/reset via clean import, not in-place upgrade.
- No tables, columns, keys, row semantics, or importer payload formats changed.
- After Batch A, schema should remain frozen unless a later packet genuinely cannot proceed without schema work.

## 2. Working Model

All refactor work lands on the fork:

- Canonical upstream: `eyeonus/Trade-Dangerous:release/v1`
- Working repo: `Tromador/Trade-Dangerous:release/v1`

The fork isolates refactor work from the live upstream branch. Do not create a second refactor branch inside the fork unless a concrete problem proves it necessary.

Future workers should establish, before coding:

1. Which checkpoint and subtask is in scope.
2. Which files are already modified on the fork.
3. Whether the task is design-only, code, tests, docs, release packaging, or some combination.
4. Exact acceptance criteria for the subtask.
5. The rollback point.

Every paused task should end with a succession/handoff packet using `docs/SESSION_HANDOFF_TEMPLATE.md` or its current equivalent.

## 3. Product and Engineering Constraints

These are fixed unless later evidence forces an explicit review.

### Product constraints

- CLI and GUI are equally important.
- `pip install` remains a first-class distribution method.
- Windows packaged `.exe` / installer support remains first-class.
- `python tradegui.py` must remain viable anywhere the stack supports it.
- Core engine stays OS-agnostic and frontend-agnostic.
- SQLite remains the primary performance truth for most end users.
- MariaDB support must continue to work, but must not distort design for the SQLite majority.
- No big-bang rewrite.
- Do not remove `TradeDB` until replacement seams are proven.

### Behaviour constraints

- Existing lookup semantics, ambiguity handling, partial matching, duplicate handling, and script compatibility matter.
- Preserve lookup behaviour unless a change is explicitly intentional, tested, and documented.
- Do not remove legacy paths until the replacement path has parity tests and benchmark evidence.
- CLI and GUI must not drift into different backend semantics.

### Performance constraints

- The live SQLite DB can be larger than 2GB.
- The shipped fixture DB is useful for shape-of-cost evidence, not production timing truth.
- Measure cold and warm behaviour separately.
- Track memory as well as time where practical.
- Do not optimise route maths before setup cost has been measured down to a believable level.

### Schema constraints

- Do schema work in coherent batches.
- Do not drip tiny schema changes downstream unless unavoidable.
- After Batch A, treat the roadmap as schema-neutral by default.
- If later resolver/search work needs search columns or helper tables, handle that as a separate Batch B schema event.

## 4. Locked Design Decisions

Adopted decisions:

- Use the Option 1 ORM migration strategy.
- Shrink `TradeDB` into a compatibility shim instead of deleting it up front.
- Ship one narrow first schema batch for additive read-performance indexes.
- Remove `Added` completely.
- Remove `RareItem` completely.
- Represent rarity through `Item.rare_station_id IS NOT NULL`.
- Do not persist `is_rare`; expose it only as Python convenience logic if useful.
- Migrate commands one command at a time.
- Attack `TradeCalc` setup cost before route maths.
- Give the GUI session-scope reuse where appropriate.
- Keep the CLI short-lived and stateless.

## 5. Current Performance Diagnosis

The speed problem is not one bug. It is a stack of repeated setup costs:

1. Many commands still build a full legacy `TradeDB` object graph every run.
2. `TradeDB.load()` hydrates more data than many commands need.
3. `_loadStations()` performs a second pass over `StationItem` to compute station summary data.
4. `TradeCalc.__init__()` performs another full market scan and rebuilds Python-side buy/sell maps every run.
5. The ORM path exists but is not yet the default for most commands.
6. Name lookup/search must become strong enough before it can replace `TradeDB` broadly.
7. The GUI currently inherits the same cold-start costs as the CLI.

Bottom line:

- Route maths in `tradecalc.py` is real work and will always have some cost.
- The bigger immediate problem is repeated full-dataset preload and reshape before route maths starts.
- Highest-value work is removing repeated preload/scan work, not early micro-optimisation inside route scoring.

### Hotspot code paths

Primary files:

- `tradedangerous/cli.py`
- `tradedangerous/commands/commandenv.py`
- `tradedangerous/tradedb.py`
- `tradedangerous/tradecalc.py`
- `tradedangerous/tradeorm.py`
- `tradedangerous/guiapp/td_exec.py`

### Fixture-only evidence retained for shape, not absolute timing

Observed fixture size:

- `System`: 96 rows
- `Station`: 458 rows
- `Item`: 218 rows
- `Category`: 16 rows
- `StationItem`: 37,562 rows

Representative fixture timings:

- `TradeDB(load=True)`: about 30 ms average
- `TradeORM()`: about 2 ms average
- `trade` command: about 10 ms average
- sample `run`: about 156 ms total

Sample `run` breakdown on fixture:

- `TradeDB.load`: about 32 ms
- `TradeCalc.__init__`: about 102 ms
- `TradeCalc.getBestHops` across the calls made: less than 1 ms

Do not over-read these timings. They show that preload/reshape phases are expensive relative to useful work, but production acceptance must use a live-sized SQLite DB.

## 6. Schema Batch A — Current Authoritative State

Batch A exists to make exact resolver lookups cheap enough to support resolver-first execution. It is complete and should be treated as closed unless repo evidence says otherwise.

### Batch A public schema contract

Guaranteed public indexes:

```sql
CREATE INDEX IF NOT EXISTS idx_system_by_name ON System (name);
CREATE INDEX IF NOT EXISTS idx_station_by_system_name ON Station (system_id, name);
```

MariaDB/ORM reset outcome must expose equivalent indexes:

```sql
CREATE INDEX idx_system_by_name ON System (name);
CREATE INDEX idx_station_by_system_name ON Station (system_id, name);
```

### Source-of-truth files

SQLite fresh builds:

- `tradedangerous/templates/TradeDangerous.sql`

MariaDB fresh resets:

- `tradedangerous/db/orm_models.py`
- reset path in `tradedangerous/db/lifecycle.py`

Lifecycle entry deciding keep/rebuild:

- `tradedangerous/tradedb.py`

### Batch A verification recorded on 2026-04-17

SQLite packaged rebuild/reset outcome:

- `PRAGMA index_list('System')` showed `idx_system_by_name`.
- `PRAGMA index_list('Station')` showed `idx_station_by_system_name`.
- `EXPLAIN QUERY PLAN SELECT system_id FROM System WHERE name = 'Sol'` used `idx_system_by_name`.
- Exact `system/station` join lookup used `idx_system_by_name` and covering `idx_station_by_system_name`.

MariaDB live schema outcome:

- `System` contains `idx_system_by_name`.
- `Station` contains `idx_station_by_system_name`, `idx_station_by_name`, and `idx_station_by_system`.
- Composite station index shape is `(system_id, name)`.

### Explicit Batch A non-goals

Batch A must not include:

- new tables
- new columns
- changed column types
- primary-key changes
- foreign-key changes
- row semantic changes
- importer payload changes
- normalized search columns
- search helper tables
- staging/export tables on SQLite
- cosmetic ORM/template drift reconciliation
- opportunistic schema tweaks
- in-place upgrade logic for existing databases

### Supported rollout

Supported rollout is rebuild/reset via clean import. Existing databases are not upgraded in place under Batch A.

This is acceptable because later refactor stages will introduce a breaking schema change that will require rebuild anyway.

### Downstream release note

Short form:

> This release includes a small additive schema update for read performance. No tables or columns change. The shipped Batch A schema includes `idx_system_by_name` on `System(name)` and `idx_station_by_system_name` on `Station(system_id, name)`. Supported rollout is via rebuild/reset (`clean` import), not in-place upgrade of existing databases.

Longer form:

> This release performs a narrow additive schema update intended to improve lookup performance without changing the underlying data shape. No tables, columns, primary keys, or foreign keys are changed. The public schema now includes `idx_system_by_name` on `System(name)` and `idx_station_by_system_name` on `Station(system_id, name)`. Supported rollout is via rebuild/reset (`clean` import). Existing databases are not upgraded in place as part of this release, and later refactor stages will introduce a breaking schema change that will require rebuild anyway.

### Historical/superseded Batch A planning notes

Earlier documents planned an implementation path with these tasks:

1. freeze Batch A scope
2. capture baseline evidence
3. update fresh-build schema sources
4. implement in-place index reconciliation
5. wire reconciliation into central lifecycle
6. verify SQLite fresh-build and upgrade behaviour
7. verify MariaDB fresh-reset and upgrade behaviour
8. run parity/query-plan checks
9. package release notes
10. freeze schema again

Only the parts consistent with the verified rebuild/reset policy remain active. Do not implement the in-place reconciliation helper unless the policy is explicitly reopened.

## 7. Known Schema Drift To Keep Out Of Batch A

Known ORM/template drift from the planning documents:

- `Category` ORM declares `idx_category_by_name`; SQLite template may not.
- `Item` ORM declares `idx_item_by_category`; SQLite template may not.
- `Item` ORM index name `idx_item_by_fdevid` differs from SQLite template `idx_item_by_fdev_id`.
- ORM defines `ExportControl`; SQLite template does not.
- ORM defines `StationItem_staging`; SQLite template does not.

Do not drag this into Batch A merely because it exists. Treat each as a separate schema decision if and when it becomes required.

Future Batch B is only justified if resolver/search quality or performance genuinely requires structural search support such as normalized search columns, search helper tables, or supporting indexes for prefix/token search.

## 8. Programme Roadmap

Each checkpoint must be releasable in its own right, either as a user-visible improvement, safe schema change, or necessary enabling change that leaves the codebase cleaner and more measurable.

Every checkpoint requires:

1. explicit scope
2. explicit acceptance criteria
3. explicit rollback point
4. docs update if behaviour or process changed
5. benchmark or verification evidence where relevant

### Checkpoint A / Milestone M0 — Instrumentation and production baselines

Goal: make expensive phases visible and measurable.

Primary outputs:

- timing helper
- phase timing output
- benchmark command set
- first live baseline
- query-plan snapshot

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

Benchmark at minimum:

- `local`
- `market`
- `buy`
- `sell`
- `nav`
- `rares`
- `trade`
- `run` in at least three shapes: short local, typical user route, wide/high-hop route

Acceptance:

- preload-bound versus algorithm-bound commands can be identified with evidence.
- future changes can be compared against a stable live-DB baseline.

### Checkpoint B / Milestone M1 — Schema Batch A

Goal: unblock resolver-first work with the smallest fair schema release.

Current state: closed. See Section 6.

Workers should not re-open Batch A unless repo reality contradicts the recorded verification.

### Checkpoint C — Legacy audit and prune map

Goal: classify suspiciously ancient code as core-live, compatibility-live, dead, or unknown.

Primary output:

- `docs/AUDIT.md`

Use this before deleting legacy support code.

### Checkpoint D — Remove `Added`

Goal: remove obsolete `Added` table, schema references, import/export handling, and runtime logic.

Acceptance:

- no remaining runtime dependency on `Added`
- schema/import/export/docs/tests updated as required
- rollback point exists before the removal

### Checkpoint E — Collapse `RareItem` into `Item`

Goal: remove standalone rares table and model rarity through `Item.rare_station_id`.

Design:

- `RareItem` is removed.
- Rarity is represented by `Item.rare_station_id IS NOT NULL`.
- `is_rare` is not persisted; expose only as convenience logic in Python if useful.
- `trade rares` must continue to work on the new model.

### Checkpoint F / Milestone M2 — Resolver contract and parity tests

Goal: define and lock lookup semantics before broad migration.

Resolver responsibilities:

- system lookup
- station lookup
- place lookup
- item lookup where needed
- ambiguity handling
- helpful candidate output
- duplicate system disambiguation with `@N`
- support for `SYS`, `STN`, `SYS/STN`, and `/STN`

Preferred matching order to evaluate:

1. exact normalized match
2. exact raw match
3. prefix normalized match
4. prefix raw match
5. broader fallback only if still required

Avoid leading-wildcard `%term%` as the default path. Avoid materialising large candidate sets with `.all()` unless bounded and justified.

Acceptance:

- resolver behaviour matches legacy expectations closely enough to replace `TradeDB` for command setup.
- parity tests cover exact matches, partial matches, ambiguous names, duplicate systems with `@N`, station-only forms, system/station forms, and bad inputs.

### Checkpoint G / Milestone M3 — Resolver-first execution flow

Goal: resolve command inputs before any heavy `TradeDB` path.

Current old flow:

- `preflight` catches obvious bad syntax/option issues.
- Valid commands still often pay full `TradeDB` hydration before useful setup.

Target capability model:

- needs resolver only
- needs system/station shell
- needs item catalog
- needs full trade graph

Argument resolution to move through resolver where possible:

- `--from`
- `--to`
- `--near`
- `--avoid`
- `--via`

Acceptance:

- valid lookup-heavy commands no longer incur full `TradeDB.load()`.
- CLI and GUI use the same resolver-first semantics.
- `TradeDB(load=False)` remains only as a temporary compatibility shim where necessary.

### Checkpoint H / Milestone M4 — Migrate `local`

Goal: first clear user-visible command win.

Current pain:

- full `TradeDB` load
- Python-side distance and station filtering over hydrated objects

Plan:

1. resolve origin system via resolver
2. do system range search in SQL or a lean geometry helper
3. move station filters into SQL where practical
4. hydrate only minimal output rows
5. preserve headings, ordering, and detail output closely enough for compatibility

Station filters to push into SQL where practical:

- trading market
- black market
- shipyard
- outfitting
- refuel, repair, rearm
- pad size
- planetary/fleet/Odyssey
- max ls from star

Acceptance:

- `local` runs without mandatory full `TradeDB` preload.
- cold-start time improves on live SQLite.
- output remains acceptably close to legacy behaviour.

### Checkpoint I / Milestone M5 — Migrate `market`, `buy`, `sell`

Goal: move obvious preload-bound commands off full preload one at a time.

Shared need:

- lightweight item/category lookup service that does not require fully built legacy item/category objects.

`market` plan:

1. resolve station through resolver
2. fetch market rows directly
3. attach minimal item metadata for rendering
4. preserve ordering and filters

`buy`/`sell` plan:

1. move item/category lookup into resolver or item service
2. return matching stations from SQL
3. attach minimal station metadata for rendering
4. keep sorting behaviour identical

Acceptance:

- each command demonstrates lower cold-start time
- no behaviour regression
- no mandatory full `TradeDB` hydration
- before/after timing notes exist per command

### Checkpoint J / Milestone M6 — Split `TradeDB` by capability

Goal: turn monolithic preload into selective compatibility loading.

Suggested split:

- `load_systems()`
- `load_station_shell()`
- `load_station_summaries()`
- `load_categories()`
- `load_items()`

Key rule:

- separate station shell data from station trade summary data.

Reason:

- `nav` needs route geometry/shell data.
- `olddata` and `local --trading` may need summary data.
- most commands do not need everything.

Acceptance:

- commands can request only the subset of legacy data they need.
- old monolithic `load()` path becomes exceptional, not default.
- remaining legacy callers are audited by dependency type.

### Checkpoint K / Milestone M7 — Reduce `TradeCalc` setup cost

Goal: make `run` materially faster by narrowing preload and reshape work.

Observed issue:

- `TradeCalc.__init__()` broadly scans `StationItem`, filters demand/supply, parses timestamps row by row, and builds Python-side buy/sell maps every run.

Plan:

1. add fine-grained instrumentation inside `TradeCalc.__init__()`
2. derive candidate station IDs before constructing `TradeCalc`
3. use `restrict_station_ids` for real
4. push supply, demand, age, item, pad, planetary, fleet, Odyssey, max-ls and related constraints into SQL where safe
5. evaluate SQL-side timestamp/age handling versus Python `parse_ts`
6. consider chunked row processing only if memory becomes a problem
7. re-benchmark `run` after each narrowing change

Candidate station derivation can use:

- origin station
- destination station/system
- `--start-jumps`
- `--end-jumps`
- `--via`
- pad/planetary/fleet/Odyssey/max-ls constraints

Acceptance:

- `TradeCalc.__init__()` time drops materially on live DB.
- amount of `StationItem` scanned per run is reduced where command shape allows it.

### Checkpoint L / Milestone M8 — Migrate `olddata`, `nav`, `rares`

Goal: finish the main command migration set.

`olddata`:

- already SQL-heavy
- resolve near-system through resolver
- hydrate only minimal station metadata for returned rows

`nav`:

- genuinely needs route geometry
- should use system/station shell data only
- should not load item/category data

`rares`:

- resolve near-system through resolver
- query rare rows via direct joins using `Item.rare_station_id`
- attach minimal station shell data

Acceptance:

- migrated where justified
- explicit list exists for any commands still needing monolithic `TradeDB.load()`

### Checkpoint M / Milestone M9 — GUI session reuse and cache discipline

Goal: recover load-once benefits only where they belong: GUI session scope.

Plan:

1. keep a long-lived resolver in the GUI process
2. optionally keep a lightweight system/station cache
3. invalidate caches after import, update, explicit rebuild, or database file change detection
4. be conservative with stale data rules

Acceptance:

- repeated GUI actions feel faster than repeated CLI cold starts.
- cache invalidation is explicit and reliable.

### Checkpoint N / Milestone M10 — Route algorithm follow-up and closeout

Goal: only optimise route internals if profiling says they are now dominant.

Inspect only after setup costs have been reduced:

- destination iteration volume
- repeated `distanceTo` calls
- repeated station suitability checks
- item fit function cost
- route pruning effectiveness
- safe per-run memoisation
- precomputed destination candidates for common constraint sets, if profiling justifies it

Acceptance:

- any algorithmic optimisation is justified by live-profile evidence, not instinct.
- closeout removes quarantined dead code, aligns docs, and prepares fork for merge or selective upstream PRs.

## 9. Recommended Execution Order

If only one stream is active:

1. Instrumentation and baseline capture.
2. Batch A schema/index verification or release state confirmation.
3. Legacy audit and prune map.
4. Remove `Added`.
5. Collapse `RareItem` into `Item`.
6. Resolver contract and parity tests.
7. Resolver-first execution flow.
8. Migrate `local`.
9. Migrate `market`, `buy`, `sell`.
10. Split `TradeDB` by capability.
11. Reduce `TradeCalc` setup cost.
12. Migrate `olddata`, `nav`, `rares`.
13. GUI session reuse.
14. Closeout and prune wave 2.
15. Route algorithm tuning only if evidence still points there.

The older performance-only ordering put resolver/index work before `Added`/`RareItem` removal. The final implementation plan adds legacy cleanup before broad resolver work. If the current repo already completed Batch A, the next real step depends on current fork modifications and checkpoint status.

## 10. Suggested Session-Sized Work Packets

Tiny packets:

- add or refine timing helper
- write benchmark command list
- confirm Batch A indexes/query plans on current repo/database
- define resolver interface
- split `TradeCalc.__init__()` timing phases

Medium packets:

- exact system resolver lookup
- exact station/place resolver lookup
- command capability model
- resolver-based `local` origin lookup
- lightweight item lookup service
- `TradeDB` sub-loader split
- wire `restrict_station_ids`

Larger packets:

- ambiguity and partial-match resolver parity
- SQL-backed `local` range/filter implementation
- full `market`, `buy`, or `sell` migration
- candidate station narrowing design for `run`
- `nav` migration
- route solver tuning after fresh profiles

If health/time is tight, prefer evidence work, low-risk schema verification, interface/tests, or one-command migration. Avoid starting partial-match parity, broad `TradeDB` surgery, or route tuning unless there is enough continuity to finish or cleanly hand off.

## 11. Verification Strategy

Functional verification:

- existing tests pass
- resolver parity tests cover ambiguity, duplicates, `@N`, station/system forms, command output ordering, and bad inputs
- CLI and GUI semantics remain aligned

Performance verification:

- compare cold-start times before/after each relevant change
- compare warm times separately
- track memory where practical
- record rows scanned where possible
- use live SQLite baselines, not fixture-only data
- capture query plans for resolver queries

Resolver query-plan checks:

- exact `System.name = ?`
- exact `Station.name = ?`
- system-plus-station lookup
- partial system match
- partial station match

Rollout safety:

- land behind flags where sensible
- migrate command by command
- keep legacy path until parity is proven
- do not remove `TradeDB` prematurely

## 12. Risks and Mitigations

### Risk: lookup behaviour regressions

Mitigation:

- resolver parity test suite
- staged rollout
- preserve ambiguity text where possible

### Risk: ORM path slower than legacy behaviour

Mitigation:

- fix/verify indexes first
- prefer exact and prefix matching over wildcard scans
- profile query plans on SQLite and MariaDB

### Risk: awkward long-lived hybrid state

Mitigation:

- define clear interfaces
- migrate whole command execution paths, not isolated helper fragments
- keep compatibility shims explicit and temporary

### Risk: premature route algorithm work

Mitigation:

- keep route internals until after `TradeCalc.__init__()` narrowing
- require live-profile evidence

### Risk: stale GUI caches

Mitigation:

- explicit invalidation rules
- conservative cache scope
- same backend semantics as CLI

## 13. Mandatory Pause Conditions

Stop and reassess if any of these happen:

1. Resolver parity demands too much legacy recreation for too little gain.
2. SQLite query plans do not improve after expected indexes are present.
3. `run` remains slow after `TradeCalc` narrowing, implying route maths is now the hotspot.
4. CLI and GUI drift into different backend semantics.
5. Any helper grows into a general framework with unclear boundaries.
6. Schema work fragments into many tiny downstream-facing changes instead of coherent batches.
7. Partial migration leaves duplicated backend paths with subtly different semantics.
8. GUI caching hides stale data too aggressively.
9. Someone tries to piggyback unrelated schema changes onto a narrow release.
10. Repo state contradicts the documented Batch A status.

## 14. Explicit Non-Recommendations

Do not start with:

- rewriting `tradecalc.py` from scratch
- making every command async
- replacing SQLite for end users as a prerequisite to speed work
- deleting `TradeDB` before compatibility seams exist
- one massive ORM conversion branch across all commands
- reconciling all ORM/template drift as part of Batch A
- adding search tables/columns before resolver parity proves they are needed

## 15. Useful Reference Files

Planning/docs:

- `docs/PERF_NOTES.md`
- `docs/AUDIT.md`
- `docs/RESOLVER_CONTRACT.md`
- `docs/SCHEMA_BATCH_LOG.md`
- `docs/SESSION_HANDOFF_TEMPLATE.md`
- `docs/REFACTOR_PROGRESS.md`

Code hotspots:

- `tradedangerous/cli.py`
- `tradedangerous/commands/commandenv.py`
- `tradedangerous/tradedb.py`
- `tradedangerous/tradecalc.py`
- `tradedangerous/tradeorm.py`
- `tradedangerous/commands/trade_cmd.py`
- `tradedangerous/guiapp/td_exec.py`
- `tradedangerous/templates/TradeDangerous.sql`
- `tradedangerous/db/orm_models.py`
- `tradedangerous/db/lifecycle.py`

External references previously used only as sanity checks:

- SQLAlchemy performance FAQ
- SQLAlchemy large result set performance examples

These are supporting ORM/Core performance references, not a substitute for profiling Trade Dangerous itself.

## 16. Handoff Checklist For Any Worker Session

Before doing work:

- identify current checkpoint/subtask
- inspect current repo modifications
- state exact scope
- state acceptance criteria
- state rollback point
- identify files likely to be touched
- identify benchmark/test evidence required

Before pausing:

- summarise what changed
- summarise what was verified
- record commands/tests run
- record known failures or unknowns
- state next safe action
- state rollback point
- update docs if behaviour/process changed

## 17. Current Best Next Actions

Given Batch A is now documented as closed, do not blindly follow older “add index/migration” next-action lists.

A sane next sequence, assuming no repo modifications contradict it, is:

1. Confirm current fork status and Batch A files match the verified contract.
2. Capture or update instrumentation/baseline evidence if not already present.
3. Produce or update `docs/AUDIT.md` for legacy code classification.
4. Remove `Added` cleanly.
5. Collapse `RareItem` into `Item` and preserve `rares` command behaviour.
6. Write resolver parity matrix/tests.
7. Implement exact system/station/place resolver support.
8. Move `local` far enough to avoid full `TradeDB` preload.

If only one user-visible early win is desired after baseline work, `local` remains the strongest first command migration candidate.
