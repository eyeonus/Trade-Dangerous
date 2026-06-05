# Slice 17 — Progress-toward-a-target routing (`--towards`)

## Status

Partly implemented, with a mid-slice design correction recorded here. The gate,
validation, target resolution, the strict-progress filter, and the failure type
are written (steps 1–3 below). The first build ranked the surviving candidates by
profit, which made the route meander toward the target instead of heading at it.

That was a misreading of the spec's requirement keywords (RFC 2119 / BCP 14):
"each hop **MUST** move closer" is an absolute requirement; "a route **MAY**
optimise profit among forward-progress candidates" is genuinely optional and
cannot override the MUST. Progress is therefore the ranking; profit is only a
discretionary tie-breaker among already-compliant hops. The corrected design is
below, and the remaining code work is the ranking rework (step 4).

The legacy `--towards` behaviour was reviewed once, with Tromador's explicit
authorisation for this named purpose, to settle the reading — see "Ranking".

## What Slice 17 is

The `--towards` route modifier. It lets a commander say "trade while heading
toward this system" without pinning the route to end there. The planner still
chooses the destination, but every trade hop must make real geographic progress
toward the named target — no meandering, no profitable detour that moves away.

It is **not** `--to`. `--to` fixes the final station and the route must arrive.
`--towards` heads **directly** at the target, trading as it goes: each hop lands
nearer the target than the last, and the planner takes the most direct progress
it can, not the most profitable detour. When a hop can reach the target it does,
and the route stops there — "arrived after N hops". If the hop count runs out
first, that is fine: you end up as close as the route could get, not necessarily
there. With enough hops and jumps you arrive; the option does not promise it.

## Semantics — the contract

Drawn from `trade_run_black_box_spec.md`: option contract (line 171), early
validation (line 229), route ranking (line 492), the **towards mode** section
(lines 556–564), and the failure list (line 682).

Read with the spec's requirement keywords (RFC 2119 / BCP 14) — the wording is
deliberate and the keywords are load-bearing.

- **Intent.** Trade while moving toward a target system, **not** meander.
- **MUST — progress.** Each selected trade hop **MUST** land strictly closer to
  the target system than the previous trade position was — *unless* the hop
  reaches the target system itself. **MUST NOT** choose a hop that moves away or
  leaves the route no closer. Absolute; no discretion.
- **MAY — profit.** A route **MAY** optimise profit among the forward-progress
  candidates. This is genuinely optional and subordinate: it may pick between
  hops that already comply, but it can never soften the MUST or pull the route
  off the most direct progress. So **progress is the ranking; profit is only a
  tie-breaker** among already-compliant hops. (The first build inverted this —
  profit chose the winner, so the route meandered.)
- **ls-penalty untouched.** The protected `--ls-penalty` curve does not change.
  Under `--towards` it simply is not the primary ranking key — progress is; the
  practical-value score (profit/ls-penalty) serves only as the tie-breaker.
- **Arrival and early stop fall out of the rule.** Because ranking always takes
  the most direct progress, the route reaches the target as soon as a profitable
  hop can. Once there, nothing is strictly closer, so no hop can satisfy the
  MUST — the route ends. Arrival and the early stop are not separate features;
  they emerge from progress-first ranking plus the strict filter.
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

`fetch_open_ended_trade_candidates` is the single seam for the **filter** (the
MUST). The one-hop path calls it once; the multi-hop forward engine calls it at
**every** expansion node, with that node's landed station as the anchor (= the
previous trade position). So the progress filter added there serves every towards
shape and every hop at once. The **ranking** (the MAY) plugs in separately, at
the candidate-selection points the engines already own — see Mechanism → "The
MAY".

## Mechanism

### The MUST — the progress filter (built)

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

### The MAY — ranking the survivors (the correction)

The filter decides which hops are *allowed*; ranking decides which allowed hop
*wins*. This is where the first build was wrong: it ranked the survivors by
practical value (profit), so the route took the most profitable closer-system
each hop and drifted toward the target instead of heading at it.

Corrected: among the progress candidates, rank by **how much closer to the
target** the hop lands — the candidate nearest the target wins. Profit is the
discretionary tie-breaker only, used among candidates that are equally good on
progress. The route therefore heads directly at the target; it never trades
its way off the most-direct line.

Two consequences that need no extra machinery:

- **Arrival.** The nearest-to-target candidate is, when reachable with a
  profitable trade, the target itself — so the route lands on the target as soon
  as it can.
- **Early stop.** After arrival nothing is strictly closer, so the next hop has
  no admissible candidate and the route ends naturally at fewer than `--hops`.

Where it applies (the selection points, keyed on the canonical target — one
shared meaning, not a per-engine reimplementation):

- one-hop: the candidate pick in `route_onehop._best_open_ended_plan`.
- multi-hop: the per-node top-K keep in
  `route_common.best_open_ended_hop_candidates` and the chain selection in
  `_plan_open_anchor_route`. The beam keeps the K *closest* progressing options
  (not just the single closest), so a direct-but-dead-end first choice does not
  strand the route — the onward-viability check already guards intermediate
  hops.

