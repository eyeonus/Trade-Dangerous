# Trade Dangerous Performance Tactical Backlog

Date: 2026-03-23
Status: Tactical implementation draft
Audience: Maintainers working incrementally around limited time and energy
Companion document: `docs/performance_optimization_plan.md`

## Purpose

This document turns the larger optimization plan into milestone slices and work packets that can be tackled in smaller, safer increments.

The intent is not to pretend every problem is a one-evening change. Some pieces are inherently medium or large. The goal here is to make the stopping points explicit, keep the order sane, and surface the work items that can be done independently without losing the wider strategy.

## How To Use This Backlog

1. Treat each milestone as a logical phase, not a mandatory all-at-once branch.
2. Treat each work packet as the smallest useful chunk that can be completed, tested, and parked.
3. Prefer finishing one packet cleanly over half-starting three packets.
4. Re-run representative benchmarks after each packet that changes execution flow or preload scope.
5. Stop immediately if a packet reveals that one of the underlying assumptions was wrong.

## Ground Rules

- Preserve lookup behavior unless a change is explicitly intentional and documented.
- Do not optimize route maths before setup cost has been measured down to a believable level.
- Do not remove legacy paths until the replacement path has parity tests and benchmark evidence.
- Treat the live SQLite database as the primary performance truth.
- Treat MariaDB as important, but do not let it distort optimizations for the majority SQLite path.

## Milestone Map

| Milestone | Goal | Smallest useful deliverable | Likely size | User-visible win |
| --- | --- | --- | --- | --- |
| M0 | Visibility and benchmarks | Stage timing output for key command phases | Small | Better diagnosis, less guesswork |
| M1 | Schema/index hygiene | Indexed exact system lookup on SQLite | Small | Faster resolver groundwork |
| M2 | Resolver parity foundation | Resolver that handles basic system/station/place lookups | Medium | Cheap valid command setup |
| M3 | Resolver-first execution flow | CLI/GUI resolve before any heavy `TradeDB` load | Medium | Cold-start reduction on non-trade commands |
| M4 | Migrate `local` | `local` runs without full `TradeDB` preload | Medium | Big visible win for a common command |
| M5 | Migrate `market`, `buy`, `sell` | One command at a time off full preload | Medium | Noticeable speed-up for lookup-heavy commands |
| M6 | Split `TradeDB` by capability | Load systems/station shell separately from items | Medium | Lower cost for partial-legacy commands |
| M7 | Reduce `TradeCalc` setup cost | Real use of `restrict_station_ids` | Large | `run` gets materially faster |
| M8 | Migrate remaining commands | `olddata`, `nav`, `rares` off full preload where feasible | Medium | Broad consistency |
| M9 | GUI session reuse | Long-lived resolver/cache inside GUI process | Small/Medium | Repeated GUI actions feel faster |
| M10 | Route algorithm follow-up | Profile-driven tuning inside `getBestHops()` | Large | Only if still needed |

## Recommended Order Of Attack

If working mostly alone and intermittently, the safest order is:

1. M0
2. M1
3. M2
4. M3
5. M4
6. M5
7. M6
8. M7
9. M8
10. M9
11. M10 only if evidence still points there

That order is deliberately biased toward high-confidence structural wins before deeper surgery.

## Milestone M0: Visibility And Benchmarks

### Objective

Make the expensive phases visible so future optimization work is driven by observed cost, not intuition.

### M0.1 Add a tiny timing helper

Aim:
Introduce one lightweight utility for timing named phases.

Touch points:
- `tradedangerous/cli.py`
- `tradedangerous/tradedb.py`
- `tradedangerous/tradecalc.py`
- optional utility module if you want to avoid clutter

Output:
- a small helper that records start/stop durations
- debug output only when an existing debug or performance flag is enabled

Definition of done:
- helper is cheap when disabled
- helper can be reused from CLI, `TradeDB`, and `TradeCalc`

Good stop point:
- helper exists but is not yet wired everywhere

### M0.2 Instrument command execution stages

Aim:
Measure phase timings for real command runs.

Touch points:
- `tradedangerous/cli.py`
- `tradedangerous/commands/commandenv.py`
- `tradedangerous/tradedb.py`
- `tradedangerous/tradecalc.py`

Output:
- timing lines for parse, preflight, `TradeDB` construction, `TradeDB.load`, `TradeCalc.__init__`, route solve, total runtime

Definition of done:
- `trade`, `run`, and at least one preload-bound command all emit phase timings under debug/perf mode

Good stop point:
- timings exist even if output format is ugly

### M0.3 Create a benchmark command set

Aim:
Choose a small stable set of commands for before/after comparisons.

