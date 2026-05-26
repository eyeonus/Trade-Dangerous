# trade run Planner Rewrite — Slice Summary

Condensed record of the `trade run` planner-rewrite slices. This document is the
required startup digest: read it instead of the per-slice implementation plans
and completion reports, to save session context. It is appended to as each
slice completes.

The full per-slice plans and completion reports remain in `docs/Planner/` for
reference when detail is genuinely needed.

---

## Architecture boundary

```text
CLI parser -> RunRequest -> planner -> RunResult -> renderer
```

The new planner is the package `tradedangerous/planner/`. `trade run` uses it;
`trade run --old` routes to the quarantined legacy planner purely for
comparison. `selectNeeds()` returns `Needs.RESOLVER` for the new path and
`Needs.FULL_LEGACY` for `--old`. The new path's speed comes from selecting
`Needs.RESOLVER` and so avoiding the legacy full-database preload — not from
lazy imports.

---

## Slice 1 — First Safe Slice (complete)

Fixed station-to-station, single-hop planning.

**Supported shape:** `--from <station> --to <station> --capacity --credits --hops 1 --jumps-per --ly-per`.

**Delivered:**

- Planner package created: `__init__`, `failures`, `run_request`, `run_result`,
  `validation`, `cargo`, `score`, `reachability`, `resolver`, `data_gateway`,
  `run_onehop`, `render_text`.
- Command integration in `run_cmd.py`, `commandenv.py`, `tradeorm.py`;
  `trade run --old` added as the comparison path.
- Cargo: bounded branch-and-bound multi-commodity optimiser; destination demand
  is a hard quantity cap; no greedy-as-correctness.
- Reachability: same-system supercruise and single-jump coordinate-distance
  checks. Multi-jump (`--jumps-per >= 2`) deliberately deferred — raises
  `ReachabilityImplementationMissing`.
- Parser corrections: `--black-market` changed from a boolean switch to a Y/N/?
  state filter; `--fleet-carrier` and `--settlement` derived from
  `Station.type_id`.

**Verified:** same-system and one-jump cross-system runs; cargo/profit/credit
arithmetic; validation and typed-failure handling; unreachable-route rejection.

---

## Slice 2 — One-Hop Expanded Endpoints (complete)

`--from` and/or `--to` may be a **system**; the planner expands a system
endpoint to its eligible stations and selects the best one-hop station pair.

**Supported shapes:** all four station/system combinations for `--from` and
`--to`, including same-system.

**Delivered:**

- Endpoint resolution distinguishes a fixed station endpoint from a system
  endpoint needing expansion. Scoped `System/Station` input resolves the station
  within that system only — never a global fallback.
- System expansion is bounded to the named system (not galaxy search).
- Station-level filters applied SQL-side during expansion: `system_id`, market,
  pad size, planetary, no-planet, black-market, max-ls, fleet-carrier,
  settlement.
- One-hop station-pair matrix: every source station x destination station
  evaluated; self-pairs skipped on `station_id` equality (not raw text, so
  future fuzzy matching stays safe).
- Best pair selected by practical score, raw profit as tie-breaker.

**SQL-side pruning in force:** station filters during expansion; market role
filters; min-supply / min-demand; age cutoff; gain-per-ton; affordability of at
least one unit; self-pair skip before reachability/market/cargo work.

**Known tradeoff:** the candidate query prunes unaffordable commodities in SQL.
A pair whose only profitable commodities all exceed available credits may be
classed as "no profitable trades" rather than "no affordable cargo". This is
intentional on the hot path.

**Post-Slice-2 audit (commit `750448a2`):** the planner code was audited and
corrected — the cargo branch-and-bound fractional upper bound (unaffordable
items must `continue`, not `break`, since candidates are profit-sorted, not
price-sorted); the per-pair candidate query shape (selective join first,
diagnostic probes only on the zero-result path); and the ORM->DTO boundary
(`ResolvedSystem` DTO instead of a leaked ORM `System`).

---

## Slice 3 — Open-Ended One-Hop Search (complete)

`--from` supplied, `--to` omitted — the planner selects the destination,
finding the best one-hop trade from the fixed origin to any reachable station.

**Supported shape:** `--from <station|system>` with `--to` omitted, alongside
the fixed-endpoint shapes from Slices 1 and 2. An omitted `--to` requires
`--jumps-per 0` or `1`.

**Delivered:**

- `plan_onehop_route` dispatches on whether `--to` was supplied: fixed
  endpoints take the Slice 1/2 path, an omitted `--to` takes the open-ended
  destination search. Shared result-building is factored into
  `_assemble_result`.
- Destination resolution is staged so spatial narrowing runs first: a bounding
  box on the indexed `System.pos_x/y/z` columns, refined by an exact
  squared-distance test, yields in-range system ids; those drive the
  station-attribute filter; the market table is touched only afterwards.
- The market query fetches origin supply rows and destination demand rows as
  two single-table queries, each driven by its station-id set through the
  `StationItem` primary key, and matches them on `item_id` in Python. A single
  self-join lets SQLite scan the market table galaxy-wide by `item_id`, the
  cause of a `--pad-size S` pathology (~154s) the split query removed (~3s).
- `_MIN_MEANINGFUL_DEMAND = 2`: a destination market row counts only when
  `demand_units` is 2 or more, screening the dormant buy side of stocked goods
  (see Project Notes — Commodity supply and demand values).
- Unknown-pad stations are admitted unless `--pad-size L` is set (see Filter
  Semantics — Pad size).
- The `--jumps-per` default changes from 2 to 1.

**Verified:** validation tranches A–E and the run-short Colonia benchmark,
spot-checked against `--old`. Routes match where the planners' filter models
are comparable; the run-short benchmark was byte-identical. The one notable
divergence was the new planner correctly declining a trade to a station with
`demand_units` of 1 — an unfillable destination `--old` accepts. Open-ended
search returns in ~3s against 7–30s for `--old`.

