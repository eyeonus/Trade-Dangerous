# Slice 31 — Multi-Route Output (`--routes`), `--sco`, `--no-bulk-cap`, and Beam-Control Removal

*Implementation plan — revised after audit (Findings 1–4 folded in; see §3, §5.3,
§5.6, §9). One slice, four workstreams — three small, one substantial. The
headline is `--routes N`: return up to N final routes instead of just the winner.
Alongside it, two small new options (`--sco`, `--no-bulk-cap`) and a housekeeping
removal of three inert beam-control options.*

---

## 1. Scope and shape

Four independent workstreams. They share no logic, so they can land in any
order; the plan builds the small isolated ones first and the engine work last.

| | Workstream | Size |
|---|-----------|------|
| **A** | Remove the beam-control options (`--max-routes`, `--prune-score`, `--prune-hops`) | small |
| **B** | `--sco` — declare an SCO drive; clamp the ls-penalty to 0 | small |
| **C** | `--no-bulk-cap` — turn off the Metals/Minerals safe demand cap | small |
| **D** | `--routes N` — return up to N final routes, top-N by rank | substantial |

Order: **A → B → C → D.** Each is a separate, reviewable step.

**Not in scope (deliberate):**

- **Route diversity.** `--routes N` means "the best N routes by the engine's
  existing final-route rank", not "N meaningfully different routes". If real runs show
  useless clone spam, a distinctness key is a later, evidence-driven slice — not
  this one. Building it now is speculative complexity.
- **`--checklist` / `--x52-pro`.** Still gated. The `--routes`/`--checklist`
  interaction rule is added (§5.5), but checklist itself stays unsupported.

---

## 2. Workstream A — Remove the beam-control options

`--max-routes`, `--prune-score`, and `--prune-hops` are legacy levers for the
old search algorithm. The new planner replaced that algorithm with the beam, so
they describe a job the beam already does:

- `--max-routes` is the beam width by another name (partial routes retained
  between expansion stages = `_MULTIHOP_FRONTIER_WIDTH`). Exposing the beam width
  as a user knob is the idea already considered and rejected in
  `beam_width_analysis.md`.
