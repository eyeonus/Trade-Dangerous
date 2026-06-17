# Where Exactness Pays — Long-Route / Two-Engine Study

*The overnight investigation (2026-06-16) behind Slice 28, kept as a standalone
reference. The fix it motivated shipped in Slice 28 — see
`twenty_eighth_slice_completion_report.md`. The probe scripts and logs it was
built on were deleted at slice close, and the temporary `cargo.py` telemetry hook
was reverted. What follows is the investigation as it stood, so the
"not applied / for your approval" framing below is the overnight state, not the
current one.*

---

## TL;DR

- **The 350s blow-up is the cargo b&b grinding ~100,000 nodes per solve to *prove* an
  optimum it actually finds in under 25 nodes.** The node cap (`_SEARCH_NODE_LIMIT
  = 100_000`) is oversized by ~4,000× for the route's sake. ~99% of the cargo time
  buys nothing.
- **The fix is a few-line packer change, not an architecture rewrite.** Lowering the
  cap (or, better, a no-improvement early-stop) gives **identical routes 3.5–6×
  faster** on the slow fixed-terminal shapes (worst 354s → 92s), and is a no-op for
  small ships. Validated route-exact across hop counts 4–12, credits 500k–5M, two
  endpoints, and a floor down to cap-25.
- **It dominates the engine-rewrite idea.** Same h8/5M shape: cap fix 92s & exact;
  optimistic engine (`--via`) 129s & −6%. So consolidating onto the optimistic
  backbone is **not warranted for performance** — keep the exact fixed-terminal
  engine, just stop its grind.
- **Calibrated caveats:** cap-N is *route*-exact, not *per-solve*-exact; a *blanket*
  cap costs 0.31% on the open engine's correction pass (Finding 10), so **target the
  fixed-terminal expansion search, or use the adaptive no-improvement early-stop
  (recommended)**. Galaxy-wide unanchored shapes still untested.
- **Your thesis was right, mechanism subtler:** the slow path does fire in the
  early/poor region — but exactness *does* pay there (~11% per solve; the greedy seed
  is genuinely weak on big holds). The waste is *proving* the optimum, not *finding*
  it. Fix = "stop grinding once found," not "drop exactness."
- **Decision for you:** cap ~2,000 targeted to fixed-terminal (trivial, low-risk) vs
  the no-improvement early-stop (recommended, safe everywhere, small change +
  wider validation). Neither applied — your call.

---

## The question (from the session that prompted this)

We run a **two-speed packer** (exact greedy fast path vs branch-and-bound) and
**two routers** (fixed-terminal real-budget exact vs open/optimistic + correction).
A single example — `--from sol --to achenar --hops 8 --credits 5000000` — spent
262s of 350s in cargo b&b, while the same shape at high credits, or forced through
the optimistic via-engine, ran 3–4× faster for ~2M profit difference.

Tromador's thesis: the slow paths are **expensive exactness fired by a proxy
misaligned with where exactness pays**. They fire in the *early/poor/slack* stretch
of a long route, where the value at stake is smallest and the destination
constraint is loose. We've only ever benchmarked 1–6 hop, mid-range, big-hold,
decent-money runs — the convenient corner. The 8–12 hop and small-ship corners are
unmeasured.

**Goal:** data to answer (a) is the long-route blow-up as bad as the one example
suggests, and (b) where — if anywhere — the slower exact paths are genuinely worth
their cost. Enough to make an educated plan.

## Guardrails

Non-destructive only: read-only `trade run`, probe scripts, this doc. No commits,
no schema/data changes, no engine surgery. One temporary, behaviour-neutral
telemetry line in `cargo.py` (env-gated, reverted at close). Production code for
all measured numbers. No workflows, no spawned agents — strictly sequential.

---

## Finding 1 — the optimiser mechanism (read from `cargo.py`)

- **The b&b trigger is a conservative worst-case proxy.** `_credit_cannot_bind`
  takes the fast path only when you could fill the *entire hold* with the *most
  expensive* available commodity and still afford it. Otherwise b&b fires. It keys
  off worst-case affordability, not whether the budget actually changes the answer
  — exactly the "fires too readily" Tromador suspected.
- **The b&b seeds itself with a greedy and searches for better.** The incumbent is
  `max(greedy-by-profit-per-unit, greedy-by-profit-per-credit)`, both budget-feasible.
  So the recursion only earns its keep when it beats that seed. That gives us a
  clean measure: **gap = exact − seed**.
