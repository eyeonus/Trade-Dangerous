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
- Checkpoint: `C — Legacy audit and prune map`
- Subtask: `C1/C3/C4 bounded prune packet and audit-method tightening`
- Owner: `Tromador + ChatGPT`
- Started: `2026-04-18`
- Goal: `in progress — Chapter C resumed after checkpoint B closeout; a false-positive dead-code removal was caught and reverted, the audit method was tightened to one-at-a-time repo-internal caller verification, and a first four-function orphaned-helper prune packet landed.`

### Current blocker
- Status: `[x]`
- Blocker: `No active blocker remains for checkpoint C at this point.`
- Impact: `Work can continue with the next bounded audit target.`
- Needed to unblock: `none`

### Last updated
- Date: `2026-04-18`
- By: `ChatGPT (with runtime verification evidence and local commit work provided by Tromador)`
- Session summary: `Resumed Chapter C, caught and reversed a false-positive removal of CommandEnv.colorize after proving it is still live via dynamic lookup, re-audited the remaining candidates one at a time, removed four orphaned helper methods in 0d8c165, split and closed the X52 issue separately in a0de3a3, cleaned up the run workspace in 4da6695, and landed the Rich/color-path follow-up in 1c12adf.`

### Last known good rollback point
- Commit: `0d8c165`
- Notes: `First re-audited Chapter C prune packet landed: CommandEnv.render, spansh ImportPlugin._upsert_shipyard, spansh ImportPlugin._live_line, and eddblink _collect_station_modified_times removed. CommandEnv.colorize is explicitly excluded after false-positive correction.`

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
- [x] Batch A rollout is rebuild/reset only; in-place index reconciliation is not planned

---

## 3. Checkpoint summary board

- [x] A — Instrumentation and production baselines
- [x] B — Schema Batch A: narrow additive index release
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
- [x] A4. Capture first live baseline
  - Status note: `First live cold/warm baseline captured on 2026-04-17 against the live packaged SQLite database using the validated corpus. All ten commands completed successfully.`
  - Evidence: `docs/PERF_NOTES.md`; `tmp/checkpoint_a_baseline_20260417_143221/summary.csv`
- [x] A5. Capture resolver/query-plan notes
  - Status note: `Live SQLite query plans were captured for exact system lookup, exact station lookup, system/station join lookup, partial system, and partial station.`
  - Evidence: `tools/checkpoint_a_probe.py` output on 2026-04-16

### Notes
- `A5` evidence shows the current live SQLite DB is already using `idx_system_by_name`, `idx_station_by_name`, and `idx_station_by_system_name`.
- This means some older planning assumptions are stale relative to the inherited repo/runtime baseline.
- The benchmark corpus is now validated, and the first live cold/warm baseline was captured on 2026-04-17.
- Memory notes were not captured during this first baseline and remain optional follow-up, not a checkpoint A blocker.

---

## Checkpoint B — Schema Batch A: narrow additive index release

### Goal
Ship the first narrow additive read-performance schema batch through the supported rebuild/reset paths.

### Acceptance criteria
- `idx_system_by_name` exists on SQLite and MariaDB after supported rebuild/reset flows
- fresh DB builds/resets include the Batch A index set
- Batch A scope remains narrow
- optional station composite index is either proven and included, or explicitly deferred
- release communication matches the rebuild-only policy honestly

### Tasks
- [x] B1. Freeze Batch A scope
  - Status note: `Inherited baseline indicates Batch A scope is already narrow: idx_system_by_name plus the proven station composite index, with no wider additive schema batch evidenced.`
  - Evidence: `1bd9ba9`
- [x] B2. Add Batch A index to fresh-build schema
  - Status note: `idx_system_by_name was already present in ORM metadata and was added to the SQLite schema in inherited preparatory work; idx_station_by_system_name is present in ORM metadata and SQLite schema.`
  - Evidence: `1bd9ba9`; `tradedangerous/db/orm_models.py`; `tradedangerous/templates/TradeDangerous.sql`
- [~] B3. Add narrow in-place reconciliation helper
  - Status note: `Not planned. Supported rollout is rebuild/reset via clean import, and later schema breakage makes additive in-place reconciliation unnecessary.`
  - Evidence: `2026-04-17 policy clarification from Stef`
