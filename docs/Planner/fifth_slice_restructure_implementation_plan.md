# Unanchored Candidate Query — Restructure Implementation Plan

## Purpose

Address three deferred follow-ups against the unanchored search's
candidate query: the per-system reduction discards station pairs whose
strength is combined multi-commodity cargo; the distance-penalty is
applied per-pair *after* the bounded SQL slice, so a near-star pair whose
practical score would have won can be clipped before scoring sees it;
and the SQL ranking does not fold credits-affordability into the
row-wise cap, so at credit-thin balances the practical winner can be
clipped for the same reason. All three surfaced in the source-level
audit recorded in `fifth_slice_completion_report.md`. They were deferred
from that audit's localised remediations because the fix is
architectural, not a one-liner; this plan documents the design pass, the
probes that run before committing to a shape, and the validation route
once a shape is chosen.

## Origin

The unanchored search's `--old` comparison stays unchanged; this is a
remediation against the new planner. Specifically Findings 2 and 3 from
the audit, plus the affordability follow-up added as a third deferred
item in commit `44ef7264` — see the Deferred section of
`fifth_slice_completion_report.md` for the canonical statements.

## Why one piece of work

All three follow-ups are evidence that the bounded SQL slice does not
match the shape of the scorer that runs over it. The slice is reduced
per-(commodity, system) by unit price, then ranked by
capacity/supply/demand/limit-capped total profit. The scorer is
per-station-pair, with a distance-based penalty applied to destination
ls, against a cargo composition optimised across all commodities the
pair can jointly trade, with credits-affordability enforced when each
pair is concretely evaluated.

Three mismatches result. A station that is per-system best on no single
commodity but strong across many is invisible to the slice — only the
per-(commodity, system) cheapest seller and dearest buyer survive the
reduction. A near-star pair scoring well under practical score can be
clipped because the slice ranks by raw realisable profit, with the
distance-penalty curve only applied after. And the row-wise cap in the
SQL rank omits `floor(available_credits / supply_price)`, so at
credit-thin balances the slice can clip a pair whose affordable cargo
would have scored highest. Fixing them in separate passes means
re-shaping the slice three times; the design constraints (portability,
no anchored regression, scorer-pluggability) are identical, so one pass
is the right shape.

## Goal

Post-restructure, the bounded SQL slice should materially reduce the
known false-negative modes — per-system extrema discard, distance-penalty
post-pruning, and credits-affordability not in the rank — and, under
probe coverage, retain the practical-score winner with high confidence at
acceptable cost relative to today's ~83s SQLite baseline. Unless the
final design stops using lossy K-ranking entirely, this is risk
reduction, not proof of global correctness.

## Constraints

- **Dialect portable.** SQLite is the primary user database; MariaDB must
  work. No SQLite-specific features in the implementation. Probes run
  against SQLite alone because they measure query shape and behaviour,
  not the implementation; MariaDB confirmation comes at the end of
  validation.
- **Quarantine intact.** No reading of `tradecalc.py` or `tradedb.py`.
- **Anchored paths untouched.** The fixed, expanded, and open-ended
  one-hop shapes (`_plan_fixed_endpoints`, `_best_open_ended_plan`) are
  not modified. The restructure is internal to `_plan_unanchored` and
  the helpers it calls.
- **No regression at zero distance-penalty.** The common case (penalty
  off) must not become substantially slower than today.
- **Scorer-pluggable.** The final distance-penalty curve is still in
  discussion, but is expected to be monotonically non-increasing with
  destination arrival distance: near stations multiply score by 1 (or
  near-1), and increasingly distant stations trend downward toward 0.
  SQL must gather a sufficiently rich candidate set so the Python
  scorer can make the final decision after the slice is materialised;
  the slice must not assume the final curve can be safely approximated
  inside SQL. Validation runs against whichever Python distance-penalty
  scorer is current at the time of implementation.

## Design space

For per-system reduction discard (Finding 2):

- **α** — widen the reduction from `rank_in_system == 1` to `<= K`, K
  small (3–5). Cheap, localised. Partial: a station that is per-system
  6th in everything still doesn't surface.
- **δ** — after the bounded slice returns, derive the surviving
  (source_station, dest_station) pairs and re-fetch the *full*
  per-commodity supply/demand list per surviving pair. Cargo optimiser
  sees everything for any pair that made it through Stage 1. Doesn't
  help pairs that never made it through Stage 1.

For distance-penalty post-pruning (Finding 3):

- **D-2** — widen the bounded slice from 50 rows to a larger N
  (probe-determined) when a non-zero distance-penalty is in effect.
  Simple; the per-pair cargo optimiser is the slow Python step, not the
  SQL. **Preferred route while the distance-penalty curve is still in
  discussion**, because it preserves Python's authority over the final
  scoring policy regardless of curve shape.
