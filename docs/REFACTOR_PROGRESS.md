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
- Status: `[-]`
- Checkpoint: `L — Migrate remaining legacy command surfaces — in progress`
- Subtask: `L5, L1, L2, L3 and L4 complete (range-option contract; olddata SQL-first; nav basic A->B plotter; L3 rare cutover verified clean; L4 trade trade -> trade direct rebuilt to the full "Trade 2.0" scope per #241 — system/station endpoints, --best, --local, --age, summary header, trade kept as a live alias; audited and accepted). Remaining in L: L6 (re-evaluate remaining full TradeDB.load callers). Then M (GUI compatibility + session reuse), N (closeout), O (test-suite rebuild). The full test suite is broken by the planner rewrite — tracked as O; command work is smoke-validated, not gated on pytest. GUI deferred to M.`
- Owner: `Tromador`
- Started: `2026-06-22`
- Goal: `Finish the main command migration set (olddata, nav, trade direct, the zero-range audit, and any remaining full-load callers) without turning it into a generic command-framework rewrite. See the Checkpoint L detail for the full goal and acceptance criteria.`

### Current blocker
- Status: `[ ]`
- Blocker: `None. The K4 question is answered — the preload-first model was replaced by the clean-room planner — so the paused K3/K5/K6/K7 preload tuning is moot, not blocked.`
- Impact: `n/a`
- Needed to unblock: `n/a`

### Last updated
- Date: `2026-06-22`
- By: `Tromador + assistant`
- Session summary: `Investigated olddata/nav for L1/L2 and traced the --ly / --ly-per / --link-ly grey area through the live code. Settled the L5 range-option contract and did L5 first (reordered): --ly = search radius (default 64), --ly-per = per-jump (no default, raise if missing), zero honoured via is-not-None, global --link-ly removed outright (hard break). Applied to buy/sell/__init__; local already compliant; olddata/nav inherit at L1/L2; GUI argv builders deferred to Checkpoint M (M scope note added). flake8 clean. The full test suite is broken by the rewrite (it tests retired modules) — added Checkpoint O to rebuild it — so L5 is smoke-validated rather than gated on pytest. L5 is now smoke-verified and closed; Checkpoint O mirrored into AGENT_START_HERE's checkpoint map and execution order. olddata (L1) migrated SQL-first, audit-fixed (chunked hydration, preflight --route check, house-style blanks) and passed; commits 2be80d7e, c932d89d, 29ee5ba0. nav (L2) rebuilt as a basic A->B route plotter on the planner engine (--refuel-jumps dropped, deferred to Spansh), audit-fixed (avoided-waypoint conflict) and passed; commits 753ba10a, 2b3cccf2. L3 (rare lookup cutover on buy) verified and closed with no code change: the cutover landed in Checkpoint E, and a package sweep confirms zero live references to the retired rares command or RareItem table; buy --rare runs on the canonical Item.rare_station_id predicate (validated end-to-end at E5). The diminished in-game role of rares is a deliberate prior decision; the live-market-view narrowing was signed off as intended. L4 (trade trade -> trade direct) rebuilt to the full "Trade 2.0" scope (issue #241): renamed with trade kept as a live alias; lookup_place endpoints (system or station); --best window-function collapse, --local, --age, From/To columns and a summary header; --fill kept per-row while --load/--full-load are rejected in multi-station; the self-trade predicate was made universal after audit. Commits 52fcf35e, 730d05e2, bced88b3, 70fe7dbc, 51856299, 767c6ede, d899f7a2; smoke-verified incl. live cargo via the journal, audit passed. Only L6 remains in L.`

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
- [ ] O — Rebuild the test suite against the post-rewrite codebase

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