Suggested benchmark list:
- `local` with a common system and moderate radius
- `market` on a busy known station
- `buy` near a populated region
- `sell` near a populated region
- `nav` with a non-trivial start and destination
- `rares` near a populated region
- `trade` between two known stations
- `run` in at least three shapes: short, typical, wide

Output:
- one Markdown or JSON file documenting the exact benchmark commands

Definition of done:
- same commands can be run before and after each major packet

Good stop point:
- benchmark list written down, even if automation comes later

### M0.4 Capture one live-database baseline

Aim:
Get one trustworthy baseline from the real SQLite DB.

Output:
- phase timings for the benchmark commands
- memory notes if practical
- command results saved somewhere outside the main code path

Definition of done:
- one dated baseline exists and can be compared later

Good stop point:
- timings captured even if memory data is missing

### M0.5 Query plan snapshot for resolver candidates

Aim:
Know whether the intended lookup queries are indexed or scanning.

Queries to inspect:
- exact `System.name = ?`
- exact `Station.name = ?`
- system-plus-station lookup
- partial system match
- partial station match

Output:
- saved query plans in Markdown or text

Definition of done:
- enough evidence exists to justify or reject index work in M1

Good stop point:
- SQLite query plans captured even if MariaDB is deferred

## Milestone M1: Schema And Index Hygiene

### Objective

Fix obviously missing or weak indexing before building more on top of the resolver path.

### M1.1 Add `idx_system_by_name` to the canonical SQLite schema

Aim:
Make exact system lookups cheap on SQLite.

Touch points:
- `tradedangerous/templates/TradeDangerous.sql`
- any schema rebuild or DB generation path

Definition of done:
- new SQLite databases get the index automatically

Good stop point:
- template updated, rebuild tested on a scratch DB

### M1.2 Add upgrade handling for existing databases

Aim:
Ensure existing user databases can gain the missing index without requiring a destructive rebuild.

Touch points:
- DB migration/update path
- startup check if that is how schema drift is currently handled

Definition of done:
- an existing DB can be upgraded in place and the index appears exactly once

Good stop point:
- upgrade command or startup path creates the index correctly on a test DB

### M1.3 Verify exact lookup now uses the index

Aim:
Close the loop on M1.1 and M1.2.

Output:
- before/after `EXPLAIN QUERY PLAN` evidence

Definition of done:
- exact `System.name = ?` no longer shows a table scan on SQLite

### M1.4 Evaluate composite station lookup index

Aim:
Determine whether `Station(system_id, name)` should exist.

Why this is a separate packet:
- it is plausible and useful
- it is still a hypothesis until query plans and timings say so

Definition of done:
- decision recorded: add it now, defer it, or reject it

## Milestone M2: Resolver Parity Foundation

### Objective

Build the lightweight lookup layer that lets valid command setup happen without full `TradeDB` hydration.

### M2.1 Write the legacy lookup behavior matrix

Aim:
Document current behavior before replacing it.

Cases to capture:
- exact system match
- exact station match
- partial system match
- partial station match
- `SYS/STN`
- `/STN`
- duplicate systems with `@N`
- ambiguity text
- not-found behavior
- system given where station expected

Touch points:
- tests first, ideally
- `tradedangerous/tradedb.py`
- `tradedangerous/tradeorm.py`

Definition of done:
- there is a concrete parity checklist instead of tribal memory

Good stop point:
- cases documented even if implementation has not begun

### M2.2 Define a minimal resolver interface

Aim:
Avoid spreading one-off lookup calls all over the codebase.

Proposed interface:
- `lookup_system(name)`
- `lookup_station(name)`
- `lookup_place(name)`
- optional `lookup_item(name)` later

Definition of done:
- one interface exists with clear responsibilities

### M2.3 Implement exact system lookup first

Aim:
Get the simplest fast case working before touching ambiguity logic.

Definition of done:
- resolver can find a system by exact match with indexed SQL
- tests cover success and failure

Good stop point:
- exact-only system lookup works even if partial matching does not yet

### M2.4 Implement exact station and place lookup

Aim:
Support `station`, `system/station`, and station-only resolution flows.

Definition of done:
- exact station and place lookup work for the common happy path

### M2.5 Add ambiguity and duplicate-name handling

Aim:
Recover the less convenient but very important legacy behavior.

Definition of done:
- duplicate systems and ambiguous station names are handled predictably
- `@N` behavior has tests

### M2.6 Add partial matching carefully

Aim:
Match current user expectations without immediately falling back to expensive `%term%` scans everywhere.

Preferred order to evaluate:
1. exact normalized
2. exact raw
3. prefix normalized
4. prefix raw
5. only then broader fallback if still required

