# Slice 24 — Qualify Once: Run-Scoped Market Qualification for the Multi-Hop Engines

*Implementation plan. Status: awaiting approval. 2026-06-11.*

---

## Why

The timing baselines (`timing_baselines.md`, run sets 1 and 2) established
three facts about the multi-hop shapes:

1. **Fetch dominates everywhere** — 80–87% of expansion time on every
   shape, at every depth, under both filter states. Cargo pruning landed
   (97% of solves skipped) and barely moved wall-clock.
2. **Filters change the answer, not the bill.** `--fc N` collapsed route
   profits but left candidate-row volumes and wall-clocks unchanged.
3. **Jump range multiplies cost ~4–5× per layer** because every per-hop
   bubble is fully evaluated and the input is never capped.

Mechanism: each expansion call walks its bubble's market rows and applies
the full filter set — station attributes, `--age`, `--max-price`,
supply/demand thresholds — inside the per-anchor query. Frontier bubbles
overlap heavily, so the same station's rows are re-qualified once per
anchor that can reach it (up to 50 per layer, more across layers). The
qualification answer never changes within a run. Only the *pairing*
arithmetic (margins against a specific anchor) is genuinely per-anchor.

The fix: split the two. Qualify rows **once per run** into run-scoped
temp tables; make every anchor's pairing query read the pre-qualified
slice instead of re-walking and re-testing raw market rows.

Precedent already in the codebase: the unanchored engine builds a
run-scoped qualifying temp (fetch-path sweep, item 4) for exactly this
reason. The multi-hop engines never got the same treatment.

---

## Scope

**In:**

- Part A — probes that verify the mechanics and measure the filter
  behaviour (closes the `--fc N` question with a controlled experiment).
- Part B — the run-scoped qualification temps, wired into the open-ended
  candidate fetch used by both multi-hop engines.
- Part B stage 0 — the station-level `--age` cut, settled by the data
  findings below: market data lands as whole-station snapshots, so
  `--age` is a station-level fact, and one index pass removes ~93% of
  the market universe before any bubble is walked.

**Out (recorded so they stay decided):**

- **Persistent/materialised summary tables — rejected.** Galaxy-wide
  derived state maintained on the write path is the preload pattern in
  disk clothing. Dead, not parked.
- **Bound-ordered pairing with provable early stop — deferred.**
  Considered at length; compatible with this slice's design (it would
  order the *pairing* stage, which this slice leaves untouched). Revisit
  only if the post-slice residual still demands it.
- **Orphan-row hygiene on the write path.** The data findings show a
  current writer leaves stale rows behind under newer partial updates
  (546 stations, almost all rows inert). Investigating which
  import/listener path does it belongs with that code, not this slice.
  Recorded; the affected stations are profiled in the findings.

---

## Data findings (2026-06-11, live database, read-only probes)

Run during planning; they settle the `--age` design.

1. **Market updates are whole-station snapshots.** Of 94,344 stations
   with market rows, 93,798 (99.4%) carry one identical `modified`
   across every row. The invariant: a station's market rows cannot
   legitimately differ — an older row could only be a delisted
   commodity that should have been removed on update.
