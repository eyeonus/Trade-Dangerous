# Slice 11 Implementation Plan — Unified Single-Anchor Open Multi-Hop

## Status

Complete. Implemented on `release/v1` (commits `317644e3`, `1bf71899`,
`af352f8f`); see `eleventh_slice_completion_report.md`.

## Purpose

Two outcomes, one change.

1. **Fix the forward-open hang.** `trade run --from X --hops N` with no `--to`
   does not finish at realistic depth. Measured: a 2-hop / 2-jump case took
   **3m 37s**; the original 3-hop / 3-jump report ran **30+ minutes without
   completing**. The backward mirror (`--to Y`, same filters) finishes in
   ~2 min.

2. **Unify the two single-anchor open multi-hop searches** — open-destination
   (`--from X`, no `--to`) and open-source (`--to Y`, no `--from`) — into one
   direction-parameterised engine, removing the near-duplicate expansion,
   child-build, reconstruct, and partial-route code.

The fix and the unification are the *same* work. The forward-open path is slow
because it fits cargo against the real running budget during expansion, which
forces branch-and-bound on nearly every candidate pair. The backward open-source
path already solves exactly this: it fits cargo optimistically (a non-binding
budget, so the cheap one-pass cargo fill is always taken) and reconciles the real
budget once, at the end, with a forward credit-correction pass. Generalising that
backward design to serve both directions fixes the hang *and* collapses the
duplication.

No new user options. No new route shape — both shapes already exist and are
already allowed through validation; only the way the open-destination shape is
*found* changes.

## Root cause (measured, not assumed)

The directional asymmetry is entirely the cargo-fitting path:

- **Forward open-destination** fits against the per-node real running budget
  (`best_open_ended_trades_from`, called from `_plan_multi_hop` with
  `available_credits=node.available_credits`). At a low credits-to-capacity
  ratio (`--credits 1000000 --capacity 720` ≈ 1,389 cr per ton of hold)
  `_credit_cannot_bind` is false, so branch-and-bound runs on almost every pair.
- **Backward open-source** fits against `optimistic_credits = capacity ×
  1,000,000,000` (`best_open_ended_trades_into`), so `_credit_cannot_bind` is
  always true and every fit takes the one-pass fast path.

The 2-hop / 2-jump diagnostic confirmed it directly:

```text
Total: 217830ms (search 217795ms)
Expansion: 51 calls, 69682 candidate rows, 7462 pairs, 7462 cargo calls
Cargo: 2125 fast-path, 5337 branch-and-bound
Layer 1: ... kept 50 (511ms)
```

- The cost is **branch-and-bound CPU**, not SQL: only 69,682 rows were fetched,
  Layer 1 was 511 ms, and `time` showed `real ≈ user`, `sys 0.6s` — single-
  threaded compute, not I/O. The ~217 s is the final hop's 50 expansion calls
  running ~5,300 branch-and-bound fits at ~40 ms each.
- The expansion helper fits **every** candidate pair exactly, purely to rank
  them, then keeps the single best per node at the final hop (top 50 at
  intermediate hops). ~5,000 exact fits to choose ~50 children.

Why it was never caught: the only multi-hop run validated in Slice 8 was
fixed-terminal (`--from "Sol" --to "Lave"`), which is bounded by the destination
envelope and was run at `--jumps-per 2` with a high credit headroom
(`--capacity 128 --credits 5000000` ≈ 39 K cr/ton, so the fast path stays
available). Every protective factor in the tested case — the envelope, the
smaller bubble, the high credit headroom — is absent from the open-destination
shape at depth. The shape was claimed as supported but only its fixed-terminal
sibling was exercised.

## Scope

**In:** the two single-anchor open shapes, `N >= 2`.

```text
trade run --from X  --hops N   (no --to)   -> open destination
trade run --to   Y  --hops N   (no --from) -> open source   (already this way)
```

**Out, and untouched:**

- **Fixed-terminal `--from X --to Y --hops N`.** Two anchors, a destination
  envelope, the destination-system diversity trim, and a fixed-pair final hop.
  It is validated (Sol → Lave, ~32 s) and fast. Folding it into the generic
  engine would force the engine to carry envelope/diversity machinery the open
  shapes do not need, and would put the one validated multi-hop case at risk for
  no gain. It stays on its current real-budget path.
- **Fully unanchored multi-hop** (`--hops N`, both endpoints omitted) — still
  rejected in validation, deferred to a later shape slice.
