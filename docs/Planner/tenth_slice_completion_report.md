# Slice 10 Completion Report — Open-Origin Multi-Hop

## Status

Complete. Code committed on `release/v1`: the core shape in `bbd1e8ed`, the
performance and correctness round in `d4f6932b`. Documentation in this commit.

## What this slice adds

One new route shape — multi-hop to a fixed destination with the origin chosen by
the planner:

```text
trade run --to Y --hops N        (--from omitted, N >= 2)
```

It is the multi-hop twin of Slice 4's open-origin one-hop. Known-origin
multi-hop (`--from X --hops N`, with or without `--to`) already worked from
Slice 8. After this slice the only multi-hop shape still missing is the fully
unanchored one (both endpoints omitted), which stays deferred.

No new user options, and the route shape that comes out is unchanged. Only the
way the route is *found* is new (plus diagnostics — see below).

## How it works (recap)

Full design is in `tenth_slice_implementation_plan.md`; the condensed version is
the Slice 10 entry of `SLICE_SUMMARY.md`. In short:

- **Dispatch.** The `hops > 1` branch of `plan_route` now dispatches on
  endpoints like the one-hop branch: `--from` set -> known-origin multi-hop;
  `--from` omitted, `--to` set -> the new backward search; both omitted ->
  rejected in validation. The gate was relaxed from "requires --from" to
  "requires --from or --to" in both `validation.py` and the command-layer guard
  in `run_cmd.py`.
- **Backward search.** The route is grown backwards from Y, one hop's reach per
  layer, beam-trimmed between layers — no origin sphere built up front and no
  destination envelope (open origin moves away from the one fixed point, it does
  not aim at it). `best_open_ended_trades_into` is the per-node primitive (the
  direction-mirror of the forward `best_open_ended_trades_from`): "who profitably
  sells into this station?", grouped by the chosen source. The reachable source
  set stays a SQL subquery, and the `terminal_hop` onward-viability `EXISTS` was
  generalised to attach to whichever side is open (onward demand for an open
  source, onward supply for an open destination).
- **Per-station coalescing trim.** Each backward layer is grouped by the emerged
  source station (the best optimistic node per station is kept), then
  score-trimmed to the beam width. Source-system diversity was not needed at the
  current data shape.
- **Credits.** Money compounds forward, but the search runs backward, so it
  cannot know the running budget when it picks a source. Expansion is therefore
  credit-optimistic — cargo is fitted against a deliberately non-binding budget
  so the beam ranks on an upper-bound profit — and a forward credit-correction
  pass then re-fits each finished chain hop by hop against the real running
  budget, keeping a chain only if every hop is affordable and picking the
  highest *corrected* score.

## The performance and correctness round

The first working version was correct but slow, and under tight credits the
correction pass could blow up. A measurement-led round (`d4f6932b`) addressed it
and fixed a latent cargo bug found on the way.

**Cargo bound fix (correctness).** The branch-and-bound pruning bound spent the
credit budget with integer quantities — which is a feasible-solution value (a
lower bound), not an upper bound. When credits bind it could fall below the true
subtree optimum and prune the best cargo, returning a lower-profit plan. It is
now admissible: relax cargo capacity and the credit budget in turn, solve each
single-constraint knapsack exactly, and take the smaller result. Verified against
an exhaustive brute-force search over 24,000 randomised instances with zero
mismatches (a throwaway verification script, not part of the codebase).

**Cargo search made bounded (performance).** The correct-but-looser bound made
the search explode on large binding-credit instances, so the incumbent is seeded
with the better of two greedy feasible fills (one ranked by profit-per-unit, one
by profit-per-credit) and a hard node-visit cap backstops the worst case. A
separate exact greedy fast path skips the search entirely when the credit budget
cannot bind the plan — the common case in the credit-optimistic backward
expansion.

**Bounded correction (performance).** Re-costing thousands of finalists against
the real budget was the dominant cost. The pass now caps re-costing at the best
`_OPEN_ORIGIN_CORRECTION_WIDTH` (200) finalists by optimistic score, with an
exact early-stop: a corrected score never exceeds its optimistic score, so once
the best corrected route beats the next finalist's optimistic score, no
lower-ranked finalist can win and the loop stops. The cap is a tunable safety
backstop; the early-stop is the exact part and does the real work (see the
verification table — the cap never bound).

**Diagnostics.** Added a cargo fast/branch-and-bound split and a correction
block (`CorrectionStats`: finalists generated/attempted/corrected, the cargo
split, elapsed). These are the only DTO and renderer additions in the slice.

## Verification

All four runs share the same command at a deliberately low 1,000,000 cr budget —
the case that stresses credit-correction — with progressively tighter station
filters:

```text
trade run --to "Lave/Lave Station" --hops 3 \
    --capacity 720 --credits 1000000 --jumps-per 3 --ly-per 30   [+ filters]
```

| Filters added | Origin chosen | Profit (cr) | Practical score | Candidate rows | Finalists / attempted | Correction time | Wall-clock |
|---|---|---|---|---|---|---|---|
| (none) | AN Sextantis/INIV | 48,138,300 | 50,722,244 | 3,376,109 | 1,994 / 10 | 1 ms | 3m34.7s |
| `--age 4` | Borr/D0K-6VK | 47,883,541 | 50,458,073 | 1,286,980 | 2,351 / 3 | 5 ms | 2m37.4s |
| `--age 4 --planetary N --fc N` | Piscium Sector JW-W b1-2/Kowalski Depot | 36,352,754 | 38,501,260 | 1,215,943 | 2,500 / 50 | 2,584 ms | 2m32.8s |
| `… --pad-size L` | Piscium Sector UZ-O a6-3/Kawasaki Terminal | 28,166,219 | 29,346,721 | 578,473 | 2,500 / 101 | 4,274 ms | 2m00.4s |

Each route is valid: every hop reachable under the jump settings, every hop a
real buy/sell, every route ending at Lave/Lave Station, and every cargo bought
under the real running budget from a 1M-credit start. Profit degrades gracefully
as filters remove candidate stations (48.1M -> 47.9M -> 36.4M -> 28.2M), and the
search keeps re-finding the strong LAWD 96/Wiener Prospect -> Pangu/Appleton
Vision middle hop while varying the origin that feeds it, until `--pad-size L`
removes that leg and a different chain wins. That is the search behaving sensibly
under tightening constraints.

Four things the diagnostics confirm:

1. **The correction pass is no longer the cost.** It re-costs at most 101 of up
   to 2,500 finalists and finishes in 1 ms - 4.3 s. The 200-cap never bound (the
   most attempted was 101), so the exact early-stop alone chose the winner — the
   result is identical to re-costing every finalist.
2. **The inversion is gone.** Wall-clock now *decreases* as filters tighten
   (3m35 -> 2m37 -> 2m33 -> 2m00), tracking the candidate-row count
   (3.4M -> 1.3M -> 1.2M -> 0.58M). Tighter filters do less work, as they should.
3. **All branch-and-bound is in correction; expansion is 100% fast-path.** In
   every run the total branch-and-bound count equals the correction
   branch-and-bound count (run 4: 200 total, 200 in correction). Expansion fits
   cargo against the non-binding optimistic budget, so the fast path always
   applies there; only correction, with the real budget, ever needs the search.
   That is the fast path working as designed.
4. **The remaining cost is expansion, specifically the second backward layer.**
   Search is ~99% of wall-clock, and within it Layer 2 dominates (run 1: 109.6 s
   of 208.7 s total). That is where the next optimisation round (deferred below)
   should look — narrowing candidate rows before cargo fitting.

`--old` was not used as a parity oracle. The plan treats it as a probe, not an
oracle, and the legacy open-origin multi-hop is impractically slow for this shape
(an earlier comparison run exceeded 15 minutes without completing). Route
validity and internal consistency are the gate.

## Files changed

Core shape (`bbd1e8ed`):

```text
tradedangerous/planner/validation.py      # relaxed the multi-hop gate
tradedangerous/commands/run_cmd.py        # relaxed the command-layer guard
tradedangerous/planner/run_route.py       # dispatch + backward path + helpers
tradedangerous/planner/data_gateway.py    # generalised the terminal_hop EXISTS
```

Performance and correctness round (`d4f6932b`):

```text
tradedangerous/planner/cargo.py           # admissible bound, fast path, seed + node cap, counters
tradedangerous/planner/run_route.py       # bounded correction, early-stop, widened final layer, diagnostics
tradedangerous/planner/run_result.py      # CorrectionStats + diagnostics fields
tradedangerous/planner/render_text.py     # cargo + correction diagnostic lines
```

Request and parser carry no change; the DTO and renderer additions are
diagnostics-only.

## Deferred (not cut)

- **Expansion-cost narrowing.** The remaining wall-clock is expansion, and
  within it the second backward layer. A future round can narrow candidate rows
  in SQL before cargo fitting. A separate decision, after this one.
- **Fully unanchored multi-hop** (`--hops N`, both endpoints omitted) — the next
  shape slice.
- **All route modifiers and search/display controls** still gated in validation
  (`--via`, `--avoid`, `--towards`, `--loop`, `--unique`, `--shorten`,
  `--start-jumps`, `--end-jumps`, the pruning controls, `--routes > 1`).
- **Source-system diversity** on the backward trim — not needed at the current
  data shape.

The forward-open `--from X --hops N` shape's own wall-clock is a separate Slice 8
concern and was not touched here.
