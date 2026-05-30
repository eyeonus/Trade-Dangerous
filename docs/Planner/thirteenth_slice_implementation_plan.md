# Slice 13 Implementation Plan — Fully-Unanchored Multi-Hop

## Status

Draft, for review. Not yet implemented. This plan is being circulated to a
second agent for comment before any code is written.

## Purpose

Add the last basic route shape: multi-hop with **both endpoints omitted**.

```text
trade run --hops N        (--from omitted, --to omitted, N >= 2)
```

The planner selects the origin, the destination, and every station in between,
finding the best N-hop chain anywhere in reachable range. Today this shape is
rejected in validation; it is the one remaining hole in the shape grid:

| | one-hop | multi-hop |
|---|---|---|
| `--from X --to Y` | done | done (fixed-terminal) |
| `--from X` only | done | done (open destination) |
| `--to Y` only | done | done (open origin) |
| both omitted | done (unanchored) | **this slice** |

No new user option. No change to any existing shape.

## The core idea — two engines we already have, end to end

Fully-unanchored multi-hop is the **unanchored one-hop search's
endpoint-finder feeding the proven open-anchor forward engine**. There is no
new search algorithm; it is composition.

```text
fetch_unanchored_trade_candidates  ->  distinct source stations
        ->  seed frontier
        ->  the open-anchor expansion engine, open_role="destination"
            (grow forward, credit-optimistic, beam-trimmed)
        ->  forward credit-correction pass
        ->  best N-hop route
```

Two facts from the current code make this clean:

1. **The open-anchor engine is anchor-specific in exactly one place.**
   `_plan_open_anchor_multi_hop` (`route_single_anchor.py`) resolves the named
   endpoint and builds the seed frontier from its stations
   (`route_single_anchor.py:67-119`). Everything after the seed — the layer
   loop, per-station coalescing, the beam trim to `_MULTIHOP_FRONTIER_WIDTH`,
   the widened final layer, the credit-correction pass, the partial-route
   fallbacks, the result builder — is generic and already keyed by `open_role`.

2. **The per-node expansion primitive already works on a single station.**
   `best_open_ended_hop_candidates(session, anchor_station, ...)` takes one
   station and finds the best open-side trades from it. It does not care whether
   that station came from a named anchor or from a galaxy-wide pick. So the
   primitive, the child builder (`_make_open_child`), the correction pass
   (`_correct_open_anchor_chain`), and the partial helper
   (`_best_open_anchor_partial`) are all reused **unchanged**.

So the only genuinely new logic is: *build the seed frontier from the
unanchored search's origins instead of from a named anchor.* Everything else is
wiring (dispatch, validation, the confirmation prompt).

## Why forward, seeded from origins

The unanchored one-hop fetch already does the expensive, already-remediated
galaxy-wide narrowing (see the Slice 9 unanchored slow-case fix) and returns a
bounded, ranked set of `(source, destination)` trades. The **source** stations
of those trades are exactly "good places to start a route" — a station that
begins a high-value first hop sits in a productive region. Seed on those and
grow forward toward destinations (`open_role="destination"`), reusing the
validated forward path.

Growing backward from the unanchored destinations (`open_role="source"`) is the
mirror and would also work, but forward is the natural reading and matches the
direction the unanchored fetch already ranks. No reason to prefer backward.

Keeping the galaxy scan in the **one** existing function matters: it is the
clean-room single source of truth for "what trades exist galaxy-wide," and the
costly cost-model remediation already lives there. A second bespoke "best origin
stations" galaxy query would duplicate that surface and risk re-introducing the
same SQLite cost-model failures. Avoid it unless the seed probe (below) proves
the existing fetch cannot supply a diverse enough seed.

## Scope

**In:** `trade run --hops N` with both `--from` and `--to` omitted, `N >= 2`.

**Out, and untouched:**

- Every existing shape — one-hop (all four), fixed-terminal multi-hop, and the
  two single-anchor open multi-hop shapes. The single-anchor engine must come
  out **byte-identical** (it is the regression guard for the engine move).
- All route modifiers and search/display controls (`--via`, `--avoid`,
  `--towards`, `--loop`, `--unique`, `--shorten`, `--routes`, `--max-routes`,
  `--prune-score`, `--prune-hops`, `--start-jumps`, `--end-jumps`, `--direct`)
  stay gated in validation.

