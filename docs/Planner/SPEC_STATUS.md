# trade run — Black-Box Spec Implementation Status

`trade_run_black_box_spec.md` is the behavioural contract — an AI extraction
from the legacy path, then audited long-form by the dev team. It is the Bible.
This file is its **coverage map**: read it to see what is built, what was
deliberately varied, and what is still to do, and then open only the spec
section you actually need — instead of re-reading 33 KB each session.

Where this map and the spec disagree, the disagreement is **deliberate** (see
"Deliberate variations") — do not "fix" a varied behaviour back to the spec
without raising it.

Status as verified against `validation.py`, `run_request.py`, and the parser in
`commands/run_cmd.py`.

## Legend

```text
[done]    built, to spec
[varied]  built, deliberately different from spec — see the note
[todo]    in the spec, not yet built (gated in validation, or parses but inert)
```

---

## Option contract

### Financial and ship options

| Option | Status | Note |
|--------|--------|------|
| `--capacity` | `[done]` | Required. Rejected if missing or ≤ 0. |
| `--credits` | `[done]` | Required. Negative rejected. |
| `--insurance` | `[done]` | Reserved credits; must leave a trading budget. |
| `--limit` | `[done]` | Per-commodity unit cap; 0 = unlimited; must be ≤ `--capacity`. |
| `--margin` | `[done]` | Fraction (0–1) of accumulated profit *not* trusted as later buying power. |

### Route shape options

| Option | Status | Note |
|--------|--------|------|
| `--from` | `[done]` | Station or system; may be omitted (open origin). |
| `--to` | `[done]` | Station or system; may be omitted (open destination). |
| `--hops` | `[done]` | 1–25; an excessive count is rejected. |
| `--towards` | `[done]` | Steers toward a target system; progress-first ranking, arrives and stops early. Requires `--from`; rejects `--to`. See Variations. |
| `--loop` | `[varied]` | Round trip back to the start; requires `--from` (station or system), `--hops ≥ 2`. The galaxy-wide loop (`--from` omitted) is not supported — a recorded decision. See Variations. |
| `--via` | `[varied]` | Routes through one or more waypoints (systems or stations), any order, every route shape (fixed-terminal, single-anchor open, loop). At most six; requires an anchor (`--from`/`--to`) — a chosen variation. No partial-via routes. See Variations. |
| `--avoid` | `[done]` | Excludes a commodity, system, or station; repeated / comma-separated, fuzzy-matched like the endpoints. Avoided commodity never bought; avoided station never a route station; avoided system also barred from jump-path transit (the permit case). Explicit `--from` exempt as origin. |
| `--direct` | `[varied]` | Single direct hop between a fixed `--from` and `--to`; no jump/distance checks. Requires both endpoints; single-hop only; open-destination mode dropped. See Variations. |
| `--shorten` | `[todo]` | Gated. |
| `--unique` | `[todo]` | Gated. |
| `--loop-interval` | `[todo]` | Gated. |

### Reachability options

| Option | Status | Note |
|--------|--------|------|
| `--ly-per` | `[done]` | Required, unless `--direct` — then moot and ignored. |
| `--jumps-per` | `[done]` | Any non-negative int. Keyed default: omitted → 2 if `--ly-per ≤ 12.5`, else 1. |
| `--start-jumps` | `[done]` | Empty positioning jumps before the first trade hop; expands eligible origins from the `--from` anchor's system. Requires `--from`. |
| `--end-jumps` | `[done]` | Mirror after the last hop; expands eligible destinations from the `--to` anchor's system. Requires `--to`. |
| `--empty-ly` | `[done]` | Unladen fan-out range for `--start-jumps`/`--end-jumps`; falls back to `--ly-per` when absent. Inert on its own (deliberate no-op). |
| `--show-jumps` | `[todo]` | Parses but inert — the jump path shows in expanded output regardless of the flag. |

### Station filters

