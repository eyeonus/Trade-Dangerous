# Slice 10 Implementation Plan — Open-Origin Multi-Hop

## Status

Planned.

## Purpose

Slice 10 adds one new route shape: **multi-hop to a fixed destination with the
origin chosen by the planner**.

```text
trade run --to Y --hops N        (--from omitted, N >= 2)
```

This is the multi-hop twin of Slice 4 (open-origin one-hop). Known-origin
multi-hop (`--from X --hops N`, with or without `--to`) already works from
Slice 8. After this slice the only multi-hop shape still missing is the fully
unanchored one (`--hops N` with both endpoints omitted), which stays deferred.

No new user options. No renderer or DTO changes — the result is an ordinary
multi-hop route; only the way it is *found* is new.

---

## The shape and where it slots in

`plan_route` (run_route.py:79) already splits the work:

```text
hops == 1  ->  _plan_single_hop   (four-way endpoint dispatch)
hops  > 1  ->  _plan_multi_hop     (known-origin only, today)
```

`_plan_single_hop` already dispatches all four endpoint combinations. The
multi-hop branch does not — it hands everything to `_plan_multi_hop`, which
unconditionally resolves `--from`. Slice 10 gives the `hops > 1` branch the
same endpoint dispatch the one-hop branch has:

```text
--from set                 ->  _plan_multi_hop            (existing)
--from omitted, --to set   ->  _plan_open_origin_multi_hop (new)
both omitted               ->  rejected in validation     (deferred shape)
```

### Validation gate change

`validation.py:42` currently rejects every origin-less multi-hop:

```python
if request.hops > 1 and request.from_text is None:
    raise UnsupportedRunShape(
        "Multi-hop currently requires --from.",
        option_name="--from",
    )
```

Relax it to reject only the *both-omitted* multi-hop, which remains deferred:

```python
if request.hops > 1 and request.from_text is None and request.to_text is None:
    raise UnsupportedRunShape(
        "Multi-hop requires --from or --to.",
    )
```

Everything else in `validate_run_request` is unchanged. The deferred modifiers
(`--towards`, `--loop`, `--via`, `--avoid`, `--unique`, `--shorten`,
`--start-jumps`, `--end-jumps`, the pruning controls, `--routes > 1`) stay
rejected exactly as now.

---

## Search design — grow the route backward from Y

When only the destination is fixed, there are two ways to search. We choose
the second.

**Forward from candidate origins (rejected).** Pick possible start stations
near Y, then push routes forward toward Y. For an N-hop route "near Y" is a
sphere of radius `N * jumps-per * ly-per` — large at any decent range.
Materialising and evaluating every origin in it is, in effect, the expensive
unanchored search we are deliberately deferring.

**Backward from Y (chosen).** Start at Y and walk the route *backwards*:

```text
seed       :  Y's eligible destination stations
layer 1    :  stations that profitably sell INTO Y  (reachable, one hop)
layer 2    :  stations that profitably sell into a layer-1 station
   ...
layer N    :  the origin emerges as the start of the best backward chain
```

Each layer is bounded to a single hop's reach — a small reachable set,
beam-trimmed before the next layer. The cost profile is the same as the
known-origin multi-hop already running; there is no giant origin sphere built
up front.

This is the exact mirror of the existing forward open-destination multi-hop
(`--from X --hops N`), which wanders outward from a fixed origin with no
envelope, bounded only by the beam. Backward open-origin wanders outward from
a fixed Y the same way. **No destination envelope is involved** — the envelope
is a feature of having two fixed points (or heading toward one fixed point
from a fixed start); open-origin has only Y fixed and moves away from it.

### The backward primitive already exists

The per-node expansion the backward search needs is "who profitably sells into
this station?" — which is exactly what
`fetch_open_ended_trade_candidates(open_role="source")` already does
(data_gateway.py:763): the fixed endpoint takes the demand role, the chosen
endpoint takes the supply role, and the reachable supply set is a **subquery**,
never a materialised id list (data_gateway.py:759-768, 712-719).

The forward path wraps that fetch in `best_open_ended_trades_from`
(run_route.py:369), which groups by destination, fits cargo, scores, sorts,
and lazily computes jump paths for the top-K. Slice 10 adds the mirror,
`best_open_ended_trades_into`, which:

