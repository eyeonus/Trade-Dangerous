# Slice 17 — Progress-toward-a-target routing (`--towards`)

## Status

Planned, not yet implemented. This document is the agreed design; code proceeds
one step at a time with review between steps, per the project workflow.

## What Slice 17 is

The `--towards` route modifier. It lets a commander say "trade while heading
toward this system" without pinning the route to end there. The planner still
chooses the destination, but every trade hop must make real geographic progress
toward the named target — no meandering, no profitable detour that moves away.

It is **not** `--to`. `--to` fixes the final station and the route must arrive.
`--towards` only steers: each hop lands nearer the target than the last, and if
the hop count runs out before the target is reached, that is fine — you end up
closer, not necessarily there. With enough hops and jumps you may arrive; the
option does not promise it.

## Semantics — the contract

Drawn from `trade_run_black_box_spec.md`: option contract (line 171), early
validation (line 229), route ranking (line 492), the **towards mode** section
(lines 556–564), and the failure list (line 682).

- **Intent.** Trade while moving toward a target system, rather than wandering.
- **The hard rule.** Each selected trade hop must land **strictly closer** to
  the target system than the previous trade position was — *unless* the hop
  reaches the target system itself.
- **Hard constraint, not a tie-breaker.** Among hops that make progress, the
  normal practical-value scoring (profit, ls-penalty) still picks the winner.
  But a hop that moves away from the target, or leaves the route no closer, may
  **never** be chosen even when it is more profitable. The protected
  `--ls-penalty` curve is untouched — we filter the candidate set, we do not
  reweight it.
- **Requires `--from`.** The origin is always anchored, so `--towards` never
  touches the open-origin or fully-unanchored shapes. (Spec line 229; the check
  already exists at `run_cmd.py:351`.)
- **Mutually exclusive with `--to`.** The two contradict: `--to` fixes the
  destination, `--towards` only heads that way. Naming the same place makes one
  redundant; naming different places makes them conflict. Decided: reject the
  combination with a clear "specify one or the other" error rather than guess
  intent. (Not an early-failure the spec lists, but the spec does not sanction
  the combination either — this is the agreed resolution.)
- **Distance metric.** Straight-line, system-to-system, from the `pos_x/y/z`
  coordinates, measured to the target **system**. Strict decrease per hop.
- **Same-system hops make zero progress.** Two stations in one system share
  system coordinates, so a supercruise hop within a system does not move the
  route closer. Under the strict rule it is therefore not allowed — unless that
  system *is* the target. This falls out of the metric cleanly.
- **Failure family.** "No route satisfying towards progress" (spec line 682) —
  its own message, naming the target.

## Scope

The open-destination shapes only, where `--from` is given and `--to` is omitted:

- `--from X --hops 1` — single best hop toward the target.
- `--from X --hops N` — multi-hop, every hop progressing toward the target.

The origin may be a station or a system, and `--towards` composes with
`--start-jumps` (the first trade position is the actual first trade station,
wherever the positioning fan-out places it; progress is measured from there).

## Where it plugs in

Both open-destination shapes funnel through one candidate fetch:

```text
route_onehop._best_open_ended_plan        -> data_gateway.fetch_open_ended_trade_candidates
route_common.best_open_ended_hop_candidates -> data_gateway.fetch_open_ended_trade_candidates
```

`fetch_open_ended_trade_candidates` is the single seam. The one-hop path calls
it once; the multi-hop forward engine calls it at **every** expansion node, with
that node's landed station as the anchor (= the previous trade position). So a
progress predicate added there serves every towards shape and every hop at once,
with no per-engine change.

## Mechanism — reuse, not new invention

The constraint is a sphere: the next system must sit inside the sphere centred
on the target whose radius is the anchor's current distance-to-target. That is
the **same shape** as the bbox + squared-distance spatial prefilters already in
that fetch (e.g. `data_gateway.py:1841–1857`), so it goes in as one more SQL
predicate on the candidate destination system.

The anchor system is fixed for a given fetch call, so its distance-to-target is
a Python constant. The comparison stays entirely SQL-side and index-friendly:

```text
dist2(candidate_dest_system, target)  <  anchor_dist2
    OR  candidate_dest_system_id == target_system_id
```

A bounding-box prefilter on the candidate destination coordinates (radius =
anchor distance-to-target, centred on the target) goes alongside the squared-
distance test, mirroring the existing pattern, so the indexed `pos_x/y/z`
columns carry the narrowing before the squared-distance arithmetic runs.

The `OR ... == target_system_id` arm encodes the spec's "unless the hop reaches
the target system" clause: a hop that lands in the target system is always
admissible, including the degenerate case where the anchor already sits in the
target system (distance 0, where strict `<` could not otherwise pass).

