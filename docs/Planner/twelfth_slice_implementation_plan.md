# Slice 12 Implementation Plan — Planner Module Split and Cruft Sweep

## Status

Complete. Implemented on `release/v1` (commit `f676cfaf`); see
`twelfth_slice_completion_report.md`.

## Purpose

Pure structural rationalisation, now the planner shapes have settled. Two
outcomes:

1. **Split `run_route.py`** (2,331 lines, holds every planner) into one module
   per planner shape, behind the existing dispatch surface.
2. **Sweep out accumulated cruft** — code used by an earlier slice, dropped by a
   later one, never removed; and stale process-language comments/strings.

This is the "split the planner orchestration into per-shape modules" follow-on
recorded as deferred in the Slice 11 plan.

**No behaviour change.** The split is a move, not a rewrite: every supported run
shape must come out identical. The only output-text change on the table is the
optional rewording of two user-facing error strings (a flagged decision below).

## Guard rails

- No algorithm change. Correctness is verified by "every supported shape comes
  out byte-identical before and after."
- Clean-room intact — no legacy module is read or touched.
- `plan_route` stays importable from `tradedangerous.planner.run_route`.
  `run_cmd.py`'s only planner-search import (`from
  tradedangerous.planner.run_route import plan_route`) is unchanged — zero churn
  outside the package.
- Minimal-scope edits. Imports change as code moves; nothing else is reformatted
  or rewritten.

## Target module layout

`run_route.py` keeps the name and becomes the thin dispatch surface, so its one
external import stays valid. The planners move out beneath it. One shared module
holds what more than one planner reuses.

| File | Holds |
|------|-------|
| `run_route.py` | Wrapper / dispatch: `plan_route`, `_plan_single_hop`. |
| `route_onehop.py` | One-hop — fixed, open (`--from` / `--to`), and unanchored — plus the pair machinery they share. |
| `route_anchored.py` | Fully-anchored multi-hop (`--from X --to Y --hops N`) and the two trade primitives only it uses. |
| `route_single_anchor.py` | Part-anchored multi-hop (one open end: `--from X` or `--to Y`), its optimistic primitive, correction pass, and helpers. |
| `route_common.py` | Shared toolkit: the multi-hop frontier/beam machinery and the generic helpers used across shapes. |

The deferred **fully-unanchored** multi-hop (`--hops N`, both ends omitted) is a
future planner module when that shape lands — a sixth file, not part of this
slice.

### Allocation rule

> Used by more than one planner → `route_common.py`.
> Used by exactly one planner → that planner's own file.

Applied, this keeps the shared surface small. Notably, **none of the three trade
primitives is shared** — each queries the gateway independently:

- `best_open_ended_trades_from` (forward, real-budget) → `route_anchored.py`
- `best_fixed_pair_trade_from` (fixed final hop) → `route_anchored.py`
- `best_open_ended_hop_candidates` (optimistic) → `route_single_anchor.py`

So `route_common.py` carries frontier mechanics and helpers, **not** candidate
generation.

### Contents per file

**`run_route.py`** — `plan_route`, `_plan_single_hop`.

**`route_onehop.py`** — planners `_plan_fixed_endpoints`, `_best_open_ended_plan`,
`_plan_unanchored`; pair machinery `_PairPlan`, `_best_pair_plan`,
`_pair_is_better`, `_assemble_result`, `_raise_empty_open_search`,
`_anchor_system_from_endpoint`.

**`route_anchored.py`** — planner `_plan_multi_hop`; primitives
`best_open_ended_trades_from`, `best_fixed_pair_trade_from`.

**`route_single_anchor.py`** — planner `_plan_open_anchor_multi_hop`; primitive
`best_open_ended_hop_candidates` and its helper `_reverse_jump_path`; helpers
`_make_open_child`, `_correct_open_anchor_chain`, `_best_open_anchor_partial`,
`_finalise_correction_stats`; constants `_OPTIMISTIC_PRICE_PER_TON`,
`_OPEN_ORIGIN_CORRECTION_WIDTH`.

**`route_common.py`** — structs `_FrontierNode`, `_HopCandidate`; beam-width
constants `_MULTIHOP_EXPANSION_WIDTH`, `_MULTIHOP_FRONTIER_WIDTH`; frontier
helpers `_multihop_result`, `_best_partial_node`, `_make_child_node`,
`_reconstruct_route`; generic helpers `_stations_from_endpoint`,
`_system_from_station`, `_group_pairs`, `_elapsed_ms`.

(The dead `with_render_timing` is **removed**, not moved — see the sweep.)

## Dependency direction (no cycles)

```text
existing lower layers: run_result, run_request, failures, score, cargo,
                       reachability, resolver, data_gateway, validation
        ^
route_common      (imports lower layers only)
        ^
route_onehop      route_anchored      route_single_anchor
        ^                ^                     ^
        +--------- run_route (wrapper: imports the three planner modules) ----+
