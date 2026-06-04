# Slice 15 — Listener catch-up, plugin lint, and unanchored cutoff tightening

## Status

Draft, for review by Tromador. Not yet implemented.

## What Slice 15 is

A combined **cleanup slice**, in the spirit of Slice 12 and the 14D tidy. Three
independent pieces, none of which earns a slice of its own, bundled because they
all sit in or beside "import land":

```text
15A — Bring the EDDN listener forward to the Slice-14 TD surface
15B — Make the spansh / eddblink plugins lint clean to house style
15C — Tighten the unanchored commodity-walk early-cutoff (speed)
```

The three parts are independent and may land in any order, across more than one
session. They touch **two repositories**:

- **15A** changes the listener repo at `/home/stef/Fork/TradeDangerous-listener`.
- **15B** and **15C** change Trade-Dangerous itself.

Because 15A is a separate repo, its code changes are handed to Tromador with
ready-to-paste commit messages; the agent does not drive git there. 15B/15C
commit in TD the normal way. All Slice 15 docs live in `docs/Planner/` in TD and
are committed separately after the code is accepted, per the project workflow.

This slice does **not** revert or reshape any Slice-14 work. Slice 14 deliberately
pulled the rug (retired `tradedb`, `cache`, the preload model); 15A weaves a new
rug for the listener to stand on. TD stays as it is.

No process/slice vocabulary leaks into listener code, plugin comments, or commit
messages — the plan document is the only place that language lives.

---

## 15A — Listener Slice-14 catch-up

**Goal:** both the client and server listeners import and run against the current
post-Slice-14 TD fork.

**Mechanism (why it broke).** Slice 14 removed `tradedangerous/tradedb.py` and
`tradedangerous/cache.py` from live code (both archived). The listener imports
both modules and builds a legacy handle, `tradedb.TradeDB(load=False)`, at three
sites. Against the current fork the import fails and the constructor is gone. The
listener does all of its own live-ingestion DB work through its **own** engine and
session (`_ENGINE`, `_SessionFactory`, `sa_session()`, built from the
`tradedangerous.db` helpers, which Slice 14 left in place). The legacy handle is
only needed where the listener hands off to TD's own machinery. The CLI import
path is intact — `import_cmd` is `Needs.RESOLVER` and `trade import -P spansh` /
`-P eddblink` still work — so the listener's subprocess-style
`trade.main(('trade.py', 'import', '-P', …))` invocations keep working untouched.
Only the in-process handle and its two dead imports need fixing.

**The replacement surface.** `TradeORM(*, tdenv=None, require_db=True)` from
`tradedangerous.tradeorm` is a near one-for-one swap for `TradeDB(load=False)`:

- it defaults a `TradeEnv` if none is supplied, and the listener already builds
  `tradeenv.TradeEnv()`;
- the migrated `ImportPlugin` base already takes `tdb: TradeORM` (parameter still
  *named* `tdb`, stored as `self.tdb`), so passing a `TradeORM` into
  `eddblink_plug.ImportPlugin(tdb, tradeenv.TradeEnv())` is exactly what it now
  expects;
- `require_db` is the only per-site judgement: `True` (default) for normal
  operation against an existing DB; `False` for any site that can run before the
  DB file exists (e.g. server first-run, where a spansh import creates it).

**Scope (both files unless noted):**

- In the dual-path import block (the checkout branch — `import tradedb` etc. — and
  the packaged branch — `from tradedangerous import cli as trade, cache, tradedb,
  …`), drop `cache` and `tradedb`. `cache` is imported but never called (dead
  regardless of Slice 14); `tradedb` only supplied the handle.
- Add `TradeORM` to both import branches, matching the existing dual-path shape.
- Replace each `tradedb.TradeDB(load=False)` with `TradeORM(…)`:
  - server `run_update` (~`:492`);
  - server `bootstrap_runtime` (~`:2368`);
  - client `bootstrap_runtime` (~`:842`), whose handle feeds
    `eddblink_plug.ImportPlugin(tdb, tradeenv.TradeEnv())` (~`:844`).
- Choose `require_db` per site once each site's timing relative to DB existence is
  confirmed.
- Confirm the listener's own engine/session machinery and the
  `tradedangerous.db.locks` import (server `:1116`) are untouched — they use
  `tradedangerous.db` exports verified present after Slice 14.

**Acceptance:**

