# REFACTOR_PROGRESS.md
## Trade Dangerous modernization / performance refactor progress tracker

Working repo:
- `Tromador/Trade-Dangerous`

Working line:
- `release/v1` on the fork

Companion repo targets when server/export pipeline work is in scope:
- `Tromador/TradeDangerous-listener`

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
- Status: `[x]`
- Checkpoint: `K — Reduce TradeCalc setup cost (complete — realised by the clean-room planner rewrite, not by incremental narrowing)`
- Subtask: `K closed. K4 answered its own question: the preload-first model was replaced, not tuned. Next up is L (nav/olddata), not yet started.`
- Owner: `Tromador`
- Started: `2026-05-03`
- Goal: `Decide whether the preload-first TradeCalc/TradeDB route model should survive — answered: no. The clean-room planner rewrite (Slices 1–14, docs/Planner/) replaced it; trade run is planner-only, and tradecalc.py / tradedb.py are retired to archive/.`

### Current blocker
- Status: `[ ]`
- Blocker: `None. The K4 question is answered — the preload-first model was replaced by the clean-room planner — so the paused K3/K5/K6/K7 preload tuning is moot, not blocked.`
- Impact: `n/a`
- Needed to unblock: `n/a`

### Last updated
- Date: `2026-06-03`
- By: `Tromador + assistant`
- Session summary: `Checkpoint K closed by the clean-room planner rewrite. trade run is planner-only; the full-galaxy preload model is gone; tradecalc.py / tradedb.py are retired to archive/. Slice 14 landed across eight commits (39828ab2 -> f6958820), the last being the 14D planner cleanup. Full record in docs/Planner/ (SLICE_SUMMARY.md, fourteenth_slice_completion_report.md).`

### Last known good rollback point
- Commit: `ee777adc`
- Notes: `Fixture regenerated with full 172-system list; test workarounds reverted to natural data. All tests passing.`

---

## 2. Programme-wide locked decisions

Mark these only if they are superseded by explicit new evidence and an agreed replacement.

- [x] `Added` will be removed entirely
- [x] `RareItem` will be removed entirely
- [x] Rarity is represented by `Item.rare_station_id IS NOT NULL`
- [x] `is_rare` is convenience logic only, not stored schema
- [x] Work happens directly on `Tromador/Trade-Dangerous:release/v1`
- [x] No second refactor branch inside the fork unless later forced
- [x] Batch A rollout is rebuild/reset only; in-place index reconciliation is not planned
- [x] Checkpoint E is rebuild/reset only; no migration/backfill or old-schema assistance is planned
- [x] `trade rares` is retired; remaining useful rare lookup moves into `trade buy` filtering
- [x] `Festive Gifts` is excluded from canonical rare handling
- [x] The preload-first `trade run` model is retired; `trade run` is served by the clean-room planner querying the database directly (Checkpoint K)

---

## 3. Checkpoint summary board

- [x] A — Instrumentation and production baselines
- [x] B — Schema Batch A: narrow additive index release
- [x] C — Legacy audit and prune map
- [x] D — Remove `Added`
- [x] E — Collapse `RareItem` into `Item`
- [x] F — Resolver contract and parity tests
- [x] G — Resolver-first execution flow
- [x] H — Migrate `local`
- [x] I — Migrate `market`, `buy`, `sell`
- [x] J — Split `TradeDB` by capability
- [x] K — Reduce `TradeCalc` setup cost (realised by the clean-room planner rewrite)
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
  - Evidence: `1bd9ba9`; live SQLite probe on 2026-04-16`
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
Classify and remove dead repo-internal code before broader structural work.

### Acceptance criteria
- CLI and GUI entry roots are explicitly identified and used consistently for audit work
- reachability evidence exists for dynamic or uncertain paths
- suspicious candidates are classified into remove / archive / keep / stay-of-execution
- confirmed dead helpers are removed in bounded packets and dead whole modules are archived

### Tasks
- [x] C1. Inventory live entry points
  - Status note: `CLI root fixed as trade.py -> tradedangerous.cli.main(...) and GUI root fixed as tradegui.py -> tradedangerous.guiapp.main.main(...). These roots were then used consistently for the Chapter C audit.`
  - Evidence: `in-session Chapter C audit method and Codex callable reachability report, validated by local grep review on 2026-04-19`
- [x] C2. Add temporary tracing mode or equivalent reachability evidence
  - Status note: `Equivalent evidence was used instead of a dedicated tracing mode: one-symbol-at-a-time caller search, dynamic lookup checks, live control-flow review, targeted runtime verification where needed, and a full Codex-assisted callable reachability pass.`
  - Evidence: `false-positive correction for CommandEnv.colorize; Chapter C Codex audit report; local grep verification on 2026-04-18 and 2026-04-19`
- [x] C3. Build first audit map
  - Status note: `A bounded prune map was built and then expanded through callable inventory, candidate review, and repo-internal caller verification. The earlier false five-function packet was discarded after the colorize false positive; the tightened method then produced valid bounded prune packets.`
  - Evidence: `0d8c165`; Chapter C audit report; ae6e942`
