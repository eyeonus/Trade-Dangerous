# Slice 27 — `--via` (Route Through Waypoints)

*Implementation plan. Status: in progress. Step 1 (resolution + validation) and
Step 2a (an in-engine via-mask beam) are built; Step 2a is being **replaced** by
the leg-stitching design below after live evidence showed the beam approach has a
catastrophic cost cliff. See "Why this shape".*

---

## Why

`--via SYSTEM|STATION` forces the route to pass through one or more named
waypoints. It is the most-wanted option left on the gated list, and the last big
route-shaping modifier.

The spec places **no anchoring requirement** on `--via` (it is absent from the
"Required early failures" list that names `--towards`/`--start-jumps`/`--end-jumps`/
`--shorten`). We require **at least one anchor** (`--from` or `--to`) as a chosen
variation: a fully-unanchored via is both unbounded (it balloons the way the
unanchored loop did) and redundant (with both ends free, the cheapest way to
"include" a place is to start or finish there, so it asks for nothing a plain
`--from`/`--to` would not).

---

## Contract (spec §Via semantics, §Route ranking, §Failure)

- Accepts repeated / comma-separated **systems or stations** (token style of
  `--avoid`). A station via is met by visiting that station; a system via by
  visiting any station in that system. Order is free.
- Conflicts with `--avoid` if the via place — or, for a station, its system — is
  avoided.
- If hops are too few to fit the vias plus the fixed endpoints, fail **before**
  search, or as early as the impossibility is known.
- If no route satisfies every via, fail clearly (family: "no route satisfying via
  constraints"). Partial-via routes are permitted only if explicitly labelled —
  **we decline them**: fail clean with `NoViaRoute`, never a route that quietly
  skips a waypoint (the `--loop` stance).
- A route that violates a via must never outrank one that satisfies it; among
  satisfying routes, rank by profit as usual.

---

## Why this shape — leg stitching, not an in-engine beam

Step 2a added a per-node "which vias visited" mask to the fixed-terminal beam:
chains carrying different via-progress got their own beam slots, the terminal
envelope re-aimed at the owed via, and only a full-mask chain could win. It is
**correct**, but it pays the fixed-terminal engine's **exact cargo** cost on every
expansion, everywhere the beam wanders.

Live evidence (`--from Lave --to Zaonce --via shinrarta/ --hops 4 --jumps-per 2`):

```
fetch 7.2s, cargo 235.7s of 243.8s total; layer 2 = 239s
cargo fast-path = 4041, branch-and-bound = 4980 (a normal run fires b&b ~4×)
```

Mechanism: the fixed-terminal beam keeps the 50 most *profitable* partial routes,
with no notion of heading toward the via. A waypoint off the profit-optimal line
(Shinrarta sits in the high-priced core, where credit binds and cargo needs
branch-and-bound) drags the beam through that region; it fires the expensive
solver ~5,000 times, never converges on the waypoint, and only fails after
exhausting every hop. All that optimisation is wasted — the route never threads
the via.

The fix is to **navigate to the via cheaply, then route exactly from there**:

> Rank the vias by distance from the origin, nearest first, go `--towards` each in
> turn to reach it, then run the normal route from the last via to the
> destination. (Agreed with Tromador.)

The navigate legs reuse the open engine's **credit-optimistic** expansion (no
branch-and-bound while steering); exact cargo runs only on the final leg and the
end-to-end correction. That is what removes the 4 minutes — we stop solving exact
cargo while merely steering toward a waypoint.

---

## Design

### Vocabulary

- **Via places** `V1..Vk`: the resolved vias (each a system or a station, each
  carrying its *system* coordinates via `request.via_targets`).
- Ordered by **straight-line distance from the anchor**, nearest first.

### Direction follows the fixed anchor

The navigate direction grows from whichever endpoint is fixed:

| Shape | Anchor / direction | Final leg |
|-------|--------------------|-----------|
| `--from X --to Y --via …` | forward from X | fixed-terminal to Y |
| `--from X --via …` (open dest) | forward from X | open-ended best route |
| `--to Y --via …` (open origin) | backward from Y | open-ended best origin |
| `--loop --from X --via …` | forward from X | fixed-terminal closing on X |

Vias are ordered by distance from the anchor. Backward growth uses the existing
`open_role="source"` engine; forward uses `open_role="destination"`.

### The leg loop (orchestrator)

