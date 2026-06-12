# Slice 25 — Completion Report

**Bound-ordered streaming fetch with a provable early stop; beam-width
value-versus-time sweep.**

*Completed 2026-06-12. Code commit `dcda7bac`.*

---

## What the slice set out to do

Slice 24 left one named residual: at open filters, ~53% of per-anchor
fetch cost was Python materialising rows that mostly never produced a
winning pair. The named lever — bound-ordered pairing with a provable
early stop — was this slice's Part B. Part A gated it with two probes;
Part C ran the never-before-measured beam-width value-versus-time sweep
on the finished engine.

## What was delivered

### Part A — probes (results recorded in the implementation plan)

- **P1** replayed real runs against a simulated stop and found it would
  skip ~86–94% of rows on every multi-hop shape (100% minus five rows
  on one-hop), with zero violations from ~510k falsification solves
  across both ls-conversion paths. Gate passed.
- **P2** verified the mechanics: the bounds-EXISTS-to-join swap returns
  identical row sets; SQLite streams rows on demand (no driver
  pre-buffering); the window-function sort costs noise; the
  aggregate-temp ordering variant re-pays the whole walk and is dead.
  P2 also surfaced that the non-terminal walk was dominated by the
  per-row onward-viability EXISTS — a per-station question asked per
  row.

### Part B — the build

The open-ended candidate fetch became a streaming generator
(`iter_open_ended_station_groups` in `data_gateway.py`): open-side rows
join the fixed side's per-item price bounds (1:1 on the temp's primary
key), each station's ceiling — its best optimistic profit per unit — is
computed with a window function, and rows stream station-complete in
descending-ceiling order. Consumers solve each station's pairs as the
group arrives and stop reading at the first station whose ceiling
cannot beat the kept-score floor; the tail is never read off the
cursor, never converted, never paired. The stop conversion is
direction-aware: the anchor's ls when the anchor is the destination,
the curve's maximum (ls 0) when the destination varies.

Onward viability on intermediate hops became a per-station semi-join
against the opposite side's qualification temp, adopted after
confirming the temp's population predicates and the onward EXISTS
branches are the same filter list term for term (they were already
shared helpers on the temp side). The per-row EXISTS remains only for
cache-less paths, extracted to a module-level helper.

All three consumers were converted in turn, each verified before the
next: the open-anchor engine (`route_common`), the one-hop planners
(`route_onehop`), the fixed-terminal envelope expansion
(`route_anchored`). The unstreamed fetch was then caller-free and was
deleted (~380 lines). Streaming counters (rows read, stations consumed,
early stops) joined the expansion stats and the diagnostics output.

### Verification — routes byte-identical throughout

Seventeen route comparisons across the three seams (both open multi-hop
directions × both jump ranges, hops 3 and 6, a filtered twin,
`--towards` with the stop disabled, four one-hop shapes including a
re-run after a malformed station name made one comparison vacuous, and
both fixed-terminal shapes), then run set 5's eight final-code runs —
all identical to the old code on the same data.

### Performance (run set 5, `timing_baselines.md`)

- Open multi-hop: −45% to −61% wall; the worst shape 145.7s → 57.0s.
- Fixed-terminal: −29% / −33%; remains the slowest family, for measured
  structural reasons (the per-layer envelope defeats memo and
  bubble-skip reuse; the real-budget floor stops later; ~5× jump-path
  time).
- One-hop: planner-internal ~10× on large candidate sets
  (641ms → ~60ms from Sol; 91,584 candidates fetched → 5 read).
- Production skip rates matched P1's simulation within a few points.

### Part C — beam-width sweep

Five widths × three shapes on the finished engine. Time is linear in
width; value is a shape-dependent staircase with no universal knee;
narrowing below 50 loses 23–77% of value; open-filter wide-beam gains
are largely carrier-tail. **Decision: both widths stay at 50.** The
full analysis, graph, and the user-facing-lever idea (considered, not
adopted) live in the standalone `beam_width_analysis.md` — deliberately
outside the slice docs, kept past release.

## Variances from plan

1. **The onward-viability semi-join** was a P2 discovery promoted into
   Part B (with the predicate-identity check the plan required), not an
   original design element.
2. **Tie-break reconstruction.** Equal-rank ties now resolve by
   best-pair order (best profit-per-unit, item name, pair key) instead
   of the old unordered-scan first-appearance order; solve order
   follows the stream. Neither moved any verified route.
3. **One-hop diagnostics accounting.** The stream interleaves fetch and
   solve, so the one-hop market figure now subtracts the cargo time
   accumulated inside the loop.
4. **The sweet-spot probe** (fixed-vs-open at 2/3/4 hops) was run
   mid-slice on request; its geometric-crossover finding is recorded in
   run set 5.
5. **Part C's record** went to the standalone beam document rather than
   `timing_baselines.md`, so it survives release housekeeping.

## Recorded for later (performance only, no action owed)

- **Loose-envelope cache lever:** a fixed-terminal layer whose envelope
  is wider than its bubble constrains nothing, yet its presence still
  disables memo and bubble-skip reuse; dropping provably-loose
  envelopes from those layers' cache keys would give early layers the
  open engine's reuse.
- The fixed-terminal family is now the headline residual; the open
  shapes' former row-materialisation residual is closed.

## Housekeeping

Probe scripts and their artefacts (P1/P2 capture JSONLs, the sweep
JSONL and per-run texts, the verification output directory) deleted at
slice close per standing practice. The living docs were updated:
`BASELINE.md` (residual closed, beam decision settled),
`SPEC_STATUS.md` (performance-contract note), `INDEX.md` (this slice
and the beam analysis), `timing_baselines.md` (run set 5).