Definition of done:
- partial matching exists and is benchmarked against the live SQLite DB

### M2.7 Add resolver parity tests

Aim:
Make future migrations safer.

Definition of done:
- resolver parity suite passes against the expected legacy cases

## Milestone M3: Resolver-First Execution Flow

### Objective

Make valid command lines cheap to resolve before any heavy load happens.

### M3.1 Add a command capability model

Aim:
Replace the coarse "needs all of `TradeDB`" assumption.

Possible capabilities:
- needs resolver only
- needs system/station shell
- needs item catalog
- needs full trade graph

Definition of done:
- command metadata can express what kind of backend support it needs

Good stop point:
- capability model exists even if only one or two commands use it

### M3.2 Resolve `--from`, `--to`, `--near`, `--avoid`, `--via` via resolver

Aim:
Shift lookup cost away from `TradeDB`.

Touch points:
- `tradedangerous/commands/commandenv.py`
- CLI and GUI execution path

Definition of done:
- valid location arguments can be resolved without a full `TradeDB.load`

### M3.3 Keep compatibility shim only where necessary

Aim:
Avoid breaking everything at once.

Definition of done:
- commands that still need `TradeDB` keep working
- commands that do not need it no longer pay for it

### M3.4 Mirror the same flow in the GUI executor

Aim:
Prevent CLI and GUI from drifting into separate backend architectures.

Touch points:
- `tradedangerous/guiapp/td_exec.py`

Definition of done:
- GUI resolves arguments the same way as CLI

## Milestone M4: Migrate `local`

### Objective

Deliver the first visible command-level speed win on a command that should not need the whole legacy world.

### M4.1 Port origin-system resolution to resolver

Aim:
Remove `local`'s dependency on `nearSystem` coming from `TradeDB`.

Definition of done:
- `local` can start with a resolver-returned origin system

### M4.2 Implement system range query outside legacy object iteration

Aim:
Do the distance candidate search without preloading all legacy wrappers.

Options:
- SQL distance calculation
- SQL bounding box then precise distance in Python
- a small geometry helper if needed

Definition of done:
- candidate systems come from direct query or lean helper, not full `TradeDB` iteration

### M4.3 Move station filters into SQL where practical

Target filters:
- trading market
- black market
- shipyard
- outfitting
- refuel, repair, rearm
- pad size
- planetary/fleet/odyssey
- max ls from star

Definition of done:
- most filtering happens before rows are hydrated into render objects

### M4.4 Restore render parity

Aim:
Keep the output familiar.

Definition of done:
- headings, ordering, and detail output remain acceptably close to legacy behavior

### M4.5 Benchmark and ship `local`

Definition of done:
- cold-start time improves on live SQLite
- no obvious behavior regression remains

## Milestone M5: Migrate `market`, `buy`, and `sell`

### Objective

Move the other obvious preload-bound commands off full `TradeDB`, one command at a time.

### M5.1 Build a lightweight item lookup service

Aim:
Avoid dragging full legacy item/category structures into commands that mostly need names and IDs.

Definition of done:
- item lookup can happen without `itemByID` being fully built in memory

### M5.2 Migrate `market`

Subtasks:
- resolve station through resolver
- fetch market rows directly
- attach minimal item metadata for rendering
- preserve ordering and filters

Definition of done:
- `market` no longer depends on full `TradeDB.load`

### M5.3 Migrate `buy`

Subtasks:
- use item lookup service
- use resolver for `--near` and station references
- fetch matching stations directly
- preserve sort behavior and constraints

Definition of done:
- `buy` runs without full legacy preload

### M5.4 Migrate `sell`

Same shape as `buy`, but for sell-side lookup and ranking.

Definition of done:
- `sell` runs without full legacy preload

### M5.5 Benchmark each command separately

Aim:
Avoid bundling three migrations into one unverifiable blob.

Definition of done:
- each command has an explicit before/after timing note

## Milestone M6: Split `TradeDB` By Capability

### Objective

Turn `TradeDB` into a selective compatibility layer instead of an all-or-nothing preload.

### M6.1 Split `load()` into named sub-loaders

Candidate split:
- `load_systems()`
- `load_station_shell()`
- `load_station_summaries()`
- `load_categories()`
- `load_items()`

Definition of done:
- individual pieces can be requested independently

### M6.2 Separate station shell from station trade summaries

Aim:
Stop commands paying the `StationItem` aggregate cost unless they actually need it.

Definition of done:
- commands can ask for station metadata without also calculating item counts and ages

### M6.3 Audit remaining legacy callers

Aim:
Work out who really needs what.

