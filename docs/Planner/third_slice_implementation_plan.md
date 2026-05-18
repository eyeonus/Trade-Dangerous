# trade run Third Slice Plan — Open-Ended One-Hop Search

## Purpose

Extend the completed one-hop planner so a single hop can be planned when the
destination endpoint is left open.

Slices 1–2 required both `--from` and `--to`, and kept every query bounded to
explicitly named systems. This slice introduces the planner's first open
search: from a fixed origin, find the best one-hop trade to any reachable
station, using SQL-side spatial narrowing.

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

Permitted implementation sources:

```text
- black-box trade run behavioural specification
- first and second slice implementation plans and completion reports
- this plan
- the current planner package
- ORM models and resolver surfaces
- public command parser metadata
- local_cmd.py as the reference spatial-query pattern
- official Python / SQLAlchemy / database documentation
```

## Slice Name

```text
Open-Ended One-Hop Search
```

## Goal

Support one-hop planning where `--from` is supplied and `--to` is omitted.

The supplied origin may be a station or a system (Slice 2 behaviour,
unchanged). The omitted destination is filled by the planner as the best
reachable station, bounded by single-jump reachability from the origin
system.

## Design Constraint — Anchored Search Is Primary

This constraint governs every decision in this slice and protects against
the failure mode of the legacy planner, which front-loads the database and
filters in Python on every invocation.

```text
- The anchored search (fixed origin, spatial narrowing) is the primary
  design target. It must be optimal in isolation.
- The future unanchored search (omitted --from, or both endpoints omitted)
  is deferred. When built, it must be a separate, additive query path.
- The anchored path must never be re-expressed as a special case of a
  general galaxy scan, and the unanchored path must never be implemented
  by relaxing or parameterising the anchored path into a generic scanner.
- No speculative generality in this slice: no mode flags, no parameters,
  and no hooks anticipating the unanchored case.
- If a shared abstraction is ever warranted, it must be extracted from the
  proven fast path — discovered, not imposed top-down.
```

Sequencing enforces this: the anchored path is built and shipped first, so
the later unanchored slice has nothing to generalise from and is forced to
be separate.

## Supported Command Shapes

Continue supporting every Slice 1–2 shape (both endpoints supplied). Add:

```text
trade run --from "<station|system>"   [--to omitted]   --capacity N --credits N --hops 1 --ly-per N
```

Endpoint meanings:

```text
--from station   fixed origin station
--from system    expand to eligible origin stations in that system
--to   station   fixed destination station            (Slice 1-2)
--to   system    expand to eligible destination stations (Slice 2)
--to   omitted   planner selects the destination from reachable stations
```

Still `--hops 1` and `--routes 1`.

`--from` is required for this slice. With the new `--jumps-per` default of 1
(see below), the omitted-`--to` shape works without the user supplying
`--jumps-per` explicitly.

## Still Out of Scope

```text
- omitted --from                          (deferred, not cut — see roadmap note)
- both --from and --to omitted            (deferred, not cut — see roadmap note)
- --jumps-per >= 2 with --to omitted       (multi-jump reachability — later slice)
- --hops > 1, --start-jumps, --end-jumps
- --direct, --towards, --via, --avoid, --loop, --unique, --loop-interval, --shorten
- --routes > 1, --checklist, --x52-pro
- multi-hop search, route frontier, pruning
- bookending / meet-in-the-middle search  (a multi-hop search strategy)
```

Unsupported shapes must continue to fail explicitly when the new planner
path runs.

## Default Change — `--jumps-per`

The `--jumps-per` argument default is reduced from 2 to 1 in
`tradedangerous/commands/run_cmd.py` (the `ParseArgument('--jumps-per', ...,
default = 2, ...)` becomes `default = 1`).

Rationale: the default of 2 was set when ship jump ranges were much shorter.
Current ship technology makes a 2-jump-per-hop default unnecessary; players
who want it can still pass `--jumps-per` explicitly.

Notes:

```text
- One-line change. The argument help text does not state a default, so no
  help-text edit is needed in code. The project wiki states 2 and will need
  updating separately.
- The argument is shared by both planner paths, so this also changes the
  --old legacy path default. This is intended: the rationale is a
  game-reality argument, not a new-planner argument.
- The change lands on the refactor branch and ships with version 13. Live
  is a separate branch and is unaffected.
- The benchmark corpus is unaffected: those commands pass --jumps-per
  explicitly.
```

## Filter Change — `--pad-size` Threshold Model

`--pad-size` is reworked from an accepted-size set into a ship-fit threshold.
This is a deliberate `--pad-size` contract change, folded into this slice
because it touches the same files as the open-ended-search work
(`validation.py`, `data_gateway.py`) and the planner's station-filter path.

