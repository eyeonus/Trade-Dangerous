# Slice 26 — Completion Report

**`--loop`: anchored round-trip routes delivered; the galaxy-wide loop
investigated and decided against.**

*Completed 2026-06-13. Code commits `57d503db`, `58674c36` (anchored loop);
gate-wording reword this slice. Decision record:
`unanchored_loop_investigation.md`.*

---

## What the slice set out to do

`--loop` was the most meaningful option left on the gated list: start at a
station, trade out for N hops, end back where you started. It split naturally in
two — the **anchored loop** (`--from` named), cheap to build honestly on the
fixed-terminal engine, and the **unanchored loop** (`--from` omitted), part of
the same contract but a genuine search-design problem. The plan built the
anchored loop first and put the unanchored loop behind probes.

## What was delivered

### Anchored loop (`--loop` with `--from`)

A loop is a fixed-terminal multi-hop route whose terminal, per route chain, is
the chain's own origin station. The fixed-terminal engine took a loop mode:

- **Origins** are the `--from` endpoint's stations, intersected with the same
  endpoint's destination-eligible set — an origin that can never be sold back to
  can never close its loop.
- **Terminal rule:** the final hop targets the node's own root station (walk the
  parent links to hop 0).
- **Envelope anchor** is per-root (the root station's coordinates), not the
  shared `--to` system — so each chain's reachability is judged against its own
  closing point.
- **Frontier dedupe** keys on `(root_station, destination_system)`, so chains
  with different roots are not treated as near-duplicates and a system `--from`'s
  dominant station cannot starve the others.
- **Partial routes are suppressed** — an unclosed loop is not a loop; both
  partial-route fallback sites raise the loop failure instead.

Validation gained the `--loop` rules (`--direct`/`--loop` contradiction;
`--loop` needs `--hops ≥ 2`; `--start-jumps` composition gated with a clear
message). Dispatch routes a loop request to the fixed-terminal engine in loop
mode. A loop-specific no-route failure (`NoLoopRoute`) names the loop and offers
the loop levers. Shipped in `57d503db`.

### Terminal-qualification fix

A code-level audit of the committed anchored loop found two correctness defects,
both rooted in one mechanism: the loop's terminal set was built from origin
stations without applying the destination-side checks a real sell-back requires.
A demand-dead origin (nothing sellable back to it) and an avoided origin could
both pollute the frontier as terminals that can never legitimately close.

The fix builds the loop terminal set as a *real* destination-qualified set
before seeding: `fetch_loop_closable_station_ids` keeps only origins with usable
demand, excluding avoided commodities and applying the bulk-sale-tax effective
demand floor (sensitive raw demand 2–3 → effective 0, unsellable); avoided
stations and systems are removed up front. The shared demand predicate was
factored out (`_demand_viability_filters`) so the loop check and the onward-hop
check apply the identical conditions. Shipped in `58674c36`; verified against the
spec's reviewer variants on real data and confirmed byte-identical on non-loop
shapes.

## The unanchored loop — investigated and decided against

The unanchored loop's answer is the best anchored loop over *every* eligible
origin. Legacy got it by preloading the whole galaxy and brute-forcing — the
pattern this rewrite removes. Two probes tested whether it could be reproduced
within the architecture, both constrained by the standing decision that the beam
widths stay at 50.

- **P1 (seed fidelity)** killed the original "rank origins by a cheap
  loop-fitness score, keep the top K" design. The inbound half of the score
  cannot be measured (83 of 85 candidate origins never appear as a sink in the
  one-hop set), and the outbound half is a loose predictor — the galaxy's #2 loop
  sat at proxy rank 61, well past the width of 50. This is the documented
  blindness of any beam search (`beam_width_analysis.md`, finding 3); no proxy
  rescues it within 50.
- **P2 (sequential cost)** measured the only width-50-honouring alternative —
  run an honest anchored loop from every admitted origin, best wins. The default
  `hops 2` is cheap (45s, on a shape already behind a confirmation prompt), but
  per-origin cost grows ~5.2× per hop: `hops 4` is 8.3 min, `hops 6` projects to
  hours.

The decision was to **not support the galaxy-wide loop**. `--loop` requires
`--from`; the bare form is rejected with a clear message. The full evidence,
the alternatives weighed, and the homework for any future reopen are in
`unanchored_loop_investigation.md`. It is a settled decision, not a deferred
task.

## Variances from plan

1. **Part B was not built.** The plan carried the unanchored loop as
   probe-gated, expecting a build if the probes passed. P1 failed the seeding
   design and P2 showed the only compliant alternative is too costly at depth, so
   the slice closes with the anchored loop shipped and the unanchored loop
   decided against — recorded, not parked.
2. **`--start-jumps` with `--loop`** stays gated as the plan allowed (the
   repositioned origin cannot close its loop); no further work taken.

## Housekeeping

Probe scripts and their artefacts (seed-fidelity, pool-size, and
sequential-cost captures) deleted at slice close per standing practice; their
results are reproduced in `unanchored_loop_investigation.md`. The gate message
was reworded to state the `--from` requirement as settled rather than "not
supported yet". Living docs updated: `SPEC_STATUS.md` (`--loop` → `[varied]`,
loop-routes and failure rows, a new variation entry), `BASELINE.md` (`--loop`
done, the galaxy-wide loop added to settled decisions), `INDEX.md` (this slice
and the investigation record).
