# Slice 9 Implementation Plan — Max Price Filter and Testable Route Output

## Status

Planned.

## Purpose

Slice 9 is a small support slice alongside the main multi-hop planner work.

It has two independent parts:

- **Part A:** add a maximum absolute commodity price filter using `--max-price` / `--mp`.
- **Part B:** improve `trade run` route output so test runs expose the basic buy, travel, sell, and profit numbers needed for manual inspection.

This slice does not extend route shapes or change multi-hop search strategy.

---

# Part A — `--max-price` / `--mp`

## Goal

Filter obvious carrier-fiction price rows while preserving reasonable carrier trading.

This must be a different lever from `--fleet-carrier N`.

`--fleet-carrier N` removes carriers entirely.

`--max-price` should preserve ordinary carrier market rows and remove only rows whose absolute commodity price is beyond the configured sanity cap.

## User-Facing Behaviour

Add:

```text
--max-price
--mp
```

Semantics:

```text
omitted       -> use default cap
explicit 0    -> disable max-price filtering
explicit N    -> use N cr/t as the cap
```

Default:

```text
1,500,000 cr/t
```

The cap applies globally to market prices used by `trade run`:

```text
source-side supply_price must be <= max_price
destination-side demand_price must be <= max_price
```

When disabled with `--max-price 0`, no absolute price cap is applied.

## Evidence for Default

A local database probe was run against `data/TradeDangerous.db`.

At a candidate cap of `1,500,000 cr/t`, carrier rows preserved were:

```text
carrier demand rows preserved: 10,316 / 10,670 = 96.68%
carrier supply rows preserved: 19,585 / 20,938 = 93.54%
```

So the cap is not equivalent to excluding fleet carriers.

The same probe showed the highest known non-carrier prices in the inspected data were below the proposed default:

```text
highest known non-carrier demand price observed: 1,085,334 cr/t
highest known non-carrier supply price observed:   247,599 cr/t
```

The observed non-carrier high prices were legitimate high-value mineral demand, including:

```text
Musgravite
Void Opal
Grandidierite
Monazite
Rhodplumsite
Benitoite
Serendibite
Alexandrite
Low Temperature Diamonds
```

A lower global cap such as `99,000 cr/t` would remove a large amount of legitimate non-carrier demand and is therefore unsuitable as a global default.

## Design Decision

Use a global `1,500,000 cr/t` max-price default.

Do not make the filter carrier-only.

Reasons:

```text
1.5M preserves the observed legitimate non-carrier high-price rows.
It removes the obvious multi-million carrier-fiction rows.
It does not depend on station type classification being perfect.
It is a cheap row-local SQL predicate on StationItem.
It targets absolute price fiction directly.
```

## SQL-First Requirement

`--max-price` must be applied early in SQL wherever candidate market rows are selected.

This is a row-local predicate:

```text
StationItem.supply_price <= max_price
StationItem.demand_price <= max_price
```

It must not be implemented as:

```text
renderer filtering
final-route filtering
primary Python post-filtering
```

Python-side checks may exist only as defensive guards after SQL has already narrowed candidate rows.

## Expected Implementation Points

### Request Layer

Add a request field:

```text
max_price: int
```

Add a named default constant:

```text
DEFAULT_MAX_PRICE = 1500000
```

Parser/request behaviour must preserve omitted versus explicit zero:

```text
parser omitted value -> None
request max_price    -> 1500000

parser explicit 0    -> 0
request max_price    -> 0

parser explicit N    -> N
request max_price    -> N
```

Direct construction of `RunRequest()` should use the same effective default.

### Command Parser

Add:

```text
--max-price
--mp
```

Type:

```text
credits
```

Parser default:

```text
None
```

Help text should state:

```text
Maximum commodity market price to use.
Default: 1,500,000 cr/t.
Use 0 to disable.
```

### Validation

Reject negative values:

```text
--max-price must not be negative.
```

Allow zero:

```text
--max-price 0
```

Zero means disabled, not “maximum price zero”.

### Legacy `--old` Path

The parser is shared with the legacy comparison path.

Changing the parser default to `None` must not feed `None` into the legacy path.

For `--old`, restore historical behaviour by converting omitted `--max-price` to disabled:

```text
if cmdenv.maxPrice is None:
    cmdenv.maxPrice = 0
```

The legacy path should not inherit the new default unless explicitly decided later.

### Data Gateway

Apply active max-price filtering to candidate selection.

Active means:

```text
request.max_price > 0
```

Required SQL-side predicates:

```text
source supply rows:
    supply_price > 0
    supply_price <= request.max_price

destination demand rows:
    demand_price > 0
    demand_price <= request.max_price
```

Apply this in all planner candidate-fetch paths:

```text
fixed station-pair candidates
open-ended candidates
unanchored supply reduction
unanchored demand reduction
unanchored same-system matching where relevant
unanchored on-demand reach matching where relevant
multi-hop expansion where it uses open-ended candidate fetches
```

Where a path reduces supply and demand separately, apply the cap in the relevant row fetch/reduction step, not after rows have been materialised.