- **The shared bubble row-volume cost** (the ~2 min the backward path also
  spends pulling and grouping the reachable bubble's market rows). Not the
  bottleneck at realistic filters — the 2-hop case fetched only ~70 K rows. A
  separate, optional follow-up (proxy ranking / SQL row-narrowing in the
  candidate fetch), not part of this slice.

## Dispatch

The `hops > 1` branch of `plan_route` gains a three-way endpoint dispatch that
mirrors the one-hop dispatcher (`_plan_single_hop`):

```text
--from X --to Y   ->  _plan_multi_hop            (fixed-terminal; unchanged)
--from X          ->  generic engine, open_role="destination"   (was the slow path)
--to   Y          ->  generic engine, open_role="source"        (was _plan_open_origin_multi_hop)
both omitted      ->  rejected in validation     (already so)
```

That symmetry with the one-hop dispatch (fixed-pair / open-source / open-dest /
unanchored) is a sign the seams sit in the right place.

`_plan_multi_hop` loses its open-terminal (`to_system_xyz is None`) branch — it
is now only ever called with `--to` set, so the `if to_system_xyz is not None`
conditionals inside it collapse to always-true and can be simplified. That is a
secondary tidy, not a behavioural change.

## The generic engine

Generalise the current `_plan_open_origin_multi_hop` into one engine
parameterised by `open_role` (`"source"` or `"destination"`). It seeds at the
**anchored** endpoint and grows the chain one hop's reach at a time toward the
**open** end:

- **Seed** — the anchor's eligible stations at `hop_index = 0`, no cargo.
  Open-source seeds on `--to`'s stations (as today); open-destination seeds on
  `--from`'s stations.
- **Expand** — per frontier node, the direction-neutral optimistic primitive
  (below) returns the top-K trades on the open side, cargo fitted against the
  non-binding optimistic budget, scored with the ls-penalty on the *fixed*
  node's `ls_from_star`, jump paths computed for survivors only.
- **Trim** — per-station coalescing (keep the best optimistic chain per emerged
  open-side station) then a score trim to `_MULTIHOP_FRONTIER_WIDTH`. This is the
  backward path's existing trim; it is a strict improvement over the forward
  open-terminal path's plain top-N trim and works for both directions.
- **Final layer** — widened (`top_k = _MULTIHOP_EXPANSION_WIDTH`,
  `terminal_hop=True`) so correction has several candidates per node, not one.
  **Quality bonus for the forward shape:** its current final hop keeps only the
  single best trade per node (`top_k=1`); inheriting the widened, correction-
  aware final layer means it finds better routes, not just finds them faster.
- **Correct** — the forward credit-correction pass re-fits each finalist chain
  hop by hop against the real running budget (`base_trade_budget + floor((1 -
  margin) * accumulated_profit)`), keeps only chains where every hop re-fits,
  and picks the highest *corrected* practical score. Bounded by
  `_OPEN_ORIGIN_CORRECTION_WIDTH` with the existing exact early-stop.
- **Partial routes** — the correction-aware partial helper, returning the best
  completed shorter chain that survives correction.

### The direction-neutral optimistic primitive

`best_open_ended_trades_into` becomes the single optimistic per-node primitive,
parameterised by `open_role` (proposed neutral name to settle at
implementation: `best_open_ended_hop_candidates`). For each frontier node it:

- calls `fetch_open_ended_trade_candidates(open_role=...)` with the node as the
  single fixed endpoint on the opposite role;
- groups candidates by the **open** side (the side the planner chooses);
- fits cargo against the optimistic budget (fast path), scores, sorts, and
  computes jump paths for the top-K survivors only;
- returns each survivor's chosen open-side station plus the per-pair
  `TradeCandidate` tuple (`hop_candidates`) for the correction re-fit.

`best_open_ended_trades_from` survives, but **only** for the fixed-terminal
intermediate hops (real budget + the destination envelope). The minor remaining
overlap between it and the optimistic primitive is acceptable: they differ in
budget mode and in carrying the envelope, and keeping them apart is clearer than
one helper behind several mode flags.

## What stays direction-aware

It is not literally one identical function. Three things depend on direction,
and collapse to roughly one `open_role` parameter threaded through three places:

1. **The fetch role** — `open_role="source"` asks "who sells into this node?"
   (onward *demand* viability on intermediate hops); `open_role="destination"`
   asks "what can this node sell onward?" (onward *supply* viability). This is
   already handled in `fetch_open_ended_trade_candidates` — see the data layer
   note below.
2. **Which station the child becomes** — the chosen open-side station (source
   for open-source, destination for open-destination).
3. **Chain orientation for correction** — money always flows origin →
   destination, but the anchor sits at opposite ends. Open-source seeds at the
   destination, so the parent walk from a finalist is already origin-first;
   open-destination seeds at the origin, so the parent walk is destination-first
   and must be reversed to money order before the correction walk. The
   correction pass takes the orientation and otherwise re-fits identically.

Item 3 is the fiddly part and the place a bookkeeping slip would hide, so it
gets an explicit before/after check (a known backward `--to` route must come out
byte-identical, and a forward `--from` route must reconstruct in the correct
station order).

## Credit handling (both directions, after the change)

Expansion is **credit-optimistic** in both directions; the **forward credit-
correction pass** is the single place the real budget is enforced. The
correctness guarantee is the one already proven for the backward path: any route
returned has had every hop re-fitted and confirmed affordable under the real
forward budget. The residual quality nuance — the beam *ranks* on optimistic
profit, so a globally-best route could in principle be trimmed before it reaches
the finalist set — is the same one already accepted for `--to`, and is well
inside the spec's "comparable practical value, not exact optimum" standard.

## The data layer is already generic

`fetch_open_ended_trade_candidates` already takes `open_role` and already
attaches the onward-viability `EXISTS` to whichever side is open, checking the
role the next hop needs. The reachable set is already a SQL subquery, never a
materialised id list. Validation was already relaxed to "multi-hop requires
`--from` or `--to`". So this slice is concentrated almost entirely in
`run_route.py`; `data_gateway.py` and `validation.py` are expected to be
untouched.

## Validation plan

No automated harness (project decision). Spot-check against `--old` where
useful; route validity is primary, not parity.

- **Refactor regression guard (the important one).** A known backward `--to`
  route must come out **identical** to the current planner — same stations,
  same cargo, same profit. Run `--to "Lave/Lave Station" --hops 3` and
  `--to "Sol" --hops 2` before and after and diff the output. The engine is
  being refactored under the open-source shape, so it must reproduce exactly.
- **The hang is gone.** The 2-hop / 2-jump `--from "Lave/Lave Station"` case
  must finish in seconds with `Cargo:` now overwhelmingly fast-path, and the
  original 3-hop / 3-jump command must complete.
- **Forward route quality.** Spot-check a forward `--from X --hops N` route
  against `--old` for comparable-or-better practical value (the widened final
  layer should help). A higher `--old` profit is not a regression until its
  hops are checked against `_MIN_MEANINGFUL_DEMAND`, the bulk-sale-tax cap, and
  `--max-price`.
- **Fixed-terminal untouched.** `--from "Sol" --to "Lave" --hops 3 --jumps-per 2
  --ly-per 30 --capacity 128 --credits 5000000 --fc N --age 2` must be
  unchanged (it does not go through the generic engine; confirm anyway).
- **One-hop and the run-short Colonia benchmark** unchanged.

## Implementation order

1. Save this plan.
2. Add the three-way dispatch to the `hops > 1` branch of `plan_route`; split
   `_plan_multi_hop` down to the fixed-terminal case only and simplify its
   now-always-true envelope conditionals.
3. Generalise the optimistic primitive (`best_open_ended_trades_into` ->
   direction-neutral, `open_role` parameter).
4. Generalise the engine (`_plan_open_origin_multi_hop` -> direction-neutral),
   the child build, the correction pass (orientation parameter), and the partial
   helper.
5. Point both open shapes at the generic engine; retire the old forward
   open-terminal path inside `_plan_multi_hop`.
6. Local validation: the regression guard first, then the hang, forward quality,
   fixed-terminal, and the one-hop / benchmark set.
7. Update `SLICE_SUMMARY.md` — docs after the code is accepted.
8. Completion report after sign-off.

## Files expected to change

```text
tradedangerous/planner/run_route.py     # dispatch, generic engine, generalised helpers
```

`data_gateway.py`, `validation.py`, the renderer, DTOs, request, and parser are
expected to be untouched.

## Noted for later

- **Shared bubble row-volume.** Once the branch-and-bound premium is gone, both
  open shapes share the ~2 min floor from fetching and grouping the reachable
  bubble's market rows. Cutting it (proxy ranking, or per-system SQL row-
  narrowing in the candidate fetch) is a separate optimisation; defer until it
  is the measured bottleneck.
- **Full three-way unification.** If fixed-terminal `--from X --to Y` is ever
  wanted on the same engine, the engine would need an optional envelope and the
  fixed-pair final hop. Not worth the risk now; recorded so the option is not
  lost.
- **Split the planner orchestration into per-shape modules.** `run_route.py` now
  holds every planner — one-hop (fixed / open / unanchored), fixed-terminal
  multi-hop, and the unified single-anchor engine this slice adds. The
  specialisation is correct (different shapes want different algorithms), but the
  single file has outgrown easy reading. A follow-on slice should move each
  planner into its own module, with the shared multi-hop parts (the frontier
  node, beam constants, expansion primitives, reconstruct/correction helpers) in
  one common home, leaving `plan_route` as the thin dispatch surface. Do it
  *after* this slice and as a **pure structural move — no behaviour change** — so
  its diff is verifiable by "everything comes out identical," kept clean of this
  slice's logic change.
