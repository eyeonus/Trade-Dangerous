# Slice 29 — `--unique` and `--loop-interval` (No-Revisit Route Constraints)

*Implementation plan. Revised after audit — the audit findings and the
worker's additions are folded in; the headline change from the first draft is
that the revisit filter lives **inside** the candidate helpers, not at the
caller.*

Both options are built together: they are the same constraint at two strengths.

---

## 1. What the spec asks

From `trade_run_black_box_spec.md`:

- `--unique` — do not visit the same **station** more than once
  (lines 178, 496, 586).
- `--loop-interval N` — do not revisit a station until at least `N` hops have
  passed since the previous visit (line 588). `N < 2` is invalid (line 590).
- Early failures: `--loop` with `--unique` (line 233); `--loop-interval` below 2
  (line 237).
- Ranking: a route that violates the constraint must **never outrank** one that
  satisfies it (line 498).
- If a requested unique / loop-interval route is impossible under the hop count
  and station set, **fail clearly** (line 592).

**They are one constraint.** `--unique` is `--loop-interval` with the gap set to
the whole route — "never revisit." Build the loop-interval machinery; unique is
its unbounded case.

---

## 2. Why this is harder than `--avoid`

`--avoid` resolved once into a static id set — the same exclusion for every
chain, known before the search runs, pushed straight into SQL.

`--unique` / `--loop-interval` are **path-dependent per-chain state.** Whether a
station is allowed depends on where *this particular partial route* has already
been, and it changes as the chain grows.

Consequences:

- **It cannot live in SQL.** It is a search-time route-topology rule, not a
  market-eligibility filter. Which rows are *fetched* does not change.
- **Blast radius is the frontier search.** No change to cargo fitting, the score
  curve, or the galaxy-wide prompts.
- **The precedent exists.** `--via` put per-chain state (`via_satisfied`) on
  `_FrontierNode`, made the trim key history-aware, and added an in-helper
  reservation so a must-reach station survives the top-K trim. We reuse all
  three ideas.

---

## 3. The three places the rule must act

This is the spine of the build. The rule is not one filter in one place — it
acts at three distinct points, each fixing a different failure mode.

### 3.1 Candidate selection — *inside* the helpers

**Why caller-side filtering is wrong.** The candidate helpers rank and cap at
top-K and stream with an early stop: "once the next ceiling cannot beat the
floor the stream is abandoned — the remaining stations are never read out of the
database" (`route_common.py:1135`). If illegal revisits fill the top-K, or an
illegal high-score candidate raises the kept-score floor, **legal candidates
below the cut are never read.** Filtering only what the helper *returns* can
therefore produce a worse route or a false collapse.

**The fix.** Pass the expanding node's **forbidden station-id set** into the
helper. The helper skips those open stations *at the stream-consume point* —
before they count toward top-K or move the threshold. Skipped illegal stations
never starve legal ones, so the stream keeps reading legal candidates until it
has top-K legal or is genuinely exhausted. (This subsumes the "over-fetch /
refill" idea — there is nothing to refill if the illegal ones never consumed a
slot.)

**The precedent.** The helper already reserves `required_station_ids` "past the
top-K trim, so a station the route must reach is never trimmed away"
(`route_common.py:1089`). This is the mirror: a set the helper must *exclude*
rather than *reserve*.

**All three seams need the parameter** — they are distinct helpers:

| Helper | Module | Role |
|--------|--------|------|
| `best_open_ended_hop_candidates` | `route_common.py:1025` | open-anchor expansion + final; `--via` |
| `best_open_ended_trades_from` | `route_anchored.py:516` | fixed-terminal intermediate hops |
| `best_fixed_pair_trade_from` | `route_anchored.py:726` | fixed-terminal final hop, vs the fixed Y |

The fixed-Y case is trivial (Y is a single station — legal or not), but it
**must** still be checked, or `--unique` could "complete" a route onto an
already-visited terminal.

### 3.2 Child construction — roll history forward, orientation-aware

See §4 — this is the regression-prone part and gets its own section.

### 3.3 Frontier trim key — don't coalesce away a distinguishable legal chain

Even once legal candidates are fetched (§3.1), the frontier trim can still
discard a legal chain. Today an engine keeps the best-scoring chain per station
(open) or per system (fixed-terminal). Two chains at the same place with
different histories are **different search states** — one may still complete the
route, the other may have burned a station it needs. So the trim key gains a
history fragment:

| Engine | Current key | Add |
|--------|-------------|-----|
| Open-anchor (`route_common.py:846`) | `station_id` | `(station_id, _revisit_key(node))` |
| Fixed-terminal (`route_anchored.py:358`) | `system_id` / `(root, system)` | fold `_revisit_key(node)` in |
| `--via` (`route_via.py:168, 179`) | `(station, mask, lane, root)` | add `_revisit_key(node)` |