Model:

```text
--pad-size takes one ship pad size — S, M, or L — meaning "the ship needs at
least this pad". A station qualifies when its largest pad is at least that:
  L  ->  large-max stations only
  M  ->  medium- or large-max stations
  S  ->  small-, medium- or large-max — effectively no filter
```

Rules:

```text
- `?` is not a valid input. `--pad-size ?`, `--pad-size M?`, and any
  multi-letter value are rejected with a validation error.
- A station whose own max pad size is unknown is never eligible: it is
  dropped by an always-on station-eligibility predicate, whether or not
  --pad-size was given — a guardrail against routing a ship somewhere it
  cannot land. A named station with an unknown pad therefore fails as an
  ineligible station; the silent drop applies only to set-based queries.
- The earlier accepted-set behaviour, including the "exclude large
  starports" use case, is not carried over. Full rationale is in
  docs/Planner/tuples.md.
```

The change is entirely planner-side: the CLI parser (`PadSizeArgument`) and
the `--old` path are not touched, since the planner already re-interprets
`cmdenv.padSize` past the `RunRequest` boundary.

Deferred: the CLI help text and its `SML?` example need updating to match —
a follow-up, outside the planner.

## Behavioural Requirements

### Endpoint roles

The orchestrator inspects `request.to_text` for empty/`None`. When present,
both endpoints are fixed and the existing Slice 1–2 path runs unchanged.
When absent, the destination is open and the new path runs. `request.from_text`
is always present (validation enforces it).

### Fixed origin resolution

Reuse `resolver.resolve_endpoint` and `_stations_from_endpoint` for the
origin only. The omitted destination is never passed to the resolver.

A fixed origin resolves to exactly one **anchor system** (a station endpoint
→ its system; a system endpoint → itself) and a fixed origin-station set
(one station, or eligible stations in that system). Existing origin-side
failures (`SourceStationIneligible`, etc.) are reused unchanged.

### Reachable-station spatial query — the new core

The open destination set is the stations in systems reachable from the
anchor system in a single loaded jump. The query narrows spatially in SQL
before any market join (the `local_cmd.py` pattern):

```text
1. anchor system coords (ax, ay, az); reach radius L = max_ly_per_jump
2. bounding box (index-using coarse filter):
     System.pos_x BETWEEN ax-L AND ax+L
     System.pos_y BETWEEN ay-L AND ay+L
     System.pos_z BETWEEN az-L AND az+L
3. exact refinement, still SQL-side, no sqrt:
     (pos_x-ax)^2 + (pos_y-ay)^2 + (pos_z-az)^2 <= L*L
4. station-attribute filters (market != 'N', pad size, planetary, no-planet,
   black-market, max-ls, fleet-carrier, settlement) applied in the same
   statement
```

For `--jumps-per 0`, restrict the open side to the anchor system only
(same-system supercruise; squared distance `= 0`). For `--jumps-per 1`, use
the full radius. `--jumps-per >= 2` with `--to` omitted is rejected in
validation.

### Open-ended trade candidate generation

One bulk, spatially bounded query produces all candidate trades across the
fixed origin-station set × the open reachable destination set:

```text
- origin side (small): source_item.station_id IN (fixed origin station ids)
- destination side:     destination_item joined to Station + System,
                        carrying the bounding-box + squared-distance +
                        station-attribute predicates inline
                        (NOT a Python-side id list)
- joined on item_id, plus the existing per-trade filters used by
  fetch_station_pair_candidates:
    positive source supply price and units
    positive destination demand price and units
    (demand_price - supply_price) within the gain-per-ton range
    min-supply, min-demand, age cutoff where supplied
    source supply_price <= available credits (affordability of one unit)
```

Returns `tuple[TradeCandidate, ...]` with both `source_station_id` and
`destination_station_id` populated. The destination-side filters live in
this query, so every surviving candidate's destination station has already
passed station-attribute filtering.

The destination-side `ResolvedStation` DTOs (needed for distance penalty
scoring and for output names) are fetched only for the distinct destination
station ids that actually appear in candidates. Reachable stations with no
profitable trade are never materialised — consistent with the data-scale
note: do not load known-dead rows into planner space.

### Station-pair evaluation and selection

Group candidates by `(source_station_id, destination_station_id)`. For each
pair:

```text
1. skip self-pairs (source_station_id == destination_station_id)
2. run the existing optimise_cargo
3. score with score_with_destination_penalty using the destination
   station's ls_from_star
4. retain the best pair via the existing _pair_is_better
   (practical score, raw profit tie-break)
```