- [~] B4. Wire reconciliation through central lifecycle path
  - Status note: `Not planned for the same reason as B3.`
  - Evidence: `2026-04-17 policy clarification from Stef`
- [x] B5. Verify SQLite fresh-build/reset path
  - Status note: `Verified on 2026-04-17 against the packaged SQLite database after the supported rebuild/reset flow. PRAGMA output showed idx_system_by_name and idx_station_by_system_name, and EXPLAIN QUERY PLAN used idx_system_by_name for exact system lookup plus covering idx_station_by_system_name for exact system/station join lookup.`
  - Evidence: `packaged SQLite runtime output on 2026-04-17 using %LOCALAPPDATA%\TradeDangerous\data\TradeDangerous.db`
- [x] B6. Verify MariaDB fresh-build/reset path
  - Status note: `Verified in practice on 2026-04-17 from the live MariaDB td_live schema: System includes idx_system_by_name and Station includes idx_station_by_system_name, idx_station_by_name, and idx_station_by_system.`
  - Evidence: `live MariaDB schema screenshots for td_live.System and td_live.Station on 2026-04-17`
- [x] B7. Decide on optional composite station index
  - Status note: `Decision already made in inherited preparatory work: include idx_station_by_system_name because live SQLite plan/timing evidence justified it.`
  - Evidence: `1bd9ba9`; live SQLite probe on 2026-04-16
- [x] B8. Write release-note text for Batch A
  - Status note: `Release-note text finalized in the Batch A spec and aligned to the rebuild/reset-only rollout policy.`
  - Evidence: `docs/schema_batch_a_spec.md`

### Notes
- `1bd9ba9` predates the formal refactor session but is part of the inherited baseline and must be treated as such.
- Checkpoint B is now complete under the rebuild/reset-only rollout policy.
- The remaining schema work in later checkpoints is expected to be breaking and rebuild-driven, not additive in-place upgrade work.

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
- Date: `2026-04-17`
  - Topic: `Batch A rollout policy`
  - Decision: `Support rebuild/reset rollout only for Batch A. Do not implement or promise additive in-place reconciliation of existing databases.`
  - Reason: `Users were already directed to use clean import/rebuild, and later refactor stages will introduce breaking schema changes that make long-lived additive upgrade support poor value.`
  - Revisit trigger: `Only if a later release policy explicitly restores support for in-place schema upgrades.`

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
- Date: `2026-04-17`
  - Blocker: `Windows console encoding caused the first post-reboot benchmark attempt to fail when DEBUG output emitted a Unicode arrow`
  - Checkpoint affected: `A`
  - Severity: `Low`
  - Needed decision/input: `Force UTF-8 console/Python settings before rerunning the baseline harness on Windows`
  - Current workaround: `Use chcp 65001 plus PYTHONIOENCODING=utf-8 and PYTHONUTF8=1 for benchmark sessions`
- Date: `2026-04-17`
  - Blocker: `Formal fresh SQLite rebuild/reset verification for Batch A is not yet recorded`
  - Checkpoint affected: `B`
  - Severity: `Medium`
  - Needed decision/input: `Run the supported rebuild/reset flow and inspect the recreated SQLite indexes/query plan`
  - Current workaround: `Source inspection confirms the indexes are present in the template and ORM metadata, but runtime verification is still required before closing B`

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
- [x] Milestone: `Checkpoint A first live cold/warm baseline captured`
  - Date completed: `2026-04-17`
  - Commit:
  - Notes: `Recorded cold and warm timings for all ten benchmark commands from the validated corpus; successful Windows execution required UTF-8 console/Python settings for DEBUG output.`
- [x] Milestone: `Checkpoint B rebuild/reset verification and release-note closeout`
  - Date completed: `2026-04-17`
  - Commit:
  - Notes: `Verified packaged SQLite runtime index presence and query-plan usage after the supported rebuild/reset path, confirmed live MariaDB schema presence for the same Batch A indexes, and finalized release-note text for the rebuild-only rollout policy.`

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
