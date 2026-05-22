# Sixth Slice — Multi-Jump Per-Hop Reachability

## Purpose

Make `--jumps-per >= 2` work for every trade run shape — both endpoints
fixed, one endpoint omitted, both endpoints omitted — so `--jumps-per`
becomes a real user knob instead of one validation-clipped to 0 or 1
for two of the three shapes. The slice also lands the deferred default
rule that ties `--jumps-per`'s default value to `--ly-per` (2 jumps when
the ship's jump range is low; 1 jump otherwise), because once every
shape carries multi-jump the default behaves consistently regardless of
which endpoints the user named.

## Origin

`SLICE_SUMMARY.md`, end-of-Slice-5 deferrals:

> **Deferred (not cut):** multi-jump per-hop reachability
> (`--jumps-per >= 2`) and multi-hop routing (`--hops > 1`).

And from the deferred-decisions section:

> The keyed default belongs with the slice that delivers that
> capability.

Slice 6 picks up the multi-jump deferral and the default rule that
depends on it. Multi-hop routing is the next major body of work and is
out of scope.

## Goal

After this slice:

- `--jumps-per` set to any non-negative integer is accepted by
  validation regardless of which endpoints were supplied.
- The planner returns a route whose every hop is at most
  `--jumps-per` jumps long, each within `--ly-per`.
- `JumpPath` carries the ordered intermediate-system sequence so
  `--show-jumps` has the data it needs.
- The default `--jumps-per` is 2 when `--ly-per <= 12.5`, else 1,
  applied only when the user does not name `--jumps-per` explicitly.
- The same-system (`--jumps-per 0`) fast path continues to skip
  hyperspace entirely.
- At `--jumps-per 1` the new unified `>= 1` implementation returns
  the same routes the current single-jump code returns today, and at
  comparable cost.
- An unreachable fixed-endpoint route fails with `NoReachableRoute`
  and a message naming the remedies (raise `--jumps-per`, raise
  `--ly-per`, or in a later slice more hops) — not with
  `NoProfitableTrades`. Classification is already correct in the
  current code; this slice sharpens the message.
- Performance does not regress on the existing slice validation set;
  performance on multi-jump shapes is measured against `--old` and
  recorded.

## Framing — `--jumps-per` is a ceiling

`--jumps-per N` is the maximum number of jumps a hop may use, not an
exact count. `--jumps-per 5` means consider any path of 0, 1, 2, 3, 4,
or 5 jumps. The 1-jump path is the N=1 case of the same general
implementation that finds 5-jump paths; it is not a separately-shaped
problem.

This collapses what would otherwise be three branches per piece (zero,
one, many) down to two:

- **N=0 (same-system)** stays a fast path because it skips hyperspace
  entirely — no jump search at all.
- **N >= 1** is one general implementation per piece. The single-jump
  case is the implementation walking exactly one frontier layer; the
  multi-jump case is the same implementation walking more.

Specialising the N=1 case for cost — keeping today's single-jump code
as a dedicated fast track — is an optimisation question, not an
architecture one. The probes settle it: if the general implementation
costs measurably more at N=1 than today's code does, the existing
single-jump code can stay as a specialised path. That is a measured
fallback, not the starting design.

The ceiling shapes search differently across shapes, and the plan
calls that out so future readers don't over-engineer:

- **Open-ended and unanchored**: the planner picks the destination, so
  "fewer jumps for similar practical score" is a real preference —
  closer destinations win ties and near-ties when other factors agree.
- **Fixed-endpoint**: the destination is the user's pick. For each
  candidate (source, destination) station pair, the walk finds the
  shortest path to the destination as a natural side effect of
  expanding outward one layer at a time. No enumeration of alternative
  path lengths for the same pair, no scoring across jump-count
  variants — the user's endpoint choice already pins what the trade
  is. `--jumps-per` here is a sufficiency test: is there a path at
  all within the budget? The walk's answer is yes-with-this-path or
  no.

## Constraints

- **SQL-first.** Narrowing happens in SQL before anything reaches
  Python. The lesson from the Slice 4 audit (commit `db82e655`) is in
  force: handing a materialised id list back to a later query as a
  literal `IN (...)` flips SQLite off the indexed plan. The reachable
  set stays in SQL — subquery or temp table — for every shape, never
  a Python list.
- **No galaxy preload.** Per-request cost is bounded by
  `--jumps-per × --ly-per` around the search anchor(s), not by the
  size of the galaxy.
- **Dialect portable.** SQLite is the primary backend; MariaDB must
  work. Recursive CTE is supported by both at deployed versions but
  its query-planner behaviour and cost differ between them, so the
  design accounts for that.
- **Quarantine intact.** No reading of `tradecalc.py` or `tradedb.py`.
- **Leave room for multi-hop.** Slice 7 will combine multi-jump with
  `--hops > 1`. The combinatorial expansion is severe: at 5 hops × 2
  jumps with `--from` pinned the route can already reach most of the
  populated bubble; at 6–7 hops with both endpoints pinned, the same.
  Slice 6's design must not paint Slice 7 into a corner — specifically,
  no per-request cost model that only holds for one hop.
- **No regression at N=0 or N=1.** Same-system (N=0) keeps its fast
  path verbatim. At N=1, the unified `>= 1` implementation must
  produce the same routes today's single-jump code produces; cost
  equivalence at N=1 is the probe gate, and a specialised N=1 fast
  path is the documented fallback if the general shape regresses.

## The three pieces of work

One user knob, three places where the planner has to honour it. The
plan keeps them separate because the constraints differ; the
deliverable bundles them.

### Piece A — Fixed-endpoint pair reachability

When both endpoints resolve to specific stations (Slice 1) or specific
systems with station expansion (Slice 2), the planner needs a single
yes/no for each candidate (source, destination) pair: is there a path
of at most `--jumps-per` jumps, each within `--ly-per`?