- [x] C4. Quarantine obvious non-runtime junk
  - Status note: `Confirmed dead helpers were removed from live modules in small packets, and dead legacy modules/deprecated tooling were moved under archive. Explicit keeps and stays of execution were recorded instead of being pruned opportunistically.`
  - Evidence: `0d8c165`; ae6e942; archive moves for db/adapter.py, prices.py, mapping.py, edscupdate.py, edsmupdate.py, submit-distances.py, misc/clipboard.py, misc/edsc.py, plugins/edcd_plug.py`

### Notes
- Chapter C started with a false-positive removal of `CommandEnv.colorize()`. That was corrected after proving the symbol remained live via dynamic lookup in `tradecalc.Route.detail()`. From that point onward, the audit standard was tightened to repo-internal caller proof, dynamic lookup checks, and bounded symbol packets.
- Side issues surfaced during the audit but were handled separately and are closed: X52 behaviour (`a0de3a3`) and the Rich / colour-path split (`1c12adf`). These do not remain open Chapter C work.
- First valid Chapter C prune packet landed in `0d8c165`, removing `CommandEnv.render`, `spansh ImportPlugin._upsert_shipyard`, `spansh ImportPlugin._live_line`, and `eddblink _collect_station_modified_times`.
- Chapter C closeout landed in `ae6e942`, removing confirmed dead helpers from live modules and archiving dead legacy modules/deprecated tooling.
- Explicitly retained after review: `tradedangerous/commands/TEMPLATE.py`, `tradedangerous/db/paths.py::get_sqlite_db_path`, `tradedangerous/tradedb.py::TradeDB.lookupAdded`, `tradedangerous/tradeorm.py::TradeORM.commit`, and `tradedangerous/fs.py::copyallfiles`.
- Checkpoint C is complete.

---

## Checkpoint D — Remove `Added`

### Goal
Delete the obsolete `Added` table and all live references.

### Acceptance criteria
- fresh DB has no `Added`
- no supported command/import/export path relies on `Added`
- no live ORM/runtime references remain
- release/docs state plainly that a fresh DB rebuild is required for the breaking schema change

### Tasks
- [x] D1. Remove `Added` from ORM and canonical schema
  - Status note: `Added model removed from ORM metadata, System.added_id removed from ORM metadata, Added table removed from the canonical SQLite schema, and System.added_id removed from the canonical SQLite schema.`
  - Evidence: `accepted edits to tradedangerous/db/orm_models.py and tradedangerous/templates/TradeDangerous.sql, validated by fresh MariaDB rebuild on the test server on 2026-04-20`
- [x] D2. Remove template/import/export plumbing
  - Status note: `Added removed from TradeDB.defaultTables and bootstrap copying, Added import helper/cache handling removed, templates/Added.csv removed from package data and deleted from the repo, and the exported System.csv contract now omits the obsolete added_id column.`
  - Evidence: `accepted edits to tradedangerous/tradedb.py, tradedangerous/cache.py, pyproject.toml, and deletion of tradedangerous/templates/Added.csv; live test-server export confirmed System.csv header 'unq:system_id,name,pos_x,pos_y,pos_z,modified' on 2026-04-20`
- [x] D3. Remove live runtime references and wrapper dependencies
  - Status note: `SA_Added import usage removed, TradeDB.lookupAdded removed, the legacy System.addedID wrapper field/signature removed, _loadSystems() no longer depends on SA_System.added_id, addLocalSystem() no longer writes added_id, and spansh_plug.py no longer seeds or writes Added.`
  - Evidence: `accepted edits to tradedangerous/tradedb.py and tradedangerous/plugins/spansh_plug.py, validated by successful spansh seed and listener startup/live ingestion against the post-D schema on 2026-04-20`
- [~] D4. Add schema sanity detection / rebuild path
  - Status note: `Not planned. Checkpoint D is a breaking schema change and v13 simply expects a fresh rebuilt database; no code was added to detect or assist obsolete v12 schemas.`
  - Evidence: `2026-04-20 checkpoint D policy clarification from Tromador`
- [x] D5. Update tests, fixtures, docs
  - Status note: `Checkpoint D was validated end-to-end on the test server and client path: fresh MariaDB rebuild, spansh seed, listener startup/live ingestion, published CSV export, clean eddblink import from the test server, and trade run smoke tests in both CLI and GUI. The progress tracker has been updated to reflect D closeout.`
  - Evidence: `2026-04-20 local/test validation on the mort-clone server and Windows client`

### Notes
- Checkpoint D started and was closed out on 2026-04-20.
- This checkpoint deliberately does not include migration handling, old-schema detection, or runtime babysitting for pre-D databases.
- Supported operator/user action is a normal rebuild/clean import on upgrade.
- The server/export validation surface for this checkpoint included the companion repo `Tromador/TradeDangerous-listener`.

---

## Checkpoint E — Collapse `RareItem` into `Item`

### Goal
Remove standalone rares table, model canonical rarity through `Item.rare_station_id`, and retire the dedicated rare subsystem.

### Acceptance criteria
- fresh DB has no `RareItem`
- v13 expects a fresh rebuilt database; no migration/backfill or old-schema assistance is provided
- rarity is modelled by `Item.rare_station_id`, with `is_rare` convenience logic only
- canonical rare identity is item-side; `StationItem` is live market overlay only
- `trade rares` is retired and any still-useful rare lookup behaviour is covered by `trade buy` filtering
- importer/cache/export logic no longer treats rares as a separate table
- `Festive Gifts` is excluded from canonical rare handling

### Tasks
- [x] E1. Add `Item.rare_station_id` and only genuinely needed parity fields
  - Status note: `Landed in ORM and canonical SQLite schema. Canonical rarity is now item-side via Item.rare_station_id, with Station as the FK target and restrictive delete semantics.`
  - Evidence: `tradedangerous/db/orm_models.py`; `tradedangerous/templates/TradeDangerous.sql`
- [x] E2. Add computed `is_rare` convenience logic if useful
  - Status note: `Landed as Item.is_rare convenience logic only; no persisted is_rare column was added.`
  - Evidence: `tradedangerous/db/orm_models.py`
- [x] E3. Remove dedicated rare command surface and cover any still-useful behaviour through `trade buy` filtering
  - Status note: `trade rares has been retired from the live command registry, and trade buy now supports --rare filtering, rare browse mode, and the associated command-surface guards.`
  - Evidence: `tradedangerous/commands/__init__.py`; `tradedangerous/commands/buy_cmd.py`; archived `tradedangerous/commands/rares_cmd.py`
- [x] E4. Remove importer/cache special cases and rare-only export/template plumbing
  - Status note: `All plumbing removed: TradeDB bootstrap no longer carries RareItem, Spansh rare enrichment writes Item.rare_station_id, templates/RareItem.csv evacuated from repo and package data, RareItem cache header special-casing removed. spansh_plug.py: sentinel station_id guard for 0xFFFFFFFFFFFFFFFF overflow added, skip_galaxy + file= silent failure fixed, listings.csv/listings-live.csv moved out of public_csv (listener-owned). eddblink_plug.py: stale 'skip rare items' comment updated.`
  - Evidence: `tradedangerous/tradedb.py`; `tradedangerous/plugins/spansh_plug.py`; `tradedangerous/plugins/eddblink_plug.py`; `tradedangerous/cache.py`; `pyproject.toml`; `17bc9ade`; `99e2d710`
- [x] E5. Remove `RareItem` schema/runtime/docs/tests
  - Status note: `RareItem fully eradicated from ORM, schema, docs, and GUI. docs/ORM_Schema_reference.md and docs/db_engine_reference.md updated to reflect Checkpoint E model. GUI RaresWorkspace removed; buy --rare checkbox wired into Buy workspace extended options (f57c411). supply_units > 0 filter added to buy_cmd --rare path. End-to-end validation passed: spansh seed → listener --no-update --export-live-now → eddblink clean import → trade buy --rare returns 142 rares.`
  - Evidence: `tradedangerous/db/orm_models.py`; `tradedangerous/templates/TradeDangerous.sql`; `docs/ORM_Schema_reference.md`; `docs/db_engine_reference.md`; `tradedangerous/commands/buy_cmd.py`; `f57c411`; live MariaDB validation on 2026-04-26
- [x] E6. Encode the `Festive Gifts` exclusion narrowly
  - Status note: `Landed in the Spansh rare-enrichment path so Festive Gifts is excluded from canonical rare handling.`
  - Evidence: `tradedangerous/plugins/spansh_plug.py`

### Notes
- Canonical rarity is item-side: `Item.rare_station_id` answers whether an item is rare and identifies its canonical source station.
- `StationItem` is live market overlay only. A live row for a rare belongs in `StationItem` like any other commodity, but absence of a `StationItem` row does not disprove canonical rarity.
- `trade rares` is retired. The surviving useful rare lookup behaviour now lives on the `trade buy` path.
- Checkpoint E is rebuild/reset only and deliberately does not include migration handling, backfill, old-schema detection, or runtime babysitting for pre-E databases.
- Checkpoint E is complete. End-to-end validation passed on 2026-04-26.

---

## Checkpoint F — Resolver contract and parity tests

### Goal
Define and lock lookup semantics before broad command migration.

### Acceptance criteria
- resolver contract doc exists and is populated
- parity tests exist
- exact/common place resolution works without full `TradeDB.load()`

### Tasks
- [x] F1. Write resolver contract document
  - Status note: `RESOLVER_CONTRACT.md written from full code-read of tradedb.py and tradeexcept.py. Covers normalization pipeline, listSearch, lookupSystem, lookupPlace (fast/slow paths), lookupStation, lookupItem, error types, behaviour classification, parity matrix, and fixture requirements. §13 corrected after F2 testing revealed one wrong matrix entry.`
  - Evidence: `docs/RESOLVER_CONTRACT.md`; `9faa1ec`
- [x] F2. Convert legacy behavior into tests
  - Status note: `53 parity tests covering normalization, lookupSystem (including @N), lookupPlace fast and slow paths, lookupStation, lookupItem, and @N boundary/negative cases. v13 fixtures regenerated from sol-25ly crop; Create_Fixtures.md procedure documented.`
  - Evidence: `tests/test_resolver_parity.py`; `95d5538`; `8a9cac1`
- [x] F3. Implement exact system lookup
  - Status note: `lookup_system() rewritten as self-contained ORM query. _split_system_index() added. Exact match via CIString (NOCASE/utf8mb4_unicode_ci). @N disambiguation ordered by (pos_x, pos_y, pos_z, system_id). LookupError on no match, AmbiguityError on duplicate name, TradeException on out-of-range @N. TypeError on non-string. Slash and partial matching explicitly excluded. 9 new tests.`
  - Evidence: `tradedangerous/tradeorm.py`; `tests/test_tradeorm_lookup_db.py`
- [x] F4. Implement exact station and place lookup
  - Status note: `lookup_station() rewritten: Station/System pass-through, TypeError for non-str, scoped lookup via system arg, dual-scan (exact station + exact system) with contract-correct reconciliation. lookup_place() rewritten: System/Station pass-through, TypeError, fast path (bare/@name via lookup_system + station fallback; @ suppresses station fallback), slow path (raw exact system query, NOT lookup_system — @N stays out of compound syntax), unknown-system global fallback, duplicate-system combined candidates. _system_lookup() and _station_lookup() removed. 30 new tests (TestLookupStation + TestLookupPlace). All 43 ORM tests + 53 parity tests passing.`
  - Evidence: `tradedangerous/tradeorm.py`; `tests/test_tradeorm_lookup_db.py`
- [x] F5. Add ambiguity and `@N` handling
  - Status note: `TestAmbiguityAndAtNDisambiguation added (7 tests) plus torm_with_crossname_ambiguity fixture. Covers: lookup_place fast-path AmbiguityError propagation, @N disambiguation (@1/@2), @ prefix + @N, out-of-range @N → TradeException, lookup_station @N not stripped (LookupError), dual-scan cross-name AmbiguityError. No tradeorm.py changes needed — all behaviours already correct from the exact-lookup implementation.`
  - Evidence: `tests/test_tradeorm_lookup_db.py`; `bfccd34c`
- [x] F6. Add partial matching carefully
  - Status note: `Module-level _normalize_trans/_trim_trans added to tradeorm.py. Four static helpers: _prefix_of, _list_search (mirrors listSearch: exact/word/partial tiers), _place_lookup (mirrors _lookup: exact/close/word/any tiers with space-based word boundaries), _resolve_place_tiers. All five unscoped candidate queries use two-step ILIKE: prefix ILIKE first (index-friendly), then interior ILIKE ('%token%') if prefix returns nothing. lookup_system partial fallback passes the full original name (including any @N) to both _prefix_of and _list_search — @N is treated as a literal search string in the partial path per documented legacy behaviour. lookup_station (scoped) uses all-stations-in-system + _list_search; (unscoped) uses two-step ILIKE for both station and system candidates. lookup_place fast-path station fallback: two-step ILIKE + _list_search. lookup_place slow-path: system part uses two-step ILIKE + _place_lookup; scoped station part uses all stations in matched systems; global station part uses two-step ILIKE + _place_lookup. Punctuation-normalised interior matches (e.g. 'CD37' → 'CD-37 15492') not supported without a normalised column — DELIBERATE ORM CHANGE, recorded in RESOLVER_CONTRACT.md. TestPartialMatching has 16 tests. 177 total tests passing on 2026-04-29.`
  - Evidence: `tradedangerous/tradeorm.py`; `tests/test_tradeorm_lookup_db.py`; `docs/RESOLVER_CONTRACT.md`; commits `493a2ae`, `1896bdaf`; 177 tests passing on 2026-04-29`

