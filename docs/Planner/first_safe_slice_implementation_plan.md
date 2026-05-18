# First Safe Slice Implementation Plan

Scope:

trade run
  --from station
  --to station
  --capacity N
  --credits N
  --hops 1
  --jumps-per N
  --ly-per N

Out of scope for this slice:
- system-wide origin expansion;
- system-wide destination expansion;
- omitted --from / --to;
- --start-jumps;
- --end-jumps;
- --direct;
- --towards;
- --loop;
- --via;
- --unique;
- --loop-interval;
- --shorten;
- --routes > 1;
- --checklist;
- --x52-pro;
- multi-hop route search;
- broad frontier pruning.

Source quarantine:
- Do not inspect, import, call, subclass, adapt, translate, or summarise:
  - tradedangerous/tradecalc.py
  - tradedangerous/tradedb.py
- Do not use legacy route, trade, or DB facade objects as planner inputs.
- Existing run command parser metadata may remain as the command entry surface.
- ORM/schema/resolver surfaces only for data access.

---

## 1. New module/file layout

New package:

tradedangerous/planner/

Files:

- tradedangerous/planner/__init__.py
  - Package marker.
  - No behavioural logic.

- tradedangerous/planner/run_request.py
  - Neutral request DTOs.
  - Conversion target from cmdenv.
  - No database access.

- tradedangerous/planner/run_result.py
  - Planner result DTOs.
  - Route/hop/cargo output structures.
  - No database access.

- tradedangerous/planner/failures.py
  - Typed planner failures.
  - Does not depend on command-layer exceptions.

- tradedangerous/planner/validation.py
  - First-slice validation beyond existing parser validation.
  - Ensures this slice only accepts the supported shape.

- tradedangerous/planner/resolver.py
  - Place resolver for exact/scoped station inputs.
  - Uses permitted ORM/schema/resolver surfaces only.
  - For this slice, station-only resolution is required.

- tradedangerous/planner/data_gateway.py
  - Read-only ORM/schema access.
  - Fetches systems, stations, and market candidates.
  - Returns planner DTOs, not ORM entities.

- tradedangerous/planner/reachability.py
  - Same-system handling.
  - Single bounded reachability check for source system -> destination system.
  - First implementation may use direct distance if maxJumpsPer == 1.
  - If maxJumpsPer > 1, use bounded BFS over permitted system graph if the ORM/schema surface exposes neighbours/range lookup safely.
  - If no permitted reachability surface exists yet, fail with a typed "reachability implementation missing" during development, not a false route.

- tradedangerous/planner/cargo.py
  - Bounded multi-commodity cargo optimiser.
  - Destination demand is a hard cap.
  - No greedy-as-correctness.

- tradedangerous/planner/score.py
  - Raw profit score for this slice.
  - ls-penalty can be included if cheap, but the first slice may initially report raw score only if --ls-penalty is not yet wired.
  - If --ls-penalty option is active by default in current parser, this module should implement the protected curve before user-facing activation.

- tradedangerous/planner/run_onehop.py
  - Orchestrates first-slice planning.
  - Input: RunRequest.
  - Output: RunResult.
  - No command-layer printing.

- tradedangerous/planner/render_text.py
  - Temporary renderer for new RouteResult.
  - Human-readable default output.
  - No dependency on legacy Route/TradeCalc structures.

Command integration:

- tradedangerous/commands/run_cmd.py
  - Keep existing parser metadata initially.
  - Add a first-slice branch after fast validation and before legacy planner construction.
  - Convert cmdenv -> RunRequest.
  - Call run_onehop planner.
  - Render RouteResult.

---

## 2. DTO definitions

DTOs should be plain immutable-ish data containers.

RunRequest:

- capacity_units
- starting_credits
- insurance_reserve
- cargo_limit_per_item
- margin
- from_text
- to_text
- hops
- max_jumps_per_hop
- max_ly_per_jump
- age_days
- min_gain_per_ton
- max_gain_per_ton
- min_supply
- min_demand
- pad_size_filter
- planetary_filter
- no_planet
- fleet_carrier_filter
- settlement_filter
- black_market_filter
- max_ls
- ls_penalty_percent
- show_jumps
- summary
- progress
- detail
- debug

ResolvedSystem:

- system_id
- name
- dbname
- x
- y
- z

ResolvedStation:

- station_id
- name
- dbname
- system_id
- system_name
- x
- y
- z
- ls_from_star
- market
- black_market
- max_pad_size
- planetary
- fleet_carrier
- settlement
- type_id
- modified
- data_age_days

