# Unanchored Candidate Query — Restructure Implementation Plan

## Purpose

Address two structural findings against the unanchored search's candidate
query: the per-system reduction discards station pairs whose strength is
combined multi-commodity cargo, and `--ls-penalty` is applied per-pair
*after* the bounded SQL slice, so a near-star pair whose practical score
would have won can be clipped off before scoring sees it. Both surfaced in
the source-level audit recorded in `fifth_slice_completion_report.md`. They
were deferred from that audit's localised remediations because the fix is
architectural, not a one-liner; this plan documents the design pass, the
probes that run before committing to a shape, and the validation route once
a shape is chosen.

## Origin

The unanchored search's `--old` comparison stays unchanged; this is a
remediation against the new planner. Specifically Findings 2 and 3 from the
audit — see the Deferred section of `fifth_slice_completion_report.md` for
the canonical statements.

## Why one piece of work

Both findings are evidence that the bounded SQL slice does not match the
shape of the scorer that runs over it. The slice is reduced per-(commodity,
system) by unit price, then ranked by realisable total profit. The scorer
is per-station-pair, multiplied by `ls_penalty_multiplier(dest_ls,
penalty_percent)`, against a cargo composition optimised across all
commodities the pair can jointly trade.

Two mismatches result. A station that is per-system best on no single
commodity but strong across many is invisible to the slice — only the
per-(commodity, system) cheapest seller and dearest buyer survive the
reduction. And a near-star pair scoring well under practical score can be
clipped because the slice ranks by raw realisable profit, with the
ls-penalty curve only applied after. Fixing them in separate passes means
re-shaping the slice twice; the design constraints (portability, no
anchored regression) are identical, so one pass is the right shape.

## Goal

Post-restructure, the bounded SQL slice contains the (source_station,
destination_station) pair that wins under the public scoring contract —
multi-commodity `optimise_cargo` × `ls_penalty_multiplier(dest_ls,
penalty_percent)` — with high confidence and at acceptable cost relative to
today's ~83s SQLite baseline.

## Constraints

- **Dialect portable.** SQLite is the primary user database; MariaDB must
  work. No SQLite-specific features in the implementation. Probes run
  against SQLite alone because they measure query shape and behaviour, not
  the implementation; MariaDB confirmation comes at the end of validation.
- **Quarantine intact.** No reading of `tradecalc.py` or `tradedb.py`.
- **Anchored paths untouched.** The fixed, expanded, and open-ended one-hop
  shapes (`_plan_fixed_endpoints`, `_best_open_ended_plan`) are not
  modified. The restructure is internal to `_plan_unanchored` and the
  helpers it calls.
- **No regression at `--ls-penalty=0`.** The common case must not become
  substantially slower than today.

## Design space

For per-system reduction discard (Finding 2):

- **α** — widen the reduction from `rank_in_system == 1` to `<= K`, K small
  (3–5). Cheap, localised. Partial: a station that is per-system 6th in
  everything still doesn't surface.
- **δ** — after the bounded slice returns, derive the surviving
  (source_station, dest_station) pairs and re-fetch the *full* per-commodity
  supply/demand list per surviving pair. Cargo optimiser sees everything
  for any pair that made it through Stage 1. Doesn't help pairs that never
  made it through Stage 1.

For ls-penalty post-pruning (Finding 3):

- **D-2** — widen the bounded slice from 50 rows to a larger N
  (probe-determined) when `penalty_percent > 0`. Simple; the per-pair cargo
  optimiser is the slow Python step, not the SQL.
- **D-3** — two-pass SQL: rank by raw realisable, take top-N; join
  `Station.ls_from_star` for dest, apply a monotonic linear ls-penalty
  proxy in SQL on that narrow set, take top 50. The full sigmoid
  `ls_penalty_multiplier` continues to run in Python on the resulting set.

Out of consideration:

- Per-station-pair as the primary query unit. Stations² within reach is too
  many — millions to tens of millions of pairs at typical `--ly-per`. The
  deliverable is "best one-hop pair", which doesn't require enumerating all
  pairs.
- Encoding the full sigmoid `ls_penalty_multiplier` in SQL. Boost, drop and
  middle terms involve floating exponentiation and a sigmoid blend;
  portability and ugliness make this not worth the marginal selection
  improvement over a monotonic linear proxy.

## Recommended starting hypothesis

Subject to probe results: **α + δ** for Finding 2 (widen K to 5 plus
per-pair full re-fetch), **D-2** for Finding 3 (widen the slice when
penalty is non-zero). Smallest blast radius, leans on the existing
`optimise_cargo` and `score_with_destination_penalty`, easiest to roll
back. Promote to D-3 only if D-2's wider slice costs too much in Python
evaluation time.

