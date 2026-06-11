# Slice 23 — Fetch-Path Overhead Sweep — Completion Report

Slice 22 left the planner fetch-bound: with cargo pre-filtered, the dominant
cost became fetching and grouping candidate rows, plus a layer of smaller
repeated-work leaks in the hot paths. This slice closed seven verified leaks.
The headline is SQL-side narrowing of the open-ended candidate queries — rows
that could never pair no longer leave the database. Routes are unchanged; the
large open multi-hop shape roughly halved.

Planned in session, not in a separate plan doc (the Slice 20 pattern): a
fresh-eyes seam analysis was supplied, each claimed issue was verified against
the code before any fix, and all seven held up.

---

## The issues, verified

| # | Seam | Verified mechanism |
|---|------|--------------------|
| 1 | Open-ended fetch over-materialised | The open side's query had no item or price coupling to the fixed side; rows for commodities the fixed endpoint never trades were fetched, matched in Python, and thrown away. For the backward shape the large open side was even fetched before the small fixed side, so an empty fixed side was discovered after the big query. |
| 2 | Per-pair zero-result classification | The fixed-pair matrix ran up to two failure-probe queries per empty pair inside the hot loop, paid even when a later pair won. |
| 3 | Station DTO rehydration | Both multi-hop expansion helpers re-fetched station DTOs from the database every call; frontier layers rediscover the same stations. |
| 4 | Unanchored per-item reductions | The bounds phase reduced Station to a qualifying temp once — then dropped it, and every per-commodity reduction joined Station again with the full attribute-predicate set re-evaluated, twice per item. |
| 5 | Redundant reachable precompute | The open-anchor expansion ran the in-memory cKDTree BFS before every fetch; on a reachable-memo hit the result was discarded unread. |
| 6 | Bulk-tax category lookup per fetch | Both candidate-fetch paths re-resolved the Metals/Minerals category ids per call. |
| 7 | Per-row timestamp calls | `_age_days()` called `datetime.now()` for every candidate row. |

Items 6 and 7 landed first (with the classification *flag* groundwork for
item 2) in `ec8d1c08`, which also hardened the bulk-tax resolution: missing
Metals/Minerals categories now raise `PlannerDataError` instead of silently
degrading to "nothing is sensitive".

---

## The headline fix — narrowing in SQL, not Python

A first attempt at item 1 built per-item min/max price dictionaries in Python
from the fetched fixed-side rows. It was rejected before landing: the
aggregation is GROUP BY work, and bounds the open-side query must honour
belong in SQL, not in a Python dict the rows have to come out to meet.

The landed shape keeps the two-query anti-self-join design and adds a
narrowing stage inside it:

1. The fixed side's per-item price extremes are aggregated straight into a
   small temp table — `INSERT … SELECT item_id, MIN(price), MAX(price) …
   GROUP BY item_id` over the fixed station ids. No row crosses into Python
   for this.
2. If the temp is empty the fetch returns immediately — before the large
   open-side query, which previously ran first on the backward shape.
3. The open-side query gains a correlated EXISTS probe against the temp:
   the row's item must exist there, at a price that could clear
   `--gain-per-ton` against the fixed side's best price (and stay under
   `--max-gain-per-ton` when set). The same query shape as the existing
   onward-viability EXISTS, so the outer query keeps driving from the
   reachable station set rather than flipping onto an item-id scan.

The bounds are interval-overlap **necessary** conditions, never sufficient
ones: the exact per-pair gain test still runs in the Python match loop, so the
candidate set is provably unchanged — only rows that could never pair stop
being fetched.

---

## The supporting fixes

- **Aggregate failure classification (item 2).** The matrix planner fetches
  with classification disabled and tracks which stations took part in
  reachable pairs; two set probes run only on the no-route failure path,
  built on the same filter builders as the single-pair classifier so the
  definitions cannot drift. Successful searches pay zero classification
  queries. One corner-case nuance, accepted: in a matrix where one pair's
  source lacks data and a different pair's destination lacks data, the old
  per-pair probing reported a missing side; the aggregate probes report "no
  profitable trades" — arguably the more accurate family, since both sides
  did have data somewhere in range.