`plan_jump_path` today has three branches: same-system, `--jumps-per 0`
rejection, and a direct distance test for `--jumps-per == 1`; anything
above raises `ReachabilityImplementationMissing`. The new shape keeps
the same-system fast path and the `--jumps-per 0` rejection, and
replaces the rest with a single bounded walk that terminates on the
first frontier layer when a direct neighbour matches, or on a later
layer when a longer path matches, or with `NoReachableRoute` when the
depth cap is reached without success.

**Edge-source options for the walk:**

- **A1 — Per-frontier SQL query.** Each layer of the walk issues one
  SQL query asking for systems within `--ly-per` of any frontier
  system, excluding visited ones. N queries per call; frontier can
  grow.
- **A2 — Pre-fetched local bubble.** One SQL query returns every
  system within `(--jumps-per × --ly-per)` of the source; in-memory
  adjacency built from `pos_x/y/z`; the walk runs Python-side on the
  bounded set. One query per call.
- **A3 — Recursive CTE.** `WITH RECURSIVE` walks the graph entirely
  in SQL. Path reconstruction inside the CTE is awkward; portability
  between SQLite and MariaDB at the depths Slice 7 will eventually
  reach is the open question.

**Starting hypothesis: A2.** Single round-trip, bounded by spatial
query, scales predictably. A1 is the fallback if A2's bubble blows up
in dense regions. A3 stays in scope because it is also a candidate for
Piece B and a shared shape may suit both.

### Piece B — Open-ended reachable-station query

When one endpoint is supplied and the other is the planner's choice,
`_reachable_station_id_query` builds a subquery of station ids
reachable from the anchor system. Today the subquery has two cases:
N=0 filters to the anchor system alone, and the else-branch filters
to systems within a single bounding box of `--ly-per` around the
anchor — the N=1 implementation.

The new shape keeps the N=0 case as today and replaces the else-branch
with a general N >= 1 expansion capped at `--jumps-per`. At N=1 the
general expansion must produce the same system set as today's single
bounding box; cost equivalence is the probe gate.

**Shape options for the general expansion:**

- **B1 — Recursive CTE from the anchor.** A `WITH RECURSIVE` CTE
  expands outward layer by layer, accumulating reachable system ids,
  capped at `--jumps-per` depth. Single composable statement; remains
  usable inside `.in_(...)` so the candidate query holds its
  primary-key plan.
- **B2 — Iterative widening into a temp table.** N SQL passes, each
  appending newly reachable systems to a per-request temp table; the
  candidate query's reachable-system filter becomes a join to that
  temp table. More machinery, no recursion to worry about.

**Starting hypothesis: B1.** Single query, no temp-table management,
fits the existing subquery-composition pattern from Slice 4. B2 is the
portable fallback if recursive CTE cost differs unacceptably between
backends, or if recursion hits a depth limit that bites at Slice 7's
combined multi-hop × multi-jump cardinalities. If P3 shows B1 has
measurable overhead over the existing bounding box at N=1, today's
bounding-box query stays as a specialised N=1 fast path with B1
handling N >= 2.

Rejected outright: a single bounding box of radius
`(--jumps-per × --ly-per)` with no graph walk. At typical density that
over-includes badly — systems in the bounding-box corners are not
reachable by sequential jumps from the centre. The candidate query
downstream would waste market-row fetches on unreachable stations. The
SQL-first rule means narrowing honestly, not just narrowing cheaply.

### Piece C — Unanchored reach map

`_populate_reach_map` today builds the unanchored reach map as a
cross join of `System` with itself, bounded by `--ly-per`. The N=0
case skips the reach map entirely (the existing
`same_system = request.max_jumps_per_hop == 0` short-circuit); the
else-branch builds the N=1 map of every ordered system pair within
range — already millions of rows for single-jump. Widening that map
to multi-jump pairs by naive self-join produces hundreds of millions
of rows at 2 jumps in dense space. Death.

The new shape keeps the N=0 short-circuit as today and replaces the
N=1 map population with a general N >= 1 shape capped at
`--jumps-per`. At N=1 the general shape must produce the same pair
set as today's cross join; cost equivalence is the probe gate, and
specialising N=1 as today's cross join is a real possibility.

This is the scale risk in the slice and the place probes have to
settle the shape, not the plan.

**Candidate shapes for the general expansion:**

- **C1 — Recursive CTE map populator.** Build the multi-jump
  reachable-pair map by a recursive CTE that, for each source system,
  expands its reach set up to `--jumps-per` layers. Result materialised
  into `td_unanchored_reach`. Single statement; cost depends on the
  optimiser's handling of the recursion.
- **C2 — Stage-by-jump matching.** Keep today's cross-join map as the
  base. For multi-jump, run the per-commodity match through the
  1-jump map first; then for each surviving commodity expand each
  source's reach by an additional jump and re-match, deduplicating
  winners by source/destination. The map never grows; cost is N
  matching passes instead of one.
- **C3 — On-demand expansion during match.** Don't pre-materialise
  multi-jump pairs at all. For each candidate (commodity,
  source_station, dest_station) the per-commodity match produces, run
  a reachability check on demand using Piece A's machinery. Changes
  the match pattern.

**No starting hypothesis** — none of these is settled before
measurement. P4 (below) sizes the relative cost. The constraint
common to all three: whatever shape wins, matching does not pull rows
into Python for filtering. SQL-first is the discriminator. If P4
shows the general shape regresses meaningfully at N=1, today's cross
join stays as the specialised N=1 path with the chosen general shape
handling N >= 2.

## Default rule (`--jumps-per` keyed to `--ly-per`)

When the user does not name `--jumps-per` explicitly:

```text
--ly-per <= 12.5    default --jumps-per 2
--ly-per >  12.5    default --jumps-per 1
```

Lifted unmodified from the deferred-decisions section of
`SLICE_SUMMARY.md`.