- **D-3** — two-pass SQL: rank by raw realisable, take top-N; join
  `Station.ls_from_star` for dest, apply a monotonic linear
  distance-penalty proxy in SQL on that narrow set, take top 50. The
  Python scorer continues to run on the resulting set. **Provisional
  only.** A SQL proxy bakes a curve into the slice, which is the
  architectural opposite of scorer-pluggability, and is at best an
  approximation of the Python scorer. Off the table until the
  distance-penalty curve is finalised, and only revisited if D-2's
  wider slice costs too much in Python evaluation time.

For affordability not in the SQL ranking key:

- **ε** — extend the row-wise cap in the SQL CASE expression to include
  `floor(available_credits / supply_price)` as an additional minimum
  alongside supply, demand, capacity and `--limit-per-item`. Trivially
  portable; the cost is one more `CASE WHEN` branch in the rank. Only
  meaningful when credits are the binding constraint; P5 sizes that.

Out of consideration:

- Per-station-pair as the primary query unit. Stations² within reach is
  too many — millions to tens of millions of pairs at typical
  `--ly-per`. The deliverable is "best one-hop pair", which doesn't
  require enumerating all pairs.
- Encoding the full distance-penalty curve in SQL. Portability and
  ugliness aside, the curve is still in flux; baking it into the slice
  forfeits scorer-pluggability.

## Recommended starting hypothesis

Subject to probe results: **α + δ** for Finding 2 (widen K to 5 plus
per-pair full re-fetch), **D-2** for Finding 3 (widen the slice when a
non-zero distance-penalty is in effect; Python keeps full authority over
final scoring), and **ε** for the affordability follow-up (row-wise
credits cap folded into the SQL rank). Smallest blast radius, leans on
the existing `optimise_cargo` and the current Python scorer, easiest to
roll back. D-3 stays off the table while the distance-penalty curve is
in discussion.

## Probes

All five run before any production code change. Standalone files at the
repo root, untracked, throwaway. SQLite against the live dataset on the
Crucial T700.

A *request profile* is a combination of capacity, available credits,
`--ly-per`, `--jumps-per`, pad-size threshold, station filters,
`--limit-per-item`, and the distance-penalty parameter (currently
`--ls-penalty`). The unanchored search picks both endpoints itself, so
the probes vary *profile*, not origin. A probe may pin internal scope
(for example, a fixed pseudo-random reach-map sample) to control cost;
that is a probe-local approximation and is not treated as proving the
unanchored global case.

- **P1 — Practical-score winner agreement at varied distance-penalty.**
  Take a handful of representative request profiles. Run the candidate
  query at the current top-50 limit and at a wider top-N limit (300,
  plus larger if needed). For each slice, compute the current Python
  distance-penalty scorer × `optimise_cargo` per pair at the
  distance-penalty parameter set to typical low, medium, and high
  values. Question: does the top-50 winner equal the wider-slice winner?
  Record per-profile, per-penalty agreement and the practical-score gap
  when they disagree.

- **P2 — Multi-commodity packing frequency.** Instrument `optimise_cargo`
  to record how many distinct commodities are in the winning pair's
  cargo. Run over the same representative request profiles, varying
  capacity in particular (small/medium/large) since capacity drives
  multi-commodity behaviour. Question: what fraction of wins are
  multi-commodity? If small, Finding 2 is a small bite in practice; if
  large, δ is essential.

- **P3 — Cost of widening K in the per-system reduction.** Vary
  `rank_in_system <= K` for K ∈ {1, 3, 5, 10}. For each K record:
  pre-limit reachable match cardinality where practical, limited
  result cardinality, and total time per query. Recording the
  post-limit count alone would mostly measure the slice clamp, not
  the join-space growth that K actually drives. Question: does K = 5
  cost noticeably more than K = 1, and does K = 10 cost a lot more
  than K = 5?

- **P4 — Pair-set coverage under K = 1 vs K = 5.** For each request
  profile, compute the surviving (source_station, dest_station) pair
  set under K = 1 and K = 5. For each set, fetch the full per-commodity
  supply/demand rows per pair directly in the probe (a probe-local
  implementation of δ, not production code yet) and run the current
  Python scorer × `optimise_cargo`. Question: does the K = 5 winner
  equal the K = 1 winner? If they diverge, by how much under practical
  score?

- **P5 — Affordability-sensitive ranking.** Run representative request
  profiles at varied credit levels, including deliberately credit-thin
  balances where `available_credits / supply_price` is the binding
  constraint for some candidate pairs. Compare the current
  capacity/supply/demand/limit-capped ranking against a ranking that
  *also* caps row units by `floor(available_credits / supply_price)`.
  Question: can the current bounded slice clip the practical winner
  when credits are the binding constraint, and how often is that the
  case across representative Cmdr balances?