- `--prune-score` / `--prune-hops` are a percentage-threshold pruning policy. The
  beam's fixed top-K trim is an equivalent pruning policy, which the spec
  explicitly permits (spec §Pruning controls: "may use an equivalent or better
  pruning policy"). The beam-width sweep is the benchmark evidence.

So they are removed, not left gated — the `--shorten` treatment. After removal
the parser raises its existing unrecognised-option error.

| File | Change |
|------|--------|
| `commands/run_cmd.py` | Remove the three `ParseArgument` blocks (`--max-routes` `:277`, `--prune-score` `:297`, `--prune-hops` `:303`). |
| `planner/run_request.py` | Remove fields `max_routes` / `prune_score` / `prune_hops` (`:95–97`) and their `cmdenv` mapping (`:162–164`). |
| `planner/validation.py` | Remove the `unsupported_non_zero` entries (`:215–216`) and the `--prune-hops` gate (`:227–231`). Remove the now-empty `unsupported_non_zero` loop if nothing else uses it. |

Verification: `trade run … --max-routes 5` (and the other two) now fail as
unknown options; every other shape is unaffected.

---

## 3. Workstream B — `--sco`

`--sco` declares a Supercruise Overcharge drive. The behaviour (from BASELINE):
clamp the ls-penalty to 0, so distant stations are not penalised.

Confirmed from `score.py:21`: `ls_penalty_multiplier` returns `1.0` when
`penalty_percent <= 0`, so feeding it 0 disables the penalty.

**The default is 12.5, not 0 (Finding 1).** The `RunRequest` field default is 0,
but a normal CLI `trade run` receives the parser default `--ls-penalty 12.5`
(`run_cmd.py:206`), mapped straight into `ls_penalty_percent`. So an ordinary run
already carries a 12.5 penalty. `--sco` overrides whatever value was parsed —
explicit or the 12.5 default — and feeds `0.0` into the existing score curve.

Seam: in `run_request` normalisation, set `ls_penalty_percent = 0.0` when the
`--sco` flag is set, after the parsed `lsPenalty` has been read. `score.py` is
not touched — the protected curve is untouched; `--sco` only feeds it a 0.

| File | Change |
|------|--------|
| `commands/run_cmd.py` | New boolean flag `--sco` (dest `sco`). |
| `planner/run_request.py` | New `sco: bool` field; in normalisation, force `ls_penalty_percent = 0.0` when set. |

Interaction: `--sco` with an explicit `--ls-penalty` — `--sco` wins (penalty
forced to 0). Stated, not an error; it is the point of the flag. No validation
rule needed.

---

## 4. Workstream C — `--no-bulk-cap`

By default the planner caps Metals/Minerals destination quantity at
`floor(demand * 0.25)` to avoid the in-game bulk-sale price penalty.
`--no-bulk-cap` turns that off: fill the full demand at the headline price, the
escape hatch from the safe default.

The cap rides on a `sensitive` / `is_sensitive` flag threaded through many sites
in `data_gateway.py`. That flag derives from two session-cached resolvers:
`_bulk_sale_tax_category_ids(session)` and
`_bulk_sale_tax_sensitive_item_ids(session)`.

Clean off-switch: make the *resolution* return empty when the flag is set. With
no sensitive ids, every `in sensitive_*_ids` test is False, so `sensitive` is
False everywhere and the cap evaporates uniformly — full demand, the
`min_demand_floor` drops back to `_MIN_MEANINGFUL_DEMAND`, the sensitive-category
exclusions do not fire, and the `* 0.25` SQL floor is never reached. One seam,
not a dozen arithmetic edits.

Implementation: a thin request-aware wrapper for each resolver that returns
`frozenset()` when `request.no_bulk_cap` is set, otherwise delegates to the
cached resolver. The wrapper must **bypass** the cache on the empty path, not
write the empty set under the real cache key (which would poison a later run on
the same session).

| File | Change |
|------|--------|
| `commands/run_cmd.py` | New boolean flag `--no-bulk-cap` (dest `noBulkCap`). |
| `planner/run_request.py` | New `no_bulk_cap: bool` field. |
| `planner/data_gateway.py` | Request-aware wrappers around the two sensitivity resolvers; the ~6 call sites read the wrapper. Cache untouched on the empty path. |

Verification: a known Metals/Minerals run shows the cap binding by default (a
sensitive line at `floor(demand/4)`); with `--no-bulk-cap` the same line fills to
full demand. Non-bulk shapes unchanged.

---

## 5. Workstream D — `--routes N` (multi-route output)

The substantial workstream.

### 5.1 Contract

`--routes N` returns **up to** N final valid routes, ordered by the engine's
existing final-route **rank**, with deterministic tie-breaks. For
ordinary routes the rank is practical score; under `--towards` it remains the
existing progress-first rank.

- **N is a maximum, not a quota.** Return however many valid final routes exist;
  fewer than N is not a failure.
- **No diversity key.** Near-duplicates are acceptable for now (§1).
- **Acceptance criterion (documented verbatim):** *`--routes N` means "show the
  best N routes by the engine's existing final-route rank", not "show N
  meaningfully different routes".*

`--routes` is already parsed and carried (`run_request.routes: int = 1`); it is
only gated in validation today. The result DTO is already plural
(`RunResult.routes: tuple[PlannedRoute, ...]`), so no result-DTO change is
needed.

### 5.2 The N-aware selection rule

Each engine today finds **one** best route and early-stops once no remaining
candidate can beat it. That becomes a bounded top-N:

1. Keep the best **N** corrected/finalist routes (a bounded, sorted structure).
2. Only early-stop once you already hold **N** routes.
3. Compare the next candidate's optimistic upper bound against the **Nth-best**
   kept route, not the best.
4. **`--routes 1` reduces to today's path byte-identically** — the inert proof,
   as `--towards` / `--unique` / `--shorten` used. With N=1 the structure holds
   one route and the Nth-best *is* the best, so the comparison and the early-stop
   are the current logic unchanged.

This rule applies at every seam in §5.3.

### 5.3 The selection seams

There are **five**, not three — one-hop has three subpaths, each collapsing to a
single best route today (Finding 2). All five turn keep-best into keep-best-N.

**One-hop (`route_onehop.py`).** Three subpaths, all confirmed single-route:

- `_plan_fixed_endpoints` (`:39`) → `_best_pair_plan` returns one best pair →
  `_assemble_result(routes=(route,))`. Change: `_best_pair_plan` keeps the top-N
  pairs; `_assemble_result` builds a route per pair.
- `_best_open_ended_plan` (`:100`) → `_KeptScoreThreshold(1, …)` (`:159`) → one
  best pair. Change: threshold N; the stop floor becomes the Nth-best kept score
  once N are held; keep top-N pairs. Preserve `enabled=request.towards_target is
  None` (towards disables score-pruning).
- `_plan_unanchored` (`:317`) → `_KeptScoreThreshold(1, …)` (`:365`) → one best
  pair. Change: threshold N; keep top-N pairs; build up to N routes.

`_assemble_result` (`:615`) is generalised to build N routes from N pairs (today
it takes one `best_pair` and returns `routes=(route,)`). `--routes 1` passes a
one-element sequence → byte-identical output.

**Fixed-terminal multi-hop (`route_anchored.py`).** The final close
`best_fixed_pair_trade_from` (`:767`) returns the *single* best terminal trade
per frontier node, so "keep top-N finalists" alone is too narrow (Finding 3): a
prefix whose top three closes are 100 / 99 / 98 would surrender 99 and 98 to a
weaker prefix's 60. Since the contract is "best N by rank" and diversity is not
required, the close helper gains a top-K variant
(`best_fixed_pair_trades_from(…, top_k=N)`) so each prefix can contribute up to K
terminal candidates; final selection then takes the global top-N. **Low cost:**
the helper already runs jump-path, fetch, and cargo for every destination and
keeps the best — top-K changes only what is *retained*, not the work done.
`top_k=1` reproduces today's single close (confirm any internal pruning interacts
cleanly at build).

