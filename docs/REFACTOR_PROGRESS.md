# REFACTOR_PROGRESS.md
## Trade Dangerous modernization / performance refactor progress tracker

Working repo:
- `Tromador/Trade-Dangerous`

Working line:
- `release/v1` on the fork

Purpose:
- provide an immediate snapshot of what is done vs not done
- let future agent sessions start with state, not archaeology
- give one place to mark completed checkpoints, active work, blockers, and deferred items

---

## 0. Usage rules

### Status conventions
Use these consistently:

- `[ ]` not started
- `[-]` in progress
- `[x]` done
- `[!]` blocked / needs decision
- `[~]` intentionally deferred
- `[?]` status unclear, needs verification

### Update rules
Whenever a task changes state, update:
1. the checkbox
2. the short status note
3. the “Last updated” section
4. the “Current active task” section if relevant

### Session rule
At the end of every non-trivial session, update this file before stopping.

### Truthfulness rule
Do not tick a task unless:
- the code is committed or otherwise present in the working tree
- the acceptance condition for that task has actually been met

---

## 1. Current snapshot

### Current active checkpoint
- Status: `[-]`
- Checkpoint: `A — Instrumentation and production baselines`
- Subtask: `A4 first live baseline capture`
- Owner: `Stef + ChatGPT`
- Started: `2026-04-16`
- Goal: `record the first cold/warm live SQLite baseline using the validated checkpoint A benchmark corpus`

### Current blocker
- Status: `[!]`
- Blocker: `The first live baseline has not yet been recorded, even though the benchmark corpus is now validated.`
- Impact: `Checkpoint A cannot be marked done until cold/warm timing evidence is written down.`
- Needed to unblock: `run the validated corpus as cold and warm passes and record the results in docs/PERF_NOTES.md`

### Last updated
- Date: `2026-04-16`
- By: `ChatGPT (with live DB probe and command validation run by Stef)`
- Session summary: `Accepted in-session timing instrumentation for CLI, TradeDB, and TradeCalc; captured live SQLite query plans; validated the checkpoint A benchmark corpus against a live packaged SQLite DB refreshed via recent import; confirmed inherited preparatory index work via commit 1bd9ba9; aligned the project docs to the actual repo/runtime baseline.`

### Last known good rollback point
- Commit: `cf27373`
- Notes: `PERF_NOTES benchmark corpus and checkpoint A evidence update landed successfully; current tracker state now describes the repo as it stands after that docs commit.`

---

## 2. Programme-wide locked decisions

Mark these only if they are superseded by explicit new evidence and an agreed replacement.

- [x] Use Option 1 ORM migration strategy
- [x] `TradeDB` is being shrunk into a compatibility shim, not deleted up front
- [x] CLI and GUI remain equally first-class
- [x] Core engine remains OS-agnostic and frontend-agnostic
- [x] `Added` will be removed entirely
- [x] `RareItem` will be removed entirely
- [x] Rarity is represented by `Item.rare_station_id IS NOT NULL`
- [x] `is_rare` is convenience logic only, not stored schema
- [x] Work happens directly on `Tromador/Trade-Dangerous:release/v1`
- [x] No second refactor branch inside the fork unless later forced

---

## 3. Checkpoint summary board

- [-] A — Instrumentation and production baselines
- [-] B — Schema Batch A: narrow additive index release
- [ ] C — Legacy audit and prune map
- [ ] D — Remove `Added`
- [ ] E — Collapse `RareItem` into `Item`
- [ ] F — Resolver contract and parity tests
- [ ] G — Resolver-first execution flow
- [ ] H — Migrate `local`
- [ ] I — Migrate `market`, `buy`, `sell`
- [ ] J — Split `TradeDB` by capability
- [ ] K — Reduce `TradeCalc` setup cost
- [ ] L — Migrate `olddata`, `nav`, `rares`
- [ ] M — GUI session reuse and cache discipline
- [ ] N — Legacy prune wave 2 and closeout

---

## 4. Detailed checkpoint tracker

---

## Checkpoint A — Instrumentation and production baselines

### Goal
Make expensive phases visible and measurable.

