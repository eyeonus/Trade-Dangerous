# Planner Rewrite Documentation Index

Quick reference guide to the docs/Planner/ directory for agents and developers.

---

## Essential Startup Documents

**Read these first before proposing or implementing anything in this side mission.**

### [BASELINE.md](BASELINE.md)
The condensed current-state digest — the primary startup read. Contains:
- Architecture boundary (CLI → RunRequest → planner → RunResult → renderer) and the module map
- What works now (the route-shape grid and cross-cutting behaviour)
- The rules that still bind future work (query discipline, filter semantics, market-data facts, settled decisions)
- What is still owed, and where to read deeper

**Purpose:** Start here. It replaces reading the full slice history at startup.

### [SPEC_STATUS.md](SPEC_STATUS.md)
The coverage map of the behavioural spec. For every option and section it records:
- `[done]` — built to spec
- `[varied]` — built, deliberately different (with the reason)
- `[todo]` — in the spec, still gated or inert

It also closes out the spec's five "open decisions for supervisor".

**Purpose:** See at a glance what is implemented, varied, or outstanding — then open only the spec section it points to, instead of re-reading the whole contract.

### [trade_run_black_box_spec.md](trade_run_black_box_spec.md)
The authoritative behavioural contract — the "Bible". An AI extraction from the legacy path, audited long-form by the dev team. Defines what the command must do (without saying how), the option contract, failure categories, eligibility rules, cargo/financial constraints, jump reachability, the ls-penalty curve, the benchmark corpus, and the source-quarantine rules.

**Purpose:** The contract of record. Not a full re-read each session — reach for it through `SPEC_STATUS.md` when you need a section's detail.

### [SLICE_SUMMARY.md](SLICE_SUMMARY.md)
Frozen slice-by-slice history (Slices 1–15). Architecture boundary, a summary of every completed slice, data-scale notes, filter semantics, and the deferred decisions as they stood.

**Purpose:** Deep reference, not a startup read. No longer appended to — new slices update `BASELINE.md` and `SPEC_STATUS.md` instead.

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

### Slice 11 — Unified Single-Anchor Open Multi-Hop (Complete)
**Both single-anchor open multi-hop shapes (`--from X` and `--to Y`) run on one direction-keyed engine; fixes the open-destination hang by giving it the open-origin search's credit-optimistic expansion.**

| Document | Content |
|----------|---------|
| [eleventh_slice_implementation_plan.md](eleventh_slice_implementation_plan.md) | Design plan for Slice 11: generalising the open-origin engine to serve both open shapes via `open_role`, the three-way multi-hop dispatch, the direction-aware correction-pass orientation, and trimming `_plan_multi_hop` to fixed-terminal only. |
| [eleventh_slice_completion_report.md](eleventh_slice_completion_report.md) | Proof of completion: root cause of the forward-open hang (real-budget branch-and-bound during expansion), the unify/wire/trim commits, and before/after verification — `--to` and `--from --to` byte-identical, the `--from` hang fixed (30min+ to ~3m10). |

### Slice 12 — Planner Module Split and Cruft Sweep (Complete)
**Pure structural rationalisation: `run_route.py` split into one module per planner shape, plus removal of dead code accumulated across earlier work. No behaviour change.**

| Document | Content |
|----------|---------|
| [twelfth_slice_implementation_plan.md](twelfth_slice_implementation_plan.md) | Design plan for Slice 12: the five-module target layout (dispatch / one-hop / fully-anchored / part-anchored / shared common), the used-by-many-vs-used-by-one allocation rule, the dead-code inventory, and the no-behaviour-change verification approach. |
| [twelfth_slice_completion_report.md](twelfth_slice_completion_report.md) | Proof of completion: the split executed via a deterministic AST-extract workflow, dead code removed, and verification — import, flake8, and AST parity (every symbol present once with identical code), plus live-data spot-checks. |

### Slice 13 — Fully-Unanchored Multi-Hop (Complete)
**Multi-hop with both endpoints omitted; the planner selects the origin, the destination, and every station in between — the last basic route shape.**