The rule applies only when the user did not supply `--jumps-per` —
an explicit user value always wins, including `--jumps-per 0` and
`--jumps-per 1`. The distinction between "user supplied nothing" and
"user supplied a number that happens to equal the default" must be
preserved through whichever layer sets the default. Where the rule
physically lives (cmdenv parser vs `run_request_from_cmdenv`) is a
small implementation choice settled at the time of the change.

## Validation rule change

The current guard at `validation.py:113–119`:

```text
omitted endpoint + --jumps-per not in (0, 1)  ->  UnsupportedRunShape
```

…exists because open-ended and unanchored multi-jump are not built.
Slice 6 builds them. The rule is removed. The remaining `--jumps-per`
rule — non-negative integer required — stays.

## Probes

All probes run before any production code lands. Standalone scripts at
the repository root, untracked, throwaway — same posture as the Slice
5 restructure probes. SQLite against the live dataset on the Crucial
T700. A result file per probe; results summarised back into this plan
in a follow-up section before the implementation step.

A *request profile* is a combination of source/anchor system (where
the shape needs one), `--ly-per`, `--jumps-per`, and station/commodity
filters where they affect the candidate set.

Every probe that compares shapes includes `--jumps-per 1` cases
alongside the multi-jump cases — that is how cost equivalence (or
regression) at the common case surfaces.

### P1 — Bubble cardinality (Piece A)

For a sample of source systems covering dense (Sol-region), medium
(Colonia), and sparse (rim) star fields, measure the count of systems
returned by the bounding-box-plus-squared-distance query at radius
`--jumps-per × --ly-per` for combinations
`(jumps, ly) ∈ {(1, 15), (1, 20), (2, 15), (2, 20), (3, 15), (3, 20), (5, 20)}`.

Question: is the bubble small enough to load and walk in memory at
typical and worst-case parameters, and how does cost grow with N?

### P2 — Per-frontier vs pre-fetch wall-clock (Piece A)

Implement A1 and A2 as standalone probes. Same set of
`(source, destination, --ly-per, --jumps-per)` cases, mixing reachable
and unreachable destinations, with `--jumps-per` covering 1, 2, 3, 5.
Measure end-to-end wall-clock per call. Compare both shapes against
each other and against today's direct-distance test at N=1.

Question: which shape is faster, by how much, does the answer change
with bubble density or `--jumps-per`, and does either shape regress
meaningfully against today's N=1 code?

### P3 — Recursive CTE from anchor (Piece B)

Implement B1 against `System` for varied anchors and `--jumps-per`
values of 1, 2, 3, 5. Measure: rows returned, wall-clock for the CTE
alone, and wall-clock when composed into a representative candidate
query via `.in_(...)`. At N=1 also measure today's bounding-box query
on the same anchors for direct comparison.

Question: does B1 hold its query plan when composed into the
candidate query (the Slice 4 audit lesson), is its cost stable across
backends, and does it regress meaningfully against today's
bounding-box query at N=1?

### P4 — Reach-map widening shapes (Piece C)

Implement C1, C2, and C3 as standalone probes against the unanchored
candidate query. For three to five request profiles with
`--jumps-per` of 1 and 2, measure cold-to-candidates wall-clock and
peak intermediate temp-table size. At N=1 the comparison is against
today's cross-join `_populate_reach_map`.

Question: which shape is feasible at the unanchored search's scale,
does any shape match or beat the current ~83s SQLite baseline at
`--jumps-per 1`, and how much does N=2 cost relative to N=1?

### P5 — MariaDB cross-backend sanity

For the recursive-CTE shapes (B1 and, if it survives P4, C1), one
short run against MariaDB on the Linux VM with a representative
profile.

Question: are the recursive CTE shapes portable in practice, not just
in spec?

## Probe results

Results from each probe summarised back here as it runs. The full
per-probe data files (`probe_pN_results.md` at the repo root) stay
untracked.

### P1 — Bubble cardinality (Piece A)

Standalone probe run against the live SQLite database. Anchors covered
Sol-region dense space, Colonia region (medium), and three high-|pos|
systems on the rim (sparse). Seven `(jumps, ly)` combinations per
anchor, COUNT(\*) over the bounding-box-plus-squared-distance bubble,
median of three warm repeats. Full table in the untracked
`probe_p1_results.md`.

**Headline:** the bubble is small enough to load and walk in memory at
every tested combination, including the worst case.

**Worst-case point:** Sol at `(jumps=5, ly=20)` -> L=100 ly -> ~8,070
systems, ~3.5 ms for the COUNT.

**Density behaviour:**

- Dense (Sol): roughly cubic growth with L — 51 (L=15), 108 (L=20),
  287 (L=30), 659 (L=40), 917 (L=45), 2,082 (L=60), 8,070 (L=100).
- Medium (Colonia): saturates around 148 systems by L=60 and stays
  there. Colonia is an isolated pocket; multi-jump adds little
  reachable population.
- Sparse (rim picks): every combination returns 1. The rim anchors
  are genuine singletons.

**Implication for Piece A:** A2 (pre-fetched local bubble, one SQL
round-trip) is feasible at every tested combination. The bubble does
not blow up at Sol-region density even at `(5, 20)`. The remaining
question — walk wall-clock relative to A1's per-frontier shape and to
today's N=1 direct-distance test — is P2's, not P1's.

**Note on anchor selection:** the dense band picked Sol and its two
nearest-to-origin neighbours from the database, which surfaced a
system named "Test" at `(-1, 0, 0)`. Counts at "Test" match Sol's
exactly, so it does not affect the cardinality reading. The entry
is in the live data; origin is upstream of this rewrite, not a probe
artefact.

### P2 — Per-frontier vs pre-fetch wall-clock (Piece A)

Standalone probe run against the live SQLite database. Three sources
(Sol dense, Colonia medium, rim singleton sparse), four destinations
per dense/medium source (three reachable at ~25/~50/~80 ly, one
cross-region unreachable), one cross-region unreachable for sparse.
Twelve `(--ly-per, --jumps-per)` combinations per pair × three shapes
(A1, A2, direct), median of three warm repeats. A1 ran with a 120s
per-call budget (between-layers check; doesn't interrupt an in-flight
query). A2 used a proper KDTree adjacency
(`scipy.spatial.cKDTree.query_ball_point`) per the plan's "adjacency
built from pos_x/y/z". Full table in the untracked
`probe_p2_results.md`.