**Deferred (not cut):** an omitted `--from`, both endpoints omitted, and
multi-jump open-ended search. These must reach the new planner before `--old`
is retired at v13.

Full record: `docs/Planner/third_slice_completion_report.md`.

---

## Slice 4 — Open-Ended Origin Search (complete)

`--to` supplied, `--from` omitted — the planner selects the origin, finding
the best one-hop trade into the supplied destination from any reachable
station.

**Supported shape:** `--to <station|system>` with `--from` omitted, alongside
every fixed-endpoint shape (Slices 1-2) and the omitted-`--to` shape (Slice 3).
At least one of `--from` / `--to` must be supplied; both omitted is rejected.

**Delivered:**

- Slice 3's open-ended destination search is generalised, not duplicated, into
  one parameterised path. `_best_open_destination_plan` becomes
  `_best_open_ended_plan`, keyed on `open_role` — the trade role of the
  endpoint the planner selects. Only the fixed-endpoint derivation reads
  `open_role`; resolution, candidate query, pair evaluation, scoring, and
  result assembly are direction-agnostic.
- `plan_onehop_route` dispatches three ways: both endpoints fixed ->
  `_plan_fixed_endpoints`; one omitted -> `_best_open_ended_plan` with the
  matching `open_role`; both omitted -> rejected in validation.
- `fetch_open_ended_trade_candidates` assigns the fixed and spatially-reached
  station sets to the supply and demand queries from `open_role`.
- Fixed-side and open-side station DTOs merge into one
  `station_id -> ResolvedStation` map; the pair loop resolves either side
  without a direction branch.
- Validation: `--from` is no longer required; the both-omitted shape is
  rejected (`UnsupportedRunShape`); the omitted-endpoint `--jumps-per` guard
  applies to whichever endpoint is omitted.

**Reachable-station query shape:** the `--to "Sol"` dense-region validation
command exposed a query that did not scale. The open-ended candidate query
constrained `StationItem.station_id` with a station-id list materialised into
Python and passed back as a literal `IN (...)`. A short list keeps SQLite on
the `StationItem` primary key; a list of thousands of ids flips it to a
galaxy-wide commodity-index scan (`ANY(item_id)`) — millions of page reads.
The reachable set is now a SQL subquery: `_reachable_station_id_query` returns
a `Select`, composed into the candidate query with `.in_(<subquery>)`, which
holds the primary-key plan. `--to "Sol"` returns in ~2.5s against a prior
multi-minute non-completion. The lesson is recorded in the project `CLAUDE.md`
("Query work belongs in the database").

**Verified:** the omitted-`--from` shapes (station, system, `--jumps-per 0`);
the Slice 3 open-destination set and the run-short benchmark re-run after the
query-shape change, unchanged; the both-endpoint shapes; the two new failure
checks (`UnsupportedRunShape`, no traceback). Dense-region performance
verified on `--to "Sol"`.

**Post-completion audit:** a source-level audit found the open-ended search
over-excluding the fixed endpoint — its whole station set was passed as a
blanket exclusion to the open-side reachable query, which for a system fixed
endpoint emptied the open set under `--jumps-per 0` and suppressed valid
same-system trades under `--jumps-per 1`. Corrected to a pair-level invariant
(commit `db82e655`): the reachable set stays broad, self-pairs are screened
per pair at candidate assembly (`source != destination`), and the failure
probe `any_reachable_station_pair` answers pair existence so a lone fixed
station still classifies as `NoReachableRoute`.

**Deferred (not cut):** both endpoints omitted (the unanchored galaxy search),
and multi-jump open-ended search. These must reach the new planner before
`--old` is retired at v13.

Full record: `docs/Planner/fourth_slice_completion_report.md`.

---

## Slice 5 — Unanchored Galaxy Search (complete; restructure investigated and parked)

Neither `--from` nor `--to` supplied — the planner selects both endpoints,
finding the best one-hop trade anywhere in reachable range. The one-hop
family is now complete.

**Supported shape:** `trade run` with both `--from` and `--to` omitted,
alongside every fixed and open-ended shape from Slices 1-4. Both omitted
still requires `--jumps-per 0` or `1`.

**Delivered:**

- `plan_onehop_route` dispatches four ways: both endpoints fixed, `--from`
  only, `--to` only, and neither. The last routes to `_plan_unanchored`, a
  separate additive path that shares no body with the anchored open-ended
  search — the unanchored search differs in kind, not in a parameter.
- `fetch_unanchored_trade_candidates` is the galaxy-wide candidate query —
  exhaustive in consideration, bounded in materialisation. A reachable-system
  map is built once per run as a run-scoped temporary table; each commodity
  is reduced to its cheapest supplier and dearest buyer per system, and
  matched through the map. Commodities are walked in descending
  profit-per-unit bound order; the walk stops once `capacity x bound` cannot
  beat the best concrete trade found, so only a handful of commodities are
  examined and the candidate set never approaches the galaxy.
- The per-system reduction uses a `ROW_NUMBER` window function — standard
  SQL, no reliance on any backend's handling of non-grouped columns — so the
  query is backend-portable.
- `run_cmd` gates the both-omitted shape behind an interactive confirmation:
  it warns the search is slow and asks before planning. A non-affirmative
  answer or a non-TTY invocation exits cleanly with guidance, no traceback,
  the planner never invoked. Validation runs before the prompt, so a command
  that cannot run fails immediately rather than after a confirmation the
  planner would then refuse.
- `prefer_in_memory_temp_storage` in `db/utils.py` holds the run-scoped
  temporary tables in memory — on SQLite via `PRAGMA temp_store`, which the
  reachable-system map (millions of rows) needs to avoid a disk-file spill;
  other backends are a documented no-op. The anchored planner and query
  functions are unmodified.