2. **The 546 exceptions are almost entirely inert.** They hold 87,296
   stale rows between them, but 99.1% have zero supply and
   sub-threshold demand — already excluded by the standard eligibility
   predicates. Live residue galaxy-wide: 79 sellable and 698 buyable
   stale rows. Average lag 2.2 days, so a current writer leaves
   partial updates behind — an import/listener-side observation,
   out of this slice's scope.
   Profile of the 546: overwhelmingly settled infrastructure (200
   Coriolis, 83 planetary outposts, 69 Orbis; only 51 carriers at ~19
   stale rows each). The worst cases are 85–92% stale with row totals
   near the full commodity catalogue (~360–380 rows), the stale bulk
   being zero-supply/zero-demand padding. Leading hypothesis: an
   earlier bloated full-catalogue write sitting beneath a newer,
   smaller, honest market list, with no delete-missing on update.
   One named case illustrates the limits: Gandharvi/Bogun Hydroponics
   Nursery is flagged `market = Y` here and carries 32 rows passing
   the eligibility thresholds — but the upstream aggregators disagree
   about it (Spansh shows a market, Inara shows none), so whether the
   market exists in-game is unverified either way. Since our import
   chain includes spansh data, this database agreeing with Spansh is
   expected regardless of in-game truth: where upstreams disagree, we
   inherit whichever wrote last and cannot adjudicate from inside.
   Internal flag-vs-rows inconsistency is negligible (25 stations
   flagged `N` carry 653 rows galaxy-wide). The firm part is the
   timestamp invariant: a station's market rows should share one
   modified time, and the 546 stations where they do not mark a
   write-path fault whatever the in-game truth. Investigation
   deferred to the listener/import work.
3. **`Station.modified` is not a freshness signal.** Only 74% match
   their newest market row; 8.5% of stations have a record more than a
   day *newer* than their market (touched without a market update).
   Deliberately not used — station freshness derives from the market
   rows themselves.
4. **The cut is big.** At `--age 3` on the current snapshot, 6,907 of
   94,344 stations and ~1.1M of ~19M rows survive. The `modified`-led
   covering index (`si_mod_stn_itm`) yields the fresh-station set in a
   single range scan.

---

## Part A — Probes (no engine changes; scripts uncommitted, deleted at slice end)

### P1 — Verify the query plan

`EXPLAIN QUERY PLAN` on the open-ended candidate fetch for a fixed,
known anchor (Sol/Daedalus; one run at `--jumps 1`, one at `--jumps 2`).

Confirm or refute:

- The query drives from the reachable-station set (station-first), not
  from an item or price index.
- Station-attribute filters (`--fc`, `--planetary`, `--pad-size`)
  exclude a station **before** its StationItem rows are visited.

If station-first does not hold, that is a defect to fix on its own
before any caching work — caching a mis-planned query bakes the fault in.

### P2 — Fixed-anchor filter sweep (the `--fc N` question)

The run-set-2 comparison was confounded: filtered runs chose different
frontier anchors, so bubble volumes were never compared like for like.
P2 controls that: **same anchor, same bubble**, fetch repeated under
each filter state:

- open filters (baseline)
- `--fc N`
- `--planetary N`
- `--age 3` (and one tighter value, e.g. `--age 1`)
- combinations (`--fc N --age 3` as the realistic-play case)

Record per state: rows materialised, fetch wall-clock, and (from P1
plans) whether the scan volume moved or only the output did.

Alongside, one SQL aggregate over the test bubbles: stations per system
by carrier/non-carrier, and market rows per station for each class —
testing the working hypothesis that carriers are near-ubiquitous but
unevenly dense, and quantifying how much row volume they actually carry.

**Deliverable:** a recorded conclusion about what attribute filters can
and cannot do to cost, in the completion report and folded into
`timing_baselines.md`.

### P3 — Cost split: qualification vs pairing

Time the per-call fetch cost in two parts for a sample of anchors:

- qualification share — applying the run-constant predicates to the
  bubble's rows;
- pairing share — the anchor-specific work (fixed-side bounds EXISTS,
  gain test, onward-viability EXISTS).

This sets the expected ceiling for Part B's win and is the gate: if
qualification is a trivial share of the walk, Part B is not worth its
complexity and the slice stops after recording that.

Also measure: the union-of-bubbles size on the worst baseline shape
(`--from sol --hops 6 --jumps 2`) — distinct stations and qualified-row
count — to size the temp tables before building them.

---

## Part B — Run-scoped qualification temps

### Design

Two temp tables per run, mirroring the unanchored engine's
supply/demand split:

- `td_run_supply_qual` — rows a station can *sell* (supply side):
  station_id, item_id, price, units (+ system_id for spatial joins).
- `td_run_demand_qual` — rows a station will *buy* (demand side):
  same shape.