Suggested audit output:
- command or module name
- systems needed?
- station shell needed?
- station summaries needed?
- categories/items needed?
- full trade graph needed?

Definition of done:
- a dependency table exists for remaining legacy consumers

### M6.4 Switch any easy legacy callers to partial loads

Aim:
Capture wins even before full ORM migration finishes everywhere.

Definition of done:
- at least one command still on `TradeDB` now uses selective sub-loads

## Milestone M7: Reduce `TradeCalc` Setup Cost

### Objective

Shrink the amount of market data `run` has to scan and reshape before route solving.

### M7.1 Add fine-grained instrumentation inside `TradeCalc.__init__`

Aim:
Know exactly which part of constructor work dominates.

Potential sub-phases:
- candidate station gathering
- SQL fetch
- timestamp handling
- buy/sell map construction
- suitability filtering

Definition of done:
- constructor timings are split enough to guide the next packet

### M7.2 Derive candidate station IDs before constructing `TradeCalc`

Aim:
Use command constraints to narrow the market scan.

Candidate inputs:
- origin station or system
- destination station or system
- `--via`
- `--avoid`
- jump radius constraints
- station capability filters

Definition of done:
- candidate station set can be passed into the constructor path

### M7.3 Wire `restrict_station_ids` for real

Aim:
Use the narrowing hook that already exists.

Definition of done:
- benchmark confirms reduced row scan for command shapes that can be narrowed

Good stop point:
- hook wired even if narrowing heuristics remain conservative

### M7.4 Push more filtering into SQL

Targets to verify:
- demand and supply thresholds
- age threshold
- item constraints
- buy/sell side filtering

Definition of done:
- fewer irrelevant `StationItem` rows reach Python

### M7.5 Evaluate SQL-side timestamp handling

Hypothesis:
- computing age in SQL may be cheaper than parsing timestamps row by row in Python

Definition of done:
- one measured answer exists for SQLite, and preferably MariaDB too
- keep or reject based on evidence

### M7.6 Consider chunked processing only if needed

Aim:
Reduce memory spikes if row volume is still large.

Definition of done:
- decision recorded: unnecessary, useful later, or implemented

### M7.7 Re-benchmark `run`

Definition of done:
- updated timings show whether setup is still dominant

## Milestone M8: Migrate Remaining Commands

### Objective

Finish the obvious command-level migration work once the key seams exist.

### M8.1 Migrate `olddata`

Likely shape:
- resolver for near-system lookup
- direct query for station age data
- minimal station metadata hydration

Definition of done:
- `olddata` no longer needs full legacy preload

### M8.2 Migrate `nav`

Likely shape:
- may still need some geometry support
- should not need items or categories

Definition of done:
- `nav` uses resolver plus system/station shell data only

### M8.3 Migrate `rares`

Likely shape:
- resolver for near-system
- direct query for rare goods data
- minimal station metadata

Definition of done:
- `rares` no longer needs full preload

### M8.4 Re-evaluate whether any commands still truly need monolithic `TradeDB.load()`

Definition of done:
- list is short, explicit, and justified

## Milestone M9: GUI Session Optimization

### Objective

Recover the original "load once, answer many questions" idea for GUI sessions without depending on it for CLI behavior.

### M9.1 Keep a long-lived resolver in the GUI process

Definition of done:
- repeated GUI actions do not recreate the resolver every time

### M9.2 Optionally keep a lightweight system/station cache

Definition of done:
- repeated GUI actions avoid reloading unchanged shell metadata

### M9.3 Add cache invalidation rules

Invalidate on:
- import
- update
- rebuild
- DB file replacement or timestamp change if practical

Definition of done:
- stale cache behavior is controlled and explicit

## Milestone M10: Route Algorithm Follow-Up

### Objective

Only tune route solving after the surrounding setup cost has been cut down enough that the remaining bottleneck is truly inside route evaluation.

### M10.1 Re-profile `getBestHops()` and friends

Questions to answer:
- is distance calculation repeated excessively?
- are station suitability checks repeated unnecessarily?
- is destination candidate volume too large?
- are there low-risk memoization opportunities within one run?

Definition of done:
- a profile-backed list of actual hot spots exists

### M10.2 Take one algorithmic packet at a time

Aim:
Avoid destabilizing the route engine with speculative rewriting.

Definition of done:
- each optimization is isolated, benchmarked, and reversible

## Suggested Session-Sized Work Packets

If you only have a short window, these are good one-session candidates:

### Tiny packets

- M0.1 timing helper
- M0.3 benchmark command list
- M1.1 add `idx_system_by_name` to schema template
- M1.3 confirm query plan improvement
- M2.2 define resolver interface
- M7.1 split `TradeCalc.__init__` timing phases

