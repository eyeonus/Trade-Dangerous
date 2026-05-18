# trade run second Slice Plan — One-Hop Expanded Endpoints

## Purpose

Extend the completed first safe slice from fixed station-to-station planning into bounded one-hop endpoint expansion.

The first safe slice proves this boundary:

```text
CLI parser
  -> RunRequest
  -> planner
  -> RunResult
  -> renderer
```

The next slice should preserve that architecture and add one new planner capability:

```text
Given one or both endpoints as systems, expand those systems to eligible stations,
evaluate valid one-hop station pairs, and return the best route.
```

This is still not multi-hop routing. It is the smallest useful step from “known station pair” to “planner selects between alternatives”.

---

## Absolute Source Quarantine

The quarantine remains mandatory.

Do not inspect, import, call, subclass, adapt, translate, summarise, or ask another tool to summarise:

```text
tradedangerous/tradecalc.py
tradedangerous/tradedb.py
```

Do not use legacy route-planning objects, legacy database facade objects, private route/cache/frontier structures, or adapters that recreate them.

Do not convert new planner results into legacy route objects.

The planner must continue to operate through:

```text
RunRequest -> planner -> RunResult -> renderer
```

Permitted implementation sources:

```text
- black-box trade run behavioural specification
- first safe slice implementation plan
- first safe slice completion report
- this next-slice plan
- current planner package
- ORM models
- resolver surfaces
- public command parser metadata
- public/black-box tests
- fixture data used to prove route validity and arithmetic
```

---

## Slice Name

```text
One-Hop Expanded Endpoints
```

---

## Goal

Support one-hop route planning where `--from` and/or `--to` may resolve to a system.

The planner should expand system endpoints to eligible stations, evaluate all valid source/destination station pairs within that bounded endpoint set, optimise cargo for each viable pair, and return the highest-scoring one-hop route.

---

## Supported Command Shapes

Continue supporting the completed first-slice shape:

```text
trade run --from "System/Station" --to "System/Station" --capacity N --credits N --hops 1 --jumps-per N --ly-per N
```

Add support for these endpoint combinations:

```text
trade run --from "System"         --to "System/Station" --capacity N --credits N --hops 1 --jumps-per N --ly-per N
trade run --from "System/Station" --to "System"         --capacity N --credits N --hops 1 --jumps-per N --ly-per N
trade run --from "System"         --to "System"         --capacity N --credits N --hops 1 --jumps-per N --ly-per N
```

Endpoint meanings:

```text
--from station:
  fixed source station

--from system:
  expand to eligible source stations in that system

--to station:
  fixed destination station

--to system:
  expand to eligible destination stations in that system
```

---

## Still Out of Scope

Do not implement these in this slice:

```text
- --hops > 1
- --start-jumps
- --end-jumps
- omitted --from
- omitted --to
- --direct
- --towards
- --via
- --avoid
- --loop
- --unique
- --loop-interval
- --shorten
- --routes > 1
- --checklist
- --x52-pro
- broad galaxy-wide search
- multi-hop route graph search
- route pruning/frontier expansion
```

Unsupported shapes should continue to fail explicitly when the new planner path is selected.

---

## Behavioural Requirements

### Endpoint Resolution

The planner must distinguish between:

```text
- explicit station endpoint
- system endpoint requiring station expansion
```

For scoped station input:

```text
System/Station
```

the station must be resolved within that system.

Do not fall back to broad global station matching when the user supplied a scoped system/station form.

For system input:

```text
System
```

the system resolves first, then expands to eligible stations in that system.

### Station Expansion

When expanding a system endpoint, include only stations that are eligible for the requested role.

For source-side expansion, stations must be capable of acting as a source.

For destination-side expansion, stations must be capable of acting as a destination.

Apply station filters during or before expansion where practical.

Filters include, where already supported by the first slice:

```text
- market availability
- pad size
- planetary / non-planetary state
- fleet carrier state
- settlement state
- black market state
- max ls distance
- market-data age
```

### Station Pair Evaluation

For every valid source/destination station pair:

```text
1. check station eligibility
2. check reachability
3. generate trade candidates
4. optimise cargo
5. calculate raw profit
6. calculate practical score where applicable
7. retain the best valid one-hop route
```

Pairs that fail reachability, station eligibility, market-data eligibility, or cargo feasibility must be excluded from selection.

They may be recorded in diagnostics if that is already convenient, but diagnostics are not the primary deliverable.

### Cargo Rules

Reuse the first-slice cargo optimiser.

Continue enforcing:

```text
- cargo capacity
- starting credits minus insurance reserve
- per-item cargo limit
- source supply
- destination demand as a hard cap
- positive buy/sell prices
- positive profit subject to gain filters
- exact total cost/profit arithmetic
```

Do not replace the cargo optimiser with a greedy-only selector.

### Route Selection

The selected route must be the highest-scoring valid one-hop route among all valid station pairs in the expanded endpoint set.

For this slice, raw profit may remain the primary score unless the current planner already wires practical score penalties into user-facing route selection.

A route that violates constraints must never be selected over a valid route.

### Output

The renderer must show the actual selected stations, not merely the endpoint systems.

Output must make clear:

```text
- selected source station
- selected destination station
- commodities
- quantities
- expected gain
- total gain / final credits
```

Existing first-slice station-to-station output must not regress.

---

## Failure Requirements

Fail clearly for:

```text
- unknown source system
- unknown destination system
- unknown scoped station
- ambiguous endpoint
- system endpoint with no eligible source stations
- system endpoint with no eligible destination stations
- no reachable station pair
- no profitable trade across all valid pairs
- no affordable cargo across all valid pairs
- unsupported route shape
```

Selected system endpoints with no usable market stations must be distinguished from unknown systems.

Expected planner failures must not emit tracebacks.

---

## Suggested Internal Shape

The exact names are not mandatory, but the planner should gain the following concepts.

### Endpoint Resolution Result

Represents either:

```text
FixedStationEndpoint
SystemStationSetEndpoint
```

or equivalent data.

Essential fields:

```text
- endpoint role: source or destination
- original user text
- resolved system, if applicable
- fixed station, if applicable
- expanded station list, if applicable
```

### Station Pair Candidate

Represents one candidate one-hop route before final selection.

Useful fields:

```text
- source station
- destination station
- reachability result
- trade candidates
- cargo plan
- raw profit
- practical score
- rejection reason, if rejected
```

This should remain one-hop-specific. Do not introduce a general multi-hop graph abstraction in this slice.

### Pair Selector

Responsible for:

```text
1. expanding endpoints
2. applying station filters
3. generating bounded station pairs
4. excluding unreachable pairs
5. producing cargo plans for viable pairs
6. selecting the best one-hop result
```

---

## Data Access Guidance

Prefer bounded ORM/query access.

The search space is bounded by the selected endpoint systems, not by the galaxy.

A reasonable implementation strategy:

```text
1. resolve endpoint text
2. fetch eligible source station set
3. fetch eligible destination station set
4. fetch source-side quote data for all source station IDs
5. fetch destination-side quote data for all destination station IDs
6. evaluate station pairs in planner space using already narrowed data
```

Avoid broad market materialisation.

Avoid repeated database round trips per commodity.

Per-pair cargo optimisation is acceptable for this slice as long as quote fetching is reasonably bounded and measured.

---

## Tests to Add

### Endpoint Resolution / Expansion

Add tests for:

```text
- station -> station remains supported
- system -> station expands source stations
- station -> system expands destination stations
- system -> system expands both sides
- scoped station does not fall back globally
- unknown system fails as unknown system
- unknown station inside valid system fails as unknown station
- system-only endpoint no longer fails merely because it is system-only
```

### Station Eligibility

Add tests for:

```text
- source system with no eligible market stations fails source-side
- destination system with no eligible market stations fails destination-side
- pad-size filter excludes incompatible stations only
- no-planet filter excludes planetary stations only
- black-market state filter works across expanded stations
- max-ls filter excludes distant stations
- stale market data is excluded
```

### Pair Selection

