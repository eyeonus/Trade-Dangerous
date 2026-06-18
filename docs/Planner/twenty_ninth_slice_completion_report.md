# Slice 29 — `--unique` and `--loop-interval` (No-Revisit Route Constraints)

*Proof of completion. Planned in `twenty_ninth_slice_implementation_plan.md`
(revised after an audit pass); built in six commits, verified on live data.*

---

## Summary

`--unique` and `--loop-interval` are built, together, across every multi-hop
engine. They are one constraint at two strengths: `--unique` forbids visiting a
station twice; `--loop-interval N` forbids revisiting until `N` hops have passed.
`--unique` is the unbounded case of `--loop-interval`.

The build was staged: un-gate + validation, then inert per-chain state, then
enforcement engine by engine (fixed-terminal → open-anchor → `--via`), then the
specific failure message. Each enforcement step was verified on live data before
the next was built.

Commits:

| Commit | What |
|--------|------|
| `d140ff04` | Un-gate; validation rules (loop+unique, unique+interval, interval<2). |
| `9b249b89` | Per-chain `visited_order` threaded through the engines — inert. |
| `88f73042` | Fixed-terminal enforcement. |
| `c0506c3b` | Open-anchor enforcement (open-destination, open-origin, unanchored). |
| `87264c72` | `--via` enforcement. |
| `7a8cc8bd` | `NoUniqueRoute` specific failure. |

---

## The contract reading

Spec §"unique and loop interval": *"`--loop-interval N` forbids revisiting a
station until at least `N` hops have passed since the previous visit."*

Read literally: a revisit is forbidden when the gap (`q − p`, hops since the
previous visit) is `< N`. The implementation matches exactly — the forbidden
window is the last `N − 1` visited stations, which is the same condition.