| Option | Status | Note |
|--------|--------|------|
| `--planetary` | `[done]` | Y/N/? accepted-state set. |
| `--no-planet` | `[done]` | Rejected if combined with `--planetary`. |
| `--fleet-carrier` | `[done]` | Y/N/? set. |
| `--settlement` | `[done]` | Y/N/? set. |
| `--black-market` | `[done]` | Y/N/? set. |
| `--ls-max` | `[done]` | Max distance from arrival star. |
| `--age` | `[done]` | Excludes rows older than N days. No default — absent `--age` uses every row (deliberate; see BASELINE). The cutoff is sampled once at the run's first fetch, so one run shares one "now"; the multi-hop shapes also derive a fresh-station set from it up front, so stale stations are never walked. |
| `--pad-size` | `[varied]` | Ship-fit threshold, not the legacy model — see Variations. |

### Commodity and trade filters

| Option | Status | Note |
|--------|--------|------|
| `--gain-per-ton` | `[done]` | Min profit/unit; default 1. |
| `--max-gain-per-ton` | `[done]` | Max profit/unit; default 0 = off. A *default* cap is a deferred idea (see BASELINE), the option itself works. |
| `--supply` | `[done]` | Min source supply. |
| `--demand` | `[done]` | Min destination demand. |

### Search and display controls

| Option | Status | Note |
|--------|--------|------|
| `--routes` | `[todo]` | Only `--routes 1` supported; > 1 rejected. |
| `--max-routes` | `[todo]` | Gated (non-zero). |
| `--prune-score` | `[todo]` | Gated (non-zero). |
| `--prune-hops` | `[todo]` | Gated (non-default; default 3). |
| `--checklist` | `[todo]` | Gated. |
| `--x52-pro` | `[todo]` | Gated (also requires `--checklist`). |
| `--summary` | `[todo]` | Parses but inert. |
| `--progress` | `[todo]` | Parses but inert. |

### Beyond the spec's option contract

| Option | Status | Note |
|--------|--------|------|
| `--max-price` | `[varied]` | **Added** — not in the spec. Absolute price cap (default 1,500,000 cr/t). See Variations. |
| `--ls-penalty` | `[done]` | The protected curve (spec §ls-penalty), implemented in `score.py`. |

Implementation note: option status records the shared behavioural meaning. Route
engines may apply that meaning differently for performance, but must not own
separate semantics for the same option.

---

## Behavioural sections

