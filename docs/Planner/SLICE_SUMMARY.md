# trade run Planner Rewrite — Slice Summary

Condensed record of the `trade run` planner-rewrite slices. This document is the
required startup digest: read it instead of the per-slice implementation plans
and completion reports, to save session context. It is appended to as each
slice completes.

The full per-slice plans and completion reports remain in `docs/Planner/` for
reference when detail is genuinely needed.

---

## Architecture boundary

```text
CLI parser -> RunRequest -> planner -> RunResult -> renderer
```

The new planner is the package `tradedangerous/planner/`. `trade run` uses it;
`trade run --old` routes to the quarantined legacy planner purely for
comparison. `selectNeeds()` returns `Needs.RESOLVER` for the new path and
`Needs.FULL_LEGACY` for `--old`. The new path's speed comes from selecting
`Needs.RESOLVER` and so avoiding the legacy full-database preload — not from
lazy imports.

---

## Slice 1 — First Safe Slice (complete)

Fixed station-to-station, single-hop planning.

**Supported shape:** `--from <station> --to <station> --capacity --credits --hops 1 --jumps-per --ly-per`.

**Delivered:**

- Planner package created: `__init__`, `failures`, `run_request`, `run_result`,
  `validation`, `cargo`, `score`, `reachability`, `resolver`, `data_gateway`,
  `run_onehop`, `render_text`.
- Command integration in `run_cmd.py`, `commandenv.py`, `tradeorm.py`;
  `trade run --old` added as the comparison path.
- Cargo: bounded branch-and-bound multi-commodity optimiser; destination demand
  is a hard quantity cap; no greedy-as-correctness.
- Reachability: same-system supercruise and single-jump coordinate-distance
  checks. Multi-jump (`--jumps-per >= 2`) deliberately deferred — raises
  `ReachabilityImplementationMissing`.
- Parser corrections: `--black-market` changed from a boolean switch to a Y/N/?
  state filter; `--fleet-carrier` and `--settlement` derived from
  `Station.type_id`.

**Verified:** same-system and one-jump cross-system runs; cargo/profit/credit
arithmetic; validation and typed-failure handling; unreachable-route rejection.

---

## Slice 2 — One-Hop Expanded Endpoints (complete)

`--from` and/or `--to` may be a **system**; the planner expands a system
endpoint to its eligible stations and selects the best one-hop station pair.

**Supported shapes:** all four station/system combinations for `--from` and
`--to`, including same-system.

**Delivered:**

- Endpoint resolution distinguishes a fixed station endpoint from a system
  endpoint needing expansion. Scoped `System/Station` input resolves the station
  within that system only — never a global fallback.
- System expansion is bounded to the named system (not galaxy search).
- Station-level filters applied SQL-side during expansion: `system_id`, market,
  pad size, planetary, no-planet, black-market, max-ls, fleet-carrier,
  settlement.
- One-hop station-pair matrix: every source station x destination station
  evaluated; self-pairs skipped on `station_id` equality (not raw text, so
  future fuzzy matching stays safe).
- Best pair selected by practical score, raw profit as tie-breaker.

**SQL-side pruning in force:** station filters during expansion; market role
filters; min-supply / min-demand; age cutoff; gain-per-ton; affordability of at
least one unit; self-pair skip before reachability/market/cargo work.

**Known tradeoff:** the candidate query prunes unaffordable commodities in SQL.
A pair whose only profitable commodities all exceed available credits may be
classed as "no profitable trades" rather than "no affordable cargo". This is
intentional on the hot path.

**Post-Slice-2 audit (commit `750448a2`):** the planner code was audited and
corrected — the cargo branch-and-bound fractional upper bound (unaffordable
items must `continue`, not `break`, since candidates are profit-sorted, not
price-sorted); the per-pair candidate query shape (selective join first,
diagnostic probes only on the zero-result path); and the ORM->DTO boundary
(`ResolvedSystem` DTO instead of a leaked ORM `System`).