## The seed — the one real design decision

The seed frontier is the distinct **source** stations of
`fetch_unanchored_trade_candidates`, materialised as `ResolvedStation` DTOs
(via `fetch_stations_by_id`, exactly as `_plan_unanchored` already does), built
into `_FrontierNode`s at `hop_index = 0`. As in the single-anchor engine the
**route** accumulators are zeroed (`accumulated_raw_profit = 0`,
`accumulated_practical_score = 0.0`) — a route genuinely has no profit before its
first hop, and the forward credit-correction pass re-derives everything from the
real budget regardless.

**Trimming the seed needs its own ranking key, held outside the node.** This is
the one place the unanchored seed differs from the single-anchor seed, and it
must be explicit or the widening lever is half-built. The single-anchor engine
zeroes its seed scores *and never trims the seed* — it keeps every eligible
anchor station, because that set is already small (one system's stations). The
unanchored seed is different: it stands in for a ranked galaxy-wide candidate
set, and a widened fetch can return more sources than the beam width. If the
trim sorted on the zeroed `accumulated_practical_score`, it would be sorting on
all-equal `0.0` — an arbitrary cut that could discard exactly the good origins
the widening was meant to surface.

So: when grouping the unanchored candidates by source station, retain a **seed
rank** taken from that source's best candidate, and use it — not the route
score — for the pre-frontier trim and the optional source-system diversity pass.
The seed rank is a *selection key only*; it never becomes route profit (the node
still starts at zero). Ranking key, in preference order:

1. The best candidate's estimated practical first-hop value (its cargo-fitted
   profit under the destination ls-penalty), if cheaply computable from data the
   fetch already returns.
2. The best candidate's realisable-profit expression — profit-per-unit × a safe
   feasible quantity — which is essentially what the unanchored fetch already
   ranks on internally.
3. As an explicit fallback, the order the fetch already returns candidates in
   (it is ranked `realisable_profit DESC`), so "first N distinct sources" is a
   defensible, documented cut rather than an accidental one.

The probe (below) decides which is cheapest to compute from the returned rows;
option 2 or 3 is almost certainly enough, since the fetch's own ordering already
encodes origin quality.

The open question this leaves is **seed diversity**, not seed ranking. Seeding
from the best one-hop origins is a heuristic: the best start for an N-hop route
is not always the best first-hop origin. This is within the spec's "comparable
practical value, not exact optimum" standard, and consistent with how the whole
unanchored family already works — but only if the seed is wide and diverse
enough to contain good multi-hop starts.

### Pre-code probe (gates the seed design)

The natural seed is **narrow by construction.** `fetch_unanchored_trade_candidates`
is capped at `_UNANCHORED_MATCH_LIMIT = 50` trades total (`data_gateway.py:1019`,
applied as the SQL `LIMIT` and the Python-stream cap) — it is built to find the
single best *one-hop* trade, not to enumerate origins. The distinct **source**
stations among those <= 50 trades will be fewer still, and the carrier-dominance
note (winners clustering on a handful of carrier stations) suggests they may
cluster hard. So the seed-widening lever is **likely required**, not a fallback.
The probe settles whether and by how much.

Run the unanchored candidate fetch under the reference realistic filters
(`--age 3 --fc N --planetary N --pad-size L --jumps-per 3 --ly-per 30`,
matching the Slice 9 unanchored baseline) and measure:

- the number of **distinct source station ids** in the returned candidates;
- the number of **distinct source systems** they fall in.

Interpretation and remediation ladder (the default fetch returns <= 50 trades,
so a seed at the full beam width of 50 almost certainly needs the widening
lever):

- **If the <= 50 default trades already yield a healthy, well-spread set of
  distinct sources:** seed as-is, seed-rank-trimmed to the beam width. Unlikely
  given the cap, but the cheapest outcome if it holds.
- **Primary lever — widen the fetch for the seed call.** Raise the unanchored
  fetch's candidate cap *for the seed call only* (a parameter on
  `fetch_unanchored_trade_candidates`, default `_UNANCHORED_MATCH_LIMIT`
  unchanged so the one-hop path is byte-identical), trading a larger candidate
  set for more, more diverse origins. The probe sizes the widened value.
