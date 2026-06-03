# Slice 14 Completion Report — Complete Checkpoint K: retire the legacy route/preload architecture

## Status

Complete on `release/v1`. Eight code commits:

- `39828ab2` refactor(run): make trade run planner-only and split the cache module
- `d5ab4370` refactor(buildcache): run on the TradeORM resolver handle
- `03eca1c1` refactor(import): run import and the importer plugins on the TradeORM handle
- `3cdf70f1` refactor(commands): park nav and olddata off the legacy handle
- `83ee24b2` refactor(commands): remove the legacy handle backend lane
- `75ba5f3c` refactor(db): remove the retired legacy tradedb module
- `39a3ba80` chore(archive): snapshot the pristine pre-split cache.py
- `f6958820` refactor: planner cleanup, run --pad-size parser, and stale-reference tidy

## What this slice delivered

Slice 14 closes **Checkpoint K**. K began life as "reduce `TradeCalc` setup
cost", but the K4 architecture review and the planner side-mission (Slices 1–13)
established that incremental preload tuning was the wrong target: the clean-room
planner replaces the legacy route/calculator architecture wholesale rather than
narrowing it. Slice 14 is the retirement. After it, the legacy `trade run` path,
the `TradeCalc` calculator, the full-galaxy preload model, and the `TradeDB`
handle are all gone from live code, and `trade run` is served entirely by the new
planner querying the database directly.

This is a breaking development-fork slice (the fork is not the live v12.x
codebase). `nav` and `olddata` are intentionally parked for checkpoint L; the GUI
(`guiapp/`) and the test suite are likewise allowed-broken pending rebuild. Those
states are deliberate, not regressions.

## Delivered

**14A — Legacy `trade run` retired (commit `39828ab2`).**

- `--old` removed; `run_cmd.py` is planner-only (`needs = Needs.RESOLVER`). The
  legacy `TradeCalc` / `Route` branch and the render support that only consumed
  legacy `Route` objects are deleted.
- `tradecalc.py` archived to `archive/tradedangerous/tradecalc.py`.
- `cache.py` split in the same commit to prepare the lifecycle move: the
  `.prices` pathway became `import_prices.py`, the CSV upsert worker became
  `db/import_csv.py`, and the `BuildCache*` exception family moved to
  `tradeexcept.py` (its base `TradeException` already lived there).

**14B — Full-preload retired as a live command model.**

- The full-galaxy preload trigger — the legacy backend lane that loaded the
  whole galaxy into memory before a command ran — is gone. No live command
  preloads the galaxy any more.
- `nav` and `olddata` were parked (commit `3cdf70f1`): their module-level legacy
  imports removed, backend set to `Needs.NOTHING`, and a fail-early
  `validateRunArgumentsFast` that defers each cleanly to checkpoint L. Their
  `run` / `render` bodies are left dormant for the L rebuild.

**14C — `buildcache` / lifecycle / import moved onto `TradeORM`.**

- `TradeORM` extended into the one DB handle: `sql_path`, `session_maker`,
  `csv_path`, `template_path`, the template bootstrap, and a `require_db`
  opt-out so build/bootstrap commands can construct the handle before the SQLite
  file exists.
- `buildcache` (commit `d5ab4370`) rebuilds via a self-contained
  `_rebuild_database(engine, data_dir, tdenv)`; `import` and the eddblink /
  spansh plugins (commit `03eca1c1`) run on the TradeORM handle
  (`session_maker`, `db_path`, `sql_path`, `data_dir`).
- The legacy backend lane removed (commit `83ee24b2`): the `Needs` enum reduced
  to `NOTHING` + `RESOLVER`; `LEGACY_HANDLE` / `needs_legacy_db` / `wantsTradeDB`
  deleted; a command that declares no backend now fails loudly rather than being
  handed a legacy handle.
- `tradedb.py` removed from live code and archived **pristine** (commit
  `75ba5f3c`); a byte-identical pre-split snapshot of `cache.py` archived as well
  (commit `39a3ba80`) so every retired module has an archive copy.

**14D — Planner cleanup (commit `f6958820`).**

- Renamed `_OPEN_ORIGIN_CORRECTION_WIDTH` → `_OPEN_SHAPE_CORRECTION_WIDTH`; the
  cap serves every open run shape now, not just open-origin.
- Reworded the planner's "reachable" failure messages to plain "within range".
- Corrected the open-origin/backward docstrings in `route_common` /
  `route_unanchored` that went stale when the open-anchor engine became shared
  across both open shapes.
- Gave `trade run` its own `--pad-size` parser: a single `S`/`M`/`L` ship-fit
  threshold, rejecting `?` and multi-letter input at parse time, with help that
  matches the filter. The shared `PadSizeArgument`, `CommandEnv.checkPadSize`,
  the planner filter, and the safety-net validator are untouched — the parser and
  help were aligned to the filter, not the reverse.
- Folded the display-label tables into `formatting.py` and deleted the stray
  `commands/display_labels.py`; consumers use `formatting.<label>`.
- Updated `commands/TEMPLATE.py` to the `needs = Needs.RESOLVER` backend
  contract.
- Refreshed the stale "TradeDB" comments that implied the retired module is still
  live (`cli`, `commandenv`, `tradeexcept`, `csvexport`); the provenance notes
  ("mirrors / retired / previously TradeDB") were left intact.

## Verification

No automated harness (project decision); correctness is spot-checked against live
data and the retired `--old` path while comparison is still possible.

- **14A–14C** were validated by Tromador across the recovery sessions: a
  multi-hop `trade run` to Colonia plans correctly on the planner-only path; the
  `trade station` deprecation notice fires; `trade buildcache` begins importing
  on a fresh handle (then the populated database was restored); the legacy
  `tradedb` / `tradecalc` references are gone from live, non-GUI code.
- **14D** is flake8-clean across every touched file; `cli` (which eagerly imports
  every command) and both import plugins import cleanly; the `--pad-size` parser's
  accept/reject behaviour was exercised directly against the filter's `S`/`M`/`L`
  truth table.

## Notes

- The archive is complete: `tradedb.py`, `tradecalc.py`, `cache.py`, and
  `DefaultShipIndex.json` all have pristine copies under `archive/`. Git reports
  the module strips as `R100` renames into `archive/`, confirming the snapshots
  are byte-identical to their pre-retirement originals.
- A spansh investigation during 14D flagged a suspected SQLite `NameError` in
  `_upsert_system` (an undefined `has_added_col`). It proved unreachable on
  SQLite — the `is_sqlite` branch returns first — so the suspicion was wrong and
  the exploratory change was reverted. spansh is unchanged this slice.

## Deferred (not cut)

- `nav` and `olddata` are parked at `Needs.NOTHING` with dormant `run` / `render`
  bodies, to be rebuilt on the planner foundation at **checkpoint L**.
- A full end-to-end spansh import has not been run this slice. The repo's
  `spansh_plug.py` is the current migrated copy (commit `03eca1c1`) — it imports
  clean, references none of the retired modules, and uses the TradeORM handle — so
  it is expected to work; a real testbed import (with the listener) is the
  remaining confirmation. An older pre-removal reference copy of the plugin
  differs by ~6 hunks, which is expected of the older file, not a repo-side debt.
- The GUI (`guiapp/`) and the pytest suite remain allowed-broken pending their
  own rebuilds.
