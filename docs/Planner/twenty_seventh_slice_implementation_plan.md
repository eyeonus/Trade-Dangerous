# Slice 27 — `--via` (Route Through Waypoints)

*Implementation plan, **revised after audit**. This supersedes the leg-stitching
design committed at `a580fd86`, which is withdrawn. The audit established that the
Step-2a via-satisfaction **state model is sound** and that the failure was its
**execution policy** — exact, real-credit cargo optimisation inside a wide beam
while the route was still locating the waypoint. The correct response is: retain
the state, replace the expensive expansion. No implementation until this revision
is reviewed.*

---

## Why

`--via SYSTEM|STATION` forces the route through one or more named waypoints. The
spec sets **no anchoring requirement** on it; we require at least one anchor
(`--from` or `--to`) as a chosen variation — a fully-unanchored via is both
unbounded and redundant (with both ends free, the cheapest way to "include" a
place is to start or finish there).

---

## Contract (spec §Via semantics, §Route ranking, §Failure)

- Repeated / comma-separated **systems or stations**. A station via is met by
  visiting that station; a system via by visiting any station in that system.
  **Order is free.**
- Conflicts with `--avoid` if the via place — or, for a station, its system — is
  avoided.
- Too few hops for the vias plus the fixed endpoints → fail **before** search, or
  as early as the impossibility is known.
