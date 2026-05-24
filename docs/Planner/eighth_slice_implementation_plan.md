# Slice 8 Plan — Vanilla Multi-Hop From a Known Origin

## Purpose

Extend the planner from a single hop to N hops, with the origin always
named by `--from`. Slice 8 is the first slice where credits propagate
between hops, `--margin` finally has a real effect, and a route is a
sequence rather than a pair.

The wider multi-hop option family (`--via`, `--avoid`, `--towards`,
`--loop`, `--unique`, `--loop-interval`, `--shorten`, `--routes` top-N,
the pruning controls, `--start-jumps`, `--end-jumps`, omitted `--from`,
and both endpoints omitted) is deliberately deferred to later slices.
Slice 8 keeps scope narrow so the multi-hop frontier model can land
cleanly before the shape-modifying options pile on top of it.

---

## Supported Shapes

Slice 8 adds two new shapes on top of Slices 1–7:

```text
trade run --from X --hops N            # open terminal, planner picks last station
trade run --from X --to Y --hops N     # fixed terminal, last hop ends at Y
```

All Slices 1–7 shapes continue to work unchanged at `--hops 1`. Multi-hop
(N ≥ 2) requires `--from`; the open-`--from` and both-omitted shapes
remain one-hop-only for this slice.

---

## Decision

**Beam frontier search.** Each hop level keeps a bounded set of
best-scoring partial routes; each surviving partial is expanded into the
next layer, the combined layer is rescored, and the layer is trimmed
back to the frontier width.

Two width constants, intentionally separate:

```python
_MULTIHOP_EXPANSION_WIDTH = 50   # max children generated per frontier node per hop
_MULTIHOP_FRONTIER_WIDTH  = 50   # max partial routes retained between hops
```

Expansion width controls per-node fan-out (how many destination
candidates one source station may produce in one hop). Frontier width
controls how many cumulative partial routes survive into the next hop.
With both at 50, the worst-case scored set per hop is 2500 partials
sorted by accumulated score and trimmed back to 50.

Two constants rather than one because the two concepts are not the same:
a generous expansion width lets each individual node explore widely;
the frontier width is what bounds the total search cost between hops.

Hidden constants rather than wiring `--max-routes` now: the user-facing
meaning of `--max-routes` (displayed routes? retained partials?
per-depth? per-node?) is not settled, and Slice 8 should not bake one
interpretation in before that decision is made.

The search is heuristic, not globally optimal. A truly optimal N-hop
plan over the full reachable graph is combinatorial; beam search with
realistic widths produces routes comparable to `--old`'s heuristics
while staying fast. Quality is verified against `--old` on the
benchmark corpus; if it regresses, the natural follow-up is a smarter
per-hop pruning gate (related to the deferred `--prune-score`).

---

## Pieces

### Piece A — Frontier model and search loop

A frontier node captures the state at the end of hop K: which station
the cargo just sold at, the cargo and jump path that brought it there,
accumulated profit and score so far, and credits available for hop K+1's
buy.

```python
@dataclass(frozen=True, slots=True)
class _FrontierNode:
    station: ResolvedStation
    parent: _FrontierNode | None         # None at the origin
    hop_index: int                       # 0 = origin, K = after hop K
    accumulated_raw_profit: int          # sum of raw profits hops 1..K
    accumulated_practical_score: float   # sum of practical scores hops 1..K
    available_credits: int               # budget for the next hop's buy
    hop_cargo: CargoPlan | None          # cargo that arrived at this node (None at origin)
    hop_jump_path: JumpPath | None       # jump path of the hop into this node (None at origin)
```

Search outline:

```text
frontier = [origin_node_for(station) for station in resolved_from_stations]
for hop in 1 .. N - 1:
    next_frontier = []
    for node in frontier:
        children = best_open_ended_trades_from(
            session, node.station, request,
            available_credits=node.available_credits,
            top_k=_MULTIHOP_EXPANSION_WIDTH,
            bubble_cache=bubble_cache,
        )
        next_frontier.extend(child_from_trade(node, trade) for trade in children)
    if not next_frontier:
        raise multi-hop NoProfitableTrades for this state
    next_frontier.sort(key=lambda n: n.accumulated_practical_score, reverse=True)
    frontier = next_frontier[:_MULTIHOP_FRONTIER_WIDTH]

# Final hop:
if --to:
    finalists = [
        fixed_pair_plan_from(node, request.to_text)
        for node in frontier
        if reachable(node.station, --to)
    ]
else:
    finalists = []
    for node in frontier:
        children = best_open_ended_trades_from(
            session, node.station, request,
            available_credits=node.available_credits,
            top_k=1,             # only need each node's single best terminal hop
            bubble_cache=bubble_cache,
        )
        finalists.extend(child_from_trade(node, trade) for trade in children)

if not finalists:
    raise multi-hop NoReachableRoute / NoProfitableTrades as appropriate
winner = max(finalists, key=accumulated_practical_score)
route = reconstruct_route(winner)
```

Route reconstruction walks the winner's parent chain back to the origin
node, collecting `(hop_cargo, hop_jump_path, source_station, destination_station)`
tuples in order, and builds `PlannedHop`s and the final `PlannedRoute`.

### Piece B — Per-node expansion helper

Factor the inner "given a source station and available credits, return
the top-K best one-hop trades" out of `_best_open_ended_plan` so multi-hop
can call it per frontier node without duplicating the dispatcher.

Proposed signature:

```python
def best_open_ended_trades_from(
    session: Session,
    source_station: ResolvedStation,
    request: RunRequest,
    *,
    available_credits: int,
    top_k: int,
    bubble_cache: dict[int, _LocalBubble],
) -> list[_HopCandidate]: ...
```

`_HopCandidate` carries the destination station, cargo plan, jump path,
practical score, and raw profit. The list is sorted by practical score
descending and truncated to `top_k`.

`_best_open_ended_plan` becomes the K=1 caller of this helper (plus the
single-hop diagnostics accumulation and `_assemble_result` call) when
`--hops == 1`. No behaviour change for the one-hop path.

`available_credits` is plumbed through rather than recomputed inside —
multi-hop needs to call the helper with a per-node budget, which is not
`request.starting_credits - request.insurance_reserve` anywhere past
hop 1.

### Piece C — Fixed terminal-hop evaluation

For `--from X --to Y --hops N`, hop N is a per-frontier-node fixed-pair
plan. Reuse the arithmetic in `_best_pair_plan`, called once per surviving
frontier node with that node's station as source and Y's resolved
stations as destinations.

A frontier node whose station cannot reach any Y station in `--jumps-per`
drops out at the final hop. If every surviving node drops out, raise a
multi-hop `NoReachableRoute`. If at least one node reaches Y but none
produce a profitable last hop, raise a multi-hop `NoProfitableTrades`.

Cost is bounded by frontier width × |Y stations|, which for a station Y
is 50 × 1 and for a system Y is 50 × (eligible stations in system).

### Piece D — Public entry rename

Rename `plan_onehop_route` to `plan_route`. Mechanical: the function
stays in `tradedangerous/planner/run_onehop.py` for this slice (the file
rename is a separate cleanup not worth bundling). `run_cmd.py` updates
its single call site and its single import.

Inside `plan_route`, dispatch on hop count:

```python
def plan_route(session, request):
    started = time.perf_counter()
    validate_run_request(request)
    validation_ms = _elapsed_ms(started)
    bubble_cache = {}
    if request.hops == 1:
        return _plan_single_hop(session, request, started, validation_ms, bubble_cache)
    return _plan_multi_hop(session, request, started, validation_ms, bubble_cache)
```

`_plan_single_hop` is the current four-way dispatcher (renamed from
the body of `plan_onehop_route`). `_plan_multi_hop` is new.

### Piece E — Validation widening

In `validation.py`:

- Drop `if request.hops != 1: raise UnsupportedRunShape(...)`.
- Add `if request.hops < 1: InvalidNumericOption("--hops must be at least 1.", option_name="--hops")`.
- Add `if request.hops > _MULTIHOP_MAX_HOPS: InvalidNumericOption("--hops exceeds the supported maximum.", option_name="--hops")`. Settle the constant: spec just says "excessive" — propose 25 as a sensible upper bound (any trader running more than 25 hops in one plan is using the wrong tool).
- Add `if request.hops > 1 and request.from_text is None: UnsupportedRunShape("Multi-hop currently requires --from.", option_name="--from")`.
- The existing `unsupported` table stays: `--direct`, `--towards`, `--loop`, `--via`, `--avoid`, `--unique`, `--loop-interval`, `--shorten`, `--checklist`, `--x52-pro` continue to reject.
- The `unsupported_non_zero` table stays unchanged: `--start-jumps`, `--end-jumps`, `--max-routes`, `--prune-score` continue to reject.

