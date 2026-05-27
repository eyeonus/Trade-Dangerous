# Slice 8 Follow-up — Fixed-Station Multi-Hop Route Quality

## Purpose

Handover brief for the next worker on the multi-hop planner. Slice 9
close-out exposed a route-quality regression on the fixed-station
multi-hop shape — `--from <station> --to <station> --hops N` — that
the Slice 8 verification did not cover. This document captures what
is known so work can start without re-deriving the situation. The
Slice 9 completion report (`ninth_slice_completion_report.md`,
section "Fixed-station multi-hop route quality (Slice 8 follow-up)")
carries the full write-up.

The standard startup docs (`INDEX.md`, `SLICE_SUMMARY.md`,
`trade_run_black_box_spec.md`, and the highest-numbered slice plan)
must be read first per the project CLAUDE.md. This document is
incremental to those, not a replacement.

## The defect

Reproducible regression:

```text
trade run --from "Sol/Abraham Lincoln" --to "Lave/Lave Station" \
          --capacity 128 --credits 5000000 --hops 3 \
          --jumps-per 2 --ly-per 30 --fc N --age 2
```

Observed:

```text
new planner:  1,237,504 cr
legacy --old: 3,045,686 cr
```

The new planner returns ~41% of `--old`'s profit on this shape. The
`--old` route uses Hydrogen Fuel out of Sol/Abraham Lincoln, then
Gold + Polymers from LP 855-34/Acton Port to Delkar/de Kamp Orbital,
then Biowaste to Lave/Lave Station. The new planner instead picks
Hydrogen Fuel -> LFT 824 -> Crucis -> Lave with Goslarite and
Onionhead Gamma Strain — locally profitable but missing the
high-value LP 855-34 -> Delkar transition.

Scoping:

- Slice 8 verified the system-expanded shape `--from "Sol"` at
  7,838,971 cr matching `--old` exactly. The fixed-station shape
  was not in that verification.
- Confirmed not caused by Slice 9 Part A's `--max-price` cap: the
  same command with `--max-price 0` returns the identical
  1,237,504 cr figure.

## Mechanism, as understood

Beam-search myopia, not the same beam-concentration failure fixed
during Slice 8.

Slice 8's fix (commit `d6a253d5`) keeps at most one node per
destination system in the global frontier trim, addressing
concentration on near-duplicate stations in high-volume systems.
That solved the system-origin Sol -> Lave regression, where many
Sol origin stations were competing for the same 50 frontier slots.

The Abraham Lincoln case is different. With a pinned station origin,
the Hop 1 frontier has only one origin to expand from, and the kept
set is determined entirely by the first-hop destinations produced
from that one station. Beam scoring by accumulated profit can favour
myopic destinations: a moderate Hop 1 that opens excellent onward
trades may be dropped in favour of a stronger Hop 1 that does not
lead anywhere as profitable.

Diagnostics block from the regression run:

```text
Layer 1: 1 in, 1 calls, 50 children, kept 36
Layer 2: 36 in, 36 calls, 649 children, kept 50
Final hop: 50 attempted, 39 reach destination, 253 market candidates, 39 viable
```

The central warning for the next worker:

```text
The new planner may be pruning strategically useful positioning hops
before they have enough depth to prove their value.
```

This is not an argument to widen the beam by default. It is a
warning that early score-only pruning can be structurally wrong for
fixed-station fixed-terminal multi-hop, especially where the first
hop is a low-profit positioning move.

## Important legacy-behaviour context

The legacy `--old` path does not keep a 50-wide score-ranked beam at
default settings.

For fixed-terminal multi-hop, legacy applies distance feasibility
pruning: routes too far from the destination to plausibly finish
inside the remaining hop budget are dropped. That is comparable in
spirit to the new planner's fixed-`--to` envelope.

But legacy does **not** perform a hard global score/top-N route trim
after Hop 1 or Hop 2 unless user pruning options such as
`--max-routes` or `--prune-score` are active.

That distinction matters here.

The Abraham Lincoln -> Lave legacy winner begins with a very
low-profit positioning hop:

```text
Sol/Abraham Lincoln -> LP 855-34/Acton Port
Hydrogen Fuel, +13,056 cr
```

That hop is not attractive by local profit. Its value is that it
positions the route for the high-value second hop:

```text
LP 855-34/Acton Port -> Delkar/de Kamp Orbital
Gold + Polymers
```

The new planner may therefore be pruning too early: it may discard a
feasible, strategically useful low-profit Hop 1 before Hop 2 has a
chance to reveal the route's value.

This is not an argument to copy legacy's broad Python-heavy route
processing. It is an argument to distinguish:

```text
good pruning:
  SQL-side feasibility pruning and data reduction

dangerous pruning:
  early score-only beam trimming before a route has enough depth to
  demonstrate downstream value
```

Legacy effectively preserves route diversity by retaining best routes to
destinations rather than doing a pure global top-N beam at every layer.

## Candidate explanations to distinguish

The diagnostics currently prove the shape of the failure but not the
exact drop point. Three candidate explanations are consistent with
the observed route:

A. `LP 855-34/Acton Port` is generated from `Sol/Abraham Lincoln`,
   but is outside the per-parent top-K returned by the first
   expansion.

   If true, the failure is per-parent expansion pruning. The useful
   positioning hop is locally too weak to survive even before the
   global layer trim.

B. `LP 855-34/Acton Port` is inside the first expansion result, but
   is removed by fixed-terminal destination-system diversity because
   another station in `LP 855-34` has a better Hop 1 score.

   If true, the system-level diversity rule is too coarse for
   multi-hop: station identity matters because different stations in
   the same system can have different onward supply.

C. `LP 855-34/Acton Port` survives Hop 1, but the onward transition
   `LP 855-34/Acton Port -> Delkar/de Kamp Orbital` dies during
   Layer 2 trimming.

   If true, the issue is second-layer accumulated-score pruning
   rather than Hop 1 retention.

The probe must track station identity, not just destination system
id. Knowing that some `LP 855-34` station survived is insufficient;
the legacy route specifically needs `LP 855-34/Acton Port`.

## Probe target

Trace this exact legacy route through the new helpers:

```text
Sol/Abraham Lincoln
-> LP 855-34/Acton Port
-> Delkar/de Kamp Orbital
-> Lave/Lave Station
```

The probe should answer:

```text
Hop 1:
  Was LP 855-34/Acton Port generated from Sol/Abraham Lincoln?
  What was its full per-parent rank before top_k truncation?
  Was it inside the returned top_k?
  Was it removed by destination-system diversity?
  If LP 855-34 was represented by a different station, which station was kept?

Hop 2:
  If Acton Port is forced/survives into the frontier, is Delkar/de Kamp
  Orbital generated?
  What is its per-parent rank?
  What is its accumulated score at the Layer 2 trim?
  Does it survive Layer 2's fixed-terminal trim?

Hop 3:
  If Delkar/de Kamp survives, does the fixed final-hop evaluator produce
  the Biowaste trade into Lave/Lave Station?
  What total profit do the new helpers compute for the full legacy route?
```

The useful classification is:

```text
A: not generated / outside per-parent top_k
B: generated but wrong same-system station retained
C: survives Hop 1 but dies at Layer 2 trim
D: survives to final but cargo/profit differs
```

If the full legacy route computes to the same total through the new
helpers, the issue is pruning/retention, not price maths or cargo
maths.

## Suggested first steps

The slice plan should not be written without empirical probes.
Suggested investigation, before any code change:

1. Add probe-only instrumentation to `_plan_multi_hop`
   (`tradedangerous/planner/run_route.py:613`) or a separate
   `research/perf/` probe that records the destinations of the
   generated and kept frontier nodes per layer.

   The probe should record station ids and system ids, not just names,
   so same-system substitutions are visible.

2. Re-run the regression command and inspect the recorded frontiers.
   This answers whether the loss is case A, B, C, or D.

3. If `LP 855-34/Acton Port` is not generated or not returned by the
   first expansion, the question becomes whether the per-parent
   expansion top-K is pruning useful positioning hops too early.

4. If `LP 855-34/Acton Port` is generated but another LP 855-34
   station is kept instead, the question becomes whether
   system-level diversity is too coarse and station identity must be
   preserved for onward-supply reasons.

5. If `LP 855-34/Acton Port` survives Hop 1 but Delkar dies at Layer
   2, the question becomes how the Layer 2 trim chooses 50 of 649
   generated children and whether that decision is sound for the
   fixed-station fixed-terminal shape.

6. A second fixed-station shape is useful before generalising a final
   fix, but do not block the first diagnosis on hunting one. First
   classify the known Abraham Lincoln -> Lave failure. Once the
   mechanism is known, choose or construct a second probe that
   exercises the same mechanism.

Once probes localise the loss, the design question is scoped: widen
the beam, change the trim criterion, delay early score pruning, add
look-ahead potential to the score, or restructure the search shape
for the fixed-station case. A fix should not be picked before the
probe.

See `fifth_slice_restructure_implementation_plan.md` for the
project's "probe before fixing" precedent — six empirical probes ran
against the unanchored search before the restructure was decided not
to ship.

## Possible remediation directions, not decisions

Do not treat this list as a recommendation to implement any of these
before probing. It is here to stop a fresh worker from collapsing the
problem into "increase width".

Potential fixes depend on the classification:

```text
If case A:
  Per-parent expansion is losing the positioning hop. Consider
  per-parent diversity, delayed early pruning, or a small protected
  feasible-positioning set before increasing top_k.

If case B:
  Destination-system dedup is keeping the wrong station. Consider
  preserving station-level candidates within a system when onward
  supply differs, or using a two-stage trim that preserves one
  system representative while allowing additional same-system
  stations only when they have distinct onward value.

If case C:
  Layer 2 global trim is losing the payoff transition. Consider a
  fixed-terminal trim rule that accounts for remaining route value,
  or delays hard score pruning until after two hops when the first
  hop can be a positioning move.

If case D:
  The route survives but computes differently. Investigate cargo,
  price, filter, final-hop, or station-resolution mismatch.
```

