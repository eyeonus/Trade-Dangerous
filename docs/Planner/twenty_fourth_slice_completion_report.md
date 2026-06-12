# Slice 24 — Completion Report

*Qualify once: run-scoped market qualification for the multi-hop engines.*
*Completed 2026-06-12. Plan: `twenty_fourth_slice_implementation_plan.md`*
*(P1–P3 results are recorded in place there as they landed).*

---

## What the slice set out to do

Split the open-ended candidate fetch's cost in two: the run-constant
qualification (does this row pass the thresholds, the age window, the
price cap?) and the anchor-specific pairing maths. Answer the first
once per station into run-scoped temp tables instead of once per
anchor that can reach it, and — settled by the planning-stage data
findings — turn `--age` into a station-level cut so stale stations are
never walked at all.

## What was built

**Part A — probes (results in the plan file):**

- **P1** confirmed the open-ended fetch is well-planned: station-first
  drive, attribute filters applied before any market row is touched.
  Nothing to fix before caching.
- **P2** pinned the bubble and established the filter cost law: a
  filter buys fetch relief in proportion to the market rows it
  removes, not the stations. `--fc N` is row-trivial in current data
  (carriers ~0.6 rows each); `--planetary N` is the row-mover. The
  `--age` predicate, pre-slice, never shrank the walk — its saving was
  cheap row rejection.
- **P3** replaced its own broken instrument (the subtraction split was
  swamped by Python row materialisation) with COUNT-only timings and a
  direct temp rehearsal. Per-anchor decomposition at open filters:
  ~34% SQL walk + qualification, ~13% pairing EXISTS, ~53% Python
  materialisation of returned rows. Rehearsal: 21–44% per-anchor
  saving; build amortises in 2–3 overlapping anchors. Union sizing on
  the worst shape: ~1.5M qualified rows — comfortably in temp budget.
  Gate verdict: GO.

**Part B — the build (commit `e5947267`):**

- `QualificationCache` in `data_gateway.py`: per-side run-scoped temps
  (`td_run_supply_qual` / `td_run_demand_qual`, PK station_id+item_id
  WITHOUT ROWID), populated lazily and SQL-side end to end — a
  seen-stations temp and a batch temp compute the unseen slice of each
  bubble with one INSERT…SELECT; no id list round-trips through
  Python.
- **Stage 0**: with `--age` set, the fresh-station set is derived once
  (single range scan over the `modified`-led covering index); stale
  stations are never walked. The row-level age predicate is retained,
  so mixed-timestamp stations behave byte-identically.
- **Frozen cutoff**: the `--age` cutoff is sampled once at the run's
  first fetch — one "now" per run instead of a cutoff drifting with
  the wall clock across a long search. Signed off as the (tiny)
  behaviour change it is.
- **Skip marker**: bubbles already fully processed for a side are
  skipped outright on repeat visits (keyed on the reachable-memo key;
  only when no envelope/`--towards` narrowing is in play).
- **ANALYZE discipline**: `analyze_temp_table()` re-runs only when the
  temp has doubled since the last pass — the stats lesson honoured at
  bounded cost.
- The pairing query reads the temp and applies only anchor-specific
  terms (bubble scope, per-hop credit cap, fixed-side bounds EXISTS,
  onward viability). The fixed side and the bounds build read
  StationItem directly — one named place, nothing run-constant to
  hoist. Constant predicates live in shared helpers used by both the
  direct path and the temp build, so they cannot drift.
- Diagnostics: a `Qualification:` line (stations, rows cached, time)
  in the standard output; counters on `ExpansionStats`. Always-on, as
  with the rest of the instrumentation (the pre-release gating flag
  remains a separate task).

## Verification

- **Exactness:** run set 3 — all sixteen runs with a recorded baseline
  (eight open-filter vs run set 1, eight `--fc N` vs run set 2)
  reproduce candidate rows, pairs, profits and routes to the digit.
  The `--age` shape was verified by a same-instant cache-on/cache-off
  comparison: byte-identical.
- **Performance:** fetch down ~8–13% on the open-anchor shapes; the
  fixed-terminal envelope shapes break even (the envelope narrows the
  station list per call, so the skip marker never engages — they are
  now the slowest shapes left). A new `--planetary N` block confirms
  the P2 row law at run scale (−31% rows, −34% fetch on the worst
  shape).
- **The age cut** (run set 4, on the freshly rebuilt zero-mixed
  database): worst shape 124s open → 55.3s at `--age 3` → 38.3s at
  `--age 1` (−55% / −69%). A realistic stacked-filter command
  (`--age 1 --planetary N --fc N --pad-size L`) runs the same shape in
  ~27s (−78%). Aged baselines are anchored to recorded start times;
  comparisons must apply the `--age` delta rule (project CLAUDE.md).

## Variances from the plan

- The temps omit the planned `system_id` column — the pairing path
  scopes by station id and never joins spatially; an unused column is
  dead weight.
- The seen-station tracking is SQL-side (a temp), not the planned
  Python set — same lazy semantics, no id materialisation, in keeping
  with the query-discipline rules.
- The skip marker and the frozen cutoff were added during the build;
  both are recorded above.
- P3's planned subtraction split was discarded as invalid when
  measured; the replacement instruments are described in the plan's
  P3 results.

## Discovered alongside (import-path, not planner)

The planning-stage data findings exposed the mixed-timestamp write
fault. The station snapshot write rule
(`docs/station_snapshot_write_rule.md`) was specified and applied to
three writers: spansh market + ShipVendor (`b2c3b90e`) and the
eddblink listings import (`f72dfcb9`), the latter caught minting 487
mixed stations from perfectly clean server data on the first fresh
rebuild. A clean re-import then produced a zero-mixed database —
94,367 of 94,367 stations uniform — which is the invariant stage 0
rests on, now true by construction. The spec's audit checklist
(eddblink's ShipVendor.csv handling, any straggler import commands)
remains open there.

## Deferred / out, restated

- **Bound-ordered pairing with provable early stop** — deferred
  pending the post-slice residual, and the residual now has a measured
  shape: per-anchor cost is dominated by Python materialising returned
  rows (~53% at open filters), which only returning fewer rows can
  cut. The natural candidate for the next performance slice.
- **Materialised summary tables** — rejected; dead, not parked.
- **Diagnostics gating flag** — before release; separate task.

## Commits

| Commit | What |
|---|---|
| `257dcd69` | P1 results recorded |
| `27e8f545` | P2 results + filter cost law into the baselines |
| `1aa1f2e3` | P3 results + GO decision |
| `e5947267` | Part B: qualify-once temps, stage 0, skip marker, diagnostics |
| `090cd399` | Run set 3 recorded (exactness + open/fc/planetary blocks) |
| `31493ade` | Run set 4 recorded (aged baselines) |
| `b2c3b90e`, `f72dfcb9`, `ef0d00cb`, `a81649aa` | Write-rule fixes and spec (import-path side quest) |

Probe scripts and their artefacts were deleted at close, per the
probe rule.