| Document | Content |
|----------|---------|
| [thirteenth_slice_implementation_plan.md](thirteenth_slice_implementation_plan.md) | Design plan for Slice 13: composing the unanchored one-hop candidate fetch with the proven forward open-anchor engine, the seed-rank trim, the engine relocation to `route_common`, the dispatch and validation changes, and the prompt rework. |
| [thirteenth_slice_completion_report.md](thirteenth_slice_completion_report.md) | Proof of completion: the engine move proven byte-identical, `route_unanchored` seeding the engine galaxy-wide, valid routes across filtered / unfiltered / tight-credit / `--limit` runs, existing shapes and benchmark unchanged, prompt reword verified. |

### Slice 14 — Complete Checkpoint K: Retire the Legacy Route/Preload Architecture (Complete)
**Legacy `trade run`, `TradeCalc`, the full-galaxy preload model, and `TradeDB` retired; `trade run` is planner-only. Closes the main refactor's Checkpoint K.**

| Document | Content |
|----------|---------|
| [fourteenth_slice_implementation_plan.md](fourteenth_slice_implementation_plan.md) | Design plan for Slice 14: the 14A–D structure (retire legacy `trade run`, kill full-preload, decide buildcache/lifecycle, planner cleanup), the `tradedb.py` / `buildcache` policies, and the breaking-fork validation posture. |
| [slice_14_succession_handover.md](slice_14_succession_handover.md) | Mid-14C succession handover: the cache-split and single-TradeORM-handle strategy, the definitive tradedb-kill consumer map and kill sequence, and the outstanding loose ends. |
| [fourteenth_slice_completion_report.md](fourteenth_slice_completion_report.md) | Proof of completion: the eight commits, what each part (14A–D) delivered, archive completeness, and the verification posture. |

### Slice 15 — Listener Catch-Up, Plugin Guardrails, and Unanchored Bounds (Complete)
**EDDN listener brought forward to the post-Slice-14 TradeORM surface; spansh generic-dialect fallbacks replaced with explicit guardrails; the unanchored price bounds made filter-aware and station-driven (filtered run ~7m45 → ~2m15, route unchanged).**

| Document | Content |
|----------|---------|
| [fifteenth_slice_implementation_plan.md](fifteenth_slice_implementation_plan.md) | Design plan for Slice 15: the 15A–C structure — listener catch-up in the separate repo, the spansh generic-fallback purge, and the unanchored early-cutoff tightening. |
| [fifteenth_slice_completion_report.md](fifteenth_slice_completion_report.md) | Proof of completion: the listener TradeORM swap and the Category.csv-seeding keystone, the thirteen-fallback guardrail purge, and the filter-aware + station-driven bounds with the py-spy/EXPLAIN diagnosis and the 43.9s → ~0.75s bounds timing. |

### Slice 16 — Empty-Jump Endpoint Positioning (Complete)
**`--start-jumps` / `--end-jumps` treat a named `--from` / `--to` as a positioning anchor; eligible trade endpoints expand from the anchor's system within N empty jumps. `--empty-ly` sets the unladen fan-out range (falls back to `--ly-per`).**

| Document | Content |
|----------|---------|
| [sixteenth_slice_implementation_plan.md](sixteenth_slice_implementation_plan.md) | Design plan for Slice 16: the role-keyed `_stations_from_endpoint` seam, reuse of `reachable_systems_from` and the temp-table station fetch, the anchor-as-positioning-point semantics, the empty-`--ly` fallback, and the private positioning bubble-cache. |
| [sixteenth_slice_completion_report.md](sixteenth_slice_completion_report.md) | Proof of completion: the four-step build, the new `fetch_eligible_stations_in_reachable_systems` helper, architecture compliance, the bubble-cache isolation answer to the audit, and live-data spot-checks showing the endpoint expands off the anchor while guardrails and `--empty-ly` behave. |

### Slice 17 — Progress-Toward-a-Target Routing (`--towards`) (Complete)
**`--towards SYSTEM` steers an open-destination route toward a target without forcing arrival (requires `--from`, excludes `--to`). Each hop must land strictly closer, ranked progress-first (closest, then fewer hops, profit only a tie-breaker); a hop reaching the target ends the route ("arrived after N hops").**

