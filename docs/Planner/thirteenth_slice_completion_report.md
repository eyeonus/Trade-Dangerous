# Slice 13 Completion Report — Fully-Unanchored Multi-Hop

## Status

Complete on `release/v1`. Three code commits:

- `1c99def0` refactor(planner): share the open-anchor multi-hop engine via route_common
- `7775bcb3` feat(planner): plan fully-unanchored multi-hop routes
- `0663f488` fix(run): reword the unanchored-search confirmation prompt

## What this slice delivered

The last basic route shape: multi-hop with **both endpoints omitted**.

```text
trade run --hops N        (--from omitted, --to omitted, N >= 2)
```

The planner selects the origin, the destination, and every station in between.
This fills the one remaining hole in the shape grid — every `trade run` route
shape the spec defines is now served by the new planner. No new user option, no
change to any existing shape.

## The approach — composition, not a new search

Fully-unanchored multi-hop is the unanchored one-hop candidate fetch feeding the
proven forward open-anchor engine. There is no new search algorithm:

```text
fetch_unanchored_trade_candidates  ->  distinct source stations
  ->  rank by realisable-profit proxy, trim to the beam width
  ->  seed the open-anchor engine, open_role="destination"
  ->  forward credit-correction pass
  ->  best N-hop route
```

The unanchored one-hop fetch already does the expensive, narrowed galaxy scan
(including the cost-model remediation from the Slice 9 follow-up) and returns a
bounded, ranked set of trades. Its **source** stations are good places to start
a route, so the search seeds on them and grows forward — exactly the
open-destination multi-hop path (`--from X`), just seeded galaxy-wide instead of
from one named system.

## Delivered

**Engine relocation (commit `1c99def0`).** The open-anchor expansion engine
moved out of `route_single_anchor.py` into `route_common.py`, generalised to
accept a pre-built seed frontier so more than one planner can drive it:

- The engine `_plan_open_anchor_route`, the per-node primitive
  `best_open_ended_hop_candidates`, the correction pass
  `_correct_open_anchor_chain`, the partial-route helper
  `_best_open_anchor_partial`, `_finalise_correction_stats`,
  `_reverse_jump_path`, `_make_open_child`, and the `_OPTIMISTIC_PRICE_PER_TON`
  / `_OPEN_ORIGIN_CORRECTION_WIDTH` constants now live in the shared module.
- `route_single_anchor.py` is reduced to a thin front: resolve the anchor, build
  the seed from its stations, call the engine.
- The move is verbatim apart from the engine's new `seed_frontier` parameter and
  reworded docstring (see Verification).

**New planner (commit `7775bcb3`).** `route_unanchored.py`,
`_plan_unanchored_multi_hop`:

- Runs `fetch_unanchored_trade_candidates`; an empty result is the usual
  "no profitable trades" failure.
- Ranks each distinct source station by a realisable-profit proxy —
  `profit_per_unit × min(ceiling, source_supply, effective_demand)`, where the
  ceiling is capacity narrowed by `--limit` when set — recomputed in Python from
  fields the returned `TradeCandidate` already carries. This mirrors the
  gateway's `_realisable_profit_expression`; no extra query, no cargo fit to rank
  the seed.
- Materialises only the source stations, sorts by that rank (station-id breaking
  ties for determinism), keeps the top `_MULTIHOP_FRONTIER_WIDTH` (50), and
  builds zeroed hop-0 frontier nodes. The trim is done here, not in the engine:
  the engine expands every seed node, and the default fetch yields hundreds of
  sources, so an untrimmed galaxy seed would blow up the first layer.
- Calls the relocated engine forward (`open_role="destination"`) and attaches the
  seed-scan counters to the result diagnostics via `replace`, leaving the engine
  untouched.

**Dispatch and validation (commit `7775bcb3`).**

- `plan_route`'s multi-hop branch gains an explicit both-omitted arm; the
  `--to`-only arm was made explicit at the same time so a `None --to` can no
  longer fall through into the source-open engine.
- The two both-omitted multi-hop rejections — the planner gate in `validation.py`
  and the command-layer guard in `run_cmd.py` — were removed. The shape grid is
  complete, so there is nothing left to reject.

