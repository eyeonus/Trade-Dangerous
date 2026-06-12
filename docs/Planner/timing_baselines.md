# Planner Timing Baselines

Recorded wall-clock and phase-split figures for the multi-hop route shapes,
kept so future performance work has something honest to compare against.

Routes and profits drift as the database refreshes — treat the chosen
stations and credit figures as indicative only. The stable signal is the
**relationship between data volume and time**: candidate rows fetched, the
phase split, and how both scale with hops and jump range.

## Conditions

- **Date:** 2026-06-11
- **Machine:** Zen (i9-13900K, 64 GB, WSL2 Ubuntu, SQLite on NVMe)
- **Code state:** post fetch-path sweep, with the open-anchor expansion
  phase timers newly wired (this is the first run set where the open
  shapes report a real phase split)
- **Common arguments:** `--capacity 720 --credits 200000000 --ly-per 30`
- Jump range column: `1` = omitted `--jumps-per` (defaults to 1 at this
  `--ly-per`), `2` = `--jumps 2` as typed (accepted for `--jumps-per`)

## Headline table

| # | Shape | Jumps | Wall | Planner | Fetch | Cargo | Jump | Cand. rows | Pairs | Route profit |
|---|-------|-------|------|---------|-------|-------|------|-----------|-------|--------------|
| 1 | `--from sol --hops 3` | 1 | 15.3s | 14.4s | 12.3s | 1.7s | 7ms | 855,247 | 97,782 | 163,058,562 |
| 2 | `--from sol --hops 3` | 2 | 63.0s | 61.9s | 50.7s | 8.5s | 727ms | 3,400,663 | 387,397 | 163,248,642 |
| 3 | `--to lave --hops 3` | 1 | 4.7s | 3.8s | 3.1s | 545ms | 6ms | 276,438 | 27,819 | 21,183,840 |
| 4 | `--to lave --hops 3` | 2 | 22.6s | 21.6s | 17.9s | 2.6s | 471ms | 1,425,683 | 147,651 | 102,440,568 |
| 5 | `--from sol --hops 6` | 1 | 33.0s | 32.0s | 26.9s | 4.2s | 16ms | 1,834,125 | 212,158 | 226,749,996 |
| 6 | `--from sol --hops 6` | 2 | 139.3s | 138.0s | 114.8s | 16.6s | 1.7s | 7,226,858 | 824,033 | 298,178,370 |
| 7 | `--from sol --to lave --hops 6` | 1 | 10.0s | 8.9s | 7.3s | 687ms | 12ms | 359,594 | 46,108 | 76,410,414 |
| 8 | `--from sol --to lave --hops 6` | 2 | 125.4s | 123.9s | 100.1s | 5.9s | 11.1s | 3,974,953 | 458,448 | 193,186,530 |

"Planner" is the diagnostics `Total`; "Fetch/Cargo/Jump" are the
`Expansion phases` line; "Wall" is `time`'s `real`.

## What the numbers establish

**Fetch throughput is flat.** Rows fetched per second of fetch time, per
run: 69.6k / 67.0k / 88.4k / 79.6k / 68.2k / 63.0k / 49.0k / 39.7k.
The open shapes cluster at 63–88k rows/s regardless of hops or jump
range — time scales with rows examined, with no superlinear blow-up.
The fixed-terminal shape (runs 7–8) pays more per *returned* row,
consistent with its extra SQL-side predicates (destination envelope,
fixed-side price bounds) rejecting more rows per row kept.

**Jump range multiplies; hops add.** `--jumps 2` grows every per-hop
search bubble — observed ~4–5× the candidate rows per expansion call
(the r³ geometric ceiling is 8×; real star/market density gives less).
Extra hops just append layers of capped size (frontier 50), each at
near-constant cost: per-layer time at 1 jump is ~6s, at 2 jumps ~27s,
flat across layers 2–5 (runs 5–6). This is why run 2 (3 hops, 2 jumps,
3.4M rows, 62s) costs more than run 5 (6 hops, 1 jump, 1.8M rows,
32s): twice the rows, twice the time.

**The phase split accounts for 97–98% of expansion time** in every run.
There is no unattributed Python sink hiding behind the timers.

**The dominant cost is the open-side candidate fetch**, in every shape,
at every depth — the recorded residual from the fetch-path sweep. The
fetch walks the reachable stations' market rows to evaluate the
narrowing EXISTS probes; `--jumps 2` hands it 4–5× the rows to walk.
Any future attack on multi-jump wall-clock starts at that query shape.

## Secondary observations (recorded, not scheduled)

1. **Jump-path planning scales hard with range on the fixed-terminal
   shape:** 12ms at 1 jump → 11.1s at 2 jumps (run 7 vs 8). Survivor
   paths through a 2-jump bubble cost ~1000× more each. ~9% of that
   run; an edge to watch if jump ranges grow.
2. **The open-anchor engine solves cargo unpruned** (e.g. run 6: 824k
   solves, 16.6s, 0 pruned), where the fixed-terminal engine prunes
   (run 8: 442,546 pruned). Worth ~10% of an open run at best; fetch
   dwarfs it. *(Closed the same day — run set 2 below records the
   prune landing and its verification.)*
3. **Memo hit rate drops as jump range grows** (run 3: 60/68 hit/miss →
   run 4: 38/90) — wider bubbles make the frontier more spatially
   diverse, and each miss costs more. A contributor to the multiplier,
   not the driver.

## Per-run diagnostics (verbatim)

### 1 — `--from sol --hops 3` (1 jump)

```text
Route: Sol/Daedalus -> LHS 449/W0L-W2W, profit 163058562 cr
Total: 14364ms (resolution 0ms, station-filter 2ms, search 14354ms)
Expansion: 163 calls, memo 102/61 hit/miss, 855247 candidate rows, 97782 pairs, 97782 cargo calls, 6725 children, 14259ms
Expansion phases: fetch 12292ms, cargo 1689ms, jump 7ms
Cargo: 97785 fast-path, 0 branch-and-bound, 0 pruned, 1664ms
Correction: 2500 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
Layer 1: 63 in, 63 calls, 1800 children, kept 50 (2854ms)
Layer 2: 50 in, 50 calls, 2425 children, kept 50 (6441ms)
real 0m15.285s
```

### 2 — `--from sol --hops 3 --jumps 2`

```text
Route: Sol/Daedalus -> LHS 449/W0L-W2W, profit 163248642 cr
Total: 61913ms (resolution 0ms, station-filter 2ms, search 61900ms)
Expansion: 163 calls, memo 99/64 hit/miss, 3400663 candidate rows, 387397 pairs, 387397 cargo calls, 6700 children, 61320ms
Expansion phases: fetch 50720ms, cargo 8486ms, jump 727ms
Cargo: 387400 fast-path, 0 branch-and-bound, 0 pruned, 8392ms
Correction: 2500 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
Layer 1: 63 in, 63 calls, 1800 children, kept 50 (12375ms)
Layer 2: 50 in, 50 calls, 2400 children, kept 50 (26880ms)
real 1m3.028s
```

### 3 — `--to lave --hops 3` (1 jump)

```text
Route: Crucis Sector HC-U b3-5/KLG-45W -> Lave/Lave Station, profit 21183840 cr
Total: 3785ms (resolution 0ms, station-filter 2ms, search 3776ms)
Expansion: 128 calls, memo 60/68 hit/miss, 276438 candidate rows, 27819 pairs, 27819 cargo calls, 5150 children, 3754ms
Expansion phases: fetch 3127ms, cargo 545ms, jump 6ms
Cargo: 27822 fast-path, 0 branch-and-bound, 0 pruned, 538ms
Correction: 2450 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
Layer 1: 28 in, 28 calls, 200 children, kept 50 (167ms)
Layer 2: 50 in, 50 calls, 2500 children, kept 50 (1911ms)
real 0m4.673s
```

### 4 — `--to lave --hops 3 --jumps 2`

```text
Route: Faisel C/Q7Z-5TX -> Lave/Lave Station, profit 102440568 cr
Total: 21596ms (resolution 0ms, station-filter 2ms, search 21582ms)
Expansion: 128 calls, memo 38/90 hit/miss, 1425683 candidate rows, 147651 pairs, 147651 cargo calls, 5050 children, 21429ms
Expansion phases: fetch 17908ms, cargo 2593ms, jump 471ms
Cargo: 147654 fast-path, 0 branch-and-bound, 0 pruned, 2558ms
Correction: 2400 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
Layer 1: 28 in, 28 calls, 200 children, kept 50 (559ms)
Layer 2: 50 in, 50 calls, 2450 children, kept 50 (9511ms)
real 0m22.597s
```

### 5 — `--from sol --hops 6` (1 jump)

```text
Route: Sol/Daedalus -> LHS 449/W0L-W2W, profit 226749996 cr
Total: 31975ms (resolution 0ms, station-filter 2ms, search 31958ms)
Expansion: 313 calls, memo 249/64 hit/miss, 1834125 candidate rows, 212158 pairs, 212158 cargo calls, 14177 children, 31732ms
Expansion phases: fetch 26882ms, cargo 4241ms, jump 16ms
Cargo: 212164 fast-path, 0 branch-and-bound, 0 pruned, 4189ms
Correction: 2477 finalists, 1 attempted, 1 corrected, 6 cargo calls (6 fast-path, 0 b&b), 1ms
Layer 1: 63 in, 63 calls, 1800 children, kept 50 (2841ms)
Layer 2: 50 in, 50 calls, 2425 children, kept 50 (6281ms)
Layer 3: 50 in, 50 calls, 2500 children, kept 50 (6382ms)
Layer 4: 50 in, 50 calls, 2475 children, kept 50 (5723ms)
Layer 5: 50 in, 50 calls, 2500 children, kept 50 (6384ms)
real 0m32.969s
```

### 6 — `--from sol --hops 6 --jumps 2`

```text
Route: Sol/Daedalus -> LHS 449/W0L-W2W, profit 298178370 cr
Total: 137961ms (resolution 0ms, station-filter 2ms, search 137931ms)
Expansion: 313 calls, memo 190/123 hit/miss, 7226858 candidate rows, 824033 pairs, 824033 cargo calls, 14150 children, 136737ms
Expansion phases: fetch 114755ms, cargo 16598ms, jump 1691ms
Cargo: 824039 fast-path, 0 branch-and-bound, 0 pruned, 16400ms
Correction: 2500 finalists, 1 attempted, 1 corrected, 6 cargo calls (6 fast-path, 0 b&b), 1ms
Layer 1: 63 in, 63 calls, 1800 children, kept 50 (12070ms)
Layer 2: 50 in, 50 calls, 2400 children, kept 50 (26281ms)
Layer 3: 50 in, 50 calls, 2500 children, kept 50 (27636ms)
Layer 4: 50 in, 50 calls, 2500 children, kept 50 (27540ms)
Layer 5: 50 in, 50 calls, 2450 children, kept 50 (25734ms)
real 2m19.322s
```