| Document | Content |
|----------|---------|
| [seventeenth_slice_implementation_plan.md](seventeenth_slice_implementation_plan.md) | Design plan for Slice 17, with the mid-slice correction recorded: the MUST (strict-progress filter at the shared open-destination fetch) vs the MAY (progress-first ranking, profit an optional tie-breaker) read from the spec's RFC 2119 keywords; the legacy goal-scoring review that confirmed the reading; arrival and early stop as emergent properties; the `--towards`/`--to` exclusion. |
| [seventeenth_slice_completion_report.md](seventeenth_slice_completion_report.md) | Proof of completion: the five-step build, the shared progress-rank helper applied at every selection point (non-towards paths byte-identical), arrival capture in the open-anchor engine, arrival reporting, and the Sol → Lave spot-check arriving in 2 of 3 hops. |

### Slice 18 — Direct Point-to-Point Trade (`--direct`) (Complete)
**`--direct` plans the single most profitable trade between a fixed `--from` and `--to` with no jump-path or distance checks — the relocation run that doesn't fly empty. Requires both endpoints, single hop only; `--ly-per`/`--jumps-per` tolerated but ignored; `--towards` and empty-jump positioning rejected.**

| Document | Content |
|----------|---------|
| [eighteenth_slice_implementation_plan.md](eighteenth_slice_implementation_plan.md) | Design plan for Slice 18, with the authorised legacy trace that pinned the contract: legacy `--direct` forced `hops = 1`, set the jump range to effectively infinite, and skipped reachability; the open-destination "to anywhere" mode (a full-galaxy in-Python scan) is deliberately dropped. The validation philosophy — tolerate the moot, reject contradictory route-shape intent — and the renderer handling of a hop with no jump path. |
| [eighteenth_slice_completion_report.md](eighteenth_slice_completion_report.md) | Proof of completion: the un-gate across both validation layers, the canonical `hops → 1`, the reachability skip in `_best_pair_plan`, the renderer's direct-leg line, and the spot-checks. Records the discovery that `trade run` carries two validation layers (the redundancy the next slice resolves). |

### Slice 19 — Fuzzy Name Matching and Duplicate-System Disambiguation (Complete)
**`trade run` resolves partial endpoint names (exact → prefix → substring, no typo tolerance) by reusing the shared `TradeORM` lookup, with an approximate-match echo and `@N` coordinate disambiguation for genuine duplicate system names. Resolution moved to dispatch; the planner reads resolved endpoint DTOs and never touches the database handle. A follow-on set the namespace-by-syntax policy (bare = system, `/name` = station, no cross-namespace fall-through; errors name a System or Station, never "place"), moved partial-candidate gathering onto a normalised `lookup_name` superset, and rendered ambiguity labels before the session closes.**

| Document | Content |
|----------|---------|
| [nineteenth_slice_implementation_plan.md](nineteenth_slice_implementation_plan.md) | Design plan for Slice 19: reuse `lookup_place`/`lookup_system` rather than building a second resolver; resolve `--from`/`--to`/`--towards` once at dispatch onto `RunRequest`; the approximate-match echo; the #224 `@N`-by-coordinate disambiguation; and the three lookup-path defects (regex escaping, the stray `45`, the stale TradeDB-wrapper attributes) fixed via one shared candidate-list formatter at both raise sites. |
| [nineteenth_slice_completion_report.md](nineteenth_slice_completion_report.md) | Proof of completion: the resolver-as-adapter wiring, the resolve-once-at-dispatch flow, the shared `format_system_candidates` helper, the regex escape, and the live spot-checks — partial names, the `@N` collision list, the invalid-index message, and an `@1` selection growing a real route from one specific duplicate system. |

### Slice 20 — Single Validator (Complete)
**The legacy command-layer argument checker is retired; the planner's
`validate_run_request` on the `RunRequest` is the one validator. Three
argument-pair rules moved into it first (`--towards` and `--start-jumps` need
`--from`; `--end-jumps` needs `--to`); the `--towards`/`--to` and
`--direct`/`--hops` exclusions stay at the parser.**

Planned in session, not in a separate plan doc — a small slice.

| Document | Content |
|----------|---------|
| [twentieth_slice_completion_report.md](twentieth_slice_completion_report.md) | Proof of completion: the three rules ported, `validateRunArgumentsFast` removed, the insurance non-divergence, the two kept call sites, and the live spot-checks. |

