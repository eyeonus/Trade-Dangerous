# Slice 22 — Cargo Pre-Filter (Skip Unwinnable Cargo Solves)

Implementation plan. The cargo optimiser is the dominant cost on the route
shapes that fit cargo against the **real** credit budget. We fully solve every
candidate station pair, then sort by practical score and keep only a handful —
throwing most of the expensive solves away. This slice adds a cheap, admissible
pre-check: before running the branch-and-bound solve on a pair, ask whether it
could possibly beat the pairs we are already keeping. If it provably cannot, the
solve is skipped.

---

## What the measurement showed

The scope pass measured cargo time against total time across the route shapes
(`--ly-per 30 --jumps-per 2 --capacity 200 --credits 5000000 --fc N`):

| Shape | Engine | Total | Cargo | Bottleneck |
|---|---|---|---|---|
| `--from Sol --to Lave` h3 | fixed-terminal (real budget) | 285s | **246s (86%)** | Cargo (9,637 b&b) |
| `--from Sol` h1 | one-hop open (real budget) | 519s | **516s (99%)** | Cargo |
| `--from Sol` h3 | optimistic open multi-hop | 159s | 6s (4%) | Fetch/group (3.4M rows) |
| `--to Lave` h3 | optimistic open multi-hop | 37s | 3s (7%) | Fetch/group (1.6M rows) |
| `--from Diso --to Lave` h1 | fixed pair | 0.3s | 0s | trivial |

The split tracks **how cargo is fitted**, not how "open" the route is:

- **Real-budget shapes (Camp A)** — credits bind, so cargo drops into
  branch-and-bound. Cargo dominates. These are the targets of this slice.
- **Optimistic-budget shapes (Camp B)** — the open *multi-hop* engine fits
  against a deliberately non-binding budget (then corrects once at the end), so
  cargo is all fast-path and effectively free. Their cost is fetching and
  grouping millions of candidate rows. **This slice does nothing for Camp B** —
  skipping a solve that is already cheap saves nothing. Camp B is a separate,
  named follow-up (candidate narrowing for the open shapes).

The fit-to-keep ratio is the headroom: the fixed-terminal case fully solves
~51,600 pairs and keeps ~3,250 — a 16:1 ratio. Most b&b work is spent on pairs
that lose the trim.

---

## The fix in principle

Rank stays the same; we just stop solving pairs that cannot place.

1. **Reuse the proven bound.** `cargo.py` already carries
   `optimistic_upper_bound` — an admissible over-estimate it uses internally to
   prune its own branch-and-bound. At the root (`index=0`, full capacity, full
   credits, zero profit) it bounds the whole pair's optimal **raw** profit. We
   reuse it; we do not invent a new bound.

2. **Fold in the ls multiplier.** The trim ranks by *practical score* =
   `raw_profit * ls_penalty_multiplier(destination_ls, penalty)`. That
   multiplier can **exceed 1** — the curve boosts close stations (up to ~1.5x),
   so raw profit alone is **not** a ceiling on practical score. The multiplier
   depends only on the destination's ls distance and the penalty percent, both
   known before any solve, so we fold the exact per-pair multiplier into the
   comparison.

3. **Compare against the kept threshold.** Maintain the score of the worst pair
   currently kept (the K-th best, or simply the single best for the one-hop
   shapes). A pair is skipped when its optimistic ceiling cannot reach it.

### Why it is exact

Let `B` be the root bound (so `B >= true optimal raw profit`), `m` the
destination's ls multiplier, and `T` the current kept threshold (a practical
score). The pair's maximum possible practical score is `B * m`, and since
`B >= true raw`, `B * m >= true practical score`.

Skip only when `B * m < T` (strict). Then `true practical < T`, so the pair
cannot reach the kept set — not even on a tie, since the comparison is strict.
`T` only ever rises, so a skipped pair can never become competitive later.

Every pair whose true score could place is therefore still solved, and the kept
set is unchanged. **Routes come out byte-identical.** The `< T` strictness
preserves exact ties, so the existing tie-break ordering is untouched.

### The `--towards` carve-out

`--towards` ranks **progress-first** (distance to target), not by score — see
`_pair_is_better`. A profit-based prune is invalid there: a low-score pair with
better progress can legitimately win. So pruning is **disabled whenever
`request.towards_target` is set**. (`--towards` requires `--from` and excludes
`--to`, so it only reaches the open-destination shapes; the fixed-terminal
engine never sees it.)

---

## Step 1 — Prune hook in `cargo.py`

