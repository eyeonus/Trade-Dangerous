# Slice 9 Completion Report

## Status

**Slice 9 is complete.**

Two independent support pieces shipped alongside the larger multi-hop
work: `--max-price` as a row-local absolute commodity-price cap, and
an expanded plain-text route output for auditable manual inspection.
Both were planned as side quests in `ninth_slice_implementation_plan.md`
and committed without touching the planner's route-selection behaviour.

The Performance Re-baseline portion of the slice plan was deferred —
rationale below.

A multi-hop route-quality regression on the fixed-station shape
surfaced during Part B smoke testing. It is not caused by Part A and
not in scope for this slice; it is captured as the next piece of work,
to revisit Slice 8.

## Part A — `--max-price` / `--mp`

### Public surface

```text
--max-price <N>     row-local cap on absolute StationItem prices
--mp <N>            short alias

omitted             apply DEFAULT_MAX_PRICE (1,500,000 cr/t)
explicit 0          disabled — no absolute price cap
explicit N >= 0     use N cr/t as the cap
negative            validation failure: --max-price must not be negative
```

### Default justification

A live-database probe inspected carrier and non-carrier rows
separately at four sanity thresholds:

```text
threshold (cr/t)   supply rows above threshold   demand rows above threshold
                   carrier    non-carrier        carrier    non-carrier
1,500,000          2,120      0                  383        0
5,000,000          1,009      0                  288        0
10,000,000         602        0                  241        0
50,000,000         1          0                  0          0
```

Highest non-carrier observations:

```text
supply: 1,049,029 cr/t — Thargoid Heart at Musca Dark Region/Betancourt Base
demand: 1,085,334 cr/t — Musgravite at ICZ FB-X c1-19/Grant City
```

The 1.5M default sits comfortably above legitimate non-carrier maxima
on both sides while removing 2,503 obvious carrier-fiction rows in a
single predicate. No legitimate row is removed at the chosen cap.

The probe also showed supply-side fiction to be more prevalent than
demand-side (2,120 vs 383 rows above 1.5M), with top supply prices at
60.78M cr/t (Titan Maw Deep Tissue Sample) and top demand prices at
49.85M cr/t (Titan Deep Tissue Sample). Both-sides capping is therefore
the right call. The alternative — capping demand only on the grounds
that supply is naturally filtered by `available_credits` — fails for
any Cmdr with multi-billion credits, who sees no upper bound from
affordability and would otherwise see fictional carrier supply rows
leak into route candidates.

### Implementation

Request layer (`tradedangerous/planner/run_request.py`):

```text
DEFAULT_MAX_PRICE constant exposed at module top
max_price: int field on RunRequest, default DEFAULT_MAX_PRICE
_resolve_max_price helper applies the default on omission while
  preserving explicit 0 (= disabled)
```

CLI parser (`tradedangerous/commands/run_cmd.py`):

```text
--max-price and --mp registered with type "credits" and parser
  default None
new-planner branch resolves None via _resolve_max_price
--old branch maps None back to 0 so the legacy planner sees its
  historical no-cap state
```

Validation (`tradedangerous/planner/validation.py`):

```text
negative --max-price rejected with InvalidNumericOption
zero is permitted and means disabled
```

Data gateway (`tradedangerous/planner/data_gateway.py`):

Row-local `<= max_price` predicates conditionally appended in every
candidate-fetch path:

- `fetch_station_pair_candidates` — fixed-pair source supply +
  destination demand
- `_classify_zero_result_failure` — both probes, so the failure
  message stays consistent under the cap (a station whose only
  rows are above the cap has no usable data under the current
  settings)
- `fetch_open_ended_trade_candidates` — supply, demand, and the
  onward-supply EXISTS used by multi-hop intermediate hops
- `_unanchored_item_bounds` — supply min and demand max, tightening
  the walk's early-cutoff bound while keeping it admissible
- `_reduce_supply_by_system` and `_reduce_demand_by_system` — the
  unanchored per-commodity reductions