**Sweep choice — `--ly-per` in {15, 30, 50}.** Earlier P2 used a too-
narrow {15, 20} set carried over from P1 without questioning. The
real spread of ship jump ranges, default through engineered, covers
~10-50 ly per loaded jump for trade-fit hulls; 50 ly is the realistic
upper end without stripping a hull to a flying gas can. Above that,
cargo weight pulls the range back. {15, 30, 50} samples stock,
optimal-module, and engineered ranges. The earlier {15, 20} corner
missed the high-ly shallow-reach behaviour entirely.

**Correctness:** A1 and A2 agree on `reached` everywhere. No A1
timeouts triggered. The largest A1 case (Sol -> Colonia at (50, 5))
ran 191s — the budget check fires between layers and cannot interrupt
a single huge layer-N query. Probe-implementation quirk, not a
finding.

**Verdict: A2 dominates.** A2 wins almost every case, by huge margins
where the dense-Sol bubble matters:

| Case | (ly, j) | A1 (ms) | A2 (ms) | A2 advantage |
|---|---|---:|---:|---:|
| Sol -> Colonia (22 kly, unreachable) | (50, 5) | 191,461 | 55 | 3,500x |
| Sol -> Colonia (22 kly, unreachable) | (50, 3) | 36,181 | 22 | 1,650x |
| Sol -> G 123-7 (80 ly, reachable d=2) | (50, 5) | 5,692 | 190 | 30x |
| Sol -> LHS 3221 (50 ly, reachable d=4 at ly=15) | (15, 5) | 678 | 8.7 | 78x |

**A1 wins one narrow corner**, by small margins in absolute terms:
destination reachable at depth 1, `--ly-per >= 30`, `--jumps-per >= 2`.
A2 wastes a large bubble fetch on what is really a single-jump check.

| Case | (ly, j) | A1 (ms) | A2 (ms) | A1 advantage |
|---|---|---:|---:|---:|
| Sol -> Vega (d=1, ly=50, j=5) | (50, 5) | 3.5 | 77 | 74 ms |
| Sol -> Vega (d=1, ly=50, j=3) | (50, 3) | 3.6 | 29 | 25 ms |
| Sol -> Vega (d=1, ly=30, j=5) | (30, 5) | 1.6 | 31 | 29 ms |

A1's best win is 74 ms; A2's best win is 191 seconds. The asymmetry
is decisive — A1 is not worth implementing as a fallback or hybrid.

**Implications for Piece A:**

- **A2 selected as the sole shape.** No A1 fallback, no per-layer
  SQL machinery.
- **Bubble cache, mandatory.** Key on
  `(source_system_id, max_bubble_radius_ly)`. Per-RunRequest lifetime.
  A Sol L=250 bubble is ~60k systems plus its KDTree — tens of
  megabytes, comfortable. Without the cache, a 10x10 station-pair
  matrix at Sol `--ly-per 50` does 7.7s of repeated bubble builds;
  with the cache it is ~130 ms total. Applies to all anchored shapes
  (Slices 1/2/3/4); Slice 5's unanchored search has its own reach
  map and is unaffected.
- **Direct-line early-out in `plan_jump_path`.** Before the bubble
  fetch, test whether the destination is within `--ly-per` of the
  source by squared distance. If yes, return a single-jump path.
  Three lines; microseconds. Kills the A1-wins corner entirely —
  every case A1 won was a "destination reachable in one direct
  jump" case, and the early-out resolves those without ever
  fetching a bubble. Generalises cleanly: a user at `--jumps-per 5`
  whose destination is 22 ly away gets the same fast path.
- **scipy as a planner dependency.** `scipy.spatial.cKDTree` lifts
  from probe to planner. Added to `pyproject.toml` in Piece A's
  implementation step. numpy comes along as a transitive dependency.

**Earlier P2 reading (probe rev 1) is superseded.** That run used a
too-narrow `--ly-per` sweep ({15, 20}) and an A2 implementation that
skipped the adjacency build, recomputing distances per BFS layer.
Both undersold A2's strengths and missed the high-ly shallow-reach
corner entirely. The current numbers replace that read.

### P3 — Recursive CTE reachable-system subquery (Piece B)

Standalone probe run against the live SQLite database. Three anchors
(Sol dense, Colonia medium, sparse rim singleton), twelve
`(--ly-per, --jumps-per)` combinations, three repeats per case. Three
queries per combo: B1 alone (CTE returning distinct reachable
system_ids), B1 composed (`Station.system_id IN (CTE)`), and at N=1
only today's single bounding-box query alone + composed for direct
comparison. Full table in the untracked `probe_p3_results.md`.

**CTE shape lesson.** Initially written with `UNION ALL` + terminal
`DISTINCT` (the textbook portable pattern). Dense Sol at (15, 5) did
not terminate — UNION ALL with depth-in-row produces a path-count
explosion in dense graphs. Switched to `UNION` (deduplication during
recursion); cumulative CTE bounded by `|reachable| x (max_depth + 1)`.
Both SQLite and MariaDB support UNION in recursive CTEs at the
versions we ship against; the "portable safe" instinct on UNION ALL
was misapplied.

**Correctness:** B1 returns same system set as today's bounding-box
query at N=1 (verified per anchor). Composed station counts match
between B1 and bbox at N=1.

**Composition preserves the index plan.** B1 composed tracks B1 alone
within a few percent at every depth (e.g., Sol (15, 5): 982 ms alone
vs 986 ms composed). The IN-subquery composition does not flip
SQLite off the indexed plan — the Slice 4 audit lesson holds for the
CTE shape.

