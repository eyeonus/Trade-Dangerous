# Planner Rewrite Documentation Index

Quick reference guide to the docs/Planner/ directory for agents and developers.

---

## Essential Startup Documents

**Read these first before proposing or implementing anything in this side mission.**

### [trade_run_black_box_spec.md](trade_run_black_box_spec.md)
Clean-room behavioural specification for the route planner. Defines:
- What the command must do (without saying how it does it)
- User-facing option contract (all supported CLI flags)
- Failure categories and error messages
- Station/commodity/route eligibility rules
- Cargo fitting and financial constraints
- Jump reachability and the ls-penalty curve
- Benchmark corpus for testing route quality/speed
- Source quarantine rules (prohibits reading `tradecalc.py` and `tradedb.py`)

**Purpose:** The authoritative contract. Use this to understand what features must be preserved.

### [SLICE_SUMMARY.md](SLICE_SUMMARY.md)
Condensed digest of the planner-rewrite project. Contains:
- Architecture boundary (CLI → RunRequest → planner → RunResult → renderer)
- Summary of all completed slices
- Data scale notes and query patterns
- Filter semantics reference (Y/N/? state filters, pad-size thresholds)
- Deferred decisions awaiting next slice
- Cleanup candidates (low-priority technical debt)

**Purpose:** This is the required startup read instead of per-slice plans. Start here.

---

## Per-Slice Plans and Reports

Each completed slice has an implementation plan (what needs to be done) and a completion report (what was done).

### Slice 1 — First Safe Slice (Complete)
**Fixed station-to-station, single-hop planning.**

| Document | Content |
|----------|---------|
| [first_safe_slice_implementation_plan.md](first_safe_slice_implementation_plan.md) | Design plan for Slice 1: module structure, responsibilities, cargo optimiser strategy, reachability checking approach. |
| [first_slice_completion_report.md](first_slice_completion_report.md) | Proof of completion: modules implemented, command integration points, supported shape, validation behaviour. |

### Slice 2 — One-Hop Expanded Endpoints (Complete)
**System endpoints expand to eligible stations; planner selects best station pair.**

| Document | Content |
|----------|---------|
| [second_slice_implementation_plan.md](second_slice_implementation_plan.md) | Design plan for Slice 2: endpoint resolution, system expansion scope, SQL-side pruning strategy, station-pair matrix evaluation, scoring model. |
| [second_slice_completion_report.txt](second_slice_completion_report.txt) | Proof of completion (text format): what was delivered, validated shapes, audit corrections. |

### Slice 3 — Open-Ended One-Hop Search (Complete)
**Omitted `--to` endpoint; planner finds best reachable destination.**

| Document | Content |
|----------|---------|
| [third_slice_implementation_plan.md](third_slice_implementation_plan.md) | Design plan for Slice 3: spatial narrowing via bounding-box SQL query, open-ended destination search, _MIN_MEANINGFUL_DEMAND threshold, pad-size filter semantics. |
| [third_slice_completion_report.md](third_slice_completion_report.md) | Proof of completion: routes match where planner filter models align; spot-checked against `--old`; run-short benchmark byte-identical; open-ended search ~3s vs. 7–30s legacy. |

### Slice 4 — Open-Ended Origin Search (Complete)
**Omitted `--from` endpoint; planner finds the best reachable origin. One open-ended search now serves both anchored directions.**

| Document | Content |
|----------|---------|
| [fourth_slice_implementation_plan.md](fourth_slice_implementation_plan.md) | Design plan for Slice 4: generalising the open-ended search to run from either anchored endpoint via `open_role`; three-way dispatch. |
| [fourth_slice_completion_report.md](fourth_slice_completion_report.md) | Proof of completion: omitted-`--from` shapes, the unified open-ended search, the reachable-station subquery fix, validation. |

### Slice 5 — Unanchored Galaxy Search (Complete; restructure investigated and parked)
**Both endpoints omitted; planner selects origin and destination, finding the best one-hop trade galaxy-wide.**