### Piece F — Failure messages

Extend `_planner_result_message` in `run_cmd.py` with a `request.hops > 1`
branch carrying three new wordings:

```text
"No profitable continuation was found after hop K of N from X with the current settings."
"No N-hop route from X to Y was profitable under the current settings."
"No reachable N-hop route from X to Y under the current jump settings."
```

Exact wording settles at implementation time; the families are: empty
mid-route frontier, all final hops unprofitable, no last-hop reach to Y.

The one-hop family stays unchanged. The multi-hop branch only activates
when `request.hops > 1`, so existing single-hop messages are unaffected.

### Piece G — Margin handling

`--margin` finally takes effect. At each frontier node, available credits
for the next hop's cargo buy are:

```text
available_credits = (starting_credits - insurance_reserve)
                  + (1 - margin) * accumulated_raw_profit
```

Margin only affects what the planner is willing to *spend*; raw profits
and the final credits readout stay raw. The renderer is unaffected by
margin — it displays accumulated raw profit and the actual ending
credits, not the margin-adjusted budget.

Margin is currently zero by default and the validation does not gate on
it; that stays. Tromador can pass `--margin 0.25` and have it shape
hop 2's cargo budget without changing what the route reports as profit.

### Piece H — Diagnostics

Add to `PlannerDiagnostics`:

```python
hops_planned: int = 1                                  # 1 for single-hop; N for multi-hop
multihop_frontier_widths: tuple[int, ...] = ()         # frontier size at each hop layer
multihop_expansions_examined: int = 0                  # total per-node expansions evaluated
```

Single-hop paths leave these at their defaults so the existing
diagnostics output stays unchanged.

---

## Probes Before Code

Three probes, run against the live database before any planner code is
written. Each settles a perf or correctness question; outcomes are
recorded inline in this document as they complete.

### P1 — Reach-set cost per source, repeated

**Question:** Multi-hop calls `_reachable_station_query` once per frontier
node per hop layer (50 sources × N-1 hops). The temp table behind it is
built per call. Is that cost bearable, or does the build need to be
factored behind a per-request memo keyed on `(source_system_id,
max_jumps_per_hop, max_ly_per_jump)`?

**Probe:** time 50 successive `_reachable_station_query` builds from
distinct source systems within a `--from Colonia/Jaques --jumps-per 2
--ly-per 20` context. Compare total wall-clock against one large reach
query covering all 50 sources at once.

**Decision rule:**
- If 50 calls < ~2 s total: leave per-call build; simplest code.
- If much higher: factor temp-table build behind a per-request memo on the source-system key.

The bubble cache from Slice 6 already amortises BFS across calls; this
probe is specifically about the SQL temp-table churn.

### P2 — Frontier width sweep at hop 1

**Question:** Is 50 a meaningful frontier width for representative
trading-corpus runs, or is the 50th-best route at hop 1 already noise?

**Probe:** for `--from Colonia/Jaques --jumps-per 2 --ly-per 20
--capacity 128 --credits 5000000`, take Slice 3's
`_best_open_ended_plan` candidate list, score every pair, sort, log the
top 100 practical scores. Inspect the curve.

**Decision rule:**
- If 50th best ≥ ~25% of 1st best: width = 50 is meaningful.
- If 50th best is already noise (< 5% of 1st best): consider dropping the default to 20 or 25.

This probe shapes the constant defaults; the structural search code is
the same either way.

### P3 — Last-hop `--to` reach feasibility

**Question:** For `--from X --to Y --hops N`, does the frontier need a
forward-feasibility bias so hop K's frontier favours nodes within
realistic distance of Y? Or is the natural high-profit ranking enough?

**Probe:** synthesise `--from Colonia/Jaques --to Sol --hops 3`
(well-separated, plenty of intermediate territory). At hop 2, count how
many of the 50 frontier nodes have Y's system inside their per-source
bubble — i.e. can complete in one hop.

