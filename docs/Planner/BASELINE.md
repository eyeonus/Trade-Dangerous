# trade run Planner — Baseline

The required startup read. It says **what the planner does now**, **what rules
still bind future work**, and **what is still owed**. It deliberately does not
retell how each slice was built — that history lives in `SLICE_SUMMARY.md` and
the per-slice plans / completion reports, kept on disk as deep reference.

The companion file `SPEC_STATUS.md` is the option-by-option coverage map of the
black-box spec; read it (not the whole 33 KB spec) to see what is implemented,
what was deliberately varied, and what is still to do.

---

## Where we are

The clean-room rewrite of `trade run` has reached a working baseline. Every
basic route shape is served by the new planner, the legacy route/preload
architecture is retired, and the EDDN listener has been brought forward to the
current database surface. What remains is the route-modifier and
search/display option surface — see "What's still owed".

---

## Architecture boundary

```text
CLI parser -> RunRequest -> planner -> RunResult -> renderer
```

New planning logic begins past the neutral `RunRequest` DTO; everything the
planner returns is a `RunResult`. No legacy objects cross either boundary, and
the planner queries the database directly — it never pre-loads the galaxy into
memory (the legacy behaviour this rewrite exists to remove).

The planner package is `tradedangerous/planner/`. Route planning is split by
shape:

| Module | Responsibility |
|--------|----------------|
| `run_route.py` | Dispatch only (`plan_route`, `_plan_single_hop`). |
| `route_onehop.py` | Single-hop planners — fixed / open-ended / unanchored. |
| `route_anchored.py` | Fully-anchored multi-hop (`--from X --to Y`). |
| `route_single_anchor.py` | Part-anchored multi-hop front (one open end). |
| `route_unanchored.py` | Fully-unanchored multi-hop (both endpoints omitted). |
| `route_common.py` | Frontier/beam machinery, the shared open-anchor expansion engine, generic helpers. |

Supporting modules: `data_gateway.py` (all SQL/candidate queries),
`cargo.py` (the cargo optimiser), `reachability.py` (jump paths),
`resolver.py` (name resolution), `render_text.py` (renderer),
`run_request.py` (request DTO + parsing/normalisation),
`run_result.py` (result DTO), `score.py` (the protected ls-penalty curve),
`validation.py`, `failures.py` (typed exceptions).

Dependency direction is one-way: `route_common` -> planners -> dispatch.

---

## Planner Architecture Rule — Shared Semantics, Specialised Engines

The planner intentionally uses specialised route engines. Do not collapse them
into a generic route engine for architectural neatness.

The engines may differ in search strategy, SQL shape, pruning, frontier
management, temporary-table use, and other performance-critical mechanics.

However, route engines must not independently define the meaning of user
options.

For every new `trade run` option:

- The option's meaning must be resolved once into canonical request state.
- Engine modules may consume that canonical state in engine-specific ways.
- Engine modules must not each grow their own semantic implementation of the
  same option.
- Avoid creating parallel helpers such as:
  - `route_onehop._avoid()`
  - `route_anchored._avoid()`
  - `route_single_anchor._avoid()`
  - `route_unanchored._avoid()`

If engine-specific handling is needed for performance, name and structure it as
an adapter to the shared meaning, not as a new interpretation of the option.

Correct pattern:

```text
shared option meaning
    -> canonical RunRequest / constraint state
        -> engine-specific query/search application
```

Incorrect pattern:

```text
each route engine parses, resolves, or decides the meaning of the option itself
```

Short rule:

```text
Do not unify the engines.
Do unify the contract.
```
---

## What works now

### Route shapes — the grid is complete

| Hops | `--from` & `--to` fixed | `--from` only | `--to` only | both omitted |
|------|------|------|------|------|
| **one-hop** | fixed pair | open destination | open origin | unanchored galaxy |
| **multi-hop** | fixed-terminal | open destination | open origin | fully unanchored |

- Endpoints may be a **station** or a **system**; a system endpoint expands to
  its eligible stations and the planner picks the best pair.
