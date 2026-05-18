---
title: "trade run Black-Box Behavioural Specification"
subtitle: "Clean rewrite contract for Trade Dangerous route planning"
author: "Prepared for Tromador / Trade Dangerous"
date: "2026-05-10"
lang: en-GB
---

# trade run Black-Box Behavioural Specification

## Document status

This document is a behavioural contract for a clean rewrite of `trade run`.

It specifies what the command must do for the user. It deliberately does not specify the legacy implementation strategy, internal object model, cache layout, route expansion code, database facade, or calculation module design.

This document intentionally contains no source citations. It is meant to be safe implementation input for AI workers without pulling them toward the legacy code path.

## Source quarantine

Implementation workers assigned to this rewrite must not inspect, import, call, subclass, adapt, translate, copy from, or ask another tool to summarise the quarantined legacy route-planning and legacy database implementation modules.

The quarantined modules are named here only to prohibit their use:

- `tradedangerous/tradecalc.py`
- `tradedangerous/tradedb.py`

The rewrite may reuse general command-line parsing infrastructure up to a neutral parsed-request boundary. After user input has been parsed and validated into a neutral request object, route planning must enter new implementation code.

The new route planner must not receive or require legacy calculation objects, legacy database facade objects, or legacy in-memory market snapshots.

Permitted sources for implementation workers:

- this specification;
- public command help and user-facing README material;
- neutral parser output / command request objects;
- database schema and ORM definitions where needed to query the current database;
- project benchmark command corpus;
- official documentation for Python, SQLAlchemy, the selected database backend, optimisation algorithms, and any chosen packages.

Prohibited sources for implementation workers:

- quarantined legacy calculation/database implementation modules;
- copied or translated legacy algorithms from those modules;
- summaries of those modules prepared for implementation use;
- tests that require reproducing private intermediate state from the quarantined modules.

## Purpose

`trade run` searches for profitable Elite Dangerous commodity trading routes.

Given ship capacity, available credits, jump capability, station constraints, market data, and route constraints, it recommends where the player should go, what cargo to buy, where to sell it, and the expected profit.

The command's practical purpose is:

```text
Find a valid trading route that obeys the user's constraints, makes equal or better practical profit than the existing command for comparable data, and resolves materially faster.
```

The route does not need to match the existing command's exact station sequence or cargo mix. A different route is acceptable when it is valid, profitable, and at least comparable in practical value.

## Primary success criteria

A rewrite is successful when, for the benchmark corpus and ordinary user queries, it provides:

1. valid routes that obey the same user-facing constraints;
2. equal or better expected profit, or roughly comparable profit where practical travel-time penalties deliberately reduce raw-profit preference;
3. materially lower wall-clock runtime;
4. clear errors when no valid route exists;
5. stable, human-usable output.

A 1-2 second improvement on an approximately 30 second route calculation is not enough. The expected improvement is large enough to be obvious in normal use and in benchmark runs.

The benchmark comparison is not expected to use byte-identical market data forever. The galaxy economy changes. The comparison is intended to detect meaningful differences in route quality and runtime, not litigate tiny market drift.

## Non-goals

The rewrite is not required to preserve:

- exact route identity from the existing command;
- exact cargo mix from the existing command;
- exact internal ranking frontiers;
- exact pruning artefacts;
- exact internal object names;
- exact formatting byte-for-byte;
- private intermediate state used by old implementation tests.

The rewrite must preserve the public command contract and protected domain behaviour.

## Protected behaviour

The following behaviours are protected and must be preserved unless the project supervisor explicitly changes the contract:

- CLI option meanings.
- Constraint enforcement.
- Profit arithmetic.
- Cargo feasibility rules.
- Station and commodity filtering semantics.
- Jump and reachability semantics.
- Useful output content.
- Distinct no-data, no-route, unknown-name, ambiguous-name, and invalid-option failures.
- The `--ls-penalty` curve described in this document.

The `--ls-penalty` curve is protected because it solves a known gameplay problem: some stations are extremely far from the system arrival star and can take many real-world minutes to reach. A route that looks profitable on paper can be a bad recommendation if it wastes the player's time in supercruise.

## Route quality standard

A route is valid if it satisfies all user-supplied constraints.

Among valid routes, better routes are those that produce greater practical player value.

Without `--ls-penalty`, practical value is primarily expected credit profit.

With `--ls-penalty`, practical value is expected credit profit adjusted for station distance from arrival star using the protected penalty curve. A lower raw-profit route can be preferable if it avoids extreme in-system travel time.

