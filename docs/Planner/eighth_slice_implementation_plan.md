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

Hidden constants rather than wiring `--max-routes` now: the black-box
spec defines `--max-routes` as the maximum number of partial routes
retained between expansion stages, so its future mapping is
`_MULTIHOP_FRONTIER_WIDTH`. It is not the final display count and not
the per-node child count. Slice 8 still defers the user-facing option,
so `_MULTIHOP_FRONTIER_WIDTH` remains a constant for now;
`_MULTIHOP_EXPANSION_WIDTH` stays an internal fan-out cap.

The search is heuristic, not globally optimal. A truly optimal N-hop
plan over the full reachable graph is combinatorial; beam search with
realistic widths produces routes comparable to `--old`'s heuristics
while staying fast. Quality is verified against `--old` on the
benchmark corpus; if it regresses, the natural follow-up is a smarter
per-hop pruning gate (related to the deferred `--prune-score`).

---

## Pieces

### Piece A — Frontier model and search loop

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

Intermediate destinations are not terminal recommendations. For hops
1..N-1, a destination must also be viable as the source of a later hop:
supply-only stations may start routes, demand-only stations may end
routes, but mid-route stations must have usable onward selling data under
the current filters. This is a frontier-quality constraint, not a
global station rule — the final hop may still end at a demand-only
station.

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
            terminal_hop=False,
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
        fixed_pair_plan_from(
            node,
            resolved_to_stations,
            available_credits=node.available_credits,
            terminal_hop=True,
        )
        for node in frontier
    ]
else:
    finalists = []
    for node in frontier:
        children = best_open_ended_trades_from(
            session, node.station, request,
            available_credits=node.available_credits,
            top_k=1,             # only need each node's single best terminal hop
            terminal_hop=True,
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
    terminal_hop: bool,
    bubble_cache: dict[int, _LocalBubble],
) -> list[_HopCandidate]: ...
```

`_HopCandidate` carries the destination station, cargo plan, jump path,
practical score, and raw profit. The list is sorted by practical score
descending and truncated to `top_k`.

`terminal_hop` controls whether demand-only destinations are allowed.
When `False`, the helper must keep only destination stations that are
also viable onward sources under the current source-side filters. When
`True`, the helper may end at any valid destination station.

`_best_open_ended_plan` becomes the K=1 caller of this helper with
`terminal_hop=True` (plus the single-hop diagnostics accumulation and
`_assemble_result` call) when `--hops == 1`. No behaviour change for the
one-hop path.

`available_credits` is plumbed through rather than recomputed inside —
multi-hop needs to call the helper with a per-node budget, which is not
`request.starting_credits - request.insurance_reserve` anywhere past
hop 1. That means the data gateway functions must also accept
`available_credits` explicitly:

```python
fetch_open_ended_trade_candidates(..., available_credits=available_credits)
fetch_station_pair_candidates(..., available_credits=available_credits)
```

Single-hop callers pass the initial trade budget. Multi-hop callers pass
the frontier node's budget.

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
- Add `if request.margin < 0 or request.margin > 1: InvalidNumericOption("--margin must be between 0 and 1.", option_name="--margin")`. Negative margin invents extra capital; values above 1 make accumulated profit reduce buying power below the base budget.
- The existing `unsupported` table stays: `--direct`, `--towards`, `--loop`, `--via`, `--avoid`, `--unique`, `--loop-interval`, `--shorten`, `--checklist`, `--x52-pro` continue to reject.
- The `unsupported_non_zero` table stays unchanged except for `--prune-hops`: `--start-jumps`, `--end-jumps`, `--max-routes`, `--prune-score` continue to reject when non-zero.
- Add `if request.prune_hops != 3: UnsupportedRunShape("--prune-hops is not supported for this planner slice.", option_name="--prune-hops")`. The parser default is 3, so only explicit non-default use is rejected.

Mirror the deferred-option checks in `validateRunArgumentsFast()` where they already exist so command-layer early rejection and planner validation remain aligned.

### Piece F — Partial-route failures and failure messages

A multi-hop search may fail after already finding useful completed hops.
Do not discard that work. If at least one trade hop has completed before
the frontier gets stuck, return the best partial route found so far with
a clear warning that the requested N-hop route was not completed.

Examples:

```text
WARNING: Requested 5 hops, but no viable continuation was found after hop 3.
Showing the best 3-hop partial route found.