- **Complementary lever — source-system diversity on the seed trim.** Keep at
  most one seed station per system before the seed-rank trim, echoing the Slice 8
  destination-system diversity refinement, so a widened set does not collapse
  back onto a few carrier-heavy systems. Diversity uses the same seed rank to
  choose which station represents each system.
- **Last resort, separate decision (not assumed here):** a dedicated top-K
  supply-station seed query. Only if widening plus system diversity still cannot
  supply a diverse enough seed — and weighed against the cost of a second
  galaxy-wide query surface.

The probe result is recorded inline in this plan before code begins, the same
way Slices 5 and 6 gated their structural choices on probe evidence.

## Engine placement (decision for review)

The expansion engine is about to be used by two planners (single-anchor and
fully-unanchored), so the Slice 12 allocation rule — *used by more than one
planner → `route_common.py`* — points at moving it there. But that is a large
relocation (~785 lines), and Slice 12's discipline was that a structural move
stays clean of logic changes so its diff is verifiable by "everything identical."
Mixing a big move with the new behaviour in one step would lose that property.

Two candidate approaches, presented for the reviewer to weigh:

**Approach 1 — clean move, sequenced as two steps inside the slice
(recommended).**

- *Step A (structural, no behaviour change):* move the open-expansion engine and
  its direct helpers (`_plan_open_anchor_multi_hop` core, the
  `best_open_ended_hop_candidates` primitive, `_reverse_jump_path`,
  `_make_open_child`, `_correct_open_anchor_chain`, `_best_open_anchor_partial`,
  `_finalise_correction_stats`, and the `_OPTIMISTIC_PRICE_PER_TON` /
  `_OPEN_ORIGIN_CORRECTION_WIDTH` constants) into `route_common.py`. Generalise
  the engine to accept a **pre-built seed frontier** so both planners call it.
  `route_single_anchor.py` becomes the thin "resolve anchor → build seed → call
  engine" front. Verify single-anchor output byte-identical (the engine move is
  the regression guard).
- *Step B (behavioural):* add `route_unanchored.py` with
  `_plan_unanchored_multi_hop` (fetch unanchored → seed → call the engine,
  `open_role="destination"`), wire dispatch, relax validation, handle the
  prompt.

This keeps the one-way layering (`route_common` → planners → dispatch), satisfies
the Slice 12 rule, and keeps each step independently reviewable.

**Approach 2 — minimal diff, defer the move.**

Leave the engine in `route_single_anchor.py`; the new module imports the engine
from it. Smaller, lower-risk diff, but it is a planner importing a planner,
which muddies the layering Slice 12 just established. A later structural slice
would tidy it (as Slice 12 itself was a later tidy).

Recommendation: **Approach 1**, because it is what the Slice 12 layout was
built for and the engine move is cheaply verifiable. Flagging Approach 2 as the
lower-churn fallback if the reviewer prefers to keep this slice's diff small.

**Resolved: Approach 1.** The review endorsed it as the right default — it
preserves the Slice 12 layering and lets the engine move be verified separately,
byte-identical, before any new behaviour lands. Step 2 of the sequencing is that
move; step 3 adds the new planner on top of the relocated engine.

## Module name

The new planner is `route_unanchored.py`. The multi-hop family is organised by
anchor count — two anchors (`route_anchored`), one anchor
(`route_single_anchor`), zero anchors (`route_unanchored`) — so the name
completes that two/one/zero trichotomy and the multi-hop dispatch reads
symmetrically. No risk of confusion with the one-hop unanchored search: that
search lives inside `route_onehop.py` (the single-hop module) and has no module
of its own, so the bare name `route_unanchored` is unambiguous as the multi-hop
planner. No "_multi" suffix — it would be redundant word-salad given where the
one-hop version actually sits.

## Dispatch

`run_route.py`'s multi-hop branch (`run_route.py:56-68`) currently has **no
explicit both-omitted arm** — its final `return` assumes the `--to`-only case
and calls the engine with `open_role="source"`. Both-omitted cannot reach it
today only because validation rejects it first. So before validation is
relaxed, the dispatch must gain an explicit both-omitted branch, or a relaxed
validation would route both-omitted into the source-open engine and crash on a
`None` `--to` in `resolve_endpoint`.