## Probes

All four run before any production code change. Standalone files at the
repo root, untracked, throwaway. SQLite against the live dataset on the
Crucial T700.

- **P1 — Practical-score winner agreement at varied `--ls-penalty`.** Take
  a handful of representative origins. Run the candidate query at the
  current top-50 limit and at a wider top-N limit (300, plus larger if
  needed). For each slice, compute `optimise_cargo` ×
  `ls_penalty_multiplier` per pair at `penalty_percent` = 0, 50, 100.
  Question: does the top-50 winner equal the wider-slice winner? Record
  per-origin, per-penalty agreement and the practical-score gap when they
  disagree.

- **P2 — Multi-commodity packing frequency.** Instrument `optimise_cargo`
  to record how many distinct commodities are in the winning pair's cargo.
  Run over the same representative origins. Question: what fraction of
  wins are multi-commodity? If small, Finding 2 is a small bite in
  practice; if large, δ is essential.

- **P3 — Cost of widening K in the per-system reduction.** Vary
  `rank_in_system <= K` for K ∈ {1, 3, 5, 10}. For each K record: matched
  row cardinality after `_match_reachable_trades`, total time per query.
  Question: does K = 5 cost noticeably more than K = 1, and does K = 10
  cost a lot more than K = 5?

- **P4 — Pair-set coverage under K = 1 vs K = 5.** For each origin, compute
  the surviving (source_station, dest_station) pair set under K = 1 and
  K = 5. For each set, fetch the full per-commodity supply/demand rows per
  pair directly in the probe (a probe-local implementation of δ, not
  production code yet) and run `optimise_cargo` ×
  `ls_penalty_multiplier`. Question: does the K = 5 winner equal the
  K = 1 winner? If they diverge, by how much under practical score?

Probe output goes to a results file at repo root, untracked. Results are
summarised back into this plan once they're in, before any production code
change.

## Decision points after probes

- **K**: do we widen the per-system reduction at all, and if so to what
  value?
- **Slice-limit growth**: D-2 chosen, the slice grows to what N when
  penalty is non-zero? Does D-3 outperform D-2 enough to justify the SQL
  complexity?
- **δ scope**: full re-fetch of all commodities per surviving pair, or
  limited to commodities present in the slice plus their per-pair
  neighbours?
- **Penalty-dependent slice limit vs always-wide slice**: is the cost of an
  always-wider slice negligible at `penalty_percent=0`, in which case the
  penalty-dependent branch is unnecessary complexity?

## Implementation outline (post-probes, hypothesis shape)

1. `_reduce_supply_by_system` / `_reduce_demand_by_system` — change
   `rank_in_system == 1` to `rank_in_system <= K`, K from a module-level
   constant.
2. `fetch_unanchored_trade_candidates` — bounded slice limit becomes a
   function of `request.ls_penalty_percent` (rises from 50 to N when
   penalty is set), or unconditionally wider if the always-wide decision
   wins.
3. `data_gateway` — new helper `fetch_pair_market_details(session, pairs)`
   returning the full per-(commodity, source_station, dest_station) row
   set for the surviving pair list. SQL stays portable: subquery joining
   `StationItem` to both sides of the pair list, with the pair list
   carried as a temp table (the same pattern the reachability map uses).
4. `_plan_unanchored` — after `_group_pairs`, replace `pair_candidates`
   with the re-fetched detail rows before calling `optimise_cargo`.
5. Anchored entry points unchanged.

## Validation

- Compare top-pair selection against the pre-change baseline
  (`44ef7264`) on the representative origins from probes P1–P4.
  Disagreements must score higher under practical score in the new
  shape — that is the entire point.
- Spot-check against `--old` for sanity, accepting `--old`'s pick may
  differ; the comparison is route validity and practical score, not route
  identity.
- Performance: `--ls-penalty=0` invocations must not be substantially
  slower than today. `--ls-penalty>0` invocations may legitimately be
  slower for a more correct answer.
- MariaDB confirmation: one end-to-end run on the Linux VM against the
  chosen shape before sign-off.

## Out of scope

- Multi-hop routing (`--hops > 1`).
- Multi-jump per hop (`--jumps-per >= 2`).
- Finding 6 (`input()` / `EOFError` after `isatty()` returns true) — left
  as-is.

## Risk and rollback

Rollback target: commit `44ef7264`. All edits are localised to unanchored
helpers and `_plan_unanchored`'s pair evaluation; nothing on anchored,
fixed-endpoint, or open-ended paths. If probe results invalidate the
hypothesis, this plan is updated with a revised shape before any
production code lands.