| Document | Content |
|----------|---------|
| [fifth_slice_implementation_plan.md](fifth_slice_implementation_plan.md) | Design plan for Slice 5: the unanchored both-endpoints-omitted search as a separate additive path; bounded reachable-system-map candidate query; confirmation prompt. |
| [fifth_slice_completion_report.md](fifth_slice_completion_report.md) | Proof of completion: four-way dispatch, the bounded candidate query, the confirmation prompt, ~83s vs ~293s legacy. Carries the source-level audit and its localised remediations. |
| [fifth_slice_restructure_implementation_plan.md](fifth_slice_restructure_implementation_plan.md) | Design plan for the candidate-query restructure addressing audit Findings 2 (per-system extrema discarding multi-commodity station pairs), 3 (`--ls-penalty` applied after the bounded SQL slice), and the credits-affordability follow-up. Investigated empirically through six probes (P1–P6) under both no-`--age` and realistic `--age 1/2/7` data shapes; **decision: parked / monitored, not implemented**. 144 axis-uplift checks returned zero higher-scoring winners. Findings remain valid mechanisms; current data and scorer do not make them affect winner selection. Re-evaluation triggers and the carrier-dominance observation recorded in the plan. |

### Slice 6 — Multi-Jump Per-Hop Reachability (Complete)
**`--jumps-per >= 2` works for every shape; default keyed to `--ly-per`; planner failure messages cleaned up.**

| Document | Content |
|----------|---------|
| [sixth_slice_implementation_plan.md](sixth_slice_implementation_plan.md) | Design plan for Slice 6: three pieces (fixed-endpoint pair reachability, open-ended reachable-station query, unanchored reach map), five probes (P1–P5) gated before code, the keyed `--jumps-per` default, and the failure-message sharpening. Probe results recorded inline. |
| [sixth_slice_completion_report.md](sixth_slice_completion_report.md) | Proof of completion: A2 bubble + BFS for Piece A, B2 iterative widening into `td_reachable_systems` for Piece B, C3 on-demand reach during match for Piece C, `JumpPath.distance_ly` redefined as polyline length, keyed default, validation pin removed, `PlannerResultError` with five message-family wordings, unanchored prompt rewritten, `^C` cleanup-mask closed. `--old` no longer holds any one-hop shape the new planner cannot serve. |

### Slice 7 — Bulk-Sale-Tax Safe Demand Cap (Complete)
**Metals/Minerals destination quantity capped at `floor(demand * 0.25)` to avoid the in-game bulk-sale price penalty.**

| Document | Content |
|----------|---------|
| [seventh_slice_implementation_plan.md](seventh_slice_implementation_plan.md) | Design plan for Slice 7: conservative 25% safe cap on Metals/Minerals destination demand, no discounted-price modelling, EDCD/FDevIDs category as source of truth, deferred `--bulk-tax-mode` option. Supporting research in [mined_tax.md](mined_tax.md) / [mined_tax.pdf](mined_tax.pdf). |
| [seventh_slice_completion_report.md](seventh_slice_completion_report.md) | Proof of completion: sensitivity resolution via `Category.name`, DTO fields on `TradeCandidate` / `CargoLine`, all three fetch paths wired (fixed-pair, open-ended, unanchored), dialect-portable `cast(... * 0.25, Integer)` for the SQL floor, hop-level renderer note. Verification at Prince Prominence -> Evangelisti showed Gold and Beryllium cap-binding at exact `floor(demand / 4)` values. |

### Slice 8 — Vanilla Multi-Hop from Known Origin (Complete)
**Known-origin multi-hop planning for `--from X --hops N` and fixed-terminal `--from X --to Y --hops N`.**

| Document | Content |
|----------|---------|
| [eighth_slice_implementation_plan.md](eighth_slice_implementation_plan.md) | Design plan for Slice 8: vanilla multi-hop from a known origin, fixed-terminal route shaping, frontier and expansion widths, SQL-side destination envelope pruning, destination-system frontier diversity, deferred advanced route modifiers. |
| [eighth_slice_completion_report.md](eighth_slice_completion_report.md) | Proof of completion: known-origin multi-hop implemented, fixed-terminal Sol -> Lave matches legacy profit while remaining faster, SQL envelope pruning restored performance, system-diverse frontier trim restored route quality, partial-route warning branches probed. |