| Spec section | Status | Note |
|--------------|--------|------|
| Early validation | `[done]` | One validator — the planner's `validate_run_request` on the `RunRequest`; the legacy command-layer checker was removed. Parser-level mutual exclusions (`--to`/`--towards`/`--loop`, `--direct`/`--hops`) stay at the parser. Some early-failure pairs (e.g. `--unique` with `--loop`) are moot while `--unique` is gated. |
| Name and place resolution | `[done]` | Syntax picks the namespace: a bare name is a system, `/name` a station, `system/station` a scoped station — no cross-namespace fall-through; misses and candidate lists name a System or Station (never "place"). Partial matching (exact → prefix → substring, gathered against a normalised `lookup_name` superset) and duplicate-system `@N` coordinate disambiguation are active for `trade run`, through the shared `TradeORM` lookup. |
| Origin selection | `[done]` | Station / system / omitted; `--start-jumps` expands origins from the anchor's empty-jump neighbourhood. |
| Destination selection | `[done]` | Station / system / omitted; `--end-jumps` expands destinations from the anchor's empty-jump neighbourhood. |
| Avoid semantics | `[done]` | Commodity / system / station exclusion; avoided systems barred from transit; explicit `--from` origin exempt. Namespace by syntax (bare = system or commodity, slash = place), resolved precision-first with a place winning a same-tier tie. |
| Via semantics | `[varied]` | Built: every named waypoint visited (any order), every route shape, no partial-via route. Requires an anchor — a chosen variation. See Variations. |
| Station eligibility | `[done]` | All implemented filters applied SQL-side. |
| Market-data eligibility | `[varied]` | To spec, plus `_MIN_MEANINGFUL_DEMAND = 2` — see Variations. |
| Trade candidate generation | `[done]` | |
| Cargo fitting | `[done]` | Capacity, credits, insurance, margin, limit, supply, demand-as-cap, gain-per-ton. Avoided-commodity input is moot (`--avoid` gated). |
| Credits, insurance, margin | `[done]` | |
| Reachability | `[done]` | `--ly-per`, `--jumps-per`, same-system supercruise. `--direct` bypasses reachability for a fixed pair (see Variations). |
| Route generation | `[done]` | |
| Route ranking | `[done]` | Practical value with ls-penalty; `--to` honoured; `--towards` ranks progress-first (closest, then fewer hops, profit only breaking ties). `--loop` closes the route on its own start station. `--via` carries the full waypoint mask — a route missing a waypoint never outranks one satisfying it, and satisfying routes rank by profit. The remaining shaping options (`--shorten`/`--unique`) are gated. |
| ls-penalty | `[done]` | Protected curve. |
| towards mode | `[done]` | Progress-first per-hop ranking; arrives and stops early; mutually exclusive with `--to`. See Variations. |
| loop routes | `[varied]` | Anchored loop built: closes on its own start station, requires `--from`, `--hops ≥ 2`, per-chain terminal rule on the fixed-terminal engine. The galaxy-wide loop (`--from` omitted) is not supported — a recorded decision. See Variations. |
| shorten routes | `[todo]` | |
| unique and loop interval | `[todo]` | |
| Pruning controls | `[todo]` | |
| Output contract | `[done]` | Default route output plus verbose per-hop / cumulative / jump-path detail. |
| Checklist output | `[todo]` | |
| Progress output | `[todo]` | |
| Failure behaviour | `[varied]` | Distinct families implemented; affordability is folded into "no profitable trades" — see Variations. The loop, towards, and via no-route classes are implemented (a route that cannot close back to its start, cannot make forward progress, or cannot visit every waypoint and reach the endpoint, fails in the no-route family); the unique no-route class is moot (gated). Matrix endpoint shapes classify missing-data failures in aggregate on the no-route path, not per pair; in a rare cross-pair corner (one pair's source lacks data, a different pair's destination lacks data) the reported family is "no profitable trades" where per-pair probing named a side. |
| Data requirements | `[done]` | Database is the source of truth; only the needed scope is materialised. |
| Performance contract | `[done]` | Early narrowing, filters pushed into SQL, materially faster than legacy. The real-budget shapes (fixed-terminal, one-hop open) additionally pre-filter cargo — a pair that cannot beat the kept set skips the branch-and-bound solve (exact; routes unchanged), solving best-first so the threshold rises fast. The open-ended candidate fetches are narrowed in SQL by the fixed endpoint's per-item price bounds, stream station groups best-ceiling-first, and stop reading at the first station that provably cannot beat the kept set — the tail is never read out of the database (exact; routes unchanged; open multi-hop −45–61% wall). |

---

## Deliberate variations from the spec

Each of these is a chosen difference, not a gap. Do not revert without raising it.

1. **`--pad-size` is a ship-fit threshold.** Spec §Station filters says "require
   compatible landing pad size". We took it to mean "the ship needs at least
   this pad": `L` = large-max only; `M` = medium/large + unknown-pad; `S` =
   every station. `?` / multi-letter values are rejected. The legacy
   "exclude large starports to find trades smaller ships can reach" use case is
   deliberately dropped — simplicity judged to outweigh it.

2. **`--max-price` added.** The spec's option contract has no absolute
   price cap. Owner-set fleet-carrier prices produce fictional multi-million
   cr/t rows that would win and distort the search, so we added one (default
   1,500,000 cr/t, sized so no legitimate non-carrier row is lost; `0`
   disables). A different axis from `--max-gain-per-ton`, which caps per-ton
   *profit*.

3. **`_MIN_MEANINGFUL_DEMAND = 2`.** Spec §Market-data eligibility accepts any
   positive demand. A stocked commodity reports its dormant buy side as 0 or 1,
   so a `demand_units = 1` destination is an unfillable sale, not a real trade —
   we decline it; legacy accepts it.

4. **No separate "cannot afford cargo" failure.** Spec §Failure behaviour lists
   distinct no-data / no-route classes; we fold "profitable trades exist but the
   commander can't afford any" into "No profitable trade was found". Proving the
   distinction is expensive and the case rarely matters in normal play.

5. **`--jumps-per` keyed default.** The spec mandates no default. Omitted
   `--jumps-per` defaults to 2 when `--ly-per ≤ 12.5` (short-range ships reach
   too little on one jump), else 1.