**Verified:** the both-omitted shape for `--jumps-per 1` and `0`, against
`--old` — the new planner returns a valid route in ~83s where `--old` takes
~293s on the same hardware. The prompt's affirmative, non-affirmative,
bare-Enter and non-TTY paths; `--jumps-per >= 2` rejected before the prompt
with no traceback; the run-short Colonia benchmark and the Slice 1-4 shapes
unchanged.

**Performance:** the unanchored search is the slow one-hop shape by nature,
roughly one to two minutes against a warm database, dominated by the
one-time reachable-system map build. The confirmation prompt exists for
exactly that reason.

**Deferred (not cut):** multi-jump per-hop reachability (`--jumps-per >= 2`)
and multi-hop routing (`--hops > 1`) — the larger body of work still ahead.

**Source-level audit:** Tromador audited the unanchored search against the
source after sign-off. Three localised remediations applied on `release/v1`:
temp identifier columns flipped from `Integer` to `BigInteger` for MariaDB
portability (commit `a80e5ae4`, proven against MariaDB on a Linux VM);
self-pairs excluded in SQL rather than later in `_group_pairs`
(`ee9a0a52`); per-commodity ranking key changed from unit profit to
capacity/supply/demand/limit-capped total profit, expressed with portable
nested CASE (`8b3fa02a`).
Two structural findings — per-system extrema discarding multi-commodity
station pairs, and `--ls-penalty` applied after the bounded SQL slice —
plus a credits-affordability follow-up, were taken to a planned
restructure of the unanchored candidate query and investigated
empirically. Six probes (P1–P6, captured in
`fifth_slice_restructure_implementation_plan.md`) ran against the live
dataset under both no-`--age` and realistic `--age 1/2/7` data shapes,
testing whether α (widened K), δ (per-pair full menu), ε (credits in
the SQL rank), or a wider top-N slice produces a higher-scoring
practical winner. Result: 144 axis-uplift checks, zero higher-scoring
winners surfaced. **Restructure parked**; findings accepted as
mechanically real but monitored / not implemented. The mechanisms
hold; current data shape and the locked scorer do not make them affect
winner selection. Re-evaluation triggers and the carrier-dominance
observation are recorded in the restructure plan.

Full record: `docs/Planner/fifth_slice_completion_report.md`.

---

## Slice 8 — Vanilla Multi-Hop from Known Origin (complete)

Known-origin multi-hop routing. The planner now supports vanilla multi-hop
from a supplied origin, with or without a fixed destination.

**Supported shapes:**

```text
trade run --from X --hops N
trade run --from X --to Y --hops N
```

**Delivered:**

- `run_onehop.py` renamed to `run_route.py`; `run_cmd.py` now imports
  `plan_route` from the renamed module.
- Multi-hop search builds layered route frontiers from the known `--from`
  endpoint and propagates credits hop-to-hop using the established margin
  haircut.
- Intermediate hops use `terminal_hop=False`, so demand-only stations can end
  a route but cannot occupy a mid-route frontier slot that must be a viable
  onward source.
- Fixed-terminal `--to` multi-hop uses a remaining-hop direct-distance
  envelope to keep the search pointed at the destination. The envelope is
  pushed into SQL, composing with the reachable-station query so
  out-of-envelope destinations are filtered before Python materialisation,
  grouping, cargo fitting, scoring, and sorting.
- Fixed-terminal global frontier trimming now applies destination-system
  diversity: after score sorting, at most one frontier node per destination
  system survives into the next layer. This preserves bounded beam width while
  avoiding near-duplicate station/system clusters consuming the frontier.
- Partial multi-hop results are returned when the search completes at least
  one hop but cannot complete the requested hop count. The planner emits
  structured `PartialRouteWarning` values; `render_text.py` owns the
  user-facing warning wording and diagnostics are preserved.

**Verified:** fixed-terminal Sol -> Lave at 3 hops now matches the legacy
route profit exactly while remaining materially faster:

```text
new planner:  7,838,971 cr, ~32.5s real
legacy --old: 7,838,971 cr, ~46.4s real
```

The quality trace showed the previous lower-profit result was not a cargo,
price, scoring, SQL-envelope, per-parent expansion, or final-hop mismatch.
The legacy-quality route produced the same total through the new helpers as
through `--old`; it had previously died only at hop-1 global frontier trim
(`Sol/Shen -> Charunder`, per-parent rank 14, global rank 316). The
destination-system diversity trim recovered the route without widening the
beam.

A controlled partial-route probe exercised the three warning branches:
expansion-layer collapse after a completed hop, final-hop collapse with no
reachable destination, and final-hop collapse with reachable destination but
no viable trade.

**Deferred (not cut):** omitted `--from`, both endpoints omitted, `--via`,
`--avoid`, `--towards`, `--loop`, `--unique`, `--loop-interval`, `--shorten`,
`--routes` top-N, `--max-routes`, `--prune-score`, `--prune-hops`,
`--start-jumps`, and `--end-jumps`.

Full record: `docs/Planner/eighth_slice_completion_report.md`.

---

## Slice 6 — Multi-Jump Per-Hop Reachability (complete)

`--jumps-per >= 2` works for every trade run shape — fixed endpoints,
one endpoint omitted, and both omitted. The slice also lands the
deferred default keyed to `--ly-per` and the user-facing failure-message
cleanup. `--old` no longer holds any one-hop shape the new planner
cannot serve.

**Supported shape:** every Slice 1–5 shape with `--jumps-per` now any
non-negative integer rather than restricted to 0 or 1 outside the
fixed-station case.

**Delivered:**