### 7 — `--from sol --to lave --hops 6` (1 jump)

```text
Route: Sol/Daedalus -> Lave/Lave Station, profit 76410414 cr
Total: 8946ms (resolution 0ms, station-filter 3ms, search 8927ms)
Expansion: 253 calls, memo 93/160 hit/miss, 359594 candidate rows, 46108 pairs, 46108 cargo calls, 6444 children, 8199ms
Expansion phases: fetch 7340ms, cargo 687ms, jump 12ms
Cargo: 7701 fast-path, 0 branch-and-bound, 38461 pruned, 679ms
Layer 1: 63 in, 63 calls, 1800 children, kept 50 (2847ms)
Layer 2: 50 in, 50 calls, 2414 children, kept 50 (3853ms)
Layer 3: 50 in, 50 calls, 1258 children, kept 50 (602ms)
Layer 4: 50 in, 50 calls, 710 children, kept 40 (616ms)
Layer 5: 40 in, 40 calls, 262 children, kept 16 (318ms)
Final hop: 16 attempted, 16 reach destination, 222 market candidates, 16 viable, 691ms
real 0m10.013s
```

### 8 — `--from sol --to lave --hops 6 --jumps 2`

```text
Route: Sol/Daedalus -> Lave/Lave Station, profit 193186530 cr
Total: 123862ms (resolution 0ms, station-filter 2ms, search 123836ms)
Expansion: 263 calls, memo 116/147 hit/miss, 3974953 candidate rows, 458448 pairs, 458448 cargo calls, 10772 children, 119409ms
Expansion phases: fetch 100079ms, cargo 5904ms, jump 11119ms
Cargo: 15989 fast-path, 0 branch-and-bound, 442546 pruned, 5823ms
Layer 1: 63 in, 63 calls, 1800 children, kept 50 (12111ms)
Layer 2: 50 in, 50 calls, 2400 children, kept 50 (39214ms)
Layer 3: 50 in, 50 calls, 2500 children, kept 50 (30085ms)
Layer 4: 50 in, 50 calls, 2462 children, kept 50 (27264ms)
Layer 5: 50 in, 50 calls, 1610 children, kept 50 (11302ms)
Final hop: 50 attempted, 30 reach destination, 625 market candidates, 28 viable, 3860ms
real 2m5.409s
```

---

# Run set 2 — prune verification and `--fc N` twins (2026-06-11, post-prune)

Same day, same database state — verified, not assumed: the re-runs'
volume counters match run set 1 to the digit. Code state: run set 1
plus the open-anchor cargo prune (`f754e0c2`) — pairs solve best-first
and skip the branch-and-bound when their admissible ceiling cannot beat
the worst kept child.

## Prune verification — open filters, re-runs of runs 2 and 6

Routes, profits, and every volume counter (rows / pairs / children /
memo) identical to run set 1; only the work split moved. Exactness
holds.

| Run | Wall | Planner | Fetch | Cargo | Jump | Pruned | Route profit |
|---|---|---|---|---|---|---|---|
| 2′ `--from sol --hops 3 --jumps 2` | 66.1s | 61.4s | 52.6s | 5.2s | 768ms | 376,973 / 387,400 (97.3%) | 163,248,642 — identical |
| 6′ `--from sol --hops 6 --jumps 2` | 139.1s | 137.5s | 119.0s | 10.7s | 1.7s | 801,822 / 824,039 (97.3%) | 298,178,370 — identical |

Cargo phase fell 39% / 36%; net wall-clock flat, because the saving
(3–6s) is the same order as run-to-run fetch variance on these shapes.

## `--fc N` twins

Same eight commands as run set 1 with `--fc N` appended.

| # | Shape | Jumps | Wall | Planner | Fetch | Cargo | Jump | Cand. rows | Pairs | Pruned | Route profit |
|---|-------|-------|------|---------|-------|-------|------|-----------|-------|--------|--------------|
| F1 | `--from sol --hops 3` | 1 | 15.1s | 14.1s | 12.1s | 1.4s | 8ms | 855,001 | 96,020 | 90.7% | 33,105,036 |
| F2 | `--from sol --hops 3` | 2 | 61.0s | 59.9s | 51.3s | 4.9s | 705ms | 3,567,035 | 372,703 | 97.2% | 69,515,420 |
| F3 | `--to lave --hops 3` | 1 | 4.9s | 3.9s | 3.2s | 553ms | 7ms | 277,296 | 27,590 | 75.7% | 18,582,480 |
| F4 | `--to lave --hops 3` | 2 | 23.3s | 22.3s | 18.9s | 2.1s | 486ms | 1,500,244 | 152,099 | 94.1% | 25,972,045 |
| F5 | `--from sol --hops 6` | 1 | 34.0s | 32.9s | 28.3s | 3.5s | 17ms | 2,034,917 | 207,383 | 90.9% | 61,157,520 |
| F6 | `--from sol --hops 6` | 2 | 139.5s | 138.1s | 118.2s | 11.7s | 913ms | 8,256,208 | 772,753 | 97.2% | 122,108,434 |
| F7 | `--from sol --to lave --hops 6` | 1 | 9.7s | 8.5s | 7.6s | 618ms | 12ms | 382,856 | 47,231 | 83.5% | 41,325,120 |
| F8 | `--from sol --to lave --hops 6` | 2 | 111.9s | 110.5s | 90.2s | 7.0s | 7.6s | 4,399,501 | 453,138 | 96.6% | 92,674,980 |

## What run set 2 establishes

**`--fc N` changes the answer, not the bill.** Against the open-filter
twins, candidate-row volumes are equal or slightly *higher* under
`--fc N` (e.g. F5: 2,034,917 vs 1,834,125; F8: 4,399,501 vs 3,974,953)
and wall-clocks land within run variance. Carriers dominate the
*winners* (profits collapse, 163M → 33M on the h3 shape) but not the
*work*: the cost is in-range market-row volume, and the frontier simply
settles on different, equally dense non-carrier anchors. Station
filters are not a performance lever; the query shape is the only one
left.

**The prune holds under `--fc N`.** Open-anchor engine: 75.7–97.2%
of solves pruned, lowest exactly where margins compress hardest (the
thin Lave-side market, F3). Fixed-terminal engine: effectively
unchanged by the filter (83.4% → 83.5% at 1 jump, 96.5% → 96.6% at 2).
The provably-can't-win mechanism survives margin compression in this
engine; cargo cost stays minor under both filter states.

**Sol and Lave are not symmetric under `--fc N` — do not read their
difference as engine behaviour.** Lave's open side seeds 4 layer-1
nodes without carriers (28 with); Sol seeds 63 either way, its
non-carrier market density absorbing the filter. The `--to lave`
figures reflect a thin local market, not an engine trait.

**Route revisit ping-pong is expected.** The `--fc N` h6 routes shuttle
between the same station pairs (e.g. Meliae ↔ LP 274-24 four hops
running) — legitimate best-profit behaviour while revisits are allowed;
`--unique` is the (gated) option that will suppress it.

## Per-run diagnostics (verbatim)

### 2′ — `--from sol --hops 3 --jumps 2` (open filters, post-prune)

```text
Route: Sol/Daedalus -> LHS 449/W0L-W2W, profit 163248642 cr — identical to run 2
Total: 61418ms (resolution 0ms, station-filter 5ms, search 61400ms)
Expansion: 163 calls, memo 99/64 hit/miss, 3400663 candidate rows, 387397 pairs, 387397 cargo calls, 6700 children, 60920ms
Expansion phases: fetch 52634ms, cargo 5167ms, jump 768ms
Cargo: 10427 fast-path, 0 branch-and-bound, 376973 pruned, 5093ms
Correction: 2500 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
Layer 1: 63 in, 63 calls, 1800 children, kept 50 (12585ms)
Layer 2: 50 in, 50 calls, 2400 children, kept 50 (27611ms)
real 1m6.058s
```

### 6′ — `--from sol --hops 6 --jumps 2` (open filters, post-prune)

```text
Route: Sol/Daedalus -> LHS 449/W0L-W2W, profit 298178370 cr — identical to run 6
Total: 137529ms (resolution 0ms, station-filter 2ms, search 137497ms)
Expansion: 313 calls, memo 190/123 hit/miss, 7226858 candidate rows, 824033 pairs, 824033 cargo calls, 14150 children, 136330ms
Expansion phases: fetch 119011ms, cargo 10688ms, jump 1741ms
Cargo: 22217 fast-path, 0 branch-and-bound, 801822 pruned, 10530ms
Correction: 2500 finalists, 1 attempted, 1 corrected, 6 cargo calls (6 fast-path, 0 b&b), 1ms
Layer 1: 63 in, 63 calls, 1800 children, kept 50 (11824ms)
Layer 2: 50 in, 50 calls, 2400 children, kept 50 (26721ms)
Layer 3: 50 in, 50 calls, 2500 children, kept 50 (27465ms)
Layer 4: 50 in, 50 calls, 2500 children, kept 50 (28130ms)
Layer 5: 50 in, 50 calls, 2450 children, kept 50 (25080ms)
real 2m19.108s
```

### F1 — `--from sol --hops 3 --fc N`

```text
Route: Sol/Daedalus -> Struve 2398/Veroiu Gateway, profit 33105036 cr
Total: 14063ms (resolution 0ms, station-filter 2ms, search 14052ms)
Expansion: 163 calls, memo 97/66 hit/miss, 855001 candidate rows, 96020 pairs, 96020 cargo calls, 6800 children, 13966ms
Expansion phases: fetch 12132ms, cargo 1354ms, jump 8ms
Cargo: 8946 fast-path, 0 branch-and-bound, 87077 pruned, 1336ms
Correction: 2500 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
Layer 1: 63 in, 63 calls, 1800 children, kept 50 (2810ms)
Layer 2: 50 in, 50 calls, 2500 children, kept 50 (6644ms)
real 0m15.107s
```

### F2 — `--from sol --hops 3 --fc N --jumps 2`