The fixed-terminal trim is a *diversity* dedupe (one chain per system); folding
the history fragment in keeps distinguishable chains alive but lets more than
one chain per system survive. Sanity-check that we are not trading away the
spatial spread the dedupe exists to provide (probe, §8).

---

## 4. Orientation — the regression-prone part

`visited_order` is stored in **route order** (origin → … → terminal). The
history derivations assume that order, so the roll-forward must respect it — and
the open-origin engine grows the chain **backward**.

For `open_role="source"` the helper runs backward (`route_common.py:1052`):
`trade.destination_station` is the chosen *source*, so the new child stands
**earlier** in route order than its parent. `_make_open_child`
(`route_common.py:1534`) currently takes no role and would *append*, building
reversed history. `--via` to-only shapes also use `open_role="source"`, so they
inherit this.

The rule, made explicit:

```text
forward growth  (open_role="destination"; fixed-terminal):
    APPEND the new station to visited_order
    interval window = the TAIL:  visited_order[-(N-1):]

backward growth (open_role="source"; --via to-only):
    PREPEND the new station to visited_order
    interval window = the HEAD:  visited_order[:N-1]
```

`--unique` is orientation-agnostic (membership in the whole set is symmetric).
**Only `--loop-interval` cares** — but it cares completely, so the orientation
must be threaded, not assumed. `_make_open_child` gains `open_role` (or a small
orientation-aware roll helper sits beside it).

---

## 5. Shared contract (unify the contract, not the engines)

Resolve the revisit rule once from `RunRequest` into canonical state:
`none` / `unique` / `interval(N)`. The options already parse and carry onto
`RunRequest` (`unique: bool`, `loop_interval: int | None`).

Add one field to `_FrontierNode`, mirroring `via_satisfied`:

```python
visited_order: tuple[int, ...] = ()   # station ids, route order
```

Seeded at the hop-0 node with `(origin_station_id,)` in each engine's seed
construction (the same places `via_satisfied` is seeded). Default `()`, so when
no rule is active the field is inert and every existing run is byte-identical.

Three shared helpers in `route_common`:

- `_revisit_forbidden(node, request, *, orientation) -> frozenset[int]` — the
  set the candidate helpers skip (§3.1):
  - unique → `frozenset(node.visited_order)`
  - interval-N forward → `frozenset(node.visited_order[-(N-1):])`
  - interval-N backward → `frozenset(node.visited_order[:N-1])`
- `_revisit_roll(parent_order, station_id, *, orientation) -> tuple` — append or
  prepend per §4.
- `_revisit_key(node, request) -> Hashable` — the trim-key fragment (§3.3),
  **canonically ordered for determinism**:
  - unique → `tuple(sorted(node.visited_order))` — set membership only, so
    sort; two equal-set chains coalesce.
  - interval-N → the route-order window tuple (`[-(N-1):]` forward,
    `[:N-1]` backward) — **not** sorted: order matters here, because the window
    slides as the chain grows, so two same-set/different-order chains are
    *different* states and must not coalesce.
  - none → `()`.

A raw `frozenset` must never enter a tie-break sort — the via trim is
deterministic on purpose (`_lane_sort_key`, "never by dict iteration order"),
and `tuple(sorted(...))` / route-order tuples keep that property.

---

## 6. Failure classification

Add `NoUniqueRoute(NoReachableRoute)` to `failures.py`, mirroring
`NoLoopRoute` / `NoViaRoute` (covers both unique and loop-interval).

Because the filter lives inside the helper (§3.1), the helper is where the
bookkeeping lives: it counts open stations skipped *solely* for the revisit rule
(a counter on `ExpansionStats`). A collapse today falls through to a partial
route or `NoProfitableTrades` (`route_common.py:812-842`) and cannot tell
"revisit-blocked" from "nothing profitable."

New rule at each collapse point — open expansion, open final correction,
fixed-terminal intermediate, fixed-terminal final, via collapse: if a layer
collapsed with **no legal continuation anywhere** *and* the revisit-skip counter
fired, raise `NoUniqueRoute` (naming the option), instead of falling through to
the partial / no-profit path.

Mixed-cause corner (some nodes had no data, others were revisit-blocked): name
`NoUniqueRoute` anyway — it is the actionable constraint for a user who set the
flag. This matches the existing aggregate failure-classification approach used
for matrix endpoints (SPEC_STATUS §Failure behaviour).

---

## 7. Validation / un-gate

In `validation.py`:

- Remove `--unique` and `--loop-interval` from the `unsupported` tuple
  (lines 172-184).