When comparing the rewrite against the existing command:

```text
new route must be valid under the same options
new route should produce equal-or-better practical value
new route must calculate materially faster
exact same route is not required
```

If the rewrite produces materially lower profit or materially lower penalty-adjusted value, that is a regression unless the supervisor accepts a deliberate semantic change.

## Domain model

A system is a star system with coordinates.

A station is a market location within a system. It may have attributes such as market availability, pad size, planetary state, fleet-carrier state, settlement state, black-market availability, distance from arrival star, services, and market-data age.

A commodity is a market item that can be bought or sold at stations. Commodity market data includes buy price, sell price, supply, demand, and timestamp or age.

A hop is one station-to-station trading leg.

A route is an ordered sequence of station visits connected by hops.

A jump is one system-to-system hyperspace jump.

Supercruise is same-system travel from the arrival star to a station, or between stations in the same system.

## Required inputs

`trade run` requires:

- cargo capacity;
- starting credits;
- maximum jump range, unless direct mode is selected.

The command must reject missing required inputs before expensive route-planning work begins.

Credits may use common suffixes such as thousands, millions, and billions where the existing CLI parser supports them.

## Command option contract

The rewrite must support the public `trade run` option surface unless the supervisor explicitly removes or changes an option.

### Financial and ship options

- `--capacity`: maximum cargo units.
- `--credits`: starting credits.
- `--insurance`: credits reserved and unavailable for cargo purchase.
- `--limit`: maximum units of any single commodity to buy on a hop. Zero means unlimited subject to other constraints.
- `--margin`: safety margin for treating previous gains as usable future buying power.

### Route shape options

- `--from`: starting system or station.
- `--to`: final system or station.
- `--towards`: target system the route must progress toward.
- `--loop`: route must return to its starting station.
- `--via`: system or station that must appear on the route.
- `--avoid`: commodity, system, or station to exclude.
- `--hops`: number of station-to-station trade legs.
- `--direct`: assume destinations are reachable without jump-path checks.
- `--shorten`: prefer reaching the final destination in fewer hops while preserving good trade value.
- `--unique`: do not visit the same station more than once.
- `--loop-interval`: require a minimum hop gap before revisiting a station.

### Reachability options

- `--ly-per`: maximum light years per loaded jump.
- `--empty-ly`: maximum light years per unladen jump, used for origin/destination expansion where applicable.
- `--jumps-per`: maximum system jumps per trading hop.
- `--start-jumps`: expand eligible origins around `--from`.
- `--end-jumps`: expand eligible destinations around `--to`.
- `--show-jumps`: show jump path or same-system travel detail.

### Station filters

- `--pad-size`: require compatible landing pad size.
- `--planetary`: include only matching planetary status values.
- `--no-planet`: require non-planetary stations.
- `--fleet-carrier`: include only matching fleet-carrier status values.
- `--settlement`: include only matching settlement status values.
- `--black-market`: include only matching black market status values.
- `--ls-max`: exclude stations beyond a maximum distance from arrival star.
- `--age`: exclude market data older than the requested number of days.

### Commodity and trade filters

- `--gain-per-ton`: minimum profit per unit.
- `--max-gain-per-ton`: maximum profit per unit.
- `--supply`: minimum source supply required for a commodity to be considered.
- `--demand`: minimum destination demand required for a commodity to be considered.

### Search and display controls

- `--routes`: maximum number of final routes to display.
- `--max-routes`: maximum number of partial routes retained between expansion stages.
- `--prune-score`: discard weak partial routes after the configured pruning hop.
- `--prune-hops`: first hop number from which score pruning may apply.
- `--progress`: display long-running search progress.
- `--summary`: compact route output.
- `--checklist`: interactive route checklist.
- `--x52-pro`: external device output for checklist mode.

## Early validation

The command must fail before route planning when required static inputs are missing or contradictory.

Required early failures include:

- missing `--capacity`;
- missing `--credits`;
- missing `--ly-per` unless `--direct` is used;
- `--x52-pro` without `--checklist`;
- `--towards` without `--from`;
- `--start-jumps` without `--from`;
- `--end-jumps` without `--to`;
- `--shorten` without `--to`;
- `--loop` with `--unique`;
- `--loop` with `--direct`;
- `--limit` greater than `--capacity`;
- insurance reserve that leaves no practical trading budget;
- `--loop-interval` below 2;
- negative credits;
- negative capacity;
- negative cargo limit;
- negative jumps-per-hop;
- fewer than one hop;
- excessive hop count beyond the supported search policy;
- fewer than one requested output route;
- multiple displayed routes with checklist mode;
- `--shorten` with `--loop`;
- `--prune-score` outside its percentage range;
- `--prune-hops` below 2.