---

## Slice 3 — Open-Ended One-Hop Search (complete)

`--from` supplied, `--to` omitted — the planner selects the destination,
finding the best one-hop trade from the fixed origin to any reachable station.

**Supported shape:** `--from <station|system>` with `--to` omitted, alongside
the fixed-endpoint shapes from Slices 1 and 2. An omitted `--to` requires
`--jumps-per 0` or `1`.

**Delivered:**

- `plan_onehop_route` dispatches on whether `--to` was supplied: fixed
  endpoints take the Slice 1/2 path, an omitted `--to` takes the open-ended
  destination search. Shared result-building is factored into
  `_assemble_result`.
- Destination resolution is staged so spatial narrowing runs first: a bounding
  box on the indexed `System.pos_x/y/z` columns, refined by an exact
  squared-distance test, yields in-range system ids; those drive the
  station-attribute filter; the market table is touched only afterwards.
- The market query fetches origin supply rows and destination demand rows as
  two single-table queries, each driven by its station-id set through the
  `StationItem` primary key, and matches them on `item_id` in Python. A single
  self-join lets SQLite scan the market table galaxy-wide by `item_id`, the
  cause of a `--pad-size S` pathology (~154s) the split query removed (~3s).
- `_MIN_MEANINGFUL_DEMAND = 2`: a destination market row counts only when
  `demand_units` is 2 or more, screening the dormant buy side of stocked goods
  (see Project Notes — Commodity supply and demand values).
- Unknown-pad stations are admitted unless `--pad-size L` is set (see Filter
  Semantics — Pad size).
- The `--jumps-per` default changes from 2 to 1.

**Verified:** validation tranches A–E and the run-short Colonia benchmark,
spot-checked against `--old`. Routes match where the planners' filter models
are comparable; the run-short benchmark was byte-identical. The one notable
divergence was the new planner correctly declining a trade to a station with
`demand_units` of 1 — an unfillable destination `--old` accepts. Open-ended
search returns in ~3s against 7–30s for `--old`.

**Deferred (not cut):** an omitted `--from`, both endpoints omitted, and
multi-jump open-ended search. These must reach the new planner before `--old`
is retired at v13.

Full record: `docs/Planner/third_slice_completion_report.md`.

---

## Slice 4 — Open-Ended Origin Search (complete)

`--to` supplied, `--from` omitted — the planner selects the origin, finding
the best one-hop trade into the supplied destination from any reachable
station.

**Supported shape:** `--to <station|system>` with `--from` omitted, alongside
every fixed-endpoint shape (Slices 1-2) and the omitted-`--to` shape (Slice 3).
At least one of `--from` / `--to` must be supplied; both omitted is rejected.

**Delivered:**

- Slice 3's open-ended destination search is generalised, not duplicated, into
  one parameterised path. `_best_open_destination_plan` becomes
  `_best_open_ended_plan`, keyed on `open_role` — the trade role of the
  endpoint the planner selects. Only the fixed-endpoint derivation reads
  `open_role`; resolution, candidate query, pair evaluation, scoring, and
  result assembly are direction-agnostic.
- `plan_onehop_route` dispatches three ways: both endpoints fixed ->
  `_plan_fixed_endpoints`; one omitted -> `_best_open_ended_plan` with the
  matching `open_role`; both omitted -> rejected in validation.
- `fetch_open_ended_trade_candidates` assigns the fixed and spatially-reached
  station sets to the supply and demand queries from `open_role`.
- Fixed-side and open-side station DTOs merge into one
  `station_id -> ResolvedStation` map; the pair loop resolves either side
  without a direction branch.
- Validation: `--from` is no longer required; the both-omitted shape is
  rejected (`UnsupportedRunShape`); the omitted-endpoint `--jumps-per` guard
  applies to whichever endpoint is omitted.