- calls `fetch_open_ended_trade_candidates(open_role="source")` with the
  frontier node's station as the single fixed **destination** and the node's
  system as the anchor;
- groups candidates by **source** station (the chosen side);
- fits cargo and scores each pair — the ls-penalty applies to the fixed node's
  `ls_from_star`, which is the hop's true destination, matching forward
  semantics;
- sorts by practical score and computes jump paths for the top-K survivors
  only.

It returns the chosen **source** station per candidate, where the forward
helper returns the chosen destination. The two are direction-mirrors; they
share the cargo optimiser, the scorer, the jump-path lookup, and the bubble
cache.

### Intermediate-node viability — mirror of `terminal_hop`

Forward search uses `terminal_hop=False` on intermediate hops so a demand-only
station cannot occupy a frontier slot that must be a viable onward *source*;
the check is a correlated `EXISTS` on onward supply, attached to the open
(destination) side (data_gateway.py:814-837).

Backward search needs the mirror: an intermediate backward node (one that will
be expanded further back) must be a viable onward *buyer*, so the next hop can
sell into it. That is an `EXISTS` on onward *demand*, attached to the open
(source) side. The origin layer (the last backward layer, not expanded again)
needs no such check — the origin is a pure source.

So the existing `terminal_hop` logic in `fetch_open_ended_trade_candidates`
generalises cleanly: attach the onward-viability `EXISTS` to **whichever side
is the open side**, checking the role that side needs for the *next* hop —
onward supply for an open destination (forward), onward demand for an open
source (backward). This keeps the check in SQL, as a correlated `EXISTS` on the
`StationItem` primary key.

### Money flows forward — the credit-correction pass

This is the one genuinely new wrinkle, and the trickiest part of the slice.

Credits compound *forward*: you start with your trade budget at the origin and
each hop's profit (after the `--margin` haircut) funds the next hop's buy.
`_make_child_node` (run_route.py:1067) does this forward, because the forward
search knows the running budget at every node.

A backward search does **not** — it discovers the origin last, so at the moment
it picks a source it cannot know the budget that will be available there. We
handle this in two stages:

1. **Backward expansion is credit-optimistic.** Cargo is fitted as if money is
   no object (capacity / supply / demand bound only), so the beam ranks on an
   upper-bound profit. `--max-price` and all other SQL filters still apply; only
   the affordability pre-filter (`supply_price <= available_credits`,
   data_gateway.py:777) is relaxed for this phase by passing a budget high
   enough not to bind.

2. **A forward credit-correction pass finalises each finished chain.** When a
   backward chain reaches N hops, walk it forward from the emerged origin,
   re-fitting cargo per hop with the *real* running budget (the
   `base_trade_budget + floor((1 - margin) * accumulated_profit)` rule, reused
   from `_make_child_node`). This produces the true per-hop cargo, profit, and
   credit balance, and builds the `PlannedHop`s. Run it over each finalist and
   pick the best corrected one.

Re-fitting can **fail**, and the pass must handle that rather than assume the
forward walk always succeeds. A hop chosen optimistically may be unaffordable
under the real running budget; `optimise_cargo` then raises `NoProfitableTrades`
(its hard quantity cap includes `available_credits // buy_price`). So:

- Correct finalists in descending optimistic score. For each, walk forward from
  the emerged origin and re-fit every hop against the real running budget.
- If any hop raises `NoProfitableTrades`, **discard that finalist** and move to
  the next.
- A finalist is eligible only if *every* hop re-fits. Among eligible finalists,
  pick the highest **corrected** practical score — correction can reorder them,
  so score the corrected chains, not the optimistic ones.
- The same discard-and-fall-back rule applies to partial-route reconstruction:
  a shorter chain is returned only if all of its hops re-fit.
- If no finalist and no partial survives correction, the result is a clean
  no-profitable-trade / no-route failure — never a crash, never an over-stated
  route. That is the same family the near-broke commander falls into, out of
  scope under the settled "no separate no-affordable-cargo diagnosis" decision;
  the planner still has to degrade cleanly.