Validation should happen in the cheapest sensible order. Static argument failures must not require route planning or broad market access.

## Name and place resolution

User-supplied places may refer to systems or stations.

Supported user forms should include:

```text
system
station
system/station
@system
/station
@system/station
system\station
```

A station-qualified system form must resolve the system first and then search stations in that system. It must not default to broad global station matching when the user supplied a scope.

Resolution must be deterministic for the same database snapshot and input.

Resolution must distinguish:

- unknown input;
- ambiguous input;
- valid system;
- valid station.

Where fuzzy or partial matching is supported, it must be bounded and predictable. Exact or scoped matches should be attempted before broad approximate matches.

If ambiguity remains, the error must provide enough information for the user to disambiguate.

## Origin selection

`--from` may identify a station or a system.

If `--from` identifies a station, that station is the sole route origin.

If `--from` identifies a system, eligible trading stations in that system are candidate origins.

If `--from` is omitted, eligible origins may be selected from the available market data, subject to the user's filters and performance policy.

`--start-jumps` expands eligible origins to stations reachable from the `--from` system within the requested jump count. It uses `--empty-ly` if supplied; otherwise it uses `--ly-per`.

If no eligible origin remains, the command must fail with an origin-side no-data or invalid-constraint message.

## Destination selection

`--to` may identify a station or a system.

If `--to` identifies a station, that station is the sole final destination.

If `--to` identifies a system, eligible trading stations in that system are candidate final destinations.

If `--to` is omitted, eligible destinations may be selected from the available market data, subject to the user's filters and performance policy.

`--end-jumps` expands eligible destinations to stations reachable from the `--to` system within the requested jump count. It uses `--empty-ly` if supplied; otherwise it uses `--ly-per`.

If no eligible destination remains, the command must fail with a destination-side no-data or invalid-constraint message.

## Avoid semantics

`--avoid` accepts repeated and comma-separated values.

Each avoid token may identify:

- a commodity;
- a system;
- a station.

Avoided commodities must not be recommended for purchase.

Avoided systems must not be used as route stations or path systems.

Avoided stations must not be used as route stations.

If the explicit start station is also avoided, the command may still start there because the user explicitly selected it. Avoidance still applies to later visits and to other route positions.

A token that cannot be resolved as any supported avoid type must fail clearly.

## Via semantics

`--via` accepts repeated and comma-separated systems or stations.

A route satisfies a station via when it visits that station.

A route satisfies a system via when it visits any station in that system.

A via conflicts with avoid if the via place itself is avoided or its system is avoided.

If the requested number of hops is too small to include the required vias and fixed endpoints, the command must fail before route search or as early as that impossibility is known.

If no route can satisfy all via requirements, the command must fail clearly. Returning partial-via routes is permitted only when the output explicitly says that not all vias were satisfied.

## Station eligibility

A candidate station must satisfy all relevant user filters for its route role.

A station may be rejected for:

- no usable market;
- no usable market data;
- no source-side selling data when used as a source;
- no destination-side buying data when used as a destination;
- pad-size mismatch;
- planetary/no-planet mismatch;
- fleet-carrier mismatch;
- settlement mismatch;
- black-market mismatch;
- being too far from arrival star under `--ls-max`;
- market data being too old under `--age`;
- station avoidance;
- system avoidance.

Filters that support unknown state should accept `?` where the public CLI supports it. Supplying all possible states is equivalent to no filter.

Settlement `Y` is a planetary subset. If the user combines settlement and planetary filters in a contradictory way, the command must reject the input.

## Market-data eligibility

A commodity market record is usable only if the relevant price and quantity fields satisfy the current search role.

For source-side selling, the station must have a positive supply price and sufficient supply under the `--supply` threshold.

For destination-side buying, the station must have a positive demand price and sufficient demand under the `--demand` threshold.

If `--age` is supplied, market records older than the limit must be excluded.

Invalid or unparsable market timestamps are data errors and must not be silently treated as fresh.

## Trade candidate generation

For a source/destination station pair, a commodity is a candidate trade when:

- the source station sells it;
- the destination station buys it;
- source and destination market data pass age and quantity filters;
- the commodity is not avoided;
- destination sell value minus source buy cost is within the gain-per-ton range;
- at least one cargo unit could be bought under the current constraints.