```text
python tradedangerous_listener_client.py      -> imports and starts, no ImportError/AttributeError
python tradedangerous_listener.py             -> imports and starts (server)
<live ingestion smoke>                        -> a market message is processed and a StationItem written
<client eddblink refresh>                     -> completes via the existing CLI invocation
<server spansh import>                         -> completes via the existing CLI invocation
grep -nE "tradedb|TradeDB|\bcache\b" <both>   -> no live hits except the new TradeORM references
```

**Deliverable:** edits in the listener repo, plus commit message(s) for Tromador
to paste.

---

## 15B — spansh / eddblink plugins: flake8 clean to house style

**Goal:** both plugin files pass the project flake8 config clean, and the one
real-bug-class finding is root-caused rather than silenced.

**Mechanism / current state.** `eddblink_plug.py` is already clean (0 violations).
`spansh_plug.py` has four, almost certainly lint debris from the Slice-14 plugin
repointing:

```text
:402   E306  expected 1 blank line before a nested definition       (trivial)
:1152  F841  local variable 'e' is assigned to but never used       (trivial)
:1869  F821  undefined name 'has_added_col'                          (real-bug class)
:1887  F821  undefined name 'has_added_col'                          (real-bug class)
```

The project flake8 config (`tox.ini`, `max-line-length = 180`) is already tuned to
house style — it deliberately ignores `W291`/`W293` so the blank-line-carries-
indentation rule does not fight the linter — so "clean to house style" means
"pass this config", which the files already nearly do.

**The F821 is not cosmetic.** `has_added_col` is read at `:1869`/`:1887` but never
assigned in scope — a name that would raise `NameError` if that path runs. It
reads like a flag that was dropped during the Slice-14 edits (most plausibly
tracking "did this run `ALTER TABLE … ADD COLUMN`", gating a dependent follow-up
step). The fix is to **understand what it guards and restore it correctly**, or, if
the logic genuinely no longer needs it, remove the dead read — *not* to paper over
it with a blind `has_added_col = False`.

**Scope:**

- Fix `E306` and `F841` (confirm the `except … as e` at `:1152` does not intend to
  use `e` before dropping it).
- Trace and correctly resolve both `F821`s; state the mechanism in the completion
  notes.
- Apply house style (blank-line indentation, comment hygiene) **only within the
  touched regions** — no full-file reformat of a ~2,900-line module. Scope control
  applies: the file is already clean bar these four hits, so the change stays small
  and local.

(`ruff` is in the toolchain and does deeper checks, but the user's gate is flake8.
A `ruff check` pass on the two files is a worthwhile adjacent look, not a
requirement of this slice.)

**Acceptance:**

```text
flake8 tradedangerous/plugins/spansh_plug.py tradedangerous/plugins/eddblink_plug.py  -> clean
```

with the F821 resolution carrying a stated cause, not a silencer.

---

## 15C — Unanchored commodity-walk early-cutoff: filter-aware bounds

**Goal:** remove (or materially reduce) the pathology where an unanchored search
with *more* restrictive station filters runs *slower* than one with fewer.

**Mechanism (hypothesis — to be verified before any code).** This rests on a prior
analysis the agent has **not yet confirmed against source**; verifying it is the
first step of 15C, not an assumption to build on.

The analysis:

- The unanchored commodity walk computes broad profit bounds in
  `_unanchored_item_bounds()` that ignore the station filters, while the actual
  supply/demand reductions run against the **filtered** station universe (filters
  already pushed into SQL via `_station_attribute_predicates()`). So this is *not*
  a Python-side late-filtering problem.
- The asymmetry drives the early-cutoff. With loose filters, a carrier-fiction
  trade sets a huge `best_total_profit` on the first commodity, so the walk's
  `capacity * profit_bound <= best_total_profit` cutoff fires almost immediately —
  the run looks fast.
- With restrictive filters (`--fc N --pad-size L --planetary N`) that big number is
  filtered out, the cutoff threshold climbs slowly, and the walk grinds through
  many more commodities whose galaxy-view bounds still look attractive. Each one
  pays reduction + temp-table + `ANALYZE` + pair-match + reachability cost. Net:
  restrictive filters run slower.
- Proposed fix: make the bound calculation **filter-aware**, so the walk and its
  cutoff operate on the same effective station universe as the reductions.

**Relationship to the earlier reorder note.** A separate, smaller thing was spotted
in `route_unanchored.py`: the beam-width trim runs *after* `fetch_stations_by_id`
materialises every seed source (hundreds), when it could trim to the top fifty
first and fetch only those. That is a row-count saving in the multi-hop *seed*, and
it does **not** explain the more-filters-slower symptom. It is at most a free
adjacent tidy — flagged here, to be folded in or left by decision, not assumed.