### Acceptance criteria
- timing helper exists
- top-level execution timings exist
- benchmark command set is defined
- at least one real live SQLite baseline is recorded
- resolver candidate query plans are captured

### Tasks
- [x] A1. Add minimal timing helper
  - Status note: `TradeEnv.time_block added in-session and DEBUG-gated timing output now exists at the helper level.`
  - Evidence: `tradedangerous/tradeenv.py` in-session accepted edit
- [x] A2. Instrument top-level command execution
  - Status note: `CLI parse/preflight/TradeDB/run/render/total timings were added in-session, and TradeDB/TradeCalc phase timing was extended enough to expose the main current costs.`
  - Evidence: `tradedangerous/cli.py`, `tradedangerous/tradedb.py`, `tradedangerous/tradecalc.py` in-session accepted edits
- [x] A3. Define benchmark command set
  - Status note: `The non-run and run benchmark commands were validated against the live packaged SQLite database and are now fixed in PERF_NOTES for checkpoint A baseline capture.`
  - Evidence: `docs/PERF_NOTES.md`; live command validation on 2026-04-16
- [ ] A4. Capture first live baseline
  - Status note: `Not yet recorded.`
  - Evidence:
- [x] A5. Capture resolver/query-plan notes
  - Status note: `Live SQLite query plans were captured for exact system lookup, exact station lookup, system/station join lookup, partial system, and partial station.`
  - Evidence: `tools/checkpoint_a_probe.py` output on 2026-04-16

### Notes
- `A5` evidence shows the current live SQLite DB is already using `idx_system_by_name`, `idx_station_by_name`, and `idx_station_by_system_name`.
- This means some older planning assumptions are stale relative to the inherited repo/runtime baseline.
- The benchmark corpus is now validated; the remaining Checkpoint A step is baseline capture.

---

## Checkpoint B — Schema Batch A: narrow additive index release

### Goal
Ship the first narrow additive read-performance schema batch.

### Acceptance criteria
- `idx_system_by_name` exists on SQLite and MariaDB
- existing DBs are upgraded in place where appropriate
- fresh DB builds include the Batch A index
- Batch A scope remains narrow
- optional station composite index is either proven and included, or explicitly deferred

### Tasks
- [x] B1. Freeze Batch A scope
  - Status note: `Inherited baseline indicates Batch A scope is already narrow: idx_system_by_name plus the proven station composite index, with no wider additive schema batch evidenced.`
  - Evidence: `1bd9ba9`
- [x] B2. Add Batch A index to fresh-build schema
  - Status note: `idx_system_by_name was already present in ORM metadata and was added to the SQLite schema in inherited preparatory work; idx_station_by_system_name is present in ORM metadata and SQLite schema.`
  - Evidence: `1bd9ba9`; `tradedangerous/db/orm_models.py`
- [ ] B3. Add narrow in-place reconciliation helper
  - Status note: `Still pending. Existing DBs remain valid but this checkpoint has not yet added a dedicated reconciliation helper.`
  - Evidence:
- [ ] B4. Wire reconciliation through central lifecycle path
  - Status note: `Still pending.`
  - Evidence:
- [ ] B5. Verify SQLite fresh-build and upgrade path
  - Status note: `Live SQLite evidence confirms current indexed state, but formal fresh-build/upgrade verification for the checkpoint is not yet recorded.`
  - Evidence:
- [ ] B6. Verify MariaDB fresh-build and upgrade path
  - Status note: `ORM metadata already includes the exact-lookup indexes, but formal fresh-build/upgrade verification for MariaDB is not yet recorded.`
  - Evidence:
- [x] B7. Decide on optional composite station index
  - Status note: `Decision already made in inherited preparatory work: include idx_station_by_system_name because live SQLite plan/timing evidence justified it.`
  - Evidence: `1bd9ba9`; live SQLite probe on 2026-04-16
- [ ] B8. Write release-note text for Batch A
  - Status note: `Still pending.`
  - Evidence:

### Notes
- `1bd9ba9` predates the formal refactor session but is part of the inherited baseline and must be treated as such.
- Remaining Checkpoint B work is now primarily verification, reconciliation, and documentation alignment rather than proving the value of the two key lookup indexes from scratch.