```text
Route: Sol/Navarrete's Prospect -> Meliae/Hadfield Hub, profit 69515420 cr
Total: 59913ms (resolution 0ms, station-filter 2ms, search 59898ms)
Expansion: 163 calls, memo 88/75 hit/miss, 3567035 candidate rows, 372703 pairs, 372703 cargo calls, 6800 children, 59386ms
Expansion phases: fetch 51308ms, cargo 4900ms, jump 705ms
Cargo: 10454 fast-path, 0 branch-and-bound, 362252 pruned, 4830ms
Correction: 2500 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
Layer 1: 63 in, 63 calls, 1800 children, kept 50 (11907ms)
Layer 2: 50 in, 50 calls, 2500 children, kept 50 (28051ms)
real 1m1.004s
```

### F3 — `--to lave --hops 3 --fc N`

```text
Route: Hydrae Sector QI-T b3-3/Bernhard Horizons -> Lave/Lave Station, profit 18582480 cr
Total: 3909ms (resolution 0ms, station-filter 2ms, search 3900ms)
Expansion: 104 calls, memo 36/68 hit/miss, 277296 candidate rows, 27590 pairs, 27590 cargo calls, 5150 children, 3880ms
Expansion phases: fetch 3214ms, cargo 553ms, jump 7ms
Cargo: 6717 fast-path, 0 branch-and-bound, 20876 pruned, 547ms
Correction: 2500 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
Layer 1: 4 in, 4 calls, 150 children, kept 50 (132ms)
Layer 2: 50 in, 50 calls, 2500 children, kept 50 (2029ms)
real 0m4.857s
```

### F4 — `--to lave --hops 3 --fc N --jumps 2`

```text
Route: G 113-20/Ansari Hangar -> Lave/Lave Station, profit 25972045 cr
Total: 22250ms (resolution 0ms, station-filter 2ms, search 22236ms)
Expansion: 104 calls, memo 14/90 hit/miss, 1500244 candidate rows, 152099 pairs, 152099 cargo calls, 5150 children, 22095ms
Expansion phases: fetch 18875ms, cargo 2070ms, jump 486ms
Cargo: 8988 fast-path, 0 branch-and-bound, 143114 pruned, 2042ms
Correction: 2500 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
Layer 1: 4 in, 4 calls, 150 children, kept 50 (471ms)
Layer 2: 50 in, 50 calls, 2500 children, kept 50 (9986ms)
real 0m23.310s
```

### F5 — `--from sol --hops 6 --fc N`

```text
Route: Sol/Daedalus -> LHS 6350/Zaschka Point, profit 61157520 cr
Total: 32937ms (resolution 0ms, station-filter 2ms, search 32918ms)
Expansion: 313 calls, memo 239/74 hit/miss, 2034917 candidate rows, 207383 pairs, 207383 cargo calls, 14300 children, 32686ms
Expansion phases: fetch 28260ms, cargo 3530ms, jump 17ms
Cargo: 18808 fast-path, 0 branch-and-bound, 188581 pruned, 3491ms
Correction: 2500 finalists, 1 attempted, 1 corrected, 6 cargo calls (6 fast-path, 0 b&b), 1ms
Layer 1: 63 in, 63 calls, 1800 children, kept 50 (2777ms)
Layer 2: 50 in, 50 calls, 2500 children, kept 50 (6512ms)
Layer 3: 50 in, 50 calls, 2500 children, kept 50 (5844ms)
Layer 4: 50 in, 50 calls, 2500 children, kept 50 (6729ms)
Layer 5: 50 in, 50 calls, 2500 children, kept 50 (5615ms)
real 0m34.005s
```

### F6 — `--from sol --hops 6 --fc N --jumps 2`

```text
Route: Sol/Navarrete's Prospect -> LHS 6350/Zaschka Point, profit 122108434 cr
Total: 138129ms (resolution 0ms, station-filter 2ms, search 138101ms)
Expansion: 313 calls, memo 217/96 hit/miss, 8256208 candidate rows, 772753 pairs, 772753 cargo calls, 14300 children, 136674ms
Expansion phases: fetch 118175ms, cargo 11748ms, jump 913ms
Cargo: 21995 fast-path, 0 branch-and-bound, 750764 pruned, 11597ms
Correction: 2500 finalists, 1 attempted, 1 corrected, 6 cargo calls (6 fast-path, 0 b&b), 1ms
Layer 1: 63 in, 63 calls, 1800 children, kept 50 (11860ms)
Layer 2: 50 in, 50 calls, 2500 children, kept 50 (28887ms)
Layer 3: 50 in, 50 calls, 2500 children, kept 50 (24277ms)
Layer 4: 50 in, 50 calls, 2500 children, kept 50 (27211ms)
Layer 5: 50 in, 50 calls, 2500 children, kept 50 (25042ms)
real 2m19.514s
```

### F7 — `--from sol --to lave --hops 6 --fc N`

```text
Route: Sol/Navarrete's Prospect -> Lave/Lave Station, profit 41325120 cr
Total: 8545ms (resolution 0ms, station-filter 2ms, search 8526ms)
Expansion: 256 calls, memo 95/161 hit/miss, 382856 candidate rows, 47231 pairs, 47231 cargo calls, 6492 children, 8412ms
Expansion phases: fetch 7613ms, cargo 618ms, jump 12ms
Cargo: 7812 fast-path, 0 branch-and-bound, 39461 pruned, 610ms
Layer 1: 63 in, 63 calls, 1800 children, kept 50 (2790ms)
Layer 2: 50 in, 50 calls, 2500 children, kept 50 (4067ms)
Layer 3: 50 in, 50 calls, 1236 children, kept 50 (596ms)
Layer 4: 50 in, 50 calls, 768 children, kept 43 (652ms)
Layer 5: 43 in, 43 calls, 188 children, kept 14 (343ms)
Final hop: 14 attempted, 14 reach destination, 180 market candidates, 14 viable, 77ms
real 0m9.715s
```

### F8 — `--from sol --to lave --hops 6 --fc N --jumps 2`

```text
Route: Sol/Navarrete's Prospect -> Lave/Lave Station, profit 92674980 cr
Total: 110468ms (resolution 0ms, station-filter 2ms, search 110446ms)
Expansion: 263 calls, memo 140/123 hit/miss, 4399501 candidate rows, 453138 pairs, 453138 cargo calls, 10644 children, 107404ms
Expansion phases: fetch 90182ms, cargo 6963ms, jump 7563ms
Cargo: 15550 fast-path, 0 branch-and-bound, 437711 pruned, 6882ms
Layer 1: 63 in, 63 calls, 1800 children, kept 50 (12215ms)
Layer 2: 50 in, 50 calls, 2500 children, kept 50 (42172ms)
Layer 3: 50 in, 50 calls, 2500 children, kept 50 (28618ms)
Layer 4: 50 in, 50 calls, 2414 children, kept 50 (17033ms)
Layer 5: 50 in, 50 calls, 1430 children, kept 50 (8077ms)
Final hop: 50 attempted, 41 reach destination, 999 market candidates, 41 viable, 2331ms
real 1m51.888s
```

# Probe set P2 — fixed-anchor filter sweep (2026-06-11, Slice 24)

Run set 2's `--fc N` twins compared different frontiers, so row volumes
were never like for like. P2 pinned the bubble — one anchor, one
reachable temp, the same fetch under each filter state — and settled
what attribute filters do to cost. Full tables in the Slice 24 plan
(`twenty_fourth_slice_implementation_plan.md`, P2 results).

The law it establishes:

- **A filter buys cost relief in proportion to the market rows it
  removes, not the stations.** `--planetary N` removed 42% of rows and
  ~34% of fetch time. `--fc N` removed 41% of *stations* but 1.2% of
  rows — fetch time did not move.
- **`--fc N` is row-trivial in this snapshot** because carriers here
  are near-empty: 0.6 market rows per carrier against 29 per
  non-carrier; 92% of carriers in the Sol bubble carry no rows at all.
  Its effect on routes (run set 2) is pairing-side — fewer stations,
  fewer pairs — not fetch-side.
- **`--age` never shrinks the walk today**: it is a row predicate, so
  rows visited are unchanged; its time saving is rows failing the
  cheap `modified` test before the per-row EXISTS probes. The Slice 24
  stage-0 station-level cut is what turns `--age` into a walk reducer.

# Run set 3 — qualification cache verification (2026-06-11, post Part B)

Conditions as run set 1, code state: qualify-once run-scoped temps
(commit `e5947267`). All 24 runs script-driven back to back
(`run_set3.sh`), so cache warmth is uniform after the first run. Three
blocks over the eight baseline shapes: open filters, `--fc N`, and a
new `--planetary N` block with no prior baseline (this set becomes its
reference). No `--age` shape is in the baseline set; the stage-0
station cut was verified exact separately during the build.

## Headline table — open filters (vs run set 1)

| # | Shape | Jumps | Wall (was) | Fetch (was) | Qual | Cand. rows | Pairs | Profit |
|---|---|---|---|---|---|---|---|---|
| 1 | `--from sol --hops 3` | 1 | 13.8s (15.3) | 10.7s (12.3) | 558ms | 855,247 | 97,782 | 163,058,562 |
| 2 | `--from sol --hops 3` | 2 | 56.2s (63.0) | 46.5s (50.7) | 2.8s | 3,400,663 | 387,397 | 163,248,642 |
| 3 | `--to lave --hops 3` | 1 | 4.7s (4.7) | 2.9s (3.1) | 347ms | 276,438 | 27,819 | 21,183,840 |
| 4 | `--to lave --hops 3` | 2 | 21.5s (22.6) | 17.1s (17.9) | 2.1s | 1,425,683 | 147,651 | 102,440,568 |
| 5 | `--from sol --hops 6` | 1 | 29.8s (33.0) | 24.1s (26.9) | 583ms | 1,834,125 | 212,158 | 226,749,996 |
| 6 | `--from sol --hops 6` | 2 | 124.0s (139.3) | 103.9s (114.8) | 3.9s | 7,226,858 | 824,033 | 298,178,370 |
| 7 | `--from sol --to lave --hops 6` | 1 | 10.2s (10.0) | 7.6s (7.3) | 832ms | 359,594 | 46,108 | 76,410,414 |
| 8 | `--from sol --to lave --hops 6` | 2 | 121.9s (125.4) | 98.8s (100.1) | 4.9s | 3,974,953 | 458,448 | 193,186,530 |

## What run set 3 establishes