Each candidate trade must retain enough data to report:

- commodity name;
- source station;
- destination station;
- buy price;
- sell price;
- profit per unit;
- quantity loaded;
- total profit;
- data age where displayed.

## Cargo fitting

For each hop, cargo fitting must select quantities that obey:

- cargo capacity;
- available credits;
- insurance reserve;
- safety margin for previous gains;
- per-commodity unit limit;
- source supply;
- destination demand policy if the chosen implementation treats demand as a quantity cap;
- avoided commodities;
- gain-per-ton filters.

The selected cargo should maximise expected hop value under those constraints.

A more complete optimiser is allowed and encouraged if it produces equal or better profit while remaining fast enough. The rewrite is not required to reproduce a legacy greedy cargo mix.

For small fixtures, tests should include exact optimal cargo cases so that the optimiser can be verified independently of any legacy result.

## Credits, insurance, and margin

`--insurance` reserves credits that cannot be spent on cargo.

Initial trade capital is:

```text
starting credits - insurance reserve
```

`--margin` is a safety control for market fluctuation and route compounding.

The required behaviour is:

```text
future buying power must not rely on 100% of previous expected gains when a margin is specified
```

For example, with a 25% margin, only 75% of previous expected gain should be trusted as available capital for later purchases.

Displayed profit should make clear whether it is raw expected profit or margin-adjusted planning value.

## Reachability

Unless `--direct` is active, route hops must respect jump constraints.

`--ly-per` is the maximum distance per loaded jump.

`--jumps-per` is the maximum number of system jumps allowed per station-to-station trade hop.

Same-system station movement is allowed where a valid trade exists. It should be treated as supercruise, not hyperspace.

Avoided systems must not be used in jump paths.

Avoided stations must not be route stations. They do not by themselves block travel through their parent system unless that system is also avoided.

`--show-jumps` must display the selected jump path where available. Same-system movement should be presented as supercruise.

`--direct` bypasses reachability checks and assumes candidate destinations are reachable. It is incompatible with `--loop`.

## Route generation

Route search starts from the eligible origin station set.

For each hop, the planner must:

1. determine candidate destinations reachable under the current route state and user constraints;
2. determine candidate trades between the current source and each candidate destination;
3. fit cargo under financial and capacity constraints;
4. calculate hop profit and practical score;
5. extend partial routes;
6. retain enough partial routes to find high-quality final routes under the selected search policy.

The route planner may use graph search, dynamic programming, database-side candidate generation, precomputed trade edges, branch-and-bound, shortest path algorithms, knapsack optimisation, or another suitable method.

The method must be chosen for correctness, route quality, and measured speed. It must not be derived from quarantined source.

## Route ranking

Routes are ranked by practical value.

Without `--ls-penalty`, practical value is primarily expected profit.

With `--ls-penalty`, practical value is expected profit adjusted by station distance from arrival star.

When route-shaping options are present, ranking must also honour their intent:

- `--to`: finish at the requested final place.
- `--towards`: make real progress toward the target system each hop.
- `--loop`: return to the starting station.
- `--shorten`: prefer reaching the final destination in fewer hops while retaining good trade value.
- `--via`: include the requested via places.
- `--unique`: do not revisit stations.

A route that violates constraints must never outrank a route that satisfies them.

## ls-penalty

`--ls-penalty` exists because distance from system arrival star translates into real-world player time.

Some stations are so far away that a nominally profitable route is a bad recommendation for normal trading. The penalty prevents the planner from recommending routes that waste too much supercruise time for a quick trade.

The protected curve uses station distance from arrival star in kilo-light-seconds:

```text
x = floor_to_0.1_kls(distance_ls / 1000)
```

The primitive sigmoid is:

```text
sigmoid(v) = v / (1 + abs(v))
```

The composite curve is:

```text
boost   = (1 - sigmoid(25 * (x - 1))) / 4
drop    = (-1 - sigmoid(50 * (x - 4))) / 4
middle  = (-1 + 1 / (x + 1) ** ((x + 1) / 4)) / 2
curve   = boost + drop + middle
```

If the middle term overflows for extreme distances, use:

```text
middle = -0.5
```

The user-supplied `--ls-penalty` value is converted to a multiplier weight in the range 0-1:

```text
weight = clamp(ls_penalty_percent / 100, 0, 1)
```

The practical score multiplier is:

```text
multiplier = 1 + curve * weight
```

The hop or route score affected by station distance is multiplied by this value.

Required qualitative behaviour:

- stations under roughly 1 Kls may receive a mild preference;
- stations beyond roughly 1 Kls begin losing score;
- stations beyond roughly 4 Kls lose score aggressively;
- extremely distant stations should not win merely because their raw profit is high.

This curve is protected behaviour.

## towards mode

`--towards SYSTEM` is a statement of user intent: the user wants to trade while moving toward a target system, not meander around the galaxy.

Each selected trade hop must move the route closer to the target system than the previous trade position, unless the hop reaches the target system.

If no profitable valid hop can be found that moves closer to the target, the command must fail with a clear no-route message explaining that no profitable forward progress was available under the supplied constraints.

A route may still optimise profit among forward-progress candidates, but it must not choose a profitable hop that moves away from the target or leaves the route no closer.

## loop routes

`--loop` requires the route to finish at the starting station.

It is incompatible with `--direct` and `--unique`.

A loop route is valid only if every hop is valid and the final station is the original starting station.

Ranking loop routes should avoid rewarding longer routes purely because they accumulate more hops. A normalised practical value such as score per hop or profit per practical effort is acceptable.

## shorten routes

`--shorten` requires `--to`.

It is incompatible with `--loop`.

The command should prefer routes that reach the requested destination sooner when profit is comparable. A much worse route should not win solely because it is shorter unless the user-facing semantics explicitly say shortest route dominates profit.

## unique and loop interval

`--unique` forbids visiting the same station more than once.

`--loop-interval N` forbids revisiting a station until at least `N` hops have passed since the previous visit.

`--loop-interval` below 2 is invalid.

If a requested unique or loop-interval route is impossible under the hop count and station set, the command must fail clearly.

## Pruning controls

Pruning is a performance control, not a correctness requirement.

`--max-routes` limits the number of partial routes retained between expansion stages.

`--prune-score P` is intended to discard weak partial routes after the search has progressed far enough for route scores to be meaningful.

Starting at `--prune-hops`, a sensible interpretation is:

```text
retain partial routes whose score is at least P percent of the current best partial-route score
```

For example, if the best partial route score is 1,000,000 and `--prune-score 80` is active, partial routes below 800,000 may be discarded before further expansion.

The implementation may use an equivalent or better pruning policy if:

- user constraints remain hard constraints;
- pruning behaviour is documented;
- route quality remains comparable or better on benchmarks;
- the command does not silently report invalid routes as valid.

## Output contract

Default output must show a human-usable route with enough information to fly it:

- route path;
- source stations;
- destination stations;
- commodities to buy;
- quantities;
- expected gain;
- final estimated credits or total gain;
- gain-per-ton or equivalent profit summary.

Verbose output should include additional useful details where available:

- practical score;
- buy price;
- sell price;
- source and destination data age;
- station attributes;
- per-hop gain;
- cumulative gain;
- jump path.

Output formatting does not need to be byte-for-byte identical to the existing command. It must remain readable, stable, and script-tolerant enough for practical use.

## Checklist output

`--checklist` produces an interactive route flow for a single selected route.

It should guide the user through:

- buying cargo;
- optional refuel/dock prompts where detail mode requests them;
- travel or jumps;
- selling cargo;
- cumulative gain and credit updates where detail mode requests them.

`--x52-pro` requires checklist mode and mirrors checklist progress to the supported device.

Checklist mode is only valid when one route is displayed.

## Progress output

`--progress` may show long-running search progress.

Progress reporting must not change results.

Progress reporting must not materially degrade planner performance.

## Failure behaviour

The command must distinguish these failure classes:

- invalid command-line option combination;
- missing required input;
- unknown system, station, or commodity;
- ambiguous system, station, or commodity;
- selected station has no market;
- selected station has no usable price data;
- no eligible origins;
- no eligible destinations;
- no profitable trades;
- no reachable route under jump constraints;
- no route satisfying via constraints;
- no route satisfying towards progress;
- no route satisfying loop or unique constraints;
- user cancellation.

Failures should name the relevant option or route side where practical.

If a no-route condition is caused by user constraints, the message should make that clear rather than implying missing data.

If a selected station exists but lacks needed market data, the message should distinguish that from an unknown station.

## Data requirements

The planner needs access to:

- systems and coordinates;
- stations and their parent systems;
- station market/service attributes;
- station distance from arrival star;
- commodity identifiers and names;
- station commodity buy/sell prices;
- supply and demand;
- market-data timestamps or age;
- any station type fields needed for pad, planetary, fleet-carrier, settlement, black-market, and service filters.

The planner should treat the database as the source of truth.

