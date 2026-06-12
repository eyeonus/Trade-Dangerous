# Beam Width — Value versus Time Analysis

*Measured 2026-06-12. Decision: both beam widths stay at 50.*

This document stands alone: everything needed to understand, judge, or
re-run the analysis is here. It records the only end-to-end measurement
of the planner's beam widths to date, and the decision taken on it.

---

## What the beams are

The multi-hop route search is a beam search: at each hop layer it keeps
only the best partial routes and discards the rest. Two constants in
`tradedangerous/planner/route_common.py` set how much survives:

- `_MULTIHOP_EXPANSION_WIDTH` — how many candidate next-hops each
  partial route may generate (per-node fan-out).
- `_MULTIHOP_FRONTIER_WIDTH` — how many partial routes are carried
  forward into the next layer, after a system-diversity trim.

Both are 50. `route_anchored.py` and `route_unanchored.py` import them
at module load, so an experiment must override the binding in all three
modules, not just `route_common`.

A beam search is a heuristic: it does not examine every possible route,
so a wider beam can find better routes at proportionally higher cost,
and a narrower one is faster but can miss winners. The question this
analysis answers: **what does the route-value versus wall-time curve
actually look like as the beam narrows and widens?**

The only prior evidence was indirect: a one-seed, hop-1 probe (2026,
route-shape build-out) that checked the *score curve* of candidates at
a single layer — whether the 50th-best candidate was still a real trade
(it was, at ~40% of #1). That established 50 keeps no junk; it said
nothing about what wider beams might find. No end-to-end sweep had ever
been run.

## Method

Both constants set to the same value per run — 10, 25, 50 (baseline),
100, 200 — one planner invocation per width, one process per run, on
three shapes:

```text
mid    trade run --from sol --hops 3 --jumps 2  --capacity 720 --credits 200000000 --ly-per 30
worst  trade run --from sol --hops 6 --jumps 2  --capacity 720 --credits 200000000 --ly-per 30
fc N   worst + --fleet-carrier N   (the realistic-economy control)
```

Single database snapshot throughout (same day, no importer running, no
`--age`). Engine state: the bound-ordered streaming fetch with the
provable early stop and the qualify-once cache — i.e. the production
engine as of commit `dcda7bac`. Value is the winning route's final
cumulative profit as printed in the route output; time is process wall
clock (≈1s of which is interpreter/database startup).

To reproduce: set the width on all three module bindings before
planning, e.g. in a wrapper script —

```python
from tradedangerous.planner import route_anchored, route_common, route_unanchored
for module in (route_common, route_anchored, route_unanchored):
    module._MULTIHOP_EXPANSION_WIDTH = WIDTH
    module._MULTIHOP_FRONTIER_WIDTH = WIDTH
import trade
trade.main(["trade", "run", ...])
```

Remember route values drift with every data refresh — the *shape* of
the curves is the durable result, not the credit figures.

## The data

| width | mid (open) | worst (open) | worst (`--fc N`) |
|---|---|---|---|
| 10  | 11.0s / 72.1M  | 14.2s / 87.4M   | 12.2s / 50.6M  |
| 25  | 15.1s / 72.1M  | 26.7s / 132.0M  | 26.0s / 57.1M  |
| 50  | 26.8s / 72.1M  | 57.7s / 375.3M  | 48.3s / 84.0M  |
| 100 | 49.5s / 107.1M | 111.3s / 456.3M | 93.0s / 84.2M  |
| 200 | 114.7s / 137.8M | 258.8s / 456.3M | 207.7s / 103.3M |

Cells are `wall time / final route profit` (M = millions of credits).

```text
profit, as a share of that shape's best measured        wall
mid (open)
  w10   ██████████··········   72.1M                    11.0s
  w25   ██████████··········   72.1M                    15.1s
  w50   ██████████··········   72.1M                    26.8s
  w100  ████████████████····  107.1M                    49.5s
  w200  ████████████████████  137.8M                   114.7s
worst (open)
  w10   ████················   87.4M                    14.2s
  w25   ██████··············  132.0M                    26.7s
  w50   ████████████████····  375.3M                    57.7s
  w100  ████████████████████  456.3M                   111.3s
  w200  ████████████████████  456.3M  (same route)     258.8s
worst (fc N)
  w10   ██████████··········   50.6M                    12.2s
  w25   ███████████·········   57.1M                    26.0s
  w50   ████████████████····   84.0M                    48.3s
  w100  ████████████████····   84.2M                    93.0s
  w200  ████████████████████  103.3M                   207.7s
```

## Findings

1. **Time is linear in width.** Every doubling of the beam roughly
   doubles wall time, on every shape. The search cost is driven by
   anchor count, and anchors scale directly with the frontier.

2. **Value is a staircase, not a curve with a knee.** Each shape goes
   flat and then jumps again at a different width: mid is flat 10–50
   then jumps twice; worst climbs steeply to 100 then holds (width 200
   re-finds the identical route); the filtered shape knees at 50, holds
   to 100, then finds +23% at 200. There is no width at which all
   three plateau.

3. **The jumps are structural, which is why no local measure predicts
   them.** A wider beam keeps a mid-rank station whose *descendants*
   two hops later are excellent. The hop-1 score curve cannot see
   that — a station at rank 150 with a mediocre first trade can lead
   the best six-hop chain. This is the inherent blindness of any beam
   search, bought deliberately in exchange for not searching the whole
   graph.

4. **Narrowing below 50 is not safe.** Width 10 gives up 77% of the
   worst shape's value (87M vs 456M) and 40% of the filtered shape's
   (51M vs 84M). The mid shape alone tolerated it. Whatever appeal a
   faster narrow beam has, it is paid for in real route value.

5. **Under open filters, the extra value of wide beams lives heavily
   in the fleet-carrier tail.** The worst shape's spectacular climb
   (87M → 456M) is open-filter; the `--fc N` control's climb is far
   shallower (51M → 103M). Carrier owner-set prices put extreme-margin
   trades thinly scattered through the galaxy; a wider net keeps
   catching more of them. This matches the long-recorded carrier-
   dominance behaviour of unfiltered searches.

## Decision — 50 stays

No measured width dominates 50. The candidates:

- **Narrower** (10/25): time halves, but finding 23–77% less value on
  two of three shapes is a bad default trade.
- **100**: doubles every multi-hop wall time. The filtered economy —
  the one that reflects station-to-station trading rather than carrier
  arbitrage — gains 0.3%. The case for 100 is essentially a case for
  chasing carrier prices, and a default should not pay double time for
  that.
- **200**: quadruple time, shape-dependent gains, and the filtered
  gain (+23%) still costs 3.5 minutes on a shape that runs in 48s
  at width 50.

So 50 remains the default for both constants: it sits at the filtered
economy's knee, it is the established baseline every verification run
is anchored to, and nothing in the data offers a better single number.

**Considered and not adopted:** exposing beam width as a user-facing
option ("how long will you wait for a better route?"). The sweep shows
the trade-off is real and shape-dependent, which is the argument *for*
a lever; the argument against is that it breaks route reproducibility
between users, invites support noise ("TD gave me a worse route" —
with a non-default width in play), and adds a tuning surface to a tool
whose value is giving one good answer. Not adopted; recorded here so
the discussion does not restart from zero.

## If this is revisited

- Re-run the sweep on then-current data before re-arguing from these
  figures; the staircase positions move with the market.
- The `--fc N` control is the load-bearing comparison. Open-filter
  gains overstate what a wider beam earns in the real economy.
- Any change to the constants changes routes. It is a recorded
  decision with a fresh sweep as evidence, never a quiet retune.