### Notes
- Punctuation-normalised interior substring matching (e.g. `"CD37"` → `"CD-37 15492"`) is a deliberate unsupported case. The ORM searches raw stored names; without a normalised generated column, stage-1 punctuation deletion cannot be applied on the DB side. Recorded in RESOLVER_CONTRACT.md as a DELIBERATE ORM CHANGE.

---

## Checkpoint G — Resolver-first execution flow

### Goal
Resolve command inputs before heavy legacy load.

### Acceptance criteria
- common command argument resolution works without full `TradeDB.load()`
- CLI and GUI follow the same resolution path
- no behavior regression in argument handling

### Tasks
- [x] G1. Add capability-style command model
  - Status note: Accepted after review. Needs enum (NOTHING/RESOLVER/LEGACY_HANDLE/FULL_LEGACY); wantsTradeDB fallback preserved; runtime construction matches tier; CLI tests cover all four tiers.
  - Evidence: commits 3bd0bb57, f2c9719f, 1a20e8a5; 269 tests passing.
- [x] G2. Move `--near`, `--from`, `--to` to resolver path
  - Status note: Accepted after review. checkFromToNearORM() resolves starting/ending/near only; origin/dest left command-owned. Regression test confirms trade_cmd shortcut fields are not pre-resolved.
  - Evidence: commits fb700a54, 305e2fa6; 271 tests passing.