### Status — complete and signed off (2026-06-21)
- The original acceptance criteria above (measure TradeCalc setup, narrow candidate stations, scan fewer rows, improve `run` before route-maths) are **superseded, not individually ticked**: the preload-first TradeCalc/TradeDB route model was replaced wholesale rather than tuned, so those row-scan / setup measures no longer describe how `trade run` works.
- The replacement — the clean-room `trade run` route planner in `tradedangerous/planner/` — is **feature-complete**: every route shape (one-hop and multi-hop; fixed, open-origin, open-destination, and unanchored) plus the full route-modifier, search, and output option surface are built. `trade run` is planner-only; `tradecalc.py` and `tradedb.py` are retired to `archive/`; the full-galaxy preload model is gone.
- Full record in `docs/Planner/` (BASELINE.md, SPEC_STATUS.md, INDEX.md) and the v13.0.0 release notes (`docs/Planner/RELEASE_NOTES_v13.0.0.md`).
- **Checkpoint K is complete.** Next is Checkpoint L (olddata, nav, trade direct), not yet started.

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
- [x] L1. Migrate `olddata`
  - Status note: `olddata rewritten SQL-first on Needs.RESOLVER (un-parked). Aggregates MAX(StationItem.modified)->age per station, pushes all filters (--near bounding-box + exact sphere, --min-age, pad, planetary, fleet/settlement via type_id, --ls-max) into SQL, orders oldest-first and LIMITs in the DB, then hydrates only the survivors. Inherits the L5 contract: --ly = search radius (default 64; --ly 0 = this system only). Legacy wrappers replaced with the house helpers (_fleet_state/_settlement_state/_dist_from_star); --route rebuilt on a local distance helper; Station column now shows System/Station via dbname(). Audited and passed after a fix pass (commit 29ee5ba0): hydration chunked at 900 against the bind-parameter ceiling, --route validated at preflight before any query, in-function blank lines indented to house style; flake8 and ruff clean.`
  - Evidence: `tradedangerous/commands/olddata_cmd.py; smoke-verified 2026-06-22 — default (global oldest), --near Sol --ly 12, --ly 0 (Sol-only, DistLy 0.00), --route (path order), --min-age all correct; commits c932d89d (rebuild) + 29ee5ba0 (audit fixes); audit passed 2026-06-22`
- [x] L2. Migrate `nav`
  - Status note: `nav rebuilt as a basic A->B route plotter on the planner's plan_jump_path (public reachability surface; no full preload). Iterative-deepening jump bound from the straight-line minimum, stopping when the reachable set stops growing; --ly-per required (zero rejected at preflight). --via routes through ordered waypoints, --avoid removes systems from the graph (the avoid-vs-required-waypoint conflict is rejected before planning, with the initial source exempt), --stations lists each stop's stations (command-owned query, display filters in Python, default shows all). --refuel-jumps dropped: advanced fuel/neutron routing is intentionally left to Spansh. flake8 + ruff clean. Audit passed after one fix pass (the avoided-waypoint conflict). Unreachable "no route" branch taken as read, not live-triggered.`
  - Evidence: `tradedangerous/commands/nav_cmd.py; commits 753ba10a (rebuild) + 2b3cccf2 (avoid-waypoint fix); audit passed 2026-06-22; smoke-verified one/multi-jump, --detail/-vv, filtered --stations (200->11 with --pad S), chained --via, avoid conflict + source exemption`