**15C1 — Verify the mechanism (probe, no code).**

- Read `_unanchored_item_bounds()` and `_station_attribute_predicates()` and
  confirm the bound is genuinely filter-blind while the reductions are filtered.
- Reproduce the symptom on warm live data: time an unanchored run with and without
  `--fc N --pad-size L --planetary N`, and capture commodities-examined (add a
  counter if the diagnostics do not already expose one alongside
  `pairs_examined` / `pairs_accepted`).
- Confirm the commodity count and cutoff threshold are the actual cost driver. If
  the probe does **not** confirm it, stop and re-plan rather than implement a fix
  for an unproven cause (Falsification Rule).

**15C2 — Filter-aware bound (code, only if 15C1 confirms).**

- Push the station-attribute predicates into the bound query so commodities are
  ranked by their best case **under the active filters**, not the galaxy best case.
- The bound must stay **admissible** — an over-estimate of realisable profit under
  the active filters — so the early-cutoff can never discard a true winner. The
  existing outer cutoff deliberately uses raw `profit_bound` as an over-estimate;
  tightening it must not cross from over- to under-estimate. Correctness is the
  hard constraint; speed is the goal.

**Acceptance:**

```text
unanchored --fc N --pad-size L --planetary N  -> no longer slower than the unfiltered run
                                                 (or the gap materially reduced)
winning route                                  -> unchanged on the verification commands
bound                                          -> argued still admissible
commodities-examined                           -> materially lower on the filtered run
```

---

## Sequencing

Independent parts; order is flexible and the slice may span sessions. One logical
step at a time, review between steps per the project workflow.

A suggested order, smallest-first:

1. **15B** — clears the Slice-14 plugin lint debris; smallest, TD-side, warms up.
2. **15A** — the headline; listener repo; commit messages handed over.
3. **15C** — probe-gated (15C1 before 15C2); most design, so last.

Nothing forces this order; if a session is better spent on 15A or 15C, take it.

## Validation posture

No automated test harness (project decision). Validation is spot-check + flake8 +
symptom timing, per part above. All test commands are handed to Tromador to run;
the agent does not run them automatically.

## To confirm during implementation

- **15A:** the exact downstream use of the server's two handles (`run_update`,
  `bootstrap_runtime`); the per-site `require_db` value; the precise dual-path
  import-block shape in both files.
- **15B:** what `has_added_col` guards (the F821 root cause); that the `:1152`
  handler does not intend to use `e`.
- **15C:** the verification outcome of 15C1 — whether the filter-blind-bound
  mechanism is the real cost driver, and whether a commodities-examined counter
  already exists; the decision on whether to fold in the `route_unanchored.py`
  trim-before-fetch reorder.

## Source facts confirmed for this plan

- Listener handle sites: server `tradedb.TradeDB(load=False)` at `:492` and
  `:2368`; client at `:842`, feeding `eddblink_plug.ImportPlugin(tdb,
  tradeenv.TradeEnv())` at `:844`. Dead imports: `cache`, `tradedb` on the packaged
  import line (server `:38`, client `:39`) and the checkout branch (`import
  tradedb`, both `:31`).
- New surface: `TradeORM(*, tdenv=None, debug=None, require_db=True)` in
  `tradedangerous/tradeorm.py`; defaults a `TradeEnv`; opens a session and copies
  template files at construction. `ImportPluginBase.__init__(self, tdb: TradeORM,
  tdenv)` stores `self.tdb`. `import_cmd` is `Needs.RESOLVER`, so the CLI import
  path is intact.
- Listener's own DB layer (`make_engine_from_config`, `get_session_factory`,
  `resolve_data_dir`, `load_config`, `ensure_fresh_db`, `db.locks`) is present and
  unaffected after Slice 14.
- flake8: `eddblink_plug.py` clean; `spansh_plug.py` four hits (`:402` E306, `:1152`
  F841, `:1869`/`:1887` F821 `has_added_col`). Config in `tox.ini`, max-line 180,
  tuned to house style.
- `_unanchored_item_bounds()` and `_station_attribute_predicates()` are named from
  the prior analysis and are **not yet read by the agent** — 15C1 verifies them.

## Documentation updates (after code is accepted)

- `docs/Planner/SLICE_SUMMARY.md` (Slice 15 entry)
- `docs/Planner/INDEX.md` (Slice 15 row)
- Slice 15 completion report
- Project `CLAUDE.md` only if the listener's relationship to the TD surface needs
  recording for later sessions.