- [x] G3. Move `--avoid` and `--via` to resolver path
  - Status note: Accepted after review and fix. checkAvoidsORM() resolves items via lookup_item() (full catalogue scan for normalised equivalence) then places via lookup_place(); normalize_str() exact check suppresses place lookup on normalised-exact item match. checkViasORM() resolves each via as a place with CommandLineError on not-found. Both called from run() for RESOLVER-tier commands. normalize_str() added to TradeORM as public two-stage normalisation helper.
  - Evidence: commits be8a6fb7, 2c697f35; 290 tests passing.
- [x] G4. Keep `TradeDB(load=False)` only as transitional shim
  - Status note: station_cmd and shipvendor_cmd moved from wantsTradeDB=False (LEGACY_HANDLE) to Needs.NOTHING — both are deprecated no-ops that touch no backend. LEGACY_HANDLE docstring updated to make transitional intent explicit. Needs.NOTHING test extended to cover all three no-op commands.
  - Evidence: tradedangerous/commands/station_cmd.py; tradedangerous/commands/shipvendor_cmd.py; tradedangerous/commands/commandenv.py; tests/test_commandenv.py
- [x] G5. Mirror the same flow in GUI
  - Status note: _execute_td_command updated to mirror CLI capability-aware backend selection. TradeORM import added. Finally block closes torm independently when not aliased as tdb. Four unit tests covering all four tiers including NOTHING.
  - Evidence: tradedangerous/guiapp/td_exec.py; tests/test_gui_td_exec.py; commits 4bc36483, 104f6d68

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
- [x] H1. Port origin resolution to resolver
  - Status note: `needs = Needs.RESOLVER` replaces `wantsTradeDB=True`. `checkFromToNearORM()` resolves `--near` to an ORM System object before `run()` is entered.
  - Evidence: `tradedangerous/commands/local_cmd.py`; commit `45148695`