This mirrors the Slice 2 `_best_pair_plan` selection logic, but the
candidate set comes from one bulk query instead of a per-pair query inside
an N×M loop.

### Reachability

The spatial query is itself the reachability filter for the open side, so
per-pair `plan_jump_path` calls are not used for filtering. `plan_jump_path`
is called exactly once — for the winning pair — to build the `JumpPath` for
output. Same-system pairs are reported as supercruise.

### Cargo

Unchanged. The first-slice cargo optimiser and all its constraints
(capacity, credits minus insurance reserve, per-item limit, source supply,
destination demand as a hard cap, positive profit under gain filters, exact
total cost/profit arithmetic) continue to apply per pair.

### Output

No renderer change expected — the selected route already carries concrete
source and destination `ResolvedStation` objects, and Slice 2 already
renders planner-selected stations. Verify only that output reads sensibly
when the user did not name the selected destination.

## Failure Requirements

Reuse the existing failure taxonomy — no new failure classes are needed:

```text
- origin unknown / ambiguous              -> existing resolver failures
- origin system has no eligible stations  -> SourceStationIneligible
- no reachable stations in range          -> NoReachableRoute
- reachable stations but no profitable trade -> NoProfitableTrades
- profitable trades but no affordable cargo  -> NoAffordableCargo
- --from omitted (this slice)             -> MissingRequiredInput (--from)
- --jumps-per >= 2 with --to omitted       -> UnsupportedRunShape
- --pad-size ? / multi-letter / invalid    -> InvalidRunRequest
```

All map cleanly through the existing `run_cmd.py` exception handling.
Expected planner failures must not emit tracebacks. Open-ended failure
granularity is intentionally coarse — one aggregate reason — consistent with
the multi-hop diagnostic-granularity note.

## Suggested Internal Shape

Concrete, minimal-scope change set:

```text
commands/run_cmd.py
  - ParseArgument('--jumps-per', ...): default 2 -> 1

planner/run_request.py
  - replace the pad_size_filter tuple field with a single raw --pad-size
    value on RunRequest; normalisation only strips/uppercases and does not
    silently discard bad input, so validation can error on it

planner/validation.py
  - keep _require_present(from_text, "--from")
  - remove _require_present(to_text, "--to"); --to is now optional
  - add: to_text empty/None AND max_jumps_per_hop not in (0, 1)
         -> UnsupportedRunShape
  - replace the SL-combination guard with the pad-size threshold check:
    --pad-size must be None or exactly one of S / M / L; ?, multi-letter
    values, and anything else -> InvalidRunRequest
  - the both-endpoints-fixed path keeps current behaviour (no scope widening)

planner/data_gateway.py
  - add System to the orm_models import
  - extract the station-attribute predicates out of _station_filter_predicates
    (everything except the Station.system_id pin) into a reusable helper;
    fetch_eligible_stations_in_system composes the system pin + that helper
  - add a bounding-box + squared-distance predicate helper over System
  - add fetch_open_ended_trade_candidates(session, fixed_origin_station_ids,
        anchor_system, request) -> tuple[TradeCandidate, ...]
  - add fetch_stations_by_id(session, station_ids) -> dict[int, ResolvedStation]
  - pad size: expand the required size to its qualifying set (S -> no filter,
    M -> {M,L}, L -> {L}) for the station predicate and _pad_size_matches;
    add an always-on baseline predicate excluding stations whose max pad size
    is not S / M / L, and apply the same exclusion in validate_station_filters

planner/run_onehop.py
  - plan_onehop_route dispatches on whether to_text is present:
      present -> existing _best_pair_plan path
      absent  -> new _best_open_destination_plan path
  - _best_open_destination_plan: resolve origin -> bulk candidate query ->
    fetch destination station DTOs -> per-pair cargo/score -> best route ->
    single plan_jump_path call for the winning pair -> assemble RunResult

unchanged: resolver.py, cargo.py, score.py, reachability.py,
           render_text.py, run_result.py, failures.py
```

No `fixed_role` or direction parameter is introduced —
`fetch_open_ended_trade_candidates` is fixed-origin / open-destination only.
The mirrored open-origin query is a purely additive change for the later
unanchored slice and is deliberately not built here.

## Data Access Guidance

