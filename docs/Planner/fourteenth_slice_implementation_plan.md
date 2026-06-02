# Slice 14 — Complete Checkpoint K: retire the legacy route/preload architecture

## Status

Draft, for review by Tromador. Not yet implemented.

## What Slice 14 is

Slice 14 is the **completion of Checkpoint K**.

K began as "reduce `TradeCalc` setup cost". K4 and the planner side-mission
changed the correct solution: incremental tuning of `TradeCalc` / preload was the
wrong target, and the clean planner rewrite replaced the legacy
route/calculator architecture instead. Slices 1–13 produced the replacement.
Slice 14 closes K by retiring the legacy route path, the `TradeCalc` calculator,
the full-preload execution model, and by deciding the future of
`buildcache` / lifecycle.

This is a **breaking development-fork** slice. The fork is not the live codebase
(v12.x is live). Commands may break or remain broken during this work if that is
useful, provided the broken state is **intentional and documented**. The March
refactor guardrails (e.g. "do not delete `TradeDB` up front", "N is for
cleanup") are **historical context, not binding constraints** — the plan is
based on where the fork is now.

## Structure

```text
14A — Retire legacy trade run
14B — Kill full-preload as a live command model
14C — Decide the fate of buildcache / lifecycle
14D — Planner cleanup (the original baseline tidy)
```

Each part is implemented and reviewed in turn. Within a part, multiple coherent
edits may land together.

---

## 14A — Retire legacy `trade run`

**Goal:** `trade run` becomes planner-only.

**Scope:**

- Remove `--old` (the `ParseArgument`, `run_cmd.py:309`).
- Make `run_cmd.py` always use the new planner / resolver path: replace
  `selectNeeds` (`:46-51`) with `needs = Needs.RESOLVER`; drop the
  `if not getattr(cmdenv, "old", …)` guard at `run()` (`:1440`) so the new path
  is unconditional.
- Remove the legacy `TradeCalc` branch from `run_cmd.py`: the `else` body —
  legacy default-restoration (`:1510-1520`) and the legacy planner
  (`TradeCalc` `:1550`, `Route` `:1562`, route loop, `NoHopsError` /
  `UserAbortedRun` handling through ~`:1774`).
- Remove legacy route/checklist/render support that only consumes legacy
  `Route` objects (`run(self, route, cr)` at `:456`+, with its `describeAge`
  use).
- Remove `tradecalc` (and now-orphaned `tradedb`) imports from live
  `run_cmd.py` (`:8-9`).
- Archive `tradecalc.py` → `archive/tradedangerous/tradecalc.py`.
- Remove or archive tests that directly exercise legacy `TradeCalc`
  (`tests/test_tradecalc_db.py`; the `tradecalc`-patching stale-age test in
  `tests/test_trade_run.py`).
- Remove the `TradeCalc` top-level package re-export (`__init__.py:21`, `:38`).

**Acceptance:**

```text
trade run --old
```

should fail because `--old` no longer exists.

```text
grep -R "tradecalc\|TradeCalc" tradedangerous tests -n
```

should show no live-code hits outside `archive/` and `docs/`.

---

## 14B — Kill full-preload as a live command model

**Goal:** no supported command path relies on `TradeDB(load=True)` / full
in-memory preload as live architecture.

**Scope:**

- Remove or inert `FULL_LEGACY` (the `Needs` flag, `commandenv.py`).
- Remove `needs_full_load` if it no longer has a real job.
- Stop `cli.py` from constructing the full preload path (`cli.py:125`,
  `TradeDB(cmdenv, load=cmdenv.needs_full_load)` → build the legacy handle
  `load=False`; the import path needs only a non-preloaded handle).
- Allow `nav` and `olddata` to break during this slice.
- Do not treat `nav` / `olddata` breakage as a Slice 14 blocker.
- Record that their future is checkpoint L or deletion.

Wording to carry into the docs:

```text
nav and olddata are allowed to be broken during Slice 14.

They are not acceptance gates for K. Their future is checkpoint L or deletion.
Breakage is acceptable in the development fork, but must be recorded so later
agents do not mistake it for an unexpected regression.
```

(The record lives in `REFACTOR_PROGRESS.md` under L and in the Slice 14
completion report — not buried in code.)

**Acceptance:**

```text
grep -R "FULL_LEGACY\|needs_full_load" tradedangerous -n
```

should be empty, or point only at deliberately inert / archival compatibility
text. 

No live command should request FULL_LEGACY / needs_full_load as an execution path.

---

## 14C — Decide the fate of `buildcache` / lifecycle

**Goal:** decide what happens to `buildcache` and the database lifecycle code.
**Do not assume the answer before auditing.**

`buildcache` is historical TD v1.0 terminology: in the original model the CSV
files were the authority and the SQLite database was a generated "cache". That
model no longer cleanly describes the modernised codebase.

Starting map (grounded; the audit confirms and extends it):

```text
commands/buildcache_cmd.py   LEGACY_HANDLE
commands/import_cmd.py        LEGACY_HANDLE  -> cache.regeneratePricesFile (a stub: returns immediately)
cache.buildCache(tdb, …)     uses tdb.engine / .Session() / .importTables / .dbPath   (cache.py:1131-1146)
db/lifecycle.py:330          ensure_fresh_db -> buildCache(tdb, tdenv)
plugins/spansh_plug.py:1024  regeneratePricesFile(self.tdb, …)  (stub)
plugins/eddblink_plug.py     import flow
```

14C decides whether `buildcache` should:

1. remain as a deprecated compatibility command name over a modern lifecycle
   implementation;
2. be renamed / replaced by a clearer database lifecycle command;
3. be absorbed properly into `tradedangerous/db/lifecycle.py` and related
   importer workflows;
4. or be removed / archived if its remaining behaviour is obsolete.

Wording to carry:

```text
14C does not assume the answer is "rename buildcache" or "delete buildcache".

It starts by auditing the lifecycle path and deciding what the modern ownership
model should be.
```

**Companion — the non-lifecycle `TradeDB` couplings.** To make `tradedb.py`'s
fate decidable, 14C also resolves the remaining live couplings that are *not*
lifecycle:

- the display-label dicts (`tradedb.py:554-557`) pulled by `buy` / `sell` /
  `local` for render sort keys → rehome to a neutral module (proposed
  `commands/display_labels.py`), repoint the three commands;
- `commandenv.py`'s `from …tradedb import AmbiguityError, Station`
  (`AmbiguityError` already lives in `tradeexcept`);
- the `TradeDB` top-level re-export (`__init__.py:22`, `:39`).

**Acceptance for 14C:**

- Current `buildcache`, `import`, `eddblink`, `spansh`, and lifecycle entry
  points are mapped.
- The remaining `TradeDB` dependency in rebuild/import/lifecycle flow is either
  removed, explicitly retained with reason, or marked as deliberate temporary
  breakage in the v13 fork.
- The chosen future command / API shape is documented.
- `db/lifecycle.py` is identified as the intended home for lifecycle policy
  unless the audit proves otherwise.
- No `buildcache` / lifecycle work is deferred vaguely to checkpoint N.

---

## 14D — Planner cleanup (the original baseline tidy)

**Goal:** the planner-package hygiene pass this session opened with, now landed
on the post-14A/B/C code.

**Scope:**

- **flake8** — `run_cmd.py:53` `E305` (likely moot after 14A reshapes that
  region; re-check and clear whatever remains across `planner/` + `run_cmd.py`).
- **Stale constant** — rename `_OPEN_ORIGIN_CORRECTION_WIDTH`
  (`route_common.py:580`, `:1089`) and reword its comment: it serves every open
  shape now, not just open-origin.
- **Failure-message wording** — `route_onehop.py:464-470` ("No **reachable**
  source/destination station had usable selling/buying data") and the per-station
  raises in `data_gateway.py:653` / `:679` leak the internal "reachable" concept;
  reword to the friendlier place-named style. Then remove the now-resolved
  `StationHasNoUsablePriceData` cleanup note from `SLICE_SUMMARY.md`.
- **Docstring/comment accuracy** after the Slice 13 engine move — `route_common`
  (relocated engine), `route_single_anchor` (thin front), `route_unanchored`:
  fix phrasing that still reads "single-anchor" / "open-origin" where it now
  describes the shared engine. Fix only genuine staleness; no reformatting.
- **`--max-gain-per-ton` / `--mgpt` note** — rewrite the stale `SLICE_SUMMARY`
  note that frames a `--max-gain-per-ton` cap as "under discussion with eyeonus":
  that discussion produced Slice 9's `--max-price` (a different axis); `--mgpt`
  itself is simply a deferred, unimplemented trade filter.
- **`--pad-size` CLI threshold fix** — give `trade run` its own `--pad-size`
  parser: accept exactly one of `S` / `M` / `L`, reject `?` / multi-letter at
  parse time with the threshold message, and a threshold-model help string (no
  more `SML?` example). Leave the shared `PadSizeArgument`, `CommandEnv.checkPadSize`,
  and the other five commands untouched; the planner's `validation.py` threshold
  check stays as the safety net. This closes the three-layer mismatch (parser /
  `checkPadSize` / planner) and the silent `SML?`→no-filter quirk, all of which
  were investigated and confirmed against source this session.
- **`display_labels.py` home** — `commands/display_labels.py` (the render-sort
  label dicts rehomed in 14B) is only ~20 lines including comments. Find it a
  more fitting home than a standalone command-folder module rather than leave a
  tiny stray file; pick the target during 14D.

**Acceptance:** `flake8` clean on `planner/` + `run_cmd.py`; the constant and
failure-message wording carry no internal-concept leak; `trade run --pad-size`
gives one consistent threshold message for all bad input and honest `--help`;
the `SLICE_SUMMARY` notes corrected.

---

## `tradedb.py` policy

```text
tradedb.py is not protected by policy in Slice 14.

It may remain temporarily only if source audit proves live dependencies still
exist after 14A/14B/14C. Any such dependency must be named as a remaining K
blocker or explicitly accepted development-fork breakage.

It must not be deferred vaguely to checkpoint N.
```

This is not an instruction to delete `tradedb.py` blindly — it means the file is
no longer sacred. Keep it only with named evidence (its likely surviving
dependency is the `buildCache` lifecycle path, which 14C adjudicates).

## `buildcache` policy

```text
Do not classify buildcache / lifecycle work as Checkpoint N cleanup.

buildcache is not just dead-code debris. It is live database lifecycle/import
architecture, and it historically holds together parts of the old TradeDB model.
Checkpoint N is for cleanup after the architecture is settled. It is not where
live lifecycle decisions should be hidden.

If buildcache or lifecycle code remains unresolved after Slice 14, record it as:
  "remaining K lifecycle blocker"
or:
  "explicitly accepted temporary development-fork breakage"
not as generic N cleanup.
```

---

## Sequencing

One logical step at a time, review between steps per the project workflow.

1. **14A** — retire legacy `trade run`; `run` becomes `RESOLVER`-only;
   `tradecalc.py` archived.
2. **14B** — kill the full-preload trigger; `FULL_LEGACY` / `needs_full_load`
   inert; `nav` (and likely `olddata`) go dark.
3. **14C** — audit `buildcache` / lifecycle (read-only first), resolve the
   residual `TradeDB` couplings, decide and document `tradedb.py`'s fate.
4. **14D** — planner cleanup, landed on the settled post-A/B/C code.
5. **Docs** — this plan now; the rest after code is accepted (committed
   separately per workflow).

## Validation posture

This is a breaking development fork. Validation proves **intentional state**, not
v12 compatibility. Test commands are handed to Tromador to run.

```text
trade run --old                 -> option no longer exists
grep -R "tradecalc\|TradeCalc"  -> no live-code hits outside archive/docs
grep -R "FULL_LEGACY\|needs_full_load" tradedangerous -> removed or inert
trade run <smoke shapes>        -> still work (run-short benchmark; a multi-hop run)
trade buy / sell / local        -> still work (after the display-dict rehome)
trade nav / olddata             -> may break; if broken, recorded as intentional
                                   v13 fork state, not a K acceptance blocker
trade buildcache / import       -> per the 14C decision: still work, modernised,
                                   or explicitly marked temporarily broken/deferred
                                   within the K lifecycle notes
pytest                          -> after the 14A/14D test changes (handed over)
```

## Documentation updates (after code is accepted)

- `docs/Planner/SLICE_SUMMARY.md` (Slice 14 entry)
- `docs/Planner/INDEX.md`
- Slice 14 completion report
- `docs/REFACTOR_PROGRESS.md` (K closed via the planner project; active
  checkpoint → L; `nav`/`olddata` intentional-breakage record; the 14C
  lifecycle outcome)
- `docs/AGENT_START_HERE.md` (K narrative)
- `docs/final_implementation_plan.md`
- Project `CLAUDE.md` (`--old` retired, `tradecalc` gone, quarantine status;
  the planner side-mission's relationship to K)
- `docs/Planner/trade_run_black_box_spec.md` (drop `--old`-as-comparison-path)

Required documentation message:

```text
The March refactor plan has been superseded during Checkpoint K.

K was originally framed as TradeCalc setup reduction. K4 showed that incremental
TradeCalc optimisation was the wrong target. The planner rewrite replaced the
legacy route/calculator architecture instead.

Slice 14 closes K by removing the legacy route path, retiring TradeCalc, killing
the full-preload execution model, and deciding the future of buildcache/lifecycle.
```

## Source facts confirmed for this plan

- `--old` footprint in `run_cmd.py`: `selectNeeds` `:46-51`, arg `:309`, the
  `run()` fork `:1440`, the legacy branch `:1510-1774`, the legacy render method
  `:456`+, imports `:8-9`.
- After `--old` is removed, the only `FULL_LEGACY` consumer is `nav`
  (`wantsTradeDB=True`); `buildcache` / `import` are `LEGACY_HANDLE`
  (`load=False`).
- `buildCache` uses a live `TradeDB` instance (`cache.py:1131-1146`);
  `regeneratePricesFile` is a stub (`return` at `:1201`).
- Display dicts at `tradedb.py:554-557`; consumers `buy` / `sell` / `local`
  (and the `--old` render path, removed in 14A).
- `tradecalc` live consumers: `run_cmd.py` (`--old`), `__init__.py` re-export,
  `tests/test_tradecalc_db.py`, the `test_trade_run.py` stale-age test.
- `AmbiguityError` is defined in `tradeexcept.py:53` (rehoming target for the
  `commandenv` import).
- Pad-size three-layer pipeline: `PadSizeParser` (`parsing.py:43`), shared
  `CommandEnv.checkPadSize` (`commandenv.py:367`, maps `SML?`→`None`), planner
  `validation.py:194`; SQL filter `_PAD_SIZE_QUALIFYING` (`data_gateway.py:1862`).

## To confirm during implementation

- That the legacy render method `run(self, route, cr)` (`:456`) and every
  `tradedb` name imported at `run_cmd.py:8` are `--old`-only before removing the
  imports.
- That no live caller depends on the bare `tradedangerous.TradeDB` /
  `tradedangerous.TradeCalc` re-export before trimming `__init__`.
- The 14C audit outcome — `buildcache`'s future shape and whether `tradedb.py`
  has a named surviving dependency.
- The chosen home for the display dicts (`display_labels.py` vs
  `station_types.py`).

## tradedb.py kill — definitive live-consumer map (whole-repo search, 2026-06-02)

Live `tradedangerous/` consumers only. GUI (`guiapp/`, = M), `tests/` (rewrite),
and `archive/` (already gone) are out of scope and intentionally not listed.
This is the **complete** set — nothing else live imports or uses `tradedb`.

- `cli.py:41,127` — the ONLY constructor: `TradeDB(load=False)`, built for the
  legacy-handle commands. Everything below merely *receives* that instance; this
  is the single real runtime coupling.
- `buildcache_cmd.py` — receives a TradeDB; uses `dbPath`, `dbFilename`,
  `sqlPath`, `sqlFilename`, `dataPath`, `engine`. (The rebuild itself is now
  engine-centric inside this file — `_rebuild_database` — and needs no handle.)
- `import_cmd.py` — receives a TradeDB; uses `reloadCache()`, `close()`, and
  `.Session` via the `.prices` loader (`import_prices.importDataFromFile`).
- `plugins/spansh_plug.py` — receives a TradeDB; uses `engine`, `Session`.
- `plugins/eddblink_plug.py` — receives a TradeDB; uses `engine`, `Session`,
  `close`, `dataPath`, `dbPath`, `sqlPath`, `reloadCache()`.
- `plugins/__init__.py` — `TradeDB` type-hint on the plugin base only.
- `nav_cmd.py` — `from …tradedb import Station, System`. **L — accepted broken,
  no work.**

`buildcache_cmd`, `import_cmd`, `plugins/__init__`, `spansh_plug` also carry a
TYPE_CHECKING `TradeDB` hint (annotation only).

### What TradeORM must gain to absorb the runtime users

- `sql_path` (callers `str()` the paths for the `dbFilename`/`sqlFilename`
  message strings).
- a session factory (`session_maker`; callers use `session_maker()`).
- a sanity-check entry point — implemented as `lifecycle.verify_db()` (a
  report-only wrapper over `ensure_fresh_db(rebuild=False)`), **not** a method on
  TradeORM; replaces the legacy `TradeDB.reloadCache()`. `import`/`eddblink`
  call it where they used `tdb.reloadCache()`.
- the template bootstrap (copy `Category.csv` / `TradeDangerous.sql`), moved out
  of `TradeDB.__init__`.
- already present: `engine`, `db_path`, `data_dir`, `close`.
- **WRINKLE:** `TradeORM.__init__` raises `MissingDB` when the SQLite file is
  absent. `buildcache` must run on a missing DB (it creates it), so its RESOLVER
  migration must tolerate that — a guard/flag — before the flip.

### Kill sequence

1. **Extend TradeORM** with the above (additive, safe).
2. **Flip `buildcache` + `import` to `Needs.RESOLVER`**; retype the four TradeDB
   hints to TradeORM; point `import`/`eddblink`/`spansh` handle uses at TradeORM.
3. **Cut `cli`'s `from . import tradedb`** + the legacy-handle construction.
4. `nav` goes dark (L).
5. Revert the two interim `tradedb.py` edits and `git mv` the pristine original
   into `archive/`.
