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

Beam-search myopia, not beam concentration.

Slice 8's fix (commit `d6a253d5`) keeps at most one node per
destination system in the global frontier trim, addressing
concentration on near-duplicate stations in high-volume systems.
That fix relies on the system-expanded origin populating the Hop 1
frontier with multiple plausible starting stations. With a pinned
origin, the Hop 1 frontier has only the one origin to expand from,
and the kept set is determined entirely by per-hop accumulated
profit on the destination side. Beam scoring by accumulated profit
favours myopic destinations: a moderate Hop 1 that opens excellent
onward trades is dropped in favour of a stronger Hop 1 that does
not lead anywhere as profitable.

Diagnostics block from the regression run:

```text
Layer 1: 1 in, 1 calls, 50 children, kept 36
Layer 2: 36 in, 36 calls, 649 children, kept 50
Final hop: 50 attempted, 39 reach destination, 253 market candidates, 39 viable
```

Two candidate explanations consistent with this shape, both
unproven without further evidence:

A. The critical intermediate's system (LP 855-34) does not survive
   Hop 1's per-hop profit ranking into the kept 36 unique-system
   frontier nodes.

B. LP 855-34 does survive into Hop 1, but the LP 855-34 -> Delkar
   transition does not survive Layer 2's accumulated-score trim
   of the 649 generated children to the kept 50.

Resolving (A) vs (B) is the obvious first investigation step.

## Suggested first steps

The slice plan should not be written without empirical probes.
Suggested investigation, before any code change:

1. Add probe-only instrumentation to `_plan_multi_hop`
   (`tradedangerous/planner/run_route.py:613`) that records the
   destinations of the kept frontier nodes per layer. Cheap to
   add since the frontier is already in hand at the moment of
   the trim. Re-run the regression command and inspect the
   recorded frontiers; this answers (A) vs (B) directly.

2. If LP 855-34/Acton Port is not in Layer 1's kept set (case A),
   the question becomes: by which Layer 1 candidates was it
   outscored, and is the scoring criterion correct? If it is in
   Layer 1's kept set but its onward transition dies at Layer 2
   (case B), the question becomes: how does the trim decide which
   50 of 649 to keep, and is that decision sound for the
   fixed-station shape?

3. Repeat on a second fixed-station shape before settling on a
   diagnosis. One data point can mislead. Pick a shape the
   `--old` planner solves well and the new one underperforms;
   the existing `--from "Sol/..." --to "Lave/..."` benchmark
   is one, others should be cheap to find.

Once probes localise the loss, the design question is scoped:
widen the beam, change the trim criterion, add look-ahead
potential to the score, or restructure the search shape for the
fixed-station case. A fix should not be picked before the probe.
See `fifth_slice_restructure_implementation_plan.md` for the
project's "probe before fixing" precedent — six empirical probes
ran against the unanchored search before the restructure was
decided not to ship.

## What not to do

- Do not widen the beam by reflex. Layer 2 already keeps 50 of
  649 generated children; reflex-widening produces marginal
  returns at significant wall-clock cost on dense Bubble shapes,
  and the diagnostic value of identifying *why* the right route
  is missing is lost.
- Do not inspect or import from the legacy quarantined modules
  (`tradedangerous/tradecalc.py`, `tradedangerous/tradedb.py`).
  See the project CLAUDE.md "Source Quarantine" section.
- Do not paper over the regression by changing the verification
  shape. The fixed-station shape is supported by the new planner
  (Slice 8 plan, supported shapes); route quality must be
  comparable to `--old`.

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