Each site appends the predicate only when `request.max_price > 0`,
matching the existing `min_supply` / `cutoff` conditional style.

### Verification

Smoke runs:

- Help output exposed `--max-price` and `--mp`.
- Negative `--max-price` failed validation cleanly with no traceback.
- Colonia short benchmark identical under default `--max-price` and
  `--max-price 0` (commodity prices in the benchmark are well under
  the cap on both sides).
- `--max-price 1000` correctly cut legitimate sell-side trades, e.g.
  Liquor at 1303 cr/t demand. The deliberately-low cap working as
  designed prompted a sanity discussion about whether to cap both
  sides or only demand; the probe evidence above settled it in
  favour of both sides.
- Legacy `--old` branch unchanged: argparse default `None` is mapped
  back to 0 on entry, preserving historical no-cap behaviour in the
  comparison path.

Committed as `d244a142`.

## Part B — Testable Route Output

### What changed

Plain-text route output expanded in `render_run_result` /
`_render_route` / `_render_hop`. The route header now carries:

```text
Route:
  <start> -> <end>
  Starting credits: N cr
  Total route profit: N cr
  Final credits: N cr
  Practical score: N         (only when it differs from raw profit)
```

Each hop renders as ordered blocks:

```text
Hop K:
  From: <source>

  Buy:
    Q t Commodity @ P cr/t = T cr
    Metals/Minerals capped at 25% ...   (when bulk-sale cap binds)

  Travel:
    Same-system supercruise              (or)
    N jump(s), D.DD ly: A -> ... -> B

  To: <destination>

  Sell:
    Q t Commodity @ P cr/t = T cr
      Profit: P cr/t, T cr total

  Hop totals:
    Buy cost: N cr
    Sale value: N cr
    Hop profit: N cr
    Cumulative profit: N cr
    Credits after sale: N cr
```

Cumulative profit and the credit balance are threaded across hops by
the renderer. The plan called for the credit balance to be raw rather
than margin-adjusted — what shows up in the in-game balance after the
sale, not the planner-internal trusted-for-onward-spend figure — and
that is what the renderer prints.

Existing renderer features preserved unchanged: the partial-route
warning header, the multi-hop diagnostics footer, the bulk-sale-tax
cap note inside the Buy block, and the practical-score line in the
route header when score differs from raw profit.

### Verification

Smoke commands exercised every conditional branch in the renderer:

- Same-system supercruise: Colonia short benchmark — `Travel:`
  rendered as `Same-system supercruise`.
- Multi-jump path with intermediate systems: rendered as
  `N jump(s), D.DD ly: A -> ... -> B`.
- Multi-hop with cumulative threading: Sol -> Lave at 3 hops.
  Hop 1 cumulative profit = Hop 1 raw profit; Hop 2 cumulative
  = Hop 1 + Hop 2 raw; Hop 3 cumulative = total route profit; the
  Hop 3 credits-after-sale figure matched the route header's
  Final credits.
- Bulk-sale-tax cap note: Prince Prominence -> Evangelisti at
  2048t. Multi-commodity Buy and Sell blocks rendered with the cap
  note in the Buy block.

Committed as `a0c22484`.

## Deferrals

### Performance Re-baseline (out of slice) — investigated and remediated

The slice plan called for re-measuring unanchored wall-clock under
`--max-price` default so the Slice 6 caveat — "early-cutoff
acceleration is not representative of clean-data performance" —
could be updated with honest numbers. Originally deferred to the
multi-hop follow-up that revisits Slice 8. When the re-baseline
was attempted (2026-05-27) the run did not complete in usable time
even under realistic filters, escalating to a root-cause
investigation. Two SQLite cost-model failures were proven against
the live database via probes v2–v6:

- **Empty-temp pathology.** SQLite picks a query plan for the
  match step that drives a `System x System` cross-join and
  treats the run-scoped temp tables (`td_unanchored_supply`,
  `td_unanchored_demand`) as inner probes. When either temp table
  has no rows — the norm for carrier-only commodities at the top
  of the bound list under `--fc N` — the join still evaluates
  millions of spatial pairs before discovering zero matches. ~5
  minutes per empty walk on the live data.
