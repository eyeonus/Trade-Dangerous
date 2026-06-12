# Slice 25 — Bound-Ordered Pairing with a Provable Early Stop; Beam-Width Sweep

*Implementation plan. Status: draft for approval, 2026-06-12.*

---

## Why

Slice 24 left one named residual, with the evidence already on file
(P3, `twenty_fourth_slice_implementation_plan.md`): at open filters,
~53% of per-anchor fetch cost is Python materialising the rows the
open-side query returns. The SQL walk is fixed; the rows crossing the
SQL→Python boundary are not. Most of them never produce a winning
pair — they are fetched, built into objects, matched, grouped, and
then lose.

The Slice 22 prune already skips the expensive cargo solve for pairs
that provably cannot beat the kept set. But it fires *after* the rows
exist in Python. This slice moves the same idea one stage earlier:
stop the rows being read at all.

The mechanism, in one line: have SQL return the open side's rows
**best-case-first**, stream them instead of fetching them all, and
stop reading at the first point where everything still unread provably
cannot beat what we already hold.

---

## Scope

**In:**

- Part A — probes that measure whether the early stop would fire early
  enough to pay, and what the SQL-side ordering costs. Go/no-go gate.
- Part B — the bound-ordered streaming fetch and the early stop, wired
  into the open-ended candidate path used by the open-anchor engine,
  the one-hop open planners, and the fixed-terminal envelope fetch.
- Part C — the beam-width value-versus-time sweep, run **after** Part B
  on the finished engine. Produces the wider-vs-thinner-beams graph and
  a keep-or-change decision on the width constants.

**Out (recorded so they stay decided):**

- **The unanchored matcher** (`fetch_unanchored_trade_candidates`) —
  it has its own bounded, temp-table design (Slices 5/15/23) and its
  own cost profile. Not touched here; revisit separately if its
  residual ever warrants it.
- **The fixed-pair fetch** (`fetch_station_pair_candidates`) — both
  sides are named places, the row volume is small, there is no open
  side to order. Nothing to win.
- **Changing the beam constants inside Part B.** The sweep decides
  that, with evidence, as its own step. No tuning slips into the
  engine work.
- **Persistent/materialised galaxy-wide summaries — still dead** (per
  Slice 24), not revived by this slice.

---

## Background — the shape of the seam today

`fetch_open_ended_trade_candidates` (`data_gateway.py`) fetches the
open side's rows with `.all()` — every row materialised — matches
supply to demand by item in Python, builds `TradeCandidate` objects,
sorts by profit per unit, and returns the lot.

The consumer (the Slice 22 machinery, present at all three call
sites) then groups candidates by station pair, orders the pairs by a
cheap optimistic ceiling (`cargo_order_key`), and solves them
best-first. `_KeptScoreThreshold` tracks the K-th best child kept so
far; `cargo_prune_floor` converts that score back into a raw-profit
floor, and a pair whose ceiling cannot reach it skips the solve.

Two facts about that machinery matter for the design:

1. The kept-set floor is **per anchor** and starts empty: nothing can
   be pruned (or stopped) until K pairs have actually solved. For the
   one-hop planners K = 1, so the floor exists after the first solve.
   For multi-hop expansion K = 50 (the expansion width), so the floor
   is the *50th*-best child — a much weaker bar.
2. Solve order changes the work done, never the children chosen — the
   recorded Slice 22 argument. The early stop inherits it.

---

## Part B — Design

### The unit of truncation is the station pair, not the row

A pair here is always (anchor × open station), and the cargo solve is
multi-commodity: a pair's plan can use several items, so its rows are
scattered through any row-ordered stream. Truncating *rows* would
hand surviving pairs an incomplete candidate list and silently change
their cargo plans — not byte-identical, not acceptable.

So the stream is grouped: rows arrive **station-complete**, stations
ordered by their best case, best first. A station we read is read in
full; a station we stop before is skipped in full. Surviving pairs
are therefore complete and solve exactly as today.

### The per-station ceiling, computed in SQL

The fixed side's per-item price extremes already sit in the
`td_open_fixed_bounds` temp (Slice 23). Joining the open-side row to
it (replacing the present EXISTS probe with a join that yields the
bound) gives each row an optimistic profit-per-unit in SQL:

```text
open destination:  row.demand_price  - bounds.min_price   (best buy)
open source:       bounds.max_price  - row.supply_price   (best sell)
```

A station's ceiling is then `capacity × max(optimistic ppu)` over its
rows — the same dominant term as the optimiser's root bound. It is
deliberately loose where looseness keeps it admissible: unit counts,
the bulk-tax demand cap, and per-item credit limits are ignored (each
can only make the real value *smaller* than the ceiling).

Mechanically: a window function (`MAX(...) OVER (PARTITION BY
station_id)`), ordering the stream by `(station_ceiling DESC,
station_id)` — or an equivalent per-station aggregate into a small
ordered temp if the probe shows SQLite plans the window badly. P2
decides which.

### The stop rule

The consumer drives the stream and owns the floor, exactly as it owns
the solve today. Per station group, in arrival order:

1. Read the station's rows; build its candidates; solve its pairs
   best-first (the existing path, unchanged).
2. Floor rises as solves complete (`_KeptScoreThreshold`, unchanged).
3. Before reading the next station: if
   `next_station_ceiling × best-case ls multiplier < floor-as-raw-profit`,
   stop. Close the cursor; every unread station is provably below the
   bar.

The ls conversion is direction-aware, for free:

- **Open source** (backward expansion): the hop's destination is the
  anchor, whose `ls_from_star` is fixed — the exact conversion
  (`cargo_prune_floor` at the anchor's ls) applies.
- **Open destination** (forward): the destination varies per station,
  so the conversion uses the curve's best case (ls = 0). Looser but
  admissible. Folding each station's real ls into the SQL ceiling is
  a recorded refinement, taken only if P1 says the loose bound stops
  too late.

### Why routes stay byte-identical

- Stations are skipped only when their ceiling — an upper bound on any
  pair they could form, by construction — cannot reach the kept floor.
  The floor only rises. A skipped station could never have entered the
  kept set, so the chosen children are unchanged.
- Stations that are read are read whole; their pairs solve from the
  same complete candidate lists as today.
- Solve order shifts (SQL ceiling order vs `cargo_order_key` order) —
  covered by the standing Slice 22 argument: order changes work done,
  never children chosen.
- **Tie-break preservation:** final child selection breaks progress-
  rank ties by original fetch order, which today derives from the
  candidate sort `(-profit_per_unit, item_name)`. The streaming
  consumer rebuilds the surviving candidates into that same sorted
  order before grouping, so surviving pairs keep today's relative
  order and ties resolve identically.
- **`--towards` carve-out:** the threshold is disabled there (progress
  ranking, no score floor), so the early stop is disabled too — the
  stream simply runs to completion, byte-identical by inspection. Same
  carve-out as Slice 22.

### Touch points

- `planner/data_gateway.py` — the open-side query gains the bounds
  join, the ceiling, the ordering, and a streamed (station-grouped)
  variant; the fixed side and the bounds-temp build are unchanged.
- `planner/route_common.py` — the open-anchor engine's consumption
  loop drives the stream and the stop; threshold/solve logic reused
  as-is.
- `planner/route_onehop.py`, `planner/route_anchored.py` — same
  pattern at their call sites (K = 1 and the envelope fetch
  respectively), one seam at a time.
- Diagnostics — stop-point counters on the expansion stats
  (stations skipped, rows not read), always-on like the existing
  counters, so the effect is visible in standard output.

---

## Part A — Probes (gate before build; scripts uncommitted, deleted at slice end)

### P1 — Would the stop fire early enough to pay?

Instrument real runs (no engine change): record, per anchor, the
per-station ceilings in descending order and the floor's trajectory
as pairs solve. Replay the two against each other to find where the
stop *would* have fired, and what fraction of stations/rows it would
have skipped.

Shapes: the worst baseline (`--from sol --hops 6 --jumps 2`), a
mid-size open shape, and a one-hop open run (K = 1, the strongest
floor). Open filters and a realistic filtered state.

**Gate:** if the simulated stop skips a trivial share of rows (worst
case: K = 50's weak floor meets a short, flat ceiling tail), the win
is not there — record the numbers, stop the slice after Part C's
sweep, and close the residual as measured-and-declined.

**P1 results (2026-06-12) — gate passed decisively: GO for Part B.**

Probe: `fetch_open_ended_trade_candidates` wrapped in-process; the
real candidates pass through untouched, and alongside each call the
probe replays the proposed consumption — stations in descending-
ceiling order, pairs solved best-first against a fresh K-sized
threshold — and records where the stop would fire. Ceilings are
reconstructed from the candidate set exactly as the SQL bounds join
would compute them (open price against the fixed side's best price
per item); rows that survive SQL but form no candidate are invisible
to the probe, so the skip percentages below *understate* the SQL-side
truth slightly. Verify mode then re-solves every skipped station
against the floor at the stop, hunting for a counterexample.

| shape | K | stop fired | stations skipped | rows skipped (read / fetched) | violations |
|---|---|---|---|---|---|
| one-hop open from Sol | 1 | 1/1 | 99.9% | **100.0%** (5 / 91,584) | 0 (verified) |
| `--from sol --hops 3 --jumps 2` | 50 | 139/139 | 90.3% | **93.0%** (261k / 3.74M) | 0 (verified) |
| `--to lave --hops 3 --jumps 2` (backward) | 50 | 100/101 | 88.9% | **86.1%** (178k / 1.28M) | 0 (verified) |
| `--from sol --hops 6 --jumps 2` (worst) | 50 | 285/288 | 91.6% | **93.9%** (496k / 8.18M) | — |
| worst + `--fc N` | 50 | 289/290 | 93.8% | **94.4%** (515k / 9.20M) | — |

Findings:

1. **The K = 50 floor is not weak in practice.** The risk section's
   worst case did not materialise: the ceiling tail is long and
   steep, so even the 50th-best child's score outruns it after a few
   dozen stations. The stop fired in 99% of candidate-bearing calls
   across every multi-hop shape.
2. **Both ls conversions hold.** Forward (ls = 0 curve maximum) and
   backward (anchor ls) were each falsification-tested — zero
   violations across ~510k skipped station-solves on the three
   verified shapes.
3. **The K = 1 one-hop case is near-total.** Five rows read of
   91,584 fetched; the engine's own diagnostic showed 20,812 of
   20,814 pairs already pruned by Slice 22 — the early stop turns
   those pruned pairs into rows never read at all.
4. **Expected win.** P3 (Slice 24) put Python row materialisation at
   ~53% of per-anchor cost; cutting ~93% of rows read removes most
   of that share, before counting the pairing-loop and grouping work
   that disappears with it. The SQL-side ordering cost (P2) is the
   remaining unknown.

### P2 — What does the ordering cost, and does streaming actually stream?

- `EXPLAIN QUERY PLAN` on the ordered, bounds-joined query: confirm
  the join keeps the station-first plan (P1 of Slice 24 establishes
  the reference shape) and measure the sort's cost against today's
  query on the same bubbles.
- Confirm SQLAlchemy/SQLite streaming behaviour: rows fetched in
  batches off the cursor (`yield_per` / partitions), Python-side cost
  proportional to rows *read*, not rows the query matched. This is
  the mechanism the whole slice rests on — verify it, don't assume it.
- Window function vs aggregate-temp ordering: pick whichever plans
  cleanly; record the loser so it stays decided.

**P2 results (2026-06-12) — mechanism verified; window-ordering chosen;
GO confirmed with calibrated expectations.**

Probe: the same in-process wrapper as P1; for sampled forward calls the
open-side query was rebuilt three ways on the live session (the run's
reachable temp and qualification temp reused via memo/cache) and timed:
A today's EXISTS shape read in full, B bounds-joined + window-ordered
(`MAX(opt_ppu) OVER (PARTITION BY station_id)`), C ceiling aggregated
into a temp first. Eight samples on `--from sol --hops 3 --jumps 2`,
four terminal / four non-terminal after a sampler fix (the first pass
caught only non-terminal calls).

Findings:

1. **Exact.** A, B and C returned identical row sets in all eight
   samples (count + order-insensitive checksums).
2. **Streaming streams.** The fractional read (7% of rows, the P1
   fraction, via `yield_per` partitions + explicit close) beat the
   full read consistently — pysqlite produces rows on demand; the
   driver pre-buffering risk is dead.
3. **Sort cost is noise.** B full vs A full sits within ±5% (one
   outlier sample recorded). The ORDER BY does force the whole walk
   before the first row — the saving is in what is never emitted,
   converted, or processed after it.
4. **C is dead.** Its ceiling-temp build re-pays the entire walk
   (~190ms on the big bubble — as much as today's whole query), and
   the ceiling depends on the per-anchor bounds so it cannot be
   reused across anchors. Window-ordering (B) is the design. Decided.
5. **Calibration.** On raw SQL+read alone, the fractional B read runs
   ~65–75% of A's full read (terminal: ~60ms vs ~87ms; non-terminal:
   ~214ms vs ~280ms). The rest of the win is Python work P2
   deliberately excludes: the per-row match loop, candidate
   construction, and grouping that the ~93% unread rows (P1) never
   enter. Expect roughly a third to a half off per-anchor fetch cost,
   not the P1 headline percentage.
6. **Found: the non-terminal walk is dominated by the per-row
   onward-viability EXISTS.** A non-terminal call returning 808 rows
   costs ~198ms where a terminal call of similar output costs ~47ms —
   the difference is the onward probe, evaluated per row though its
   correlation key is the station. Candidate refinement for Part B:
   onward viability is (for the forward role) "station has at least
   one row in the supply qualification temp" — a per-station
   semi-join against run-scoped state that already exists, replacing
   a per-row StationItem EXISTS. Must be proven predicate-identical
   to the current EXISTS branches before adoption; checked at build
   time, byte-identical verification as ever. Independent of the
   early stop and compounding with it.

---

## Part B — Build record (2026-06-12)

Built as designed, one seam at a time, each verified byte-identical
before the next: the open-anchor engine (`route_common`), the one-hop
planners (`route_onehop`), then the fixed-terminal envelope path
(`route_anchored`). The old monolithic fetch was deleted once the third
seam left it caller-free. Verification across the slice: 17 of 17 route
comparisons identical (eleven seam-1 shapes including `--towards` and a
filtered twin, four one-hop shapes plus the corrected station-endpoint
re-run, two fixed-terminal shapes), then run set 5's eight final-code
runs re-confirmed against the same-day old-code reference.

The onward-viability semi-join was adopted: the filter lists were
confirmed term-for-term identical between the onward EXISTS branches
and the qualification temps' population predicates (they were already
shared helpers on the temp side), so a non-terminal fetch populates the
opposite side's temp for its bubble and semi-joins it per station. The
no-cache fallback (one-hop, always terminal) keeps the per-row EXISTS,
extracted to a module-level helper.

Two deliberate micro-variations from the old consumption, recorded:
equal-progress-rank tie-breaks now resolve by reconstructed best-pair
order (best ppu, item name, pair key) instead of the old unordered-scan
first-appearance order, and solve order follows the stream's ceiling
order. Neither changed any verified route; the Slice 22 argument (order
changes work done, never children chosen) covers the solve order, and
the tie-break reconstruction proved route-stable across the whole
verification set.

Headline results (full table and diagnostics in `timing_baselines.md`
run set 5): open multi-hop shapes −45 to −61% wall (worst shape 145.7s
→ 57.0s), fixed-terminal −29/−33%, one-hop planner-internal ~10× on
big-candidate shapes. Production skip rates matched P1's simulation
within a few points.

Two findings recorded for later (mechanism and numbers in run set 5):

- **Loose-envelope cache lever.** The fixed-terminal engine's per-layer
  destination envelope disables the reachable-memo and bubble-skip
  reuse even on layers where the envelope is wider than the bubble and
  so constrains nothing. Dropping a provably-loose envelope from those
  layers' cache keys would give early layers the open engine's reuse.
  Performance only; not this slice.
- **Fixed-vs-open crossover is geometric.** sol→lave at jumps 2: fixed
  wins 12× at 2 hops, breaks even at 3, loses from 4 up. The
  destination constraint pays while total reach is comparable to the
  separation. Useful context for users and for any future envelope
  work; no action owed.

---

## Part C — Beam-width value-versus-time sweep (after Part B)

The question (eyeonus's): what does the value-vs-time curve look like
with thinner and wider beams? Never measured — Slice 8's P2 only
checked the hop-1 score curve's shape at one seed (is #50 still a
real trade?). No end-to-end sweep exists.

Run after Part B so the numbers describe the engine we will actually
be running — tuning on a finished pitch.

**Method:** probe script sets `_MULTIHOP_EXPANSION_WIDTH` /
`_MULTIHOP_FRONTIER_WIDTH` (together, same value) per run and invokes
the planner in-process. Record final route score, profit, and
wall-clock per width.

- Widths: 10, 25, 50 (baseline), 100, 200. The wide end on slow
  shapes costs real wall-clock; if 200 is prohibitive on the worst
  shape, cap that shape at 100 and say so.
- Shapes: one mid open multi-hop, the worst baseline shape, one
  realistic filtered run. Same database snapshot throughout; `--age`
  runs widened per the reproduction rule if the sweep spans real time.

**Decision rule:** 50 stays unless the curve shows a clearly better
operating point — value flat while time falls (narrow) or value still
climbing materially (wide). Any change to the constants changes
routes; it is a recorded decision with the graph as evidence, never a
silent retune. If narrowing wins, note the compounding effect: a
smaller K strengthens the kept floor, which makes Part B's stop fire
earlier still.

**Deliverable:** the value-vs-time table and graph in
`timing_baselines.md`, plus the decision — and an answer for eyeonus
either way.

**Part C results (2026-06-12) — swept; both widths stay at 50.**

The sweep ran as designed (five widths × three shapes on the finished
engine) and produced a decisive dataset. The full record — data, graph,
findings, decision rationale, and the user-facing-lever idea
(considered, not adopted) — lives in its own standalone document,
**`beam_width_analysis.md`**, kept deliberately outside the slice docs
as the durable reference. Headlines: time is linear in width; value is
a shape-dependent staircase with no universal knee; narrowing below 50
loses 23–77% of value on two of three shapes; the big wide-beam gains
under open filters are carrier-tail value (the `--fc N` control knees
at 50); no measured width dominates 50. Variance from plan: the sweep
was recorded in the standalone document rather than
`timing_baselines.md`, at Tromador's request, so it survives release
housekeeping.

---

## Verification

- **Routes byte-identical** against the standard baseline command set
  (both filter states, 1 and 2 jumps), same posture as Slices 22–24.
- **Counter expectations differ from Slice 24:** rows-fetched /
  candidate-row counters are *expected to fall* — that is the point.
  Children chosen, pair groupings of survivors, and route output must
  not move. The new stop-point counters report what was skipped.
- Wall-clock recorded as run set 5 in `timing_baselines.md`; the Part
  C sweep recorded alongside.
- `--towards` runs verified unchanged (stop disabled).

## Risks

- **The K = 50 floor is weak.** The multi-hop stop waits for 50
  solved pairs before it can fire. P1 measures this directly; it is
  the slice's go/no-go.
- **Sort cost eats the win.** Ordering 30–40k rows is cheap in C, but
  the plan must stay station-first; P2 checks both before any code.
- **Streaming surprises.** If the driver materialises the full result
  despite streaming APIs, the saving vanishes — P2 verifies the
  mechanism in isolation first.
- **Tie-break drift.** The rebuilt candidate ordering must reproduce
  today's `(-profit_per_unit, item_name)` order among survivors;
  byte-identical verification catches any slip.

## Order of work

1. P1, P2; results recorded in this file as they land.
2. Go/no-go on Part B against the P1 gate.
3. Part B build, one seam at a time (open-anchor engine, then
   one-hop, then the envelope fetch), verified against baselines at
   each step.
4. Run set 5 into `timing_baselines.md`.
5. Part C sweep on the finished engine; graph, decision, and
   constants change (if any) recorded.
6. Completion report; probes deleted.
