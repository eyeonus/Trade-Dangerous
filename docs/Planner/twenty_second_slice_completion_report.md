# Slice 22 — Cargo Pre-Filter — Completion Report

The cargo optimiser was the dominant runtime cost on the route shapes that fit
cargo against the real credit budget. This slice adds a cheap, admissible
pre-check that skips the expensive branch-and-bound solve for any candidate pair
that provably cannot beat the pairs already being kept. Routes are unchanged;
the slow shapes are 6–130× faster.

---

## What the measurement found

A scope pass measured cargo time against total time across every route shape
(`--ly-per 30 --jumps-per 2 --capacity 200 --credits 5000000 --fc N`). The
shapes split into two camps by **how cargo is fitted**:

| Shape | Engine | Total | Cargo | Bottleneck |
|---|---|---|---|---|
| `--from Sol --to Lave` h3 | fixed-terminal (real budget) | 285s | 246s (86%) | **Cargo** |
| `--from Sol` h1 | one-hop open (real budget) | 519s | 516s (99%) | **Cargo** |
| `--from Sol` h3 | optimistic open multi-hop | 159s | 6s (4%) | Fetch/group |
| `--to Lave` h3 | optimistic open multi-hop | 37s | 3s (7%) | Fetch/group |

**Camp A** (real budget) drops into branch-and-bound and is cargo-bound.
**Camp B** (the open multi-hop engine, which fits against a deliberately
non-binding optimistic budget and corrects once at the end) is all fast-path and
spends its time fetching candidate rows. This slice targets Camp A only; the
Camp B fetch cost is a separate concern, recorded as a follow-up.

The headroom was the fit-to-keep ratio: the fixed-terminal case fully solved
~51,600 pairs and kept ~3,250 — most branch-and-bound work spent on losers.

---

## The mechanism

Ranking is unchanged; pairs that cannot place simply stop being solved.

- **Reused bound.** `cargo.py` already carried `optimistic_upper_bound`, an
  admissible over-estimate it uses internally for its own branch-and-bound
  pruning. Evaluated at the root it bounds the whole pair's optimal raw profit.
  No new bound was written.
- **Folded ls multiplier.** The kept set ranks by practical score =
  `raw_profit * ls_penalty_multiplier(...)`, and that multiplier can exceed 1
  (the curve boosts close stations), so raw profit alone is not a ceiling on the
  ranked score. The exact per-pair multiplier — known from the destination ls
  distance before any solve — is folded into the comparison.
- **Kept-score threshold.** A small `_KeptScoreThreshold` tracks the worst score
  in the top-K (K=1 collapses to the single-best the one-hop planners keep). A
  pair is skipped when `bound * multiplier < threshold` (strict).
- **Best-first solving.** Pairs are solved in descending order of a cheap
  optimistic key, so the threshold rises fast and the long tail prunes hard.

### Exactness

The bound is an over-estimate and the threshold only rises, so a skipped pair's
true score is strictly below the kept floor — it could never place, ties
included (the comparison is strict). The fixed-terminal engine pins selection to
`(score desc, original position asc)`, reproducing the unordered scan's tie
order exactly; the one-hop engines select via `_pair_is_better`, already a total
order down to station id, so they are order-independent by construction. Pruning
is disabled under `--towards`, which ranks by progress toward a target rather
than by score.

---

## What was built

| Step | Change |
|------|--------|
| 1 | `cargo.py`: `prune_below_raw` parameter; admissible root-bound check returning `None` when the pair cannot place; `pruned` counter and `cargo_pruned()` getter. |
| 2 | `route_common.py`: `_KeptScoreThreshold`, `cargo_prune_floor`, `cargo_order_key` — the shared prune mechanism. |
| 3 | `route_anchored.py`: best-first order + threshold + prune in `best_open_ended_trades_from`, with `(score, original position)` selection. |
| 4 | `route_onehop.py`: the same applied to `_best_open_ended_plan` and `_plan_unanchored` (top-1). |
| 5 | Diagnostics: a `pruned` count on the `Cargo:` line; the single-hop diagnostics block brought to parity with the multi-hop one (phase timings, candidate count, full cargo split, unanchored counters). |

Instrumentation added alongside the work — a module-level cargo timer
(`cargo_time_ms`) and a per-phase fetch/cargo/jump split in the fixed-terminal
expansion — was kept, by decision, as standing diagnostics.

---

## Verification (live data)

| Run | Route | Pruned | Cargo | Total | Before |
|---|---|---|---|---|---|
| Fixed-terminal `--from Sol --to Lave` h3 | **byte-identical** | 47,457 / 51,596 | 5.5s | 46s | 285s |
| One-hop `--from Sol` h1 | identical | 84,413 (6 solved) | 0.7s | ~5s | 8m40 |
| Open-origin `--to Lave` h3 (Camp B) | unchanged | **0** | 2.8s | 41s | unchanged |

- The fixed-terminal route matched exactly — profit 5,244,784, score 5,536,265,
  the same three hops — with the branch-and-bound count down from 9,637 to
  1,061. **"Same route"** confirmed by inspection.
- The one-hop open collapsed to **6 actual solves**: best-first ordering solved
  the winning Bauxite→Meliae trade early and the rising threshold pruned the
  84k-pair tail. Cargo 516s → 0.7s.
- Camp B reported **0 pruned** and ran unchanged — the prune is correctly inert
  where cargo is already fast-path, confirming the wiring is scoped to the
  engines that needed it.

flake8 clean on every touched file.

---

## Bottleneck shift (observed, not addressed here)

With cargo solved, the fixed-terminal expansion is now fetch-bound:

```
Expansion phases: fetch 35589ms, cargo 5523ms, jump 2425ms
```

That fetch is the Layer-1 repeated demand scan — the open shapes' candidate-fetch
cost surfaces here too (the one-hop open pulls 414k candidates with no
envelope). Narrowing candidate rows before they leave SQL is the genuine next
lever, and is the remaining half of the deferred "shared expansion-cost floor".
Out of scope for this slice.

---

## Touched files

| File | Change |
|------|--------|
| `planner/cargo.py` | `prune_below_raw` + root-bound check + `None` sentinel; `pruned` counter, `cargo_pruned()`; module cargo timer. |
| `planner/route_common.py` | `_KeptScoreThreshold`, `cargo_prune_floor`, `cargo_order_key`; cargo time/prune onto `_multihop_result`. |
| `planner/route_anchored.py` | Prune wiring in `best_open_ended_trades_from`; fetch/cargo/jump phase timers. |
| `planner/route_onehop.py` | Prune wiring in the two open one-hop planners; cargo counters onto the one-hop diagnostics. |
| `planner/run_result.py` | `ExpansionStats` phase fields; `cargo_pruned_solves` diagnostic field. |
| `planner/render_text.py` | `pruned` on the `Cargo:` line; enriched single-hop diagnostics block. |