Target dispatch (mirrors the one-hop four-way dispatcher in `_plan_single_hop`):

```text
--from X --to Y   ->  _plan_multi_hop                  (fixed-terminal)
--from X          ->  engine, open_role="destination"  (open destination)
--to   Y          ->  engine, open_role="source"       (open origin)
both omitted      ->  _plan_unanchored_multi_hop       (new)
```

## Validation — two gates, not one

Both-omitted multi-hop is rejected in **two** places today, and both must relax:

- `validation.py:43-46` — the planner-side gate:
  `if request.hops > 1 and request.from_text is None and request.to_text is None:
  raise UnsupportedRunShape("Multi-hop requires --from or --to.")`.
- `run_cmd.py` (~`423-430`) — the command-layer guard, raising
  `CommandLineError("Multi-hop requires --from or --to.")` for `hops > 1` with
  neither endpoint named.

Both were relaxed together at Slice 10 from "requires `--from`" to "requires
`--from` or `--to`"; Slice 13 relaxes them again to allow both-omitted when
`N >= 2`, leaving the rest of the multi-hop validation contract intact. The
command-layer guard runs during argument processing, before the run executes, so
it must relax for the request to reach the confirmation prompt at all.

## Confirmation prompt (heaviest shape — must be gated)

This is the slowest shape in the planner: the unanchored galaxy seed cost
(~2m 33s under realistic filters per the Slice 9 baseline) **plus** multi-hop
expansion on top (seed width × N hops × per-node open-ended fetch). It must sit
behind the existing both-omitted confirmation prompt.

The prompt is **already hops-agnostic.** It gates on `_is_unanchored_request`
(`run_cmd.py:1359-1362` — `not request.from_text and not request.to_text`), with
the affirmative/non-affirmative/non-TTY handling at `run_cmd.py:1459-1501`. So
once the two both-omitted gates above relax, both-omitted multi-hop flows through
this prompt automatically — no new gate is needed. Only the wording needs a pass.
Two reasons: the current copy is calibrated for one-hop unanchored, and
multi-hop unanchored is heavier still (seed scan plus N layers of expansion); and
the current text describes finding "one best trade", which is actively inaccurate
for `--hops N`. The reworded prompt should describe a "best route" / "multi-hop
route" and key its language off `request.hops` so it reads correctly for both the
one-hop and multi-hop unanchored shapes. Validation already runs before the
prompt, so an invalid multi-hop request still fails fast rather than after a
confirmation.

## Diagnostics

The engine's result builder (`_multihop_result`, `route_common.py:89-143`)
carries the multi-hop diagnostics (layer stats, expansion stats, correction
stats) but **not** the unanchored counters — its `PlannerDiagnostics(...)` call
does not set them. The one-hop `_plan_unanchored` sets
`unanchored_pairs_examined`, `unanchored_pairs_accepted`,
`unanchored_bubble_systems`, and `unanchored_per_commodity_cap_hits` directly
(the fields already exist on `PlannerDiagnostics`). To surface the seed cost on
the multi-hop result they must be **threaded** into `_multihop_result` as
optional parameters and passed through to `PlannerDiagnostics`. Small, additive,
and inert for every existing caller (they default to absent).

Resolution and station-filter timings: there is no name resolution for an
unanchored run. Mirror `_plan_unanchored` — `resolution_ms = 0.0`, and account
the seed-fetch time as the station-filter / market-query time.

## Sequencing

Each numbered step imports and runs after it; one logical step at a time, with
review between them per the project workflow.

1. **Seed probe.** Measure distinct seed sources/systems from the unanchored
   fetch; record the result here; settle the seed design.
2. **Engine generalisation (structural).** Per the chosen approach, make the
   expansion engine callable with a pre-built seed frontier (and, if Approach 1,
   relocate it to `route_common.py`). Verify single-anchor `--from` and `--to`
   multi-hop come out byte-identical (regression guard).
3. **New planner.** `route_unanchored.py`: fetch unanchored candidates →
   build and trim the seed frontier → call the engine forward.
4. **Dispatch + validation.** Add the both-omitted multi-hop arm to
   `plan_route`; relax the validation rejection.
5. **Prompt.** Ensure the both-omitted confirmation prompt covers multi-hop;
   reword for the heavier cost.