Probe output goes to a results file at repo root, untracked. Results
are summarised back into this plan once they're in, before any
production code change.

## Decision points after probes

- **K**: do we widen the per-system reduction at all, and if so to what
  value?
- **Slice-limit growth**: D-2 chosen, the slice grows to what N when
  the distance-penalty parameter is non-zero? D-3 stays off the table
  until the distance-penalty curve is finalised.
- **δ scope**: full re-fetch of all commodities per surviving pair, or
  limited to commodities present in the slice plus their per-pair
  neighbours?
- **Penalty-dependent slice limit vs always-wide slice**: is the cost
  of an always-wider slice negligible at zero penalty, in which case
  the penalty-dependent branch is unnecessary complexity?
- **Credits cap (ε)**: does folding `floor(available_credits /
  supply_price)` into the row-wise cap meaningfully change the bounded
  slice at credit-thin balances? If P5 finds the answer is "rarely",
  defer the change; if "often enough at low balances", land it
  alongside the rest.

## Implementation outline (post-probes, hypothesis shape)

1. `_reduce_supply_by_system` / `_reduce_demand_by_system` — change
   `rank_in_system == 1` to `rank_in_system <= K`, K from a
   module-level constant.
2. `_match_reachable_trades` — extend the row-wise cap CASE expression
   to include `floor(available_credits / supply_price)` as a third
   minimum alongside `capped_supply` and `capped_demand`. Portable
   integer division expressed with nested CASE.
3. `fetch_unanchored_trade_candidates` — bounded slice limit becomes a
   function of the request's distance-penalty parameter (rises from 50
   to N when penalty is non-zero), or unconditionally wider if the
   always-wide decision wins.
4. `data_gateway` — new helper `fetch_pair_market_details(session,
   pairs)` returning the full per-(commodity, source_station,
   dest_station) row set for the surviving pair list. SQL stays
   portable: a temp table carries the pair list and joins to
   `StationItem` on both sides, mirroring the reachability map pattern.
5. `_plan_unanchored` — after `_group_pairs`, replace `pair_candidates`
   with the re-fetched detail rows before calling `optimise_cargo`. The
   distance-penalty scorer remains called from Python on the resulting
   evaluated pair; no scorer logic moves into SQL.
6. Anchored entry points unchanged.

## Validation

- Compare top-pair selection against the pre-change baseline
  (`44ef7264`) across the request profiles used in probes P1–P5.
  Disagreements must score higher under the *current* Python
  distance-penalty scorer in the new shape — that is the entire point.
- Spot-check against `--old` for sanity, accepting `--old`'s pick may
  differ; the comparison is route validity and practical score, not
  route identity.
- Performance: zero-penalty invocations must not be substantially
  slower than today. Non-zero-penalty invocations may legitimately be
  slower for a more correct answer.
- MariaDB confirmation: one end-to-end run on the Linux VM against the
  chosen shape before sign-off.
- Validation uses whichever Python distance-penalty scorer is current
  at the time of implementation. If the scorer changes before this
  work lands, the probes do not need to be re-run unless the change
  alters ranking direction — it is the *ranking shape* the slice has
  to contain, not the specific numeric output.

## Out of scope

- Multi-hop routing (`--hops > 1`).
- Multi-jump per hop (`--jumps-per >= 2`).
- Finding 6 (`input()` / `EOFError` after `isatty()` returns true) —
  left as-is.
- Choice of the final distance-penalty curve — separate piece of work;
  this plan accommodates any Python distance-penalty scorer that is
  monotonically non-increasing with destination arrival distance.

## Risk and rollback

Rollback target: commit `44ef7264`. All edits are localised to
unanchored helpers and `_plan_unanchored`'s pair evaluation; nothing
on anchored, fixed-endpoint, or open-ended paths. If probe results
invalidate the hypothesis, this plan is updated with a revised shape
before any production code lands.

## Probe results and decision

P1 through P5 ran against SQLite on the live dataset with no `--age`
set. A supplementary P6 re-ran the same axes under `--age` values of
1, 2, and 7 days — the range Cmdrs actually use when `--age` is set,
which is the dominant usage pattern. Question for all six: do α, δ,
ε, or a wider slice limit produce a higher-scoring practical winner
than the current production query shape, under the current Python
scorer?

### Summary of probe results