**Reachable-station query shape:** the `--to "Sol"` dense-region validation
command exposed a query that did not scale. The open-ended candidate query
constrained `StationItem.station_id` with a station-id list materialised into
Python and passed back as a literal `IN (...)`. A short list keeps SQLite on
the `StationItem` primary key; a list of thousands of ids flips it to a
galaxy-wide commodity-index scan (`ANY(item_id)`) — millions of page reads.
The reachable set is now a SQL subquery: `_reachable_station_id_query` returns
a `Select`, composed into the candidate query with `.in_(<subquery>)`, which
holds the primary-key plan. `--to "Sol"` returns in ~2.5s against a prior
multi-minute non-completion. The lesson is recorded in the project `CLAUDE.md`
("Query work belongs in the database").

**Verified:** the omitted-`--from` shapes (station, system, `--jumps-per 0`);
the Slice 3 open-destination set and the run-short benchmark re-run after the
query-shape change, unchanged; the both-endpoint shapes; the two new failure
checks (`UnsupportedRunShape`, no traceback). Dense-region performance
verified on `--to "Sol"`.

**Post-completion audit:** a source-level audit found the open-ended search
over-excluding the fixed endpoint — its whole station set was passed as a
blanket exclusion to the open-side reachable query, which for a system fixed
endpoint emptied the open set under `--jumps-per 0` and suppressed valid
same-system trades under `--jumps-per 1`. Corrected to a pair-level invariant
(commit `db82e655`): the reachable set stays broad, self-pairs are screened
per pair at candidate assembly (`source != destination`), and the failure
probe `any_reachable_station_pair` answers pair existence so a lone fixed
station still classifies as `NoReachableRoute`.

**Deferred (not cut):** both endpoints omitted (the unanchored galaxy search),
and multi-jump open-ended search. These must reach the new planner before
`--old` is retired at v13.

Full record: `docs/Planner/fourth_slice_completion_report.md`.

---

## Slice 5 — Unanchored Galaxy Search (complete; restructure investigated and parked)

Neither `--from` nor `--to` supplied — the planner selects both endpoints,
finding the best one-hop trade anywhere in reachable range. The one-hop
family is now complete.

**Supported shape:** `trade run` with both `--from` and `--to` omitted,
alongside every fixed and open-ended shape from Slices 1-4. Both omitted
still requires `--jumps-per 0` or `1`.

**Delivered:**

- `plan_onehop_route` dispatches four ways: both endpoints fixed, `--from`
  only, `--to` only, and neither. The last routes to `_plan_unanchored`, a
  separate additive path that shares no body with the anchored open-ended
  search — the unanchored search differs in kind, not in a parameter.
- `fetch_unanchored_trade_candidates` is the galaxy-wide candidate query —
  exhaustive in consideration, bounded in materialisation. A reachable-system
  map is built once per run as a run-scoped temporary table; each commodity
  is reduced to its cheapest supplier and dearest buyer per system, and
  matched through the map. Commodities are walked in descending
  profit-per-unit bound order; the walk stops once `capacity x bound` cannot
  beat the best concrete trade found, so only a handful of commodities are
  examined and the candidate set never approaches the galaxy.
- The per-system reduction uses a `ROW_NUMBER` window function — standard
  SQL, no reliance on any backend's handling of non-grouped columns — so the
  query is backend-portable.
- `run_cmd` gates the both-omitted shape behind an interactive confirmation:
  it warns the search is slow and asks before planning. A non-affirmative
  answer or a non-TTY invocation exits cleanly with guidance, no traceback,
  the planner never invoked. Validation runs before the prompt, so a command
  that cannot run fails immediately rather than after a confirmation the
  planner would then refuse.
- `prefer_in_memory_temp_storage` in `db/utils.py` holds the run-scoped
  temporary tables in memory — on SQLite via `PRAGMA temp_store`, which the
  reachable-system map (millions of rows) needs to avoid a disk-file spill;
  other backends are a documented no-op. The anchored planner and query
  functions are unmodified.