- **Multi-jump per hop** (`--jumps-per >= 2`) works for every shape. Same-system
  movement is supercruise, not a jump.
- The two galaxy-wide shapes (one-hop and multi-hop, both endpoints omitted)
  are gated behind an interactive confirmation prompt — they are slow by nature.

### Cross-cutting behaviour

- **Endpoint name resolution** — `--from` / `--to` / `--towards` resolve once at
  dispatch through the shared `TradeORM` lookup: exact, then prefix, then
  substring (no typo tolerance). Syntax picks the namespace, with no
  cross-namespace fall-through: a bare name (optionally `@`-prefixed) is always
  a **system**, `/name` is always a **station**, `system/station` is a station
  within the named system(s), `system/` is the named system. A bare miss
  reports `unknown system: …`; a station-form miss reports `unknown station:
  …`; every error and candidate list names a System or a Station — never
  "place". A non-exact match echoes `… resolved as …`. Genuine duplicate system
  names disambiguate by `@N` with coordinates (`Name@N — (x, y, z)`, ordered by
  Galactic X); a bare collision lists the candidates, a bad index reports the
  valid range. Partial-name candidates are gathered against a stored normalised
  `lookup_name` key — a true superset of the Python matcher, so the SQL
  prefilter never hides a match. The planner consumes the resolved endpoint DTOs
  on `RunRequest`; the database handle never enters the planner. (The
  `lookup_name` column this relies on, and other schema edits made alongside
  this work, are documented in the main-refactor docs — schema surface is
  recorded there, not in the planner docs.)
- **Cargo optimiser** — bounded branch-and-bound, multi-commodity; the bound is
  admissible (proven exact against a brute-force harness). Destination demand is
  a hard quantity cap, not just an eligibility threshold. Callers pre-filter:
  a candidate pair whose admissible ceiling cannot beat the worst pair currently
  kept skips the solve, and pairs are solved best-first so the threshold rises
  fast. Exact (routes unchanged); it is what makes the real-budget shapes
  (fixed-terminal, one-hop open) fast — the fixed-terminal Sol→Lave run dropped
  285s → 46s, the one-hop open from Sol 8m40 → ~5s.
- **Bulk-sale-tax cap** — Metals/Minerals destination quantity capped at
  `floor(demand * 0.25)` to avoid the in-game bulk-sale price penalty.
- **`--max-price`** — absolute commodity-price cap (default 1,500,000 cr/t),
  clipping carrier-fiction rows. `--max-price 0` disables it.
- **`--ls-penalty`** — the protected travel-time curve (defined in the spec,
  implemented in `score.py`). Untouched.
- **Route output** — expanded plain-text per-hop and cumulative figures for
  manual audit; partial-route warnings; the bulk-tax cap note.
- **`--jumps-per` keyed default** — omitted `--jumps-per` defaults to 2 when
  `--ly-per <= 12.5`, otherwise 1.
- **Empty-jump positioning** (`--start-jumps` / `--end-jumps`) — a named
  `--from` / `--to` is treated as a positioning anchor, not a forced trade
  endpoint; eligible origins (or destinations) expand from its system within N
  empty jumps. `--empty-ly` sets the unladen fan-out range, falling back to
  `--ly-per`. The empty repositioning flight is shown in the route output.
- **`--towards`** — steers an open-destination route toward a target system
  without forcing arrival (requires `--from`; mutually exclusive with `--to`).
  Each hop must land strictly closer to the target, ranked progress-first:
  closest wins, then fewer hops, profit only breaking ties — so it heads
  directly at the target and does not meander to chase profit. A hop reaching
  the target ends the route ("arrived after N hops"); if the hops run out first
  it gets as close as it can. The "MAY optimise profit" in the spec is read as
  the optional permission it is, subordinate to the "MUST move closer" rule.