Populated with **all run-constant predicates applied once**:

- station attribute filters (state sets, pad-size, avoid station/system);
- `--age` cutoff;
- `--max-price` cap;
- supply ≥ `--supply` / demand ≥ max(`_MIN_MEANINGFUL_DEMAND`, `--demand`);
- avoided-commodity exclusion.

**Stays in the pairing query (anchor-specific, cannot be hoisted):**
the fixed-side per-item price-bounds EXISTS, the `--gain-per-ton` /
`--max-gain-per-ton` pair test, onward-viability EXISTS, and the
`--towards` progress filter.

### Stage 0 — station-level `--age` cut

When `--age` is set, derive the fresh-station set first: distinct
station ids from `StationItem` where `modified >=` the cutoff — one
range scan over the `si_mod_stn_itm` covering index. Only stations in
that set are ever qualified or walked. The row-level age predicate is
retained in the temp build (those rows are being read anyway), so the
546 mixed-timestamp stations behave byte-identically to today: the
full performance win with zero behaviour change. `Station.modified`
is deliberately not consulted (finding 3).

### Lazy population

The union of a run's bubbles is not known up front, and qualifying the
whole galaxy would be preload by another name. So the temps fill
on demand: when an anchor's fetch encounters stations not yet
qualified, qualify **just those stations** (one INSERT…SELECT scoped to
the new station ids), then run the pairing query against the temp. A
run-scoped Python set of qualified station ids (ids only) tracks what is
already in — the same threading pattern as the existing station DTO
cache and reachable memo.

Overlapping bubbles then cost nothing new: a station qualifies the first
time any anchor reaches it, and every later anchor reads the temp.

### Statistics and dialect

`analyze_temp_table()` after each population burst, before the pairing
query — the established SQLite-vs-MariaDB lesson (`abce23a0`): temp
tables without statistics invert SQLite join orders, and bare `ANALYZE`
is not portable SQL.

### Exactness argument

The qualification predicates move verbatim from the per-anchor query to
the temp build. Same predicates, same source rows, same database state →
the qualified set is identical, and the pairing query computes the same
candidates from it. No ordering, scoring, or selection logic changes.
Verification must show byte-identical routes and unchanged volume
counters (rows / pairs / children) against baseline run sets 1 and 2.

### Touch points

- `planner/data_gateway.py` — temp build + the open-ended fetch reads
  the temps; the seam is inside `fetch_open_ended_trade_candidates`, so
  both engines inherit it.
- `planner/route_common.py`, `planner/route_anchored.py` — thread the
  run-scoped qualification handle alongside the existing caches.
- Diagnostics: add qualified-station / qualified-row counters and a
  qualification-time figure to the expansion stats, so the effect is
  visible in the standard output (instrumentation stays always-on; the
  pre-release gating flag remains a separate, later task).

### Verification

Re-run the baseline command set (both filter states, 1 and 2 jumps).
Required: identical routes, identical volume counters, fetch phase down
on the multi-hop shapes, and — the point of the slice — a visible cost
difference between filtered and unfiltered runs. Record as run set 3 in
`timing_baselines.md`.

---

## Risks

- **Temp size on wide runs.** The h6 `--jumps 2` union could reach a
  few million qualified rows. P3 measures this before anything is
  built; if it is unmanageable, fall back to layer-scoped temps
  (qualify per layer, drop between layers) at the cost of some re-use.
- **First-touch latency.** Layer 1 pays most of the qualification;
  later layers ride the cache. Net must still win — the baselines
  catch a regression immediately.
- **SQLite temp storage pressure.** Monitor; `temp_store` behaviour on
  the WSL build to be observed during probes, not assumed.

## Order of work

1. P1 → P2 → P3, results recorded in this file as they land.
2. Go/no-go on Part B against the P3 gate.
3. Part B build, one engine seam at a time, verified against baselines.
4. Run set 3 into `timing_baselines.md`; completion report; probes
   deleted.