```

One way, top to bottom. The shared toolkit **cannot** fold into the wrapper: the
wrapper imports the planner modules to dispatch to them, so a planner importing
its helpers back out of the wrapper would be a circular import. That is why the
shared module earns its own file.

## Cruft sweep

`flake8 -F` (pyflakes) is already clean across the package — no unused imports.
The cruft is at the function/comment level, which pyflakes cannot see.

### Dead code — referenced nowhere in the whole repo, safe to delete

| Item | Location | What it is |
|------|----------|-----------|
| `with_render_timing` | `run_route.py` (~8 lines) | Orphaned helper, never called. |
| Resolver dead cluster | `resolver.py` (~90 lines) | The superseded "resolve a bare station" path: `StationReference`, `parse_station_reference`, `resolve_station`, `_resolve_station_reference`, `_resolve_exact_station_global`. Replaced by `resolve_endpoint`. Self-contained cascade — `_find_exact_stations_global` stays (live path). |
| `ReachabilityImplementationMissing` | `failures.py` | The early guard for "multi-jump not implemented yet". Multi-jump shipped; the class is dead and its docstring ("no permitted implementation yet") is now false. |
| `MarketQuote` | `run_result.py` | A DTO nothing uses; superseded by `TradeCandidate`. |

### Stale process-language comments — reword (no behaviour change)

Probe/slice labels meaningless to a future reader; keep the reasoning, drop the
label:

- `run_route.py` — `# ... (P2) keep both at 50 ...` and `# ... per probe P1`.
- `data_gateway.py` — `# The reach map that prior slices used ...`.

(Leave the legitimate technical uses untouched: `data_gateway.py`'s "top slice" /
"bounded slice" comments mean rows-of-a-result, and `phase=` in the renderer and
DTOs is a real field name, not process language.)

## Decisions (resolved)

1. **User-facing "planner slice" wording — left as-is.** The "*… is not supported
   for this planner slice.*" messages in `validation.py` were kept unchanged: they
   are removed when the deferred options they guard (e.g. `--prune-hops`) are
   implemented, so there was nothing worth carrying forward, and leaving them kept
   the slice at zero output change.

2. **`PlannerCancelled` — removed.** The typed failure was never raised or caught;
   removed as dead code, trivially re-added when cancellation is wired.

## Sequencing

Each numbered step is one commit for review; the tree imports and runs after
every step. Bottom-up extraction means `run_route.py` shrinks gradually while
staying valid.

1. **Cruft sweep.** Remove the dead code (and `PlannerCancelled` if approved);
   reword the stale comments (and the user-facing messages if approved). Done
   first, while it is all still in one place, so the moves that follow are pure.
2. **Extract `route_common.py`** — the shared structs, constants, frontier
   helpers, and generic helpers. Update references in `run_route.py`.
3. **Extract `route_onehop.py`** — the one-hop planners and pair machinery.
4. **Extract `route_anchored.py`** — the fully-anchored planner and its two
   primitives.
5. **Extract `route_single_anchor.py`** — the part-anchored planner, its
   primitive, helpers, and constants.
6. **Reduce `run_route.py`** to the wrapper (dispatch only) and finalise the
   import wiring.
7. **Docs** — update `SLICE_SUMMARY.md` and `INDEX.md`; completion report after
   sign-off. (Docs commit is separate from the code, per the project workflow.)

## Validation

No automated harness (project decision). The proof is identical output. After
the sweep, and again after the split, re-run a representative command from each
supported shape and diff against a pre-change capture:

- run-short Colonia benchmark (same-system one-hop).
- Fixed-pair one-hop; open `--from` one-hop; open `--to` one-hop.
- Fixed-terminal multi-hop (Sol → Lave, 3 hops).
- Open-destination multi-hop (`--from X --hops N`).
- Open-origin multi-hop (`--to Y --hops N`).

All must be byte-identical before/after, except the two reworded error strings
(if approved), which only change wording on those specific failure paths. An
`import tradedangerous.planner.run_route` check after each extraction step
confirms the package still wires up.

The dead-code removals cannot change output — the code is unreachable. The
comment rewords cannot change output — they are comments.

## Files expected to change

```text
tradedangerous/planner/run_route.py          # reduced to wrapper/dispatch
tradedangerous/planner/route_common.py       # new
tradedangerous/planner/route_onehop.py       # new
tradedangerous/planner/route_anchored.py     # new
tradedangerous/planner/route_single_anchor.py # new
tradedangerous/planner/resolver.py           # dead cluster removed
tradedangerous/planner/failures.py           # dead exception(s) removed
tradedangerous/planner/run_result.py         # dead DTO removed
tradedangerous/planner/data_gateway.py       # one stale comment reworded
tradedangerous/planner/validation.py         # user-facing wording (if approved)
```

`cargo.py`, `score.py`, `reachability.py`, `render_text.py`, `run_request.py`,
and the parser are untouched.

## Noted, not done

- **`score.py` stays its own module.** It is small (54 lines) but holds the
  *protected* ls-penalty curve, is coherent, and is named for what it is.
  Folding a spec-protected curve into a grab-bag helpers file would lose
  readability, not gain it. `failures.py` likewise stays — it is the canonical
  exceptions module every module imports.
- **Public-name tidy (optional).** `best_open_ended_trades_from`,
  `best_open_ended_hop_candidates`, and `best_fixed_pair_trade_from` carry no
  leading underscore but are module-internal now (no external importer). They
  could be prefixed `_` for consistency. Left out by default as it touches
  identifiers; raise if wanted.