MarketQuote:

- station_id
- item_id
- item_name
- buy_price
- sell_price
- supply_units
- demand_units
- supply_level
- demand_level
- modified
- age_days

TradeCandidate:

- item_id
- item_name
- source_station_id
- destination_station_id
- buy_price
- sell_price
- profit_per_unit
- source_supply_units
- destination_demand_units
- source_age_days
- destination_age_days

CargoLine:

- item_id
- item_name
- quantity
- buy_price
- sell_price
- profit_per_unit
- total_cost
- total_profit
- source_supply_units
- destination_demand_units

CargoPlan:

- lines
- units_loaded
- total_cost
- total_profit
- unused_capacity
- unspent_capital

JumpPath:

- source_system_id
- destination_system_id
- systems
- distance_ly
- jumps
- is_same_system
- is_reachable

PlannedHop:

- source_station
- destination_station
- cargo
- raw_profit
- practical_score
- jump_path

PlannedRoute:

- stations
- hops
- total_raw_profit
- total_practical_score
- starting_credits
- ending_credits

RunResult:

- routes
- diagnostics
- warnings

PlannerDiagnostics:

- validation_ms
- resolution_ms
- station_query_ms
- market_query_ms
- reachability_ms
- cargo_optimisation_ms
- render_ms
- total_planner_ms
- candidate_trade_count

---

## 3. Required data queries

Use ORM/schema surfaces where available. The logical queries are:

### Query A: resolve scoped source station

Input:

- from_text = "System/Station" or equivalent supported station-qualified form

Required behaviour:

- parse scope;
- resolve system exactly or deterministically;
- resolve station within that system only;
- do not fall back to broad station matching when scope was supplied.

Returned fields:

- station_id
- station name/dbname
- system_id
- system name/dbname
- system coordinates
- station attributes needed for source eligibility

### Query B: resolve scoped destination station

Same as Query A, using to_text.

Returned fields:

- station_id
- station name/dbname
- system_id
- system name/dbname
- system coordinates
- station attributes needed for destination eligibility

### Query C: source station market quotes

Input:

- source_station_id
- age filter if supplied
- min supply threshold if supplied
- commodity avoid set if later enabled

Where:

- station_id = source_station_id
- supply_price > 0
- supply_units >= min_supply if min_supply is supplied
- modified is parseable
- modified is within max age if max age supplied

Returned fields:

- item_id
- source buy_price = supply_price
- source supply_units
- source supply_level
- source modified

### Query D: destination station market quotes

Input:

- destination_station_id
- age filter if supplied
- min demand threshold if supplied

Where:

- station_id = destination_station_id
- demand_price > 0
- demand_units >= min_demand if min_demand is supplied
- demand_units > 0 always, because demand is a hard cap
- modified is parseable
- modified is within max age if max age supplied

Returned fields:

- item_id
- destination sell_price = demand_price
- destination demand_units
- destination demand_level
- destination modified

### Query E: candidate trade join

Join source and destination quote sets on item_id.

Computed:

- profit_per_unit = destination demand_price - source supply_price

Where:

- profit_per_unit >= min_gain_per_ton
- if max_gain_per_ton > 0, profit_per_unit <= max_gain_per_ton
- source supply_units > 0
- destination demand_units > 0
- at least one unit affordable from available trade capital

Returned:

- TradeCandidate list.

### Query F: reachability data

For first slice:

- If source system == destination system:
  - reachable as same-system supercruise.
- Else:
  - require max_ly_per_jump.
  - require max_jumps_per_hop >= 1.
  - for max_jumps_per_hop == 1:
    - compute Euclidean distance between source and destination system coordinates.
    - reachable iff distance <= max_ly_per_jump.
  - for max_jumps_per_hop > 1:
    - use permitted system-range ORM/schema surface if available.
    - do bounded BFS up to max_jumps_per_hop.
    - do not inspect quarantined range-generation code.

If no permitted range surface exists, defer multi-jump support rather than fabricating reachability.

---

## 4. Validation flow

Layer 1: existing parser

- Existing run command parser parses CLI args into cmdenv.
- Existing parser type conversions remain in place.

Layer 2: existing fast validation

- Call validateRunArgumentsFast(cmdenv).
- This catches required static failures already represented in the command layer.

Layer 3: first-slice support validation

Reject anything outside the first safe slice:

- --from missing
- --to missing
- hops != 1
- direct enabled
- start-jumps != 0
- end-jumps != 0
- towards supplied
- loop enabled
- via supplied
- avoid supplied, unless avoid is implemented in this slice
- unique enabled
- loop-interval supplied
- shorten enabled
- routes != 1
- checklist enabled
- x52-pro enabled
- max-routes supplied non-zero
- prune-score supplied non-zero
- prune-hops changed only matters later; ignore or reject consistently
- capacity <= 0
- credits < 0
- insurance >= credits
- limit < 0
- limit > capacity
- jumps-per < 0
- ly-per <= 0
- min supply < 0
- min demand < 0
- min gain per ton < 0 unless existing public semantics allow otherwise
- max gain per ton < 0
- max gain per ton > 0 and max gain per ton < min gain per ton
- settlement/planetary contradiction if both surfaces are active

Layer 4: resolution validation

- Resolve --from as station.
- If resolution is system-only, fail with UnsupportedFirstSliceShape.
- Resolve --to as station.
- If resolution is system-only, fail with UnsupportedFirstSliceShape.
- Unknown and ambiguous names use typed resolver failures.

Layer 5: station eligibility validation

Source station must:

- exist;
- have market;
- satisfy source-side station filters;
- have usable source-side market data.

Destination station must:

- exist;
- have market;
- satisfy destination-side station filters;
- have usable destination-side market data.

Layer 6: reachability validation

- If same system: reachable.
- Else verify jump path under ly-per and jumps-per.
- If not reachable: NoReachableRoute.

Layer 7: trade/cargo validation

- Generate trade candidates.
- If none: NoProfitableTrades.
- Optimise cargo.
- If optimiser returns zero units: NoAffordableCargo or NoProfitableTrades depending cause.
- Return exactly one route.

---

## 5. Typed failure classes

Base:

- PlannerFailure
  - message
  - option_name
  - entity_name
  - details

Validation failures:

- InvalidRunRequest
- UnsupportedFirstSliceShape
- MissingRequiredInput
- ContradictoryOptions
- InvalidNumericOption

Resolution failures:

- UnknownPlace
- AmbiguousPlace
- UnknownSystem
- AmbiguousSystem
- UnknownStation
- AmbiguousStation

Station/data failures:

- StationHasNoMarket
- StationHasNoUsablePriceData
- SourceHasNoSellingData
- DestinationHasNoBuyingData
- SourceStationIneligible
- DestinationStationIneligible
- MarketTimestampInvalid

Route failures:

- NoReachableRoute
- NoProfitableTrades
- NoAffordableCargo

Runtime:

- PlannerCancelled
- PlannerInternalError

Command-layer mapping:

- InvalidRunRequest and option failures map to CommandLineError.
- Unknown/Ambiguous failures map to CommandLineError with disambiguation text.
- Station/data no-data failures map to NoDataError where existing command conventions expect no-data.
- NoReachableRoute / NoProfitableTrades map to NoDataError or a dedicated command-level no-route error if one already exists outside quarantined code.

Do not leak internal stack traces in normal output.

---

## 6. Cargo optimiser choice for this slice

Use a bounded multi-commodity optimiser from the start.

Hard rule:

- destination demand_units is a hard upper bound on recommended sale quantity.

Per-candidate maximum quantity:

- source supply_units
- destination demand_units
- request capacity
- request cargo limit if non-zero
- affordable quantity from available capital

Optimisation problem:

- maximise total profit;
- bounded integer quantities;
- shared capacity constraint;
- shared credit constraint;
- item-specific quantity bounds.

Recommended first implementation:

- Branch-and-bound over candidate commodities ordered by profit-per-unit descending.
- Use greedy fractional upper bound only as pruning bound, not as correctness.
- Track best complete integer cargo plan.
- Stop only after proving best for the candidate set.

Why branch-and-bound for first slice:

- candidate set is one station pair only;
- benchmark command is one hop only;
- preserves correctness better than greedy;
- easier to reason about than a credit-indexed DP if credits are large;
- can use dominance pruning.

Required optimiser tests:

- user’s counterexample:
  - capacity = 2
  - credits = 100
  - A cost 60 profit 10 cap >= 1
  - B cost 50 profit 9 cap >= 2
  - expected: 2xB, profit 18

- demand cap:
  - source supply 100
  - destination demand 3
  - capacity 64
  - expected quantity <= 3

- hybrid cargo:
  - highest-profit item cannot fill hold due to demand/supply/credit/limit;
  - expected plan combines commodities.

Fallback:

- Greedy may be used only for candidate ordering, initial lower bound, or emergency diagnostic comparison.
- Greedy result must not be labelled optimal.
- If branch-and-bound is too slow on real station-pair data, promote a bounded DP or hybrid exact strategy after measurement.

---

## 7. Benchmark/check commands

Primary slice benchmark:

trade run --from "Colonia/Akinyemi Horticultural Market" --to "Colonia/Jaques Station" --capacity 64 --credits 1000000 --hops 1 --jumps-per 1 --ly-per 20

Expected checks:

- command completes without legacy planner;
- source station resolves exactly;
- destination station resolves exactly;
- route has exactly one hop;
- route starts at Akinyemi Horticultural Market;
- route ends at Jaques Station;
- jump constraint is satisfied or same-system travel is reported;
- every cargo line has:
  - quantity > 0
  - buy_price > 0
  - sell_price > buy_price
  - quantity <= source_supply
  - quantity <= destination_demand
- total cargo quantity <= 64
- total cargo cost <= 1,000,000 minus insurance
- total profit equals sum(quantity * (sell_price - buy_price))
- final credits equals starting credits + total profit
- runtime is materially below old baseline for run-short.

Validation check commands:

trade run --from "Colonia/Akinyemi Horticultural Market" --to "Colonia/Jaques Station" --credits 1000000 --hops 1 --jumps-per 1 --ly-per 20

Expected:
- missing --capacity failure before DB planning.

trade run --from "Colonia/Akinyemi Horticultural Market" --to "Colonia/Jaques Station" --capacity 64 --hops 1 --jumps-per 1 --ly-per 20

Expected:
- missing --credits failure before DB planning.

trade run --from "Colonia/Akinyemi Horticultural Market" --to "Colonia/Jaques Station" --capacity 64 --credits 1000000 --hops 1 --jumps-per 1

Expected:
- missing --ly-per failure before DB planning.

trade run --from "Colonia/Akinyemi Horticultural Market" --to "Colonia/Jaques Station" --capacity 64 --credits 1000000 --hops 2 --jumps-per 1 --ly-per 20

Expected:
- unsupported first-slice shape, not legacy fallback unless explicitly enabled.

Optional developer switch:

- Add an environment variable or hidden config gate for first-slice planner activation.
- Suggested name: TD_RUN_PLANNER_V2_ONEHOP=1
- During development, if unset, existing behaviour can remain.
- Once accepted, invert or remove the gate.

---

## 8. Exact integration point with existing parser/renderer

File:

- tradedangerous/commands/run_cmd.py

Existing surfaces to preserve:

- help = 'Calculate best trade run.'
- name = 'run'
- usesTradeData = True
- arguments list
- switches list
- validateRunArgumentsFast(cmdenv)

Integration point:

- Inside the run command entry function in run_cmd.py.
- After cmdenv has been populated by the existing parser.
- Immediately after validateRunArgumentsFast(cmdenv) succeeds.
- Before any legacy TradeCalc construction.
- Before any legacy TradeDB facade lookup/planner use.
- Before any legacy Route object is constructed.

Planned flow:

1. Existing parser populates cmdenv.
2. run_cmd.py calls validateRunArgumentsFast(cmdenv).
3. New first-slice selector checks whether cmdenv is exactly supported:
   - starting present;
   - ending present;
   - hops == 1;
   - direct false;
   - maxJumpsPer present;
   - maxLyPer present;
   - no unsupported route-shape options.
4. If supported and v2 gate enabled:
   - build neutral RunRequest from cmdenv;
   - planner owns resolution/data/reachability/cargo;
   - render RouteResult using new render_text module;
   - return command result without touching legacy planner.
5. If not supported:
   - during development: either raise UnsupportedFirstSliceShape when v2 gate is enabled, or fall back to existing command path when v2 gate is unset.
   - after acceptance: expand supported surface incrementally.

Renderer boundary:

- Do not adapt new result into legacy Route.
- Do not use Checklist for this slice.
- New renderer prints from RouteResult.
- Later, checklist can be reimplemented against RouteResult rather than legacy route objects.

---

## 9. Tests to write first

Test group A: request validation

- missing capacity
- missing credits
- missing ly-per without direct
- negative capacity
- negative credits
- insurance >= credits
- limit > capacity
- hops != 1 rejected by first-slice validator
- routes > 1 rejected
- checklist rejected
- direct rejected for first slice
- start-jumps/end-jumps rejected
- towards/loop/via/unique/shorten rejected

Test group B: resolver

- exact scoped station resolves:
  - Colonia/Akinyemi Horticultural Market
- exact scoped destination resolves:
  - Colonia/Jaques Station
