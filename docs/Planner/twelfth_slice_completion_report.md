# Slice 12 Completion Report — Planner Module Split and Cruft Sweep

## Status

Complete on `release/v1`, commit `f676cfaf`
("refactor(planner): split route planning into per-shape modules").

## What this slice delivered

A pure structural rationalisation of the route planner — no behaviour change,
no new option. Two things:

1. **Module split.** `run_route.py` had grown to ~2,300 lines holding every
   planner shape. It is now split into one module per shape, behind an unchanged
   dispatch surface. This completes the planner-orchestration module split
   deferred at Slice 11.
2. **Cruft sweep.** Dead code accumulated across earlier work — superseded by
   later work but never removed — was deleted, and stale internal labels in
   comments were reworded.

## Module layout

```text
run_route.py            103   dispatch only (plan_route, _plan_single_hop)
route_onehop.py         576   fixed / open-ended / unanchored single-hop
route_anchored.py       594   fully-anchored multi-hop (--from X --to Y)
route_single_anchor.py  812   part-anchored multi-hop (one open end)
route_common.py         332   frontier/beam machinery + generic helpers
```

- `run_route.py`'s only public import, `plan_route` (used by `run_cmd.py`), is
  unchanged — zero churn outside the package.
- Dependency direction is one-way: `route_common` -> planners -> dispatch.
  `route_common` imports nothing from any `route_*` module, so there are no
  import cycles.
- The three trade-candidate primitives turned out to be single-planner — each
  queries the data gateway independently. (The forward primitive does not wrap
  the optimistic one; the earlier impression that it did was a docstring
  mention, not a call.) They therefore stay with their planner, and
  `route_common` carries no candidate-generation code, keeping the shared
  surface small.

## Cruft removed

Each was unreferenced across the entire repository before removal:

- `with_render_timing` — orphaned helper, never called.
- The superseded "resolve a bare station" path in `resolver.py`:
  `StationReference`, `parse_station_reference`, `resolve_station`,
  `_resolve_station_reference`, `_resolve_exact_station_global`. Replaced by
  `resolve_endpoint`; the `UnsupportedRunShape` import that path left orphaned
  in `resolver.py` was dropped in the same edit.
- `ReachabilityImplementationMissing` — the guard for "multi-jump not
  implemented yet". Multi-jump is implemented, so the exception and its
  "no permitted implementation yet" docstring were dead.
- `MarketQuote` — an unused DTO superseded by `TradeCandidate`.
- `PlannerCancelled` — a typed failure never raised or caught.

Comment rewords (no behaviour change): the probe/scheme labels "(P2)" and
"per probe P1", the phrase "the reach map that prior slices used", and
"Piece A's bubble cache" were reworded to state the reasoning rather than the
development step that produced them.

The user-facing "*… is not supported for this planner slice.*" messages in
`validation.py` were deliberately left unchanged: they are removed when the
deferred options they guard (e.g. `--prune-hops`) are implemented, so there was
nothing worth carrying forward, and leaving them kept the slice at zero output
change.

`score.py` (54 lines, the protected ls-penalty curve) and `failures.py` (the
canonical exceptions module every module imports) were kept as their own
modules — small but coherent, and clearer named than folded into a shared
helpers file.

## How it was done

The split was executed as a multi-agent workflow built around a deterministic
extractor, so no function body was ever retyped by hand:

1. **Snapshot** — the current `run_route.py` was copied and an AST script
   captured every top-level symbol's exact source text (decorators and leading
   comments included) into a JSON map.
2. **Extract** — four agents in parallel assembled the new modules by
   concatenating the captured source for their assigned symbols, then settled
   each module's imports using flake8 as the oracle (remove unused, add
   missing).
3. **Slim** — `run_route.py` was rebuilt from the captured `plan_route` and
   `_plan_single_hop` source plus the new import block.
4. **Verify** — in parallel: a whole-package import (including `run_cmd`), a
   full flake8 pass, and an AST parity check.

The workflow scaffolding (snapshot, symbol map, build/verify scripts) lived
under `research/perf/` and was removed at slice close; it was never committed.

## Verification

- **Import:** the whole planner package and `tradedangerous.commands.run_cmd`
  import cleanly.
- **flake8:** zero output across `tradedangerous/planner/`.
- **AST parity:** every top-level symbol from the pre-split snapshot is present
  exactly once across the five modules — no duplicates, none missing, none
  extra, and no `ast.unparse`-normalised code differences. This is the core
  correctness gate: it proves the executable code is identical, only relocated.
- **Live data:** the run-short Colonia benchmark returned its expected
  same-system route (49,717 cr); a 3-hop `--from "Sol" --to "Lave/Lave Station"`
  run returned a valid, affordable three-hop route (3,656,064 cr) with healthy
  diagnostics.

## Deferred (not cut)

Unchanged from Slice 11, less the now-completed module split:

- The shared expansion-cost floor (narrow candidate rows before cargo fitting).
- Fully-unanchored multi-hop (`--hops N`, both endpoints omitted) — the next
  shape slice.
- All route modifiers and search/display controls still gated in validation.
