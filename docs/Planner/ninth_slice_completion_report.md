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

### Performance Re-baseline (out of slice)

The slice plan called for re-measuring unanchored wall-clock under
`--max-price` default so the Slice 6 caveat — "early-cutoff
acceleration is not representative of clean-data performance" —
could be updated with honest numbers. The three commands were:

```text
trade run --capacity 720 --credits 200000000 --hops 1 --jumps-per 2 --ly-per 30 --age 1
trade run --capacity 720 --credits 200000000 --hops 1 --jumps-per 2 --ly-per 30 --age 1 --fc N
trade run --capacity 720 --credits 200000000 --hops 1 --jumps-per 2 --ly-per 30 --age 1 --max-price 0
```

Deferred to the multi-hop follow-up that revisits Slice 8. That work
is likely to touch shared helpers — `_reachable_station_query`, the
temp-table memo, possibly the candidate-fetch shape — and any of
those would disturb unanchored wall-clock too. Recording timings now
and re-recording them after the multi-hop changes would double the
work for a snapshot already known to be provisional. The Slice 6
caveat remains accurate until the re-baseline is run.

### Fixed-station multi-hop route quality (Slice 8 follow-up)

Smoke testing of the multi-hop Part B output exposed a regression on
the fixed-station shape that Slice 8 did not verify:

```text
Command: trade run --from "Sol/Abraham Lincoln" --to "Lave/Lave Station"
         --capacity 128 --credits 5000000 --hops 3 --jumps-per 2
         --ly-per 30 --fc N --age 2

new planner:  1,237,504 cr
legacy --old: 3,045,686 cr
```

Confirmed not caused by `--max-price`: the same command with
`--max-price 0` returns the identical 1,237,504 cr figure.

Slice 8 verified its destination-system diversity trim on `--from
"Sol"` (system-expanded origin), at 7,838,971 cr matching `--old`.
The fixed-station shape was not in that verification.

The mechanism is beam-search myopia rather than beam concentration.
Slice 8 addressed concentration: near-duplicate stations in the same
destination system crowding the top-50 frontier slots, fixed by
keeping at most one node per destination system in the global trim.
With a pinned origin, the Hop 1 frontier loses the system-expansion
diversity the Slice 8 fix relied on. The diagnostics from the
regression run confirm the shape:

```text
Layer 1: 1 in, 1 calls, 50 children, kept 36
Layer 2: 36 in, 36 calls, 649 children, kept 50
```

Either the LP 855-34 system (whose Acton Port is the route's
critical intermediate in the `--old` answer) does not survive Hop 1's
per-hop profit ranking into the top 36 unique-system frontier nodes,
or it survives but the LP 855-34 -> Delkar transition does not
survive Layer 2's accumulated-score trim of the 649 generated
children to the kept 50.

Either way, beam scoring by accumulated per-hop profit favours
myopic destinations: a moderate Hop 1 that opens excellent onward
trades is dropped in favour of a stronger Hop 1 that does not lead
anywhere as profitable. The Slice 8 fix does not help here because
the problem is search shape, not duplication.

To pick up as the next piece of work — revisiting Slice 8 — with a
probe set and design discussion before any code change. A hopeful
one-line beam widening or scoring tweak is unlikely to produce a
robust fix.

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