- scoped station does not fall back to global station search if station missing inside scoped system
- unknown system gives UnknownSystem
- unknown station in valid system gives UnknownStation
- ambiguous unscoped station gives AmbiguousStation, if unscoped station support is enabled
- first slice rejects system-only --from
- first slice rejects system-only --to

Test group C: station eligibility

- source station with market = N fails StationHasNoMarket
- destination station with market = N fails StationHasNoMarket
- source with no usable supply-side quotes fails SourceHasNoSellingData
- destination with no usable demand-side quotes fails DestinationHasNoBuyingData
- pad-size mismatch fails
- no-planet mismatch fails
- black-market requirement mismatch fails
- max-ls exclusion fails
- age exclusion fails
- invalid timestamp is not treated as fresh

Test group D: trade candidate generation

- only same item_id joins source and destination
- buy_price must be positive
- sell_price must be positive
- profit_per_unit must meet min gain
- max gain excludes excessive gain when set
- source supply threshold applies
- destination demand threshold applies
- destination demand zero excludes candidate

Test group E: cargo optimiser

- greedy counterexample proves exact optimiser:
  - capacity 2
  - credits 100
  - A: cost 60, profit 10
  - B: cost 50, profit 9
  - expected 2xB
- demand hard cap:
  - cannot recommend quantity above destination demand
- source supply hard cap
- per-item limit cap
- credit cap
- hybrid cargo required
- exact total cost/profit arithmetic
- no affordable cargo returns NoAffordableCargo

Test group F: reachability

- same-system returns reachable and marks supercruise
- one-jump route within ly-per returns reachable
- one-jump route beyond ly-per returns NoReachableRoute
- jumps-per 0 between different systems fails
- show-jumps includes path detail where path exists

Test group G: one-hop planner integration

- fixture DB one-hop route returns expected optimal cargo
- no profitable trade returns NoProfitableTrades
- no reachable route returns NoReachableRoute
- run-short real-data benchmark returns a valid one-hop route
- planner diagnostics include query/cargo/render timings

Test group H: command integration

- v2 gate enabled + supported command uses new planner
- v2 gate enabled + unsupported command fails UnsupportedFirstSliceShape
- v2 gate unset preserves existing behaviour during development
- command output contains:
  - source station
  - destination station
  - commodity names
  - quantities
  - buy/sell prices or gain summary
  - total gain
  - final credits

---

## 10. Files expected to change

New files:

- tradedangerous/planner/__init__.py
- tradedangerous/planner/run_request.py
- tradedangerous/planner/run_result.py
- tradedangerous/planner/failures.py
- tradedangerous/planner/validation.py
- tradedangerous/planner/resolver.py
- tradedangerous/planner/data_gateway.py
- tradedangerous/planner/reachability.py
- tradedangerous/planner/cargo.py
- tradedangerous/planner/score.py
- tradedangerous/planner/run_onehop.py
- tradedangerous/planner/render_text.py

Modified files:

- tradedangerous/commands/run_cmd.py
  - add new planner branch after fast validation;
  - avoid passing legacy objects into new planner;
  - keep public parser surface unchanged.

Possible modified files, depending current test layout:

- tests/planner/test_run_request_validation.py
- tests/planner/test_resolver.py
- tests/planner/test_station_eligibility.py
- tests/planner/test_trade_candidates.py
- tests/planner/test_cargo_optimizer.py
- tests/planner/test_reachability.py
- tests/planner/test_run_onehop.py
- tests/commands/test_run_cmd_onehop_v2.py
- benchmarks/trade_run_onehop.py or equivalent benchmark harness location

Files explicitly not to inspect or modify in this slice:

- tradedangerous/tradecalc.py
- tradedangerous/tradedb.py

Files not to couple to:

- any test fixture asserting legacy private route/frontier/cache internals
- any legacy object adapter that recreates TradeCalc/Route semantics internally

---

## First implementation order

1. Add DTO and failure modules.
2. Add cargo optimiser with fixture-only tests.
3. Add first-slice validation tests.
4. Add resolver tests for scoped station names.
5. Add data gateway queries for station and station-pair candidates.
6. Add reachability for same-system and one-jump coordinate distance.
7. Add run_onehop orchestration.
8. Add text renderer.
9. Add gated run_cmd.py integration.
10. Run validation tests.
11. Run cargo optimiser tests.
12. Run one-hop fixture planner test.
13. Run run-short benchmark command.
14. Compare route validity, cargo arithmetic, and wall-clock runtime.