### Target resolution

`--towards SYSTEM` resolves to a target system (id + coordinates) **once**, at
planner dispatch, via the existing name resolver — resolution needs a database
session, so it belongs at planner entry, not in pure request parsing. The
resolved target is carried as canonical request state into the open-destination
engines, which hand it to the fetch. If `--towards` happens to name a station,
its parent system is used (lenient, consistent with how `--from`/`--to` system
expansion treats a station's system); to confirm during implementation.

## Architecture — one shared meaning, no per-engine option logic

Checked against the planner's shared-semantics / specialised-engines rule
(BASELINE). This slice complies by construction:

- The meaning of `--towards` is resolved once into canonical request state (the
  target system id + coordinates) and applied in exactly **one** shared place —
  the `fetch_open_ended_trade_candidates` seam.
- The route engines (`route_onehop`, `route_common`'s forward expansion) do
  **not** each grow their own towards handling. They pass the canonical target
  through to the one fetch and consume its narrowed result; they differ only in
  how they then search.
- No parallel `route_*._towards()` helpers. The progress predicate is built by
  one shared helper at the single fetch point.

Do not unify the engines; do unify the contract — this slice unifies the
contract at the fetch seam and leaves each engine's search strategy untouched.

## Steps

One logical step at a time, review between each.

1. **Gate + validation.** Drop `--towards` from the "unsupported" lists in the
   parser (`run_cmd.py`) and in `validation.py`. Keep the existing
   `--towards` requires `--from` check. Add the `--towards` + `--to` rejection
   ("specify one or the other") alongside it. After this step `--towards`
   parses and validates but is not yet honoured — a safe inert state between
   steps, not a ship point.
2. **Resolve the target + the progress predicate.** Resolve `--towards` to a
   target system (coordinates) at dispatch and carry it as canonical request
   state into the open-destination engines. Add the strict-progress predicate
   to `fetch_open_ended_trade_candidates`, built by one shared helper, active
   only when a target is set. With no target the query is byte-for-byte as
   today.
3. **Failure path.** When the open search yields no route under the progress
   constraint, raise the "no route satisfying towards progress" failure naming
   the target. If the engine can cheaply tell "profitable trades exist but none
   progress" from "no profitable trade at all", say which; otherwise fold them
   with a message that still names the target — the same posture as the settled
   "no separate affordability diagnosis" decision.
4. **Documentation** (after code accepted): `SPEC_STATUS.md`, `BASELINE.md`,
   `INDEX.md`, and the Slice 17 completion report.

## To confirm during implementation

- **Single shared predicate helper.** Both fetch entrypoints are the same
  function, so one helper consulting canonical state covers both shapes; confirm
  at the seam there is no second candidate-fetch path that bypasses it.
- **Target resolution path.** Reuse the endpoint resolver; settle the
  station-names-a-target case (use parent system) explicitly.
- **No-progress vs no-trade distinction.** Whether the cheaper "exists but no
  progress" signal is available from the open search, for the failure message.
- **Performance.** The predicate only ever *removes* candidate rows (a sphere
  around the target), so it cannot make the search slower than the unconstrained
  open-destination run; if anything it narrows it. Watch it on a spot-check,
  don't pre-optimise.

## Acceptance — spot-checks, handed to Tromador

```text
--from X --towards Z --hops N   -> multi-hop route; each hop strictly closer to Z;
                                   route need not reach Z
--from X --towards Z --hops 1   -> single best hop that moves toward Z
--towards Z without --from      -> clean CommandLineError (already enforced)
--towards Z --to Y              -> clean CommandLineError ("specify one or the other")
--towards Z, no progressing trade -> "no route satisfying towards progress",
                                   naming Z
default (no --towards)          -> existing open-destination routes unchanged
```

## Out of scope

- `--towards` combined with `--to` — rejected, not supported.
- `--avoid`, `--via`, `--loop`, `--shorten`, `--unique`, `--direct`, and the
  pruning controls — later slices.
- Any reshaping of the per-hop search engine or the scoring curve — Slice 17
  only narrows the candidate set; it does not change how survivors are ranked.

## Validation posture

No automated test harness (project decision). Validation is spot-check plus
flake8 on touched regions. All test commands are handed to Tromador to run; the
agent does not run them automatically.

## Documentation updates (after code is accepted)

- `docs/Planner/SPEC_STATUS.md` — `--towards` option row and the "towards mode"
  behavioural row move to `[done]`; note the `--towards`/`--to` exclusion.
- `docs/Planner/BASELINE.md` — `--towards` added to "what works now"; removed
  from the modifier list in "what's still owed".
- `docs/Planner/INDEX.md` — Slice 17 entry.
- Slice 17 completion report.
