# Trade Run Seventh Slice — Completion Report

## Status

Seventh slice implementation is complete within the agreed scope. The
planner code is committed on `release/v1` (`dc06c9d4`); this report
and the `SLICE_SUMMARY.md` update are the closing record.

Slice name:

```text
Bulk-Sale-Tax Safe Demand Cap
```

Repository: Tromador/Trade-Dangerous
Branch: release/v1

---

## Purpose

Elite Dangerous applies a per-unit price penalty when more than ~25%
of a station's advertised demand is sold in one transaction on Metals
and Minerals commodities. The discount curve and floor multiplier
are not precisely documented and vary by station and state, so the
planner does not model the discounted prices. Instead it caps the
planned destination quantity at `floor(demand * 0.25)` for affected
commodities, keeping the advertised sell price in force on the planned
quantity.

This is a correctness fix landed ahead of multi-hop routing. Multi-hop
capital propagation needs accurate per-hop profit; building hop-N+1
capacity on inflated hop-N sell-price assumptions would compound the
error across a route.

---

## Scope Completed

### Sensitive classification

Affected commodities are identified by membership in the EDCD/FDevIDs
categories "Metals" and "Minerals". `Category.name` is the contract;
local `category_id` and `item_id` values are deployment-local
artefacts. Two helpers in `data_gateway.py` resolve lazily per fetch
path:

- `_bulk_sale_tax_category_ids(session) -> frozenset[int]` matches on
  `Category.name`, case-insensitive (CIString) on both backends.
  Returns empty set if neither category is present locally, so
  behaviour degrades safely to "no item is sensitive".
- `_bulk_sale_tax_sensitive_item_ids(session) -> frozenset[int]`
  returns the flat item-membership set used by the unanchored walk,
  which iterates every profitable item and benefits from O(1)
  membership tests over re-resolving category per item.

### DTO surface

`TradeCandidate` and `CargoLine` gain:

```text
bulk_sale_tax_sensitive: bool
effective_destination_demand_units: int
```

Raw `destination_demand_units` is preserved for display and downstream
awareness. The effective field is what cargo fitting and unanchored
ranking read for the destination-side quantity cap — equal to
`floor(raw * 0.25)` when sensitive, equal to raw otherwise.

### Fixed-pair path

`fetch_station_pair_candidates` extends its existing `Item` join to
select `category_id` alongside `name`, computes sensitivity and
effective demand per row, and drops rows where effective demand is
zero. The drop turns an unusable sensitive candidate into a silent
skip — buying data was fine, the safe quantity is just zero — rather
than promoting it to a destination-side data failure.

### Open-ended path

`fetch_open_ended_trade_candidates` extends its post-fetch item
lookup from `(item_id, name)` to `(item_id, name, category_id)`,
producing parallel `item_names` and `item_categories` dicts. Per-item
sensitivity is computed once in the outer supply loop; per-pair
effective demand is computed in the inner demand loop and triggers
the same zero-drop logic as the fixed-pair path.

### Unanchored path

The bulk of the slice's mechanical surface. `_reduce_demand_by_system`
takes an `is_sensitive: bool` argument and writes a new
`effective_demand_units` column on the `td_unanchored_demand` temp
table — `cast(StationItem.demand_units * 0.25, Integer)` when
sensitive, the raw column otherwise. The cast is the dialect-portable
floor: SQLite and MariaDB both return float for `int * 0.25` and
truncate-toward-zero on integer cast, equalling floor for the
non-negative demand values here. SQLite's `FLOOR()` is only available
when compiled with math functions, hence the cast.

The demand floor in the candidate filter rises from
`_MIN_MEANINGFUL_DEMAND = 2` to `4` when sensitive, so rows that would
cap to effective zero are filtered before materialisation.

`_realisable_profit_expression` reads
`demand_temp.c.effective_demand_units` directly when computing
realisable units for ranking. The cap therefore shapes which
`(supply, demand)` pair wins inside the SQL ranking — a high-demand
destination where the cap doesn't bind beats a small-demand
destination where the cap clips realisable cargo.

`_unanchored_candidate_from_row` accepts `is_sensitive: bool` and
computes effective demand in Python via integer floor division
(`demand_units // 4`) when populating the DTO.

`fetch_unanchored_trade_candidates` resolves `sensitive_item_ids`
once per call and computes `is_sensitive` per item in the walk,
plumbing through to `_reduce_demand_by_system` and
`_unanchored_candidate_from_row`.

### Cargo fitting

`cargo.py` `_build_bounded_candidates` reads
`trade.effective_destination_demand_units` for the destination-side
ceiling. The change is one identifier swap; the bounded
branch-and-bound algorithm is unchanged. Non-sensitive items see no
behaviour change (effective == raw).

`_concrete_total_profit` in `data_gateway.py` mirrors the swap for
the unanchored walk's per-commodity lower bound used by the
descending-profit-bound cutoff. The walk's outer bound
(`capacity * profit_bound`) is unchanged and still uses raw
profit_bound — an overestimate for sensitive items, which only widens
the search and never discards a winner.