WARNING: Requested 4 hops to Lave, but no reachable/profitable final hop was found.
Showing the best 3-hop partial route found.
```

This is not an extra diagnostic pass. The partial route is reconstructed
from the existing best frontier node, so it uses state already produced
by normal search. If no trade hop was completed, there is no partial
route to show and the command raises the normal no-result failure.

Extend `_planner_result_message` in `run_cmd.py` only for true no-result
multi-hop failures. Partial-route failures should travel through the
normal `RunResult` path with `RunResult.warnings`, not through
`PlannerResultError`.

The multi-hop planner must attach enough structured context to warnings
or raised failures for the command layer and renderer to describe what
happened without parsing message text. Use the existing
`PlannerFailure.details` mapping for raised no-result failures and
`RunResult.warnings` for rendered partial routes. Useful context:

```text
completed_hops  # number of completed trade hops in the partial route
requested_hops  # requested route length
phase           # "expansion" or "final"
reason          # "no_viable_continuation", "no_reachable_route", or "no_viable_trade"
```

Do not run extra diagnostic probes solely to distinguish "profitable but
unaffordable" from "no profitable trade". That distinction is deliberately
not a separate `trade run` user-facing diagnosis. If affordability-only
knowledge falls out of the normal candidate/cargo path for free, it may
be counted for debug diagnostics, but the user-facing failure remains in
the broader no-viable-trade family.

The one-hop family stays unchanged. The multi-hop branch only activates
when `request.hops > 1`, so existing single-hop messages are unaffected.

### Piece G — Margin handling

`--margin` finally takes effect. At each frontier node, available credits
for the next hop's cargo buy are:

```text
base_trade_budget = starting_credits - insurance_reserve
trusted_profit = floor((1 - margin) * accumulated_raw_profit)
available_credits = base_trade_budget + trusted_profit
```

The value passed to candidate generation and cargo optimisation must be
an integer. Do not let a fractional margin leak a float into cargo
fitting: the optimiser relies on integer credit arithmetic.

Margin only affects what the planner is willing to *spend*; raw profits
and the final credits readout stay raw. The renderer is unaffected by
margin — it displays accumulated raw profit and the actual ending
credits, not the margin-adjusted budget.

Validation must reject negative margins and margins greater than 1 before
planning. The default remains zero. Tromador can pass `--margin 0.25`
and have it shape hop 2's cargo budget without changing what the route
reports as profit.

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

### P1 — Per-node expansion cost, repeated

**Question:** Multi-hop calls the open-ended expansion helper once per
frontier node per hop layer. Is the full per-node expansion cost
bearable at the planned beam width, or does the helper need earlier
bounding before cargo optimisation?

**Probe:** build a representative hop-1 frontier from a dense inhabited
Bubble origin, not from the old Colonia benchmark corpus. Start with a
candidate such as:

```text
trade run --from Sol --jumps-per 2 --ly-per 30 --capacity 128 --credits 5000000
```

If the current database makes Sol a poor probe seed, choose another
well-populated Bubble origin and record the reason. Then time 50 calls
to `best_open_ended_trades_from(...)` from the resulting frontier source
stations with `top_k=_MULTIHOP_EXPANSION_WIDTH` and
`terminal_hop=False`.

Record, per call and in total:

```text
elapsed_ms
reachable/temp-table build time
candidate row count
grouped station-pair count
cargo optimiser calls
children returned
```

Also record the same counters for `terminal_hop=True` on the final-hop
shape, because final hops may admit demand-only stations that
intermediate hops deliberately reject.

**Decision rule:**
- If 50 full expansions fit comfortably inside the Slice 8 performance
  target, keep the simple per-node helper.
- If expansion cost is dominated by cargo optimisation across too many
  grouped pairs, add an early bound/top-K gate before full cargo
  optimisation.
- If expansion cost is dominated specifically by reachable temp-table
  churn, factor the reachable build behind a per-request memo keyed on
  `(source_system_id, max_jumps_per_hop, max_ly_per_jump)`.

The bubble cache from Slice 6 already amortises BFS across calls; this
probe measures the real hot path: reachable set, market fetch, pair
grouping, cargo fitting, scoring, and trimming.

### P2 — Frontier width sweep at hop 1

**Question:** Is 50 a meaningful frontier width for representative
Bubble multi-hop runs, or is the 50th-best route at hop 1 already noise?

**Probe:** using the same non-Colonia seed selected for P1, take the
candidate list that would feed `best_open_ended_trades_from(...)`, score
every grouped station pair, sort, and log the top 100 practical scores.
Inspect the curve.

**Decision rule:**
- If 50th best ≥ ~25% of 1st best: width = 50 is meaningful.
- If 50th best is already noise (< 5% of 1st best): consider dropping the default to 20 or 25.

This probe shapes the constant defaults; the structural search code is
the same either way.

### P3 — Last-hop `--to` reach feasibility

**Question:** For `--from X --to Y --hops N`, does the frontier need a
forward-feasibility bias so hop K's frontier favours nodes within
realistic distance of Y? Or is the natural high-profit ranking enough?

**Probe:** first choose a named Bubble origin/destination pair that is
locally verified reachable within the planned hop budget. Candidate
examples are Sol -> Lave or Sol -> Shinrarta Dezhra, but do not trust
memory here: preflight the pair with the current database and Slice 6
reachability helpers before using it as a probe case.

Use a command shape like:

```text
trade run --from Sol --to Lave --hops 3 --jumps-per 2 --ly-per 30 --capacity 128 --credits 5000000
```

Adjust the named destination or jump settings if the preflight says the
pair is not reachable in three trade hops. At hop 2, count how many of
the 50 frontier nodes have Y's system inside their per-source bubble —
i.e. can complete in one final trade hop.

**Decision rule:**
- If most can reach (≥ 50% of frontier): no special prefilter; rank by score and let the last-hop evaluation drop the unreachable nodes.
- If few can: add a soft prefilter to the frontier-trim — penalise nodes whose direct distance to Y exceeds `(hops_remaining * --jumps-per * --ly-per)`, so they fall out before the layer trim.

Slice 6's `is_system_pair_reachable` is the building block in either
direction; this probe is about whether the planner needs to *bias*
toward feasibility, not whether the check itself works.

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

**Probe:** first choose a named origin/destination pair that is locally
verified reachable within the planned hop budget. Candidate examples are
Sol -> Lave or Sol -> Shinrarta Dezhra, but do not trust memory here:
preflight the pair with the current database and Slice 6 reachability
helpers before using it as a probe case.

Use a command shape like:

```text
trade run --from Sol --to Lave --hops 3 --jumps-per 2 --ly-per 30 --capacity 128 --credits 5000000
```

Adjust the named destination or jump settings if the preflight says the
pair is not reachable in three trade hops. At hop 2, count how many of
the 50 frontier nodes have Y's system inside their per-source bubble —
i.e. can complete in one final trade hop.

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
2. `trade run --from X --to Y --hops N` plans an N-hop route from X ending at Y. If the search gets stuck after at least one completed hop, it renders the best partial route found with a warning that the requested N-hop route was not completed. If no hop can be completed, it fails cleanly with the appropriate no-result message.
3. `--margin` reduces the planner's available cargo budget at hop K+1 by `margin * profit_at_hop_K` (cumulative).
4. The renderer shows each hop in sequence with its own buy/sell/fly block and renders any `RunResult.warnings` before the route. A per-hop "credits in hand" or per-hop cumulative-gain display is out of scope.
5. All Slice 1–7 shapes continue to work unchanged at `--hops 1`. Behavioural identity, not just compilation.
6. Validation rejects:
   - `--hops < 1`
   - `--hops > _MULTIHOP_MAX_HOPS`
   - `--hops > 1` with no `--from`
   - The deferred option list (`--via`, `--avoid`, `--towards`, `--loop`, `--unique`, `--loop-interval`, `--shorten`, `--routes != 1`, `--prune-score`, `--start-jumps`, `--end-jumps`, `--checklist`, `--x52-pro`, `--direct`) continues to reject cleanly. No silent acceptance.
7. `PlannerDiagnostics` exposes `hops_planned`, `multihop_frontier_widths` per layer, and `multihop_expansions_examined`.
8. Spot-checked against `--old` on a non-Colonia seeded Bubble run selected during probes, for example `--from Sol --capacity 128 --credits 5000000 --hops 2 --jumps-per 2 --ly-per 30`: new planner's route is valid, profitable, and materially faster than the legacy path on the same command.
9. Spot-checked against `--old` on the `--from X --to Y --hops N` shape for at least one locally preflighted, reachable Bubble origin/destination pair at N = 3.

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
