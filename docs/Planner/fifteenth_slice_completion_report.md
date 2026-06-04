# Slice 15 Completion Report — Listener catch-up, plugin guardrails, and unanchored bounds

## Status

Complete. Two code commits on `release/v1` in Trade-Dangerous:

- `53812f29` refactor(spansh): drop generic-dialect fallbacks for explicit guardrails (15B)
- `b13ac661` perf(planner): make unanchored price bounds filter-aware and station-driven (15C)

Plus the docs commit `9efe4ff3` (plan doc + a SLICE_SUMMARY de-duplication).

15A changes a **separate repository** — the EDDN listener at
`/home/stef/Fork/TradeDangerous-listener` (branch `master`) — and is handed to
Tromador as a paste-ready commit message to land in that repo himself, so it is
not a Trade-Dangerous commit.

## What this slice delivered

A combined cleanup slice: three independent pieces in or beside "import land",
bundled because none earns a slice of its own. 15A is in the listener repo; 15B
and 15C are in Trade-Dangerous. They were planned to land in any order across
more than one session, and did.

## Delivered

**15A — Listener catch-up (listener repo).**

- The listener still imported the `cache` and `tradedb` modules that Slice 14
  retired. Its dual-path import block has a repo-local branch and a packaged
  branch; the packaged branch fires in this environment and pulled the removed
  modules, breaking startup.
- Swapped `tradedb.TradeDB(load=False)` → `TradeORM()` at all three construction
  sites (server `run_update` and `bootstrap_runtime`, client) and dropped the
  dead `cache` / `tradedb` imports from both dual-path import blocks.
- The `bootstrap_runtime` site is load-bearing, not dead: it stages
  `Category.csv`, the root of the foreign-key chain (every table's FKs trace back
  to Category), and is the bootstrap's one template-seeding step. `TradeORM()`
  preserves that seeding side effect — it copies the template seed files on
  construction and never preloads the galaxy, the exact successor to the old
  `TradeDB(load=False)`.
- Validated live: the server listener started, loaded its dicts (items, systems,
  ~785k stations), began the spansh download, and resumed live EDDN ingestion on
  MariaDB.
- The client path was not QA'd (decision: fix on a ticket if anyone ever hits
  it) and a full spansh import is assumed working until shown otherwise.

**15B — Plugin guardrails (commit `53812f29`).**

- The spansh plugin carried hand-rolled "generic backend" upsert and fast-sync
  paths as a fallback for any dialect that is neither SQLite nor MariaDB. There
  is no engine for another backend and every other dialect-specific operation
  already raises on an unknown dialect, so these were dead weight implying a
  portability the app does not have.
- Removed all thirteen generic fallbacks, each replaced with a `RuntimeError`
  matching db/utils' "Unsupported dialect" wording. A dead `added`-column
  reference (left over from the retired Added table) in the System path went with
  it. Also cleared a stale "(unchanged)" note in the db/utils dialect-checks
  comment and two flake8 hits. Net ≈ −251 lines in `spansh_plug.py`.

**15C — Unanchored bounds, filter-aware and station-driven (commit `b13ac661`).**

Two changes to the galaxy-wide per-commodity price bounds that gate the
fully-unanchored search (`_unanchored_item_bounds`). The bound is the dearest
demand price minus the cheapest supply price per commodity; the walk visits
commodities in descending-bound order and stops early once the best concrete
trade found beats every remaining commodity's ceiling.

1. **Filter-aware.** The bound ignored the station-attribute filters (pad size,
   planetary, fleet carrier). A filtered run strips the lucrative trades and
   lowers the best concrete profit, but the bound stayed sky-high on the excluded
   stations (a fleet carrier's wild price, say), so the early-cutoff never fired
   and the walk ground through commodities that could not win — more filters made
   the search *slower*. Applying the same per-row filters the per-commodity
   reductions apply makes the bound track what is actually reachable. Every filter
   only ever removes rows, which can only lower a bound, so the result stays a
   true upper bound and the cutoff cannot skip a real winner.

2. **Station-driven.** The filter-aware bound joined every market row to Station,
   so SQLite scanned all ~11.2M supply/demand rows and seeked Station once per
   row — with ~86% of stations failing the filter (110,339 of 785,992 pass pad-L
   / no-planet / has-market), most of that work was wasted. The fix reduces
   Station to the qualifying station ids in a temp table once, then aggregates
   only those stations' market rows, forcing the optimiser to drive from that
   small set. The force-order keyword is dialect-specific (`CROSS JOIN` on SQLite,
   `STRAIGHT_JOIN` on MariaDB — SQLite's `CROSS JOIN` suppresses join reordering,
   MariaDB's does not), wrapped in a new `force_order_join` helper in `db/utils`.

The diagnosis was measured, not guessed. A py-spy profile of the filtered run
showed it was SQL-execution-bound: `do_execute` (43.9%) and `fetchall` (38.2%)
dominated self-time — ~82% in SQL — while the Python candidate cross-product and
cargo solves were under 2% combined (refuting an earlier hypothesis that the
object-building dominated). `EXPLAIN QUERY PLAN` showed the 11.2M-row index scan
plus a per-row Station primary-key seek; a head-to-head timing of the supply
bound was 43.9s (StationItem-first, the join's natural plan) versus ~0.75s
(station-first, driving from the qualifying temp), identical results.

Net effect on the filtered two-hop run: ~7m45 (filter-blind) → ~4m04
(filter-aware) → ~2m15 (station-driven); the `station-filter` diagnostic phase
fell from ~171s to ~73s. The route is unchanged throughout.

## Verification

No automated harness (project decision); correctness is spot-checked against
live data.

- **15C correctness.** The filtered two-hop run produced an identical route and
  profit (15,240,518 cr) with the station filters and again with `--age 10`. The
  new bounds were proven byte-identical to the plain-join form by a SQL
  symmetric-difference check — `0` rows differ in either direction, on both the
  supply (MIN) and demand (MAX) aggregate — so route-neutrality holds independent
  of any data churn. The unfiltered baseline stayed healthy (~2m35), its route
  differing from the historical baseline only by live-data drift since the data
  was last renewed. Both touched modules compile and import; flake8 clean.
- **15B.** flake8 clean; the plugin imports clean and references none of the
  removed generic paths.
- **15A.** The server listener was run live and ingested successfully on MariaDB.

## Notes / Deferred (not cut)

- 15A's listener-repo commit is Tromador's to make in that separate repo, with
  the supplied message. The client path and a full end-to-end spansh import are
  assumed-working pending a real run or a ticket.
- The plan doc (`fifteenth_slice_implementation_plan.md`) was committed with its
  original "draft / not yet implemented" status, and its 15B section describes
  the pre-evolution scope (lint) rather than the generic-fallback guardrail purge
  it became. A status and scope refresh on the plan doc is a minor follow-up.
- `force_order_join` is a deliberate dialect-specific helper, added with explicit
  permission for this case; it lives in `db/utils` beside `analyze_temp_table`
  under the "Query planner helpers" section.