- **Station DTO cache (item 3).** `fetch_stations_by_id` takes a run-scoped
  cache; both multi-hop engines thread one alongside the bubble cache and
  reachable memo. Only unseen ids touch the database. DTOs are immutable for
  a run, so semantics cannot change.
- **Run-scoped qualifying temp (item 4).** Built once per unanchored run
  (now carrying the `system_id` the reductions partition by), ANALYZEd so the
  optimiser knows its cardinality, reused by the bounds aggregates and both
  per-item reductions; the per-item join became a primary-key probe.
- **Precompute skip (item 5).** The reachable-memo key moved into one shared
  helper with a public containment check; the open-anchor expansion skips the
  BFS when the memo already holds the anchor's temp table.

---

## Verification (live data)

| Run | Route | Before | After |
|---|---|---|---|
| Fixed-terminal `--from Sol --to Lave` h3 | **byte-identical** — profit 5,244,784, and 51,596 pairs / 1,061 b&b / 47,457 pruned all match the Slice 22 record | 46s (fetch 35.6s) | 38.5s (fetch 24.5s) |
| Open-destination `--from Sol` h3 | post-match candidate total matches (3,399,096 ≈ 3.4M) | 159s | **83s** |
| Open-origin `--to Lave` h3 | post-match candidate total matches (1,580,914 ≈ 1.6M) | 41s | 34s |
| One-hop open `--from Sol` h1 | identical — same trade, same 84,413 pruned / 6 solved | ~5s | ~5.6s |
| Unanchored h1 | sane route; no pinned baseline to compare | — | 98s |

The post-match candidate totals landing on the recorded figures is itself
evidence of exactness: the narrowing only removes rows that could never pair,
so the candidate count must not move — and it did not.

An incidental observation from verification, worth keeping: `--to Sol` h3 ran
in 75s against `--from Sol` h3's 83s, while `--to Lave` ran in 34s — the
driver is the anchor's eligible-station count (Sol seeds 63 layer-1 frontier
nodes, Lave 4), not which end of the route is open. Lave has many stations
but few with usable market data.

flake8 clean across the planner package.

---

## Bottleneck after this slice (observed, not addressed)

Fetch remains the dominant cost on the multi-hop shapes — 24.5s of the
fixed-terminal 38.5s. The EXISTS probe stops rows being materialised and
matched, but the database still walks the reachable stations' market rows to
evaluate it. Cutting deeper means a different query shape; that is the next
lever if these shapes need to be faster still.

Minor: the open-anchor engine does not populate the per-phase
fetch/cargo/jump timers (they print as 0ms on the open multi-hop shapes);
only the fixed-terminal helper is wired. Display gap, cheap to close when
diagnostics next get attention.

---

## Commits

| Commit | Change |
|--------|--------|
| `ec8d1c08` | Hot-loop groundwork: classification flag, session-cached bulk-tax ids (+ `PlannerDataError` hardening), single per-fetch `now_utc`. |
| `402ce54e` | Open-ended candidate queries narrowed by fixed-side item/price bounds in SQL. |
| `13580caa` | Pair-matrix failures classified once on the failure path, not per empty pair. |
| `c952c198` | Run-scoped station DTO cache across frontier expansion calls. |
| `26ed8095` | Unanchored per-item reductions driven from one run-scoped qualifying temp. |
| `b555a6f0` | Reachable-set precompute skipped when the memo already holds the table. |

## Touched files

| File | Change |
|------|--------|
| `planner/data_gateway.py` | Bounds temp + EXISTS narrowing in the open-ended fetch; shared usable-data filter builders and station-set probes; qualifying-temp reuse in the unanchored reductions; memo-key helper; DTO-cache support in `fetch_stations_by_id`; bulk-tax caching; per-fetch `now_utc`. |
| `planner/route_onehop.py` | Matrix loop fetches without classification; aggregate probes on the failure path. |
| `planner/route_anchored.py` | Station cache threaded through fixed-terminal expansion; final-hop fetch without classification. |
| `planner/route_common.py` | Station cache threaded through open-anchor expansion; BFS skip on memo hit. |
| `planner/failures.py` | `PlannerDataError`. |