**N=1 vs bbox:** B1 is 1.5-2x slower than today's bbox at N=1
(Sol ly=50: 3.88 ms vs 1.49 ms). Minor CTE machinery overhead;
sub-5 ms absolute.

**Where B1 falls over — dense Sol high depth:**

| (ly, j) | Reachable | B1 alone (ms) | B1 composed (ms) |
|---:|---:|---:|---:|
| (15, 5) | 2,416 | 982 | 986 |
| (30, 3) | 5,358 | 2,221 | 2,215 |
| (30, 5) | 19,272 | **20,841** | 20,135 |
| (50, 3) | 20,985 | **18,875** | 18,980 |
| (50, 5) | 58,521 | **141,855** | **162,007** |

142 seconds for the open-ended candidate query at Sol (50, 5) is
interactive-prohibitive. The (30, 5) and (50, 3) cases at ~20 seconds
are also rough. Above ~5,000 reachable systems the cost rises sharply
with depth.

Mechanism: even with UNION dedup the recursive engine still visits
every reachable system at every depth it can be reached at, hashing
each candidate against existing CTE rows. At 58k reachable × 6 depth
slots ≈ 350k cumulative rows × per-row dedup hash + the spatial JOIN
producing each one. SQLite handles it correctly; the constant factor
is heavy.

B1 is correct and composition-clean but its cost at scale is not
acceptable. P3b measures the alternative shape.

### P3b — B2 iterative widening (Piece B follow-on)

Same anchors, same sweep, same comparison shape. B2 per call: reset
per-request temp table, insert anchor at depth 0, then for each depth
1..max_depth `INSERT INTO td_reachable_systems SELECT ... FROM System
JOIN td_reachable_systems WHERE r.depth = current_depth - 1 AND NOT
EXISTS (...)`. Layer-by-layer widening, with the temp table's PK on
system_id keeping the dedup fast. Full table in the untracked
`probe_p3b_results.md`.

**Correctness:** B2's reachable set matches B1 at every
`(anchor, ly, jumps)`. At N=1 both match today's bbox. The three
shapes produce the same set; the choice is purely about cost.

**Cost vs B1 — Sol dense:**

| (ly, j) | B1 (ms) | B2 (ms) | B2 advantage | Reachable |
|---:|---:|---:|---:|---:|
| (15, 3) | 117 | 101 | 1.16x | 630 |
| (15, 5) | 982 | 661 | 1.49x | 2,416 |
| (30, 5) | 20,841 | 12,165 | 1.71x | 19,272 |
| (50, 3) | 18,875 | 18,887 | tied | 20,985 |
| (50, 5) | **141,855** | **85,009** | **1.67x** | 58,521 |

B2 is faster at every heavy case by 1.5-1.7x. At low depth or small
frontiers B2 and B1 are within measurement noise. Colonia and sparse
anchors complete sub-50 ms regardless of shape.

**Composition cost:** B2 composed wall-clock tracks B2 alone within
noise (Sol (50, 5): 85.0 s alone vs 84.0 s composed). The temp table's
PK-indexed system_id column makes the `Station IN (subquery)`
composition essentially free.

**N=1 vs today's bbox:** B2 is 2-3x slower than bbox at N=1 from temp
table machinery (CREATE INDEX, DELETE, anchor INSERT). Sub-5 ms
absolute; not a meaningful regression.

**Implications for Piece B:**

- **B2 selected.** Faster than B1 at every heavy case; ties or noise
  at lower cases; minor overhead at N=1.
- **Cost at the worst case (~85 s at Sol (50, 5)) is still slow.**
  Structural: the dense Sol graph at depth 5 reaches 58 k systems
  regardless of which shape walks it. B2's saving of ~57 s vs B1 at
  this case is non-trivial and the saving compounds across hops in
  Slice 7's multi-hop work, where the reachability query runs
  per-hop.
- **UX:** matches Slice 5's unanchored confirmation-prompt pattern.
  Multi-jump open-ended on a dense ship range is an explicit user
  request; prompt for confirmation before the slow walk.
- **Implementation notes:** per-request temp table `td_reachable_systems`
  created and torn down per RunRequest. Layer INSERT uses portable
  `NOT EXISTS` for skip-already-known (supported on both SQLite and
  MariaDB). Composed candidate query:
  `Station.system_id IN (SELECT system_id FROM td_reachable_systems)`.
- **Python-driven alternative considered, not selected.** Piece A's
  machinery (bubble fetch + scipy KDTree + Python BFS) could in
  principle generate the same reachable set faster — KDTree neighbour
  queries on a 60 k-system bubble would likely cut Sol (50, 5) to
  seconds rather than 85 seconds. It moves work back to Python and
  adds scipy as a dependency to a path that's currently pure SQL.
  Worth recording as a future optimisation lever if Slice 7's
  multi-hop compounding makes B2 unworkable; not required to land
  Slice 6.

### P3c — B2 composed with age filter

P3b's composed measurement returned every Station in reachable
systems. The realistic production candidate query also filters by
market-data freshness via `--age`. P3c re-measures the composed query
with an age filter to size the production candidate set and the
filter's cost.

Composed query gains `AND EXISTS (SELECT 1 FROM StationItem WHERE
station_id = s.station_id AND modified > :cutoff)`. Cutoff was
DB-relative (`MAX(StationItem.modified) - 3 days`) — slightly more
permissive than wall-clock `--age 3` would be for a freshly-imported
database, but representative within ~1 day. Full table in the
untracked `probe_p3c_results.md`.

**Two findings.**

**1. The age filter is essentially free at the composition step.** At
Sol (50, 5): no-age composed 71.6 s, age-3 composed 73.1 s — a 2 %
increase. SQLite's plan probes `StationItem (station_id, item_id)` PK
once per candidate station; the predicate cost is low even at
hundreds of thousands of candidates.

**2. The age filter shrinks the candidate set by ~50x in dense
space.** Sol kept-percentages are 2-4 % across the sweep; the
candidate count drops from hundreds of thousands of geographically-
reachable stations to ~10 k stations with fresh market data:

| (ly, j) | no-age stations | age-3 stations | kept % |
|---:|---:|---:|---:|
| (15, 5) | 45,191 | 1,539 | 3.4% |
| (30, 5) | 267,465 | 6,227 | 2.3% |
| (50, 3) | 288,491 | 6,629 | 2.3% |
| (50, 5) | 558,613 | 11,342 | 2.0% |

Colonia (medium) keeps 5-9 %; the sparse rim anchor returns 0 fresh
stations — its local data is all stale.

**Implications:**

- **Age filter belongs in the composed candidate query**, not pushed
  into the reachable-system temp table build. Geography (B2) and
  freshness (the EXISTS predicate) are independent concerns; mixing
  them would tangle the implementation without performance benefit.
- **Downstream planner cost is bounded by the post-age-filter
  count**, not the raw reachable count. At Sol (50, 5) the planner
  processes ~11 k candidate stations, not 558 k. Per-station market
  evaluation, scoring, and cargo work all scale with this smaller
  number.
- **The 73 s composed cost at Sol (50, 5) produces ~11 k usable
  candidates** — roughly 6 ms per candidate generated. Acceptable
  under the same confirmation-prompt UX as Slice 5's unanchored
  search.
- **B2 selection unchanged.** P3c sharpens the production picture
  around the selection; the shape decision stands.

### P4 — Unanchored reach-map widening shapes (Piece C)

Standalone probe run against the live SQLite database. Five request
profiles — A (ly=15, j=1), B (ly=15, j=2), C (ly=30, j=2), D (ly=50,
j=2), E (ly=50, j=1) — fixed knobs across all: capacity 128, credits
100M, `--age 3`, `--pad-size M`, `--min-gain-per-ton 1`. Four shapes
at N=1 (`today`, C1, C2, C3) and three at N>=2 (C1, C2, C3 — `today`
omitted by construction; production does not support multi-jump
unanchored). Per-shape wall-clock budget 600 s; SQLite `interrupt()`
on expiry. Candidates deduplicated uniformly by
`(item_id, source_station_id, destination_station_id)` so counts are
unique concrete candidates per shape. Best trade by the same
`_concrete_total_profit` path production uses. Full table in the
untracked `probe_p4_results.md`.

**Headline:** C3 selected. C1 times out at every multi-jump profile;
C2 completes only at the smallest multi-jump profile and times out at
realistic engineered jump ranges; C3 completes every profile in
14–44 s, exactly matches `today` at both N=1 baseline profiles, and
agrees with C2 on the only N>=2 cross-check the data supports.

**N=1 baseline (correctness gate):**

| Profile | shape | wall-clock (s) | candidates | best item | best profit |
|---|---|---:|---:|---|---:|
| A (ly=15) | today | 80.59 | 652 | Steel | 53,020,544 |
| A (ly=15) | C1 | 68.55 | 652 | Steel | 53,020,544 |
| A (ly=15) | C2 | 62.63 | 652 | Steel | 53,020,544 |
| A (ly=15) | **C3** | **33.40** | 652 | Steel | 53,020,544 |
| E (ly=50) | today | 132.57 | 271 | Titan Drive Component | 205,863,270 |
| E (ly=50) | C1 | 198.26 | 271 | Titan Drive Component | 205,863,270 |
| E (ly=50) | C2 | 135.27 | 271 | Titan Drive Component | 205,863,270 |
| E (ly=50) | **C3** | **14.60** | 271 | Titan Drive Component | 205,863,270 |