**Verified:** the both-omitted shape for `--jumps-per 1` and `0`, against
`--old` — the new planner returns a valid route in ~83s where `--old` takes
~293s on the same hardware. The prompt's affirmative, non-affirmative,
bare-Enter and non-TTY paths; `--jumps-per >= 2` rejected before the prompt
with no traceback; the run-short Colonia benchmark and the Slice 1-4 shapes
unchanged.

**Performance:** the unanchored search is the slow one-hop shape by nature,
roughly one to two minutes against a warm database, dominated by the
one-time reachable-system map build. The confirmation prompt exists for
exactly that reason.

**Deferred (not cut):** multi-jump per-hop reachability (`--jumps-per >= 2`)
and multi-hop routing (`--hops > 1`) — the larger body of work still ahead.

**Source-level audit:** Tromador audited the unanchored search against the
source after sign-off. Three localised remediations applied on `release/v1`:
temp identifier columns flipped from `Integer` to `BigInteger` for MariaDB
portability (commit `a80e5ae4`, proven against MariaDB on a Linux VM);
self-pairs excluded in SQL rather than later in `_group_pairs`
(`ee9a0a52`); per-commodity ranking key changed from unit profit to
capacity/supply/demand/limit-capped total profit, expressed with portable
nested CASE (`8b3fa02a`).
Two structural findings — per-system extrema discarding multi-commodity
station pairs, and `--ls-penalty` applied after the bounded SQL slice —
plus a credits-affordability follow-up, were taken to a planned
restructure of the unanchored candidate query and investigated
empirically. Six probes (P1–P6, captured in
`fifth_slice_restructure_implementation_plan.md`) ran against the live
dataset under both no-`--age` and realistic `--age 1/2/7` data shapes,
testing whether α (widened K), δ (per-pair full menu), ε (credits in
the SQL rank), or a wider top-N slice produces a higher-scoring
practical winner. Result: 144 axis-uplift checks, zero higher-scoring
winners surfaced. **Restructure parked**; findings accepted as
mechanically real but monitored / not implemented. The mechanisms
hold; current data shape and the locked scorer do not make them affect
winner selection. Re-evaluation triggers and the carrier-dominance
observation are recorded in the restructure plan.

Full record: `docs/Planner/fifth_slice_completion_report.md`.

---

## Project Notes

### Data scale

`Station` has ~800K rows; `StationItem` has ~19M rows. Candidate queries must
stay aggressively selective and prune as early as possible, ideally in SQL.
Reducing the selected row set takes priority even where dead rows might aid
error granularity. Default posture: trust established invariants; avoid
speculative edge-case probes; push filtering into SQLAlchemy/DB predicates; use
Python-side validation only as a safety net on already-narrowed result sets; do
not add classification work unless it changes a real user-facing outcome or
prevents an observed failure.

### Multi-hop diagnostic granularity

Slice 2 uses lightweight aggregate failure tracking across the bounded one-hop
station-pair matrix — cheap because every pair is evaluated anyway. Before
extending from one-hop to multi-hop route expansion, reassess this: rich
rejection-state tracking across a combinatorial route frontier increases
complexity, memory churn, and pruning burden. Likely policy — keep detailed
aggregate errors for bounded one-hop evaluation; use coarse failure
counters/reasons for multi-hop by default; reserve richer telemetry for an
explicit diagnostics/debug mode.

### Distance calculation

`research/notebooks/DistanceCalc.ipynb` records micro-benchmarks of Euclidean
system-distance computation. The result that matters here: when a distance is
only being compared against a radius, test the un-rooted sum of squares against
the squared radius and skip the square root entirely. This is the basis for the
Slice 3 spatial query filtering on `<= L*L` in SQL rather than computing a
square root. The notebook's remaining content is Python-side micro-optimisation
(`dx*dx` over `dx**2`, a cached `sqrt` lookup) — largely moot for the planner,
which does distance work in SQL, not in a Python hot loop.