- **`--direct`** — the relocation run. Plans the single most profitable trade
  between a fixed `--from` and `--to` with no jump-path or distance checks; the
  commander flies the route themselves. Requires both endpoints, single hop only
  (mutually exclusive with `--hops`). `--ly-per`/`--jumps-per` are tolerated but
  ignored; `--towards` and empty-jump positioning are rejected as contradictory.
  The hop carries no jump path and shows as a direct leg in the route output.
- **`--avoid`** — excludes a commodity, system, or station from a route. Tokens
  resolve once at dispatch (repeated / comma-separated, fuzzy-matched like the
  endpoints): a slash means a place, a bare token is a system or commodity,
  resolved precision-first with a place winning a same-tier tie. An avoided
  commodity is never bought (so never carried or sold); an avoided station is
  never a route station; an avoided system is barred as a route station *and*
  from every jump path — the permit case, since a permit-locked system cannot be
  entered even in transit. The explicit `--from` is exempt as the origin: you may
  start in an avoided system, but the route never returns to it.

### Legacy retired

`trade run` is planner-only. The legacy `trade run --old` path, `TradeCalc`, the
full-galaxy preload model, and `TradeDB` are gone from live code (archived).
`TradeORM` is the single DB handle. The EDDN listener was repointed off the
retired `tradedb`/`cache` modules onto `TradeORM`. Argument validation is single
too: the legacy command-layer checker was removed, leaving the planner's
`validate_run_request` (on the neutral `RunRequest`) as the one validator —
parser-level mutual exclusions (`--to`/`--towards`/`--loop`,
`--direct`/`--hops`) stay at the argument parser.

---

## Rules that still bind future work

### Query discipline