---

## Checkpoint C — Legacy audit and prune map

### Goal
Classify suspiciously ancient or possibly dead code before deleting anything.

### Acceptance criteria
- `docs/AUDIT.md` is populated
- entry points are inventoried
- tracing or equivalent evidence exists for uncertain paths
- suspicious candidates have a classification and action plan

### Tasks
- [ ] C1. Inventory live entry points
  - Status note:
  - Evidence:
- [ ] C2. Add temporary tracing mode or equivalent reachability evidence
  - Status note:
  - Evidence:
- [ ] C3. Build first audit map
  - Status note:
  - Evidence:
- [ ] C4. Quarantine obvious non-runtime junk
  - Status note:
  - Evidence:

### Notes
-

---

## Checkpoint D — Remove `Added`

### Goal
Delete the obsolete `Added` table and all live references.

### Acceptance criteria
- fresh DB has no `Added`
- old DB is rebuilt or rejected cleanly
- no supported command/import/export path relies on `Added`
- no live ORM/runtime references remain

### Tasks
- [ ] D1. Remove `Added` from ORM and canonical schema
  - Status note:
  - Evidence:
- [ ] D2. Remove template/import/export plumbing
  - Status note:
  - Evidence:
- [ ] D3. Remove live runtime references and wrapper dependencies
  - Status note:
  - Evidence:
- [ ] D4. Add schema sanity detection / rebuild path
  - Status note:
  - Evidence:
- [ ] D5. Update tests, fixtures, docs
  - Status note:
  - Evidence:

### Notes
-

---

## Checkpoint E — Collapse `RareItem` into `Item`

### Goal
Remove standalone rares table and model rarity through `Item.rare_station_id`.

### Acceptance criteria
- fresh DB has no `RareItem`
- old DB migrates or reports unmappable rows honestly
- `trade rares` works end-to-end on the new model
- importer/cache logic no longer treats rares as a separate table

### Tasks
- [ ] E1. Add `Item.rare_station_id` and only genuinely needed parity fields
  - Status note:
  - Evidence:
- [ ] E2. Add computed `is_rare` convenience logic if useful
  - Status note:
  - Evidence:
- [ ] E3. Implement migration/backfill from old `RareItem`
  - Status note:
  - Evidence:
- [ ] E4. Rewrite `trade rares`
  - Status note:
  - Evidence:
- [ ] E5. Remove importer/cache special cases
  - Status note:
  - Evidence:
- [ ] E6. Remove `RareItem` schema/docs/tests
  - Status note:
  - Evidence:

### Notes
-

---

## Checkpoint F — Resolver contract and parity tests

### Goal
Define and lock lookup semantics before broad command migration.

### Acceptance criteria
- resolver contract doc exists and is populated
- parity tests exist
- exact/common place resolution works without full `TradeDB.load()`

### Tasks
- [ ] F1. Write resolver contract document
  - Status note:
  - Evidence:
- [ ] F2. Convert legacy behavior into tests
  - Status note:
  - Evidence:
- [ ] F3. Implement exact system lookup
  - Status note:
  - Evidence:
- [ ] F4. Implement exact station and place lookup
  - Status note:
  - Evidence:
- [ ] F5. Add ambiguity and `@N` handling
  - Status note:
  - Evidence:
- [ ] F6. Add partial matching carefully
  - Status note:
  - Evidence:

### Notes
-

---

## Checkpoint G — Resolver-first execution flow

### Goal
Resolve command inputs before heavy legacy load.

### Acceptance criteria
- common command argument resolution works without full `TradeDB.load()`
- CLI and GUI follow the same resolution path
- no behavior regression in argument handling

### Tasks
- [ ] G1. Add capability-style command model
  - Status note:
  - Evidence:
- [ ] G2. Move `--near`, `--from`, `--to` to resolver path
  - Status note:
  - Evidence:
- [ ] G3. Move `--avoid` and `--via` to resolver path
  - Status note:
  - Evidence:
- [ ] G4. Keep `TradeDB(load=False)` only as transitional shim
  - Status note:
  - Evidence:
- [ ] G5. Mirror the same flow in GUI
  - Status note:
  - Evidence:

### Notes
-

---

## Checkpoint H — Migrate `local`

### Goal
Deliver the first clear user-visible performance win.

### Acceptance criteria
- `local` no longer needs full `TradeDB.load()`
- output remains acceptably stable
- cold-start timing improves materially

### Tasks
- [ ] H1. Port origin resolution to resolver
  - Status note:
  - Evidence:
- [ ] H2. Replace full legacy range iteration
  - Status note:
  - Evidence:
- [ ] H3. Push station filters into SQL
  - Status note:
  - Evidence:
- [ ] H4. Restore render parity
  - Status note:
  - Evidence:
- [ ] H5. Benchmark before/after
  - Status note:
  - Evidence:

### Notes
-

---

## Checkpoint I — Migrate `market`, `buy`, `sell`

### Goal
Move obvious preload-bound trading commands off full preload.

### Acceptance criteria
- each command runs without full legacy preload
- each command has explicit before/after timing evidence
- GUI path still uses the same core logic

### Tasks
- [ ] I1. Build lightweight item lookup service
  - Status note:
  - Evidence:
- [ ] I2. Migrate `market`
  - Status note:
  - Evidence:
- [ ] I3. Migrate `buy`
  - Status note:
  - Evidence:
- [ ] I4. Migrate `sell`
  - Status note:
  - Evidence:
- [ ] I5. Benchmark each command separately
  - Status note:
  - Evidence:

### Notes
-

---

## Checkpoint J — Split `TradeDB` by capability

### Goal
Turn `TradeDB` into a selective compatibility layer.

### Acceptance criteria
- commands can request only the subset of legacy preload they need
- monolithic `load()` is no longer the default for every legacy path

### Tasks
- [ ] J1. Create explicit sub-loaders
  - Status note:
  - Evidence:
- [ ] J2. Separate station shell from station summaries
  - Status note:
  - Evidence:
- [ ] J3. Audit remaining `TradeDB` callers by capability
  - Status note:
  - Evidence:
- [ ] J4. Move at least one easy caller to partial load
  - Status note:
  - Evidence:

### Notes
-

---

## Checkpoint K — Reduce `TradeCalc` setup cost

### Goal
Reduce `TradeCalc.__init__()` setup overhead before touching route maths.

### Acceptance criteria
- `TradeCalc` setup phases are measured
- candidate station narrowing is working
- realistic command shapes scan fewer rows
- `run` shows measurable improvement before route-maths work begins

### Tasks
- [ ] K1. Add `TradeCalc.__init__()` sub-phase timings
  - Status note:
  - Evidence:
- [ ] K2. Derive candidate station IDs before constructor
  - Status note:
  - Evidence:
- [ ] K3. Wire station restriction narrowing properly
  - Status note:
  - Evidence:
- [ ] K4. Push more filtering into SQL
  - Status note:
  - Evidence:
- [ ] K5. Evaluate SQL-side timestamp handling
  - Status note:
  - Evidence:
- [ ] K6. Consider chunking only if evidence demands it
  - Status note:
  - Evidence:
- [ ] K7. Re-benchmark `run`
  - Status note:
  - Evidence:

### Notes
-

---

## Checkpoint L — Migrate `olddata`, `nav`, `rares`

### Goal
Finish the main command migration set.

### Acceptance criteria
- `olddata`, `nav`, and `rares` no longer depend on full preload
- remaining monolithic `TradeDB` callers are few and justified

### Tasks
- [ ] L1. Migrate `olddata`
  - Status note:
  - Evidence:
- [ ] L2. Migrate `nav`
  - Status note:
  - Evidence:
- [ ] L3. Complete full `rares` cutover on new item model
  - Status note:
  - Evidence:
- [ ] L4. Re-evaluate remaining full `TradeDB.load()` callers
  - Status note:
  - Evidence:

### Notes
-

---

## Checkpoint M — GUI session reuse and cache discipline

### Goal
Recover “load once, answer many questions” only where it belongs: GUI session scope.