### Market data path

Market data reaches a route through stages, and only the first is the true
source:

```text
Spansh (bulk) + EDDN/ZMQ (live)  ->  TradeDangerous database  ->  trade run
```

`Spansh` provides a full-galaxy dump used as a bulk baseline (`spansh_plug.py`;
a full import takes hours). `EDDN` over ZMQ provides the live stream — the
freshest data, as commanders visit stations. These two are the upstream
origins.

`eddblink` is **not** an upstream source. It downloads an already-built
TradeDangerous database — normally the project server's — itself assembled from
Spansh and EDDN. Same schema; `trade run` would route against it directly. When
tracing where a stored value originates, look at `spansh_plug.py` and the
listener, not `eddblink`.

### Market data freshness

There is **no default age limit**. With no `--age`, every row is used whatever
its age. This is deliberate: no `--age` means the user wants everything. It also
supports the `trade olddata` playstyle — import the full Spansh dump, keep the
archaeology, and seek out long-unvisited stations to relight them by
republishing their markets. A default cutoff would silently remove that.
`--age` is the user's opt-in lever; the GUI persists it so it is set once.

Freshness is a lifecycle, not a fault. The project server purges old data on
its own configured schedule; a local database is never pruned unless the user
runs `eddblink`'s clean option, so it grows organically. Stale rows are
therefore expected — old fleet-carrier data especially will accumulate.

### Markets have two independent sides

Buying and selling at a station are independent. Fleet-carrier owners set their
markets by hand and price freely (pricing is not game-driven). So a station can
legitimately **supply only** (sell, buy nothing) or **demand only** (buy, sell
nothing). This drives a routing rule:

```text
supply-only station   can only be a route origin
demand-only station   can only be a route destination
mid-route station     must do both (multi-hop)
```

The legacy planner assumes every station both buys and sells — an assumption
from before fleet carriers existed — so it discards one-sided stations. The new
planner handles them, and can therefore find trades the legacy path cannot.

A route may legitimately end at a station whose own goods are not worth
carrying onward (low-value bulk such as biowaste is still valid supply).
Deciding where to draw the line on whether an end station's onward stock is
worth anything is not worth the development cost, and is deliberately not
attempted.

### Carrier dominance in unanchored winners

Across the P1–P6 probe sweeps (full record in
`fifth_slice_restructure_implementation_plan.md`), every unanchored
production winner under `--age 1/2/7` involved a fleet carrier on at least
one side of the trade. 88.9% had a carrier destination, 66.7% a carrier
source, 55.6% were carrier-to-carrier, and none were
non-carrier-to-non-carrier. Carrier markets carry the long tail of extreme
single-commodity margins because their prices are owner-set rather than
game-driven; the unanchored search correctly reports what the data
contains.

Titan Drive Component recurs in the P6 examples as a concrete case: it
is a required material for purchasing pre-engineered SCO drives at human
tech brokers, so demand is steady and supply is scarce, and carrier
owners price it freely. The unanchored search surfaces it because the
data legitimately shows extreme margins on it, not because of any
planner bias toward that commodity.

Carrier-backed routes are valid market observations and are not treated
as invalid. The user-side concern is **execution risk**, not planner
correctness: carrier stock and demand are player-controlled and can
change between an EDDN snapshot and a Cmdr's arrival, and the API
snapshot lag between observation and flight is unavoidable. The
`--age`, `--supply`, `--demand`, and `--fleet-carrier` Y/N/? filters
give Cmdrs the levers to control this. If execution risk becomes a
recurring complaint, the remediation is a Cmdr-facing filter or a docs
note, not a candidate-query change.

### Commodity supply and demand values