```text
frontier = anchor's eligible stations           # hop_index 0
for Vi in vias ordered by distance from anchor:
    frontier = navigate(frontier, target=Vi, hop_bound)   # arrival beam at Vi
    if not frontier: raise NoViaRoute
route = final_leg(frontier, destination, hop_bound)       # exact / open
if route is None: raise NoViaRoute / the leg's own failure
return route
```

Each navigate leg seeds from the previous leg's **arrival beam** (the stations at
`Vi`, not a single chain), so the final leg can pick the best via-station to pass
through. A via equal to the anchor is already satisfied at hop 0 — its leg is a
no-op.

### One hop budget, tracked per chain

Total `--hops N`. Each chain carries its own `hop_index`; no expansion may push a
chain past `N`. Navigate legs are **progress-first** (closest, then fewest hops —
already how `_node_progress_rank` ranks `--towards`), so a chain reaches its via
in the minimum hops and a near via costs exactly one hop. Each navigate leg is
bounded to leave at least one hop for every remaining via and, where the route has
a fixed terminal (`--to` / loop), one for the final close. The final leg continues
each arrival chain from its own `hop_index` toward the destination.

If any via cannot be reached, or the final leg cannot complete, within `N`:
`NoViaRoute`, raised fast — no full-depth wandering.

### Credit threading

Navigate legs run credit-optimistic (cheap). At the handoff into the **final**
leg, the navigate prefix (origin → … → Vk) is run through the existing forward
credit-correction so the final leg starts from a **real** credit state, and any
navigate prefix that is unaffordable under the real budget is dropped there. The
final leg then runs normally — fixed-terminal exact for `--to`/loop, the open
engine (optimistic + its own correction) for an open destination. The whole route
ends up on real credits, consistent end to end.

---

## The seams (from reading the code)

### Reused as-is

- `best_open_ended_hop_candidates` — the credit-optimistic per-node expansion
  (fast-path cargo, no b&b). The navigate engine's workhorse.
- `_make_open_child`, `_correct_open_anchor_chain` — open child construction and
  the forward credit-correction pass.
- `_node_progress_rank` / `_route_progress_rank` — progress ranking (closest,
  fewest hops, profit last). Confirmed in code: minimum-hop arrival is already
  what these reward, so the navigate leg will not burn hops on a tour.
- `_plan_open_anchor_route` (route_common) — already takes a `seed_frontier`, so
  the **open-destination** final leg can be seeded from the via-arrival beam
  directly.
- Step-1 plumbing: `resolver.resolve_via_tokens`, `ResolvedVia` / `ViaTarget`,
  `RunRequest.via_system_ids` / `via_station_ids` / `via_targets`, the validation
  rules (anchor-required, hop-count, avoid-conflict, `--direct` exclusion),
  `run_cmd` wiring, `failures.NoViaRoute`, the `_planner_result_message`
  `NoViaRoute` case.

### New

- **`_navigate_to_target`** (route_common) — a focused primitive: optimistic
  expansion from a seed frontier toward one target, capturing chains that
  **arrive** and returning the arrival beam (not a finished route). Written to
  reuse the expansion building blocks above rather than refactoring the working
  `_plan_open_anchor_route`/`--towards` path, to keep risk low. Arrival is
  **target-aware**: `station.system_id == target` for a system via,
  `station.station_id == target` for a station via. (The existing `--towards`
  arrival test is system-level only — line ~772 of route_common.)
- **`route_via.py`** — the orchestrator module (one module per shape): order the
  vias, run the leg loop, thread the hop budget and credits, build the result.
- **Seed-frontier parameter on the fixed-terminal engine** — `_plan_multi_hop`
  (route_anchored) currently builds its hop-0 frontier from `origin_stations` at
  zero credits. It gains a seed-frontier path so the `--to`/loop final leg can
  continue from the via-arrival beam, carrying each chain's `hop_index` and credit
  state. (`_plan_open_anchor_route` already has this; only the fixed-terminal one
  needs it.)
- **Dispatch** — a `request.via` branch in `run_route.plan_route`, ahead of the
  shape branches, routing to `route_via.plan_via_route`.

### Replaced / removed (Step 2a rollback)

The via no longer rides the fixed-terminal beam, so the 2a additions to
`route_anchored` come out: the `via_satisfied` field's use in the dedupe key,
finalist filter, envelope re-aim, and the `via_mode` / `_via_failure` branches in
`_plan_multi_hop`; plus the temporary `[via-diag]` probe. The `via_satisfied`
field on `_FrontierNode` and the `_via_satisfied_by` / `_via_full_set` helpers are
removed unless the seed-frontier work finds a use for them. Step 1 stays intact.