While implementing the predicate, confirm existing candidate-fetch paths
already enforce `supply_price > 0` / `demand_price > 0` in SQL rather than
relying on Python-side post-filtering. If any path was filtering positive
prices in Python, tidy at the same time.

## Part A Acceptance Criteria

Part A is accepted when:

```text
--max-price and --mp are accepted by the CLI.
Omitted --max-price applies 1,500,000 cr/t.
--max-price 0 disables absolute price filtering.
--max-price N applies N cr/t.
Negative --max-price fails cleanly.
The new planner applies max-price in SQL-side StationItem predicates.
Fixed-pair, open-ended, unanchored, and multi-hop expansion paths all honour the cap.
Rows above the active cap cannot appear in planned cargo.
--old does not silently inherit the new default cap.
```

---

# Part B — Testable Route Output

## Goal

Improve plain-text `trade run` output so route results are auditable during testing.

This is not a visual redesign.

No colour, rich formatting, or table polish is required.

The output only needs to expose the core route numbers clearly enough to inspect the planner’s behaviour.

## Required Per-Hop Output

For each hop, show:

```text
1. What is bought:
   - commodity name
   - quantity in tonnes
   - buy price per tonne
   - total buy cost

2. Travel:
   - same-system supercruise, or
   - jump path
   - intermediate systems when multiple jumps are used

3. What is sold:
   - commodity name
   - quantity in tonnes
   - sell price per tonne
   - profit per tonne
   - total sale value
   - total line profit

4. Hop totals:
   - total buy cost
   - total sale value
   - hop profit
   - cumulative profit
   - credits after sale
```

For the complete route, show:

```text
starting credits
total route profit
final credits
practical score, when it differs from raw profit
```

## Renderer Scope

Keep formatting logic in:

```text
tradedangerous/planner/render_text.py
```

Do not push presentation logic into route planning.

The current DTOs already expose the needed data:

```text
CargoLine.quantity
CargoLine.buy_price
CargoLine.sell_price
CargoLine.profit_per_unit
CargoLine.total_cost
CargoLine.total_profit
PlannedHop.jump_path
PlannedHop.raw_profit
PlannedRoute.total_raw_profit
PlannedRoute.starting_credits
PlannedRoute.ending_credits
```

## Suggested Output Shape

Example shape only; exact wording can be adjusted during implementation:

```text
Route:
  Colonia/Akinyemi Horticultural Market -> Colonia/Jaques Station
  Starting credits: 1,000,000 cr
  Total route profit: 123,456 cr
  Final credits: 1,123,456 cr

Hop 1:
  From: Colonia/Akinyemi Horticultural Market

  Buy:
    64 t Example Commodity @ 1,000 cr/t = 64,000 cr

  Travel:
    1 jump, 12.34 ly: Colonia -> Example

  To: Colonia/Jaques Station

  Sell:
    64 t Example Commodity @ 2,000 cr/t = 128,000 cr
      Profit: 1,000 cr/t, 64,000 cr total

  Hop totals:
    Buy cost: 64,000 cr
    Sale value: 128,000 cr
    Hop profit: 64,000 cr
    Cumulative profit: 64,000 cr
    Credits after sale: 1,064,000 cr
```

For same-system movement:

```text
Travel:
  Same-system supercruise
```

For jump paths:

```text
Travel:
  N jump(s), D.DD ly: System A -> System B -> System C
```

Intermediate systems should naturally appear from the existing `JumpPath.systems` tuple.

## Multi-Commodity Hops

If a hop carries multiple commodities, show one buy line and one sell line per commodity.

Per-line calculations:

```text
buy total       = quantity * buy_price
sale total      = quantity * sell_price
profit per ton  = sell_price - buy_price
line profit     = quantity * profit per ton
```

Use existing DTO totals where available.

## Cumulative Profit

For route rendering:

```text
cumulative_profit += hop.raw_profit
credits_after_sale = route.starting_credits + cumulative_profit
```

This should report raw post-sale credits.

Do not display margin-adjusted future buying power in the normal output for this slice.

Margin-adjusted capital is planner-internal spendability, not actual credits after sale.

## Existing Output Features to Preserve

Do not remove:

```text
partial route warnings
bulk-sale-tax cap note
multi-hop diagnostics block
practical score line when score differs from raw profit
```

Warnings should still appear before route details.

Diagnostics should still appear after route details.

## Part B Acceptance Criteria

Part B is accepted when route output shows:

```text
per-hop buy quantity
per-hop buy price per tonne
per-hop total buy cost
travel path or same-system supercruise
intermediate systems for multi-jump travel
per-hop sell quantity
per-hop sell price per tonne
per-hop profit per tonne
per-hop total sale value
per-hop line profit
hop profit
cumulative profit
credits after sale
route total profit
final credits
```

Existing warnings, diagnostics, and bulk-sale-tax notes must remain visible.

---

# Validation Plan

## Part A Tests

Add or update request/default tests:

```text
omitted --max-price -> request.max_price == 1500000
--max-price 0       -> request.max_price == 0
--max-price 500000  -> request.max_price == 500000
RunRequest()        -> max_price == 1500000
negative max-price  -> clean validation failure
```