### Acceptance criteria
- repeated GUI actions are faster than cold CLI runs where appropriate
- no aggressive stale-data bugs
- GUI still uses the same business logic as CLI

### Tasks
- [ ] M1. Keep long-lived resolver in GUI scope
  - Status note:
  - Evidence:
- [ ] M2. Add lightweight system/station shell cache if justified
  - Status note:
  - Evidence:
- [ ] M3. Add invalidation rules
  - Status note:
  - Evidence:
- [ ] M4. Verify repeated GUI actions and stale-data behavior
  - Status note:
  - Evidence:

### Notes
-

---

## Checkpoint N — Legacy prune wave 2 and closeout

### Goal
Delete quarantined dead code and align docs/comments with reality.

### Acceptance criteria
- dead code proven by audit is removed
- comments/docs no longer lie
- fork is ready for selective upstream merge/PR work

### Tasks
- [ ] N1. Delete proven-dead runtime code in small packets
  - Status note:
  - Evidence:
- [ ] N2. Move remaining compatibility-only code under explicit legacy labeling
  - Status note:
  - Evidence:
- [ ] N3. Update docs/comments to match current truth
  - Status note:
  - Evidence:
- [ ] N4. Run final verification set
  - Status note:
  - Evidence:
- [ ] N5. Prepare release/merge notes
  - Status note:
  - Evidence:

### Notes
-

---

## 5. Deferred / parked items

Use this for ideas that are real but explicitly not in the current checkpoint.

- [ ] Deferred item:
  - Why deferred:
  - Revisit after checkpoint:
- [ ] Deferred item:
  - Why deferred:
  - Revisit after checkpoint:

---

## 6. Decisions log

Record decisions that materially affect later work.

### Decision template
- Date:
- Topic:
- Decision:
- Reason:
- Revisit trigger:

### Entries
- Date: `2026-04-16`
  - Topic: `Inherited exact-lookup index baseline`
  - Decision: `Treat commit 1bd9ba9 as inherited pre-refactor groundwork. Do not plan idx_system_by_name or idx_station_by_system_name as if they still need first-time justification.`
  - Reason: `The current repo/runtime state already contains that work, and live SQLite query-plan evidence confirms active use of the indexes.`
  - Revisit trigger: `Only if fresh-build or upgrade verification shows schema drift or missing coverage.`

---

## 7. Blockers log

### Blocker template
- Date:
- Blocker:
- Checkpoint affected:
- Severity:
- Needed decision/input:
- Current workaround:

### Entries
- Date: `2026-04-16`
  - Blocker: `First live cold/warm baseline not yet recorded`
  - Checkpoint affected: `A`
  - Severity: `Medium`
  - Needed decision/input: `Run the validated benchmark corpus and write the results into PERF_NOTES`
  - Current workaround: `Use the validated corpus immediately for baseline capture; no further command selection work is required before timing begins`

---

## 8. Completed milestones log

Use this as the short “what is already definitely done” section for quick scanning.

- [x] Milestone: `Inherited schema/index groundwork for exact system and station resolution`
  - Date completed: `2026-03-24`
  - Commit: `1bd9ba9`
  - Notes: `Added idx_system_by_name to the SQLite schema and idx_station_by_system_name to SQLite schema plus ORM metadata; live SQLite evidence at the time and again on 2026-04-16 justified the station composite index.`
- [x] Milestone: `Checkpoint A benchmark corpus validated on live packaged SQLite`
  - Date completed: `2026-04-16`
  - Commit:
  - Notes: `Validated local, market, buy, sell, nav, rares, trade, and short/typical/wide run command shapes against a recently refreshed live SQLite database.`

---

## 9. Quick-start for future sessions

Before starting work, check:

- [ ] Which checkpoint is active
- [ ] Which subtask is active
- [ ] Whether acceptance criteria are already written
- [ ] Whether there is a blocker recorded
- [ ] Whether the rollback point is known
- [ ] Whether `docs/SESSION_HANDOFF_TEMPLATE.md` needs to be filled before stopping

If any of those are missing, fix this document first.