- **The fast path is exact** when credit can't bind (greedy-by-profit-per-unit fills
  the hold optimally with unit weights). So the two speeds are *exact-fast* and
  *exact-slow*, not exact-vs-approximate. The approximation only enters at the
  **engine** level, when the open/via engines run the packer in `ignore_credits`
  (optimistic) mode during search and correct the finalists afterwards.

## Finding 2 — the optimistic engine still pays b&b in correction (sanity run)

`--from sol --hops 2 --capacity 100 --credits 1000000 --fc n` (open destination,
tight credits): 350 b&b solves, **all in the correction phase** (2.4s). So
"optimistic avoids b&b" really means "avoids it *during search* — but still pays it
on the finalists when credits bind." The correction cost is bounded by the finalist
count, not the full pair count, which is why it stays cheap relative to a
fixed-terminal real-budget search.

## Finding 3 — synthetic packer gap: the slow path CAN matter (refutes prior)

`packer_gap_probe.py` — 28,784 synthetic solves across capacity {16,100,290,720} ×
n-commodities {2,3,4,6,8,12} × credit-tightness {0.05‥1.5}, comparing production
exact vs the replicated seed.

| Metric | Value |
|--------|-------|
| b&b fired | 98.6% of solves |
| exact beat seed | **42.6%** of solves |
| gap% mean / median / max | **3.32% / 0.00% / 81.07%** |
| worst case | cap=100, n=4, tight=0.35: seed 126,600 vs exact 668,746 (5.3×) |

Read: **most of the time the seed is already optimal (median 0%)**, but a sizeable
minority of mixes have a real gap, with a heavy tail. So the b&b cannot be dismissed
a priori — on *some* commodity mixes it recovers a lot.

The open question this forces: **are those high-gap mixes ones real Elite markets
actually produce?** The synthetic generator allows free combinations (margins to 6×,
log-uniform prices) that may be unrealistic. The gap is largest at small capacity
and mid-tightness, and *shrinks* at capacity 720 (mean gap 0.6–1.9% vs 2–6.6% at
cap 100) — bigger holds average the integer-rounding loss away. That hints the
big-hold real case may sit near the benign end, but it must be measured, not assumed.

**Next:** real planner solves via the env-gated telemetry, harvested from the route
matrix below.

---

## Finding 4 — the long-route blow-up is a FIXED tax, not exponential (Wave 2a)

Hops curve, the nasty setting (cap 720, ly 30, j2, 5M credits, sol → achenar):

| hops | wall | b&b solves | cargo time | profit |
|------|------|-----------|-----------|--------|
| 4 | 307s | 6,180 | 259s | 42.9M |
| 6 | 338s | **6,677** | 263s | 74.0M |
| 8 | 354s | **6,677** | 264s | 105.2M |
| 10 | 366s | **6,677** | 264s | 136.3M |
| 12 | 378s | **6,677** | 264s | 167.5M |

The b&b count **saturates at 6,677 from 6 hops up** and cargo time is flat at
~264s. The blow-up is a fixed tax paid in the early poor layers; extra hops just
stack cheap fast-path layers on top (fast-path solves 6.9k → 41.9k while b&b stays
put). So 12 hops (378s) is barely worse than 8 (354s) — long routes are **not**
exponentially worse, but they all carry the same ~264s front-loaded b&b tax. This
is the mechanism behind the one example that started the study.

## Finding 5 — big-hold real gap is LARGE, and the b&b doesn't even finish (Wave 2a)

The seed-vs-exact gap on the 6,504 distinct big-hold b&b solves:

| | small ship (16t, Wave 1) | big hold (720t, 5M) |
|--|--|--|
| mean gap | 2.1% | **10.8%** |
| median gap | 0.3% | 8.6% |
| max gap | 11% | **80%** |
| nodes median | 44 | **~100,293 (the cap)** |

Two things at once, and they flip my big-hold prediction:

1. **The seed is genuinely poor on big holds** (mean 10.8% under the search result,
   worst 80% — seed 1.86M vs exact 9.38M on a 3-commodity mix). So we can NOT just
   use the seed raw on big holds; it would lose real profit and mis-rank candidates.
2. **The b&b hits the 100,000-node safety cap** (median ~100,293) and returns
   best-effort. The branching factor is the hold size (the search loops over
   `range(max_quantity, -1, -1)`, up to 720 branches per item), so cost explodes
   with capacity while small holds stay cheap and complete. **So on exactly the
   expensive solves, the "exact" answer is not exact — it is best-within-100k-nodes.**
   We pay ~264s for an answer that is already approximate.