All four shapes converge on identical candidate count and identical
best trade at both N=1 profiles. C1 carries 1.5–2× CTE overhead vs
`today` (consistent with P3's B1 read). C2 stage-1-only ≈ `today`
within noise (same code path). C3 is 2–9× faster than `today` at N=1
because it never materialises the reach map — at Profile E the base
reach map is 44.9 M rows that C3 simply doesn't build.

**N>=2 multi-jump:**

| Profile | shape | wall-clock (s) | candidates | best item | best profit |
|---|---|---:|---:|---|---:|
| B (ly=15, j=2) | C1 | TIMEOUT @ 600 | — | — | — |
| B (ly=15, j=2) | C2 | 131.16 | 1,280 | Titan Drive Component | 72,378,792 |
| B (ly=15, j=2) | **C3** | **31.94** | 690 | Titan Drive Component | 72,378,792 |
| C (ly=30, j=2) | C1 | TIMEOUT @ 600 | — | — | — |
| C (ly=30, j=2) | C2 | TIMEOUT @ 600 | — | — | — |
| C (ly=30, j=2) | **C3** | **18.13** | 291 | Titan Drive Component | 205,863,270 |
| D (ly=50, j=2) | C1 | TIMEOUT @ 600 | — | — | — |
| D (ly=50, j=2) | C2 | TIMEOUT @ 600 | — | — | — |
| D (ly=50, j=2) | **C3** | **43.80** | 320 | Titan Drive Component | 205,863,270 |

**C1 rejected.** Recursive CTE materialisation of the all-pairs
multi-jump reach map times out at every multi-jump profile, including
the smallest (ly=15, j=2). The plan's scale-risk call-out for Piece C
("hundreds of millions of rows at 2 jumps in dense space, death") is
confirmed by measurement.

**C2 rejected for now.** The plan-faithful staged implementation —
immutable N=1 base map, per-(commodity, stage) scratch reach holding
only depth-exactly-K pairs — completes at Profile B (131 s) and
agrees with C3 on the best trade there. At Profiles C and D the
per-commodity recursive widening fans out unworkably; both time out.
C2 is not architecturally broken; it is empirically not viable at
realistic engineered jump ranges.

**Candidate-count comparability — caveat.** N=1 candidate counts are
strictly comparable across all four shapes (identical, by
construction with uniform dedup). At N>=2 C2 and C3 candidate counts
are **not** strictly comparable. C2's stage-by-stage structure runs
N independent top-50 matches per commodity, so a single commodity
can yield up to ~100 candidates at j=2 (capped only by dedup across
stages). C3 caps total accepted at 50 per commodity. The B-profile
C2 count of 1,280 vs C3's 690 reflects that, not a missing-trade
defect. The selection evidence at N>=2 is **best-trade agreement**
(C2 vs C3 at Profile B: identical pair, identical 72,378,792 profit)
and **completion/runtime** (C3 the only shape that completes at
Profiles C and D), not a head-to-head candidate count read.

**C3 internal instrumentation observed:**

| Profile | pairs examined | accepted | bubble cache (source systems) |
|---|---:|---:|---:|
| A (ly=15, j=1) | 652 | 652 | 169 |
| B (ly=15, j=2) | 956 | 690 | 181 |
| C (ly=30, j=2) | 356 | 291 | 95 |
| D (ly=50, j=2) | 345 | 320 | 80 |
| E (ly=50, j=1) | 271 | 271 | 76 |

The direct-distance prefilter is necessary-not-sufficient at N>=2
and tight in practice — accept rates 72–93%. The probe did not record
per-commodity cap hits in the result table, so production should add
that counter if cheap; it is the right signal for detecting future
truncation pressure. The bubble cache stays small (76–181 source
systems) because surviving commodities concentrate supply in a handful
of systems..

**Implications:**

- **C3 selected for Piece C.** Reasons: identical correctness vs
  `today` at N=1 across both small-ly and large-ly profiles, agrees
  with C2 on the only N=2 cross-check the data supports, completes
  every profile under budget, and removes the slice's headline scale
  risk (no multi-jump reach map materialised).
- **No specialised N=1 fast path needed for Piece C.** C3 is
  meaningfully faster than `today` at both N=1 profiles — production
  N=1 unanchored becomes faster, not slower, under the unified shape.
  This resolves the Piece C N=1 specialisation decision point: the
  general shape handles N>=1 uniformly; today's cross-join populator
  is removed when C3 lands.
- **Production C3 must expose instrumentation for** the four
  counters the probe records or implies:
  - pair rows examined per request (sum across commodities);
  - reachable rows accepted per request;
  - source-system bubble-cache count per request;
  - optionally per-commodity cap-hit count (not recorded in the P4
    result table, but a regression signal worth keeping if cheap to
    add).
  These ride alongside the existing wall-clock measurement so a
  production regression can be diagnosed without re-instrumenting.
- **Architectural reuse with Piece A.** The bubble fetch + scipy
  KDTree machinery is the same shape P2 selected for `plan_jump_path`.
  A shared `_load_local_bubble` helper and a shared per-RunRequest
  bubble cache fit both Piece A and Piece C cleanly. Less new code
  than C2 would have needed.
- **Carrier dominance unchanged.** Every multi-jump winner in P4 is
  Titan Drive Component, consistent with the carrier-dominance
  observation already in `SLICE_SUMMARY.md`. P4 confirms but does
  not extend that finding; no planner change required.
- **C2 remains a documented fallback.** If the dataset later evolves
  to a shape that breaks C3's prefilter-then-reach pattern (e.g. very
  dense supply systems with sparse multi-jump connectivity making the
  bubble cache memory-bound), C2's staged scratch is the reference
  alternative to revisit.

## Decision points after probes

- **Piece A shape**: A2 vs A1 vs A3.
- **Piece B shape**: B1 vs B2.
- **Piece C shape**: C1 vs C2 vs C3, and the fallback if none beats
  the single-jump baseline by an acceptable margin.
- **N=1 specialisation**: per piece, does the chosen general shape
  regress measurably against today's N=1 code? If yes for any piece,
  today's N=1 code stays as a specialised fast path with the general
  shape handling N >= 2; if no, the general shape handles N >= 1
  uniformly and today's N=1 code is removed.
- **Bubble caching for Slice 2's expanded-fixed loop**: if P2 shows
  the bubble fetch dominates per-pair cost when the same source
  system recurs across pairs, a per-request cache keyed on
  `(source_system_id, --jumps-per, --ly-per)` lands; otherwise skip.
- **`JumpPath.distance_ly` semantics**: multi-jump cannot return a
  straight-line source-to-destination distance and still call it
  meaningful. Either redefine the field as the total polyline length
  (sum of jump distances) or add a separate `path_distance_ly`. The
  choice depends on whether any current caller relies on the
  straight-line meaning — a grep across `tradedangerous/planner/` and
  `tradedangerous/commands/` answers this before the change.

## Implementation outline (post-probes)

1. **`reachability.py`** — `plan_jump_path` keeps its same-system fast
   path and its `--jumps-per 0` rejection. The direct-distance N=1
   branch and the `ReachabilityImplementationMissing` raise are
   replaced by the chosen general walk (A1/A2/A3) capped at
   `--jumps-per`. New helper for the chosen edge-source shape
   (`_load_local_bubble` for A2, etc.). Path reconstruction returns
   the ordered system sequence; `distance_ly` follows the decision-
   point choice. The `NoReachableRoute` raise on failure carries a
   message naming the remedies (raise `--jumps-per`, raise
   `--ly-per`, in a later slice more hops). If the N=1 specialisation
   decision lands as "keep specialised", the direct-distance branch
   stays and the general walk handles `--jumps-per >= 2`.

2. **`data_gateway.py`** —
   - `_reachable_station_id_query` keeps its N=0 branch. The N=1
     bounding-box branch is replaced by the chosen general shape
     (B1/B2) capped at `--jumps-per`. If the N=1 specialisation
     decision lands as "keep specialised", the bounding-box branch
     stays and the general shape handles `--jumps-per >= 2`.
   - `_populate_reach_map` keeps the N=0 short-circuit (which skips
     the map entirely). The N=1 cross-join is replaced by the chosen
     general shape (C1/C2/C3). If the N=1 specialisation decision
     lands as "keep specialised", the cross join stays and the
     general shape handles `--jumps-per >= 2`.
   - Shared bubble-fetch helper if Piece A goes A2 and the same
     helper suits Piece B's anchor expansion.

