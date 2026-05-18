# trade run Fourth Slice Plan — Open-Ended Origin Search

## Purpose

Extend the one-hop planner so a single hop can be planned when the *origin*
endpoint is left open.

Slice 3 delivered the open-ended *destination* search: `--from` fixed, `--to`
omitted, the planner selecting the destination. That search is not
destination-specific in nature — it is an anchored open-ended search that
happened to have only one caller. This slice generalises it to work from
either anchored endpoint, so an omitted `--from` with a fixed `--to` is served
by the *same* code path, selecting the origin instead of the destination.

The deliverable is one open-ended one-hop search parameterised by which
endpoint is open — not two parallel searches. Slice 3's open-destination
search becomes one case of it.

After this slice the one-hop family is complete but for one shape — both
endpoints omitted — which is the genuinely unanchored galaxy search and
remains deferred.

The architecture boundary is unchanged:

```text
RunRequest -> planner -> RunResult -> renderer
```

## Absolute Source Quarantine

The quarantine remains mandatory. Do not inspect, import, call, subclass,
adapt, translate, summarise, or ask another tool to summarise:

```text
tradedangerous/tradecalc.py
tradedangerous/tradedb.py
```

Do not use legacy route-planning objects, legacy database facade objects, or
private route/cache/frontier structures, and do not convert planner results
into legacy route objects. `tradedangerous/commands/run_cmd.py` remains
permitted — it is the command entry surface, not a quarantined module.

Generalising the planner's own Slice 1-3 code is in scope and expected; the
quarantine concerns only the two legacy modules named above.

Permitted implementation sources:

```text
- black-box trade run behavioural specification
- first, second, and third slice implementation plans and completion reports
- this plan
- the current planner package
- ORM models and resolver surfaces
- public command parser metadata
- local_cmd.py as the reference spatial-query pattern
- official Python / SQLAlchemy / database documentation
```

## Slice Name

```text
Open-Ended Origin Search
```

## Goal

Support one-hop planning where `--to` is supplied and `--from` is omitted, by
generalising the open-ended search delivered in Slice 3 to run from either
anchored endpoint.

The supplied destination may be a station or a system (Slice 2 behaviour,
unchanged). The omitted origin is filled by the planner as the best reachable
station, bounded by single-jump reachability to the destination system.

## Design Constraint — Anchored Search Still Primary

This carries forward the Slice 3 constraint.

```text
- The open-ended search built in Slice 3 is generalised, not mirrored. One
  parameterised path serves both anchored directions; the open-destination
  search becomes one case of it.
- Slice 3 correctly declined to add the direction parameter speculatively when
  only one caller existed. Slice 4 is the second concrete caller, so the
  parameter is warranted now and is introduced here — the abstraction is
  discovered at the point the second caller arrives, not imposed ahead of need.
- The parameter selects between two anchored directions only. It does not turn
  the search into a generic galaxy scanner.
- The genuinely unanchored search (both endpoints omitted) remains deferred. It
  must be a separate, additive path, never a parameterisation of an anchored
  query. No hooks or flags anticipating it are added here.
```

## Supported Command Shapes

Continue supporting every Slice 1-3 shape. Add:

```text
trade run --to "<station|system>"   [--from omitted]   --capacity N --credits N --hops 1 --ly-per N
```

Endpoint meanings:

```text
--from station   fixed origin station                    (Slice 1-2)
--from system    expand to eligible origin stations       (Slice 2)
--from omitted   planner selects the origin               (NEW)
--to   station   fixed destination station                (Slice 1-2)
--to   system    expand to eligible destination stations  (Slice 2)
--to   omitted   planner selects the destination          (Slice 3)
```

Still `--hops 1` and `--routes 1`. With the `--jumps-per` default of 1
(unchanged from Slice 3), the omitted-`--from` shape works without the user
supplying `--jumps-per`.

At least one of `--from` / `--to` must be supplied. Both omitted is rejected
(see Failure Requirements).

## Still Out of Scope

```text
- both --from and --to omitted              (deferred, not cut — see roadmap note)
- --jumps-per >= 2 with an endpoint omitted  (multi-jump reachability — later slice)
- --jumps-per default keyed to --ly-per      (deferred — see roadmap note)
- --hops > 1, --start-jumps, --end-jumps
- --direct, --towards, --via, --avoid, --loop, --unique, --loop-interval, --shorten
- --routes > 1, --checklist, --x52-pro
- multi-hop search, route frontier, pruning
- --progress
```