1. **The cache is exact.** All sixteen runs with a recorded baseline
   (open vs run set 1, `--fc N` vs run set 2's F1–F8) reproduce
   candidate rows, pairs, profits and routes to the digit.
2. **Fetch is down ~8–13% on the open-anchor shapes** (runs 1–6), the
   qualification cost (0.3–3.9s) repaid with margin by the cheaper
   per-anchor walks. Wall-clock follows: run 6 is 15.3s faster.
3. **The fixed-terminal shapes (7, 8) roughly break even.** The
   destination envelope narrows the station list per call, which
   disables the repeat-bubble skip and shrinks reuse; the cache
   neither helps nor hurts there.
4. **`--planetary N` confirms the row law at run scale** (new
   baseline block): on the worst shape it removes 31% of candidate
   rows and 34% of fetch time against its open twin — filters pay
   exactly in rows removed, now compounded by the cache.
5. **The residual is materialisation-shaped, as P3 predicted.** With
   re-qualification gone, what remains of fetch tracks rows returned
   per anchor. The deferred bound-ordered pairing is the named lever
   on that; evidence on file in the Slice 24 plan.

## Per-run diagnostics (verbatim)

### [open 1/8] trade run --from sol --hops 3  --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 12827ms (resolution 0ms, station-filter 2ms, search 12808ms)
  Expansion: 163 calls, memo 102/61 hit/miss, 855247 candidate rows, 97782 pairs, 97782 cargo calls, 6725 children, 
12729ms
  Expansion phases: fetch 10723ms, cargo 1547ms, jump 8ms
  Qualification: 24833 stations, 216502 rows cached, 558ms
  Cargo: 8927 fast-path, 0 branch-and-bound, 88858 pruned, 1528ms
  Correction: 2500 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
  Layer 1: 63 in, 63 calls, 1800 children, kept 50 (2648ms)
  Layer 2: 50 in, 50 calls, 2425 children, kept 50 (6046ms)

real	0m13.794s
```

### [open 2/8] trade run --from sol --hops 3 --jumps 2  --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 55079ms (resolution 0ms, station-filter 2ms, search 55032ms)
  Expansion: 163 calls, memo 99/64 hit/miss, 3400663 candidate rows, 387397 pairs, 387397 cargo calls, 6700 children, 
54566ms
  Expansion phases: fetch 46548ms, cargo 5294ms, jump 746ms
  Qualification: 105611 stations, 921205 rows cached, 2787ms
  Cargo: 10427 fast-path, 0 branch-and-bound, 376973 pruned, 5220ms
  Correction: 2500 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
  Layer 1: 63 in, 63 calls, 1800 children, kept 50 (10873ms)
  Layer 2: 50 in, 50 calls, 2400 children, kept 50 (25831ms)

real	0m56.169s
```

### [open 3/8] trade run --to lave --hops 3  --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 3776ms (resolution 0ms, station-filter 2ms, search 3763ms)
  Expansion: 128 calls, memo 60/68 hit/miss, 276438 candidate rows, 27819 pairs, 27819 cargo calls, 5150 children, 
3744ms
  Expansion phases: fetch 2859ms, cargo 774ms, jump 6ms
  Qualification: 13431 stations, 38530 rows cached, 347ms
  Cargo: 6751 fast-path, 0 branch-and-bound, 21071 pruned, 769ms
  Correction: 2450 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
  Layer 1: 28 in, 28 calls, 200 children, kept 50 (173ms)
  Layer 2: 50 in, 50 calls, 2500 children, kept 50 (1975ms)

real	0m4.697s
```

### [open 4/8] trade run --to lave --hops 3 --jumps 2  --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 20495ms (resolution 0ms, station-filter 2ms, search 20469ms)
  Expansion: 128 calls, memo 38/90 hit/miss, 1425683 candidate rows, 147651 pairs, 147651 cargo calls, 5050 children, 
20351ms
  Expansion phases: fetch 17123ms, cargo 2158ms, jump 474ms
  Qualification: 94795 stations, 274503 rows cached, 2062ms
  Cargo: 8856 fast-path, 0 branch-and-bound, 138798 pruned, 2131ms
  Correction: 2400 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 0ms
  Layer 1: 28 in, 28 calls, 200 children, kept 50 (538ms)
  Layer 2: 50 in, 50 calls, 2450 children, kept 50 (9446ms)

real	0m21.507s
```

### [open 5/8] trade run --from sol --hops 6  --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 28741ms (resolution 0ms, station-filter 2ms, search 28715ms)
  Expansion: 313 calls, memo 249/64 hit/miss, 1834125 candidate rows, 212158 pairs, 212158 cargo calls, 14177 children, 
28526ms
  Expansion phases: fetch 24100ms, cargo 3135ms, jump 17ms
  Qualification: 25064 stations, 218693 rows cached, 583ms
  Cargo: 19191 fast-path, 0 branch-and-bound, 192973 pruned, 3094ms
  Correction: 2477 finalists, 1 attempted, 1 corrected, 6 cargo calls (6 fast-path, 0 b&b), 1ms
  Layer 1: 63 in, 63 calls, 1800 children, kept 50 (2619ms)
  Layer 2: 50 in, 50 calls, 2425 children, kept 50 (6056ms)
  Layer 3: 50 in, 50 calls, 2500 children, kept 50 (5762ms)
  Layer 4: 50 in, 50 calls, 2475 children, kept 50 (5058ms)
  Layer 5: 50 in, 50 calls, 2500 children, kept 50 (5663ms)

real	0m29.791s
```

### [open 6/8] trade run --from sol --hops 6 --jumps 2  --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 122700ms (resolution 0ms, station-filter 2ms, search 122625ms)
  Expansion: 313 calls, memo 190/123 hit/miss, 7226858 candidate rows, 824033 pairs, 824033 cargo calls, 14150 children,
121590ms
  Expansion phases: fetch 103862ms, cargo 11564ms, jump 1674ms
  Qualification: 125953 stations, 1102179 rows cached, 3938ms
  Cargo: 22217 fast-path, 0 branch-and-bound, 801822 pruned, 11408ms
  Correction: 2500 finalists, 1 attempted, 1 corrected, 6 cargo calls (6 fast-path, 0 b&b), 1ms
  Layer 1: 63 in, 63 calls, 1800 children, kept 50 (10825ms)
  Layer 2: 50 in, 50 calls, 2400 children, kept 50 (24866ms)
  Layer 3: 50 in, 50 calls, 2500 children, kept 50 (24081ms)
  Layer 4: 50 in, 50 calls, 2500 children, kept 50 (25348ms)
  Layer 5: 50 in, 50 calls, 2450 children, kept 50 (22706ms)

real	2m4.045s
```

### [open 7/8] trade run --from sol --to lave --hops 6  --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 9132ms (resolution 0ms, station-filter 3ms, search 9107ms)
  Expansion: 253 calls, memo 93/160 hit/miss, 359594 candidate rows, 46108 pairs, 46108 cargo calls, 6444 children, 
8397ms
  Expansion phases: fetch 7574ms, cargo 652ms, jump 13ms
  Qualification: 17201 stations, 144078 rows cached, 832ms
  Cargo: 7701 fast-path, 0 branch-and-bound, 38461 pruned, 644ms
  Layer 1: 63 in, 63 calls, 1800 children, kept 50 (2829ms)
  Layer 2: 50 in, 50 calls, 2414 children, kept 50 (3842ms)
  Layer 3: 50 in, 50 calls, 1258 children, kept 50 (654ms)
  Layer 4: 50 in, 50 calls, 710 children, kept 40 (634ms)
  Layer 5: 40 in, 40 calls, 262 children, kept 16 (470ms)
  Final hop: 16 attempted, 16 reach destination, 222 market candidates, 16 viable, 677ms

real	0m10.200s
```

### [open 8/8] trade run --from sol --to lave --hops 6 --jumps 2  --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 120454ms (resolution 0ms, station-filter 2ms, search 120392ms)
  Expansion: 263 calls, memo 116/147 hit/miss, 3974953 candidate rows, 458448 pairs, 458448 cargo calls, 10772 children,
115968ms
  Expansion phases: fetch 98822ms, cargo 5591ms, jump 9374ms
  Qualification: 111511 stations, 963629 rows cached, 4907ms
  Cargo: 15989 fast-path, 0 branch-and-bound, 442546 pruned, 5508ms
  Layer 1: 63 in, 63 calls, 1800 children, kept 50 (11901ms)
  Layer 2: 50 in, 50 calls, 2400 children, kept 50 (38427ms)
  Layer 3: 50 in, 50 calls, 2500 children, kept 50 (28346ms)
  Layer 4: 50 in, 50 calls, 2462 children, kept 50 (26625ms)
  Layer 5: 50 in, 50 calls, 1610 children, kept 50 (11244ms)
  Final hop: 50 attempted, 30 reach destination, 625 market candidates, 28 viable, 3849ms

real	2m1.928s
```

### [fcN 1/8] trade run --from sol --hops 3 --fc N --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 12516ms (resolution 0ms, station-filter 2ms, search 12495ms)
  Expansion: 163 calls, memo 97/66 hit/miss, 855001 candidate rows, 96020 pairs, 96020 cargo calls, 6800 children, 
12422ms
  Expansion phases: fetch 10686ms, cargo 1330ms, jump 8ms
  Qualification: 21754 stations, 236647 rows cached, 574ms
  Cargo: 8946 fast-path, 0 branch-and-bound, 87077 pruned, 1312ms
  Correction: 2500 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
  Layer 1: 63 in, 63 calls, 1800 children, kept 50 (2556ms)
  Layer 2: 50 in, 50 calls, 2500 children, kept 50 (6141ms)

real	0m13.471s
```

### [fcN 2/8] trade run --from sol --hops 3 --jumps 2 --fc N --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 54413ms (resolution 0ms, station-filter 2ms, search 54366ms)
  Expansion: 163 calls, memo 88/75 hit/miss, 3567035 candidate rows, 372703 pairs, 372703 cargo calls, 6800 children, 
53898ms
  Expansion phases: fetch 46142ms, cargo 5006ms, jump 688ms
  Qualification: 87421 stations, 907319 rows cached, 2232ms
  Cargo: 10454 fast-path, 0 branch-and-bound, 362252 pruned, 4935ms
  Correction: 2500 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
  Layer 1: 63 in, 63 calls, 1800 children, kept 50 (10788ms)
  Layer 2: 50 in, 50 calls, 2500 children, kept 50 (26652ms)

real	0m55.485s
```

### [fcN 3/8] trade run --to lave --hops 3 --fc N --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 3581ms (resolution 0ms, station-filter 2ms, search 3570ms)
  Expansion: 104 calls, memo 36/68 hit/miss, 277296 candidate rows, 27590 pairs, 27590 cargo calls, 5150 children, 
3551ms
  Expansion phases: fetch 2827ms, cargo 612ms, jump 6ms
  Qualification: 9620 stations, 35223 rows cached, 278ms
  Cargo: 6717 fast-path, 0 branch-and-bound, 20876 pruned, 607ms
  Correction: 2500 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
  Layer 1: 4 in, 4 calls, 150 children, kept 50 (118ms)
  Layer 2: 50 in, 50 calls, 2500 children, kept 50 (1899ms)

real	0m4.511s
```

### [fcN 4/8] trade run --to lave --hops 3 --jumps 2 --fc N --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 20317ms (resolution 0ms, station-filter 2ms, search 20292ms)
  Expansion: 104 calls, memo 14/90 hit/miss, 1500244 candidate rows, 152099 pairs, 152099 cargo calls, 5150 children, 
20164ms
  Expansion phases: fetch 16942ms, cargo 2031ms, jump 477ms
  Qualification: 81105 stations, 271035 rows cached, 1639ms
  Cargo: 8988 fast-path, 0 branch-and-bound, 143114 pruned, 2003ms
  Correction: 2500 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
  Layer 1: 4 in, 4 calls, 150 children, kept 50 (444ms)
  Layer 2: 50 in, 50 calls, 2500 children, kept 50 (9173ms)

real	0m21.349s
```

### [fcN 5/8] trade run --from sol --hops 6 --fc N --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 29469ms (resolution 0ms, station-filter 2ms, search 29439ms)
  Expansion: 313 calls, memo 239/74 hit/miss, 2034917 candidate rows, 207383 pairs, 207383 cargo calls, 14300 children, 
29224ms
  Expansion phases: fetch 25244ms, cargo 2993ms, jump 17ms
  Qualification: 22508 stations, 245886 rows cached, 624ms
  Cargo: 18808 fast-path, 0 branch-and-bound, 188581 pruned, 2953ms
  Correction: 2500 finalists, 1 attempted, 1 corrected, 6 cargo calls (6 fast-path, 0 b&b), 1ms
  Layer 1: 63 in, 63 calls, 1800 children, kept 50 (2565ms)
  Layer 2: 50 in, 50 calls, 2500 children, kept 50 (6157ms)
  Layer 3: 50 in, 50 calls, 2500 children, kept 50 (5353ms)
  Layer 4: 50 in, 50 calls, 2500 children, kept 50 (5885ms)
  Layer 5: 50 in, 50 calls, 2500 children, kept 50 (4960ms)

real	0m30.446s
```

### [fcN 6/8] trade run --from sol --hops 6 --jumps 2 --fc N --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 119248ms (resolution 0ms, station-filter 2ms, search 119185ms)
  Expansion: 313 calls, memo 217/96 hit/miss, 8256208 candidate rows, 772753 pairs, 772753 cargo calls, 14300 children, 
117883ms
  Expansion phases: fetch 100048ms, cargo 12282ms, jump 882ms
  Qualification: 96830 stations, 1017700 rows cached, 2702ms
  Cargo: 21995 fast-path, 0 branch-and-bound, 750764 pruned, 12131ms
  Correction: 2500 finalists, 1 attempted, 1 corrected, 6 cargo calls (6 fast-path, 0 b&b), 1ms
  Layer 1: 63 in, 63 calls, 1800 children, kept 50 (10637ms)
  Layer 2: 50 in, 50 calls, 2500 children, kept 50 (25885ms)
  Layer 3: 50 in, 50 calls, 2500 children, kept 50 (21440ms)
  Layer 4: 50 in, 50 calls, 2500 children, kept 50 (23635ms)
  Layer 5: 50 in, 50 calls, 2500 children, kept 50 (20870ms)

real	2m0.463s
```

### [fcN 7/8] trade run --from sol --to lave --hops 6 --fc N --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 8444ms (resolution 0ms, station-filter 2ms, search 8420ms)
  Expansion: 256 calls, memo 95/161 hit/miss, 382856 candidate rows, 47231 pairs, 47231 cargo calls, 6492 children, 
8314ms
  Expansion phases: fetch 7378ms, cargo 707ms, jump 14ms
  Qualification: 12159 stations, 142544 rows cached, 826ms
  Cargo: 7812 fast-path, 0 branch-and-bound, 39461 pruned, 699ms
  Layer 1: 63 in, 63 calls, 1800 children, kept 50 (2714ms)
  Layer 2: 50 in, 50 calls, 2500 children, kept 50 (3898ms)
  Layer 3: 50 in, 50 calls, 1236 children, kept 50 (619ms)
  Layer 4: 50 in, 50 calls, 768 children, kept 43 (635ms)
  Layer 5: 43 in, 43 calls, 188 children, kept 14 (481ms)
  Final hop: 14 attempted, 14 reach destination, 180 market candidates, 14 viable, 73ms

real	0m9.494s
```

### [fcN 8/8] trade run --from sol --to lave --hops 6 --jumps 2 --fc N --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 103250ms (resolution 0ms, station-filter 2ms, search 103193ms)
  Expansion: 263 calls, memo 140/123 hit/miss, 4399501 candidate rows, 453138 pairs, 453138 cargo calls, 10644 children,
100261ms
  Expansion phases: fetch 86142ms, cargo 5781ms, jump 6076ms
  Qualification: 92033 stations, 934123 rows cached, 4421ms
  Cargo: 15550 fast-path, 0 branch-and-bound, 437711 pruned, 5700ms
  Layer 1: 63 in, 63 calls, 1800 children, kept 50 (11829ms)
  Layer 2: 50 in, 50 calls, 2500 children, kept 50 (39359ms)
  Layer 3: 50 in, 50 calls, 2500 children, kept 50 (26081ms)
  Layer 4: 50 in, 50 calls, 2414 children, kept 50 (15409ms)
  Layer 5: 50 in, 50 calls, 1430 children, kept 50 (8239ms)
  Final hop: 50 attempted, 41 reach destination, 999 market candidates, 41 viable, 2276ms

real	1m44.639s
```

### [planN 1/8] trade run --from sol --hops 3 --planetary N --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 6944ms (resolution 0ms, station-filter 2ms, search 6929ms)
  Expansion: 110 calls, memo 45/65 hit/miss, 475238 candidate rows, 44950 pairs, 44950 cargo calls, 5350 children, 
6893ms
  Expansion phases: fetch 5911ms, cargo 795ms, jump 6ms
  Qualification: 8680 stations, 149127 rows cached, 506ms
  Cargo: 6148 fast-path, 0 branch-and-bound, 38805 pruned, 786ms
  Correction: 2500 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
  Layer 1: 10 in, 10 calls, 450 children, kept 50 (477ms)
  Layer 2: 50 in, 50 calls, 2400 children, kept 50 (3750ms)

real	0m7.874s
```

### [planN 2/8] trade run --from sol --hops 3 --jumps 2 --planetary N --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 33036ms (resolution 0ms, station-filter 1ms, search 32997ms)
  Expansion: 110 calls, memo 44/66 hit/miss, 2193555 candidate rows, 207162 pairs, 207162 cargo calls, 5272 children, 
32729ms
  Expansion phases: fetch 28150ms, cargo 2806ms, jump 713ms
  Qualification: 33885 stations, 696700 rows cached, 1829ms
  Cargo: 6974 fast-path, 0 branch-and-bound, 200191 pruned, 2767ms
  Correction: 2469 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
  Layer 1: 10 in, 10 calls, 450 children, kept 50 (2381ms)
  Layer 2: 50 in, 50 calls, 2353 children, kept 50 (17976ms)

real	0m34.092s
```

### [planN 3/8] trade run --to lave --hops 3 --planetary N --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 3175ms (resolution 0ms, station-filter 2ms, search 3163ms)
  Expansion: 128 calls, memo 58/70 hit/miss, 222966 candidate rows, 19942 pairs, 19942 cargo calls, 5150 children, 
3148ms
  Expansion phases: fetch 2559ms, cargo 498ms, jump 6ms
  Qualification: 5112 stations, 32050 rows cached, 271ms
  Cargo: 6187 fast-path, 0 branch-and-bound, 13758 pruned, 494ms
  Correction: 2450 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 0ms
  Layer 1: 28 in, 28 calls, 200 children, kept 50 (154ms)
  Layer 2: 50 in, 50 calls, 2500 children, kept 50 (1697ms)

real	0m4.095s
```

### [planN 4/8] trade run --to lave --hops 3 --jumps 2 --planetary N --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 15399ms (resolution 0ms, station-filter 2ms, search 15377ms)
  Expansion: 128 calls, memo 36/92 hit/miss, 1019867 candidate rows, 92734 pairs, 92734 cargo calls, 5006 children, 
15295ms
  Expansion phases: fetch 13050ms, cargo 1396ms, jump 470ms
  Qualification: 25015 stations, 176716 rows cached, 1332ms
  Cargo: 7319 fast-path, 0 branch-and-bound, 85418 pruned, 1379ms
  Correction: 2356 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
  Layer 1: 28 in, 28 calls, 200 children, kept 50 (457ms)
  Layer 2: 50 in, 50 calls, 2450 children, kept 50 (7930ms)

real	0m16.425s
```

### [planN 5/8] trade run --from sol --hops 6 --planetary N --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 16865ms (resolution 0ms, station-filter 2ms, search 16841ms)
  Expansion: 260 calls, memo 186/74 hit/miss, 1080281 candidate rows, 106862 pairs, 106862 cargo calls, 12752 children, 
16739ms
  Expansion phases: fetch 14507ms, cargo 1780ms, jump 15ms
  Qualification: 9102 stations, 159804 rows cached, 570ms
  Cargo: 14804 fast-path, 0 branch-and-bound, 92064 pruned, 1760ms
  Correction: 2452 finalists, 1 attempted, 1 corrected, 6 cargo calls (6 fast-path, 0 b&b), 1ms
  Layer 1: 10 in, 10 calls, 450 children, kept 50 (489ms)
  Layer 2: 50 in, 50 calls, 2400 children, kept 50 (3717ms)
  Layer 3: 50 in, 50 calls, 2500 children, kept 50 (3641ms)
  Layer 4: 50 in, 50 calls, 2450 children, kept 50 (3233ms)
  Layer 5: 50 in, 50 calls, 2500 children, kept 50 (3414ms)

real	0m17.908s
```

### [planN 6/8] trade run --from sol --hops 6 --jumps 2 --planetary N --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 80339ms (resolution 0ms, station-filter 2ms, search 80275ms)
  Expansion: 260 calls, memo 129/131 hit/miss, 4988235 candidate rows, 480952 pairs, 480952 cargo calls, 12594 children,
79621ms
  Expansion phases: fetch 68611ms, cargo 6877ms, jump 1567ms
  Qualification: 46181 stations, 938863 rows cached, 3314ms
  Cargo: 16804 fast-path, 0 branch-and-bound, 464154 pruned, 6784ms
  Correction: 2500 finalists, 1 attempted, 1 corrected, 6 cargo calls (6 fast-path, 0 b&b), 1ms
  Layer 1: 10 in, 10 calls, 450 children, kept 50 (2422ms)
  Layer 2: 50 in, 50 calls, 2353 children, kept 50 (18056ms)
  Layer 3: 50 in, 50 calls, 2469 children, kept 50 (16402ms)
  Layer 4: 50 in, 50 calls, 2469 children, kept 50 (19140ms)
  Layer 5: 50 in, 50 calls, 2353 children, kept 50 (13067ms)

real	1m21.576s
```

### [planN 7/8] trade run --from sol --to lave --hops 6 --planetary N --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 4929ms (resolution 0ms, station-filter 2ms, search 4907ms)
  Expansion: 195 calls, memo 38/157 hit/miss, 170089 candidate rows, 15805 pairs, 15805 cargo calls, 4490 children, 
4466ms
  Expansion phases: fetch 4178ms, cargo 198ms, jump 9ms
  Qualification: 6668 stations, 94459 rows cached, 565ms
  Cargo: 4972 fast-path, 0 branch-and-bound, 10875 pruned, 195ms
  Layer 1: 10 in, 10 calls, 450 children, kept 50 (533ms)
  Layer 2: 50 in, 50 calls, 2400 children, kept 50 (2298ms)
  Layer 3: 50 in, 50 calls, 1072 children, kept 50 (644ms)
  Layer 4: 50 in, 50 calls, 467 children, kept 35 (591ms)
  Layer 5: 35 in, 35 calls, 101 children, kept 12 (418ms)
  Final hop: 12 attempted, 12 reach destination, 174 market candidates, 12 viable, 422ms

real	0m5.942s
```

### [planN 8/8] trade run --from sol --to lave --hops 6 --jumps 2 --planetary N --capacity 720 --credits 200000000 --ly-per 30

```text
  Total: 93975ms (resolution 0ms, station-filter 2ms, search 93924ms)
  Expansion: 210 calls, memo 73/137 hit/miss, 2724518 candidate rows, 263715 pairs, 263715 cargo calls, 8933 children, 
90009ms
  Expansion phases: fetch 75671ms, cargo 3740ms, jump 9377ms
  Qualification: 35651 stations, 740249 rows cached, 3868ms
  Cargo: 11497 fast-path, 0 branch-and-bound, 252305 pruned, 3692ms
  Layer 1: 10 in, 10 calls, 450 children, kept 50 (2866ms)
  Layer 2: 50 in, 50 calls, 2353 children, kept 50 (30802ms)
  Layer 3: 50 in, 50 calls, 2406 children, kept 50 (21430ms)
  Layer 4: 50 in, 50 calls, 2377 children, kept 50 (24818ms)
  Layer 5: 50 in, 50 calls, 1347 children, kept 50 (10440ms)
  Final hop: 50 attempted, 29 reach destination, 754 market candidates, 28 viable, 3567ms

real	1m35.456s
```

# Run set 4 — aged baselines on the clean database (2026-06-12)

Conditions as run set 3 plus: database freshly rebuilt the same day via
the converted eddblink import (uniformity 94,367 of 94,367 — zero mixed
stations), so the snapshot invariant the `--age` station cut relies on
holds by construction. The eight baseline shapes at `--age 3`, then
`--age 1` (newly meaningful on day-fresh data). Run start times are
recorded per run in the verbatims below.

**Comparison rule — read before comparing anything to this set.**
`--age` is a rolling window, so these figures are anchored to their
recorded start times. To reproduce a run exactly later, widen `--age`
by the elapsed time since that start (minutes ÷ 1440) per the
"Reproducing `--age` runs exactly" note in the project CLAUDE.md — and
check the database's data age first: on a stale database the same
`--age` value selects a different fraction of the universe and the
comparison is meaningless.

Window sizes on this snapshot: `--age 3` keeps 19,383 of 94,367
stations (21%) and 3.1M of 15.2M rows; `--age 1` keeps 9,461 stations
(10%) and 1.45M rows.

## Headline table (open-filter run set 3 wall shown for context)

| # | Shape | Jumps | Open wall | age 3 wall / fetch | age 1 wall / fetch |
|---|---|---|---|---|---|
| 1 | `--from sol --hops 3` | 1 | 13.8s | 9.5s / 6.5s | 6.1s / 4.6s |
| 2 | `--from sol --hops 3` | 2 | 56.2s | 27.9s / 23.6s | 19.8s / 16.6s |
| 3 | `--to lave --hops 3` | 1 | 4.7s | 3.9s / 2.6s | 3.5s / 2.5s |
| 4 | `--to lave --hops 3` | 2 | 21.5s | 11.3s / 9.3s | 9.7s / 7.8s |
| 5 | `--from sol --hops 6` | 1 | 29.8s | 15.7s / 12.2s | 11.5s / 9.3s |
| 6 | `--from sol --hops 6` | 2 | 124.0s | 55.3s / 47.2s | 38.3s / 32.8s |
| 7 | `--from sol --to lave --hops 6` | 1 | 10.2s | 7.5s / 5.7s | 5.6s / 4.1s |
| 8 | `--from sol --to lave --hops 6` | 2 | 121.9s | 85.0s / 66.3s | 70.5s / 54.7s |

## What run set 4 establishes

1. **`--age` is now a real cost lever.** P2 proved that pre-cache, the
   age predicate never shrank the walk (rows visited unchanged within a
   fixed bubble). With stage 0, stale stations are never walked: the
   worst shape (run 6) drops from 124s open to 55.3s at `--age 3` and
   38.3s at `--age 1` — −55% and −69% wall.
2. **The caveat is honest scope, not noise:** an aged run answers a
   different question than an open run (fresh data only — candidate
   volumes, routes and profits all legitimately differ). The comparison
   measures what adding `--age` buys a commander, not like-for-like
   engine speed. There is no pre-cache aged baseline; this set is the
   reference for aged shapes from here on.
3. **The fresh-set build costs ~1s, once per run** (the `--age` runs'
   qualification figures sit ~1s above their open twins). One DISTINCT
   range scan over the modified-led index, paid once, buying the
   station-level cut for the whole run.
4. **The fixed-terminal j2 shape (run 8) again benefits least** —
   85s/70.5s against 121.9s open — consistent with the known cache weak
   spot: the destination envelope narrows per call, so the skip marker
   never engages there.

## Per-run diagnostics (verbatim)

### [age3 1/8] trade run --from sol --hops 3 --age 3 --capacity 720 --credits 200000000 --ly-per 30

```text
started 2026-06-12 13:58:36
  Total: 7491ms (resolution 0ms, station-filter 4ms, search 7475ms)
  Expansion: 163 calls, memo 103/60 hit/miss, 320459 candidate rows, 35666 pairs, 35666 cargo calls, 6350 children, 
7449ms
  Expansion phases: fetch 6507ms, cargo 796ms, jump 7ms
  Qualification: 27819 stations, 77881 rows cached, 1646ms
  Cargo: 7641 fast-path, 0 branch-and-bound, 28028 pruned, 788ms
  Correction: 2500 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
  Layer 1: 63 in, 63 calls, 1350 children, kept 50 (2049ms)
  Layer 2: 50 in, 50 calls, 2500 children, kept 50 (3340ms)

real	0m9.542s
```

### [age3 2/8] trade run --from sol --hops 3 --jumps 2 --age 3 --capacity 720 --credits 200000000 --ly-per 30

```text
started 2026-06-12 13:58:45
  Total: 26835ms (resolution 0ms, station-filter 2ms, search 26810ms)
  Expansion: 163 calls, memo 85/78 hit/miss, 1085490 candidate rows, 110134 pairs, 110134 cargo calls, 6350 children, 
26704ms
  Expansion phases: fetch 23572ms, cargo 1555ms, jump 1063ms
  Qualification: 110725 stations, 243759 rows cached, 3796ms
  Cargo: 8545 fast-path, 0 branch-and-bound, 101592 pruned, 1533ms
  Correction: 2500 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
  Layer 1: 63 in, 63 calls, 1350 children, kept 50 (4273ms)
  Layer 2: 50 in, 50 calls, 2500 children, kept 50 (13377ms)

real	0m27.908s
```

### [age3 3/8] trade run --to lave --hops 3 --age 3 --capacity 720 --credits 200000000 --ly-per 30

```text
started 2026-06-12 13:59:13
  Total: 2931ms (resolution 0ms, station-filter 2ms, search 2922ms)
  Expansion: 130 calls, memo 66/64 hit/miss, 97055 candidate rows, 9479 pairs, 9479 cargo calls, 5074 children, 2913ms
  Expansion phases: fetch 2649ms, cargo 212ms, jump 6ms
  Qualification: 11137 stations, 10142 rows cached, 1057ms
  Cargo: 5471 fast-path, 0 branch-and-bound, 4011 pruned, 210ms
  Correction: 2444 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
  Layer 1: 30 in, 30 calls, 150 children, kept 50 (886ms)
  Layer 2: 50 in, 50 calls, 2480 children, kept 50 (1161ms)

real	0m3.850s
```

### [age3 4/8] trade run --to lave --hops 3 --jumps 2 --age 3 --capacity 720 --credits 200000000 --ly-per 30

```text
started 2026-06-12 13:59:17
  Total: 10289ms (resolution 0ms, station-filter 2ms, search 10272ms)
  Expansion: 130 calls, memo 48/82 hit/miss, 328567 candidate rows, 31394 pairs, 31394 cargo calls, 5150 children, 
10248ms
  Expansion phases: fetch 9295ms, cargo 470ms, jump 360ms
  Qualification: 85930 stations, 64902 rows cached, 2343ms
  Cargo: 6673 fast-path, 0 branch-and-bound, 24724 pruned, 464ms
  Correction: 2500 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
  Layer 1: 30 in, 30 calls, 150 children, kept 50 (1036ms)
  Layer 2: 50 in, 50 calls, 2500 children, kept 50 (5095ms)

real	0m11.259s
```

### [age3 5/8] trade run --from sol --hops 6 --age 3 --capacity 720 --credits 200000000 --ly-per 30

```text
started 2026-06-12 13:59:28
  Total: 14646ms (resolution 0ms, station-filter 2ms, search 14625ms)
  Expansion: 313 calls, memo 249/64 hit/miss, 725141 candidate rows, 80788 pairs, 80788 cargo calls, 13848 children, 
14552ms
  Expansion phases: fetch 12207ms, cargo 2007ms, jump 16ms
  Qualification: 30927 stations, 83345 rows cached, 1301ms
  Cargo: 16835 fast-path, 0 branch-and-bound, 63959 pruned, 1991ms
  Correction: 2499 finalists, 1 attempted, 1 corrected, 6 cargo calls (6 fast-path, 0 b&b), 1ms
  Layer 1: 63 in, 63 calls, 1350 children, kept 50 (1864ms)
  Layer 2: 50 in, 50 calls, 2500 children, kept 50 (3097ms)
  Layer 3: 50 in, 50 calls, 2500 children, kept 50 (2744ms)
  Layer 4: 50 in, 50 calls, 2499 children, kept 50 (2577ms)
  Layer 5: 50 in, 50 calls, 2500 children, kept 50 (2574ms)

real	0m15.706s
```

### [age3 6/8] trade run --from sol --hops 6 --jumps 2 --age 3 --capacity 720 --credits 200000000 --ly-per 30

```text
started 2026-06-12 13:59:44
  Total: 54027ms (resolution 0ms, station-filter 2ms, search 53986ms)
  Expansion: 313 calls, memo 186/127 hit/miss, 2506516 candidate rows, 249661 pairs, 249661 cargo calls, 13850 children,
53724ms
  Expansion phases: fetch 47162ms, cargo 3919ms, jump 1575ms
  Qualification: 126071 stations, 275976 rows cached, 4440ms
  Cargo: 18415 fast-path, 0 branch-and-bound, 231252 pruned, 3867ms
  Correction: 2500 finalists, 1 attempted, 1 corrected, 6 cargo calls (6 fast-path, 0 b&b), 1ms
  Layer 1: 63 in, 63 calls, 1350 children, kept 50 (4227ms)
  Layer 2: 50 in, 50 calls, 2500 children, kept 50 (12629ms)
  Layer 3: 50 in, 50 calls, 2500 children, kept 50 (10988ms)
  Layer 4: 50 in, 50 calls, 2500 children, kept 50 (10545ms)
  Layer 5: 50 in, 50 calls, 2500 children, kept 50 (9606ms)

real	0m55.299s
```

### [age3 7/8] trade run --from sol --to lave --hops 6 --age 3 --capacity 720 --credits 200000000 --ly-per 30

```text
started 2026-06-12 14:00:39
  Total: 6459ms (resolution 0ms, station-filter 3ms, search 6437ms)
  Expansion: 247 calls, memo 81/166 hit/miss, 157263 candidate rows, 16854 pairs, 16854 cargo calls, 5050 children, 
5974ms
  Expansion phases: fetch 5656ms, cargo 243ms, jump 10ms
  Qualification: 21768 stations, 62255 rows cached, 1566ms
  Cargo: 5770 fast-path, 0 branch-and-bound, 11108 pruned, 240ms
  Layer 1: 63 in, 63 calls, 1350 children, kept 50 (2058ms)
  Layer 2: 50 in, 50 calls, 2488 children, kept 50 (2297ms)
  Layer 3: 50 in, 50 calls, 749 children, kept 50 (612ms)
  Layer 4: 50 in, 50 calls, 371 children, kept 34 (713ms)
  Layer 5: 34 in, 34 calls, 92 children, kept 8 (312ms)
  Final hop: 8 attempted, 8 reach destination, 117 market candidates, 8 viable, 446ms

real	0m7.488s
```

### [age3 8/8] trade run --from sol --to lave --hops 6 --jumps 2 --age 3 --capacity 720 --credits 200000000 --ly-per 30

```text
started 2026-06-12 14:00:47
  Total: 83519ms (resolution 0ms, station-filter 3ms, search 83482ms)
  Expansion: 263 calls, memo 106/157 hit/miss, 1374833 candidate rows, 130660 pairs, 130660 cargo calls, 9958 children, 
79605ms
  Expansion phases: fetch 66327ms, cargo 2018ms, jump 10578ms
  Qualification: 114516 stations, 248368 rows cached, 5140ms
  Cargo: 12844 fast-path, 0 branch-and-bound, 117927 pruned, 1995ms
  Layer 1: 63 in, 63 calls, 1350 children, kept 50 (5160ms)
  Layer 2: 50 in, 50 calls, 2500 children, kept 50 (26078ms)
  Layer 3: 50 in, 50 calls, 2500 children, kept 50 (23449ms)
  Layer 4: 50 in, 50 calls, 2447 children, kept 50 (17353ms)
  Layer 5: 50 in, 50 calls, 1161 children, kept 50 (7758ms)
  Final hop: 50 attempted, 37 reach destination, 878 market candidates, 37 viable, 3684ms

real	1m25.048s
```

### [age1 1/8] trade run --from sol --hops 3 --age 1 --capacity 720 --credits 200000000 --ly-per 30

```text
started 2026-06-12 14:02:12
  Total: 5198ms (resolution 0ms, station-filter 2ms, search 5185ms)
  Expansion: 163 calls, memo 96/67 hit/miss, 192394 candidate rows, 19206 pairs, 19206 cargo calls, 5606 children, 
5170ms
  Expansion phases: fetch 4608ms, cargo 474ms, jump 7ms
  Qualification: 28563 stations, 39531 rows cached, 1269ms
  Cargo: 6283 fast-path, 0 branch-and-bound, 12926 pruned, 470ms
  Correction: 2500 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
  Layer 1: 63 in, 63 calls, 638 children, kept 50 (1290ms)
  Layer 2: 50 in, 50 calls, 2468 children, kept 50 (2272ms)

real	0m6.114s
```

### [age1 2/8] trade run --from sol --hops 3 --jumps 2 --age 1 --capacity 720 --credits 200000000 --ly-per 30

```text
started 2026-06-12 14:02:18
  Total: 18706ms (resolution 0ms, station-filter 2ms, search 18685ms)
  Expansion: 163 calls, memo 85/78 hit/miss, 531870 candidate rows, 52847 pairs, 52847 cargo calls, 5750 children, 
18635ms
  Expansion phases: fetch 16613ms, cargo 802ms, jump 1000ms
  Qualification: 108716 stations, 113938 rows cached, 3063ms
  Cargo: 6826 fast-path, 0 branch-and-bound, 46024 pruned, 792ms
  Correction: 2500 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
  Layer 1: 63 in, 63 calls, 750 children, kept 50 (2212ms)
  Layer 2: 50 in, 50 calls, 2500 children, kept 50 (9140ms)

real	0m19.806s
```

### [age1 3/8] trade run --to lave --hops 3 --age 1 --capacity 720 --credits 200000000 --ly-per 30

```text
started 2026-06-12 14:02:38
  Total: 2635ms (resolution 0ms, station-filter 2ms, search 2624ms)
  Expansion: 130 calls, memo 66/64 hit/miss, 57365 candidate rows, 5733 pairs, 5733 cargo calls, 4690 children, 2618ms
  Expansion phases: fetch 2497ms, cargo 81ms, jump 5ms
  Qualification: 14602 stations, 6240 rows cached, 1017ms
  Cargo: 4923 fast-path, 0 branch-and-bound, 813 pruned, 80ms
  Correction: 2167 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 1ms
  Layer 1: 30 in, 30 calls, 100 children, kept 50 (856ms)
  Layer 2: 50 in, 50 calls, 2423 children, kept 50 (1042ms)

real	0m3.548s
```

### [age1 4/8] trade run --to lave --hops 3 --jumps 2 --age 1 --capacity 720 --credits 200000000 --ly-per 30

```text
started 2026-06-12 14:02:41
  Total: 8697ms (resolution 0ms, station-filter 2ms, search 8682ms)
  Expansion: 130 calls, memo 50/80 hit/miss, 172024 candidate rows, 17266 pairs, 17266 cargo calls, 5076 children, 
8668ms
  Expansion phases: fetch 7783ms, cargo 373ms, jump 440ms
  Qualification: 81765 stations, 31381 rows cached, 2126ms
  Cargo: 5779 fast-path, 0 branch-and-bound, 11490 pruned, 369ms
  Correction: 2476 finalists, 1 attempted, 1 corrected, 3 cargo calls (3 fast-path, 0 b&b), 0ms
  Layer 1: 30 in, 30 calls, 100 children, kept 50 (968ms)
  Layer 2: 50 in, 50 calls, 2500 children, kept 50 (3997ms)

real	0m9.688s
```

### [age1 5/8] trade run --from sol --hops 6 --age 1 --capacity 720 --credits 200000000 --ly-per 30

```text
started 2026-06-12 14:02:51
  Total: 10436ms (resolution 0ms, station-filter 2ms, search 10417ms)
  Expansion: 313 calls, memo 246/67 hit/miss, 459820 candidate rows, 44886 pairs, 44886 cargo calls, 13106 children, 
10366ms
  Expansion phases: fetch 9279ms, cargo 829ms, jump 17ms
  Qualification: 28563 stations, 39531 rows cached, 1295ms
  Cargo: 14920 fast-path, 0 branch-and-bound, 29972 pruned, 819ms
  Correction: 2500 finalists, 1 attempted, 1 corrected, 6 cargo calls (6 fast-path, 0 b&b), 1ms
  Layer 1: 63 in, 63 calls, 638 children, kept 50 (1323ms)
  Layer 2: 50 in, 50 calls, 2468 children, kept 50 (2295ms)
  Layer 3: 50 in, 50 calls, 2500 children, kept 50 (2039ms)
  Layer 4: 50 in, 50 calls, 2500 children, kept 50 (1740ms)
  Layer 5: 50 in, 50 calls, 2500 children, kept 50 (1834ms)

real	0m11.487s
```

### [age1 6/8] trade run --from sol --hops 6 --jumps 2 --age 1 --capacity 720 --credits 200000000 --ly-per 30

```text
started 2026-06-12 14:03:03
  Total: 37080ms (resolution 0ms, station-filter 2ms, search 37046ms)
  Expansion: 313 calls, memo 196/117 hit/miss, 1276223 candidate rows, 123768 pairs, 123768 cargo calls, 13247 children,
36913ms
  Expansion phases: fetch 32769ms, cargo 2185ms, jump 1441ms
  Qualification: 130971 stations, 133279 rows cached, 4071ms
  Cargo: 15905 fast-path, 0 branch-and-bound, 107869 pruned, 2160ms
  Correction: 2500 finalists, 1 attempted, 1 corrected, 6 cargo calls (6 fast-path, 0 b&b), 1ms
  Layer 1: 63 in, 63 calls, 750 children, kept 50 (2301ms)
  Layer 2: 50 in, 50 calls, 2500 children, kept 50 (9228ms)
  Layer 3: 50 in, 50 calls, 2500 children, kept 50 (8241ms)
  Layer 4: 50 in, 50 calls, 2500 children, kept 50 (6276ms)
  Layer 5: 50 in, 50 calls, 2497 children, kept 50 (7142ms)

real	0m38.309s
```

### [age1 7/8] trade run --from sol --to lave --hops 6 --age 1 --capacity 720 --credits 200000000 --ly-per 30

```text
started 2026-06-12 14:03:41
  Total: 4593ms (resolution 0ms, station-filter 3ms, search 4576ms)
  Expansion: 220 calls, memo 86/134 hit/miss, 84666 candidate rows, 8605 pairs, 8605 cargo calls, 3503 children, 4312ms
  Expansion phases: fetch 4136ms, cargo 132ms, jump 7ms
  Qualification: 18492 stations, 28431 rows cached, 1446ms
  Cargo: 3834 fast-path, 0 branch-and-bound, 4783 pruned, 131ms
  Layer 1: 63 in, 63 calls, 638 children, kept 50 (1417ms)
  Layer 2: 50 in, 50 calls, 2471 children, kept 50 (1719ms)
  Layer 3: 50 in, 50 calls, 174 children, kept 34 (465ms)
  Layer 4: 34 in, 34 calls, 179 children, kept 23 (421ms)
  Layer 5: 23 in, 23 calls, 41 children, kept 6 (301ms)
  Final hop: 6 attempted, 6 reach destination, 52 market candidates, 6 viable, 252ms

real	0m5.576s
```

### [age1 8/8] trade run --from sol --to lave --hops 6 --jumps 2 --age 1 --capacity 720 --credits 200000000 --ly-per 30

```text
started 2026-06-12 14:03:47
  Total: 69016ms (resolution 0ms, station-filter 2ms, search 68986ms)
  Expansion: 263 calls, memo 117/146 hit/miss, 678822 candidate rows, 65112 pairs, 65112 cargo calls, 8991 children, 
65414ms
  Expansion phases: fetch 54741ms, cargo 964ms, jump 9450ms
  Qualification: 112126 stations, 116944 rows cached, 4810ms
  Cargo: 10640 fast-path, 0 branch-and-bound, 54548 pruned, 953ms
  Layer 1: 63 in, 63 calls, 750 children, kept 50 (2918ms)
  Layer 2: 50 in, 50 calls, 2500 children, kept 50 (22383ms)
  Layer 3: 50 in, 50 calls, 2500 children, kept 50 (19520ms)
  Layer 4: 50 in, 50 calls, 2500 children, kept 50 (14318ms)
  Layer 5: 50 in, 50 calls, 741 children, kept 50 (6372ms)
  Final hop: 50 attempted, 38 reach destination, 493 market candidates, 38 viable, 3474ms

real	1m10.462s
```

---

# Run set 5 — bound-ordered streaming with the provable early stop (2026-06-12)

Conditions as run set 3 (open filters, no `--age`), run the same day as
the old-code reference sweep so both sides share one database state. The
"old" walls below are that same-day reference (the pre-change code run
against identical data), not run set 3's — run set 3 predates a database
rebuild, so its absolute walls are not comparable.

The change measured: the open-ended candidate fetch streams station
groups best-ceiling-first and the consumer stops reading at the first
station whose ceiling cannot beat the kept-score floor (so the tail is
never read off the cursor, converted, or paired); onward viability on
non-terminal hops is answered per station from the opposite side's
qualification temp instead of per row. All routes byte-identical to the
old code — 8/8 here, 17/17 across the slice's full verification set.

## Headline table

| # | Shape | Jumps | Old wall | New wall | Δ |
|---|---|---|---|---|---|
| 1 | `--from sol --hops 3` | 1 | 13.8s | 7.6s | −45% |
| 2 | `--from sol --hops 3` | 2 | 61.9s | 28.9s | −53% |
| 3 | `--to lave --hops 3` | 1 | 4.7s | 4.0s | −15% |
| 4 | `--to lave --hops 3` | 2 | 20.1s | 14.2s | −29% |
| 5 | `--from sol --hops 6` | 1 | 31.6s | 15.9s | −50% |
| 6 | `--from sol --hops 6` | 2 | 145.7s | 57.0s | −61% |
| 7 | `--from sol --to lave --hops 6` | 1 | 11.8s | 8.4s | −29% |
| 8 | `--from sol --to lave --hops 6` | 2 | 130.3s | 87.2s | −33% |

One-hop open (not in the table: wall is startup-dominated): planner-
internal time on the big-candidate shapes fell ~10× (641ms → ~60ms from
Sol; 91,584 candidates fetched → 5 read).

## What run set 5 establishes

1. **The early stop fires almost everywhere and the skip rates carried
   into production.** Worst shape (run 6): stops fired in 285 of 313
   calls; 780k rows read against the old code's full candidate volume.
   P1's simulated skip rates (~86–94% of rows) held within a few
   points.
2. **Open multi-hop halves or better; jump range pays the most.** The
   j2 shapes drop 53–61% — bigger bubbles have longer ceiling tails,
   so the stop removes more. j1 shapes drop 15–50% on the same
   mechanism, scaled by bubble size.
3. **Fixed-terminal improves a third, not a half, and stays the
   slowest family.** Two structural reasons, both measured: the
   destination envelope changes per layer, so the reachable-memo and
   qualification bubble-skip reuse the open engine rides is disabled
   (memo 104/159 hit/miss vs the open twin's 137/176; per-call fetch
   268ms vs 165ms despite reading fewer rows — 534k vs 780k), and the
   real-budget floor sits lower than the open engine's optimistic one,
   so the stop bites later. Plus ~5× the jump-path time (10.3s vs
   2.3s) and the close-on-destination final hop.
4. **The fixed-vs-open crossover is geometric.** Probing sol→lave at
   2/3/4 hops (jumps 2): fixed wins 12× at 2 hops (1.5s vs 17.6s, the
   envelope taut from layer 1), break-even at 3 (25.4s vs 27.5s),
   loses from 4 up (48.3s vs 37.8s). The destination constraint pays
   while total reach is comparable to the separation; with slack, the
   envelope spends the early layers excluding nothing while its
   presence still disables cache reuse. Recorded lever (since taken
   and measured — see 5): a layer whose envelope exceeds its bubble
   constrains nothing and could be dropped from that layer's cache
   keys, giving early layers the open engine's reuse.
5. **The loose-envelope lever — taken and measured (2026-06-12),
   ledger closed.** Expansion calls now drop the envelope when it
   provably contains the anchor's whole reach bubble (triangle
   inequality, per call). Exact at the counter level: memo hits,
   candidate rows, stream rows read, and early stops identical with
   and without the change. The win was the per-call qualification
   re-check alone: qualification time −26%, wall −3.4% on the worst
   shape (85.9s → 83.0s) and −6% on its j1 twin (7.2s → 6.7s);
   taut-envelope shapes unchanged (zero drops). Finding 3's memo
   implication did not survive measurement: memo hit rates are
   identical with and without the envelope — the memo key never
   carried it — and the hit-rate difference against the open twin is
   frontier composition, not the envelope. The remaining fixed-vs-open
   gap is structural and stays: rows genuinely read under the
   real-budget floor, ~5× jump-path time, and the final-hop close on
   Y — the price of guaranteeing arrival. No further lever recorded;
   no fixed-terminal performance work is owed.

## Per-run diagnostics (key lines)

```text
[1] --from sol --hops 3 (j1) — 7.55s
  Total: 6626ms; fetch 6025ms, cargo 288ms, jump 8ms
  Expansion: 163 calls, memo 104/59; Stream: 260423 rows read, 16099 stations, 139 stops
  Qualification: 49916 stations, 300013 rows, 1239ms

[2] --from sol --hops 3 --jumps 2 — 28.86s
  Total: 27782ms; fetch 25491ms, cargo 546ms, jump 1023ms
  Expansion: 163 calls, memo 81/82; Stream: 398093 rows read, 39252 stations, 139 stops
  Qualification: 208178 stations, 1276471 rows, 5059ms

[3] --to lave --hops 3 (j1) — 4.03s
  Total: 3144ms; fetch 2776ms, cargo 218ms, jump 6ms
  Expansion: 130 calls, memo 64/66; Stream: 197348 rows read, 7388 stations, 102 stops
  Qualification: 23651 stations, 130472 rows, 537ms

[4] --to lave --hops 3 --jumps 2 — 14.17s
  Total: 13045ms; fetch 11827ms, cargo 428ms, jump 444ms
  Expansion: 130 calls, memo 44/86; Stream: 264318 rows read, 14236 stations, 100 stops
  Qualification: 154478 stations, 727075 rows, 2876ms

[5] --from sol --hops 6 (j1) — 15.94s
  Total: 14649ms; fetch 13204ms, cargo 704ms, jump 16ms
  Expansion: 313 calls, memo 165/148; Stream: 571517 rows read, 37657 stations, 286 stops
  Qualification: 87384 stations, 543545 rows, 2111ms

[6] --from sol --hops 6 --jumps 2 — 57.03s
  Total: 55685ms; fetch 50891ms, cargo 1006ms, jump 2260ms
  Expansion: 313 calls, memo 137/176; Stream: 779794 rows read, 72001 stations, 285 stops
  Qualification: 261241 stations, 1556208 rows, 9084ms

[7] --from sol --to lave --hops 6 (j1) — 8.35s
  Total: 7310ms; fetch 5848ms, cargo 345ms, jump 14ms
  Expansion: 263 calls, memo 81/182; Stream: 193501 rows read, 13132 stations, 112 stops
  Qualification: 39688 stations, 214266 rows, 1633ms
  Final hop: 23 attempted, 23 reach destination, 372 market candidates, 23 viable

[8] --from sol --to lave --hops 6 --jumps 2 — 87.15s
  Total: 85689ms; fetch 70043ms, cargo 903ms, jump 10287ms
  Expansion: 263 calls, memo 104/159; Stream: 534048 rows read, 52980 stations, 203 stops
  Qualification: 234888 stations, 1389068 rows, 9481ms
  Final hop: 50 attempted, 40 reach destination, 1269 market candidates, 40 viable
```