`optimise_cargo` gains one optional keyword:

```python
def optimise_cargo(
    candidates,
    *,
    capacity_units,
    available_credits,
    cargo_limit_per_item=0,
    prune_below_raw: float | None = None,
) -> CargoPlan | None:
```

Inside `_optimise_cargo`, after the candidates are built and sorted (so
`optimistic_upper_bound` is defined) and **before** the fast-path / search
decision (~line 222):

```python
if prune_below_raw is not None:
    root_bound = optimistic_upper_bound(
        0, capacity_units, available_credits, 0
    )
    if root_bound < prune_below_raw:
        _cargo_path_counts["pruned"] += 1
        return None
```

- Returns `None` to mean "provably cannot beat the caller's kept threshold" —
  distinct from the `NoProfitableTrades` raise (no viable plan at all), so the
  two outcomes stay countable apart.
- `prune_below_raw=None` (the default) skips the block entirely, so every
  existing caller is **byte-for-byte unchanged** and never sees `None`.
- The check sits before both the fast path and the search, so a fast-path pair
  that cannot place is skipped too — cheap, but free to include.

Add `"pruned": 0` to `_cargo_path_counts`, reset it in
`reset_cargo_counters`, and add a `cargo_pruned()` getter (mirroring
`cargo_counters` / `cargo_time_ms`). The `optimise_cargo` timing wrapper already
returns whatever `_optimise_cargo` returns, so `None` passes through and the
pruned solve's (tiny) bound cost is still timed.

---

## Step 2 — Shared prune helpers in `route_common.py`

Per the planner architecture rule, the prune *meaning* is resolved once and
shared; engines apply it to their own loops. Three small helpers:

**A top-K threshold tracker** (K=1 collapses to "single best", serving the
one-hop shapes):

```python
class _KeptScoreThreshold:
    """Running score floor for the top-K kept pairs.

    current() returns the floor a new pair must beat to enter the kept set, or
    None when the set is not yet full (so nothing is pruned) or pruning is
    disabled (e.g. --towards ranks by progress, not score).
    """

    def __init__(self, keep_k: int, *, enabled: bool = True):
        self._k = keep_k
        self._enabled = enabled
        self._heap: list[float] = []          # min-heap of practical scores

    def current(self) -> float | None:
        if not self._enabled or len(self._heap) < self._k:
            return None
        return self._heap[0]

    def offer(self, score: float) -> None:
        if not self._enabled:
            return
        if len(self._heap) < self._k:
            heapq.heappush(self._heap, score)
        elif score > self._heap[0]:
            heapq.heapreplace(self._heap, score)
```

**The raw-profit floor for a given destination** — converts the practical
threshold into the `prune_below_raw` value `optimise_cargo` expects:

```python
def cargo_prune_floor(threshold, destination_ls, penalty_percent):
    """Raw-profit floor a pair to this destination must clear to place.

    None means do not prune: the threshold is not set yet, or the ls multiplier
    is non-positive (an extreme-distance station whose practical score is <= 0
    regardless of profit — rare; left for the solve to handle).
    """
    if threshold is None:
        return None
    mult = ls_penalty_multiplier(destination_ls, penalty_percent)
    if mult <= 0:
        return None
    return threshold / mult
```

**A cheap best-first ordering key** — solving the most promising pairs first
makes the threshold rise fast, so the long tail prunes hard:

```python
def cargo_order_key(pair_candidates, destination_ls, capacity, penalty_percent):
    best_ppu = max(c.profit_per_unit for c in pair_candidates)
    return capacity * best_ppu * ls_penalty_multiplier(destination_ls, penalty_percent)
```

Ordering affects only prune efficiency, never correctness — the final selection
is order-independent.

---

## Step 3 — Wire the fixed-terminal expansion (top-K)

`route_anchored.best_open_ended_trades_from` is the measured 246s seam. It
currently fits every grouped pair, appends to `scored`, then sorts and takes
`top_k` survivors. Change:

1. Build a `_KeptScoreThreshold(top_k)` (the engine never sees `--towards`, so
   `enabled=True` always here).
2. Order `grouped_pairs.items()` by `cargo_order_key` descending before the
   loop (destination ls comes from `destination_stations`).
3. In the loop, compute
   `floor = threshold.current()` → `cargo_prune_floor(floor, dest_ls, penalty)`
   and pass it as `prune_below_raw`. If `optimise_cargo` returns `None`, count a
   prune and `continue`.
