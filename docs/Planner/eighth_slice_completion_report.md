# Slice 8 Completion Report

## Status

**Slice 8 is complete.**

Implemented scope:

```text
trade run --from X --hops N
trade run --from X --to Y --hops N
```

The slice now supports vanilla known-origin multi-hop planning, including fixed-terminal multi-hop, while keeping the previously deferred route modifiers out of scope.

## Delivered Behaviour

### Multi-hop from a known origin

The planner now builds layered route frontiers from a known `--from` endpoint and propagates credits hop-to-hop.

Intermediate hops require onward-source viability so terminal-only demand stations do not occupy continuation slots.

### Fixed-terminal multi-hop

For:

```text
trade run --from X --to Y --hops N
```

the planner keeps the search directed toward the destination using a remaining-hop distance envelope.

The envelope is pushed into SQL so out-of-envelope destinations are filtered before Python materialisation, grouping, cargo optimisation, scoring, and sorting.

This avoided repeating the legacy failure mode of fetching a broad candidate universe and rejecting obvious impossibilities in Python afterwards.

### Frontier quality fix

The Sol -> Lave quality regression was traced to global frontier slot pollution.

The legacy-quality first hop:

```text
Sol/Shen Extraction Rigs -> Charunder/Whitworth Station
```

was generated and survived per-parent expansion, but was lost at the global frontier trim:

```text
per-parent rank: 14
global rank:     316
classification:  C
```

The cause was near-duplicate high-score destinations occupying too many of the fixed 50 frontier slots.

The fix is destination-system diversity during fixed-terminal global frontier trimming:

```text
sort candidates by accumulated practical score
retain at most one frontier node per destination system
stop at _MULTIHOP_FRONTIER_WIDTH
```

This preserved the bounded beam width while improving slot quality.

Open-terminal multi-hop still uses the normal score-ranked top-N frontier trim.

### Partial-route returns

Slice 8 now returns a structured partial route when planning makes progress but cannot complete the requested hop count.

Partial results preserve diagnostics and emit structured `PartialRouteWarning` data. Renderer wording remains owned by `render_text.py`, not baked into planner state.

Partial warning cases covered:

```text
expansion collapse:
  phase="expansion"
  reason="no_viable_continuation"

final no-reachable:
  phase="final"
  reason="no_reachable_route"

final reachable-but-no-trade:
  phase="final"
  reason="no_viable_trade"
```

### Module rename

`run_onehop.py` has been renamed to:

```text
run_route.py
```

The command entry point now imports `plan_route` from the renamed module.

## Validation Evidence

### Fixed-terminal Sol -> Lave

Final representative fixed-terminal run:

```text
trade run --from "Sol" --to "Lave" --hops 3 --jumps-per 2 --ly-per 30 \
  --capacity 128 --credits 5000000 --fc N --age 2
```

Result:

```text
Sol/Shen Extraction Rigs -> Lave/Lave Station
Total gain: 7,838,971 cr
Final credits: 12,838,971 cr
```

Route:

```text
Hop 1:
  Sol/Shen Extraction Rigs
  -> Charunder/Whitworth Station
  128 x Bauxite
  Gain: 1,677,056 cr

Hop 2:
  Charunder/Whitworth Station
  -> Clotho/Franke Sanctuary
  87 x Silver
  41 x Gold
  Gain: 6,003,835 cr

Hop 3:
  Clotho/Franke Sanctuary
  -> Lave/Lave Station
  128 x Land Enrichment Systems
  Gain: 158,080 cr
```

Legacy comparison:

```text
new planner:
  7,838,971 cr
  ~32.5s real

legacy --old:
  7,838,971 cr
  ~46.4s real
```

This confirms that the new planner now matches legacy profit on the representative fixed-terminal case while remaining materially faster.

### Quality trace

The quality trace confirmed that the old route was valid under the new helpers and produced the exact same total as legacy:

```text
legacy route via new helpers: 7,838,971 cr
legacy planner reported:      7,838,971 cr
new planner previous choice:  5,059,696 cr
```

The trace ruled out:

```text
cargo maths mismatch
price arithmetic mismatch
SQL envelope bug
per-parent expansion width failure
final-hop failure
```

The failure was solely at hop-1 global frontier trim.

### Partial-route warning probe

A controlled probe exercised all three partial-warning branches:

```text
expansion-layer collapse after one completed hop
final-hop collapse with no reachable destination
final-hop collapse with reachable destination but no viable trade
```

The probe verified:

```text
structured PartialRouteWarning values are returned
partial routes preserve completed hops
diagnostics are retained
renderer warning text is produced from structured warning data
```

This was treated as sufficient QA for partial-route warnings because constructing equivalent real-galaxy cases would require unstable and time-consuming dependence on exact live market/geography conditions.

## Deferred Scope Still Deferred

The following remain out of Slice 8 and should continue to reject rather than silently operate:

```text
omitted --from
both endpoints omitted
--via
--avoid
--towards
--loop
--unique
--loop-interval
--shorten
--routes top-N
--max-routes
--prune-score
--prune-hops
--start-jumps
--end-jumps
```

## Known Non-blocking Cleanup

`tradedangerous/planner/run_route.py` still has a stale module docstring:

```python
"""One-hop trade run planner orchestration."""
```

Queued replacement:

```python
"""Trade run planner orchestration."""
```

This is cosmetic and not a Slice 8 blocker.

## Conclusion

Slice 8 has met its practical completion criteria:

```text
known-origin multi-hop works
fixed-terminal multi-hop works
Sol -> Lave matches legacy route profit
fixed-terminal runtime is materially faster than legacy
frontier quality issue was diagnosed and fixed without widening the beam
partial-route warning behaviour is implemented and probed
deferred options remain out of scope
```

**Slice 8 can be closed.**