**Confirmation prompt (commit `0663f488`).** Both-omitted runs already route
through the existing unanchored confirmation prompt — it gates on the absence of
both endpoints, not on the hop count, so multi-hop flows through it once the
rejections are gone. Its wording was reworded to plainer, player-facing language
that reads correctly for both the one-hop and multi-hop unanchored shapes ("the
best trades", not "one best trade"), and the non-TTY abort message was brought
into the same voice.

## Verification

No automated harness (project decision); route validity is the gate,
spot-checked against live data.

**Engine relocation — proven byte-identical.** Two independent checks:

- *Source comparison.* Each moved helper and both constants are byte-for-byte
  identical to their pre-move source; the engine function differs only by the new
  signature parameters, the reworded docstring, and the removed resolve/seed
  front (now in the thin front). The entire search/correction/result body —
  roughly 260 lines — is unchanged.
- *Behavioural regression.* `--from X --hops N` and `--to Y --hops N` run on the
  moved code versus HEAD, with `--age` removed so the candidate set is
  deterministic, produced identical routes and identical search counts (only
  wall-clock timings differ). An earlier difference seen with `--age 3` was the
  age window shifting between the two captures — `--age` is relative to row
  modified-time — not the move.

**New shape — valid routes across the matrix.** `trade run --hops 2` with both
endpoints omitted returned valid two-hop chains, both ends planner-chosen, every
hop reachable and affordable:

- Filtered (`--fc N --planetary N --pad-size L --age 3`, 50M cr): a valid
  non-carrier route.
- Unfiltered (no `--fc`, 1M cr): a valid route; at the tight budget the forward
  credit-correction pass bound (branch-and-bound) and still produced an
  affordable route, hop 1 buying within the 1M start.
- With `--limit 50`: a valid route with every buy line at or below 50 t — five
  lines pinned at exactly 50 t — confirming `--limit` flows through both the new
  seed rank and the engine's per-commodity cap.

**Existing shapes unchanged.** The run-short Colonia benchmark, one-hop
open-destination (`--from` only), and one-hop unanchored (both omitted,
`--hops 1`) all returned valid routes. The reworded prompt reads correctly for
the one-hop unanchored case as well as the multi-hop one.

**Prompt paths.** The affirmative answer runs the search; declining (bare Enter)
prints "Search cancelled." and never invokes the planner. The non-TTY path uses
the same abort helper.

**Performance.** This is the heaviest shape by nature — the galaxy seed scan plus
multi-hop expansion. Measured wall-clock ran between roughly 80 seconds and 5.3
minutes across the tested filter and parameter sets; the seed scan (reported as
the station-filter time in diagnostics) dominates. The existing confirmation
prompt gates it.

## Notes

- The seed-scan cost surfaces in diagnostics as the station-filter time
  (resolution is zero — there is no name to resolve). The four unanchored
  counters are attached to the diagnostics DTO, matching the one-hop unanchored
  planner; neither planner's counters are rendered in the text output today.
- Seeding from the best one-hop origins is a heuristic — the best start for an
  N-hop route is not always the best first-hop origin. This sits within the
  spec's "comparable practical value, not exact optimum" standard and is
  consistent with how the rest of the unanchored family already works. If it
  proves to miss good multi-hop starts in practice, the levers (source-system
  diversity, a wider per-commodity fetch cap) remain available without a
  candidate-query rewrite.
- Carrier-backed extreme-margin trades surface in the winners whenever `--fc N`
  is not set, exactly as across the rest of the unanchored family. The planner
  reports what the data holds; the `--max-price` default still clips the
  far-tail price fiction.

## Deferred (not cut)

- All route modifiers and search/display controls still gated in validation
  (`--via`, `--avoid`, `--towards`, `--loop`, `--unique`, `--shorten`,
  `--routes`, `--max-routes`, `--prune-score`, `--prune-hops`, `--start-jumps`,
  `--end-jumps`, `--direct`).
- The shared expansion-cost floor (narrow candidate rows before cargo fitting),
  which would help every open shape.
- The stale `_OPEN_ORIGIN_CORRECTION_WIDTH` naming and docstring — it serves all
  open shapes now, not just open-origin — left out to keep the diff minimal.
