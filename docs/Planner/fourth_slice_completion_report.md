# Trade Run Fourth Slice — Completion Report

## Status

Fourth slice implementation is complete within the agreed scope. The planner
code is committed and pushed (`release/v1`, `cd57399b`); this report and the
`SLICE_SUMMARY.md` update are the closing record.

Slice name:

```text
Open-Ended Origin Search
```

Repository: Tromador/Trade-Dangerous
Branch: release/v1

---

## Purpose

This slice extends one-hop planning to the case where the *origin* is not
named. With `--to` supplied and `--from` omitted, the planner selects the
origin: the best reachable station from which to trade into the supplied
destination.

Slice 3 delivered the open-ended *destination* search. Rather than add a
second, parallel search for the origin, Slice 4 generalises the Slice 3 search
to run from either anchored endpoint through one parameterised path. The
open-ended destination search becomes one case of it.

Supported one-hop shapes are now:

```text
--from station   fixed origin station
--from system    expand to eligible origin stations
--from omitted   planner selects the origin            (this slice)
--to   station   fixed destination station
--to   system    expand to eligible destination stations
--to   omitted   planner selects the destination       (Slice 3)
```

At least one of `--from` / `--to` must be supplied. The one-hop family is now
complete but for the genuinely unanchored search — both endpoints omitted —
which remains deferred.

---

## Scope Completed

### Endpoint dispatch

`plan_onehop_route` dispatches three ways:

- both endpoints supplied — the fixed-endpoint station-pair matrix
  (`_plan_fixed_endpoints`), unchanged;
- one endpoint omitted — the open-ended search, `_best_open_ended_plan`,
  parameterised by `open_role` (the trade role of the endpoint the planner
  selects: `"source"` or `"destination"`);
- both omitted — rejected in validation.

### The unified open-ended search

`_best_open_destination_plan` is generalised into `_best_open_ended_plan`,
keyed on `open_role`. Only the fixed-endpoint derivation reads `open_role`;
endpoint resolution, the candidate query, pair evaluation, scoring, and result
assembly are direction-agnostic. The fixed-side and open-side station DTOs
merge into one `station_id -> ResolvedStation` map, so the pair loop resolves
either side of a pair without a direction branch.

`fetch_open_ended_trade_candidates` is generalised the same way: `open_role`
assigns the fixed station set and the spatially-reached set to the supply and
demand queries. `_raise_empty_open_search` is parameterised so its no-trade
and no-route messages name the anchored endpoint correctly.

### Validation

`--from` is no longer required. Validation rejects the both-omitted shape
(`UnsupportedRunShape`, "Either --from or --to must be supplied."), and the
omitted-endpoint `--jumps-per` guard now applies to whichever endpoint is
omitted.

### Reachable-station query shape

The dense-region validation command — `trade run --to "Sol"` with no station
filters — exposed a candidate query that did not scale. The open-ended query
constrained `StationItem.station_id` with a station-id list materialised into
Python from the spatial query, then handed back as a literal `IN (...)`.

For a sparse region that list is short and SQLite plans the query on the
`StationItem` primary key. For a dense region the list runs to thousands of
ids, and a large literal `IN (...)` makes SQLite abandon the primary key for
`ANY(item_id)` — a full traversal of a commodity-keyed index, galaxy-wide.
That is millions of page reads; `trade run --to "Sol"` ran for minutes
without completing.

The fix keeps the reachable station set in SQL. `_reachable_station_ids`,
which returned a materialised id tuple, became `_reachable_station_id_query`,
which returns a `Select`; the candidate query composes it with
`.in_(<subquery>)`. SQLite then holds the primary-key plan — `EXPLAIN QUERY
PLAN` confirms `SEARCH StationItem USING PRIMARY KEY`. The fixed endpoint is a
single named place, small by construction, so its id list is still passed
directly; the asymmetry is deliberate.

---

## Verified Behaviour

### Routes

The new omitted-`--from` shape was exercised for a station `--to`, a system
`--to`, and `--jumps-per 0`; all return valid one-hop routes. The open-ended
destination shapes from Slice 3 were re-run after the query-shape change and
are unchanged — the generalisation is behaviour-preserving. The both-endpoint
shapes from Slices 1-2 and the run-short Colonia benchmark are unaffected.

### Failure behaviour

- both `--from` and `--to` omitted -> `UnsupportedRunShape`, no traceback,
  message "Either --from or --to must be supplied.";
- an endpoint omitted with `--jumps-per 2` -> `UnsupportedRunShape`, no
  traceback.

### Performance

`trade run --to "Sol"` — the densest region, unfiltered — returns in about
2.5 seconds; with station filters such as `--fc N --pad-size L` it is faster
still. Before the query-shape fix the same command did not complete in any
reasonable time. See Scope Completed — Reachable-station query shape.

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

- both `--from` and `--to` omitted — the genuinely unanchored galaxy search;
- multi-jump per-hop reachability (`--jumps-per >= 2`);
- the `--jumps-per` default keyed to `--ly-per` — it depends on the planner
  being able to fly a 2-jump hop, which multi-jump reachability has not yet
  delivered. See `SLICE_SUMMARY.md` Deferred Decisions.

---

## Commits

On `release/v1`:

```text
cd57399b  feat(planner): add open-ended one-hop origin search
```

---

## Assessment

One-hop planning now covers fixed station-to-station, system-endpoint
expansion, open-ended destination selection, and open-ended origin selection,
through one open-ended search rather than two. The dense-region scaling
failure surfaced by the `--to "Sol"` validation command was traced to the
open-ended candidate query's plan and fixed by keeping the reachable station
set in SQL. The remaining one-hop gap is the unanchored both-endpoints-omitted
search; multi-hop routing is the larger body of work still ahead.