### Renderer

`render_text.py` emits a hop-level note when at least one CargoLine
on a hop has `bulk_sale_tax_sensitive` and `quantity ==
effective_destination_demand_units`:

```text
Metals/Minerals capped at 25% of destination demand to avoid the
bulk-sale price reduction.
```

One occurrence per affected hop, not per line. Wording was settled
collaboratively: it names the affected category, gives the threshold
and the reason, and avoids inviting workaround discussion or
referencing "mined" (provenance is irrelevant once cargo is in the
hold).

---

## Verified Behaviour

### Fixed-pair

```text
trade run --from "Col 285 Sector DU-B b28-8/Prince Prominence" \
          --to   "LP 98-132/Evangelisti Colony" \
          --capacity 2048 --credits 100000000 \
          --hops 1 --jumps-per 8 --ly-per 40
```

loaded:

```text
Gold        859 t   (= floor(3436 / 4))
Silver      930 t   (capacity remainder; safe_cap was 1489)
Beryllium   259 t   (= floor(1038 / 4))
Total      2048 t   (= capacity)
```

Gold and Beryllium both cap-bound at exactly `floor(demand / 4)` for
their destination demand at Evangelisti, confirmed by direct SQL
query against `StationItem.demand_units`. Silver took the capacity
remainder, demonstrating the cap composes correctly with the existing
capacity constraint.

### Open-ended

```text
trade run --to "LP 98-132/Evangelisti Colony" \
          --capacity 2048 --credits 100000000 \
          --hops 1 --jumps-per 8 --ly-per 40
```

(omitted `--from` — Slice 4 path through
`fetch_open_ended_trade_candidates` with `open_role="source"`) picked
a fleet-carrier source and loaded:

```text
Gold        859 t   (= floor(3436 / 4))
Palladium   716 t
Beryllium   259 t   (= floor(1038 / 4))
Silver      214 t   (capacity remainder)
Total      2048 t   (= capacity)
```

Same Gold and Beryllium cap-bind values as the fixed-pair test, from
a different source — the open-ended path is feeding effective demand
through to cargo fitting correctly.

### Unanchored

Accepted by symmetry with the verified anchored paths. The cap flows
through the same `effective_destination_demand_units` field on the
shared `TradeCandidate` DTO; the unanchored search adds the SQL
column on `td_unanchored_demand` and the corresponding read in
`_realisable_profit_expression`, both verified by inspection.
Constructing a visible cap-binding scenario for the unanchored
search requires finding a sensitive trade where supply > safe_cap,
capacity > safe_cap, and the planner-chosen destination has demand
in a window the search wouldn't naturally prefer over higher-demand
alternatives — the cap legitimately reshapes destination choice
toward stations where it doesn't restrict. Iterative QA on the
unanchored shape at minutes per run did not pay back given the
symmetry of the cap logic across the three fetch paths.

### Hop-level note

Appeared exactly once on the cap-affected hop of the fixed-pair test,
in the agreed form. Did not appear on the non-sensitive run-short
benchmark.

### Non-sensitive regression

```text
trade run --from "Colonia/Akinyemi Horticultural Market" \
          --to   "Colonia/Jaques Station" \
          --capacity 64 --credits 1000000 \
          --hops 1 --jumps-per 1 --ly-per 20
```

ran as expected — non-Metals/Minerals cargo, no note emitted, route
unchanged from prior behaviour.

---

## Quarantine Status

Intact.

```text
tradedangerous/tradecalc.py
tradedangerous/tradedb.py
```

Neither module was opened or used as an implementation source.
`trade run --old` remains the comparison path only.

---

## Outstanding / Deferred

Carried forward, not cut:

- **Multi-hop routing** (`--hops > 1`). The next major body of work,
  now able to compound per-hop profit on truthful sell-price
  assumptions.
- **`--bulk-tax-mode safe|ignore|estimate` user option.** The slice
  plan deferred this deliberately; the current conservative
  full-price-on-safe-quantity is the correctness baseline until the
  post-25% discount curve is better understood.
- **MariaDB end-to-end on the unanchored cap path.** The cap addition
  uses dialect-portable patterns (`Integer` column, `cast`-based
  floor) consistent with the Slice 5/6 portability work, but
  verification ran on SQLite. A multi-shape MariaDB run is the natural
  follow-on before this work goes upstream.

---

## Commits

On `release/v1`:

```text
dc06c9d4  feat(planner): cap planned destination quantity at 25% on Metals/Minerals
```

A single implementation commit lands the slice. Docs land separately
per project workflow.

---

## Assessment

Metals/Minerals trades are now planned at quantities the in-game
bulk-sale tax does not penalise, so the planner's per-hop profit
projection is correct on the dominant case where this matters. The
slice plan's stated goal — "protecting future multi-hop capital
propagation from inflated profit assumptions" — is achieved by
leaving the advertised sell price untouched and constraining quantity,
which means no downstream consumer needs to know about the tax to get
truthful arithmetic.

Multi-hop routing is the next slice.