- No satisfying route → `NoViaRoute` (family "no route satisfying via
  constraints"). **No partial-via routes** — fail clean (the `--loop` stance).
- A route violating a via never outranks one satisfying it; among satisfying
  routes, rank by profit.

---

## What the audit confirmed is right, and is kept

These Step-2a assets are **retained**, not removed:

- `_FrontierNode.via_satisfied` — the satisfaction set, tagged
  `("system", id)` / `("station", id)` (no id-space collision).
- `_via_satisfied_by()` — marks satisfaction from the **actual** station DTO, and
  correctly lets one station visit satisfy both an exact station via and its
  containing-system via.
- `_via_full_set()` — the complete requirement set.
- Mask-aware frontier **deduplication** — two chains at the same system are not
  equivalent when they hold different satisfaction sets (or, for loops, different
  roots).
- **Full-mask finalist filtering** after the final hop — so a via at `--to` can be
  satisfied by the final hop, while any sub-full-mask route is refused.
- **Loop-root identity** carried alongside via state.

The state model handles unordered vias, overlapping requirements, a via reached
before it was "targeted", a via equal to the origin, and a via reached on the
final hop — all without an ordered leg list.

---

## What is replaced — the execution policy

The cliff (live evidence: `--from Lave --to Zaonce --via shinrarta/ --hops 4
--jumps-per 2` → cargo 236s of 244s, branch-and-bound 4980× vs ~4 normal) came
from the **fixed-terminal engine's exact, real-credit expansion**
(`best_open_ended_trades_from` → `optimise_cargo` with the real budget, which
enters branch-and-bound whenever credit binds) being run on every frontier node
while the beam wandered the high-priced core trying to locate the waypoint.

The replacement is **credit-optimistic expansion + one end-to-end correction**:

- Expand with the optimistic primitive (`best_open_ended_hop_candidates`,
  `_OPTIMISTIC_PRICE_PER_TON` budget) — cargo fits as if money is no object, so
  the greedy fast path is taken and branch-and-bound does not fire during search.
- Carry the satisfaction mask through expansion, unchanged in meaning.
- Correct **once, end-to-end**, in forward money order, after complete candidate
  routes exist — the existing `_correct_open_anchor_chain` model, re-fitting each
  hop against the real running budget and dropping any chain that cannot afford
  its trades. Exact cargo therefore touches only complete candidates, never the
  thousands of intermediate expansions.

This is the open engine's optimistic/correction backbone applied to the retained
mask state.

---

## The via search — one authoritative search owner

A single search owner (one **absolute hop clock**; new module `route_via.py`, or a
clearly-bounded function), built from the optimistic primitives. Responsibilities:

### 1. Expansion — optimistic, mask-carrying
Each node expands via `best_open_ended_hop_candidates` (optimistic). Each child
updates its mask via `_via_satisfied_by()`. `open_role` follows the search
direction (forward from `--from`; backward from `--to` when `--from` is open).

### 2. Steering — distance as a heuristic, never a hard order, never `--towards`
The candidate fetch is narrowed toward the chain's **prospective next owed via**
(its system coordinates), or — once the mask is full — toward the terminal
(`--to` / loop root), reusing the Step-2a envelope geometry
(`_envelope_is_provably_loose`, the per-target radius). Critically:

- The steering target is a **separate** value from `request.towards_target`.
  `request.towards_target` activates the strict "every hop must be **closer**" SQL
  predicate at the open-destination fetch — a hard constraint `--via` never asked
  for, which would reject a via reachable only via a sideways or temporarily
  outward hop. The via steering target is used **only** as a fetch-narrowing
  envelope (a necessary remaining-range bound) and a ranking/diversity heuristic,
  never as that strict predicate.
- The order in which vias are visited is **not fixed**. Distance picks each
  chain's prospective next via as a heuristic; another via may be satisfied
  incidentally; no global nearest-first order is imposed.

### 3. Beam diversity — explicit, by (mask, next-via, loop-root)
The frontier reserves capacity per **(satisfied mask, prospective-next-via, loop
root)** rather than trimming purely by score. This stops a high-profit
zero-progress state from consuming the whole beam (the starvation that, with the
old policy, let the search wander without ever converging on the waypoint), and
keeps chains heading toward **each** owed via alive. The mask space is `2^k` and
next-via choices `≤ k`; vias are few (1–3), so this is bounded.

### 4. Exact station via retention
A station via's system is reached like any other, but **every station in that
system ties on distance**, so the requested exact station can lose the profit
tie-break and be trimmed before the arrival test sees it. The owner **explicitly
retains** an owed station-via destination when its system is in reach (a reserved
candidate slot / targeted fetch / priority ahead of ordinary system-distance
ties). A post-trim station-id test alone is insufficient.

### 5. Finalists and correction
A finalist must carry the **full mask** AND satisfy the endpoint constraint (be at
a `--to` station / close the loop on its root / be an admissible emerged open
end). Complete candidates are corrected **end-to-end** (forward money order); the
best corrected satisfying route wins. No mid-route correction, no `PlannedRoute`
→ frontier-node conversion.

### 6. Proven non-binding optimistic credit
"Optimistic = no branch-and-bound" holds only if the optimistic budget **cannot
bind**. `_OPTIMISTIC_PRICE_PER_TON` is a fixed constant; under `--max-price 0` the
configured price ceiling is removed and a market row can be arbitrarily expensive,
so the constant is not a proof. The owner must make non-binding **explicit**:
either a per-fetch budget derived from the candidates' own maximum buy price
(`capacity × max_price + ε`, guaranteeing any single-commodity fill is
affordable), or a deliberate no-credit-limit optimiser mode for the expansion
pass. Relying on the observed constant is not acceptable.

---

## Route-shape handling

| Shape | Direction / steering | Endpoint enforcement | Notes |
|-------|----------------------|----------------------|-------|
| `--from X --to Y --via …` | forward from X; steer to next owed via, then to Y | finalist at a Y station, full mask | both anchors fixed |
| `--from X --via …` (open dest) | forward from X; steer to next owed via, then open | full mask; best emerged open end | route may end at a via |
| `--to Y --via …` (open origin) | **backward** from Y; steer to next owed via, then open origin | full mask; best emerged origin | one end-to-end correction once origin emerges |
| `--loop --from X --via …` | forward from X; steer to next owed via, then to root | finalist closes on its own root, full mask | loop-root identity preserved through every frontier op |
| positioning (`--start-jumps`/`--end-jumps`) | eligible stations seeded from the anchor's bubble | as the underlying shape | a via == named anchor is **not** auto-satisfied — only the actual seeded route stations mark satisfaction |
| `--via` + user `--towards` | — | — | **rejected** this slice (see Scope decisions) |
| `--direct` + `--via` | — | — | **rejected** this slice (see Scope decisions) |

---

## Scope decisions

**`--via` + `--towards` → reject** (`UnsupportedRunShape`). Deferred because it
combines **two simultaneous steering constraints** (progress toward the user's
target *and* visiting the waypoints), which need a deliberate joint search policy.
Not described as contradictory or impossible. `--from X --towards Y --via Z` is
currently outside the parser's mutual-exclusion group and validation does not yet
reject it, so a `request.via and request.towards_text` rule is added.

**`--direct` + `--via` → reject** (kept as the blanket rejection), recorded as a
**chosen scope restriction** for this slice. The existing "a single direct hop has
no room for a waypoint" rationale is **replaced**: a direct hop's origin or
destination could in principle satisfy a via, so it is not logically impossible —
it is deferred because `--direct` bypasses the reachability model the via search
relies on.

---

## Step-1 corrections (independent of the search design — fix regardless)

1. **Early hop-count validation rewrite.** `_validate_resolved_via()` must receive
   and use **both** fixed endpoints, **loop** mode, and **positioning** mode:
   - credit a via satisfied by a fixed, **non-positioning** `--from` (hop 0) or
     `--to` (terminal); do **not** credit a positioning anchor (the actual
     endpoint is another station in the bubble);
   - reserve a route position for the fixed terminal (`--to`) and the loop close;
   - it must be **sound toward acceptance** — never reject a satisfiable request;
     the search remains the authoritative feasibility check. The current code
     false-rejects `--to Y --via Y --via C --hops 1` (valid as `C → Y`) and
     under-rejects `--from A --to B --via C --hops 1` (impossible) — both fixed by
     the corrected accounting. Cases pinned by the verification matrix below.
2. **Canonical via requirements.** Build requirements from the **deduped** sets
   (`via_system_ids` / `via_station_ids`) with coordinates keyed by tag (the
   Step-2a `via_pos` dict shape), not by iterating the raw `via_targets` token
   list, which carries duplicates (`--via Lave --via Lave`, or a system plus a
   station in that system).
3. **Remove the temporary `[via-diag]` probe** from `route_anchored`.

(The avoid-conflict check and the `via_system_ids`/`via_station_ids`/`via_targets`
carriage stay; resolution and `NoViaRoute` + its CLI rendering stay.)

---

## Reuse / new / removed

**Reused:** the mask state and helpers (`via_satisfied`, `_via_satisfied_by`,
`_via_full_set`); the optimistic primitives (`best_open_ended_hop_candidates`,
`_make_open_child`, `_correct_open_anchor_chain`); the distance/envelope geometry
(`_distance_sq_to_target`, `_envelope_is_provably_loose`, `via_targets` coords);
Step-1 plumbing (resolution, `RunRequest` fields, `NoViaRoute`,
`_planner_result_message`).

**New:** the `route_via` search owner (one hop clock, optimistic + mask + diversity
+ endpoint-finalist + end-to-end correction); the separate via steering target;
the explicit (mask, next-via, root) diversity; exact-station retention; the
derived/non-binding optimistic-credit mechanism; the corrected hop-count
validator; the dispatch branch (`request.via` ahead of the shape branches).

**Removed:** the Step-2a exact-cargo via path in `route_anchored._plan_multi_hop`
(the `via_mode`/`_via_failure` branches, the via-mask use in the fixed-terminal
dedupe/finalist/envelope) — `route_anchored` returns to pure fixed-terminal exact;
the temp probe; the fixed nearest-first leg-ordering idea (never written as code).

---

## Failure behaviour

- Hop-count infeasible up front → `CommandLineError`, before search.
- No satisfying route at search time → `NoViaRoute`, naming `--via` and the
  binding constraints (range / jumps / hops), with the existing lever hint. Raised
  as soon as no full-mask finalist survives — not after futile deep wandering,
  because the diversity reservation makes the search converge or fail fast.
- No partial-via routes.

---

## Adversarial verification matrix (from the audit)

**Ordering**
- two vias where only the non-nearest-first order fits;
- three vias where greedy ordering fails but another order succeeds;
- a system plus an exact station in that system, supplied in both token orders.

**Early validation**
- `--from A --to B --via C --hops 1` (must reject — impossible);
- `--loop --from A --via C --via D --hops 2` (must reject — only one non-origin
  via fits before the loop close);
- `--to Y --via Y --via C --hops 1` (must **accept** — `C → Y`);
- the system and exact-station forms of each;
- each repeated with `--start-jumps` / `--end-jumps`.

**Navigation**
- a via requiring one sideways or temporarily outward hop;
- an avoided direct corridor requiring a detour;
- a geometrically closer station with no viable continuation.

**Exact station semantics**
- a target system with more eligible stations than the expansion width;
- an exact station not among the top profit-ranked stations in its system;
- duplicate station tokens;
- a station plus its containing-system via satisfied by one visit.

**Credits**
- an optimistic leader that becomes unaffordable under correction;
- a lower optimistic finalist that wins after correction;
- fixed-terminal, open-destination and backward open-origin forms;
- `--max-price 0` with unusually expensive market rows.

**Route shapes**
- from + to; from-only; to-only; loop;
- via + user `--towards` (must reject); `--direct` + via (must reject);
- positioning anchors; via equal to the actual route endpoint; via equal only to
  the named positioning anchor but **not** the chosen route endpoint.

**Performance**
- the Shinrarta regression case (seconds, not minutes);
- a via reached early with many hops remaining (no exact-cargo cliff on the tail);
- branch-and-bound counts during expansion vs final correction (single digits in
  expansion);
- non-via baselines byte-identical.

---

## Order of work

1. **Step-1 corrections** (independent of search): rewrite `_validate_resolved_via`
   (both endpoints, loop, positioning; sound toward acceptance); canonicalise via
   requirements; remove the temp probe; add the `--via`+`--towards` rejection and
   reframe the `--direct`+`--via` rationale. Verify the Early-validation matrix.
2. **Roll back** the Step-2a exact-cargo via path in `route_anchored`; confirm the
   fixed-terminal engine byte-identical to pre-2a on the non-via baselines. (The
   mask state and helpers in `route_common` stay.)
3. **The `route_via` owner**: optimistic mask expansion, separate steering target,
   (mask, next-via, root) diversity, exact-station retention, non-binding
   optimistic-credit mechanism, full-mask + endpoint finalists, end-to-end
   correction. Wire the `request.via` dispatch branch.
4. **Verification**: the full adversarial matrix, the Shinrarta case first; the
   branch-and-bound and non-via-baseline checks.
5. **Completion report**; living-doc updates (`SPEC_STATUS` `--via` → `[done]`,
   `BASELINE` owed-list); probes gone; code and docs committed separately.

---

## Docs owed at close

- `twenty_seventh_slice_completion_report.md`.
- `SPEC_STATUS.md`: `--via` → `[done]`; Via-semantics row updated; the two scope
  rejections recorded as deliberate variations.
- `BASELINE.md`: `--via` owed → done; cross-cutting behaviour note.