- [x] L3. Complete post-E rare lookup cutover on `buy`
  - Status note: `Verified and closed; no code change required. The cutover itself landed in Checkpoint E (the rares command was retired to archive/ and buy --rare added); L3 confirms it is complete. A sweep of the live tradedangerous/ package finds zero references to the retired rares command, the RareItem table, or rares_cmd. buy --rare filters on the canonical predicate Item.rare_station_id IS NOT NULL (plus supply_units > 0), with browse mode and the ship/one-stop guards intact — validated end-to-end at E5 (142 rares). The only rare code outside buy is the Spansh enrichment, which writes Item.rare_station_id (reset-then-set, no RareItem table). The old command's rich rare-only metadata (Cost/Alloc columns, illegal/suppressed flags, --legal/--illegal, --away/--from) was dropped by deliberate Checkpoint E decision, not overlooked. One known semantic narrowing, signed off as intended: buy --rare is a live-market view (StationItem-backed), so a rare with no live market row at its canonical home station will not list, where the old command listed from the rare definition itself. Accepted given the deliberately diminished in-game role of rares.`
  - Evidence: `tradedangerous/commands/buy_cmd.py (--rare path: lines 164, 296-310); grep sweep of tradedangerous/ for RareItem/rares_cmd/'rares' clean apart from buy and the Spansh enrichment; tradedangerous/plugins/spansh_plug.py:2019,2039 (writes Item.rare_station_id); archive/tradedangerous/commands/rares_cmd.py (retired, options compared); end-to-end functional validation recorded at E5`
- [x] L4. Refactor `trade trade` into `trade direct`
  - Status note: `trade trade renamed to trade direct (issue #241) and built out to the full "Trade 2.0" scope. trade is kept as a first-class compatibility alias, not a deprecation: direct_cmd.py holds the engine, trade_cmd.py is a thin shim that re-exports it and sets its own name (a bare re-export would inherit name='direct' and break argparse). Endpoints resolve through lookup_place, so a bare or trailing-slash name is the whole system (all stations) and sys/station is a single station. The seller x buyer query is column-based and correlates each side through a Station alias, filtering on station_id or system_id; a universal seller_stn != buyer_stn predicate excludes self-trades when endpoints overlap. Output gained From/To station columns (shown when the matching side is a system), a From:/To: summary header, and an --age freshness filter on both ends. Multi-station output is bounded: a default cap with a one-line notice when neither --limit nor --best is given (single-station keeps the historic uncapped default), with the limit pushed into SQL. --best collapses multi-station results three ways (per-station, per-item, station) via ROW_NUMBER() windows (portable across SQLite/MariaDB), ranked by gain per ton with a deterministic tie-break, collapsing before the global limit. --local lists in-system station-to-station trades from a single system argument (dest made optional; a second endpoint or --reverse is rejected). --fill stays valid per row; --load/--full-load are rejected in multi-station (they build one cargo load). Game shortcuts updated: ~ falls back to the current system when not docked, ~@ is now a valid nav-target system endpoint. Audited and accepted after one fix pass (the self-trade predicate made universal, command help refreshed).`
  - Evidence: `tradedangerous/commands/direct_cmd.py (engine); tradedangerous/commands/trade_cmd.py (alias shim); tradedangerous/commands/__init__.py (registers direct_cmd); commits 52fcf35e (rename+alias), 730d05e2 (endpoints), bced88b3 (columns/header/--age/guards), 70fe7dbc (--best), 51856299 (--local), 767c6ede (blank-line style), d899f7a2 (audit fixes: self-trade + help); smoke-verified 2026-06-22 by Tromador incl. --fill cargo read live from the game journal; audit passed 2026-06-22`