Correctness guarantee, restated: any route returned has had every hop re-fitted
and confirmed affordable under the real forward budget. The remaining
imperfection is only that the beam *ranked* on optimistic profit during
expansion, so the globally-best route could in principle be trimmed before it
reaches the finalist set. For normal trading budgets credit rarely binds, so
this is a quality nuance well inside the spec's "comparable practical value, not
exact optimum" standard.

To keep correction cheap (no re-querying), each backward node carries the chosen
pair's `TradeCandidate` tuple — the new `hop_candidates` field described under
Chain mechanics — so `optimise_cargo` re-runs against the real budget directly.
The candidate lists are per-pair and small; the beam is bounded.

### Chain mechanics

The frontier node dataclass `_FrontierNode` (run_route.py:55) is reused with
**one addition**: a trailing optional field `hop_candidates`, holding the
`TradeCandidate` tuple for the hop that arrived at the node (with the matching
field on `_HopCandidate`, the expansion result the node is built from). It
defaults to `None`, so the forward path and its `_make_child_node` are
untouched — forward cargo is fitted against the correct budget at expansion time
and is never re-fitted. The backward path populates it, because the
credit-correction pass needs the original candidates to re-run `optimise_cargo`,
not the optimistic `CargoPlan` (which `optimise_cargo` cannot take as input).
The build and reconstruct helpers differ by direction:

- **Seed** is Y's stations at `hop_index = 0` with no cargo (mirror of the
  forward origin seed).
- **Backward child:** expanding from node `D` finds source `S` selling into
  `D`; the child node has `station = S`, `parent = D`, `hop_index =
  parent.hop_index + 1`, carrying the hop `S -> D`.
- **Reconstruction is naturally origin-first.** Walking a finished node's parent
  chain yields `[origin, ..., S1, Y]` already in route order — no reversal,
  unlike the forward path which reverses. Each non-seed node carries the hop
  that departs it toward its parent.

These need a backward-aware sibling of `_make_child_node` /
`_reconstruct_route`. Following the Slice 5 precedent (the unanchored path was
added as a separate body rather than parameterising the open-ended search,
because it differs in kind), the backward build/reconstruct logic is written as
its own small helpers sharing the `_FrontierNode` struct, rather than threading
a direction flag through the forward helpers. In practice the
forward-correction pass *is* the reconstruction — it walks origin-to-Y building
`PlannedHop`s while re-fitting cargo — so there is one combined
`_reconstruct_open_origin_route` rather than two passes.

### Beam, partial routes, diagnostics

- Beam widths reuse `_MULTIHOP_EXPANSION_WIDTH` / `_MULTIHOP_FRONTIER_WIDTH`
  (both 50). Trim each backward layer by accumulated practical score, mirroring
  the forward trim. Source-system diversity on the trim (the Slice 8
  fixed-terminal refinement) can be mirrored on the source side if a probe shows
  near-duplicate clustering; default to the plain score trim first and only add
  diversity if the route quality needs it.
- Partial routes: if a backward layer collapses before N hops, return the best
  completed shorter chain ending at Y, mirroring `_best_partial_node` and the
  forward `PartialRouteWarning` branches.
- Emit the same diagnostics structures the forward multi-hop emits
  (`LayerStats`, `ExpansionStats`, `FinalHopStats` where meaningful) so
  `_multihop_result` and the renderer treat both paths identically.

---

## SQL-first boundary

Where the work lives, restated for this slice:

**In SQL (the heavy lifting):**

- Per-layer candidate generation — supply/demand rows with the price, quantity,
  age and `--max-price` predicates and the station filters — via the existing
  `fetch_open_ended_trade_candidates`.
- Reachability narrowing — the reachable source set stays a subquery
  (`_reachable_station_query`), never an id list handed back as a literal
  `IN (...)`.
- Intermediate-node onward viability — a correlated `EXISTS` on the open side
  (onward demand for backward), as above.

**In Python (bounded, already narrowed — the allowed carve-out):**

- The beam: looping the trimmed frontier, scoring with the ls-penalty curve,
  trimming to top-N. Bounded width, fired one well-shaped query per node — the
  same orchestration shape Slice 8 already uses.
- Cargo fitting (`optimise_cargo`) — already Python everywhere.
- The forward credit-correction pass — a walk over <= N hops of a chosen chain.
  Inherently forward and sequential; not a set operation SQL would do better.

---

## Out of scope (deferred, not cut)