It should query and materialise only the data needed for the requested search scope.

## Performance contract

The rewrite must be materially faster than the existing command on the benchmark corpus.

It must be designed around early narrowing:

- validate static arguments before planning;
- resolve scoped names cheaply;
- reduce candidate systems and stations before market-pair expansion;
- push filters into database queries where practical;
- avoid broad Python materialisation when a database query can narrow the set;
- make long searches cancellable;
- measure planning and rendering separately.

This document does not mandate a specific database strategy. It mandates measured speed and route quality.

## Benchmark corpus

The following benchmark commands are the route-planning corpus. They are used by the supervisor to compare route quality and runtime.

### run-short

```text
trade run --from "Colonia/Akinyemi Horticultural Market" --to "Colonia/Jaques Station" --capacity 64 --credits 1000000 --hops 1 --jumps-per 1 --ly-per 20
```

Purpose: short constrained run.

Baseline timing evidence:

```text
cold: 26.370s
warm: 28.890s
```

### run-typical

```text
trade run --from "Colonia/Jaques Station" --capacity 128 --credits 5000000 --hops 2 --jumps-per 2 --ly-per 20
```

Purpose: representative seeded run.

Baseline timing evidence:

```text
cold: 28.380s
warm: 30.290s
```

### run-wide

```text
trade run --from "Colonia/Jaques Station" --start-jumps 1 --capacity 128 --credits 5000000 --hops 3 --jumps-per 2 --ly-per 20 --routes 3
```

Purpose: broader/heavier run.

Baseline timing evidence:

```text
cold: 32.760s
warm: 30.720s
```

Benchmark pass criteria:

- route must be valid;
- route must satisfy the same user constraints;
- route must produce equal-or-better practical value, allowing normal market drift;
- runtime must be materially lower than baseline;
- tiny runtime deltas are not success;
- if practical value is lower, the difference must be explained and accepted by the supervisor.

## Testing policy

Existing tests must be classified before being used as rewrite gates.

Authoritative test types:

- public CLI option validation;
- command failure categories;
- resolver behaviour visible to users;
- station and commodity filter behaviour;
- cargo arithmetic;
- cargo feasibility;
- jump reachability;
- route validity;
- `--ls-penalty` curve behaviour;
- benchmark route quality and runtime.

Not authoritative by default:

- tests requiring private legacy object structures;
- tests requiring private legacy cache contents;
- tests requiring exact intermediate route frontiers;
- tests requiring exact route identity where the optimum is not independently known;
- tests asserting quirks of quarantined implementation modules rather than public behaviour.

Exact expected-route tests are acceptable only when the fixture is small enough that the optimum is independently known.

For larger real-data tests, compare validity, practical value, and runtime rather than exact route identity.

## Suggested implementation boundary

A safe architecture boundary is:

```text
CLI parser -> neutral RunRequest -> new route planner -> route result -> renderer
```

The neutral request should contain parsed user intent, resolved or resolvable identifiers, numeric constraints, filter settings, and output preferences.

The new planner owns route planning. It must not receive quarantined implementation objects.

The renderer may reuse common output infrastructure where doing so does not couple the planner to quarantined source.

## Agent handoff rule

Implementation agents should receive this specification, database schema information, benchmark commands, and any new neutral request interface definitions.

They should not receive quarantined source files or summaries of how those files work.

If an implementation agent asks to inspect quarantined source to answer a design question, stop and escalate to the supervisor.

## Open decisions for supervisor

These are not blockers for implementation planning, but they may need supervisor decisions during the rewrite:

1. Whether destination demand is only an eligibility threshold or also a hard cargo quantity cap.
2. Exact tolerance for comparable profit under normal market drift.
3. Exact wall-clock performance gate for each benchmark after the new planner is integrated.
4. Whether output needs a machine-readable mode for robust future tests.
5. Whether broad unseeded galaxy-wide searches should have explicit safety limits or require user confirmation.

## Final acceptance summary

A completed rewrite is acceptable when it can demonstrate all of the following:

- it obeys the user-facing `trade run` option contract;
- it does not use quarantined implementation source;
- it returns valid routes under the supplied constraints;
- it produces equal-or-better practical value against the benchmark corpus, allowing ordinary market drift;
- it preserves the protected `--ls-penalty` curve;
- it handles no-route and no-data cases clearly;
- it materially improves runtime;
- it passes authoritative public-behaviour tests;
- it replaces implementation-coupled legacy tests with black-box, arithmetic, route-validity, and benchmark tests.