- [x] L5. Standardise the range-option contract (`--ly`, `--ly-per`, `--link-ly`) and fix zero-value fallback semantics
  - Status note: `Contract settled and applied to the existing commands. Two options, never both on one command: --ly = search-bubble radius (local/buy/sell/olddata), internal default 64ly; --ly-per = distance per jump (run/nav), no default — raise if missing (explicit 0 also invalid). Fallback is always 'x if x is not None else default', never 'or', so --ly 0 is honoured = this-system-only. The global --link-ly/-L switch is removed outright (hard break): it was a misused default-radius number, never a reachability filter in the search commands, and its only legitimate routing-edge meaning is covered by --ly-per. 64 survives as the ENV_DEFAULTS internal default. Storage standardised: radius -> ly, per-jump -> maxLyPer. Code this pass: __init__.py drops --link-ly and its now-orphaned ENV_DEFAULTS import; buy moves dest maxLyPer->ly with is-not-None fallback; sell renames --ly-per->--ly, dest->ly, is-not-None fallback; local already compliant. olddata (L1) and nav (L2) inherit the contract when rebuilt; nav makes --ly-per required like run. GUI argv builders deferred to Checkpoint M. Validation: the full suite is broken by the planner rewrite (now tracked as Checkpoint O), so L5 is confirmed by targeted smoke checks rather than pytest. Parked idea: a real jump-reachability filter for search results, only if a ticket proves it needed.`
  - Evidence: `tradedangerous/commands/__init__.py; tradedangerous/commands/buy_cmd.py; tradedangerous/commands/sell_cmd.py; smoke-verified 2026-06-22 — --link-ly/--ly-per rejected at argparse; buy "Gold" --near Sol returns ~10 rows at --ly 0 (Sol only), ~306 at --ly 30, ~1765 at default (64ly)`
- [ ] L6. Re-evaluate remaining full `TradeDB.load()` callers
  - Status note:
  - Evidence:

### Notes
- `trade rares` is retired under the locked Checkpoint E design.
- `trade direct` is `trade trade` v2: a direct market comparison command for known endpoints. (https://github.com/eyeonus/Trade-Dangerous/issues/241)
- `trade direct` must not be used as a reason to merge, replace, or delay `trade run --direct`.
- `--ly 0` and equivalent zero-range inputs are explicit user intent, not absence. Settled under L5: fallbacks use `x if x is not None else default`, never `or`, so `--ly 0` means this-system-only. The real flag is `--link-ly` (there is no `--max-link-ly`); L5 removes it. (https://github.com/eyeonus/Trade-Dangerous/issues/267)

---

---

## Checkpoint M — GUI session reuse and cache discipline

### Goal
Recover “load once, answer many questions” only where it belongs: GUI session scope.

M has also absorbed a GUI↔CLI compatibility pass. The CLI command and option
surface changed substantially across v13 — the planner rewrite of `run`, the L5
range-option standardisation, and the L1/L2 rebuilds of `olddata`/`nav` — and the
GUI argv builders in `guiapp/td_exec_commands.py` were not kept in step. The GUI is
deliberately left untouched until this checkpoint rather than patched piecemeal per
command change. M must reconcile every GUI command/option builder with the current
CLI surface (for example: `sell` now takes `--ly`, not `--ly-per`; the global
`--link-ly`/`-L` switch is gone; `olddata`/`nav` options match their rebuilt forms)
before, or alongside, the session-reuse work.

Stef random note to please remind him: Add copy from render.

### Acceptance criteria
- GUI argv builders match the current CLI command/option surface (no stale or removed flags)
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
- [ ] M5. GUI↔CLI compatibility pass — reconcile `guiapp/td_exec_commands.py` and the GUI workspaces with the post-L CLI command/option surface (foundational; likely tackled before the session-reuse tasks)
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

## Checkpoint O — Rebuild the test suite against the post-rewrite codebase

### Goal
Restore a green, meaningful test suite. The clean-room planner rewrite and the v13
command/schema changes retired large parts of the code the old tests were written
against (`tradedb.py`, `tradecalc.py`, the preload model). Much of the suite now
exercises a world that no longer exists, so this checkpoint rebuilds tests against
the current architecture rather than patching the obsolete ones.

### Acceptance criteria
- the suite runs green against the current codebase
- coverage reflects how the planner, resolver, and migrated commands actually
  behave now, not the retired preload/TradeDB model
- tests bound to archived modules are removed or rewritten, not skipped
- the suite is trustworthy again as a gate for later work (e.g. N's final verification)

### Tasks
- [ ] O1. Inventory the suite: passing, failing, and obsolete-by-design
  - Status note:
  - Evidence:
- [ ] O2. Remove or rewrite tests bound to archived modules (tradedb/tradecalc/preload)
  - Status note:
  - Evidence:
- [ ] O3. Add or repair coverage for the planner and the post-L command surface
  - Status note:
  - Evidence:
- [ ] O4. Confirm a full green run and record it as the new baseline
  - Status note:
  - Evidence:

### Notes
- Surfaced during L5: the suite is broken by the deliberate engine swap, not by any
  single command change. Validate interim command work (L5, L1, L2) with targeted
  smoke checks until O restores the suite.

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
- Date: `2026-06-22`
  - Topic: `Range-option contract (L5)`
  - Decision: `Standardise the CLI range options. --ly = search-bubble radius (local/buy/sell/olddata), default 64ly held as an internal ENV_DEFAULTS value. --ly-per = distance per jump (run/nav), no default — raise if missing; explicit 0 is invalid. Fallbacks use 'x if x is not None else default', never 'or', so --ly 0 = this-system-only. Remove the global --link-ly/-L switch outright (hard break). Storage: radius -> ly, per-jump -> maxLyPer.`
  - Reason: `--ly was overloaded across commands (radius vs per-jump, two dest names) and the 'or' fallback silently swallowed an explicit 0. --link-ly was a misused shared default that even the lead dev did not rely on; its only legitimate (routing-edge) meaning is served by --ly-per. v13 is already a rebuild-the-world release, so a hard break is consistent.`
  - Revisit trigger: `Only if a ticket proves a real need for a jump-reachability filter on search results (distinct from --ly radius), or if a removed flag is genuinely missed.`
- Date: `2026-06-22`
  - Topic: `nav scope (L2)`
  - Decision: `nav is a basic A->B route plotter: start, end, --ly-per, plus --via/--avoid/--stations. It does not model fuel, refuelling, or neutron boosting; the legacy --refuel-jumps option is dropped.`
  - Reason: `A correct refuel/neutron plotter needs a full ship/fuel model nav has no business carrying, and Spansh already does it superbly and is well known to the player base. Pointing users there beats shipping a half-version.`
  - Revisit trigger: `Only if a ticket establishes a concrete need for in-tool refuel/neutron routing that Spansh cannot reasonably serve.`
- Date: `2026-06-22`
  - Topic: `direct command scope (L4)`
  - Decision: `Rename trade trade to trade direct and build the full "Trade 2.0" wishlist from issue #241: system-or-station endpoints on either side, --best (per-station/per-item/station), --local, --age, and a summary header. Keep trade as a first-class compatibility alias (not deprecated, no removal schedule). Pre-conditions held firm: bound multi-station output (default cap + notice when neither --limit nor --best is set); split --fill (per-row, always valid) from --load/--full-load (single cargo load, rejected in multi-station); --local takes one system and rejects a second endpoint or --reverse; exclude self-trades universally, not just under --local.`
  - Reason: `direct is informational ("A to B, what sells?") and deliberately diverse from the opinionated trade run; #241 is the agreed shape and the alias preserves a long-standing invocation. The pre-conditions stop the larger pairing space from producing unbounded or nonsensical (self-trade, capacity-less) output.`
  - Revisit trigger: `Only if a ticket asks for capability beyond #241, or if trade alias usage proves worth retiring.`

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
- [x] Milestone: `Checkpoint K complete — trade run replaced by the clean-room planner`
  - Date completed: `2026-06-21`
  - Commit: `f6958820` (Slice 14 legacy-retirement closeout); planner build continued across docs/Planner/ through the v13.0.0 release notes
  - Notes: `Checkpoint K's incremental TradeCalc-narrowing goal was superseded by a full clean-room rewrite of trade run. The preload-first model was retired (tradecalc.py / tradedb.py archived; trade run is planner-only, querying the database directly), and the planner is now feature-complete — every route shape plus the full route-modifier, search, and output option surface — documented in docs/Planner/ with v13.0.0 release notes. Original K acceptance criteria superseded, not individually met.`

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