**Open-anchor multi-hop (`route_common.py`, `:1085–1166`).** The involved one.
The credit-correction loop re-fits each finalist against the real running budget
and tracks a single `best_route`; the early-stop (`:1096`) quits when the next
finalist cannot beat `best_route`. N-aware: keep a bounded top-N of *corrected*
routes; raise the early-stop threshold to the Nth-best corrected; respect the
existing correction-budget cap (`_OPEN_SHAPE_CORRECTION_WIDTH`). The shorter-chain
fallback (`_best_corrected_shorter_chain`, `:1873`) stays a **zero-results safety
net** — top-N draws from full-length corrected finalists; if zero corrected, the
fallback supplies one shorter chain. It is not a padder: if N=3 and only one
full-length route corrects, we return one.

The exact mechanics at each seam are confirmed at build (one step per engine
family); the shape — keep-best-becomes-keep-N, early-stop tests the Nth-best — is
uniform across all five.

### 5.4 Tie-breaks

Top-N ordering uses the shared `_route_progress_rank`. Where two routes tie on
that key, a deterministic secondary key (e.g. the route's station-id tuple)
fixes the order, so the output is stable run-to-run.

### 5.5 Validation

Replace the current `routes != 1` reject (`validation.py:233`) with:

- **`--routes < 1`** → rejected (spec §Early validation: "fewer than one
  requested output route").
- **`--routes > 1` with `--checklist`** → rejected (spec: "multiple displayed
  routes with checklist mode"). Currently moot — `--checklist` is itself gated —
  but the rule is correct for when checklist lands.

### 5.6 Renderer — verify only (Finding 4)

No change expected. `render_text.py` already iterates `result.routes` (`:32`),
numbers them when there is more than one (`:33`), and inserts a blank line
between them (`:38`). The work is to confirm the multi-route output reads well,
not to build a seam.

---

## 6. What this does NOT touch

- **Result DTO** — already plural; no change.
- **Renderer** — already iterates and numbers routes; verify only (§5.6), no new
  seam.
- **Cargo optimiser, `score.py` curve, beam widths, reachability** — untouched.
- **Diversity** — deferred (§1).
- **`--shorten`** — already removed from the contract; no compatibility shims.

---

## 7. Touch-point summary

| File | A | B | C | D |
|------|---|---|---|---|
| `commands/run_cmd.py` | remove 3 args | `--sco` flag | `--no-bulk-cap` flag | — |
| `planner/run_request.py` | remove 3 fields | `sco`, clamp ls-penalty | `no_bulk_cap` field | — |
| `planner/validation.py` | remove 2 gates | — | — | routes rules |
| `planner/data_gateway.py` | — | — | resolver wrappers | — |
| `planner/route_onehop.py` | — | — | — | top-N across all 3 subpaths; `_assemble_result` multi |
| `planner/route_anchored.py` | — | — | — | top-K close helper + global top-N |
| `planner/route_common.py` | — | — | — | top-N correction, Nth-best early-stop |
| `planner/render_text.py` | — | — | — | verify only (already multi-route) |

`run_result.py`, `cargo.py`, `score.py`, `reachability.py` — no change.

---

## 8. Verification

- **Inert proofs:** `--routes 1` (no flag) byte-identical before/after on
  benchmark shapes, on every shape; a run with no `--sco` and no `--no-bulk-cap`
  byte-identical.
- **A:** the three removed options now fail as unknown options.
- **B:** a plain run already carries the 12.5 ls-penalty default, so a plain run
  vs the same run with `--sco` added should differ — the `--sco` run scores as if
  ls-penalty were 0 (distant stations no longer penalised).
- **C:** a Metals/Minerals run shows the cap binding by default; `--no-bulk-cap`
  fills the same line to full demand.
- **D:** `--routes 1` matches the pre-change winner on every shape (the inert
  proof); `--routes 3` returns up to three rank-ordered routes on a
  fixed-terminal shape, on each one-hop subpath (fixed / open / unanchored), and
  on an open-anchor shape; a fixed-terminal prefix with several strong terminal
  closes contributes more than one of them to the top-N (Finding 3); a shape with
  fewer than N valid routes returns what exists (no failure); `--routes 0`
  rejected.

---

## 9. Decisions — resolved

1. **`--routes` first cut** → top-N-by-rank, no diversity key. Diversity is a
   later, evidence-driven slice. §1, §5.1.
2. **Beam-control options** → removed, not gated (the `--shorten` treatment). §2.
3. **`--no-bulk-cap` name** → chosen over `--bulk-tax-mode`, `--bulk-sell`,
   `--full-bulk-demand`, `--ignore-bulk-tax` (opt-out framing, matches the
   `--no-planet` convention). §4.
4. **N is a maximum** → return fewer if fewer valid routes exist; not a failure.
   §5.1.
5. **`--routes 1` byte-identical** → the inert proof governs the engine work, at
   every seam. §5.2.
6. **One-hop coverage is all three subpaths** (Finding 2) → fixed / open /
   unanchored each get the top-N treatment; `_assemble_result` builds N routes.
   §5.3.
7. **Fixed-terminal final close** (Finding 3) → Option 2, a top-K close helper,
   not the weaker one-close-per-prefix reading. Cheap, because the per-destination
   work already runs; only retention changes. §5.3.
8. **Renderer** (Finding 4) → already multi-route; verify only, no new seam. §5.6.