6. **`--towards` excludes `--to`.** Spec §Early validation lists `--towards`
   without `--from` as a failure but is silent on `--towards` with `--to`. The
   two contradict — `--to` fixes the destination, `--towards` only steers toward
   one — so we reject the combination with a "specify one or the other" error
   rather than guess intent. The progress ranking itself (closest first, then
   fewer hops, profit only a tie-breaker) reads the spec's "MAY optimise profit
   among forward-progress candidates" as the optional permission it is, not a
   licence to override the "MUST move closer" requirement.

7. **`--direct` is a fixed-pair single hop.** The spec describes `--direct` as a
   general reachability bypass and is silent on endpoints; its plural "hops"
   (Reachability section) leans multi-hop. We scope it to the bounded, useful
   case: the best single trade between a fixed `--from` and `--to`, jump route
   left to the commander. Three chosen differences: (a) **single hop only** —
   the legacy path forced `hops = 1` and the parser already makes `--direct`
   mutually exclusive with `--hops`; (b) **both endpoints required** — the spec
   never demands it, but an open end under `--direct` has no spatial bound, so
   we reject it; (c) **open-destination "to anywhere" mode dropped** — the
   legacy did it by scanning the whole preloaded galaxy in Python, the
   preload-first pattern this rewrite removes, so it is deferred, not rebuilt.
   `--ly-per`/`--jumps-per` are tolerated but ignored; `--towards` and empty-jump
   positioning are rejected as contradictory.

8. **`--loop` requires `--from`.** Spec §loop routes describes a round trip back
   to the start and does not require a named origin; legacy supported the
   galaxy-wide loop (`--from` omitted) by brute force over the preloaded galaxy.
   The anchored loop (`--from` named) is built and behaves to spec: it closes on
   its own start station via a per-chain terminal rule on the fixed-terminal
   engine. The galaxy-wide loop is **not supported** — a recorded decision, not a
   gap. Seeding it faithfully within the fixed beam width (which stays 50) was not
   achievable at acceptable cost, and widening the frontier to compensate is
   explicitly off the table. `--loop` without `--from` is rejected with a clear
   message. See `docs/Planner/unanchored_loop_investigation.md` for the evidence
   and the decision; reopening it would be a future slice.

9. **`--via` requires an anchor.** Spec §Via semantics sets no anchoring
   requirement. We require at least one of `--from` / `--to`: a
   fully-unanchored via is unbounded, and with both ends free the
   cheapest way to "include" a place is to start or finish there. The via
   itself is otherwise to spec — every named waypoint visited in any
   order, no partial-via route — with a six-waypoint cap that keeps the
   satisfaction mask and the per-mask search lanes bounded.

---

## Spec "Open decisions for supervisor" — how resolved

The spec closes with five decisions left to the supervisor. Current resolution:

1. **Demand: eligibility threshold or hard cargo cap?** → **Hard quantity cap.**
   Destination demand both gates eligibility and caps loaded quantity, with a
   further `floor(demand * 0.25)` sub-cap on Metals/Minerals to avoid the
   in-game bulk-sale penalty.
2. **Profit-comparison tolerance under market drift?** → Not formalised as a
   number. Spot-checked against `--old` while it existed; `--old` is now retired
   (Slice 14), so comparison is against route validity and the benchmark
   criteria, allowing ordinary drift.
3. **Per-benchmark wall-clock gate?** → No fixed figure; the standard is
   "materially faster", measured per change. The galaxy-wide shapes are
   confirmation-gated rather than time-bounded.
4. **Machine-readable output mode?** → Not implemented. The plain-text output
   was instead expanded (Slice 9) to expose auditable per-hop / cumulative
   figures. A structured mode remains an open idea.
5. **Safety limit on broad galaxy-wide searches?** → **Interactive confirmation
   prompt**, not a hard limit. A non-affirmative answer or non-TTY invocation
   exits cleanly without planning.

---

## Options that parse but do not act yet

Accepted by the parser — so they do **not** error — but nothing honours them yet.
Listed so a worker does not assume they work just because they run clean.

Three are output-display options carried over from the legacy path. Whether the
new planner reuses any of them is an open question for a later output / look-and-
feel pass; none is on the radar now, while output styling is not a priority.

```text
--show-jumps    output display: the jump path already shows in expanded output,
                so the flag toggles nothing today
--summary       output display: a legacy summary mode, not honoured yet
--progress      output display: a legacy progress mode, not honoured yet
```