Add candidate filtering tests using fixtures where practical:

```text
source supply_price above active cap is excluded
destination demand_price above active cap is excluded
rows equal to cap are allowed
rows below cap are allowed
cap disabled with 0 allows above-cap prices
```

Add path coverage for:

```text
fixed station-pair
open-ended
unanchored
multi-hop expansion where it uses open-ended candidate fetches
```

## Part B Tests

Use constructed DTOs where possible.

Renderer tests should include:

```text
single-hop route
multi-hop route
multi-commodity hop
same-system hop
multi-jump path with intermediate systems
bulk-sale-tax-sensitive line that cap-binds
```

Assertions should check for required information rather than brittle full-output byte matching.

## Smoke Commands

Run at least the existing short benchmark:

```text
trade run --from "Colonia/Akinyemi Horticultural Market" --to "Colonia/Jaques Station" --capacity 64 --credits 1000000 --hops 1 --jumps-per 1 --ly-per 20
```

Run a current multi-hop probe from the Slice 8/Slice 9 working set.

Run with default max price:

```text
trade run ...
```

Run with disabled max price:

```text
trade run ... --max-price 0
```

Run with a deliberately low cap to prove filtering is active:

```text
trade run ... --max-price 1000
```

The low-cap test is expected to change results or fail with no profitable trade depending on fixture/data shape.

## Performance Re-baseline

`fetch_unanchored_trade_candidates` walks commodities in descending
profit-per-unit bound order and stops when
`capacity * profit_bound <= best_total_profit`. Under noisy data, a single
multi-million carrier-fiction trade sets `best_total_profit` on the first
commodity examined and every legitimate commodity is then pruned. The
Slice 6 unanchored timings (e.g. 14.6s at the dense profile) were measured
under that condition.

`--max-price` removes that noise at the SQL row level before the walk sees
it. The cutoff stays — it is admissible and effectively free — but it no
longer fires after a single commodity. What SLICE_SUMMARY currently calls
"the slow case" is now the default case.

During Slice 9 validation, re-measure unanchored wall-clock with
`--max-price` default-on, with and without `--fc N`, and with the filter
explicitly disabled:

```text
trade run --capacity 720 --credits 200000000 --hops 1 \
    --jumps-per 2 --ly-per 30 --age 1
trade run --capacity 720 --credits 200000000 --hops 1 \
    --jumps-per 2 --ly-per 30 --age 1 --fc N
trade run --capacity 720 --credits 200000000 --hops 1 \
    --jumps-per 2 --ly-per 30 --age 1 --max-price 0
```

Record the timings in the Slice 9 completion report. Update the Slice 6
entry in `SLICE_SUMMARY.md` if its "early-cutoff acceleration is not
representative of clean-data performance" caveat has become obsolete or
needs rewording under the new default.

---

# Implementation Order

1. Save this plan as:

   ```text
   docs/Planner/ninth_slice_implementation_plan.md
   ```

2. Implement Part A request/parser/default handling.

3. Add validation for `--max-price`.

4. Apply SQL-side max-price predicates in data gateway candidate paths.

5. Run focused Part A tests.

6. Run local smoke probes comparing default, disabled, and deliberately low caps.

7. Re-baseline unanchored wall-clock under default `--max-price` (see Performance Re-baseline).

8. Implement Part B renderer output expansion.

9. Add renderer tests.

10. Run smoke commands and manually inspect output.

11. Update `docs/Planner/SLICE_SUMMARY.md` only after implementation and validation are complete.

12. Produce `docs/Planner/ninth_slice_completion_report.md` after sign-off.

---

# Files Expected to Change

Likely implementation files:

```text
tradedangerous/commands/run_cmd.py
tradedangerous/planner/run_request.py
tradedangerous/planner/validation.py
tradedangerous/planner/data_gateway.py
tradedangerous/planner/render_text.py
```

Likely test files depend on the current test layout and should be selected after inspecting existing planner tests.

Documentation files:

```text
docs/Planner/ninth_slice_implementation_plan.md
docs/Planner/SLICE_SUMMARY.md
docs/Planner/ninth_slice_completion_report.md
```

`SLICE_SUMMARY.md` and the completion report should wait until implementation and validation are complete.

---

# Noted For Later

Not blocking for Slice 9. Captured here so the points are not lost:

- **No-route failure messaging under default `--max-price`.** A user running
  with the new default cap who hits "no profitable trade" may not realise the
  cap is in play. The Slice 6 failure-message family ("with the current jump
  settings") could later grow a sibling phrasing for the price cap. Out of
  scope here; revisit if real complaints surface.

---

# Final Acceptance Criteria

Slice 9 is accepted when:

```text
--max-price / --mp exists.
Default max price is 1,500,000 cr/t.
Explicit --max-price 0 disables the filter.
The filter is applied early in SQL on StationItem supply and demand prices.
The filter preserves normal carrier access rather than behaving like --fleet-carrier N.
Route output exposes buy, travel, sell, per-hop, cumulative, and total route numbers.
Existing warnings, diagnostics, and bulk-sale-tax notes remain visible.
Focused tests and smoke commands pass.
```