- [x] H2. Replace full legacy range iteration
  - Status note: SQL bounding-box pre-filter (`BETWEEN` on pos_x/y/z) followed by Python sphere check replaces `genSystemsInRange()`. No full system preload required.
  - Evidence: `tradedangerous/commands/local_cmd.py`; commit `45148695`
- [x] H3. Push station filters into SQL
  - Status note: All flag filters pushed to SQL. Fleet/odyssey resolved via `type_id` (mirrors `_loadStations` constants). `--trading` uses EXISTS subquery over StationItem. Age/count fetched in a single StationItem aggregate, gated on `need_age`.
  - Evidence: `tradedangerous/commands/local_cmd.py`; commit `45148695`
- [x] H4. Restore render parity
  - Status note: All ORM attribute names corrected throughout render. Module-level helpers added for `_dist_from_star()`, `_fleet_state()`, `_odyssey_state()`. One deliberate ORM behaviour change: `Mkt` column reads `station.market` directly from DB; legacy `_loadStations()` coerced it to `Y` when `itemCount > 0`. The `--trading` filter is correct and unaffected; only the rendered `Mkt` display differs for stations where the flag and data disagree.
  - Evidence: `tradedangerous/commands/local_cmd.py`; commit `45148695`
- [x] H5. Benchmark before/after
  - Status note: 0.85s warm vs 6.98s warm baseline. ~8× improvement. User description: "effectively instant."
  - Evidence: `docs/PERF_NOTES.md`; live SQLite timing on 2026-04-30

### Notes
- The `Mkt` column render parity mismatch (H4 note above) is a deliberate ORM behaviour change, not a structural failure. The filter path is correct; only the display of the raw DB flag differs from the legacy coerced value for edge-case stations.

---

## Checkpoint I — Migrate `market`, `buy`, `sell`

### Goal
Move obvious preload-bound trading commands off full preload.

### Acceptance criteria
- each command runs without full legacy preload
- each command has explicit before/after timing evidence
- GUI path still uses the same core logic

### Tasks
- [x] I1. Build lightweight item lookup service
  - Status note: `Verified lookup_item() is sufficient for item-name-resolution in sell and buy. Added lookup_category() (exact CI + _list_search fallback, returns orm.Category with items relationship) and item_by_id() (PK lookup, LookupError on miss) to TradeORM. 10 new tests.`
  - Evidence: `tradedangerous/tradeorm.py`; `tests/test_tradeorm_lookup_db.py`; commits `cc054bb4`, `0b8384b6`
- [x] I2. Migrate `market`
  - Status note: `market_cmd.py migrated to Needs.RESOLVER. tdb.session used throughout; station_id, item_by_id(), ORM attribute names in sort/render. Polish: early no-rows exit; context-aware filtered-empty errors include origin.name. Smoke-tested live: instantaneous for basic queries, 578ms warm for --detail. 377 tests passing.`
  - Evidence: `tradedangerous/commands/market_cmd.py`; commits `5542bfd6`, `91ec8160`
- [x] I3. Migrate `buy`
  - Status note: `buy_cmd.py migrated to Needs.RESOLVER. lookup_ship() added to TradeORM. Cold-start regression fixed by constraining near-system searches before StationItem/ShipVendor probing, applying --age during StationItem lookup, removing unconditional station-wide age aggregation, chunking station hydration, and tolerating unknown ship costs during sorting. Canonical buy cold-ish timing now 3.88s vs 6.79s legacy baseline and ~13.3s regressed I3 state. Ship near Sol cold-ish timing now 1.51s. pytest clean.`
  - Evidence: `tradedangerous/commands/buy_cmd.py`, `tradedangerous/tradeorm.py`; commits `ea279202`, `8c70847f`, `759e96d5`
- [x] I4. Migrate `sell`
  - Status note: `sell_cmd.py migrated to Needs.RESOLVER. Spatial bounding-box materialises nearby station IDs before StationItem is queried. Age, demand, and price filters pushed into SQL. Station hydration chunked at 900 via joinedload. Legacy station wrapper methods replaced with ORM attributes and type_id-based helpers. Context-aware NoDataError includes item name and near-system. Cold 7.29s → 1.23s (~6×), warm 7.77s → 0.82s (~9.5×). pytest clean.`
  - Evidence: `tradedangerous/commands/sell_cmd.py`; commits `8858ba45`, `af6e7327`