Unsupported shapes must continue to fail explicitly when the new planner path
runs.

## Behavioural Requirements

### `open_role` — the one parameter

The open-ended search is parameterised by `open_role`, the trade role of the
endpoint the planner selects:

```text
open_role = "destination"   --from fixed, planner selects the destination  (Slice 3)
open_role = "source"        --to   fixed, planner selects the origin        (NEW)
```

The other endpoint is the fixed, anchored one. Its trade role is the opposite
of `open_role` and is the existing `_stations_from_endpoint` `role` value.

### Endpoint roles and dispatch

`plan_onehop_route` dispatches on which endpoints are present:

```text
--from and --to present     -> _plan_fixed_endpoints                 (Slice 1-2, unchanged)
--from present, --to absent  -> _best_open_ended_plan(open_role="destination")
--from absent, --to present  -> _best_open_ended_plan(open_role="source")
both absent                  -> rejected in validation
```

Validation guarantees at least one endpoint, so the `open_role="source"`
branch is reached only with `--to` present.

`_plan_fixed_endpoints` (both endpoints named) stays separate — an N×M
station-pair matrix with per-pair reachability and per-pair market queries.
For a single hop with both endpoints named there is nothing spatial to search:
every candidate station derives from the two named endpoints, so the matrix is
the right shape and is not a twin of the open-ended search. That is a property
of one hop with both ends fixed, not of fixed endpoints in general — see the
roadmap note on multi-hop search.

### The unified open-ended search

`_best_open_ended_plan(session, request, started, validation_ms, *, open_role)`
is the single open-ended planner. It:

```text
1. derives the fixed endpoint's role, option name, and request text from
   open_role
2. resolves the fixed endpoint and expands it to the fixed station set
   (resolver.resolve_endpoint + _stations_from_endpoint, role = fixed role)
3. takes the fixed endpoint's system as the anchor
   (_anchor_system_from_endpoint)
4. runs the bulk candidate query (below)
5. materialises the open side's station DTOs
6. evaluates station pairs and selects the best
7. builds one jump path for the winning pair and assembles the RunResult
```

Only step 1 reads `open_role`. Steps 2-7 are direction-agnostic.

### Reachable-station spatial query

The open station set is the stations in systems reachable from the anchor in a
single loaded jump. A loaded jump is symmetric in distance, so "systems within
`--ly-per` of the anchor" is the reachable set whichever endpoint is anchored.
The query narrows spatially in SQL before any market join:

```text
1. anchor system coords (ax, ay, az); reach radius L = max_ly_per_jump
2. bounding box on the indexed System.pos_x/pos_y/pos_z columns
3. exact squared-distance refinement, SQL-side, no sqrt
4. station-attribute filters applied in the same statement
```

`_reachable_destination_station_ids` already performs exactly this and is
role-neutral in its logic. Slice 4 renames it `_reachable_station_ids` and
reuses it unchanged.

For `--jumps-per 0`, the open side is the anchor system only (same-system
supercruise). For `--jumps-per 1`, the full radius. `--jumps-per >= 2` with an
endpoint omitted is rejected in validation.

### Open-ended trade candidate generation

`fetch_open_ended_trade_candidates` is generalised. It takes the fixed
endpoint's station ids (`fixed_station_ids`), the anchor system, and
`open_role`. The reachable open set comes from `_reachable_station_ids`. The
fixed set and the reachable set are assigned to the supply and demand queries
from `open_role`:

```text
open_role = "destination":  supply rows <- fixed set;      demand rows <- reachable set
open_role = "source":       supply rows <- reachable set;   demand rows <- fixed set
```

Everything else is unchanged: two single-table queries, each driven by its
station-id set through the `StationItem` primary key, matched on `item_id` in
Python; the same per-trade filters (positive source supply price and units,
positive destination demand price, `_MIN_MEANINGFUL_DEMAND`, gain-per-ton
range, min-supply / min-demand, age cutoff, affordability of one unit); and
`TradeCandidate` carrying both `source_station_id` and `destination_station_id`.