4. After a real solve, `threshold.offer(practical_score)`.

The end-of-loop sort and top-K trim are unchanged; with pruning, `scored` simply
holds fewer (never any of the winning) entries.

---

## Step 4 — Wire the one-hop open shapes (top-1)

`route_onehop._best_open_ended_plan` is the measured 516s seam;
`route_onehop._plan_unanchored` is the same top-1 pattern (one-hop unanchored,
the predicted Camp A galaxy-wide shape). Both keep a single `best_pair` via
`_pair_is_better`. For each:

1. Build a `_KeptScoreThreshold(1, enabled=request.towards_target is None)`.
   (`_plan_unanchored` has no `--towards` path, so it is always enabled; passing
   the flag keeps the two call sites identical.)
2. Order `grouped_pairs.items()` by `cargo_order_key` descending.
3. Compute the floor from `threshold.current()` and pass `prune_below_raw`; on
   `None`, count a prune and `continue`.
4. After a real solve and the score computation, `threshold.offer(practical_score)`.

`_best_pair_plan` (the fixed `--from X --to Y` one-hop) and
`best_fixed_pair_trade_from` (the fixed-terminal **final** hop) are left alone:
both are bounded by named-endpoint station counts and measured trivial /
~2s. Applying the same tracker there is consistent but low-value; deferred
unless it falls out cheaply.

---

## Step 5 — Surface the prune in diagnostics

The instrumentation already prints the cargo total; add the prune count so the
win is visible and verifiable.

- Add `cargo_pruned_solves: int = 0` to `PlannerDiagnostics`.
- Multi-hop: `_multihop_result` reads `cargo_pruned()` onto it; the `Cargo:`
  line gains `…, <N> pruned`.
- One-hop: the three planners already set `cargo_optimisation_ms`; have them
  also read `cargo_counters()` / `cargo_pruned()` onto the DTO, and extend the
  single-hop diagnostics block to show the fast-path / b&b / pruned split — so
  the `--from Sol --hops 1` verification shows the prune working, not just a
  smaller total.

---

## Query discipline

No database change. The prune is pure Python over candidates that have **already
been fetched** for the pair; it removes work, it does not add a query. The bound
is O(commodities-in-pair), the ordering one sort per call — both negligible
against the b&b they replace.

---

## Verification (spot-checks, handed to Tromador)

Re-run the two measured Camp A cases and compare against the recorded baselines:

1. `trade run --from Sol --to Lave --hops 3 --ly-per 30 --jumps-per 2 --capacity 200 --credits 5000000 --fc N`
   — baseline 285s / cargo 246s / 9,637 b&b.
2. `trade run --from Sol --hops 1 --ly-per 30 --jumps-per 2 --capacity 200 --credits 5000000 --fc N`
   — baseline 519s / cargo 516s.

Expect, for each:

- **Route byte-identical** to the baseline (same stations, same per-hop and
  total profit) — the exactness proof.
- `Cargo:` time sharply down, b&b count sharply down, a large `pruned` count.

Also re-run one Camp B shape (`--to Lave --hops 3`) to confirm it is **unchanged**
— the prune must be inert where cargo is already fast-path.

flake8 clean on every touched file.

---

## Out of scope / deferred

- **Camp B — open multi-hop fetch/group cost** (the 3.4M / 1.6M candidate-row
  shapes). A different mechanism — narrowing candidate rows before they leave
  SQL, since the open shapes have no `--to` envelope. Its own slice.
- **Faster per-solve branch-and-bound** (tighter bounding / a DP formulation).
  Touches the proven-exact optimiser; only if the pre-filter proves
  insufficient.
- The fixed-pair one-hop and the fixed-terminal final hop (low-value, see Step 4).

---

## Touched files

| File | Change |
|------|--------|
| `planner/cargo.py` | `prune_below_raw` param + root-bound check + `None` sentinel; `pruned` counter and `cargo_pruned()` getter. |
| `planner/route_common.py` | `_KeptScoreThreshold`, `cargo_prune_floor`, `cargo_order_key`. |
| `planner/route_anchored.py` | Order + threshold + prune in `best_open_ended_trades_from`. |
| `planner/route_onehop.py` | Order + threshold + prune in `_best_open_ended_plan` and `_plan_unanchored`; cargo counts onto the DTO. |
| `planner/run_result.py` | `cargo_pruned_solves` diagnostics field. |
| `planner/render_text.py` | `pruned` on the multi-hop `Cargo:` line; fast/b&b/pruned split on the single-hop block. |