- `plan_jump_path` runs a single bounded BFS over a pre-fetched local
  bubble around the source system (Piece A — settled by probe P2).
  In-memory adjacency built with `scipy.spatial.cKDTree.query_ball_tree`
  once at bubble load. A direct-distance early-out covers the
  destination-is-one-jump-away case at microsecond cost. A
  per-RunRequest `_LocalBubble` cache holds adjacency plus a path cache
  so the answer is computed once per `(source, destination)` system
  pair regardless of which station combination on those systems asks.
  `is_system_pair_reachable` is the public single-pair reach check used
  by the unanchored search.
- `_reachable_station_query` widens layer-by-layer into a
  per-RunRequest temporary table `td_reachable_systems` (Piece B —
  settled by probes P3 and P3b). The composed candidate query joins
  to that table by system id. The age filter stays in the composed
  query, not the temp-table build (probe P3c).
- `fetch_unanchored_trade_candidates` streams candidate
  `(supply, demand)` pairs through a direct-distance prefilter and a
  per-pair reach check using Piece A's bubble cache (Piece C — settled
  by probe P4). No multi-jump pair map is materialised. Production
  N=1 is faster than the previous cross-join shape because the 44 M-row
  reach map is never built. `UnanchoredCounters` records pairs
  examined, pairs accepted, bubble-cache source-system count, and
  per-commodity cap hits.
- `JumpPath.distance_ly` is the polyline length (sum of leg distances).
  The straight-line reading lost meaning the moment a path could bend.
- `--jumps-per` default is keyed to `--ly-per`: `--ly-per <= 12.5`
  defaults to 2, anything longer keeps the historical default of 1.
  Argparse default is `None` so the request builder can tell
  "omitted" from explicit `--jumps-per 1`; explicit values pass
  through untouched. The legacy `--old` branch restores its
  historical default of 1 at the top of its branch.
- Validation's omitted-endpoint `--jumps-per` pin is gone; the
  non-negative-integer check remains.
- New `PlannerResultError` in `commands/exceptions.py` prints
  `Error: <message>` with no "possible causes" footer.
  `_planner_result_message` in `run_cmd.py` builds five user-facing
  wordings from the failure type and the endpoints the user named —
  "from X to Y unreachable", "no profitable trade from X to Y",
  "from X", "to Y", and the unanchored case. Wording uses "with the
  current jump settings" rather than internal terms ("origin",
  "anchor", "selected endpoints"), and recommends `--jumps-per` only
  where increasing it is plausibly the fix.
- The unanchored confirmation prompt was rewritten away from
  "anchored / unanchored" terminology and toward a stronger, honest
  reading of the run cost (anywhere from minutes to substantially
  longer), recommending naming an endpoint or applying filters.
  Wrapped to 80-column output.
- A `^C` deep inside SQLite during the unanchored search left the
  session transaction broken; the subsequent cleanup of the per-run
  temp tables then raised `PendingRollbackError`, masking the original
  `KeyboardInterrupt`. The drop call is now wrapped in
  `try / except Exception: pass`; the temp tables are session-scoped
  and the run is being torn down anyway.

**Verified:** multi-jump exercised against `--old` across all three
shapes; route validity is the gate, not route identity. Polyline
arithmetic spot-checked (Sol → Lave at `--ly-per 30`: 144.47 LY
polyline against 114.54 LY straight line). Keyed default verified at
Sol (`--ly-per 12` → 2 jumps; `--ly-per 30` → 1 jump; boundary `12.5`
→ 2 jumps). Explicit `--jumps-per 0` and `--jumps-per 1` preserved.
Failure-message family exercised in turn; "to-only" verified by
inspection as the symmetric branch of the from-only case in the same
builder. N=0 and Slice 1–5 N=1 shapes re-run; behaviour unchanged.

**Performance:** the unanchored multi-jump search is the slow shape
by nature, gated by the existing confirmation prompt. With realistic
filters (`--age`, `--pad-size`, `--planetary`, `--fc N`) the run
completes in roughly 2–3 minutes on the live data; without filters it
is interactively prohibitive on dense space. N=1 unanchored is faster
after this slice than before (probe P4: 132 s → 14.6 s at the dense
profile), because C3 removes the cross-join reach map. Anchored
multi-jump shapes return within seconds.