| Probe | Question | Result |
|---|---|---|
| P1 | Top-50 vs wider top-N (300, 1000) at varied penalty | 0 disagreements across 5 profiles × 3 limits × 4 penalties |
| P2 | Multi-commodity packing frequency in current winners | 0/32 winners pack more than one commodity |
| P3 | Cost of widening K from 1 to 10 | Production-equivalent time flat; multipliers 0.98–1.01 |
| P4 | α / δ / α+δ winner change at no-age | 0/10 uplift on every axis |
| P5 | ε (credits-cap in SQL rank) winner change | 0/18 uplift; 5/9 profiles show real slice reordering with no winner effect |
| P6 | All four axes under `--age` 1/2/7 | 0/18 uplift on every axis × every penalty |

Combined across P4 and P6, **144 axis-uplift checks returned zero
higher-scoring winners** surfaced by any candidate-query change.

The mechanisms each axis was designed to address are real and the
probes demonstrate them on the data:

- P3 confirms the per-system reduction's K width does grow the join
  space (pre-limit cardinality rises ~1.8× from K=1 to K=10) and
  P4/P6's K=5 slices do admit new pairs that K=1 misses. The new
  pairs simply do not contain a higher-scoring winner under the
  current scorer and data.
- P5 confirms ε's credits-cap rank reorders the slice in 5/9 credit-
  thin profiles, dropping some pairs and admitting others. The
  reordering never elevates a higher-scoring winner.
- P2 confirms every production winner is single-commodity. Multi-
  commodity packing — δ's headline benefit — is never the deciding
  factor on current data.

The mechanism behind all five negative results is consistent: a
small handful of extreme single-commodity margins dominate the
candidate set. The walk's `capacity × bound ≤ best_total_profit`
cutoff terminates after 3–26 commodities, and no widening axis
finds a pair whose practical-score winner beats those leaders.

### Decision

The candidate-query restructure is **not implemented**. Findings 2
(per-system extrema discarding multi-commodity station pairs),
Finding 3 (`--ls-penalty` applied after the bounded SQL slice), and
the credits-affordability follow-up are **accepted as mechanically
real but monitored, not actioned** — the bounded SQL slice as it
stands retains the practical-score winner across every tested data
shape, profile, and penalty under the current scorer.

This is not "the audit findings were wrong." The mechanisms hold.
It is "current data shape and current scorer do not make them
materially affect winner selection in the tested envelope, and no
restructure axis tested produces a different recommendation."

### Re-evaluation triggers

The decision is conditional on the tested envelope. Re-run the
probes (or a refreshed equivalent built from this plan) if any of:

- the distance-penalty scorer materially changes
- default `--age` behaviour or commonly-used `--age` values change
- stale or fleet-carrier market handling changes (a periodic
  cleanup default, an `--age`-aware import path, etc.)
- live data shape changes enough that the extreme single-commodity
  margins stop dominating the candidate set
- `trade run` users report unanchored winner disagreement against
  `--old`, or surprising recommendations under unanchored search
- a future audit identifies a fourth mechanism not covered by α,
  δ, ε, or wider-N

### Carrier dominance — separate concern, not restructure evidence

Every P6 production winner involved a fleet carrier on at least one
side of the trade, across all `--age` values tested:

- 88.9% had a carrier destination
- 66.7% had a carrier source
- 55.6% were carrier-to-carrier
- 0% were non-carrier-to-non-carrier

This is a property of the **data**, not a planner bias and not
evidence that the candidate query needs restructuring. Carrier
markets carry the long-tail of extreme single-commodity margins
because carrier prices are owner-set rather than game-driven; the
unanchored search correctly reports what the data contains.

Carrier-backed routes are valid market observations and are not to
be treated as invalid. The project already gives Cmdrs the
`--fleet-carrier` Y/N/? state filter and unanchored search includes
them by default.

The user-side concern surfaced by P6 is **execution risk**, not
planner correctness. Carrier stock and demand are player-controlled
and can change between an EDDN snapshot and a Cmdr's arrival, and
the API snapshot lag between observation and flight is unavoidable.
P6 captured concrete examples: mid-ship and large-ship one-jump at
`--age 1` returned `Lyncis Sector QT-R b4-1/K4G-N0Z →
HIP 17213/W4T-L9T` on Titan Drive Component with `supply_obs=6` and
`demand_obs=10` at ~21h data age — a real margin but very thin
execution window. The `--age`, `--supply`, `--demand`, and
`--fleet-carrier` levers exist for Cmdrs to control this; the
remediation, if execution risk becomes a recurring complaint, is a
Cmdr-facing filter or a docs note, not a candidate-query change.

### Probe artefacts

The six probes were standalone, throwaway, untracked Python scripts
at the repository root (`probe_p1.py` through `probe_p6_age.py`),
with companion result files (`probe_p1_results.txt` through
`probe_p6_results.txt`). They are not part of the production tree;
the record of what was measured is this section. If a future probe
run is needed, the scripts can be rebuilt from this plan.

### Status

Restructure investigation closed. Slice 5 stands as delivered. No
production code change.