**Legacy reference.** Reviewed once, with Tromador's explicit authorisation for
this named purpose, to confirm the reading. The archived goal scoring
(`archive/tradedangerous/tradecalc.py:1255–1267`) makes distance-reduction to the
goal the dominant term and adds profit-per-ton divided by 25 — "Biggest reward
for shortening distance to goal … Gain per unit pays a small part". That is one
way to exercise the MAY; it confirms progress-first, profit-secondary, but its
exact constants are not binding. The rework uses a clean progress-first ordering
(closest wins, profit breaks ties) rather than copying the legacy weights, and
does not touch the protected ls-penalty curve.

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
  target system id + coordinates). Both halves consume that one canonical value:
  the **MUST** filter at the `fetch_open_ended_trade_candidates` seam, and the
  **MAY** ranking at the candidate-selection points the engines already own.
- The route engines do **not** each grow their own towards *semantics*. The
  distance-to-target progress comparison comes from one shared helper; an engine
  applies it where it already selects (one-hop pick, multi-hop keep/chain), but
  it does not re-decide what "closer" or "progress" means.
- No parallel `route_*._towards()` helpers; no copied progress logic. One filter
  predicate builder, one progress/ranking comparison, both keyed on the
  canonical target.

Do not unify the engines; do unify the contract — this slice unifies the
contract (the filter and the progress ordering) and leaves each engine's
search *strategy* its own.

## Steps

One logical step at a time, review between each. Steps 1–3 are written; step 4
is the remaining code work (the ranking correction); step 5 is docs.

1. **Gate + validation.** *[built]* Drop `--towards` from the "unsupported"
   lists in the parser (`run_cmd.py`) and in `validation.py`. Keep the existing
   `--towards` requires `--from` check. Add the `--towards` + `--to` rejection
   ("specify one or the other") alongside it.
2. **Resolve the target + the progress filter.** *[built]* Resolve `--towards`
   to a target system (coordinates) at dispatch and carry it as canonical
   request state into the open-destination engines. Add the strict-progress
   filter to `fetch_open_ended_trade_candidates`, built by one shared helper,
   active only when a target is set. With no target the query is byte-for-byte
   as today. This is the **MUST**.
3. **Failure path.** *[built]* When the open search yields no route under the
   progress constraint, raise the "no route satisfying towards progress" failure
   naming the target.
4. **Progress-first ranking + arrival reporting.** *[the rework]* This is the
   **MAY**, corrected. Rank the progress candidates by closeness to the target
   (profit only as a tie-breaker) at the one-hop candidate pick and at the
   multi-hop per-node keep and chain selection — keyed on the canonical target,
   no per-engine reinterpretation. When the winning route's last hop lands in
   the target system, report it as arrival ("arrived after N hops") rather than
   as a partial / no-viable-continuation route, since the early stop is the
   intended outcome, not a shortfall.
5. **Documentation** (after code accepted): `SPEC_STATUS.md`, `BASELINE.md`,
   `INDEX.md`, and the Slice 17 completion report.

## To confirm during the ranking rework (step 4)

- **Ranking key.** Rank candidates by destination distance to the target
  (closest wins); break ties on the existing practical-value score. For the
  multi-hop beam, the per-node keep and the chain pick order on closeness to the
  target — confirm this composes with the existing beam trim and onward-
  viability check without stranding a route on a direct-but-dead-end first hop.
- **Arrival reporting.** Detect "winning route's last hop is in the target
  system" and surface it as "arrived after N hops". The multi-hop engine already
  returns short routes with a partial-route warning when expansion runs dry;
  reuse that hop-count path but label the target-reached case as success, not a
  shortfall.
- **Performance.** Progress-first ranking is a different sort key over the same
  filtered candidates, so it adds no fetch cost. The slow open-multi-hop search
  is existing engine behaviour, not introduced here; watch but don't fold an
  engine-speed fix into this slice.

## Acceptance — spot-checks, handed to Tromador

```text
--from X --towards Z --hops N   -> heads directly at Z, each hop strictly closer;
                                   arrives and stops early when Z is reachable
                                   ("arrived after K hops", K <= N), else gets as
                                   close as it can within N hops
--from X --towards Z (ample range/hops) -> arrives at Z in fewer than N hops and
                                   reports the arrival
--from X --towards Z --hops 1   -> single hop that lands nearest Z (the target
                                   itself if a profitable hop reaches it)
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
- Reshaping the search engine's strategy or speed — the slow open-multi-hop
  search is existing behaviour, untouched here.
- Changing the protected `--ls-penalty` curve — unchanged. Ranking *order* under
  `--towards` becoming progress-first is the slice's job (in scope); the curve
  itself is not modified, and serves only as the tie-breaker.

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
