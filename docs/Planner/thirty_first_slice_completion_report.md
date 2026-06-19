# Slice 31 — Multi-Route Output (`--routes`), `--sco`, `--no-bulk-cap`, and Beam-Control Removal

*Proof of completion. Planned in `thirty_first_slice_implementation_plan.md`
(revised after audit — Findings 1–4 folded in); built in six commits, verified on
live data and at the unit level.*

---

## Summary

Four independent workstreams, three small and one substantial:

- **A — beam-control options removed.** `--max-routes`, `--prune-score`, and
  `--prune-hops` were inert legacy levers; `trade run` now rejects all three as
  unknown options.
- **B — `--sco`.** Declares a Supercruise Overcharge drive; forces the ls-penalty
  input to 0, so distant stations are not penalised.
- **C — `--no-bulk-cap`.** Off-switch for the Metals/Minerals bulk-sale demand
  cap; fills the full demand at the headline price.
- **D — `--routes N`.** Returns up to N final routes instead of just the winner,
  on every shape, best-first by the engine's existing final-route rank.

Commits:

| Commit | What |
|--------|------|
| `b1f7ab4d` | A — remove the beam-control parser args, request fields, validation gates. |
| `7da543c3` | B — `--sco` flag; clamp ls-penalty to 0 in request normalisation. |
| `c478f5e7` | C — `--no-bulk-cap`; request-aware sensitivity-resolver wrappers. |
| `c09141da` | D — `--routes N` for the single-hop shapes; validation un-gate. |
| `f8baafa7` | D — `--routes N` for the multi-hop shapes (fixed-terminal, open-anchor). |
| `e34767e4` | Docstring fix (stale return wording on `best_fixed_pair_trades_from`). |

State docs (`SPEC_STATUS.md` / `BASELINE.md`) updated in `0464c65a`.

---

## The contract reading — `--routes`

`--routes N` returns **up to** N final valid routes, ordered by the engine's
existing final-route rank, with deterministic tie-breaks.

- **Top-N by rank, not by raw score.** For ordinary routes the rank is practical
  score; under `--towards` it is the progress-first rank (closest, then fewer
  hops, then score). The shared `_route_progress_rank` is the one ordering.
- **N is a maximum, not a quota.** Return however many valid routes exist; fewer
  than N is not a failure.
- **No diversity key.** "Best N by rank" is a deliberate reading of the spec's
  display-count wording — not "N meaningfully different routes". Near-duplicates
  are accepted; a distinctness key is a later, evidence-driven change.
- **`--routes 1` is byte-identical** to the pre-`--routes` single-winner path on
  every engine — the inert proof, the same discipline `--towards` / `--unique`
  used.

---

## Mechanism

### A — beam-control removal

Parser arguments, `RunRequest` fields, and the validation gates for the three
options were removed. With no parser entry, argparse raises its existing
unrecognised-option error — the `--shorten` treatment. The beam already owns
frontier width and pruning (the spec permits an equivalent pruning policy), and
the user-facing beam-width idea was rejected earlier (`beam_width_analysis.md`).

### B — `--sco`

A boolean flag. In `run_request` normalisation, when `--sco` is set the parsed
`--ls-penalty` value (CLI default 12.5) is overridden to `0.0` before the frozen
`RunRequest` is built. `score.py` is untouched — the protected curve already
returns a multiplier of 1.0 at penalty 0, so `--sco` only feeds it a 0.

### C — `--no-bulk-cap`

The cap rides on a `sensitive` flag derived from two session-cached resolvers
(`_bulk_sale_tax_category_ids`, `_bulk_sale_tax_sensitive_item_ids`). Two
request-aware wrappers (`_effective_sensitive_category_ids` /
`_effective_sensitive_item_ids`) return an empty set under the flag, so nothing
reads as sensitive and the cap evaporates uniformly at every site — effective
demand, the min-demand floor, the category exclusions, the `* 0.25` SQL floor.
The empty path bypasses the session cache, so it never overwrites the real
resolved set for a later capped run on the same session.

### D — `--routes N`

**Validation.** The `routes != 1` gate is replaced by `--routes < 1`
(`InvalidNumericOption`) and `--routes > 1` with `--checklist`
(`ContradictoryOptions`, currently shadowed by the checklist gate).