The gap shrinks as the running budget grows mid-route (5M-bucket mean 14.6%,
~15M-bucket 5–8%, ~37M ~3%), confirming it is the poor early layers that carry it.

## Synthesis so far

- The slow path fires in the early/poor layers (Tromador's read — confirmed).
- But on big holds the *gap there is large* (~11%), so exactness is recovering real
  profit — it is NOT doing nothing. The seed alone is too weak for big holds.
- Yet the full search is both *too expensive* (264s) and *not completing* (node cap).
- The other engines' answer — optimistic during search, exact b&b only on the few
  finalists (the via run did 11 b&b vs 6,677) — got within ~6% at the route level
  for ~4× less wall. That ~6% route-level cost is smaller than the ~11% per-solve
  gap because correction recovers some and seed-ranking is partly order-preserving.

So the live levers are NOT "kill the slow packer" (seed too weak). They are:
  (a) **cap the search far lower** — if the b&b finds near-optimal early and burns
      the rest of 100k nodes proving it, a low cap keeps the profit cheaply
      (testing now, Wave 3a); and/or
  (b) **move fixed-terminal onto the optimistic backbone** like the other engines —
      a router change, needs a clean A/B (a build, for Tromador to approve).

## Finding 6 — the cheap fix works: cap the search far lower (Wave 3a)

Node-cap sweep on the worst shape (h8, 720t, 5M, sol → achenar):

| node cap | wall | cargo time | b&b solves | route profit |
|----------|------|-----------|-----------|--------------|
| 500 | **92s** | 3.6s | 7,640 | 105,181,521 |
| 2,000 | 95s | 7.3s | 7,376 | 105,181,521 |
| 10,000 | 116s | 27s | 7,153 | 105,181,521 |
| 50,000 | 222s | 133s | 6,862 | 105,181,521 |
| 100,000 (current) | 354s | 264s | 6,677 | 105,181,521 |

**Route profit is identical to the credit at every cap, while wall collapses
354s → 92s and cargo time 264s → 3.6s (73×).** The b&b finds the optimum early and
spends the remaining ~99.5k nodes per solve *proving* it. Cap at 500 → same route,
~4× faster wall, and the shape is fetch-bound again (cargo no longer the
bottleneck). This is the cheapest possible fix: one constant, no engine change.

Detail worth noting: lower caps run *more* b&b solves (7,640 vs 6,677) because a
weaker capped incumbent prunes fewer candidates caller-side — yet each is so much
cheaper the net is overwhelmingly positive, and the winner is unchanged.

Generality is the only open risk (this is one shape). Wave 3b checks cap-500
across hop counts, the tightest credits (500k), and a different endpoint.

## Finding 7 — cap-500 is route-exact across the matrix (Wave 3b)

cap-500 vs default (100k), route profit:

| shape | default profit | cap-500 profit | wall default → cap-500 |
|-------|---------------|----------------|------------------------|
| h4 5M | 42,869,237 | 42,869,237 ✓ | 307s → 50s |
| h6 5M | 74,025,379 | 74,025,379 ✓ | 338s → 78s |
| h10 5M | 136,337,663 | 136,337,663 ✓ | 366s → 106s |
| h12 5M | 167,493,805 | 167,493,805 ✓ | 378s → 119s |
| h8 500k (tightest) | 105,181,521 | 105,181,521 ✓ | 387s → 99s |
| sol→lave h6 | 72,242,229 | 72,242,229 ✓ | 336s → 77s |

Identical profit to the credit across hop counts 4–12, the tightest credits, and
two endpoints — for 3.5–6× less wall. At 500k credits cap-500 ran *more* b&b solves
(11,938 vs 8,784) and still finished in 99s vs 387s.

## Finding 8 — the nuance: cap-500 is route-exact, not per-solve-exact

The cap-500 dumps recover a *smaller* per-solve gap over the seed (mean 2.98%) than
the full cap-100k search did (10.8%). So cap-500 leaves per-solve optimality on the
table for the average candidate — yet route profit matched everywhere. Mechanism:
the route-*winning* solves converge within ~500 nodes; the harder mixes cap-500
under-optimises are mostly *losing* candidates that never affect the winner (the
binding early hops buy few commodities; the expensive deep-search mixes are
marginal). So "cap-500 = route-exact" is **empirical across six shapes, not a
guarantee.** This argues for an adaptive no-improvement early-stop (let a still-
improving winning solve finish; cut only the proven-optimal plateau grind) over a
blunt hard cap — same win, less risk. The hard-cap data proves the grind is
wasteful; the early-stop is the principled form of the fix.

## Finding 9 — the cap floor: cap-25 is still route-exact (Wave 3c)

h8 5M sol → achenar, cap below 500:

| node cap | route profit | wall |
|----------|-------------|------|
| 25 | 105,181,521 ✓ | 92s |
| 50 | 105,181,521 ✓ | 91s |
| 100 | 105,181,521 ✓ | 96s |
| 200 | 105,181,521 ✓ | 96s |
| 350 | 105,181,521 ✓ | 94s |

Exact route even at **cap-25** — the winning cargo solves converge in under 25
nodes. The full search's 100,000 cap was oversized by ~4,000× for the route's sake.
Wall is flat ~91–96s across caps 25–500 (the shape is fetch-bound once the cargo
grind is gone). The grind is overwhelmingly on *losing* candidates the search can't
prune fast but that never win.

## Finding 10 — a blanket hard cap is NOT perfectly safe (Wave 4, open engine)

Open-destination (`--to` omitted) big-hold shapes, default vs cap-2000:

| open shape | default profit | cap-2000 profit | wall | cargo |
|-----------|---------------|-----------------|------|-------|
| h8 5M | 107,276,102 | 106,942,475 (**−0.31%**) | 66s → 62s | 6.5s → 2.1s |
| h8 500k | 105,385,687 | 105,385,687 (✓) | 61s → 61s | 1.9s → 1.9s |

The open engine runs optimistic expansion + b&b only in **finalist correction**
(200 b&b solves, all in correction). Capping that correction nudged which finalist
won, costing 0.31% on the 5M shape. Two things follow: (1) a *blanket* hard cap is
not exact — it has a small open-engine cost; (2) the open engine **did not have the
perf problem** (60–66s, cargo only 6.5s), so the cap is both unneeded and slightly
lossy there. The cap fix belongs on the fixed-terminal *expansion* search, where it
is needed and route-exact — not blanket on the correction pass. This is the concrete
case for preferring the adaptive no-improvement early-stop, which would not cut a
still-improving finalist.

## Finding 11 — does the search earn its keep over the bare seed? (mostly yes, by design)

Cross-tab of the big-hold cap-100k solves by whether the search beat the seed:

| | share | nodes (median) | nodes (max) |
|--|------|----------------|-------------|
| seed already optimal (gap=0) | 22.6% | **1** | 97,538 |
| search beat the seed (gap>0) | 77.4% | ~100,323 (the cap) | 100,718 |

When greedy is already the answer, the admissible bound proves it and the search
**exits at 1 node** (0% of these reach the cap). So the work above 1 node is spent
almost entirely where greedy actually loses — the ~25 nodes to *find* a better mix
are paid only on solves that have one (~11% gain). The waste is the
*proving-optimality tail* (≈25 → 100k) on the winning solves, not effort frittered
on lost causes. A small tail of no-gain solves do grind tens of thousands of nodes
(bound too loose to confirm fast) — rare (median 1), and exactly what a
no-improvement early-stop removes. This is the sharpest argument for the early-stop:
it leaves the 1-node skips alone and cuts only the proving tail.

---

# Synthesis and recommendation

## Root cause

The cargo b&b node cap (`_SEARCH_NODE_LIMIT = 100_000`) is wildly oversized. On
big-hold tight-credit hops the search **finds the route-optimal cargo within a
handful of nodes, then spends ~100k nodes per solve proving optimality (and chasing
exact values on losing candidates that never win)**. The branching factor is the
hold size — the search loops `range(max_quantity, -1, -1)`, up to 720 branches per
item — so the grind explodes with capacity and saturates the cap on big holds while
small holds finish naturally in tens of nodes. That grind is ~99% of the 264s cargo
cost on the worst shape, and it buys nothing: route profit is identical from cap
25 to cap 100,000 across every shape tested.

A second fact reframes the "exactness" framing: at cap 100k the big-hold solves
**hit the cap and bail with best-effort** (dump nodes median ~100,293). So the
current fixed-terminal engine is *not actually exact* on these shapes — it already
returns a capped best. Lowering the cap does not surrender a guarantee we hold.

## The fix (for your approval — not applied)

Two forms, both packer-level, both keeping the exact fixed-terminal engine. The
no-improvement early-stop (2) is now the **recommended** form — Finding 10 showed a
blanket hard cap costs 0.31% on the open engine's correction pass.

1. **Immediate, low-risk — but TARGETED:** lower the node cap, applied to the
   fixed-terminal *expansion* search only (not the open engine's finalist
   correction). There it is route-exact across hop counts 4–12, credits 500k–5M, and
   two endpoints; ~3.5–6× faster wall on the slow shapes (worst: 354s → ~92s). A
   **no-op for small ships** (they finish under ~500 nodes naturally). ~2,000 carries
   ~80× margin over the cap-25 that already sufficed on the worst shape. A *blanket*
   cap is simpler but slightly lossy on the open correction (Finding 10), so scope it.

2. **Principled, recommended:** replace the hard cap with a **no-improvement
   early-stop** — bail after K nodes with no improvement to the incumbent. This lets
   a genuinely still-improving solve finish (so it does not cost the open engine its
   0.31%, and removes the empirical-not-proven risk that some unseen winning mix needs
   a deep search) while cutting the proven-optimal plateau grind. Safe everywhere.
   The hard-cap data proves the grind is wasteful; this is its safe, adaptive form.
   Needs a small change + wider-matrix validation.

## Confidence and caveats

- **Strong:** the grind is wasteful and route profit is cap-invariant — six diverse
  shapes, plus a floor to cap-25, all identical to the credit.
- **Calibrated:** cap-N is *route-exact* on everything tested, not *per-solve-exact*
  (cap-500 recovers mean 2.98% over seed vs the full search's 10.8%). It works
  because winning solves converge fast and the under-optimised mixes are losers.
  Not a proof for every possible market — hence the margin (2,000) and the
  early-stop as the robust form.
- **Open engine tested (Finding 10):** the cap matters little for open-shape *perf*
  (cargo was only 6.5s) and a blanket cap is slightly *lossy* there (0.31%) — hence
  "target the fixed-terminal search" or "use the early-stop." The galaxy-wide
  unanchored shapes are still untested (they are confirmation-gated and slow), but
  they share the open engine's optimistic+correction structure, so the same reading
  should hold; a confirming run is owed before any blanket change.

## Verdict on the two-engine question

The performance problem is a **few-line packer change, not an architecture rewrite.**
On the same h8/5M shape, all three approaches:

| approach | wall | profit |
|----------|------|--------|
| exact (cap 100k) — current | 354s | 105.18M |
| **cap fix** | **~92s** | **105.18M (exact)** |
| optimistic engine (`--via lai`, same conditions, 2026-06-16 baseline) | 129s | 98.64M (−6%) |

The cap fix **dominates** — faster than the optimistic engine *and* exact, where the
optimistic route is both slower (here) and ~6% lossy. So consolidating onto the
optimistic backbone is **not warranted for performance**; if anything the data says
keep the exact fixed-terminal engine and just stop its cargo grind. The
"long routes are effectively unanchored in the slack region" geometry remains true
and architecturally interesting, but it is not a performance lever once the grind
is gone.

## Tromador's thesis, revisited

He was right that the slow path fires in the early/poor/slack region and is "tuned
badly" — but the mechanism is subtler than "exactness doesn't pay." Exactness *does*
pay (~11% per solve on big holds; the seed is genuinely weak there). The waste is
that the search spends ~99% of its effort **proving** an optimum it already found.
The fix is not "drop exactness" — it is "stop grinding once you've found it."

## Open items for the next session

- Decide cap-2,000 vs the no-improvement early-stop (recommend the early-stop).
- Validate across the open/unanchored shapes and a couple more endpoints/holds.
- Revert is done: the temporary `cargo.py` telemetry + node-limit env hook are
  removed; the recommendation is yours to apply.

---

## Outcome (Slice 28)

Both forms shipped: the no-improvement early-stop (K=500) **and** the lowered
fuse (100,000 → 2,000), keeping the exact fixed-terminal engine. Verified
route-exact on the headline and across hops 4–12 / credits 500k–5M / two
endpoints; the open shape is within 0.31%. Diagnostics were also gated behind
`-ww`. The probe scripts and per-wave logs this study was built on were deleted
at slice close — this findings record is what is kept. See
`twenty_eighth_slice_completion_report.md`.
