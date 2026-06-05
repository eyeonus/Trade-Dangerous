# Slice 17 — Progress-toward-a-target routing (`--towards`) — Completion Report

## Status

Complete. `--towards` is live and verified against live data. The slice carried a
mid-build design correction (recorded below and in the implementation plan); the
delivered behaviour follows the corrected design without further deviation.

## What was delivered

`--towards SYSTEM` — a route modifier that steers an open-destination route
toward a target system without forcing arrival. It requires `--from` and is
mutually exclusive with `--to`. Every trade hop must land strictly closer to the
target than the previous trade position (or reach it), and among the hops that
comply the route heads **directly** at the target: ranking is progress-first —
closest wins, then fewer hops, and profit only breaks the remaining tie. A hop
that reaches the target ends the route, reported as "arrived after N hops"; if
the hops run out first the route gets as close as it can.

This is distinct from `--to`: `--to` fixes the final station and the route must
arrive there; `--towards` only points the route and stops if and when it gets
there.

## The mid-build correction

The first build treated the spec's "a route MAY optimise profit among
forward-progress candidates" as the ranking objective: it kept the strict-progress
filter but then chose the most *profitable* compliant hop. On a Sol → Lave run
that produced a profit-led meander that parked one system short of the target and
burned every hop.

Read with the spec's requirement keywords (RFC 2119 / BCP 14), the wording is
unambiguous: "each hop **MUST** move closer" is an absolute requirement; "a route
**MAY** optimise profit" is an optional permission that cannot override the MUST
or the stated "move toward, not meander" intent. So progress is the ranking and
profit is only a tie-breaker among already-compliant hops. The legacy `--towards`
goal scoring was reviewed once, with explicit authorisation for that named
purpose, and confirmed the reading — distance-reduction to the goal was the
dominant term, profit a small nudge. The new engine uses a clean progress-first
ordering (closest, then fewer hops, then profit) rather than copying the legacy
weights.

## How it was built

Five steps, reviewed one at a time.

1. **Gate + validation.** Dropped `--towards` from the "unsupported" lists in the
   parser (`run_cmd.py`) and `validation.py`. Kept the existing `--towards`
   requires `--from` check; added the `--towards` + `--to` rejection ("specify
   one or the other").
2. **Target resolution + the progress filter (the MUST).** `--towards` resolves
   once at dispatch to a target system (id + coordinates) via the existing
   resolver — a station name collapses to its parent system — and rides on the
   request as canonical state (`towards_target` on `RunRequest`). The
   strict-progress filter goes in at the single shared open-destination candidate
   fetch (`_reachable_station_query` in `data_gateway.py`) as a sphere predicate:
   a candidate destination system must be strictly closer to the target than the
   anchor (this hop's previous position), or be the target system itself. It
   reuses the existing bbox + squared-distance prefilter shape and stays entirely
   SQL-side. With no target the query is byte-for-byte as before.
3. **Failure path.** `NoTowardsProgress` (a `NoReachableRoute` subclass). When an
   open-destination search yields nothing under the progress constraint, dispatch
   re-raises in this family naming the target; the command layer renders a
   message that names the target and suggests the levers (`--hops`,
   `--jumps-per`, `--ly-per`, filters). Non-towards runs are unaffected.
4. **Progress-first ranking + arrival capture (the MAY, corrected).** One shared
   rank — `_node_progress_rank` / `_route_progress_rank` /
   `_candidate_progress_rank` in `route_common.py` — keyed on the canonical
   target. Under `--towards` it ranks closest → fewer hops → profit; with no
   target it returns a one-tuple of the profit score, so every existing sort and
   comparison is identical. It is applied at each selection point the engines
   already own: the per-node top-K, the per-layer frontier trim, the finalist
   sort, the correction early-stop and winner pick, the partial-route pick, and
   the one-hop pair pick. **Arrival capture:** a chain that lands in the target
   system can extend no further (nothing is closer), so the beam would discard
   it; the engine now collects such chains and folds them into the final
   selection, where an arrival (distance zero, fewest hops) wins.
5. **Arrival reporting.** `PlannedRoute` gained an optional `arrival_hops` field;
   dispatch flags any route whose last station is in the target system with its
   hop count (`_annotate_towards_arrival`, computed once after the winning route
   exists, so neither engine owns the check), and the renderer prints "Arrived at
   <system> after N hops".

## Architecture compliance

The meaning of `--towards` is resolved once into canonical request state and
consumed in two shared places: the MUST filter at the candidate-fetch seam, and
the MAY ranking via one shared rank helper applied where the engines already
select. No route engine grew its own towards semantics or its own progress
comparison; the engines differ only in their search strategy, which is untouched.
Arrival detection lives once in dispatch, alongside the empty-positioning legs,
not in any engine.

## Verification

- **Live spot-check (the headline).** `--from "sol" --towards "Lave/Lave Station"
  --hops 3 --jumps-per 3 --ly-per 30 --fc N --pad-size L --planetary N --age 10`
  routed Sol → Delkar → Lave and reported "Arrived at Lave after 2 hops" — direct,
  arrived, and stopped with a hop to spare. The final hop into Lave was a modest
  601 cr/t trade, taken in preference to a richer trade that would have missed the
  target: progress first, profit only a tie-breaker.
- **Regression.** A no-`--towards` open-destination run was confirmed unchanged,
  consistent with the rank collapsing to the prior profit key when no target is
  set.
- **Ranking logic.** The lexicographic order (closest beats profit; fewer hops
  beats more at equal distance; profit breaks the final tie; an arrival beats any
  non-arrival; a shorter arrival beats a longer one; no-towards is pure profit)
  was checked directly against the rank helpers.
- **Static checks.** `flake8` and `py_compile` clean on all touched files
  (`run_cmd.py`, `validation.py`, `run_request.py`, `data_gateway.py`,
  `run_route.py`, `failures.py`, `route_common.py`, `route_onehop.py`,
  `run_result.py`, `render_text.py`).

## Documentation updated

- `SPEC_STATUS.md` — `--towards` and the "towards mode" row moved to `[done]`;
  the route-ranking row notes the progress-first ordering; a sixth deliberate
  variation records the `--towards`/`--to` exclusion and the MUST/MAY reading.
- `BASELINE.md` — `--towards` added to "what works now"; removed from the modifier
  list in "what's still owed".
- `INDEX.md` — Slice 17 entry added.
