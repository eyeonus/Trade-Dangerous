# Slice 14 — Succession Handover (mid-14C)

*Updated 2026-06-02, partway through 14C. Supersedes the earlier "at the 14C
boundary" version. For the successor, who will not have seen this session.*

---

## 1. Task Purpose

Slice 14 completes **Checkpoint K**: retire the legacy route/calculator
architecture so `tradedb.py` and `tradecalc.py` can be archived. Checkpoint map:
**K** = the new planner (this side-mission), **L** = `nav`/`olddata` (allowed
broken), **M** = the GUI (`guiapp/`, allowed broken).

Parts:

- **14A** retire legacy `trade run` — *done* (prior session).
- **14B** kill full-preload + sever non-lifecycle `tradedb` couplings — *done*
  (prior session).
- **14C** decide buildcache/lifecycle fate + retire `tradedb.py` — **in progress
  this session.**
- **14D** planner cleanup — pending.
- Docs — pending (after code accepted).

14C goal, in Tromador's words: *"`tradedb.py` dead."* Rework the
lifecycle/build/import path off `TradeDB` so the module can move to archive
**pristine and unedited** (Tromador's explicit instruction — see §3).

---

## 2. Current Progress (this session) — all verified flake8-clean + import-clean

The 14C strategy settled with Tromador: split `cache.py`, move the rebuild into
the `buildcache` command, extend `TradeORM` to be the one DB handle, then cut
`cli` off `TradeDB` and archive it. Done so far:

**`cache.py` split (done):**

- `cache.py` → renamed (`git mv`, history preserved) to **`import_prices.py`** —
  the `.prices` pathway only (`importDataFromFile`, `processPricesFile`,
  `processPrices`, `parseSupply`, name-index helpers). Header reworded.
- New **`tradedangerous/db/import_csv.py`** — the `processImportFile` CSV upsert
  worker (used by eddblink and the rebuild). Worker only now (see below).
- The `BuildCache*` exception family moved to **`tradeexcept.py`** (its base
  `TradeException` already lived there). Includes `BuildCacheBaseException`,
  `DuplicateKeyError`, `DeletedKeyError`, `MultipleStationEntriesError`,
  `MultipleItemEntriesError`, `InvalidLineError`, `SupplyError`,
  `UnknownSystemError`, `UnknownStationError`, `UnknownItemError`.
- Dropped as dead: `depCheck`, the `regeneratePricesFile` stub, `DeprecatedKeyError`.
- Removed `--pricesonly` (option + its dead stub call) from `spansh_plug.py`
  (Tromador's call).
- Repoints: `import_cmd` (cache→import_prices), `lifecycle` (cache→import_csv,
  later removed entirely — see below), `eddblink` (`cache as td_cache` →
  `import_csv as td_cache`), `spansh` (dropped the `cache` import).

**Rebuild moved into the `buildcache` command (done):**

- `buildCache` was lifted out of `import_csv` into **`buildcache_cmd.py`** as the
  private **`_rebuild_database(engine, data_dir, tdenv)`** — engine-centric
  ("Shape B"): it owns its own session via `get_session_factory(engine)`, uses a
  local `_STANDARD_TABLES` manifest (the old `TradeDB.defaultTables` list), and
  needs **no db handle**. `buildcache_cmd.run()` calls it directly.
- This was Tromador's decision: `buildcache_cmd` is the sole consumer, so the
  rebuild lives entirely in that one file ("the can, kicked down the road, self
  contained"). He has a standing mental-block / unfinished thought about
  `buildcache`'s ultimate fate — **do not force that decision; leave it parked.**
- Consequence (flagged + accepted): `lifecycle.ensure_fresh_db`'s rebuild branch
  no longer rebuilds — it reports `"needs_rebuild"` and stops (it must not import
  a command module). Spansh is unaffected (already used `rebuild=False` and
  resets itself on `needs_rebuild`). `trade buildcache` is now the only
  CSV-rebuild path.

**`TradeORM` extended to be the one handle (done):**

- Gained `sql_path`, `session_maker` (+ `session = self.session_maker()`),
  `csv_path`, `template_path`, and the **template bootstrap** (copy
  `Category.csv` / `TradeDangerous.sql` from `templates/`, missing/newer only),
  ported from `TradeDB.__init__`. `from . import fs` added.

**Sanity check relocated + renamed (done):**

- The legacy `reloadCache` ("cache = the db file" baggage) is replaced by
  **`lifecycle.verify_db(engine, data_dir, tdenv)`** — a report-only wrapper over
  `ensure_fresh_db(rebuild=False)`. Tromador's explicit call: it belongs in
  `lifecycle`, **not** as a method on `TradeORM`, and must not be named
  `reloadCache`. (I briefly added it to TradeORM, then removed it on his correction.)
- Callers swapped to `verify_db`: `import_cmd.py:169`, `eddblink_plug.py:845`
  (fed the data dir from `tdenv.dataDir`, so handle-agnostic).

**Other:**

- `DefaultShipIndex.json` archived (`git mv` to `archive/`); it was unused
  repo-wide. `Category.csv` + `TradeDangerous.sql` are kept (still needed).
- Docs (`fourteenth_slice_implementation_plan.md`): added a 14D note
  (`display_labels.py` wants a better home), and recorded the definitive
  **tradedb-kill consumer map + TradeORM-gap + kill sequence**.

**Nothing is committed.** All working-tree. Tromador reviews and commits.

---

## 3. Outstanding Issues / loose ends (read carefully — this is where the misses are)

- **`olddata_cmd.py:78` calls `tdb.reloadCache()` and was NOT swapped.** It was
  missed because the consumer map was built from a `grep tradedb` string search,
  which does not catch files that reach the handle through a `tdb` variable +
  method call. `olddata` is **L** (allowed broken), so it is not a K blocker, but
  it is a real `reloadCache` caller. Either point it at `verify_db` too, or let
  it die with `tradedb` at Step IV (it is L).
- **`eddblink_plug.py:685`** — a docstring still says "Preflight uses
  `TradeDB.reloadCache()`". Stale; the actual call at :845 was swapped. Reword.
- **`tradedb.py` has TWO edits from this session that MUST be reverted before
  archiving.** Tromador wants `tradedb.py` archived **pristine / as-is** (it is a
  historical artefact, not live code). My edits to it:
  1. `from . import cache, fs` → `from . import fs` (1a, to survive the cache rename);
  2. removed the `buildCache` fallback from `reloadCache`'s `except` (1b).
  These cannot simply be reverted while it is still live, because the *original*
  `tradedb.py` imports the now-renamed `cache` module and so won't import — and
  `cli` still imports `tradedb`. So the revert is **coupled to Step IV** (cut
  `cli`'s import first, then revert + archive).
- **MissingDB wrinkle (Step II):** `TradeORM.__init__` raises `MissingDB` when the
  SQLite file is absent. `buildcache` must run on a missing DB (it creates it).
  `TradeDB(load=False)` tolerated this; `TradeORM` does not. Proposed (not yet
  built): a `TradeORM(..., require_db=False)` opt-out + a `buildcache_cmd` flag so
  `cli` constructs it tolerantly; every other command keeps fail-fast `MissingDB`.

### The tradedb kill — remaining steps (full map is in the plan)

- **Step I — extend TradeORM — DONE** (this session).
- **Step II — flip `buildcache` to `Needs.RESOLVER`**: handle the MissingDB
  wrinkle above; retype its `TradeDB` hint to `TradeORM`; point its pre-checks at
  `tdb.db_path` / `tdb.sql_path` (and `str(...)` for the message strings).
- **Step III — flip `import` to `Needs.RESOLVER`** (the meaty one): reparent the
  `.prices` session — `import_prices.importDataFromFile` uses `tdb.Session()`,
  which becomes `tdb.session_maker()`; reparent the plugins' `self.tdb` uses
  (`Session`→`session_maker`, `sqlPath`→`sql_path`, `dbPath`→`db_path`,
  `dataPath`→`data_dir`; `engine`/`close` already match); retype the `TradeDB`
  hints in `import_cmd`, `plugins/__init__`, `spansh_plug`.
- **Step IV — cut `cli.py`'s `from . import tradedb` + the legacy-handle
  construction** (`:41`, `:122-127`). `nav` and `olddata` go dark (L).
- **Step V — revert the two `tradedb.py` edits, then `git mv` the pristine
  original into `archive/tradedangerous/tradedb.py`.**

### Enumerate consumers properly before Step IV

The complete set of `TradeDB` consumers = **the commands that are
`Needs.LEGACY_HANDLE`** (no `needs = Needs.RESOLVER` / no `selectNeeds` →
fall back to `LEGACY_HANDLE`, so `cli` builds them a `TradeDB`) **plus the import
plugins** (which get the handle from `import_cmd`). Known: `buildcache`, `import`,
`nav` (L), `olddata` (L), + `spansh`/`eddblink` plugins, + `plugins/__init__`
(type hint only). **Confirm the LEGACY_HANDLE set by reading each command's
`needs`/`selectNeeds` — do NOT trust a `grep tradedb` string search** (that missed
`olddata`).

---

## 4. Context Boundaries

- **Quarantine is RELAXED for Slice 14** — `tradecalc.py` / `tradedb.py` may be
  read/edited. (But Tromador wants `tradedb.py` archived *unedited* — §3.)
- **Snapshot-before-strip:** archive a pristine copy of any legacy module before
  removing it. Already archived: `archive/tradedangerous/{tradecalc.py, cli.py,
  tradedb.py}`, `archive/tradedangerous/commands/{run_cmd.py, commandenv.py}`,
  `archive/tradedangerous/templates/DefaultShipIndex.json`.
- **M = GUI (`guiapp/`), L = `nav` + `olddata`, tests = rewrite-pending.** All
  allowed broken; do not treat as regressions, do not re-raise as objections, do
  not include them in scope lists (Tromador reads that as noise).

---

## 5. Active Protocols

- Global Tromador Protocol + project `CLAUDE.md` in force.
- **Workflow:** Claude writes code (large mechanical moves via one-shot transform
  scripts — temp `.py`, run, delete; never committed); Tromador pushes / reviews
  / commits; docs committed separately after code accepted; **tests/route
  searches handed to Tromador — never auto-run `pytest` or `trade run`.** Running
  `flake8` / a bare `import` check for verification is fine.
- **Give the WHOLE picture, not a snag at a time.** This session repeatedly
  surfaced obstacles to "kill tradedb" piecemeal (planning session, 14A/B
  session, then this one), which exhausted Tromador's patience. When asked for a
  list, produce the complete, correctly-derived list (see §3) — do not drip-feed.
- **Record decisions + their justification in the plan as they are made** — and
  the objections that were overruled and why.

---

## 6. File / Dependency References

- Python: `/home/stef/Fork/.venv/bin/python` (`-m flake8`, `-m pytest`).
- flake8 config: `tox.ini [flake8]` (ignores `W291`/`W293`/`E302`/`E303`/`E221`/
  `E231`/etc.; excludes `TEMPLATE.py`, `gui.py`).
- New/changed this session:
  - `tradedangerous/import_prices.py` (renamed from `cache.py`; `.prices` only).
  - `tradedangerous/db/import_csv.py` (new; `processImportFile` worker).
  - `tradedangerous/db/lifecycle.py` (`ensure_fresh_db` rebuild branch →
    `needs_rebuild`; new `verify_db`).
  - `tradedangerous/commands/buildcache_cmd.py` (`_rebuild_database` +
    `_STANDARD_TABLES`; engine-centric rebuild).
  - `tradedangerous/tradeorm.py` (`sql_path`, `session_maker`, `csv_path`,
    `template_path`, template bootstrap).
  - `tradedangerous/tradeexcept.py` (the `BuildCache*` exception family).
  - `tradedangerous/commands/import_cmd.py`, `tradedangerous/plugins/eddblink_plug.py`
    (reloadCache → `verify_db`), `tradedangerous/plugins/spansh_plug.py` (cache
    import dropped, `--pricesonly` removed).
- 14C-relevant still-on-`tradedb`: `cli.py` (constructs `TradeDB`),
  `buildcache_cmd`/`import_cmd`/`plugins/__init__`/`spansh_plug` (TradeDB type
  hints), `nav_cmd` + `olddata_cmd` (L).
- The definitive consumer map + kill sequence is in
  `docs/Planner/fourteenth_slice_implementation_plan.md` (section "tradedb.py
  kill — definitive live-consumer map").

---

## 7. Behavioural Tone (read this twice)

- **Tromador is a retired sysadmin/devops from the Perl era — NOT a Python
  programmer — with chronic illness and brain fog.** Plain engineering terms,
  **name the files**, no flake8 error-codes or esoteric Python jargon thrown at
  him as if he were a specialist.
- **Do not hedge, do not manufacture obstacles, do not drip-feed.** When the
  instruction is clear ("kill tradedb", "remove it"), do it and report — do not
  keep discovering one more reason it can't happen. If something genuinely blocks,
  say so once, completely, with the full picture.
- **Do not preserve dead/inert code "just in case."** Archive holds the originals.
- **Settled is settled** — do not re-raise GUI / L / test-suite scope as objections.
- Direct, confident peer; dry humour fine; **no assistant filler, no groveling**;
  structured output (tables, bullets) suits the brain-fog days; UK English; address
  him as **Tromador** (Commander in Elite contexts).