### Slice 21 — `--avoid` (Commodity / System / Station Exclusion) (Complete)
**`--avoid` excludes a commodity, system, or station from a route. Tokens resolve once at dispatch (repeated / comma-separated, fuzzy-matched like the endpoints; bare = system or commodity, slash = place, precision-first with a place winning a same-tier tie). An avoided commodity is never bought; an avoided station is never a route station; an avoided system is also barred from jump-path transit (the permit case). The explicit `--from` is exempt as the origin — start there, never return.**

| Document | Content |
|----------|---------|
| [twenty_first_slice_implementation_plan.md](twenty_first_slice_implementation_plan.md) | Design plan for Slice 21: resolve avoid tokens once into three id sets; the application seams (the shared station-attribute predicate for station/system, the buy-side commodity filters, the reachability bubble for jump-path transit); the explicit-origin carve-out; the precision-first, place-wins resolution order. |
| [twenty_first_slice_completion_report.md](twenty_first_slice_completion_report.md) | Proof of completion: the five-part build across resolution, station/system exclusion, commodity buy-side exclusion, jump-path transit exclusion, and the origin carve-out; the required-argument threading through reachability; and the live spot-checks including the transit reroute and the invariant holding. |

### Slice 22 — Cargo Pre-Filter (Complete)
**Skip unwinnable cargo solves: an admissible pre-check (the optimiser's own root bound, ls multiplier folded in) prunes the branch-and-bound solve for any pair that provably cannot beat the kept set, solving best-first so the threshold rises fast. Routes byte-identical; the slow real-budget shapes 6–130× faster (fixed-terminal Sol→Lave 285s → 46s, one-hop open from Sol 8m40 → ~5s).**

| Document | Content |
|----------|---------|
| [twenty_second_slice_implementation_plan.md](twenty_second_slice_implementation_plan.md) | Design plan for Slice 22: the Camp A (real-budget, cargo-bound) vs Camp B (optimistic-budget, fetch-bound) measurement, the reused admissible bound, the exactness proof, the `--towards` carve-out, and the wiring across the fixed-terminal and one-hop open engines. |
| [twenty_second_slice_completion_report.md](twenty_second_slice_completion_report.md) | Proof of completion: the prune mechanism, the verification table (routes unchanged, 47,457 of 51,596 solves pruned on the fixed-terminal case), Camp B confirmed inert, and the observed bottleneck shift to candidate fetch. |

### Slice 23 — Fetch-Path Overhead Sweep (Complete)
**Post-Slice-22 the planner was fetch-bound. Seven verified leaks closed — headline: the open-ended candidate queries are narrowed in SQL by the fixed side's per-item price bounds (small temp table + correlated EXISTS), so rows that could never pair never leave the database. Also: aggregate failure classification for endpoint matrices, a run-scoped station DTO cache, a run-scoped unanchored qualifying temp, a skipped redundant reachable precompute, session-cached bulk-tax ids, single per-fetch timestamps. Routes unchanged; the large open multi-hop shape 159s → 83s.**

Planned in session from a supplied seam analysis, no separate plan doc — each claimed issue was verified against the code before remediation.

| Document | Content |
|----------|---------|
| [twenty_third_slice_completion_report.md](twenty_third_slice_completion_report.md) | Proof of completion: the seven verified seams, the rejected Python-side aggregation and the SQL shape that replaced it, the exactness argument, the live verification table, and the remaining fetch-bound residual. |

---

### Slice 24 — Qualify Once (Complete)
**Run-constant row qualification answered once per station into lazily populated run-scoped temps; with `--age`, a station-level fresh-set cut means stale stations are never walked. Exact (16/16 baseline runs byte-identical); ~10% off open-filter wall, and `--age` became a true cost lever: worst shape 124s open → 55s at `--age 3` → 38s at `--age 1`; realistic stacked filters ~27s. Probes P1–P3 closed the `--fc N` question (filter cost law: relief is proportional to rows removed) and measured the residual (~53% Python row materialisation — the bound-ordering evidence).**

| Document | Content |
|----------|---------|
| [twenty_fourth_slice_implementation_plan.md](twenty_fourth_slice_implementation_plan.md) | The approved plan, with the P1/P2/P3 probe results recorded in place and the data findings that settled the `--age` design. |
| [twenty_fourth_slice_completion_report.md](twenty_fourth_slice_completion_report.md) | Proof of completion: the build, the exactness verification, run sets 3 and 4, variances from plan, and the import-path write-rule side quest. |

### Slice 25 — Bound-Ordered Streaming Fetch and Beam-Width Sweep (Complete)
**The open-ended candidate fetch streams station groups best-ceiling-first with a provable early stop — the tail is never read out of the database; onward viability becomes a per-station semi-join. Exact (17/17 + 8/8 routes byte-identical); open multi-hop −45–61% (worst shape 145.7s → 57.0s), fixed-terminal −29/−33%, one-hop ~10× planner-internal. The first end-to-end beam-width value/time sweep closed Part C: both widths stay 50 (`beam_width_analysis.md`).**

| Document | Content |
|----------|---------|
| [twenty_fifth_slice_implementation_plan.md](twenty_fifth_slice_implementation_plan.md) | The approved plan with P1/P2 probe results, the Part B build record, and the Part C sweep decision recorded in place. |
| [twenty_fifth_slice_completion_report.md](twenty_fifth_slice_completion_report.md) | Proof of completion: the streaming design, the seam-by-seam build and verification, run set 5, variances from plan, and the recorded levers (loose-envelope cache keys; the geometric fixed-vs-open crossover). |
| [beam_width_analysis.md](beam_width_analysis.md) | The standalone beam-width analysis — kept outside the slice record deliberately; see Reference section below. |

---

### Slice 26 — `--loop` (Return to the Starting Station) (Complete)
**Anchored round-trip routes delivered: a loop is a fixed-terminal route whose terminal is each chain's own origin (per-root terminal rule, per-root envelope anchor, `(root, destination_system)` frontier dedupe, partial-route suppression), plus a follow-up fix qualifying loop terminals as real sell-back destinations. The galaxy-wide loop (`--from` omitted) was investigated and decided against: a cheap seed rank cannot contain the best loops within the fixed beam width of 50 (P1), and an honest loop per admitted origin is cheap at 2 hops but explodes with depth (P2). `--loop` requires `--from`.**

| Document | Content |
|----------|---------|
| [twenty_sixth_slice_implementation_plan.md](twenty_sixth_slice_implementation_plan.md) | The approved two-part plan; Part A (anchored) built, Part B (unanchored) carries the probe results and a not-built outcome banner. |
| [twenty_sixth_slice_completion_report.md](twenty_sixth_slice_completion_report.md) | Proof of completion: the anchored loop build, the terminal-qualification fix, the unanchored decision, variances, housekeeping. |
| [unanchored_loop_investigation.md](unanchored_loop_investigation.md) | The standalone record of the unanchored-loop investigation and decision — P1/P2 findings, the alternatives weighed, and the homework for any future reopen. |

---

### Slice 27 — `--via` (Route Through Waypoints) (Complete)
**Routes through one or more named waypoints in any order, every shape (fixed-terminal, single-anchor open, loop); every waypoint visited or the run fails. Requires an anchor (`--from`/`--to`) — a chosen variation, the spec sets none — capped at six. Built on the credit-optimistic open-anchor engine with a per-chain satisfied-via mask on a lane-diversity frontier (one search lane per owed waypoint), so every visit order is explored and no high-profit lane starves a waypoint. The committed leg-stitching design was withdrawn after audit and the slice rebuilt on the mask state. The terminal lane reserves a slot for the chain nearest the destination, so a distant `--to` closes instead of the route stalling on the last waypoint.**

| Document | Content |
|----------|---------|
| [twenty_seventh_slice_implementation_plan.md](twenty_seventh_slice_implementation_plan.md) | The plan, revised after audit: the withdrawn leg-stitching design, the retained satisfied-via state model, and the credit-optimistic expansion plus lane-diversity frontier that replaced the expensive policy. |
| [twenty_seventh_slice_completion_report.md](twenty_seventh_slice_completion_report.md) | Proof of completion: resolution and validation, the via search owner, every shape, the terminal-phase progress-retention fix diagnosed by instrumentation, variances, housekeeping. |

---

### Slice 28 — Cargo Search Confident-Stop and Diagnostics Gating (Complete)
**The cargo branch-and-bound now stops when *confident*, not when it has *proved* the optimum: a no-improvement early stop (bail 500 nodes after the last improvement) plus a far lower outer fuse (100,000 → 2,000). The fuse had become the operating point — under tight credits the search ground to it proving an optimum it found within ~25 nodes, one solve per candidate pair (so the cost was multiplicative). Routes unchanged across every shape tested; the slow fixed-terminal shapes ~3.6× faster (sol→achenar h8 at 5M: 354s → ~99s, cargo 264s → 6.7s). The slow path stays — on big holds it beats its greedy seed ~11% per solve — it just stops grinding once it has the answer. Also: the route diagnostics block is gated behind `-ww` (debug level 2), so normal output is clean. Planned in-conversation; evidence in `exactness_study.md`.**

| Document | Content |
|----------|---------|
| [twenty_eighth_slice_completion_report.md](twenty_eighth_slice_completion_report.md) | Proof of completion: the confident-stop mechanism and the fuse drop; the study evidence (optimum by ~25 nodes, cap-invariant routes, the ~11% per-solve gap, the front-loaded fixed tax); verification across hops/credits/endpoints; the diagnostics single-output-path audit and the `-ww` gating. |

---

### Slice 29 — `--unique` and `--loop-interval` (No-Revisit Route Constraints) (Complete)
**The two no-revisit constraints, built together as one rule at two strengths (`--unique` is the unbounded `--loop-interval`). Enforced on every multi-hop engine through a per-chain visited-history: the candidate helpers skip forbidden stations *inside* the stream (so illegal revisits cannot starve legal candidates at the top-K cut), and the frontier trim keys carry a history fragment so a chain that can still complete is not coalesced away — orientation-aware, so the recency window is read correctly when the open-origin / `--via` to-only search grows the chain backward. Validation: `--unique` excludes `--loop` / `--loop-interval` (reject-redundant), `--loop-interval < 2` rejected, `--loop` + `--loop-interval` allowed. An impossible request fails with a specific `NoUniqueRoute`. Verified on live data — the fixed-terminal bite, the backward-orientation bracket, and `--via` + `--unique`.**

| Document | Content |
|----------|---------|
| [twenty_ninth_slice_implementation_plan.md](twenty_ninth_slice_implementation_plan.md) | The plan, revised after an audit pass: the in-helper filter (not caller-side), the route-order orientation rule, the per-(station, history) trim keys, the failure classification, and the reject-redundant decision. |
| [twenty_ninth_slice_completion_report.md](twenty_ninth_slice_completion_report.md) | Proof of completion: the six-commit build, the contract reading (gap `< N`, N=2 inert), the mechanism and the two enforcement seams, validation, the per-layer skip-delta failure classification, and the live verification. |

### Slice 30 — `--shorten` (Built, Found Inert, Removed)
**Implemented per the audited plan on both fixed-`--to` engines (rank arriving routes by practical score per hop, the legacy metric), then stripped. The per-hop ranking is inert on current data — a longer route's accumulated profit keeps its per-hop value competitive, so nothing ever shortens, not even a 25-hop route. The only metric that reliably shortens needs a profit-tolerance constant the contract does not define. Decided with eyeonus to remove the option rather than ship a flag that silently no-ops; `trade run` now rejects `--shorten` as an unknown option. Recorded in `SPEC_STATUS.md` (Variations) and `BASELINE.md` (Settled decisions).**

| Document | Content |
|----------|---------|
| [thirtieth_slice_implementation_plan.md](thirtieth_slice_implementation_plan.md) | The audited design + investigation record (carries an OUTCOME banner): the per-hop metric, the fixed-terminal and open-origin harvests, the audit's two blockers, and the resolved decisions. The feature is not in the code — see the banner. |

---

### Slice 31 — Multi-Route Output (`--routes`), `--sco`, `--no-bulk-cap`, Beam-Control Removal (Complete)
**`--routes N` returns up to N final routes — best-first by the engine's existing final-route rank, N a maximum, no diversity key, `--routes 1` byte-identical — on every shape (one-hop, fixed-terminal, open-anchor, unanchored; `--via` keeps single-route output for now). Built alongside three smaller changes: `--sco` (declares an SCO drive, clamps the ls-penalty to 0), `--no-bulk-cap` (off-switch for the Metals/Minerals bulk-sale demand cap), and removal of the inert beam-control options `--max-routes` / `--prune-score` / `--prune-hops` (now rejected as unknown options).**

| Document | Content |
|----------|---------|
| [thirty_first_slice_implementation_plan.md](thirty_first_slice_implementation_plan.md) | The audited plan (Findings 1–4 folded in): the four workstreams, the five `--routes` selection seams, the N-aware early-stop and `--routes 1` inert proof, the top-K fixed-terminal close, and the resolved decisions. |
| [thirty_first_slice_completion_report.md](thirty_first_slice_completion_report.md) | Proof of completion: the six commits, the mechanism per workstream, the live + unit verification, and the variances (build order, `--via` left single-route, renderer unchanged). |

---

### Slice 32 — Trade Run Route Output Rewrite (Rich Tiered Default, `--raw`, `--80col`) (Complete)
**`trade run`'s route output rebuilt: a rich colour table is the default, in three station-centric tiers (summary / standard / `-v` verbose) — a row per stop, what you sell on arrival and buy before leaving. Each tier adapts to the terminal width (Balance then Profit shed; at 80col standard drops its Sell column, verbose folds Sell and Buy into one tagged Trade column, so Profit survives). The original plain-text render is preserved as `--raw` (hop-centric, 80-column, verbosity-gated — for grep / pipe / scripts / diagnostics and the GUI). `--80col` forces the portable width; a same-system leg shows as a supercruise; `--summary` graduated from parse-but-inert to the lean tier. A presentation change — no planner behaviour moved.**

Planned in conversation across sessions, no separate plan doc.

| Document | Content |
|----------|---------|
| [thirty_second_slice_completion_report.md](thirty_second_slice_completion_report.md) | Proof of completion: the four-commit arc (plain rewrite → rich default → tiers → station-centric + width adaptation), the output ladder and per-stop model, what each tier carries, the colour scheme, the modules and width plumbing, verification (flake8, render probes, live runs, eyeonus sign-off), and the notes (profit attribution, the GUI path, `--summary` graduating). |

---

## Reference and Technical Notes

## Reference and Technical Notes

### [timing_baselines.md](timing_baselines.md)
Recorded wall-clock and phase-split baselines for the multi-hop route shapes
(2026-06-11 run set, the first with the open-anchor phase timers wired).
Captures the scaling findings: fetch throughput is flat (time tracks candidate
rows), jump range multiplies per-layer cost ~4–5× while hops only add layers,
and the candidate fetch dominates every shape.

**Purpose:** Before/after comparison for future performance work. Routes drift
with database refreshes; the volume/time relationships are the stable signal.

### [beam_width_analysis.md](beam_width_analysis.md)
The standalone beam-width value-versus-time analysis (2026-06-12): what the
two beam constants do, the five-width sweep across three shapes, the
staircase findings, and the decision that both widths stay at 50 (with the
user-facing-lever idea recorded as considered and not adopted).

**Purpose:** The durable record of why the beam is 50. Self-contained —
read it before re-opening any beam-width discussion.

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

- **Starting a new session?** Read `BASELINE.md`, `SPEC_STATUS.md`, and the current slice's implementation plan.
- **Implementing a feature?** Check `SPEC_STATUS.md` for what is built / varied / outstanding, and `BASELINE.md` for deferred decisions.
- **Debugging filter logic?** See `tuples.md`.
- **Understanding the spec contract?** Consult `trade_run_black_box_spec.md` — via `SPEC_STATUS.md` to find the section.
- **Verifying a route?** Reference the benchmark corpus in the spec.

---

## Notes for Agents

This rewrite is clean-room. Do not inspect, summarise, or ask about `tradedangerous/tradecalc.py` or `tradedangerous/tradedb.py`. The spec and slice plans are sufficient.

The planner operates within a fixed boundary:
```
CLI parser → RunRequest → planner → RunResult → renderer
```

All new planning logic must cross that boundary cleanly. No legacy objects, no pre-loaded galaxy state, no coupling to quarantined modules.