- Fully unanchored multi-hop (`--hops N`, both endpoints omitted) — the next
  shape slice.
- All route modifiers and search/display controls still gated in validation.
- Source-system diversity trim, unless a quality probe shows it is needed.

---

## Validation plan

No automated harness (project decision). Use `--old` (which supports an omitted
`--from` for multi-hop) as a comparison **probe, not an oracle** — route
validity is primary, not parity with `--old`.

This week's documented false regression is exactly why: `--old` accepted a route
built on a dormant buy-side row with `demand_units = 1`, which the new planner
correctly rejects under `_MIN_MEANINGFUL_DEMAND = 2`. A higher `--old` profit
can therefore be a legacy route the game cannot actually fill, not a real
regression.

Smoke commands (final values chosen against the live DB at implementation
time; `--age` tuned to local data freshness):

```text
# Open-origin multi-hop into a known hub, a few hops.
trade run --to "Lave/Lave Station" --hops 3 \
    --capacity 720 --credits 200000000 --jumps-per 3 --ly-per 30

# Same, destination given as a system (expands to Y's stations).
trade run --to "Sol" --hops 2 \
    --capacity 720 --credits 200000000 --jumps-per 3 --ly-per 30

# Compare practical value and runtime against the legacy path.
trade run --old --to "Lave/Lave Station" --hops 3 \
    --capacity 720 --credits 200000000 --jumps-per 3 --ly-per 30
```

Checks:

- Route is valid: every hop reachable under the jump settings, every hop a real
  buy/sell, route ends at a Y station.
- Route valid and materially faster wall-clock, with comparable-or-better
  practical value allowing market drift.
- If `--old` reports higher profit, do **not** call it a regression until the
  legacy route's hops have been checked against current planner rules —
  `_MIN_MEANINGFUL_DEMAND`, the bulk-sale-tax cap, and `--max-price`. Only a
  legacy route whose every hop obeys those and still out-profits the new route
  is a genuine quality regression.
- A low `--credits` run still returns a flyable route (the forward pass binds
  cargo to the real budget) rather than an over-stated one.
- Partial-route warning fires cleanly when N hops cannot be completed.
- Existing shapes unchanged: re-run a known-origin multi-hop and the run-short
  Colonia benchmark; behaviour identical.
- `--from`-and-`--to` and both-omitted multi-hop behave as before (the latter
  still rejected, no traceback).

---

## Implementation order

1. Save this plan.
2. Relax the multi-hop validation gate to reject only both-omitted at N > 1.
3. Add the endpoint dispatch to the `hops > 1` branch of `plan_route`.
4. Generalise the `terminal_hop` onward-viability `EXISTS` in
   `fetch_open_ended_trade_candidates` to attach to the open side by role.
5. Add `best_open_ended_trades_into` (the backward per-node primitive).
6. Add `_plan_open_origin_multi_hop`: backward seed from Y, credit-optimistic
   beam expansion, finalist collection, the forward credit-correction
   reconstruction, partial-route handling, diagnostics.
7. Local smoke probes: open-origin (station and system `--to`), `--old`
   comparison, low-credits, partial-route, and the unchanged-shapes regression
   set.
8. Update `SLICE_SUMMARY.md` (add the Slice 10 entry) and fold in the deferred
   carrier-fiction / `--max-price` cross-link noted below — docs after the code
   is accepted.
9. Produce `docs/Planner/tenth_slice_completion_report.md` after sign-off.

---

## Files expected to change

```text
tradedangerous/planner/validation.py     # relax the gate
tradedangerous/planner/run_route.py       # dispatch + backward path + helpers
tradedangerous/planner/data_gateway.py    # generalise terminal_hop onward check
```

Renderer, DTOs, request, and parser are expected to be untouched — no new
options, same route shape out.

Documentation:

```text
docs/Planner/tenth_slice_implementation_plan.md
docs/Planner/SLICE_SUMMARY.md
docs/Planner/tenth_slice_completion_report.md
```

---

## Noted for later

- **Envelope for an open *source*.** The reachable-set envelope is currently
  documented as meaningful only for an open destination. Open-origin multi-hop
  does not need it, so no change now; if a future shape fixes a second point
  while the origin is open, the envelope would need wiring to the source side
  too.