```text
- The spatial query is the first planner query not bounded to a named
  system. It MUST narrow via the System bounding box before touching
  StationItem. A StationItem-first scan is wrong at ~19M rows.
- Verification step (not an assumption): confirm an index supports the
  System.pos_x/pos_y/pos_z bounding-box predicate. local_cmd.py relies on
  the same shape; check the index covers this query.
- Use squared distance (<= L*L) in SQL. No sqrt. No Python-side distance
  filtering.
- Two round trips (candidate query, then fetch_stations_by_id for the
  surviving destination ids) is the lean default. If a dense-region command
  measures slow on the second trip, a single denormalised query carrying
  station + system columns is the fallback — decide on measurement, not
  speculation.
- candidate_trade_count and the existing PlannerDiagnostics timing fields
  are reused; no new diagnostics fields are added.
```

## Manual Validation

No automated test harness — per supervisor direction, the new path is
spot-checked against `--old` while results remain comparable. Run each
command on the new path and with `--old`, and compare route validity and
profit (the legacy path supports omitted `--to`, so it is a usable
baseline):

```text
trade run --from "Lave/Lave Station"  --capacity 64 --credits 1000000 --hops 1 --ly-per 20
trade run --from "Lave"               --capacity 64 --credits 1000000 --hops 1 --ly-per 20
trade run --from "Lave/Lave Station"  --capacity 64 --credits 1000000 --hops 1 --jumps-per 0 --ly-per 20
```

Regression checks (must still behave as Slice 1–2):

```text
- all both-endpoint shapes (station/system combinations)
- the run-short Colonia benchmark
- unsupported-shape and unknown-endpoint failures, no traceback
```

Also exercise one dense-region command (for example `--from "Sol"` with
`--to` omitted) to measure the spatial query where systems are densest.
Record rough manual timings.

## Performance Expectations

```text
- Fixed-endpoint shapes remain at Slice 1-2 speed (unchanged path).
- Open-ended search is bounded by the single-jump reach radius, not the
  galaxy. It should stay quick in ordinary regions; dense regions are the
  case to measure.
- Per-pair cargo optimisation count is bounded by pairs-with-candidates.
  If a dense region produces an excessive pair count, a future slice can
  pre-rank pairs by a cheap upper bound before full optimisation. Out of
  scope here — note it only if measurement shows it matters.
```

## Deferred Work — Roadmap Note

`omitted --from` and `both endpoints omitted` are deferred, not cut. The
legacy `--old` path supports them today, but `--old` is a temporary
comparison path that is retired at version 13. Any capability the new
planner does not cover by then is genuinely removed. The unanchored search
family is therefore a required future slice, not optional, and must be built
as a separate additive path per the design constraint above. `--progress`
is the spec's mechanism for long-running search feedback and has a natural
home in that slice.

## Completion Criteria

```text
- omitted --to works for both a station --from and a system --from
- both-endpoint Slice 1-2 behaviour is unchanged
- the destination side is narrowed by SQL spatial predicates, not
  Python-side filtering
- the best valid one-hop pair is selected; self-pairs are excluded
- the cargo plan obeys all first-slice cargo constraints
- --from omitted, and --jumps-per >= 2 with --to omitted, fail explicitly
  with no traceback
- output reports the actual selected destination station and cargo
- --jumps-per default is 1
- --pad-size is a ship-fit threshold: M includes L, S is effectively no
  filter, ? and multi-letter input are rejected, unknown-pad stations are
  never eligible
- --old comparison has been run and recorded on the validation commands
```

## Recommended Implementation Order

```text
1. Change the --jumps-per default to 1 in run_cmd.py.
2. Relax validation.py: --to optional; reject --jumps-per >= 2 with --to
   omitted.
3. Refactor data_gateway station-attribute predicates into a reusable
   helper.
4. Apply the --pad-size threshold model: RunRequest field + normalisation
   (run_request.py); the pad-size validation check replacing the SL guard
   (validation.py); the qualifying-set expansion and the always-on
   unknown-pad exclusion (data_gateway.py).
5. Add the bounding-box + squared-distance predicate helper.
6. Add fetch_open_ended_trade_candidates.
7. Add fetch_stations_by_id.
8. Add _best_open_destination_plan and the dispatch in plan_onehop_route.
9. Single plan_jump_path call for the winning pair; assemble RunResult.
10. Manual validation vs --old; record timings including one dense-region
    command; spot-check --pad-size S / M / L behaviour.
```

## Non-Goals

Do not build multi-hop frontier, pruning, multi-jump reachability, route
shaping (`--via` / `--avoid` / `--towards` / `--loop` / `--unique` /
`--loop-interval` / `--shorten`), `--start-jumps` / `--end-jumps`, multiple
displayed routes, bookending, or unanchored galaxy search.

This slice proves one thing cleanly:

```text
The new planner can run an SQL-bounded open-ended one-hop search from a
fixed origin and select the best valid destination pair, without touching
quarantined route-planning internals and without compromising the anchored
query for the sake of a future unanchored use case.
```