**Deferred (not cut):** multi-hop routing (`--hops > 1`) — the route
frontier, pruning, and route shaping; the larger body of work still
ahead. `--start-jumps` / `--end-jumps`. A full MariaDB end-to-end
across the three multi-jump shapes against the Linux VM (production
reuses Slice 5's dialect-portable patterns; probes ran SQLite).

Full record: `docs/Planner/sixth_slice_completion_report.md`.

---

## Slice 7 — Bulk-Sale-Tax Safe Demand Cap (complete)

Elite penalises selling more than 25% of a station's advertised
demand in one transaction on Metals and Minerals. The planner caps
the planned destination quantity at `floor(demand * 0.25)` for
affected commodities; the advertised sell price is left alone
because no quantity above the safe threshold is ever planned. A
correctness fix landed ahead of multi-hop so future capital
propagation builds on truthful per-hop profit.

**Supported shape:** every Slice 1-6 shape — fixed-endpoint pair,
omitted-`--from`, omitted-`--to`, unanchored. The cap is universal:
any sensitive commodity at any destination is capped.

**Delivered:**

- Two helpers in `data_gateway.py` resolve the EDCD/FDevIDs category
  names "Metals" and "Minerals" against `Category.name` (the
  contract) rather than hardcoded local ids (deployment-local
  artefacts). `_bulk_sale_tax_category_ids` returns the category
  frozenset; `_bulk_sale_tax_sensitive_item_ids` returns the flat
  item frozenset the unanchored walk uses for O(1) membership.
- `TradeCandidate` and `CargoLine` gain `bulk_sale_tax_sensitive: bool`
  and `effective_destination_demand_units: int`. Raw demand stays on
  the DTO for display and downstream awareness; the effective field
  is what cargo fitting and unanchored ranking treat as the
  destination-side quantity cap.
- Fixed-pair and open-ended paths compute effective demand in Python
  via integer floor division (`demand_units // 4`); rows that would
  cap to effective zero are dropped per-pair, and the empty-result
  path treats this as "no profitable trade" rather than promoting it
  to a destination-side data failure.
- Unanchored carries `effective_demand_units` as a column on
  `td_unanchored_demand`, written via dialect-portable
  `cast(StationItem.demand_units * 0.25, Integer)` so SQLite and
  MariaDB both produce the floor without leaning on `FLOOR()` (which
  SQLite only ships when math functions are compiled in).
  `_realisable_profit_expression` reads the column directly so the
  cap reshapes which pair wins in SQL. The demand floor in the
  candidate filter rises from `_MIN_MEANINGFUL_DEMAND = 2` to `4`
  when sensitive, so rows that would cap to zero are filtered before
  materialisation.
- Cargo optimiser and the unanchored concrete-profit lower bound
  consume `effective_destination_demand_units`. Non-sensitive items
  are unchanged (effective == raw). The walk's outer cutoff
  (`capacity * profit_bound`) keeps using raw `profit_bound` — an
  overestimate for sensitive items, which only widens the search and
  never discards a winner.
- Renderer emits a hop-level note when at least one CargoLine on the
  hop has `bulk_sale_tax_sensitive AND quantity ==
  effective_destination_demand_units`: "Metals/Minerals capped at
  25% of destination demand to avoid the bulk-sale price reduction."
  One occurrence per affected hop, not per line.

**Verified:** fixed-pair Prince Prominence -> Evangelisti Colony at
`--capacity 2048` loaded Gold at 859 (= `floor(3436 / 4)`) and
Beryllium at 259 (= `floor(1038 / 4)`); both exactly cap-bound,
confirmed against destination demand values queried directly. Silver
took the capacity remainder, demonstrating the cap composes
correctly with capacity. Open-ended omitted-`--from` to Evangelisti
reproduced the same cap values from a different source. Unanchored
accepted by symmetry — the cap flows through the same
`effective_destination_demand_units` field used by the verified
anchored paths, and incremental QA at minutes per unanchored run
does not pay back. Run-short Colonia benchmark unchanged
(non-sensitive winners). Hop-level note appears as designed on
cap-affected runs and is silent on the non-sensitive benchmark.

**Deferred (not cut):** multi-hop routing (`--hops > 1`), now able to
compound per-hop profit on truthful sell-price assumptions. A
`--bulk-tax-mode safe|ignore|estimate` user option (the slice plan
deferred this deliberately; the current conservative
full-price-on-safe-quantity is the right default until the post-25%
discount curve is better understood). A MariaDB end-to-end across
the unanchored cap path (production patterns are dialect-portable;
verification ran on SQLite).

Full record: `docs/Planner/seventh_slice_completion_report.md`.

---

## Slice 9 — Max Price Filter and Testable Route Output (complete)

Two independent support pieces alongside the multi-hop work: an absolute
commodity-price cap and an expanded plain-text route output. The output
expansion is renderer-only and does not change planner behaviour.

**Supported shape:** every Slice 1-8 shape — fixed-pair, omitted-`--from`,
omitted-`--to`, unanchored, and known-origin multi-hop — now respects an
absolute price cap, and prints route results with auditable per-hop and
cumulative figures.

**Delivered:**

- `--max-price` / `--mp` adds a row-local cap on absolute commodity
  prices. Default 1,500,000 cr/t; `--max-price 0` disables. Active
  values apply as SQL predicates on `StationItem.supply_price` and
  `StationItem.demand_price` across every candidate-fetch path:
  fixed-pair, the failure-classifier source / destination probes,
  open-ended (including the onward-supply EXISTS used by multi-hop
  intermediate hops), the unanchored per-commodity reductions, and
  the unanchored item-bound walk. Capping the bound walk tightens
  the early-cutoff bound; the bound stays admissible.
- Default chosen against a live-database probe. Carrier fiction
  exists on both sides: 2,120 carrier supply rows and 383 carrier
  demand rows exceed 1.5M cr/t, supply topping out at 60.78M cr/t
  (Titan Maw Deep Tissue Sample) and demand at 49.85M cr/t (Titan
  Deep Tissue Sample). Highest non-carrier prices observed are
  1,049,029 cr/t (supply) and 1,085,334 cr/t (demand), both well
  under the chosen default — no legitimate row is removed at 1.5M.
  Both-sides capping is the right call: supply-side fiction is more
  prevalent than demand-side and is not naturally filtered, since a
  Cmdr with multi-billion credits sees no upper bound from
  affordability alone.
- Legacy `--old` branch unchanged. Argparse default is `None` so the
  new planner can tell "omitted" (apply configured default) from
  "explicit 0" (disabled); the `--old` branch maps `None` back to 0
  on entry to preserve its historical no-cap behaviour. Validation
  rejects negative `--max-price`; zero is allowed.
- Renderer expanded so route output exposes the per-hop buy / travel
  / sell / profit / cumulative numbers required for manual
  inspection. Route header now carries starting credits alongside
  total profit and final credits. Each hop renders as ordered blocks
  — From, Buy, Travel, To, Sell, Hop totals — with line-level totals
  (quantity, unit price, line cost / sale value, per-tonne profit,
  line profit) and hop-level closure (buy cost, sale value, hop
  profit, cumulative profit, post-sale credit balance). Cumulative
  profit and the credit balance are threaded across hops by the
  renderer; the figures are raw, not margin-adjusted, so they match
  the in-game balance after the sale.
- Existing renderer features preserved: partial-route warnings
  before the route, multi-hop diagnostics after, the bulk-sale-tax
  cap note inside the Buy block when a Metals / Minerals line
  cap-binds, and the practical-score line in the route header when
  score differs from raw profit.

**Verified:** smoke commands across the supported shapes — same-system
supercruise (Colonia short benchmark), multi-jump path with
intermediate systems (Sol -> ... -> Lave), multi-hop with cumulative
threading (Sol -> Lave at 3 hops), the bulk-sale-tax cap probe (Prince
Prominence -> Evangelisti at 2048t). Negative `--max-price` rejected
cleanly. `--max-price 1000` cuts legitimate sell-side trades by design
at that deliberately low cap — the probe evidence settles the
both-sides decision in light of the symmetry.

**Deferred (not cut):**

- **Performance Re-baseline of the unanchored shape under
  `--max-price` default.** The slice plan called for re-measuring
  unanchored wall-clock so the Slice 6 "early-cutoff acceleration
  is not representative of clean-data performance" caveat could be
  updated with honest clean-data numbers. Deferred to the multi-hop
  follow-up that revisits Slice 8: that work is likely to touch
  shared helpers and disturb wall-clock anyway, so measuring once
  afterwards saves the double-record. The Slice 6 caveat stays
  accurate in the meantime.
- **Fixed-station multi-hop route quality.** Slice 8 verified its
  destination-system diversity trim on `--from "Sol" --to "Lave"`
  (system-expanded origin) at 7,838,971 cr matching `--old`. The
  fixed-station shape `--from "Sol/Abraham Lincoln" --to "Lave/Lave
  Station"` on the same `--hops 3 --jumps-per 2 --ly-per 30 --fc N
  --age 2` returns 1,237,504 cr against `--old`'s 3,045,686 cr.
  Confirmed not caused by `--max-price`: same result with
  `--max-price 0`. Mechanism is beam-search myopia rather than beam
  concentration: with a pinned origin the Hop 1 frontier loses the
  system-expansion diversity that the Slice 8 fix relied on, and
  per-hop accumulated-score trimming favours myopic destinations
  over moderate ones that open excellent onward trades. Picked up
  as the next piece of work — revisiting Slice 8 — with probe set
  and design discussion warranted before any code change.

Full record: `docs/Planner/ninth_slice_completion_report.md`.

---

## Project Notes

### Data scale

`Station` has ~800K rows; `StationItem` has ~19M rows. Candidate queries must
stay aggressively selective and prune as early as possible, ideally in SQL.
Reducing the selected row set takes priority even where dead rows might aid
error granularity. Default posture: trust established invariants; avoid
speculative edge-case probes; push filtering into SQLAlchemy/DB predicates; use
Python-side validation only as a safety net on already-narrowed result sets; do
not add classification work unless it changes a real user-facing outcome or
prevents an observed failure.

### Multi-hop diagnostic granularity

Slice 2 uses lightweight aggregate failure tracking across the bounded one-hop
station-pair matrix — cheap because every pair is evaluated anyway. Before
extending from one-hop to multi-hop route expansion, reassess this: rich
rejection-state tracking across a combinatorial route frontier increases
complexity, memory churn, and pruning burden. Likely policy — keep detailed
aggregate errors for bounded one-hop evaluation; use coarse failure
counters/reasons for multi-hop by default; reserve richer telemetry for an
explicit diagnostics/debug mode.

### Distance calculation

`research/notebooks/DistanceCalc.ipynb` records micro-benchmarks of Euclidean
system-distance computation. The result that matters here: when a distance is
only being compared against a radius, test the un-rooted sum of squares against
the squared radius and skip the square root entirely. This is the basis for the
Slice 3 spatial query filtering on `<= L*L` in SQL rather than computing a
square root. The notebook's remaining content is Python-side micro-optimisation
(`dx*dx` over `dx**2`, a cached `sqrt` lookup) — largely moot for the planner,
which does distance work in SQL, not in a Python hot loop.

### Market data path

Market data reaches a route through stages, and only the first is the true
source:

```text
Spansh (bulk) + EDDN/ZMQ (live)  ->  TradeDangerous database  ->  trade run
```

`Spansh` provides a full-galaxy dump used as a bulk baseline (`spansh_plug.py`;
a full import takes hours). `EDDN` over ZMQ provides the live stream — the
freshest data, as commanders visit stations. These two are the upstream
origins.

`eddblink` is **not** an upstream source. It downloads an already-built
TradeDangerous database — normally the project server's — itself assembled from
Spansh and EDDN. Same schema; `trade run` would route against it directly. When
tracing where a stored value originates, look at `spansh_plug.py` and the
listener, not `eddblink`.

### Market data freshness

There is **no default age limit**. With no `--age`, every row is used whatever
its age. This is deliberate: no `--age` means the user wants everything. It also
supports the `trade olddata` playstyle — import the full Spansh dump, keep the
archaeology, and seek out long-unvisited stations to relight them by
republishing their markets. A default cutoff would silently remove that.
`--age` is the user's opt-in lever; the GUI persists it so it is set once.

Freshness is a lifecycle, not a fault. The project server purges old data on
its own configured schedule; a local database is never pruned unless the user
runs `eddblink`'s clean option, so it grows organically. Stale rows are
therefore expected — old fleet-carrier data especially will accumulate.

### Markets have two independent sides

Buying and selling at a station are independent. Fleet-carrier owners set their
markets by hand and price freely (pricing is not game-driven). So a station can
legitimately **supply only** (sell, buy nothing) or **demand only** (buy, sell
nothing). This drives a routing rule:

```text
supply-only station   can only be a route origin
demand-only station   can only be a route destination
mid-route station     must do both (multi-hop)
```

The legacy planner assumes every station both buys and sells — an assumption
from before fleet carriers existed — so it discards one-sided stations. The new
planner handles them, and can therefore find trades the legacy path cannot.

A route may legitimately end at a station whose own goods are not worth
carrying onward (low-value bulk such as biowaste is still valid supply).
Deciding where to draw the line on whether an end station's onward stock is
worth anything is not worth the development cost, and is deliberately not
attempted.

### Carrier dominance in unanchored winners

Across the P1–P6 probe sweeps (full record in
`fifth_slice_restructure_implementation_plan.md`), every unanchored
production winner under `--age 1/2/7` involved a fleet carrier on at least
one side of the trade. 88.9% had a carrier destination, 66.7% a carrier
source, 55.6% were carrier-to-carrier, and none were
non-carrier-to-non-carrier. Carrier markets carry the long tail of extreme
single-commodity margins because their prices are owner-set rather than
game-driven; the unanchored search correctly reports what the data
contains.

Titan Drive Component recurs in the P6 examples as a concrete case: it
is a required material for purchasing pre-engineered SCO drives at human
tech brokers, so demand is steady and supply is scarce, and carrier
owners price it freely. The unanchored search surfaces it because the
data legitimately shows extreme margins on it, not because of any
planner bias toward that commodity.

Carrier-backed routes are valid market observations and are not treated
as invalid. The user-side concern is **execution risk**, not planner
correctness: carrier stock and demand are player-controlled and can
change between an EDDN snapshot and a Cmdr's arrival, and the API
snapshot lag between observation and flight is unavoidable. The
`--age`, `--supply`, `--demand`, and `--fleet-carrier` Y/N/? filters
give Cmdrs the levers to control this. If execution risk becomes a
recurring complaint, the remediation is a Cmdr-facing filter or a docs
note, not a candidate-query change.

### Commodity supply and demand values

The importers copy the game's raw `supply` and `demand` figures verbatim. For a
commodity a station stocks and sells, the game reports the dormant buy side as
0 or 1; for one it only buys, the sell side is 0. A small `demand_units` on a
stocked item is therefore not a real buyer — it is the quiet other side of the
row. The planner treats a destination market as real only when `demand_units`
is 2 or more (`_MIN_MEANINGFUL_DEMAND` in `data_gateway.py`).

The `demand_level` and `supply_level` columns are hardcoded to `-1` by
`spansh_plug.py` and carry no information — do not use them as a signal.

### Runaway unit-profit prices and a possible default `--max-gain-per-ton` cap

Slice 6 testing surfaced an unanchored winner with Gold at a sell price of
~4.7M cr/ton. Gold's normal sell range is around 50K cr/ton; a ~100x figure
is almost certainly carrier price-edit noise — a price posted to EDDN
briefly, then changed, never available long enough for a Cmdr to execute.
Plausible motives include deliberate data-poisoning, or owners using a
carrier to move credits to an alt account. The planner cannot tell intent
from data; it correctly reports what the snapshot contained.

The Titan Drive Component routes that recur in unanchored winners (see the
Carrier dominance section above) are different in kind: TDC is a crafting
reagent for engineered SCO drives, genuinely scarce, and carrier-owners
price it freely — standard MMO auction-house economics. Those margins are
high but plausible; the Gold one is not.

Under discussion between Tromador and eyeonus: a default cap on
`--max-gain-per-ton` (value TBD) that would hide the obviously-artificial
extremes while leaving legitimate high-margin trades visible. Out of scope
for Slice 6; logged here so the surfaced case isn't forgotten.

Performance side-effect — the noise is not only an output-cleanliness
issue. `fetch_unanchored_trade_candidates` walks commodities in
descending profit-per-unit bound and stops when
`capacity * profit_bound <= best_total_profit`. A single carrier-noise
trade sets `best_total_profit` to an astronomical value on the first
commodity, and every legitimate commodity afterwards gets pruned.
Wall-clock therefore *appears* fast under noise and gets dramatically
slower with `--fc N` or any other filter that removes the noise — the
slow case is the real one. The early-cutoff acceleration measured
during Slice 6 validation runs is not representative of clean-data
performance.

### No separate `NoAffordableCargo` diagnosis for `trade run`

Do not add a separate diagnostic pass to distinguish:

```text
profitable trades exist, but the commander cannot afford any useful cargo
```

from the broader planner result:

```text
No profitable trade was found with the current settings.
```

This is an intentional product/engineering decision, not an omitted check.

Reasons:

- The distinction is expensive to prove because the planner would have to keep or re-run enough candidate state to separate “no profitable candidate exists” from “candidate exists but cannot be bought after credits / insurance / limit constraints”.
- It is an edge case in normal play. Even very low balances can usually buy some cheap commodity if range, filters, and market data are otherwise viable.
- If a commander is so broke that market trading cannot buy meaningful cargo, `trade run` is the wrong recovery tool. The practical advice is outside the route planner: do a local mission, courier work, sell modules/cargo, or otherwise raise starting capital.
- The current message is sufficiently accurate for the planner’s purpose: the supplied settings did not produce an actionable profitable trade.
- More specific “you cannot afford cargo” wording would not materially improve the next action inside `trade run`, and risks spending runtime on a diagnostic that rarely matters.

Keep the user-facing failure under the existing no-result family:

```text
No profitable trade was found with the current settings.
```

Do not add a costly affordability-only probe unless a cheap signal already falls out of the main candidate path.### No separate `NoAffordableCargo` diagnosis for `trade run`

Do not add a separate diagnostic pass to distinguish:

```text
profitable trades exist, but the commander cannot afford any useful cargo
```

from the broader planner result:

```text
No profitable trade was found with the current settings.
```

This is an intentional product/engineering decision, not an omitted check.

Reasons:

- The distinction is expensive to prove because the planner would have to keep or re-run enough candidate state to separate “no profitable candidate exists” from “candidate exists but cannot be bought after credits / insurance / limit constraints”.
- It is an edge case in normal play. Even very low balances can usually buy some cheap commodity if range, filters, and market data are otherwise viable.
- If a commander is so broke that market trading cannot buy meaningful cargo, `trade run` is the wrong recovery tool. The practical advice is outside the route planner: do a local mission, courier work, sell modules/cargo, or otherwise raise starting capital.
- The current message is sufficiently accurate for the planner’s purpose: the supplied settings did not produce an actionable profitable trade.
- More specific “you cannot afford cargo” wording would not materially improve the next action inside `trade run`, and risks spending runtime on a diagnostic that rarely matters.

Keep the user-facing failure under the existing no-result family:

```text
No profitable trade was found with the current settings.
```

Do not add a costly affordability-only probe unless a cheap signal already falls out of the main candidate path.

### Reference probe — bulk-sale-tax cap

A known-working fixed-pair probe that exercises the Metals/Minerals
`floor(demand * 0.25)` cap:

```text
trade run \
  --from "Col 285 Sector DU-B b28-8/Prince Prominence" \
  --to   "LP 98-132/Evangelisti Colony" \
  --capacity 2048 --credits 100000000 \
  --hops 1 --jumps-per 8 --ly-per 40
```

The optimiser fills 2048 t with three sensitive commodities. The two
highest-margin ones cap-bind at exactly `floor(demand / 4)`, the third
takes the capacity remainder under its own (non-binding) cap. Demand
values drift, so the exact quantities change over time; if no sensitive
commodity ends up cap-binding, `docs/Planner/bulk_sale_tax_candidates.sql`
will surface fresh pairs where `supply >= safe_cap` and
`safe_cap < test capacity`.

---

## Filter Semantics Reference

Any work touching station or commodity filters must preserve these. The Y/N/?
state filters are a settled contract, implemented in `run_request.py`
(`_normalise_state_filter`). The pad-size model has been revised to a ship-fit threshold, implemented
as part of Slice 3 — see below.

### Y/N/? state filters — accepted-state sets

`--black-market`, `--fleet-carrier`, `--settlement`, and `--planetary` are
accepted-state **sets**, not three unrelated absolute modes:

```text
Y    known yes only
N    known no only
?    unknown only
Y?   known yes or unknown
N?   known no or unknown
YN   known yes or known no, excludes unknown
YN?  every state — equivalent to no filter (normalised away)
```

Match test: `(station_state or "?").upper() in requested_states`.

### Pad size — ship-fit threshold

Revised model, delivered in Slice 3.

`--pad-size` takes one ship pad size — `S`, `M`, or `L` — meaning "the ship
needs at least this pad". A station qualifies when its largest pad is at least
the requested size:

```text
L    large-max stations only
M    medium- or large-max stations, plus unknown-pad
S    every station — small, medium, large, or unknown pad
```

`?` is not a valid input: `--pad-size ?` (or `M?`, or any multi-letter value)
is rejected with a validation error.

A station whose own pad size is unknown qualifies whenever the threshold
admits a medium pad — under `--pad-size S`, `--pad-size M`, or no `--pad-size`
— and is dropped only under `--pad-size L`. The reasoning: almost every
station that is not a large starport still has at least a medium pad (orbital
outposts and most small planetary ports included), so a station whose pad is
merely unrecorded is a safe bet for a ship that would accept a medium pad
anyway. A ship that specifically needs a large pad cannot take that gamble.

This is a deliberate, accepted risk: under `--pad-size M`, an unknown-pad
station that turns out to be small-only would mis-route a ship that needs a
medium pad. It is judged worth taking for the extra reachable stations, and to
be revisited if it draws complaints.

The earlier model's "exclude large starports to find trades larger ships
cannot reach" use case is deliberately not carried over — simplicity was
judged to outweigh it.

---

## Deferred Decisions

Agreed direction not yet scheduled into a slice — pick these up when the
relevant slice opens.

### `--sco` flag

A new option declaring the user's ship has a Supercruise Overcharge drive.
When set, it clamps `--ls-penalty` to 0 and overrides any user-supplied
`--ls-penalty` value — the in-system travel-time concern the curve solves
is materially weaker for SCO-equipped ships, which can reach distant
stations in seconds rather than minutes of supercruise.

```text
--sco set        --ls-penalty treated as 0
--sco not set    --ls-penalty works as today
```

Not scoped into any current slice. How the user signals SCO ownership —
per-run flag, persisted ship profile, journal detection — is the UX
question to resolve when the option lands.

---

## Cleanup Candidates

Noted-for-later items — not bugs, no urgency, worth doing when convenient.

### `--pad-size` CLI parser message mismatch

The shared `--pad-size` CLI parser (`PadSizeArgument.PadSizeParser` in
`commands/parsing.py`) still validates and describes the older combination
model: it accepts any string of `S`/`M`/`L`/`?` characters, and its error
message and help text cite `SML?`-style combinations. `trade run` now treats
`--pad-size` as a single ship-fit threshold, and its planner-side validation
rejects `?` and multi-letter input separately.

Effect: an invalid `--pad-size` for `trade run` can fail at either layer with a
different message. A non-pad character such as `XL` is rejected by the parser
with the outdated combination wording; `?` or a valid-letter combination passes
the parser and is rejected by the planner with the correct "one of S, M, or L"
message. Rejection is always clean — no traceback — only the messaging is
inconsistent.

Not a simple message swap: `PadSizeArgument` is shared with `sell`, `buy`,
`local`, `nav`, and `olddata`, which still use the combination model. A fix
means either a `trade run`-specific pad parser and message, or accepting the
mismatch.

### `StationHasNoUsablePriceData` subclass wording

The planner-side raise messages for `SourceHasNoSellingData` and
`DestinationHasNoBuyingData` (in `planner/run_onehop.py`) still use internal
phrasing — "No reachable source station had usable selling data." and
similar. These are now surfaced through `PlannerResultError` without the
generic data-failure footer, so the wording is the only remaining issue;
"reachable" leaks an internal concept into a user-facing line. A small
follow-up could reword these to match the friendlier "no usable market
data for the chosen \<place\>" style used by the rest of the planner
failure messages. Out of scope for the failure-message cleanup that
introduced `PlannerResultError`.
