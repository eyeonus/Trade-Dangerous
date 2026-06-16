# Slice 27 — Completion Report

**`--via`: route through one or more named waypoints, on the
credit-optimistic engine with a lane-diversity frontier.**

*Completed 2026-06-16. Code commits `7338c7f7` (resolution + early
validation), `52cca992` (open-anchor seams), `b5694cd7` (the via search
owner), `a942da36` (distinct-requirement endpoint crediting), `65afa9c9`
(terminal-phase progress retention). Plan revised after audit — the
original leg-stitching design (`a580fd86`) was withdrawn.*

---

## What the slice set out to do

`--via SYSTEM|STATION` forces a run through one or more named waypoints,
in any order, on the way from origin to destination. Every waypoint must
be visited — a route that misses one is no route, not a partial result
(the `--loop` stance).

The spec sets no anchoring requirement on `--via`. We require at least
one anchor (`--from` or `--to`) as a chosen variation: a fully-unanchored
via is unbounded, and with both ends free the cheapest way to "include" a
place is just to start or finish there.

The first design committed for this slice stitched the route together
leg by leg. An audit found that approach ran exact, real-credit cargo
optimisation inside a wide beam *while the route was still hunting for
the waypoint* — branch-and-bound firing thousands of times per search. It
was withdrawn. The state model it carried was sound; only its execution
policy was wrong. The slice was rebuilt on that retained state.

## What was delivered

### Resolution and early validation

`--via` tokens resolve like the endpoints — repeated or comma-separated,
fuzzy-matched, a system or a station picked by syntax — once at dispatch.
Validation, before any search:

- Rejects `--via` with `--towards` (steering toward a single target
  contradicts threading several waypoints) and `--direct` with `--via`
  (a single fixed hop has no room for a detour).
- Requires an anchor; a fully-unanchored via is refused.
- Caps the waypoint count at six (`_MAX_CANONICAL_VIAS`) — the
  satisfaction mask and the per-mask search lanes both grow with the
  waypoint count, so the bound keeps the frontier tractable.
- Conflicts with `--avoid` when a via place — or, for a station via, its
  containing system — is also avoided.

A pinned endpoint that already sits on a via is credited against the
waypoint set by distinct-requirement matching (`a942da36`): two endpoints
on the same place cannot both claim the same waypoint, so the hop budget
is judged honestly. Shipped in `7338c7f7`, `a942da36`.

### The via search owner

A single search owner, `route_via.py` — the credit-optimistic
open-anchor backbone (`route_common._plan_open_anchor_route` primitives)
with two additions:

- **A per-chain satisfied-via mask.** Each chain carries the set of
  waypoints it has met, tagged `("system", id)` / `("station", id)`. A
  station visit satisfies both an exact-station via and its
  containing-system via. The finalist must carry the full mask.
- **A lane-diversity frontier.** A frontier entry is `(node,
  lane_target)`. A chain owing waypoints rides one lane per owed
  waypoint, collapsing to a single terminal lane once the mask is full.
  The lane label is persistent search state — set when a chain enters a
  lane, carried forward, never recomputed as "the nearest owed via this
  layer", which would quietly rebuild greedy nearest-first ordering and
  lose the orders only a non-greedy visit sequence can serve.

Expansion is optimistic (cargo fits as if money is no object, so the
greedy fast path is taken and branch-and-bound stays out of the search),
with one end-to-end credit correction on the finalists only. The trim
coalesces by `(station, mask, lane, root)`, groups into lanes, admits
coverage-first — every distinct owed-via direction gets its best root
before any direction gets a second — and reserves a per-lane fairness
floor. New seams on the open-anchor primitive (`52cca992`) carry the
unbounded-credit expansion, the station-set restriction, and the
distance/envelope steering split from ranking. Shipped in `b5694cd7`.

### Every shape

- **Fixed-terminal** (`--from` and `--to`): forward from `--from`; the
  finalist closes on a `--to` station.
- **Single-anchor open** (one end named): forward from `--from` toward an
  open destination, or backward from `--to` toward an open origin.
- **Loop** (`--from`, `--loop`): each chain closes on its own root, the
  roots qualified as real sell-back destinations before seeding.

## The terminal-phase fix

After the owner shipped, a via run to a *distant* fixed terminal still
failed: `--from sol --to achenar --via lave` raised `NoViaRoute` at 8,
10, and 12 hops, though the route is reachable and the no-via twin
succeeds.

Instrumenting the terminal lane settled the mechanism. Chains reached
the last waypoint (Lave) and then **stalled there** — the lane stayed
frozen at Lave's distance from Achenar for every later layer. The lane
*was* generating progress children that moved toward the destination;
the trim was throwing them away. The terminal lane is ranked by score,
and fresh chains arriving at Lave (completing their last waypoint that
layer) carried more accumulated profit than the chains already departing
for Achenar, so the score-ranked beam floor handed both its slots to the
fresh arrivals and re-pinned the lane to the waypoint, every layer.

The fix (`65afa9c9`): the terminal lane's floor now reserves one slot for
the chain nearest the destination — its own root, for a loop — distinct
from the score leader. The score slot still lets the terminal run take
profitable detours and fill the hop budget; the progress slot keeps the
chain actually closing on the destination alive through the trim. Exact
hop count is unchanged. Verified — `--from sol --to achenar --via lave`
now lands an 8-hop route through Lave, the terminal lane marching
174.6 → 133.8 → 87.3 → 47.3 → 7.2 ly to Achenar across the layers.

## Variances from plan

1. **The slice was rebuilt, not extended.** The committed leg-stitching
   design was withdrawn after audit and the slice rebuilt on the
   satisfied-via mask plus optimistic expansion. The revised plan records
   this; it is noted here because the shipped shape differs from the
   first plan on file.
2. **The terminal-phase progress-retention trim was added after the owner
   shipped.** It was not in the revised plan — the distant-terminal
   failure surfaced in testing, was diagnosed by instrumentation, and
   fixed. The diagnosis ruled out an "arrives early, rejected by exact-N"
   reading: no chain reached the terminal early; the terminal progress
   was generated and trimmed away. Exact-N was kept.

## Housekeeping

The temporary terminal-lane diagnostics were removed at slice close per
standing practice. Living docs updated: `SPEC_STATUS.md` (`--via` →
`[varied]`, the via-semantics / route-ranking / failure rows, a new
variation entry for the anchoring requirement), `BASELINE.md` (`--via`
done — the `route_via.py` module row, a cross-cutting behaviour entry,
removed from "still owed"), `INDEX.md` (this slice), and
`timing_baselines.md` (the first `--via` baseline alongside its
credit-bound no-via twin, which records the first case of the
real-budget branch-and-bound path firing at scale).