---

## Edge cases

- **via == anchor** (`--via` names the `--from`): satisfied at hop 0; its leg is a
  no-op.
- **via == destination** (`--via` names the `--to`): the navigate leg arrives at
  the terminal; the final leg is empty and the route ends there.
- **open destination** (`--from X --via C`, no `--to`): after the last via, the
  final leg is the open-ended best route; with zero hops left it ends at the via.
- **loop + via**: the final leg is the fixed-terminal close back on the origin,
  after the vias.
- **multiple vias**: ordered by anchor distance; one navigate leg each; the final
  leg from the last.

---

## Failure behaviour

- Hop-count infeasible up front → the Step-1 `CommandLineError` (before search).
- Via unreachable / no satisfying route at search time → `NoViaRoute`, naming
  `--via` and pointing at the constraints (range / jumps / hops), with the lever
  hint already wired in `_planner_result_message`. Raised **fast** — the leg
  structure fails as soon as a via's arrival beam is empty, not after a full-depth
  search.
- No partial-via routes (the `--loop` stance).

---

## Open subtleties to nail at implementation (flagged, not guessed)

1. **Per-chain hop accounting across stitched legs.** The final-leg engines size
   their work from `remaining_hops`; seeded from arrivals at varying `hop_index`,
   they must derive that from each seed chain's `hop_index`, not a zero
   assumption. The fixed-terminal envelope already keys off `remaining_hops`, so
   this is a seeding change, but it needs verifying against the layer loop. If
   stitched threading proves awkward, the fallback is a single hop_index-aware
   loop; start with stitching.
2. **Arrival-beam width.** How many via-arrival stations to carry into the next
   leg. Start at the existing frontier width (50); revisit only on evidence.
3. **Backward direction + via ordering.** For open-origin (`--to Y`, `--from`
   open), order vias by distance from `Y` and grow backward; confirm the arrival
   capture and credit flow read correctly in `open_role="source"`.

---

## Verification (live spot-checks)

- **The Shinrarta case** — `--from Lave --to Zaonce --via shinrarta/ --hops 4
  --jumps-per 2`: now seconds, not minutes; routes through Shinrarta, or fails
  `NoViaRoute` fast. (The headline regression fix.)
- **Via on the natural path** — `--from Sol --to "LHS 3356" --via Altair`: routes
  through Altair, sane time.
- **Multi-via** — two vias; both visited, in anchor-distance order.
- **via == --to**, **via == --from** (no-op leg), **loop + via**, **open-dest via**
  (`--from X --via C`), **open-origin via** (`--to Y --via C`).
- **Failures** — unreachable via (tight `--ly-per`) → fast `NoViaRoute`; hops too
  few → up-front error; via that is also avoided → conflict error.
- **Non-via regression** — two standard fixed-terminal and one open baseline,
  byte-identical (the via path is additive; the 2a rollback restores the
  fixed-terminal engine to its pre-2a form).
- **Cost** — the Shinrarta run's cargo split: branch-and-bound back to single
  digits on the navigate legs, exact cargo only on the final leg.

---

## Order of work

1. **Rollback 2a** in `route_anchored` (remove via-mask use, envelope re-aim,
   `via_mode`/`_via_failure`, the temp probe); restore and confirm the
   fixed-terminal engine byte-identical to pre-2a on the non-via baselines.
2. **`_navigate_to_target`** in route_common (optimistic expand → arrival beam,
   target-aware arrival). Unit-spot-check it reaches a near and a far system.
3. **Seed-frontier parameter** on `_plan_multi_hop`; confirm a hand-built seed at
   hop 0 reproduces the normal fixed-terminal result.
4. **`route_via.py`** orchestrator: order, leg loop, hop budget, credit handoff,
   result build. Wire the `request.via` dispatch branch.
5. **Spot-checks** in the verification list, the Shinrarta case first.
6. **Completion report**, living-doc updates (`SPEC_STATUS` `--via` → `[done]`,
   `BASELINE` owed-list), temp probe removed, code and docs committed separately.

---

## Docs owed at close

- `twenty_seventh_slice_completion_report.md`.
- `SPEC_STATUS.md`: `--via` → `[done]`; Via-semantics row updated.
- `BASELINE.md`: `--via` moved from owed to done; cross-cutting behaviour note.
