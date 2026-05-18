# Trade Run Third Slice — Completion Report

## Status

Third slice implementation is complete within the agreed scope and pushed.

Slice name:

```text
Open-Ended One-Hop Search
```

Repository: Tromador/Trade-Dangerous
Branch: release/v1

---

## Purpose

This slice extends one-hop planning to the case where the destination is not
named. With `--from` supplied and `--to` omitted, the planner selects the
destination itself: it finds the best one-hop trade from the fixed origin to
any reachable station.

The supported planning shape is now:

```text
trade run
  --from <station|system>
  [--to omitted]
  --capacity N
  --credits N
  --hops 1
  --jumps-per 0|1
  --ly-per N
```

The fixed-endpoint shapes from Slices 1 and 2 remain supported unchanged.

---

## Scope Completed

### Dispatch

`plan_onehop_route` branches on whether `--to` was supplied:

- `--to` present: the Slice 1/2 fixed-endpoint path (`_plan_fixed_endpoints`).
- `--to` omitted: the open-ended destination search
  (`_best_open_destination_plan`).

Result construction shared by both paths is factored into `_assemble_result`.

### Open-ended destination search

The destination station set is resolved by staged spatial narrowing, so the
spatial filter always runs before any market-table access:

1. A bounding box on the indexed `System.pos_x/pos_y/pos_z` columns, refined
   by an exact squared-distance test (`<= L*L`, no square root), yields the
   in-range system ids.
2. Those system ids drive the station-attribute filter down to the reachable
   destination station ids.
3. Only then is the market table queried.

`--jumps-per 0` restricts the search to the origin's own system; `--jumps-per
1` admits every system within a single loaded jump. Multi-jump open-ended
search is not supported and is rejected by validation.

### Market query shape

The candidate query fetches origin supply rows and destination demand rows as
two separate single-table queries, each driven by its station-id set through
the `StationItem` primary key, then matches them on `item_id` in Python.

A single SQL self-join was tried first and rejected: it lets SQLite reach the
market table by the `item_id` index and scan it galaxy-wide for a common
commodity, rather than by the station-id set. This produced a `--pad-size S`
pathology of about 154 seconds. The split query holds every table access on
the primary key and brought the same search to about 3 seconds.

### Destination demand floor

`_MIN_MEANINGFUL_DEMAND = 2`. A destination market row counts only when its
`demand_units` is 2 or more. A station that stocks and sells a commodity still
carries a nominal demand of 0 or 1 for it — the dormant buy side, copied
verbatim from the source market data. Treating that as a real buyer caps cargo
at one tonne and produces noise routes. The floor applies to the open-ended
query, the fixed station-pair query, and its zero-result failure
classification.

### Unknown-pad admission

A station whose largest pad size is unrecorded (`?`) is admitted whenever the
`--pad-size` threshold accepts a medium pad — under `--pad-size S`,
`--pad-size M`, or no `--pad-size` — and excluded only under `--pad-size L`.
This is a deliberate, accepted risk; the reasoning and the conditions for
revisiting it are recorded in SLICE_SUMMARY (Filter Semantics — Pad size).

### `--jumps-per` default

The `--jumps-per` default changes from 2 to 1.

---

## Verified Behaviour

### Route comparison

Validation tranches A–E and the run-short Colonia benchmark were spot-checked
against `trade run --old`.

- Routes match `--old` where the two planners' filter models are comparable.
- The run-short benchmark returned a byte-identical route and cargo split.
- The notable divergence: on an open-ended Sol search, `--old` selected a
  higher-value trade to a station whose `demand_units` for the commodity was
  1. That station stocks and sells the commodity; the demand of 1 is its
  dormant buy side, not a real buyer. The new planner correctly declines the
  trade. `--old` does not, and so reports an unfillable route.

### Performance

- Open-ended one-hop search returns in roughly 3 seconds where `--old` takes
  7 to 30 seconds for the comparable query.
- The `--pad-size S` pathology (about 154 seconds, caused by the self-join
  query shape) was diagnosed and removed; see Scope Completed.

### Pad-size model

`--pad-size L` excludes unknown-pad stations; `--pad-size M` and `--pad-size S`
admit them. `--pad-size L` is correctly the most restrictive threshold and was
verified to drop a medium-pad origin that the looser thresholds keep.

---

## Quarantine Status

Intact.

```text
tradedangerous/tradecalc.py
tradedangerous/tradedb.py
```

Neither module was opened or used as an implementation source. `trade run
--old` remains the comparison path only.

---

## Outstanding / Deferred

Deferred, not cut. These must reach the new planner before `--old` is retired
at v13:

- an omitted `--from`
- both endpoints omitted
- multi-jump open-ended search (`--jumps-per >= 2` with `--to` omitted)

Noted for a later slice:

- `--jumps-per` default keyed to `--ly-per` — see SLICE_SUMMARY Deferred
  Decisions; earmarked for Slice 4.
- the `--pad-size` CLI parser message mismatch — see SLICE_SUMMARY Cleanup
  Candidates.

---

## Commits

On `release/v1`:

```text
8e19b9bd  fix(planner): require meaningful demand for a destination market
fdc8fe9e  feat(planner): admit unknown-pad stations below a large-pad threshold
e9ed4c45  feat(planner): add open-ended one-hop destination search
```

---

## Assessment

The open-ended one-hop search is delivered, validated against `--old`, and on
the branch. One-hop planning now covers fixed station-to-station, system
endpoint expansion, and open-ended destination selection. The remaining
one-hop gap is an omitted `--from`; multi-hop routing is the larger body of
work still ahead.