The importers copy the game's raw `supply` and `demand` figures verbatim. For a
commodity a station stocks and sells, the game reports the dormant buy side as
0 or 1; for one it only buys, the sell side is 0. A small `demand_units` on a
stocked item is therefore not a real buyer — it is the quiet other side of the
row. The planner treats a destination market as real only when `demand_units`
is 2 or more (`_MIN_MEANINGFUL_DEMAND` in `data_gateway.py`).

The `demand_level` and `supply_level` columns are hardcoded to `-1` by
`spansh_plug.py` and carry no information — do not use them as a signal.

### Runaway unit-profit prices and a possible default `--max-gain-per-ton` cap

Slice 6 testing surfaced an unanchored winner with Gold at a sell price of
~4.7M cr/ton. Gold's normal sell range is around 50K cr/ton; a ~100x figure
is almost certainly carrier price-edit noise — a price posted to EDDN
briefly, then changed, never available long enough for a Cmdr to execute.
Plausible motives include deliberate data-poisoning, or owners using a
carrier to move credits to an alt account. The planner cannot tell intent
from data; it correctly reports what the snapshot contained.

The Titan Drive Component routes that recur in unanchored winners (see the
Carrier dominance section above) are different in kind: TDC is a crafting
reagent for engineered SCO drives, genuinely scarce, and carrier-owners
price it freely — standard MMO auction-house economics. Those margins are
high but plausible; the Gold one is not.

Under discussion between Tromador and eyeonus: a default cap on
`--max-gain-per-ton` (value TBD) that would hide the obviously-artificial
extremes while leaving legitimate high-margin trades visible. Out of scope
for Slice 6; logged here so the surfaced case isn't forgotten.

Performance side-effect — the noise is not only an output-cleanliness
issue. `fetch_unanchored_trade_candidates` walks commodities in
descending profit-per-unit bound and stops when
`capacity * profit_bound <= best_total_profit`. A single carrier-noise
trade sets `best_total_profit` to an astronomical value on the first
commodity, and every legitimate commodity afterwards gets pruned.
Wall-clock therefore *appears* fast under noise and gets dramatically
slower with `--fc N` or any other filter that removes the noise — the
slow case is the real one. The early-cutoff acceleration measured
during Slice 6 validation runs is not representative of clean-data
performance.

---

## Filter Semantics Reference

Any work touching station or commodity filters must preserve these. The Y/N/?
state filters are a settled contract, implemented in `run_request.py`
(`_normalise_state_filter`). The pad-size model has been revised to a ship-fit threshold, implemented
as part of Slice 3 — see below.

### Y/N/? state filters — accepted-state sets

`--black-market`, `--fleet-carrier`, `--settlement`, and `--planetary` are
accepted-state **sets**, not three unrelated absolute modes:

```text
Y    known yes only
N    known no only
?    unknown only
Y?   known yes or unknown
N?   known no or unknown
YN   known yes or known no, excludes unknown
YN?  every state — equivalent to no filter (normalised away)
```

Match test: `(station_state or "?").upper() in requested_states`.

### Pad size — ship-fit threshold

Revised model, delivered in Slice 3.

`--pad-size` takes one ship pad size — `S`, `M`, or `L` — meaning "the ship
needs at least this pad". A station qualifies when its largest pad is at least
the requested size:

```text
L    large-max stations only
M    medium- or large-max stations, plus unknown-pad
S    every station — small, medium, large, or unknown pad
```

`?` is not a valid input: `--pad-size ?` (or `M?`, or any multi-letter value)
is rejected with a validation error.

A station whose own pad size is unknown qualifies whenever the threshold
admits a medium pad — under `--pad-size S`, `--pad-size M`, or no `--pad-size`
— and is dropped only under `--pad-size L`. The reasoning: almost every
station that is not a large starport still has at least a medium pad (orbital
outposts and most small planetary ports included), so a station whose pad is
merely unrecorded is a safe bet for a ship that would accept a medium pad
anyway. A ship that specifically needs a large pad cannot take that gamble.