### Slice 9 — Max Price Filter and Testable Route Output (Complete)
**Absolute commodity-price cap (`--max-price`) and expanded auditable plain-text route output.**

| Document | Content |
|----------|---------|
| [ninth_slice_implementation_plan.md](ninth_slice_implementation_plan.md) | Design plan for Slice 9: a row-local `--max-price` cap applied across every candidate-fetch path, default sized against live data, plus the renderer expansion for per-hop and cumulative auditable figures. |
| [ninth_slice_completion_report.md](ninth_slice_completion_report.md) | Proof of completion: `--max-price` wired across all fetch paths, carrier-fiction probe evidence behind the default, renderer per-hop/cumulative output, and the deferred unanchored re-baseline and fixed-station route-quality investigations closed. |

### Slice 10 — Open-Origin Multi-Hop (Complete)
**Multi-hop to a fixed destination with the origin chosen by the planner (`--to Y --hops N`, `--from` omitted); the route is grown backward from Y.**

| Document | Content |
|----------|---------|
| [tenth_slice_implementation_plan.md](tenth_slice_implementation_plan.md) | Design plan for Slice 10: backward beam search from the fixed destination, the `best_open_ended_trades_into` primitive, the generalised `terminal_hop` onward-viability EXISTS, per-station coalescing trim, and credit-optimistic expansion plus a forward credit-correction pass. |
| [tenth_slice_completion_report.md](tenth_slice_completion_report.md) | Proof of completion: the backward open-origin search, the cargo bound admissibility fix proven exact, the bounded correction (exact early-stop plus a tunable cap), and four verification runs at low credits showing the wall-clock inversion removed and correction reduced to milliseconds. |

---

## Reference and Technical Notes

## Reference and Technical Notes

### [tuples.md](tuples.md)
Filter semantics and design decisions:
- **Y/N/? state filters** — accepted-state sets for `--black-market`, `--fleet-carrier`, `--settlement`, `--planetary`
- **Pad size filtering** — ship-fit threshold model (`S`/`M`/`L` means "ship needs at least this pad")

**Purpose:** Authoritative reference for how station filters work. Link to from code when implementing filter logic.

### [notes.txt](notes.txt)
Engineering notes on data scale and diagnostics:
- ~800K stations, ~19M commodity rows; pruning in SQL is critical
- Avoid speculative edge-case probes at data scale
- Multi-hop diagnostic granularity trade-offs

**Purpose:** Quick reminders on performance constraints and posture.

### [old_carrier_discrepancy_brief.md](old_carrier_discrepancy_brief.md)
Historical record of a specific fleet-carrier data issue. Likely reference material for debugging.

### [bulk_sale_tax_candidates.sql](bulk_sale_tax_candidates.sql)
SQL helper that surfaces Metals/Minerals trade pairs suitable for verifying the bulk-sale-tax 25% destination-demand cap. Excludes fleet carriers so candidates reflect background-sim economy rather than owner-set prices.

**Purpose:** Quick way to pick a verification pair when testing the cap mechanic; safer than picking from memory because demand values drift with EDDN refresh.

---

## Next Steps

- **Starting a new session?** Read `SLICE_SUMMARY.md` and the current slice's implementation plan.
- **Implementing a feature?** Check `SLICE_SUMMARY.md` for deferred decisions and cleanup candidates.
- **Debugging filter logic?** See `tuples.md`.
- **Understanding the spec contract?** Consult `trade_run_black_box_spec.md`.
- **Verifying a route?** Reference the benchmark corpus in the spec.

---

## Notes for Agents

This rewrite is clean-room. Do not inspect, summarise, or ask about `tradedangerous/tradecalc.py` or `tradedangerous/tradedb.py`. The spec and slice plans are sufficient.

The planner operates within a fixed boundary:
```
CLI parser → RunRequest → planner → RunResult → renderer
```

All new planning logic must cross that boundary cleanly. No legacy objects, no pre-loaded galaxy state, no coupling to quarantined modules.