Use small fixtures where the expected optimum is independently obvious.

Add tests for:

```text
- two source stations, one destination station: better source selected
- one source station, two destination stations: better destination selected
- two-by-two station matrix: best total cargo plan selected
- unaffordable high-profit pair loses to affordable profitable pair
- unreachable high-profit pair is excluded
- lower unit-profit mixed cargo can beat higher unit-profit unaffordable cargo
```

### Cargo Preservation

Existing cargo optimiser tests must continue passing.

Add integration checks that expanded endpoint selection still obeys:

```text
- capacity
- credits
- source supply
- destination demand
- per-item limit
- final credits arithmetic
```

### Command Integration

Add tests for:

```text
- new planner path accepts system/station mixed endpoint forms
- unsupported options still fail explicitly
- comparison path remains available
- output includes actual selected source and destination station names
```

---

## Manual Validation Commands

Use small, understandable real-data commands.

Examples:

```text
trade run --from "Lave" --to "Diso" --capacity 64 --credits 1000000 --hops 1 --jumps-per 1 --ly-per 20
```

```text
trade run --from "Lave/Lave Station" --to "Diso" --capacity 64 --credits 1000000 --hops 1 --jumps-per 1 --ly-per 20
```

```text
trade run --from "Lave" --to "Diso/Bao Station" --capacity 64 --credits 1000000 --hops 1 --jumps-per 1 --ly-per 20
```

Also re-run the completed first-slice benchmark:

```text
trade run --from "Colonia/Akinyemi Horticultural Market" --to "Colonia/Jaques Station" --capacity 64 --credits 1000000 --hops 1 --jumps-per 1 --ly-per 20
```

If the comparison path is available:

```text
trade run --old --from "Lave" --to "Diso" --capacity 64 --credits 1000000 --hops 1 --jumps-per 1 --ly-per 20
```

Use comparison results as evidence only. Do not make exact legacy route identity a hard requirement unless the fixture optimum is independently known.

---

## Performance Expectations

This slice should remain fast because the search is bounded by explicitly selected systems.

Expected performance characteristics:

```text
- fixed station-to-station remains near first-slice speed
- system endpoint expansion remains quick for ordinary systems
- no broad preload cost is introduced
- no galaxy-wide candidate materialisation is introduced
```

If a selected system contains many stations, correctness still matters, but broad optimisation should be deferred unless real timing evidence shows it is necessary.

Record rough manual timings, even if no formal harness exists yet.

---

## Completion Criteria

This slice is complete when:

```text
- all four endpoint shape combinations work
- first-slice station-to-station behaviour still works
- endpoint systems expand to eligible stations
- best valid station pair is selected
- cargo plan obeys all first-slice cargo constraints
- unreachable pairs are excluded
- unsupported route shapes still fail explicitly
- expected planner failures do not traceback
- output reports actual selected stations and cargo
- comparison path remains usable
- manual real-data validation has been run and recorded
```

---

## Recommended Implementation Order

```text
1. Add endpoint result representation.
2. Extend validation to allow system endpoints while keeping other unsupported shapes rejected.
3. Extend resolver layer to return fixed station or system endpoint result.
4. Add source/destination station expansion queries.
5. Add station-pair candidate evaluation.
6. Reuse existing reachability checks per pair.
7. Reuse existing trade candidate generation and cargo optimiser per viable pair.
8. Add best-route selection.
9. Update renderer only if needed to display selected expanded stations cleanly.
10. Add fixture tests for endpoint expansion and pair selection.
11. Re-run first-slice tests.
12. Run manual real-data validation commands.
13. Record results in the slice completion report.
```

---

## Non-Goals

Do not attempt to solve future route planning in this slice.

Specifically, do not design or implement:

```text
- generic route graph search
- multi-hop frontier management
- pruning policy
- via/avoid route constraints
- loop routing
- towards routing
- multiple displayed routes
- checklist mode
```

This slice should prove one thing cleanly:

```text
The new planner can expand bounded endpoints and select the best valid one-hop station pair without touching quarantined route-planning internals.
```