- **Missing temp-table statistics.** Even on non-empty temps,
  SQLite picks the same System-driven plan because the temp
  tables have no row-count stats. The cost model anchors on
  `System` (~80K rows, has stats from database build) and inverts
  the join order against the ~1-3K-row temp tables.

Remediation in commit `14d1222f`: empty-temp guard
(`_temp_has_rows`) before `_match_via_on_demand_reach`, plus
`ANALYZE td_unanchored_supply; ANALYZE td_unanchored_demand;`
after each per-commodity reduction. Both pieces are required —
`ANALYZE` alone does not fix the empty case (writes nothing
useful to `sqlite_stat1` for an empty table; same bad plan
persists, proven by probe v6: 256 s on walk 1 with empty temps
post-`ANALYZE`).

Measured wall-clock post-remediation, under realistic filters
(`--age 3 --fc N --planetary N --pad-size L --jumps-per 3
--ly-per 30 --capacity 720 --credits 200M`):

```text
--max-price 0               : 2m 33.228s real
default --max-price (1.5M)  : 2m 33.839s real
```

Identical route in both cases (Bhattra/Levinson Orbital →
Fengiri/Mille Gateway, 35,742,249 cr profit, 469 t Gold + 251 t
Silver, 2 jumps over 51.41 ly).

The `--age 1` shape from the original three-command re-baseline
was superseded: the local database's freshest entry is ~2 days
old, so `--age 1` would not exercise representative data.

Full investigation record:
`docs/Planner/unanchored_slow_handover.md`.

### Fixed-station multi-hop route quality (Slice 8 follow-up) — investigated and closed

Smoke testing of the multi-hop Part B output exposed a divergence on
the fixed-station shape that Slice 8 did not verify:

```text
Command: trade run --from "Sol/Abraham Lincoln" --to "Lave/Lave Station"
         --capacity 128 --credits 5000000 --hops 3 --jumps-per 2
         --ly-per 30 --fc N --age 2

new planner:  1,237,504 cr
legacy --old: 3,045,686 cr
```

The handover (`docs/Planner/slice_8_followup_handover.md`)
hypothesised beam-search myopia. Investigation (2026-05-26,
commit `f360da46`) ruled that out and traced the divergence to a
phantom demand row at LP 855-34/Acton Port: `supply_units = 2323,
demand_units = 1` — the dormant buy side of a stocked commodity.
Slice 3's `_MIN_MEANINGFUL_DEMAND = 2` correctly rejects the row,
so the new planner declines the trade; legacy `--old` does not
filter on the demand floor and computes its 3,045,686 cr total
against an in-game-unfillable Hop 1 sale.

Closely comparable shapes confirm the new planner is healthy:

```text
trade run --from "Sol" --to "Lave/Lave Station" --hops 3
  new:   5,059,696 cr   (3.1% ahead of --old)
  --old: 4,907,264 cr

trade run --from "Sol" --to "LP 855-34/Acton Port" --hops 1
  both planners: 882,176 cr
```

The hypothesised beam-search myopia was not the mechanism. Full
close-out: `docs/Planner/slice_8_followup_handover.md` (carries a
Resolution section appended at close-out time).

## Files Changed

- `tradedangerous/planner/run_request.py` — `DEFAULT_MAX_PRICE`
  constant, `max_price` field, `_resolve_max_price` helper, builder
  wiring.
- `tradedangerous/commands/run_cmd.py` — `--max-price` / `--mp`
  parser argument, `--old` branch default mapping.
- `tradedangerous/planner/validation.py` — negative-value rejection.
- `tradedangerous/planner/data_gateway.py` — SQL `<= max_price`
  predicates on every candidate-fetch path.
- `tradedangerous/planner/render_text.py` — expanded route output.

## Commits

- `d244a142` — feat(planner): apply --max-price absolute price cap
- `a0c22484` — feat(planner): expand trade run plain-text route output