- [x] I5. Benchmark each command separately
  - Status note: `Before/after timing evidence recorded for each migrated command: market (instantaneous warm / 578ms --detail), buy (6.79s → 3.88s cold, 7.10s → ~1.0s warm), sell (7.29s → 1.23s cold, 7.77s → 0.82s warm).`
  - Evidence: `docs/PERF_NOTES.md`

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
- [x] J1. Create explicit sub-loaders
  - Status note: `_loadStationShell(), _loadStationSummaries(), and updated _loadStations() wrapper landed. load() calls sub-loaders directly.`
  - Evidence: `ded4c634`
- [x] J2. Separate station shell from station summaries
  - Status note: `Shell phase creates Station wrappers with itemCount=0/dataAge=None. Summary phase enriches from StationItem aggregate. Clean boundary, each phase has its own session and timer.`
  - Evidence: `ded4c634`
- [x] J3. Audit remaining `TradeDB` callers by capability
  - Status note: `In-session capability audit of olddata, nav, and run. olddata: needs systems + station shell only (no summaries/categories/items). nav: needs shell for --stations; summaries only for itemDataAgeStr/itemCount; --refuel-jumps uses system.stations (shell sufficient); categories/items never needed. run: full load required — checkStationSuitability() needs itemCount; TradeCalc needs itemByID; all sub-loaders justified.`
  - Evidence: `In-session code read of olddata_cmd.py, nav_cmd.py, run_cmd.py, 2026-05-03`
- [x] J4. Move at least one easy caller to partial load
  - Status note: `olddata moved to Needs.LEGACY_HANDLE. preload() hook added to CommandEnv.run() (fires after tdb assignment, before resolution checks). olddata.preload() calls reloadCache()/_loadSystems()/_loadStationShell(). Summaries, categories, and items not loaded. Smoke-tested: default, --limit, --near, --route, pad/no-planet/ls filters all pass. 385 tests passing.`
  - Evidence: `5fa20c80`

### Notes
- Debug timing output changed: previously one "Loaded N Stations" line spanning both phases; now separate shell and summary lines. Observable only under debug mode. Non-blocking deliberate change.
- load() no longer routes through _loadStations(), so monkeypatching _loadStations() will not intercept load(). _loadStations() wrapper is retained for any direct callers. Test updated accordingly.
- preload() hook in CommandEnv.run() is generic: any command module that defines a callable `preload` will have it invoked before resolution checks. This is broader than olddata only and is now part of the command lifecycle contract. Documenting or testing this explicitly is deferred but flagged.

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
- Checkpoint K's original goal was wholly replaced with a complete rewrite of `trade run`
- tradedb.py and tradecalc.py were retired and archived
- tradedangerous/planner contains the new code
- this major rewrite was fully documented under docs/Planner

### Follow-up: outfitting-table drop and SQLite↔ORM reconciliation
- Schema cleanup riding on the rebuild (not part of the `trade run` planner): the
  outfitting tables `Upgrade`, `UpgradeVendor`, and the `FDevOutfitting` EDCD bridge
  were dropped. No command ever queried them — `UpgradeVendor` was a 2014 `dbimport`
  placeholder for a `buy --upgrade` mode that was never built, and at ~3.6 GiB it
  cost hours of import time. Ships (`Ship`/`ShipVendor`/`FDevShipyard`) and the
  `Station.outfitting` Y/N flag are kept.
- Removed from: the SQLite template, the ORM models, the spansh and eddblink
  importers, and the buildcache/CSV glue. The listeners drive those plugins rather
  than the tables directly, so they needed no change. (commits `ac2d2669`, `cea68d0c`)
- SQLite template reconciled with the ORM in the same pass: the two previously
  ORM-only indexes (`idx_category_by_name`, `idx_item_by_category`) added to the
  template, name columns widened to `VARCHAR(128)`, `FDevShipyard.id` made a
  PRIMARY KEY, and the unused `StationBuying`/`StationSelling` views dropped. SQLite
  effects are cosmetic; the value is keeping the two hand-maintained schemas in step
  so a consequential drift is less likely to slip through. (commit `6e5319d0`)
- Docs updated: `docs/ORM_Schema_reference.md`, `docs/db_engine_reference.md`.

---

## Checkpoint L — Migrate remaining legacy command surfaces

### Goal
Finish the main command migration set without turning command migration into a generic command-framework rewrite.

### Acceptance criteria
- `olddata` and `nav` no longer depend on full preload
- any remaining rare lookup behaviour uses the post-E `buy` path rather than a dedicated `rares` command
- `trade direct` exists as the preferred successor to `trade trade`
- `trade trade` remains available as a compatibility alias unless an explicit removal decision is recorded
- `trade direct` is implemented as a direct market comparison command, not as `trade run`, not as `trade run --direct`, and not as a planner mode
- zero-valued range arguments remain valid explicit user input where the command supports them
- remaining monolithic `TradeDB.load()` callers are few and justified