The important design constraint remains:

```text
Do not buy quality by blindly widening the frontier if the actual
problem is slot quality, pruning timing, or station identity.
```

## What not to do

- Do not widen the beam by reflex. Layer 2 already keeps 50 of 649
  generated children; reflex-widening produces marginal returns at
  significant wall-clock cost on dense Bubble shapes, and the
  diagnostic value of identifying *why* the right route is missing
  is lost.
- Do not treat "LP 855-34 system survived" as proof that the legacy
  path survived. The route needs `LP 855-34/Acton Port`
  specifically. A different station in the same system can be a dead
  end or a weaker onward source.
- Do not inspect or import from the legacy quarantined modules
  (`tradedangerous/tradecalc.py`, `tradedangerous/tradedb.py`).
  See the project CLAUDE.md "Source Quarantine" section.
- Do not paper over the regression by changing the verification
  shape. The fixed-station shape is supported by the new planner
  (Slice 8 plan, supported shapes); route quality must be
  comparable to `--old`.
- Do not assume Slice 9's price cap caused this. It has already been
  ruled out for the reproduced command by testing `--max-price 0`.

## Reference

Commits on `release/v1` carrying the Slice 8 multi-hop work:

```text
3f1e4115  perf(planner): push --to envelope into SQL; instrument multi-hop
d6a253d5  fix(planner): dedupe by destination system at the global frontier trim
b7485d2e  feat(planner): return partial multi-hop routes
01f3b8e5  docs(planner): Slice 8 completion docs.
```

Production code, not exhaustive:

- `tradedangerous/planner/run_route.py`
  - `plan_route` (entry; line 79)
  - `_plan_multi_hop` (line 613) — frontier expansion, layer trim,
    destination-system dedup
- `tradedangerous/planner/data_gateway.py`
  - `fetch_open_ended_trade_candidates` — per-frontier-node
    expansion query, also used by multi-hop intermediate hops
    (`terminal_hop=False`)
  - `_reachable_station_query` — reachable-system temp table and
    envelope filter

Probe artefacts from the unanchored work, useful as precedent for
shape and discipline (do not commit probe scripts):

- `docs/Planner/fifth_slice_restructure_implementation_plan.md`
- Memory entry: `feedback_probes_not_committed.md`

## Resolution — investigated and closed

Investigated 2026-05-26. Not a regression. The new planner is behaving
correctly; legacy `--old` was computing a total against an unfillable
in-game trade.

**Mechanism, as established:**

A probe walked the candidate-fetch from Sol/Abraham Lincoln under the
regression command's filters and found Acton Port absent from the
envelope-filtered destination set. SQL against the same database
showed why: Acton Port's `StationItem` row for Hydrogen Fuel is
`supply_units = 2323, supply_price = 126, demand_units = 1,
demand_price = 120` — Acton Port is a Hydrogen Fuel *supplier*, and
the demand_units=1 is the dormant buy side of the row. This is exactly
the case Slice 3's `_MIN_MEANINGFUL_DEMAND = 2` filter exists to
reject (see SLICE_SUMMARY.md "Commodity supply and demand values").

Legacy `--old` does not apply this filter. It treats the dormant row
as a real buyer and plans 128 t to be sold at a station that would not
take it in-game. The 3,045,686 cr total is computed against an
in-game-unfillable Hop 1 sale.

**Closely comparable shapes:**

```text
trade run --from "Sol" --to "Lave/Lave Station" --capacity 128 \
          --credits 5000000 --hops 3 --jumps-per 2 --ly-per 30 \
          --fc N --age 4

new planner: 5,059,696 cr
--old:       4,907,264 cr   (new planner ahead by 152,432 cr / 3.1%)

trade run --from "Sol" --to "LP 855-34/Acton Port" --capacity 128 \
          --credits 5000000 --hops 1 --jumps-per 3 --ly-per 30 --age 4

new planner: 882,176 cr     (128 t Bertrandite, Sol/Bourne -> Acton Port)
--old:       882,176 cr     (identical)
```

The system-expanded multi-hop shape reproduces the Slice 8
verification scenario under current data and beats legacy. The one-hop
run confirms Acton Port is a perfectly viable destination when the
trade is real.

**Mechanism the handover proposed (beam-search myopia) was not what
was happening.** The strategic positioning hop never enters the beam
because the positioning destination doesn't exist as a Hop 1 candidate
under correct demand semantics — the planner is right to refuse it.
Relaxing the demand floor would re-admit the phantom-trade noise the
Slice 3 filter was put in to keep out.

**What changes:** nothing in the planner. Slice 3 demand floor and
Slice 8 multi-hop search are behaving correctly on this shape. Slice 8
follow-up closes.

**What does not change:** if a separately reproducible fixed-station
multi-hop case turns up where `--old` beats the new planner on a route
built from real (non-phantom) trades, that warrants a new
investigation. None is open at this time.