# Slice 11 Completion Report — Unified Single-Anchor Open Multi-Hop

## Status

Complete. Code committed on `release/v1`: the engine unification in `317644e3`,
the open-destination wiring in `1bf71899`, and the dead-code trim in `af352f8f`.
Documentation in this commit.

## What this slice fixes

No new route shape and no new option. It fixes a shape that was already claimed
as supported but did not finish at realistic depth — open-destination multi-hop:

```text
trade run --from X --hops N        (--to omitted, N >= 2)
```

A filtered 3-hop / 3-jump run from a fixed origin previously did not complete in
30+ minutes. The fix unifies this shape with its mirror, open-origin multi-hop
(`--to Y --hops N`, from Slice 10), onto one engine.

## Root cause

The two shapes are direction mirrors, but they ran on different machinery:

- **Open-origin (`--to Y`)** grows the route backward from Y. Expansion is
  credit-optimistic — cargo is fitted against a deliberately non-binding budget,
  so the cheap one-pass cargo fill is always taken, and the real budget is
  reconciled once at the end by a forward credit-correction pass.
- **Open-destination (`--from X`)** grew forward from X on the known-origin
  planner, which fits cargo against the *real* running budget at every candidate
  during expansion. At a low credits-to-capacity ratio that budget binds, so
  branch-and-bound ran on nearly every candidate pair.

Both directions fan out to a large candidate set per hop — there is no envelope
when one endpoint is open. Open-origin stays fast because every expansion fit is
the cheap fast path; open-destination was slow because every expansion fit was
branch-and-bound. Measured on a 2-hop / 2-jump case: 5,337 branch-and-bound fits
against 2,125 fast-path, ~3m37.

The known-origin planner had only ever been validated in its fixed-terminal form
(`--from X --to Y`), which the destination envelope keeps small and which was
tested at a credits-to-capacity ratio that kept the fast path available. The
open-destination form — no envelope, binding budget — was never exercised at
depth.

## The fix — one engine for both open shapes

Generalise the Slice 10 backward engine into a single engine keyed on
`open_role` (the trade role of the endpoint the planner selects) and route both
open shapes through it. Both now expand credit-optimistically (fast-path cargo)
and reconcile the real budget in the correction pass. Three commits:

1. **Unify (`317644e3`).** The per-node primitive, the engine, the child
   builder, the credit-correction pass, and the partial-route helper become
   direction-neutral, parameterised by `open_role`:

   ```text
   best_open_ended_trades_into -> best_open_ended_hop_candidates
   _plan_open_origin_multi_hop -> _plan_open_anchor_multi_hop
   _make_backward_child        -> _make_open_child
   _correct_open_origin_chain  -> _correct_open_anchor_chain
   _best_open_origin_partial   -> _best_open_anchor_partial
   ```

   The open-source (`--to`) path is rewired through the generic engine unchanged.
2. **Wire (`1bf71899`).** The `hops > 1` branch of `plan_route` gains a three-way
   endpoint dispatch mirroring the one-hop dispatcher: `--from --to` ->
   fixed-terminal (unchanged); `--from` only -> `open_role="destination"`;
   `--to` only -> `open_role="source"`; both omitted -> rejected in validation.
3. **Trim (`af352f8f`).** With open-destination routed to the engine,
   `_plan_multi_hop` is only ever called with both endpoints set, so its
   open-terminal branches are unreachable. Removed: it is now unconditionally
   fixed-terminal (net -46 lines).

### What stays direction-aware

Three things, collapsing to roughly one `open_role` parameter threaded through a
few spots:

- the trade role the candidate fetch and the onward-viability `EXISTS` use;
- which station the expanded child becomes (the chosen open-side station);
- the credit-correction chain orientation. Money always flows origin ->
  destination, but the anchor sits at opposite ends. For an open source the
  parent walk already runs origin-first; for an open destination it runs
  destination-first and is reversed to money order, with each hop owned by the
  destination node rather than the source node.

## Verification

All on the live database. The live-data caveat applies — exact figures drift, so
a static DB cannot be kept — so the before/after comparisons were run
back-to-back on the same data via `git stash`.

**Open-source (`--to`) unchanged — the refactor regression guard.**
`--to "Lave/Lave Station" --hops 3 --capacity 720 --credits 200000000
--jumps-per 3 --ly-per 30`, before and after the unification: byte-identical
route *and* identical search counts (3,305,783 candidate rows, 372,345 pairs,
372,345 cargo calls, 372,348 fast-path / 0 branch-and-bound, 1,880 finalists /
1 attempted / 1 corrected). Only the wall-clock timings differed — the generic
engine executes the same operations, not merely lands on the same answer.

**Open-destination (`--from`) hang fixed.** The 2-hop / 2-jump case:

```text
              before          after
wall-clock    3m37s           ~18s
cargo fits    2,125 fast /    8,854 fast /
              5,337 b&b       4 b&b (all in correction; expansion 0)
profit        12,073,156 cr   14,261,120 cr
```

It does *more* fits (the final layer now keeps the top 50 per node, not the old
top 1), but each is the cheap fast path — so it is ~14x faster *and* finds a
better route. The route is valid and affordable from the 1M-credit start: Hop 2
is credit-bound (161 t Silver is all the budget allows after Hop 1, with cheaper
Bauxite filling the hold), which is the correction pass binding cargo to the real
budget. The original 3-hop / 3-jump filtered run went from not completing in 30+
minutes to ~3m10, expansion 100% fast-path, with the bulk-sale-tax cap correctly
applied on its Metals/Minerals hop.

**Fixed-terminal (`--from --to`) unchanged — the trim regression guard.**
`--from "Sol" --to "Lave" --hops 3 --jumps-per 2 --ly-per 30 --capacity 128
--credits 5000000 --fc N --age 2`, before and after the trim: byte-identical
route and identical search counts (53,154 candidate rows, 4,952 cargo calls,
Layer 1/2 kept 50, Final hop 50 attempted / 38 reach / 603 candidates / 38
viable). Only timings differed.

Open-destination route quality differs from the old known-origin forward path —
better, via the wider correction-aware final layer — and is within the spec's
"comparable-or-better practical value" standard. The old path was never validated
at depth (it hung), so there is no prior route to regress against.

## Files changed

`tradedangerous/planner/run_route.py` only, across the three commits. The
`open_role` parameter on `fetch_open_ended_trade_candidates` and the relaxed
multi-hop validation gate were already in place from Slice 10, so
`data_gateway.py` and `validation.py` needed no change. The renderer, DTOs,
request, and parser are untouched.

## Deferred (not cut)

- **Expansion-cost narrowing.** Both open shapes share a wall-clock floor from
  fetching and grouping the reachable bubble's market rows and fast-fitting every
  pair (the unfiltered 3-hop / 3-jump `--from` run spends ~99 s in the second
  layer). Narrowing candidate rows in SQL before cargo fitting, or proxy-ranking
  before the real fit, would help both directions. A separate round.
- **Planner-orchestration module split.** `run_route.py` now holds every planner
  (the one-hop family, fixed-terminal multi-hop, and the unified single-anchor
  engine). The specialisation is correct, but the single file has outgrown easy
  reading; a follow-on slice should move each planner into its own module as a
  pure structural move, no behaviour change. Recorded in the implementation
  plan's Noted-for-later.
- **Fully unanchored multi-hop** (`--hops N`, both endpoints omitted) — the next
  shape slice.
- **All route modifiers and search/display controls** still gated in validation.