### Medium packets

- M1.2 in-place DB upgrade for missing index
- M2.3 exact system lookup
- M2.4 exact station/place lookup
- M3.1 command capability model
- M4.1 resolver-based `local` origin lookup
- M5.1 lightweight item lookup service
- M6.1 `TradeDB` sub-loader split
- M7.3 wire `restrict_station_ids`

### Larger packets

- M2.5 plus M2.6 ambiguity and partial matching parity
- M4.2 plus M4.3 SQL-backed `local`
- full `market` or `buy` or `sell` migration
- M7.2 candidate station narrowing design
- M8.2 `nav` migration
- M10 algorithmic tuning inside route solving

## Best Early Wins

If the goal is visible benefit with relatively controlled risk, the strongest early packets are:

1. M0.2 instrument the load path
2. M1.1 plus M1.2 add and migrate `idx_system_by_name`
3. M2.1 document lookup parity rules
4. M2.3 exact system lookup
5. M2.4 exact station/place lookup
6. M3.2 resolve location args through resolver
7. M4.1 port `local` origin lookup
8. M4.2 move `local` system range search off full preload
9. M5.2 migrate `market`
10. M7.1 instrument `TradeCalc.__init__`
11. M7.3 wire `restrict_station_ids`

Those packets keep the effort focused on removing repeated cold-start cost before attacking deeper algorithm work.

## Safe Stop Points

The following are sensible places to pause without leaving the codebase conceptually lost:

- after instrumentation lands but before any behavioral changes
- after index migration lands but before resolver rollout
- after exact-match resolver support, before partial-match parity
- after `local` migration, before `market`/`buy`/`sell`
- after `TradeDB` sub-loader split, before converting all callers
- after `restrict_station_ids` wiring, before fancier narrowing heuristics

## Situations That Should Trigger A Pause

Stop and reassess if any of the following happens:

1. Resolver parity starts to demand too much legacy behavior recreation for too little gain.
2. SQLite query plans do not improve after the expected indexes are added.
3. `run` remains slow even after `TradeCalc` input narrowing, implying the route solver itself is now dominant.
4. Partial migration leaves two backend paths with subtly different semantics and too much duplication.
5. GUI-specific caching starts hiding stale data too aggressively.

## Suggested Deliverables Per Milestone

This keeps each phase concrete.

### M0 deliverables

- timing helper
- benchmark command list
- first live DB baseline
- query plan snapshot

### M1 deliverables

- schema patch or migration
- evidence of index use on exact system lookup
- decision note on composite station index

### M2 deliverables

- lookup parity matrix
- resolver interface
- resolver tests
- exact-match resolver implementation

### M3 deliverables

- command capability metadata
- resolver-first argument resolution in CLI
- same resolution flow in GUI

### M4 deliverables

- `local` migrated
- benchmark note showing improvement
- regression checks for output parity

### M5 deliverables

- lightweight item lookup service
- `market` migrated
- `buy` migrated
- `sell` migrated
- before/after timing notes for each

### M6 deliverables

- `TradeDB` sub-loaders
- dependency audit for remaining legacy callers
- at least one command using partial legacy load

### M7 deliverables

- constructor sub-phase timings
- candidate-station narrowing path
- `restrict_station_ids` wired
- updated `run` timings on live SQLite

### M8 deliverables

- `olddata`, `nav`, and `rares` reviewed and migrated where justified
- explicit list of any commands still requiring monolithic load

### M9 deliverables

- long-lived GUI resolver
- optional GUI shell cache
- explicit invalidation rules

### M10 deliverables

- route solver profile
- isolated algorithmic optimization packets if still justified

## If Health Or Time Is Tight

When energy is limited, prefer one of these categories:

- evidence work: instrumentation, baselines, query plans
- schema hygiene: low-risk index changes and verification
- interface work: resolver API definition and tests
- one-command migration at a time

Avoid starting these when you know you cannot stay with them for a while:

- partial-match parity recreation
- broad `TradeDB` refactors with many callers in flight
- route-algorithm tuning without fresh profiles

## Final Recommendation

If choosing only the next five packets, I would do these in order:

1. M0.2 instrument the current execution path
2. M1.1 plus M1.2 add and migrate the system-name index
3. M2.1 write the resolver parity matrix as tests
4. M2.3 plus M2.4 build exact-match resolver support
5. M4.1 plus M4.2 migrate `local` far enough to avoid full `TradeDB` preload

That sequence gives you evidence, a clean lookup seam, and one meaningful user-visible command win without having to solve the entire architecture in one push.