The split supply/demand query shape is retained. A single self-join lets
SQLite scan the market table galaxy-wide by `item_id` — the `--pad-size S`
pathology Slice 3 diagnosed and removed. Both table accesses must stay on the
`StationItem` primary key via a station-id set. The role filters (affordability
on the supply query, `_MIN_MEANINGFUL_DEMAND` on the demand query) stay on
their respective queries regardless of which station set feeds them.

The open side's `ResolvedStation` DTOs are fetched, via `fetch_stations_by_id`,
only for the distinct open-side station ids that appear in candidates.
Reachable stations with no profitable trade are never materialised.

### Station-pair evaluation and selection

Direction-agnostic. The fixed station DTOs and the fetched open-side DTOs are
merged into one `station_id -> ResolvedStation` map. The two sets are disjoint:
`_reachable_station_ids` is given the fixed ids as `excluded_station_ids`, so a
fixed station never appears in the open set.

Group candidates by `(source_station_id, destination_station_id)` via
`_group_pairs`, which drops self-pairs. For each pair:

```text
1. run the existing optimise_cargo
2. score with score_with_destination_penalty using the destination station's
   ls_from_star — looked up from the merged map; no direction branch needed
3. retain the best pair via the existing _pair_is_better
```

### Reachability

The spatial query is itself the reachability filter for the open side, so
per-pair `plan_jump_path` calls are not used for filtering. `plan_jump_path`
is called exactly once — for the winning pair — to build the `JumpPath` for
output. Same-system pairs are reported as supercruise.

### Cargo

Unchanged. The first-slice cargo optimiser and all its constraints (capacity,
credits minus insurance reserve, per-item limit, source supply, destination
demand as a hard cap, positive profit under gain filters, exact total
cost/profit arithmetic) continue to apply per pair.

### Output

No renderer change is expected. The selected route already carries concrete
source and destination `ResolvedStation` objects, and Slice 2-3 already render
planner-selected stations. Verify only that output reads sensibly when the
user did not name the selected origin.

## Failure Requirements

Reuse the existing failure taxonomy — no new failure classes are needed:

```text
- fixed endpoint unknown / ambiguous            -> existing resolver failures
- fixed system has no eligible stations         -> Source/DestinationStationIneligible
- no reachable station in range                 -> NoReachableRoute
- reachable stations but no profitable trade      -> NoProfitableTrades
- profitable trades but no affordable cargo        -> NoAffordableCargo
- both --from and --to omitted                   -> UnsupportedRunShape
- --jumps-per >= 2 with an endpoint omitted        -> UnsupportedRunShape
```

All map cleanly through the existing `run_cmd.py` exception handling. Expected
planner failures must not emit tracebacks. Open-ended failure granularity stays
coarse — one aggregate reason.