**Decision rule:**
- If most can reach (≥ 50% of frontier): no special prefilter; rank by score and let the last-hop evaluation drop the unreachable nodes.
- If few can: add a soft prefilter to the frontier-trim — penalise nodes whose direct distance to Y exceeds `(hops_remaining * --jumps-per * --ly-per)`, so they fall out before the layer trim.

Slice 6's `is_system_pair_reachable` is the building block in either
direction; this probe is about whether the planner needs to *bias*
toward feasibility, not whether the check itself works.

---

## Acceptance Criteria

Slice 8 is complete when:

1. `trade run --from X --hops N` plans an N-hop route from X ending at a planner-chosen station, with buy/sell sequences and propagated credits.
2. `trade run --from X --to Y --hops N` plans an N-hop route from X ending at Y, or fails cleanly with a multi-hop `NoReachableRoute` if no such route exists.
3. `--margin` reduces the planner's available cargo budget at hop K+1 by `margin * profit_at_hop_K` (cumulative).
4. The renderer shows each hop in sequence with its own buy/sell/fly block. No renderer changes required to *read* multi-hop routes — the existing iteration over `route.hops` already does this. A per-hop "credits in hand" or per-hop cumulative-gain display is out of scope.
5. All Slice 1–7 shapes continue to work unchanged at `--hops 1`. Behavioural identity, not just compilation.
6. Validation rejects:
   - `--hops < 1`
   - `--hops > _MULTIHOP_MAX_HOPS`
   - `--hops > 1` with no `--from`
   - The deferred option list (`--via`, `--avoid`, `--towards`, `--loop`, `--unique`, `--loop-interval`, `--shorten`, `--routes != 1`, `--prune-score`, `--start-jumps`, `--end-jumps`, `--checklist`, `--x52-pro`, `--direct`) continues to reject cleanly. No silent acceptance.
7. `PlannerDiagnostics` exposes `hops_planned`, `multihop_frontier_widths` per layer, and `multihop_expansions_examined`.
8. Spot-checked against `--old` on `run-typical` (`--from Colonia/Jaques --capacity 128 --credits 5000000 --hops 2 --jumps-per 2 --ly-per 20`): new planner's route is valid, profitable, and materially faster (target: well under the ~30 s baseline).
9. Spot-checked against `--old` on the `--from X --to Y --hops N` shape for at least one well-separated origin/destination pair at N = 3.

---

## Out of Scope

Carried forward, not cut:

- `--via`, `--avoid`, `--towards`, `--loop`, `--unique`, `--loop-interval`, `--shorten`
- `--routes` top-N display, `--prune-score`, `--prune-hops`
- `--start-jumps`, `--end-jumps`
- Multi-hop with omitted `--from`, both endpoints omitted
- `--checklist`, `--x52-pro` (already deferred)
- Per-hop "credits in hand" or per-hop cumulative-gain renderer display
- `--bulk-tax-mode` user option (deferred from Slice 7)
- The `StationHasNoUsablePriceData` subclass wording cleanup (deferred from Slice 6)

---

## Deferred-Decision Notes

- **Beam-width as `--max-routes`.** Slice 8 hides both width constants. When `--max-routes` lands, settle which of the two it controls (or whether it is a third concept — for example, the number of *displayed* routes).
- **Oscillation A↔B.** Accepted under this scope. If A↔B is a genuinely strong trade pair, the frontier may settle there; `--unique` is the proper fix and will land in its own slice.
- **Beam vs. globally-optimal multi-hop.** Beam search is heuristic. With realistic widths and small N (≤ 5 typically), it should produce routes competitive with `--old`'s own heuristics. Regression on the benchmark corpus would be the trigger for a smarter pruning gate.
- **`run_onehop.py` file rename.** After Slice 8 the file name is misleading — it hosts the entry point for both one-hop and multi-hop dispatch. A rename to `run_route.py` (or moving the multi-hop body into its own file with the dispatcher in `__init__.py`) is reasonable, but is left out of this slice as pure churn.

---

## Slice 8 headline

Land an N-hop frontier-search planner with origin always named,
propagating credits hop-to-hop, honouring `--margin`, and rejecting the
wider multi-hop option family cleanly so the surface stays honest about
what is not yet supported.
