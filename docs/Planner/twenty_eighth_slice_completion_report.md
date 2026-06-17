# Slice 28 — Cargo Search "Confident Stop" and Diagnostics Gating

*Planned in-conversation, no separate implementation plan — as with Slices 20
and 23. Two changes from one session's work, plus this record and the
living-doc updates. Evidence base: `docs/Planner/exactness_study.md` (the
overnight study that motivated the first change).*

---

## Summary

1. **Cargo search confident-stop** (commit `bf0d7abb`) — the branch-and-bound
   cargo optimiser now stops when it is *confident* of the answer, not when it
   has *proved* it. A no-improvement early stop plus a far lower outer fuse.
   Routes unchanged; the slow fixed-terminal shapes ~3.6× faster.
2. **Diagnostics gated behind `-ww`** (commit `286fbd7f`) — the route
   diagnostics block is debug output, emitted only at debug level 2 (`-ww`) and
   up. Normal `trade run` output is now clean.

---

## 1 — Cargo search confident-stop

### The problem (mechanism)

The cargo optimiser's branch-and-bound ran until it had *proved* no better plan
existed, capped only by a 100,000-node safety fuse. The branching factor is the
hold size (the search loops over `range(max_quantity, -1, -1)`, up to 720
branches per item), so on large holds the search found the optimum early and
then spent tens of thousands of nodes per solve merely proving it. There is one
solve per candidate pair, so the cost was multiplicative across a route. The
fuse — meant never to be reached by a real problem — had become the normal
operating point.

### The change

- **No-improvement early stop** (`_SEARCH_NO_IMPROVEMENT_LIMIT = 500`): the
  search records the node at which it last bettered its incumbent and stops once
  it has gone 500 nodes with no further improvement — stopping when confident of
  the answer rather than paying to prove it. It resets on every improvement, so
  a search that is still genuinely improving runs on; only a plateaued one stops.
- **Outer fuse lowered** `_SEARCH_NODE_LIMIT` 100,000 → 2,000: a genuine safety
  net again, not the operating point.

Both are levers, tunable on evidence like the beam width.

### Evidence (the study)

- The route-determining cargo optimum is found **within ~25 nodes**; capping the
  search anywhere from 25 to 100,000 gave **identical route profit to the
  credit** on every shape tested.
- The slow path still earns its keep: on big holds the exact search beats its
  greedy seed by a mean ~11% per solve (up to 80% on individual solves — the
  seed is genuinely weak when credits bind), so it stays — it just stops
  grinding once it has the answer.
- The 350s "blow-up" is a fixed, front-loaded tax: the b&b solve count saturates
  at ~6,677 from 6 hops up and is flat across 6/8/10/12 hops — not exponential.

### Verification

- Headline `--from sol --to achenar --hops 8 --credits 5000000`: profit
  **105,181,521 — identical**, wall **354s → ~99s**, cargo **264s → 6.7s**, the
  shape fetch-bound again.
- Route-exact across hop counts 4–12, credits 500k–5M, two endpoints, and a cap
  floor down to 25.
- Open-destination cliff-check: 106,942,475 vs the prior 107,276,102 — a 0.31%
  difference from the 2,000 fuse acting on the open engine's finalist correction.
  Accepted as immaterial (≈300k on 107M).

### Why both, not just the fuse

A 2,000 fuse *alone* would make every big-hold solve grind to exactly 2,000 every
time — the fuse as operating point again, just smaller: the same anti-pattern.
The confident-stop is what makes the search stop because it is *done* (~525 nodes
here), leaving 2,000 as a genuine safety net that is almost never hit — the
correct structure, and the one that scales if holds ever grow.

---

## 2 — Diagnostics gating behind `-ww`

### The change

`render_run_result` gained a `debug` level (default 0) and emits the diagnostics
block only at level ≥ 2; `run_cmd.render` passes `cmdenv.debug`. `-w` is an
`action='count'` argument, so `-ww` is debug level 2 — and its help text is
already "Enable/raise level of diagnostic output", so this is exactly its
intended semantics. The diagnostics are debug detail, not verbose detail, so
they key off `-w`, not `-v`.

### Coverage (the audit that confirmed one gate suffices)

The planner has a single output path: it never prints — every route shape only
*builds* a `PlannerDiagnostics` DTO and returns it in the `RunResult`.
`render_text.py` is the sole renderer. So gating that one renderer covers every
shape:

- **Single-hop** diagnostics are the `hops_planned <= 1` branch of the same
  render helper (same module, different place).
- **`--via`** builds per-layer `LayerStats` into the same DTO — no prints of its
  own.

Verified empirically: single-hop, `--via`, and multi-hop all show **0**
diagnostics blocks at normal verbosity and the block at `-ww`. The GUI renders
its own way and is unaffected.

---

## Variances and notes

- `K` (500) and the fuse (2,000) are tunable levers.
- The broader cliff-check on the galaxy-wide unanchored shapes was not run; they
  share the open engine's optimistic-plus-correction structure, so the same
  reading is expected — a confirming run is owed before treating the change as
  validated there.
- The study's probe scripts and logs were deleted at slice close; its findings
  record is kept as `docs/Planner/exactness_study.md`, a standalone reference in
  the class of `beam_width_analysis.md` and `unanchored_loop_investigation.md`.

## Living docs

- `BASELINE.md`: the performance ledger, recorded as "closed, no lever owed",
  is reopened and addressed by change 1; plus the cargo-optimiser stop note and
  the `-ww` diagnostics gating under cross-cutting behaviour.
- `INDEX.md`: this slice entry.
- `SPEC_STATUS.md`: unchanged — no spec option is affected (the gating is
  output/verbosity, the cargo change is internal and route-preserving).
