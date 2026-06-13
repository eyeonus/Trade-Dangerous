# Unanchored `--loop` — Investigation and Decision

*Recorded 2026-06-13.*

**Decision (made): the galaxy-wide `--loop` — `--loop` with no `--from` — is
not supported.** The anchored loop (`--from` named) is built and ships. This is
a settled decision, not a parked or deferred task. It is written down so that if
it is ever reopened, the work below is not repeated from zero. Reopening it
would be a future slice.

This document stands alone: the findings, the numbers, and the reasoning are all
here. The throwaway probe scripts that produced the numbers were deleted at the
end of the slice (probes are not committed); their results are reproduced below.

---

## What the unanchored loop is, and why it is hard

A loop route trades out for N hops and ends back at its starting station. With
`--from` named, that is cheap and honest — it is a fixed-terminal multi-hop
search whose terminal is the origin, and the existing engine handles it (that is
the anchored loop, which shipped).

With `--from` omitted, the planner must pick the best loop over *every eligible
origin in the galaxy*. Legacy did this by brute force: it preloaded the whole
galaxy into memory and tried every suitable station. That preload-first pattern
is exactly what this rewrite exists to remove, so the brute-force answer is off
the table. The question was whether the same behaviour could be reproduced
within the new architecture's bounds.

---

## The hard constraint

The multi-hop search is a beam search with both widths fixed at 50
(`_MULTIHOP_EXPANSION_WIDTH`, `_MULTIHOP_FRONTIER_WIDTH`). That number is a
recorded decision backed by the only end-to-end value-versus-time sweep to date
(`beam_width_analysis.md`). **The widths stay at 50, including the effective
anchor count.** No design may keep extra routes alive by widening the frontier
or by reserving per-root slots that push the carried-forward set past 50. Any
unanchored-loop design had to live inside that 50.

---

## P1 — seed fidelity (the original design failed)

The original Part B sketch was: seed candidate loop origins from the unanchored
one-hop candidate set, rank them by a cheap "loop-fitness" score, and keep the
top K. P1 tested whether that ranking actually contains the best loops.

**Setup.** The seed universe is the distinct *source* stations of
`fetch_unanchored_trade_candidates` — the same bounded, galaxy-wide best-pairs
fetch the unanchored multi-hop already uses. For a representative light shuttle
(capacity 200, `--ly-per` 20, `--jumps-per` 2) that is **~85–90 origins** from
~320 candidate pairs, and it is stable: removing the age cap or widening range
barely moves it, because the fetch is bounded per-commodity (cap 50 accepted
pairs) and stops walking commodities once the profit bound can no longer beat the
best trade seen. Ground truth: run an honest anchored loop from every origin and
rank by the real result.

**Finding 1 — the inbound half cannot be measured.** A loop origin must both buy
well outbound *and* sell well on return. But **83 of 85 origins never appear as a
*destination*** in the candidate pair set — the unanchored fetch is "best buys
and where to sell them", so it is almost all sources, no sinks. The "sells well
on return" signal is simply absent. Proxies that used it (`min(out,in)`,
`out+in`) collapsed to noise — they produced the identical ranking to the
outbound-only proxy in every row.

**Finding 2 — the outbound half is a loose predictor.** Best single-hop outbound
profit does not track loop quality:

| origin | best single trade (`out`) | honest loop (hops 3) | note |
|---|---|---|---|
| Vodyanes / JBB-6KT | 124.3M | 14.1M | one fat trade, weak return — **over-rated** |
| Col 285 / TNJ-84X | 103.8M | **112.1M** | the dominant winner, caught at out-rank 4 |
| Lhou Mans / XHT-6XK | 9.9M | 14.4M | the **#2 loop**, buried at out-rank **61** |
| Muchihiks / Q4Q-W0H | 0.1M | 3.8M | **35×** under-rated |

To keep the true top-10 loops, the cheapest proxy needed K = 61 (others 79) —
all past the width of 50. The dominant winner was caught cheaply, but genuinely
strong *multi-hop* origins with mediocre *single-hop* trades were buried.

**Why this was always going to happen.** `beam_width_analysis.md`, finding 3,
already records it: *"a station at rank 150 with a mediocre first trade can lead
the best six-hop chain ... the inherent blindness of any beam search."* A cheap
one-hop score cannot see a deep loop. So no proxy and no K rescues the
rank-and-trim design within a width of 50. **P1 failed the original seeding
design.**