- Add early failures:
  - `--loop` with `--unique` → `ContradictoryOptions` (spec line 233).
  - `--loop-interval < 2` → `InvalidNumericOption` (spec line 590).
  - **`--unique` with `--loop-interval` → `ContradictoryOptions`** (decided):

    > `--unique already forbids all station revisits; do not combine it with
    > --loop-interval.`

    Rationale: same constraint axis at different strengths; silent precedence
    would make the user's `--loop-interval N` inert; matches the rewrite's
    explicit "fail clearly" posture. No CLI precedent here for silently
    accepting a redundant stronger constraint, so we do not invent one.
- **`--loop` with `--loop-interval` is allowed** — the spec lists loop+unique as
  a failure but is silent on loop+interval, and it is sensible (a minimum gap
  before returning to the start). Feasibility (`hops >= N`) surfaces as a clean
  `NoUniqueRoute` if the search cannot close; see §9.

---

## 8. Verification and probes

- **Inert proof:** non-unique benchmark shapes byte-identical before/after (the
  field defaults to `()`), the proof `via_satisfied` used.
- **Validity:** `--unique` and `--loop-interval N` across fixed-terminal, open
  destination, open origin, unanchored, and via — no repeated station (unique),
  gap respected (interval) in the emitted routes.
- **No spurious failure:** a case where the unconstrained best route revisits but
  a valid unique route exists — confirm we find it, not `NoUniqueRoute`.
- **Validation:** `--loop --unique` rejected; `--unique --loop-interval`
  rejected with the message; `--loop-interval 1` rejected; `--loop
  --loop-interval N` valid and closes when `hops >= N`, fails clearly when
  `hops < N`.
- **Timing:** the run *shape* is unchanged — unique must not balloon wall-clock.

Two targeted probes (the riskiest fixes):

1. **Top-K legality probe** — find/construct a parent whose best candidates
   include illegal revisits ranked *above* a legal continuation. Confirm the
   helper still returns the legal continuation (so §3.1 works), rather than
   collapsing after filtering its returned top-K.
2. **Backward interval probe** — a to-only / open-origin route with
   `--loop-interval N`; inspect the emitted station sequence and confirm the gap
   is checked in **route order**, not backward construction order (so §4 works).

A third check, lower stakes: `--unique --via`, watching the reservation set
(`required_station_ids`) against the per-chain forbidden set for any odd
interaction.

---

## 9. How loop-interval composes with `--loop`

Stated because it shows the design composes without a carve-out. A loop's
closing hop returns to the origin — origin is at index 0 of `visited_order`,
revisited at hop `H`, so the gap is `H`. The interval-N filter permits that
close exactly when `H >= N`, and forbids any *earlier* return to origin — the
correct behaviour. No origin special-casing; the loop terminal rule and the
revisit filter are orthogonal. Loop runs on the fixed-terminal engine, so it
exercises the forward (append / tail-window) orientation.

---

## 10. What this does NOT touch

- No SQL / candidate-fetch change (the constraint is not expressible in SQL and
  does not change which rows are fetched — only which *returned* candidates a
  node may use).
- No cargo-optimiser change.
- No `score.py` / ls-penalty change.
- No change to beam widths or the galaxy-wide confirmation prompts.

---

## 11. Touch-point summary

| File | Change |
|------|--------|
| `validation.py` | Un-gate; loop+unique, unique+interval, interval<2 early failures. |
| `route_common.py` | `visited_order` on `_FrontierNode`; `_revisit_forbidden` / `_revisit_roll` / `_revisit_key`; orientation-aware roll in `_make_child_node` / `_make_open_child` (latter gains `open_role`); forbidden-set parameter + skip + revisit-skip counter in `best_open_ended_hop_candidates`; open-engine trim-key change; collapse → `NoUniqueRoute`. |
| `route_anchored.py` | Seed `visited_order`; forbidden-set parameter + skip in `best_open_ended_trades_from` and `best_fixed_pair_trade_from`; fold `_revisit_key` into the dedupe key; collapse → `NoUniqueRoute`. |
| `route_via.py` | Seed `visited_order`; fold `_revisit_key` into `_coalesce_key` / `_lane_key`; collapse → `NoUniqueRoute` (filter inherited via the shared helper). |
| `route_single_anchor.py`, `route_unanchored.py` | Seed `visited_order` where they build the seed frontier. |
| `run_result.py` | Revisit-skip counter field on `ExpansionStats`. |
| `failures.py` | `NoUniqueRoute(NoReachableRoute)`. |
| `route_onehop.py` | None — single trade is two distinct stations; interval needs ≥ 2 hops. |

Living docs (`BASELINE.md`, `SPEC_STATUS.md`, `INDEX.md`) updated on completion.