**Five selection seams, each turning keep-best into keep-best-N:**

- **One-hop** (`route_onehop`, all three subpaths — fixed endpoints, open-ended,
  unanchored). A bounded `_KeptPairs` collector replaces the single `best_pair`
  (keep=1 reduces to the old single-best selection). The kept-score threshold
  widens from 1 to `request.routes`, so the streaming early stop fires against
  the Nth-best score. `_assemble_result` builds one route per kept pair.
- **Fixed-terminal** (`route_anchored`). `best_fixed_pair_trade_from` becomes
  `best_fixed_pair_trades_from(…, top_k)`, returning the top-K closes per
  frontier node (top_k=1 reproduces the single best), so a strong prefix can put
  several arrivals into the final pool (audit Finding 3 / Option 2). Finalists
  are chosen top-N by a stable reverse sort, so `--routes 1` selects the same
  single winner `max()` chose.
- **Open-anchor** (`route_common`). The credit-correction loop keeps the best N
  corrected routes in a bounded `_KeptRoutes` collector instead of one
  `best_route`. The exact early-stop is N-aware: it fires only once N are held
  and the next finalist's optimistic rank cannot beat the Nth-best corrected
  route. keep=1 reduces to the old single-best loop.

**`_multihop_result`** gained an `extra_routes` parameter (default empty), so the
single-route callers — partial routes, the correction fallback, and `--via` —
stay byte-identical (`routes = (route,) + extra_routes`).

---

## Verification

**Static / unit (worker).** flake8 and import clean on every touched module. The
two bounded collectors were unit-tested directly: `_KeptPairs` and `_KeptRoutes`
each return a correct best-first top-N, and keep=1 returns the single best
(`_KeptRoutes.worst_rank()` returns the held route's rank, matching the old
single-route early-stop comparand).

**Live data (eyeonus).**

- **A** — `--max-routes 5` rejected as an unrecognised argument.
- **B** — `--sco` and `--ls-penalty 0` produced a byte-identical 5-hop route, and
  both differed from the default run. (Proven by equivalence to a *known* value,
  not difference from an arbitrary one — the robust test. The penalty only flips
  a winner when a distant station is competitive, which is rare on a single hop
  and near-certain across five, so multi-hop is the natural place to read it.)
- **C** — Rutile, `Laedla → Arque`, `--direct`: capped at 40 t (`floor(161/4)`)
  with the bulk-tax note by default, filled to 161 t with `--no-bulk-cap`, note
  gone, profit 1.29M → 3.57M. Cobalt (also Metals/Minerals) on the same hop
  confirmed the cap lifts across every sensitive commodity, not just one.
- **D, one-hop** — `--routes 1` byte-identical to the plain run; `--routes 3`
  returned three distinct destinations correctly ordered by score.
- **D, multi-hop** — `--routes 1` byte-identical on the open-anchor and
  fixed-terminal shapes; `--routes 3` returned distinct chains, best-first.

---

## Variances from plan

- **Build order.** The plan ordered A → B → C → D. D was split — one-hop built and
  its inert proof confirmed on live data before the same top-N pattern was
  replicated into the trickier multi-hop engines. Lower-risk, and it validated
  the approach on the simplest seam first.
- **`--via` left at single-route output.** The plan's five seams covered one-hop,
  fixed-terminal, and open-anchor; `--via` runs its own lane-diversity owner with
  a separate `_multihop_result` call, so `--routes N` on a via route still
  returns one route (valid under N-as-maximum). A via top-N is a future seam, not
  owed here.
- **Renderer unchanged (Finding 4).** `render_text.py` already iterates
  `result.routes`, numbers when more than one, and separates — no seam needed.
- **Fixed-terminal Option 2 is near-free.** The close helper already runs
  jump-path, fetch, and cargo for every destination; the top-K variant changes
  only what is retained, not the work done.

---

## Housekeeping

- `best_fixed_pair_trades_from` docstring corrected to match the list return.
- `SPEC_STATUS.md`: `--routes` / `--sco` / `--no-bulk-cap` to done; the beam
  options and the Pruning controls section to removed; four new variations.
- `BASELINE.md`: cross-cutting bullets for the three options, a beam-removal
  settled decision, the owed and unscheduled lists trimmed, headline updated.