This is a deliberate, accepted risk: under `--pad-size M`, an unknown-pad
station that turns out to be small-only would mis-route a ship that needs a
medium pad. It is judged worth taking for the extra reachable stations, and to
be revisited if it draws complaints.

The earlier model's "exclude large starports to find trades larger ships
cannot reach" use case is deliberately not carried over — simplicity was
judged to outweigh it.

---

## Deferred Decisions

Agreed direction not yet scheduled into a slice — pick these up when the
relevant slice opens.

### `--jumps-per` default keyed to `--ly-per`

Slice 3 changes the `--jumps-per` default from 2 to 1. Tromador and eyeonus
have since agreed to refine that default further: it should depend on
`--ly-per`. Their reasoning — the 2026 game's larger average jump ranges make
2 jumps per hop one too many for most ships; the exception is a new player
still flying a starter ship, whose short jump range shows up as a low
`--ly-per`.

The rule applies to the **default only** — an explicit `--jumps-per` always
wins:

```text
--ly-per <= 12.5    default --jumps-per 2
--ly-per >  12.5    default --jumps-per 1
```

Considered for Slice 4 and deferred: the new planner cannot yet fly a 2-jump
hop — `plan_jump_path` raises `ReachabilityImplementationMissing` for any
cross-system hop with `--jumps-per >= 2` — so a default of 2 is meaningless
until multi-jump per-hop reachability exists. The keyed default belongs with
the slice that delivers that capability. Until then the flat default of 1
stands.

### `--sco` flag

A new option declaring the user's ship has a Supercruise Overcharge drive.
When set, it clamps `--ls-penalty` to 0 and overrides any user-supplied
`--ls-penalty` value — the in-system travel-time concern the curve solves
is materially weaker for SCO-equipped ships, which can reach distant
stations in seconds rather than minutes of supercruise.

```text
--sco set        --ls-penalty treated as 0
--sco not set    --ls-penalty works as today
```

Not scoped into any current slice. How the user signals SCO ownership —
per-run flag, persisted ship profile, journal detection — is the UX
question to resolve when the option lands.

---

## Cleanup Candidates

Noted-for-later items — not bugs, no urgency, worth doing when convenient.

### `--pad-size` CLI parser message mismatch

The shared `--pad-size` CLI parser (`PadSizeArgument.PadSizeParser` in
`commands/parsing.py`) still validates and describes the older combination
model: it accepts any string of `S`/`M`/`L`/`?` characters, and its error
message and help text cite `SML?`-style combinations. `trade run` now treats
`--pad-size` as a single ship-fit threshold, and its planner-side validation
rejects `?` and multi-letter input separately.

Effect: an invalid `--pad-size` for `trade run` can fail at either layer with a
different message. A non-pad character such as `XL` is rejected by the parser
with the outdated combination wording; `?` or a valid-letter combination passes
the parser and is rejected by the planner with the correct "one of S, M, or L"
message. Rejection is always clean — no traceback — only the messaging is
inconsistent.

Not a simple message swap: `PadSizeArgument` is shared with `sell`, `buy`,
`local`, `nav`, and `olddata`, which still use the combination model. A fix
means either a `trade run`-specific pad parser and message, or accepting the
mismatch.

### `StationHasNoUsablePriceData` subclass wording

The planner-side raise messages for `SourceHasNoSellingData` and
`DestinationHasNoBuyingData` (in `planner/run_onehop.py`) still use internal
phrasing — "No reachable source station had usable selling data." and
similar. These are now surfaced through `PlannerResultError` without the
generic data-failure footer, so the wording is the only remaining issue;
"reachable" leaks an internal concept into a user-facing line. A small
follow-up could reword these to match the friendlier "no usable market
data for the chosen \<place\>" style used by the rest of the planner
failure messages. Out of scope for the failure-message cleanup that
introduced `PlannerResultError`.