`_raise_empty_open_search` is parameterised by `open_role` so its
`NoProfitableTrades` and `NoReachableRoute` messages name the anchored side
correctly: for `open_role="source"` they refer to the destination
("...to the destination from any reachable station", "...within range of the
destination system").

## Suggested Internal Shape

Concrete, minimal-scope change set:

```text
commands/run_cmd.py
  - no change. The --jumps-per parser default stays 1; the keyed default is
    deferred (see roadmap note). The new-planner reject block and the planner
    dispatch are unaffected.

planner/run_request.py
  - no change. from_text / to_text are already optional str | None.

planner/validation.py
  - remove _require_present(from_text, "--from"); --from is now optional
  - add: from_text and to_text both empty/None -> UnsupportedRunShape
         ("Either --from or --to must be supplied."), placed with the other
         shape guards, before the omitted-endpoint --jumps-per guard
  - generalise the omitted-endpoint --jumps-per guard: the condition changes
    from "not to_text" to "not from_text or not to_text", and the message is
    reworded to name both options
  - capacity / credits / ly-per remain required (_require_present unchanged)

planner/data_gateway.py
  - rename _reachable_destination_station_ids -> _reachable_station_ids
    (role-neutral name; update its docstring and both call sites)
  - generalise fetch_open_ended_trade_candidates: rename the parameter
    fixed_origin_station_ids -> fixed_station_ids, add a keyword-only
    open_role, and assign the fixed and reachable station-id sets to the
    supply and demand queries from open_role. The body below that assignment
    is unchanged.

planner/run_onehop.py
  - rename _best_open_destination_plan -> _best_open_ended_plan and add a
    keyword-only open_role; derive the fixed endpoint's role/option/text from
    open_role; the pair-evaluation core becomes direction-agnostic via the
    merged station map
  - parameterise _raise_empty_open_search by open_role for message wording
  - plan_onehop_route: three-way dispatch routing both open-ended cases into
    _best_open_ended_plan with the appropriate open_role

unchanged: cargo.py, score.py, reachability.py, resolver.py,
           render_text.py, run_result.py, failures.py
```

## Design Note — Generalising the Slice 3 Path

Slice 4 does not add a second open-ended search. It generalises the one Slice 3
built. `fetch_open_ended_trade_candidates` and `_best_open_destination_plan`
were written for a fixed origin, but their logic is not origin-specific — only
which station set is fixed and which is spatially reached differs between the
two directions. Slice 4 lifts that single difference into `open_role` and
routes both directions through the same code.

This refactors audited Slice 3 code. That is intended. The audited behaviour is
the open-*destination* path; after generalisation that path is simply the
`open_role="destination"` case and must behave identically. The Slice 3
regression checks — the open-destination validation commands and the run-short
benchmark — re-confirm this. A generalisation that changes an open-destination
result is a bug, not a feature.

## Data Access Guidance

```text
- The open-ended spatial query must narrow via the System bounding box before
  touching StationItem. _reachable_station_ids already enforces this staging —
  reuse it, do not re-implement.
- Keep the split supply/demand query shape for both directions. A single
  self-join lets SQLite scan the market table galaxy-wide by item_id, the
  --pad-size S pathology Slice 3 removed. Both table accesses stay on the
  StationItem primary key via a station-id set.
- The spatially-reached station set feeds the demand query for
  open_role="destination" and the supply query for open_role="source". Both
  are primary-key-driven single-table lookups; the query shape and its
  performance property are identical either way.
- Pass the fixed endpoint's station ids as excluded_station_ids so the fixed
  stations cannot appear in the open set (the Slice 3 audit fix, now applying
  in both directions).
- Use squared distance (<= L*L) in SQL. No sqrt. No Python-side distance
  filtering.
- candidate_trade_count and the existing PlannerDiagnostics timing fields are
  reused; no new diagnostics fields are added.
```

## Manual Validation

No automated test harness — per supervisor direction, the new path is
spot-checked against `--old` while results remain comparable. Run each command
on the new path and with `--old`, and compare route validity and profit
(the legacy path supports an omitted `--from`, so it is a usable baseline):

```text
trade run --to "Lave/Lave Station"  --capacity 64 --credits 1000000 --hops 1 --ly-per 20
trade run --to "Lave"               --capacity 64 --credits 1000000 --hops 1 --ly-per 20
trade run --to "Lave/Lave Station"  --capacity 64 --credits 1000000 --hops 1 --jumps-per 0 --ly-per 20
```

Generalisation regression — the open-destination path must be unchanged. Re-run
the Slice 3 open-destination validation commands and the run-short Colonia
benchmark; results must match the Slice 3 completion report:

```text
trade run --from "Lave/Lave Station"  --capacity 64 --credits 1000000 --hops 1 --ly-per 20
trade run --from "Lave"               --capacity 64 --credits 1000000 --hops 1 --ly-per 20
trade run --from "Colonia/Akinyemi Horticultural Market" --to "Colonia/Jaques Station" --capacity 64 --credits 1000000 --hops 1 --jumps-per 1 --ly-per 20
```

Other regression checks (must still behave as Slices 1-3):

```text
- all both-endpoint shapes (station/system combinations)
- unsupported-shape and unknown-endpoint failures, no traceback
```

New failure checks:

```text
- both --from and --to omitted        -> UnsupportedRunShape, no traceback
- --from omitted with --jumps-per 2    -> UnsupportedRunShape, no traceback
```

Also exercise one dense-region command (for example `--to "Sol"` with `--from`
omitted) to measure the spatial query where systems are densest. Record rough
manual timings.

## Performance Expectations

```text
- Fixed-endpoint and omitted---to shapes remain at Slice 1-3 speed.
- Open-origin search is bounded by the single-jump reach radius around the
  destination, not the galaxy. It should be comparable to the Slice 3
  open-destination search; dense regions are the case to measure.
```

## Deferred Work — Roadmap Note

**Both endpoints omitted.** The genuinely unanchored galaxy search. Deferred,
not cut — `--old` supports it today and `--old` retires at version 13, so the
new planner must cover it before then. It must be built as a separate additive
path, never as a generalisation of an anchored query. `--progress`
(long-running search feedback) and the open question of galaxy-scan safety
limits belong with it.

**`--jumps-per` default keyed to `--ly-per`.** Considered for this slice and
deferred. The agreed rule sets `--jumps-per 2` for `--ly-per <= 12.5`, but the
new planner cannot fly a 2-jump hop: `plan_jump_path` raises
`ReachabilityImplementationMissing` for any cross-system hop with
`max_jumps_per_hop >= 2`, and the open-ended path rejects `--jumps-per >= 2`
in validation. A default of 2 is only meaningful once multi-jump per-hop
reachability exists, so the keyed default belongs with the slice that delivers
that capability, not here. Until then the flat default of 1 stands. The
SLICE_SUMMARY "Deferred Decisions" earmark, which currently names this an
opening item for Slice 4, should be corrected when Slice 4's summary update is
written.

**Multi-jump per-hop reachability.** `--jumps-per >= 2`. Deferred since
Slice 1. A prerequisite for the keyed default above and for multi-jump
open-ended search.

**Multi-hop search and endpoint anchoring.** The one-hop dispatch treats
both-endpoints-named as a no-search path (`_plan_fixed_endpoints`) and any
omitted endpoint as a spatial search. That split holds only for a single hop.
In multi-hop routing the intermediate stations are unknowns that must be
searched even when `--from` and `--to` are both named; only a fully-pinning
`--via` set removes that, and `--direct` sidesteps it but is itself constrained
to a single hop. The multi-hop slice must not inherit a "fixed endpoints mean
no search" assumption from the one-hop dispatch — anchoring an endpoint removes
an unknown, not the need to search.

## Completion Criteria

```text
- omitted --from works for both a station --to and a system --to
- the open-destination (Slice 3) path produces identical results after the
  generalisation — verified against the Slice 3 validation commands and the
  run-short benchmark
- both-endpoint (Slice 1-2) behaviour is unchanged
- one parameterised open-ended path serves both directions; there is no
  duplicated open-ended search function
- the open side is narrowed by SQL spatial predicates anchored on the fixed
  endpoint, not Python-side filtering
- the best valid one-hop pair is selected; self-pairs are excluded; the fixed
  stations are excluded from the open set
- the cargo plan obeys all first-slice cargo constraints
- both endpoints omitted, and --jumps-per >= 2 with an endpoint omitted, fail
  explicitly with no traceback
- output reports the actual planner-selected station and cargo
- --old comparison has been run and recorded on the validation commands
```

## Recommended Implementation Order

```text
1. Relax validation.py: --from optional; reject both endpoints omitted;
   generalise the omitted-endpoint --jumps-per guard.
2. Rename _reachable_destination_station_ids -> _reachable_station_ids in
   data_gateway.py and update both call sites.
3. Generalise fetch_open_ended_trade_candidates: parameterise by open_role;
   assign the fixed and reachable station-id sets to the supply and demand
   queries from that parameter.
4. Generalise _best_open_destination_plan into _best_open_ended_plan(open_role);
   parameterise _raise_empty_open_search; widen the plan_onehop_route dispatch
   to three ways.
5. Manual validation vs --old, including the open-destination regression and
   the run-short benchmark to confirm the generalisation left open-destination
   behaviour identical; record dense-region timings.
```

## Non-Goals

Do not build multi-hop frontier, pruning, multi-jump reachability, the keyed
`--jumps-per` default, route shaping (`--via` / `--avoid` / `--towards` /
`--loop` / `--unique` / `--loop-interval` / `--shorten`), `--start-jumps` /
`--end-jumps`, multiple displayed routes, `--progress`, or the unanchored
both-endpoints-omitted search. Do not fold the fixed-endpoint planner into the
open-ended path — for a single hop they are genuinely different algorithms, not
duplicated code.

This slice proves one thing cleanly:

```text
The open-ended one-hop search runs from either anchored endpoint through a
single parameterised path — the open-origin search and the open-destination
search are one feature, not two.
```