---

## Alternatives considered (all within width 50)

- **A — sequential per-origin loops.** Run the audited anchored-loop engine once
  per admitted origin, each with its own width-50 beam, and keep the best. Full
  coverage (no origin starves another), correctness exact per origin, honours the
  width by spending **time**, not frontier. Chosen for cost measurement (P2).
- **B — proxy-trim to 50 + one shared beam** (the original design). Honours the
  width trivially but **already failed P1** — it drops top-tier loops.
- **C — batched shared beam** (⌈pool/50⌉ passes of ≤50 seeds). Cheaper than A,
  but origins within a batch still starve each other on first-hop score, and
  batch composition becomes a new source of route variation. Inferior to A.
- **D — a smarter cheap trim.** Rejected: the beam-width analysis says no local
  measure predicts deep winners, so any heuristic trim fights a documented dead
  end.

---

## P2 — sequential-origin cost (Alt A)

Faithful measurement of Alt A, both beams at 50, no early termination: each
origin runs through the audited engine directly, with one bubble cache shared
across the fetch and every per-origin run.

| depth | origins (closing) | fetch | per-origin sweep | **total** | per-origin median |
|---|---|---|---|---|---|
| **hops 2** (default `--loop`) | 89 (53) | 27.5s | 17.7s | **45.2s** | 240ms |
| **hops 4** | 89 (56) | 22.6s | 476.4s | **499s (8.3 min)** | 7.1s |
| hops 6 | — | — | — | **~3.6 h (projected)** | — |

**Mechanism.** Total cost ≈ (origins that close) × (per-origin loop cost). The
origin count (~55 closers) is the flat Alt A tax; the per-origin cost grows
**~5.2× per added hop**, which is inherent beam-at-depth, not an Alt A artefact.
Multiplied, depth is fatal past hops 3 (hops 3 ≈ 2 min; hops 5 ≈ 40 min).

Two details: origins that cannot close a loop **fast-fail in ~0.3ms**, so dead
origins cost nothing — the bill is entirely the closers. And the shared bubble
cache genuinely reuses (99 systems after the fetch → 581 at hops 2 / 1493 at
hops 4, growth decelerating), but that is the cheap part; the expensive
per-origin beam expansion and cargo fit are rebuilt per call and are not shared.

---

## The decision and its basis

The common case is cheap (`hops 2`, the default, is 45s on a shape that already
sits behind a "this may take minutes" confirmation prompt, and touches no other
command's runtime). But the cost explodes with depth, and the two honest ways to
contain it were both judged not worth taking now:

- **Cap the depth** (support unanchored `--loop` only to ~hops 3) — reduces the
  contract and still leaves a sharp cliff just past the cap.
- **Engineer a cross-origin cache** to share the per-origin SQL work — real
  production engineering, with an uncertain ceiling (the CPU-bound beam work may
  not be shareable).

The call (Tromador, to be discussed with eyeonus) was to **not support the
unanchored loop**. The anchored loop ships; `--loop` without `--from` is rejected
with a clear message pointing the user at `--from`.

---

## If this is reopened — the homework

- **The seed universe is the ~90 candidate sources**, bounded by the fetch's
  per-commodity cap and profit-ordered early stop. It is *not* short of good
  origins — the buried winners (e.g. Lhou Mans) were *in* the pool; the trim
  dropped them. So the target is full coverage of that pool, not a bigger fetch.
  Legacy's every-station brute force stays forbidden.
- **The correctness model that works is Alt A** — exact per admitted origin,
  identical to the audited anchored loop, run once per origin. Pool completeness
  (does the bounded fetch contain the galaxy's single best loop origin?) is a
  separate, accepted boundary — the same one the whole unanchored family lives
  with.
- **The one lever not yet pulled:** measure the per-origin **SQL-versus-CPU
  split** at depth. If the deep cost is dominated by origin-independent SQL
  re-fetch, a shared cross-origin qualify/candidate cache could cut it enough to
  lift the depth cap. If it is CPU beam work, it cannot, and cap-or-prohibit
  stands.
- **Closed doors:** the proxy-rank-and-trim seeding (P1) and any frontier
  widening or per-root preservation (the beam-width decision). A reopen starts
  from Alt A and the cost question, not from these.