The live dataset is large (~800K stations, ~19M `StationItem` rows). Spatial
constraints narrow the candidate set in SQL **before** joining to market data;
filtering, joins, and set membership stay in SQL; never materialise an id column
into a Python list to hand back as a large `IN (...)`. The full rules are in the
project `CLAUDE.md` ("Query work belongs in the database", "Query shape —
spatial constraints first") — this is the single most important constraint for
the filtering work coming next.

### Filter semantics — a settled contract

`--black-market`, `--fleet-carrier`, `--settlement`, `--planetary` are
accepted-state **sets**, normalised in `run_request.py`
(`_normalise_state_filter`). Match test:
`(station_state or "?").upper() in requested_states`.

```text
Y    known yes        N    known no         ?    unknown
Y?   yes or unknown   N?   no or unknown    YN   yes or no, excludes unknown
YN?  every state — equivalent to no filter (normalised away)
```

`--pad-size` is a single **ship-fit threshold** — `S`/`M`/`L` meaning "the ship
needs at least this pad". A station qualifies when its largest pad is at least
the requested size:

```text
L    large-max stations only
M    medium- or large-max, plus unknown-pad
S    every station, including unknown-pad
```

`?`, multi-letter values, and anything not `S`/`M`/`L` are rejected. An
unknown-pad station is admitted unless `--pad-size L` is set. Full reasoning in
`tuples.md`.

### Market-data facts

- **No default age limit.** With no `--age`, every row is used whatever its age
  — deliberate (supports the `olddata` relight playstyle). `--age` is the user's
  opt-in lever.
- **Markets have two independent sides.** A station may legitimately supply only
  (origin only) or demand only (destination only); mid-route stations must do
  both. The planner handles one-sided stations; legacy did not.
- **`_MIN_MEANINGFUL_DEMAND = 2`** (`data_gateway.py`). A stocked commodity
  reports its dormant buy side as 0 or 1, so a destination market counts only
  when `demand_units >= 2`.
- **`demand_level` / `supply_level` are hardcoded `-1`** by `spansh_plug.py` —
  no information; do not use them as a signal.
- **Carrier dominance.** Unanchored winners are overwhelmingly fleet-carrier
  trades (owner-set prices carry the extreme-margin tail). This is a correct
  reading of the data, not planner bias; execution risk is the user's to manage
  via `--age` / `--fleet-carrier` / `--supply` / `--demand`, and the
  `--max-price` default clips the extreme-price fiction.

### Settled decisions — do not re-litigate

- **No separate "cannot afford cargo" diagnosis.** Affordability failure is
  folded into the "No profitable trade" family deliberately — proving the
  distinction is expensive and rarely matters. Do not add an affordability-only
  probe unless a cheap signal falls out of the main path.
- **Bulk-sale-tax cap is conservative on purpose** — full price on a safe
  quantity, no discounted-price modelling, until the post-25% curve is better
  understood.
- The `--ls-penalty` curve is **protected behaviour** — change only on an
  explicit contract change.

---

## What's still owed

The authoritative, option-by-option status lives in **`SPEC_STATUS.md`**. In
short, the route shapes, empty-jump positioning, `--towards`, `--direct`, and
`--avoid` are done; what remains is the rest of the modifier and display surface
— `--via`, `--loop`, `--unique`, `--shorten`, `--loop-interval`, and the
search/display controls
(`--routes > 1`, `--max-routes`, `--prune-*`, `--checklist`, `--x52-pro`). Three
options (`--show-jumps`, `--summary`, `--progress`) parse without error but
currently do nothing — see `SPEC_STATUS.md`.

Agreed-but-unscheduled decisions and noted-for-later items:

- **`--sco` flag** — declares an SCO drive; clamps `--ls-penalty` to 0. UX
  signalling (flag / ship profile / journal) to resolve when it lands.
- **`--bulk-tax-mode`** — decided. If ever built, the switch does one thing:
  turn the cap **off** (fill to full demand at headline price) as an escape
  hatch from the safe default. The third "estimate" mode — model the post-25%
  sliding-scale discount — is dropped: that curve is community speculation, not
  documented behaviour, so there is nothing sound to model. Moot for now;
  revisit only if the curve is ever properly documented.
- **`--max-gain-per-ton` default** — the filter works; giving it a sane default
  cap (a different axis from `--max-price`) is an unscheduled idea.
- **Unanchored candidate-query restructure** — investigated and **parked**
  (per-system extrema discarding multi-commodity pairs; `--ls-penalty` applied
  after the bounded SQL slice). 144 axis-uplift checks surfaced zero
  higher-scoring winners; mechanisms hold but current data/scorer don't make
  them change a winner. Re-evaluation triggers recorded in
  `fifth_slice_restructure_implementation_plan.md`.
- **Shared expansion-cost floor** — **done**, both halves. The *cargo* half is
  the Slice 22 pre-filter (skip solving pairs that cannot place). The *fetch*
  half landed in Slice 23: the open-ended candidate queries are narrowed in
  SQL by the fixed side's per-item price bounds, so open-side rows that could
  never pair never leave the database (exact — candidates unchanged; the big
  open multi-hop shape 159s → 83s). Residual, unscheduled: fetch is still the
  dominant cost on the multi-hop shapes — the EXISTS probe stops rows being
  materialised, but the database still walks the reachable stations' market
  rows to evaluate it. Cutting deeper means a different query shape.
  Performance only.
- **`nav` / `olddata` rebuild** — parked for the main refactor's checkpoint L.
- **Listener loose ends** — the 15A change is committed in the listener repo;
  the client path and a full spansh import are assumed-working pending a real
  run.
- **MariaDB end-to-end** — the multi-jump, unanchored, and bulk-tax paths use
  dialect-portable patterns but were verified on SQLite.

---

## Reference map

| Need | Read |
|------|------|
| Option-by-option implementation status | `SPEC_STATUS.md` |
| The behavioural contract (the "Bible") | `trade_run_black_box_spec.md` |
| Full slice-by-slice history | `SLICE_SUMMARY.md` |
| Per-slice plans and completion reports | `INDEX.md` |
| Filter semantics, in depth | `tuples.md` |
| Data-scale and query posture | `notes.txt`, project `CLAUDE.md` |
| Parked unanchored restructure | `fifth_slice_restructure_implementation_plan.md` |