A consequence worth recording: `--loop-interval 2` forbids only `gap < 2`, i.e.
the `gap = 1` self-move the planner never generates, so **N=2 is inert** and
**N=3 is the first value that bites** (it forbids the immediate ping-pong
B→C→B, gap 2). That is the spec's own design, faithfully implemented — not an
off-by-one. (An off-by-one was flagged mid-slice on a misreading of the parser
help, then retracted when the spec text was checked: the parser's "2 is the
minimum allowed" means only that 1 is the no-op default, not that 2 must bite.)

---

## Mechanism

The rule is path-dependent per-chain state — unlike `--avoid`, which is a static
SQL-side set. It cannot live in SQL; it is a search-time route-topology rule, so
the blast radius is the frontier search only (no change to candidate fetch shape,
cargo fitting, or the score curve).

Three shared pieces in `route_common`, consumed by every engine:

- **`visited_order`** on `_FrontierNode` — station ids in route order, rolled
  forward in the child-builders. **Orientation-aware**: forward growth appends
  (tail window); backward open-origin / `--via` to-only growth (`open_role
  "source"`) prepends (head window). `--unique` is order-blind, but
  `--loop-interval` reads a recency window, so the stored order must be true
  route order, not search-construction order.
- **`_revisit_forbidden`** — the per-chain set the candidate helpers skip.
- **`_revisit_key`** — the trim-key fragment that keeps two chains at one station
  with different histories from coalescing. Canonical (sorted full set for
  `--unique`; ordered window for `--loop-interval`), never a raw frozenset, so
  the deterministic trims stay reproducible.

Two enforcement seams per engine:

1. **The filter lives inside the candidate helpers, not the caller.** The helpers
   stream best-ceiling-first and cap at top-K with a provable early stop; a
   caller-side filter would let illegal revisits fill the top-K or raise the
   kept-score floor and starve legal candidates lower in the stream. So the
   forbidden set is passed into `best_open_ended_hop_candidates`,
   `best_open_ended_trades_from`, and `best_fixed_pair_trade_from`, which skip
   forbidden stations before they consume a slot or move the floor. (This was the
   headline correction from the audit; the first plan filtered at the caller.)
2. **The trim key gains the history fragment** — the open engine's per-station
   coalesce, the fixed-terminal per-system dedupe, and the `--via` per-(station,
   mask, lane, root) coalesce. The `--via` lane-grouping key is deliberately left
   alone: two histories pursuing the same waypoint are the same search direction
   for the fairness trim, and splitting them would over-fragment the lanes.

Runs with no revisit rule are byte-identical: the forbidden set is empty and the
key fragment inert, so every trim key is unchanged.

---

## Validation

- `--loop` with `--unique` → `ContradictoryOptions` (a loop revisits its start).
- `--unique` with `--loop-interval` → `ContradictoryOptions` (reject-redundant:
  the stronger flag would make the interval inert; chosen over silent
  precedence).
- `--loop-interval < 2` → `InvalidNumericOption`.
- `--loop` with `--loop-interval` is allowed — a minimum gap before the route
  returns to its start; infeasibility surfaces as a clean failure.

---

## Failure classification

`failures.NoUniqueRoute` (a `NoReachableRoute` subclass). When a multi-hop layer
collapses *because* the rule forbade every continuation, the search fails with a
message naming the lever and the hop count, instead of the generic no-route
failure.

The trigger is a **per-layer skip delta**: `ExpansionStats.revisit_skips` counts
stations skipped for the rule; each collapse compares the counter against a
snapshot taken at the layer's start. A non-zero delta means *this* layer was
rule-blocked → `NoUniqueRoute`. A zero delta means a plain no-trades-onward
collapse → the existing partial route or generic failure. The guard sits ahead
of the partial-route fallback, so an impossible full-length route fails clearly
rather than silently shortening.

`--loop` and `--via` keep their own `NoLoopRoute` / `NoViaRoute`: the
loop-did-not-close and waypoint-missed facts are the certain headline there, and
those errors already name a specific option.

---

## Verification (live data)

- **Fixed-terminal bite** — `--from sol --to achenar --hops 12`. Baseline
  ping-pongs LFT 65 ↔ Munfayl ↔ Murungh; `--unique` diverges at the first
  revisit and returns 13 distinct stations (160.3M → 140.5M, the bounce's worth
  lost). `--loop-interval 4` keeps the gap-6 Munfayl revisit (allowed) while
  forbidding the gap-3 bounce — profit ordering unique < interval-4 < baseline,
  exactly as the constraint hierarchy predicts.
- **Backward orientation bracket** — open-origin `--to achenar --hops 8`. The
  baseline bounces Sol ↔ Rex (gap 2) at the origin end. `--loop-interval 2`
  reproduces the baseline byte-identical (gap-2 allowed); `--loop-interval 3`
  forbids it. The threshold flips at the bounce's exact gap, proving the backward
  search measures the gap in flight order, not search order.
- **`--via` + `--unique`** — `--from sol --to achenar --via munfayl --hops 8
  --unique`: Munfayl visited once (the via honoured), nine distinct stations (no
  revisit), and the bounce on Munfayl that the unconstrained route would take is
  suppressed.
- **No-revisit runs unchanged** — the inert-field property; spot-checked that
  non-rule runs are byte-identical.
- **Failure message** — rendered directly from `_no_revisit_route_failure`; both
  the `--unique` and `--loop-interval` forms name the right option and hop count.

---

## Variances and notes

- **Filter moved inside the helpers** (audit finding), not the caller — a bigger
  change than the first plan, and the correct one.
- **Off-by-one flagged then retracted** — the implementation matches the literal
  spec; see "The contract reading".
- **`--via` / `--loop` keep their own failures** — a deliberate narrowing of the
  plan's "raise `NoUniqueRoute` at every collapse"; the waypoint-missed /
  loop-not-closed fact is the certain primary cause there.
- **`NoUniqueRoute` is hard to provoke on live data** — a tight jump range makes
  the route *walk* into fresh territory rather than corner itself, and all of the
  (up to 50) beam chains would have to dead-end at once. It needs a genuinely
  sparse, isolated dataset; the path is correct by construction and the message
  verified. Left to surface on a real sparse-data ticket.
- **Quality risk recorded, not closed** — `--via` + `--unique` is the case most
  prone to a *spurious* no-route: the lane fairness reserves by waypoint
  direction, not by visited history, so a unique-feasible visit order can be
  score-trimmed in favour of a higher-profit order that later dead-ends. Tail
  risk; the homework is to widen the lane reservation to cover history-variants
  if a real case shows it biting.

---

## Living docs

- `BASELINE.md`: `--unique` / `--loop-interval` moved from "still owed" to
  "what works now"; the revisit-constraint behaviour recorded under
  cross-cutting behaviour.
- `SPEC_STATUS.md`: the two options and the "unique and loop interval" section
  marked done; failure behaviour updated; removed from "parse but do not act".
- `INDEX.md`: this slice entry.