6. **Validation runs.** See below.
7. **Docs.** Update `SLICE_SUMMARY.md` and `INDEX.md`; completion report after
   sign-off (docs commit separate from code, per the project workflow).

## Validation plan

No automated harness (project decision). Spot-check against `--old` where
useful; route validity is primary, not parity.

- **Single-anchor regression guard (the important one).** Known `--from X
  --hops N` and `--to Y --hops N` routes must come out **identical** before and
  after the engine generalisation/move — same stations, cargo, profit, and
  search counts. Run back-to-back via `git stash` on the same live data, as
  Slice 11 did.
- **New shape produces a valid route.** `trade run --hops 2` and `--hops 3`
  with realistic filters return a valid N-hop chain: every hop reachable under
  the jump settings, every hop affordable under the real forward budget (the
  correction pass binds cargo to the running budget), the bulk-sale-tax cap and
  `--max-price` applied where relevant.
- **Spot-check value against `--old`** for comparable-or-better practical value
  on a shape `--old` can run, allowing for the new planner's correct handling of
  one-sided stations and the `_MIN_MEANINGFUL_DEMAND` / cap / max-price filters
  (a higher `--old` figure is not a regression until its hops are checked
  against those filters, per the Slice 9 close-out).
- **Prompt paths.** Affirmative, non-affirmative, bare-Enter, and non-TTY all
  behave (no traceback; planner never invoked on a non-affirmative answer).
- **One-hop and the run-short Colonia benchmark** unchanged.

## Files expected to change

```text
tradedangerous/planner/route_unanchored.py         # new planner
tradedangerous/planner/route_common.py             # engine relocation (Approach 1)
tradedangerous/planner/route_single_anchor.py      # reduced to thin front (Approach 1)
tradedangerous/planner/run_route.py                # both-omitted multi-hop dispatch arm
tradedangerous/planner/validation.py               # relax both-omitted multi-hop gate
tradedangerous/commands/run_cmd.py                 # prompt covers multi-hop; reword
```

`cargo.py`, `score.py`, `reachability.py`, `render_text.py`, `run_request.py`,
`run_result.py` (the `PlannerDiagnostics` unanchored-counter fields already
exist, so threading them touches `route_common.py` and its callers, not the
DTO), `resolver.py`, and
`data_gateway.py` (unless the seed probe requires a widening parameter on the
unanchored fetch) are expected to be untouched.

## Source facts confirmed for this plan

All four anchor points were read in full and confirmed against source; the
design above rests on them, not on assumption:

1. **Both-omitted gates (two).** `validation.py:43-46` and the `run_cmd.py`
   command-layer guard (~`423-430`). Both reject the shape today; both relax.
2. **Confirmation prompt is hops-agnostic.** `_is_unanchored_request`
   (`run_cmd.py:1359-1362`) keys only on the absence of both endpoints; the
   prompt at `run_cmd.py:1459-1501` therefore covers multi-hop once the gates
   relax. Wording reword only.
3. **Unanchored fetch is capped at 50 trades.** `_UNANCHORED_MATCH_LIMIT = 50`
   (`data_gateway.py:1019`), applied as the SQL `LIMIT` (line 1571) and the
   Python-stream cap (line 1709). Drives the seed-width probe and the widening
   lever above.
4. **`_multihop_result` does not carry the unanchored counters** — they must be
   threaded (see Diagnostics).

The one item that still genuinely needs a runtime measurement before code is the
**seed probe** (how many distinct sources/systems the fetch yields, and the
widened cap needed) — it is a measurement, not a source read, and is step 1 of
the sequencing.

## Noted, not done

- **Stale `_OPEN_ORIGIN_CORRECTION_WIDTH` naming and docstring.** The constant
  and its comment still describe "when only a destination is given (no
  `--from`)"; since Slice 11 it serves both open shapes, and it will serve
  unanchored too. A rename/reword is a tidy opportunity, left out of scope to
  keep the diff minimal; raise if wanted alongside the engine move.
- **Seed-quality monitoring.** If the heuristic seed proves to miss good
  multi-hop starts in practice, the remediation ladder above (system diversity,
  widened fetch) is the lever — not a candidate-query rewrite. Recorded so the
  option is not lost.