### Tasks
- [ ] L1. Migrate `olddata`
  - Status note:
  - Evidence:
- [ ] L2. Migrate `nav`
  - Status note:
  - Evidence:
- [ ] L3. Complete post-E rare lookup cutover on `buy`
  - Status note:
  - Evidence:
- [ ] L4. Refactor `trade trade` into `trade direct`
  - Status note:
  - Evidence:
- [ ] L5. Audit `--ly` / `--max-link-ly` zero-value fallback semantics
  - Status note:
  - Evidence:
- [ ] L6. Re-evaluate remaining full `TradeDB.load()` callers
  - Status note:
  - Evidence:

### Notes
- `trade rares` is retired under the locked Checkpoint E design.
- `trade direct` is `trade trade` v2: a direct market comparison command for known endpoints. (https://github.com/eyeonus/Trade-Dangerous/issues/241)
- `trade direct` must not be used as a reason to merge, replace, or delay `trade run --direct`.
- `--ly 0` and equivalent zero-range inputs are explicit user intent, not absence. Audit truthiness fallbacks such as `cmdenv.maxLy or cmdenv.maxLinkLy` and use explicit `is not None` fallback semantics where affected. (https://github.com/eyeonus/Trade-Dangerous/issues/267)

---

---

## Checkpoint M — GUI session reuse and cache discipline

### Goal
Recover “load once, answer many questions” only where it belongs: GUI session scope.

Stef random note to please remind him: Add copy from render.

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
- Date: `2026-04-19`
  - Topic: `Chapter C dead-code standard`
  - Decision: `Judge dead code by repo-internal reachability. Docs, exported surface, and stale compatibility intent do not preserve code by themselves. Test-only utilities may still be kept deliberately when they remain useful to the suite.`
  - Reason: `The audit needed an explicit standard to stop dead-code decisions drifting into hypothetical external consumers or stale documentation.`
  - Revisit trigger: `Only if the repo later adopts a formal supported external API policy for these surfaces.`
- Date: `2026-04-20`
  - Topic: `Checkpoint D old-schema handling`
  - Decision: `Do not add old-schema detection, migration logic, or runtime assistance for pre-D databases. v13 simply expects a fresh rebuilt database.`
  - Reason: `Checkpoint D is a deliberate breaking schema change and the supported user/operator workflow is already a normal rebuild/clean import.`
  - Revisit trigger: `Only if release policy later changes to require explicit compatibility handling for obsolete local databases.`
- Date: `2026-04-20`
  - Topic: `Companion repo scope for server/export validation`
  - Decision: `Treat Tromador/TradeDangerous-listener as a companion target whenever schema or published CSV contracts are being validated on the server side.`
  - Reason: `Checkpoint D proved that server-side spansh/import/export and listener workflows are part of the real validation surface even when the schema changes are implemented in the main Trade-Dangerous repo.`
  - Revisit trigger: `Only if the server/listener pipeline is folded back into the main repo or replaced entirely.`
- Date: `2026-04-21`
  - Topic: `Checkpoint E rare model and rollout`
  - Decision: `Checkpoint E is a rebuild/reset-only simplification checkpoint. Remove RareItem entirely, store canonical rarity only as Item.rare_station_id, and do not add migration/backfill or old-schema assistance.`
  - Reason: `Current command and data needs no longer justify preserving the historical RareItem model, and current market import already treats rares as ordinary commodities when live data is present.`
  - Revisit trigger: `Only if later product or release policy explicitly restores a requirement for old-schema compatibility or rich rare-only metadata.`
- Date: `2026-04-21`
  - Topic: `Rare command surface`
  - Decision: `Retire trade rares and move any still-useful rare lookup behaviour into trade buy filtering.`
  - Reason: `The remaining useful rare lookup behaviour is buy-shaped, and canonical rarity belongs on Item rather than in a dedicated rare subsystem.`
  - Revisit trigger: `Only if a later command review produces a concrete user need that cannot be served cleanly through buy-side filtering.`
- Date: `2026-04-21`
  - Topic: `Festive Gifts exception`
  - Decision: `Exclude Festive Gifts from canonical rare handling.`
  - Reason: `Festive Gifts is a Frontier seasonal/event-specific commodity with bespoke behaviour and should not distort normal rare modelling.`
  - Revisit trigger: `Only if Frontier later turns Festive Gifts into a normal always-available rare commodity, which is not the current game behaviour.`

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
- Date: `2026-04-20`
  - Blocker: `Canonical System.csv source/header for Checkpoint D has not yet been confirmed in-session`
  - Checkpoint affected: `D`
  - Severity: `Low`
  - Needed decision/input: `Confirm the current System.csv header/source before finalizing the remaining import-surface cleanup`
  - Current workaround: `Continue repo-owned Added removal work first and leave the live System.csv confirmation until the code and docs packets are finished`

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
- [x] Milestone: `Checkpoint C legacy audit and prune closeout`
  - Date completed: `2026-04-19`
  - Commit: `ae6e942`
  - Notes: `Corrected an early false positive, tightened the audit method to repo-internal caller proof plus dynamic checks, removed confirmed dead helpers from live modules in bounded packets, and archived dead legacy modules/deprecated tooling.`
- [x] Milestone: `Checkpoint D Added removal validated end-to-end`
  - Date completed: `2026-04-20`
  - Commit:
  - Notes: `Validated fresh MariaDB rebuild, spansh seed, post-D System.csv export shape, listener startup/live ingestion, clean eddblink import from the test server, and trade run smoke tests in both CLI and GUI with Added removed from the schema and runtime paths.`
- [x] Milestone: `Checkpoint E RareItem collapse validated end-to-end`
  - Date completed: `2026-04-26`
  - Commit: `f57c411` (GUI closeout); `99e2d710` (importer/cache plumbing)
  - Notes: `RareItem fully removed from schema, ORM, importer, cache, export, and GUI. Sentinel station_id guard added for 0xFFFFFFFFFFFFFFFF overflow in Spansh dump. skip_galaxy + file= silent failure fixed. trade buy --rare validated with supply_units > 0 filter; returns 142 rares on test MariaDB. GUI RaresWorkspace removed; Rares only checkbox wired into buy workspace.`
- [x] Milestone: `Checkpoint F resolver contract and parity tests complete`
  - Date completed: `2026-04-29`
  - Commit: `1896bdaf` (partial matching fixes); `1ca25bc4` (test cleanup)
  - Notes: `RESOLVER_CONTRACT.md written and locked. 53 legacy parity tests. TradeORM lookup_system/station/place all implement exact + partial matching with two-step ILIKE candidate narrowing and Python-side tier matching mirroring the legacy resolver. 177 tests passing.`
- [x] Milestone: `Checkpoint G complete — resolver-first execution flow`
  - Date completed: `2026-04-30`
  - Commit: `104f6d68` (G5); `0f785462` (G4); `2c697f35` (G3); `305e2fa6` (G2); `1a20e8a5` (G1)
  - Notes: `G1: Needs capability enum (NOTHING/RESOLVER/LEGACY_HANDLE/FULL_LEGACY). G2: --near/--from/--to resolved via checkFromToNearORM(). G3: --avoid/--via resolved via checkAvoidsORM()/checkViasORM(); normalize_str() added to TradeORM. G4: station_cmd and shipvendor_cmd moved from LEGACY_HANDLE to Needs.NOTHING; LEGACY_HANDLE docstring clarified as transitional shim only. G5: GUI _execute_td_command mirrors CLI capability-aware backend selection; four unit tests covering all four tiers.`
- [x] Milestone: `Checkpoint H complete — local migrated to RESOLVER tier`
  - Date completed: `2026-04-30`
  - Commit: `45148695`
  - Notes: `local_cmd.py rewritten: SQL bounding-box + Python sphere check replaces genSystemsInRange(); all station filters pushed to SQL; fleet/odyssey via type_id; --trading via EXISTS; age/count via StationItem aggregate. 294 tests passing. H5 benchmark: 0.85s warm vs 6.98s warm baseline (~8×). Deliberate ORM behaviour change: Mkt display reads raw station.market; legacy coerced to Y when itemCount > 0. --trading filter is correct and unaffected.`
- [x] Milestone: `Checkpoint I complete — market, buy, sell migrated to RESOLVER tier`
  - Date completed: `2026-05-03`
  - Commit: `af6e7327` (sell closeout); `759e96d5` (buy cold-path fix); `91ec8160` (market polish)
  - Notes: `market: effectively instantaneous warm, 578ms for --detail. buy: 6.79s → 3.88s cold, 7.10s → ~1.0s warm; cold-start regression during I3 fixed by spatial candidate narrowing before StationItem probe. sell: 7.29s → 1.23s cold, 7.77s → 0.82s warm. All three commands on Needs.RESOLVER; no full TradeDB.load() invoked. pytest clean throughout.`
- [x] Milestone: `Checkpoint J complete — TradeDB split by capability; partial load proven`
  - Date completed: `2026-05-03`
  - Commit: `ded4c634` (J1/J2); `5fa20c80` (J3/J4)
  - Notes: `_loadStations() split into _loadStationShell() and _loadStationSummaries(). load() calls sub-loaders directly. Capability audit of olddata/nav/run confirmed olddata as the easy partial-load target. olddata moved to LEGACY_HANDLE; preload() hook added to CommandEnv.run(). olddata loads systems + station shell only; summaries/categories/items skipped. All smoke tests and 385 pytest tests passing.`
- [x] Milestone: `Checkpoint K2A complete — station type registry and settlement filter`
  - Date completed: `2026-05-07`
  - Commit: `80b67f2b` through `7df13360`
  - Notes: `Station type handling was rationalised before K3. Legacy collapsed type_id meanings were replaced with a canonical 0-15 TD-owned registry based on Spansh station types. --odyssey/--od was replaced by --settlement because the filter is settlement classification, not Odyssey capability. Fleet and settlement Y/N/? state derivation is centralised; UNKNOWN/type_id 0 is ? rather than fleet/settlement N. Spansh import maps station.type through the registry. EDDN/listener commodity ingestion does not infer station type, and unknown listener-created station types default to UNKNOWN. Fresh fixtures now use the new type_id model; fixture cleanup removed stray generated files. Fixture subsequently regenerated with corrected system list (172 systems); Blanco Manufacturing Forge is a natural duplicate in Lushertha and Jastreb Sector CL-Y d145. 432 tests passing.`

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