3. **`validation.py`** — remove the open-ended/unanchored
   `--jumps-per` pin (line 113–119). Non-negative check stays.

4. **Default-rule layer** — apply the keyed default when the user did
   not name `--jumps-per` explicitly. Layer chosen at implementation
   time, per the default-rule section above.

5. **`run_result.py`** — `JumpPath.distance_ly` documentation tweak
   (or a new `path_distance_ly` field, per decision point).

6. **`run_onehop.py`** — no structural change. The three existing
   `plan_jump_path` call sites keep their shape; the unanchored
   confirmation prompt still applies, with its existing message.
   Update the `NoReachableRoute` raise in `_plan_fixed_endpoints`'s
   failure waterfall (at lines 616–619) to name the remedies (raise
   `--jumps-per`, raise `--ly-per`, in a later slice more hops);
   the corresponding raise inside `plan_jump_path` (item 1 above)
   gets the same treatment.

## Validation

- **Known-answer cases.** Pick a handful of
  `(source, destination, --ly-per)` cases from the database where
  exactly one 2-jump or 3-jump path is geometrically possible.
  Confirm the planner finds that path, every consecutive pair is
  within `--ly-per`, and the polyline arithmetic is consistent.
  Selection is from `pos_x/y/z`, not from in-game knowledge.
- **Spot-checks against `--old`** on multi-jump shapes across all
  three families (fixed-endpoint, open-ended, unanchored). Route
  validity is the gate, not route identity.
- **Benchmark corpus.** Re-run `run-typical` (`--jumps-per 2`, fixed
  endpoint). Record wall-clock against `--old` baseline. `run-wide`
  carries `--start-jumps 1` which Slice 6 does not add, so that
  benchmark stays blocked on a separate piece of work.
- **Default-rule cases.** Three runs at `--ly-per 10`, `--ly-per
  12.5`, `--ly-per 15` without `--jumps-per`; confirm the resolved
  default is 2, 2, 1 respectively. One run with `--jumps-per 1
  --ly-per 10` to confirm the explicit user value overrides.
- **N=0 and N=1 equivalence.** Re-run the prior slices' validation
  set. N=0 results are byte-identical (same-system fast path is
  unchanged); N=1 results are equivalent under the unified
  implementation — same routes, same scores, same fail classes.
- **MariaDB end-to-end.** One full run on the Linux VM against each
  of fixed-endpoint, open-ended, and unanchored multi-jump shapes
  before sign-off.

## Failure messaging — unreachable destination

With multi-jump live for every shape, "user named a destination too
far to reach within the request's constraints" becomes a much more
common failure. Classification today is already correct: both
`_plan_fixed_endpoints` (which raises `NoReachableRoute` from its
failure waterfall at `run_onehop.py:616–619` when no station pair
is reachable) and `plan_jump_path` (which raises `NoReachableRoute`
for the single-pair unreachable case) classify the case correctly,
not as `NoProfitableTrades`. What this slice changes is the message.

Today's messages — "No reachable station pair was found for the
selected endpoints." and "Destination system is outside the
requested jump range." — name the problem but not the remedy. A
Cmdr seeing either wants to know what knob would change the answer.
Slice 6 updates both messages to point at:

- raise `--jumps-per`
- raise `--ly-per`
- (later, when multi-hop lands) increase `--hops`

The classification distinction matters because `NoReachableRoute`
and `NoProfitableTrades` mean different things — the first says
"this route is impossible as specified", the second says "the route
is fine but no trade pays". Multi-jump makes the first case much
more common; the message must be unambiguous about which is which.

## Out of scope

- **Multi-hop routing** (`--hops > 1`). Next slice.
- **`--start-jumps` / `--end-jumps`.** Origin/destination expansion
  by jump radius. Distinct piece of work — separate slice when it
  surfaces.
- **`--direct`.** Bypasses reachability entirely; not a multi-jump
  question.
- **Pruning controls** (`--max-routes`, `--prune-score`,
  `--prune-hops`). Belong with multi-hop.

## Risk and rollback

**Rollback target**: commit `eee84aa3` (current HEAD on
`release/v1`). All edits are localised to `reachability.py`,
`data_gateway.py`, `validation.py`, the default-rule layer, and a
`run_result.py` documentation tweak. Reverts cleanly.

**Scale risk on Piece C** is the headline. Probes are the gate. If no
candidate shape for the reach-map widening beats the single-jump
baseline by an acceptable margin, options are:

- accept a multi-jump unanchored cost meaningfully higher than the
  single-jump baseline (the unanchored search already prompts the
  user; the cost is honest);
- restructure the unanchored candidate generation to not depend on a
  pre-materialised pair map at all (C3-style on-demand expansion);
- if neither holds, return to the conversation with the probe
  evidence and decide.

**Correctness risk** is a wrong-but-plausible path misleading a Cmdr.
Known-answer cases catch this on Piece A. For Pieces B and C, the
per-pair reachability used during scoring and path-assembly relies on
Piece A's machinery, so a correct A protects B and C.

**Regression risk at N=0 or N=1**: N=0 is the same-system fast path
preserved verbatim. At N=1 the unified `>= 1` implementation must
produce the same routes today's single-jump code produces, verified
by re-running the prior slices' validation set. The N=1 cost-
equivalence question is the probe gate; if the unified shape regresses
measurably, today's N=1 code stays as a specialised fast path with the
general shape handling `--jumps-per >= 2`. Either outcome preserves
the common case.

**Combinatorial-expansion risk for Slice 7**: this slice's design
must leave room for multi-hop. The constraint is that no per-request
cost model assumes one hop; in particular, the unanchored reach-map
shape that wins Piece C should still be tractable when re-run per hop
in Slice 7. Probes record per-hop cost in their summaries so Slice 7
has the data to size its own scope.
