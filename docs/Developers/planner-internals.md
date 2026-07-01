# Trade Run Planner — Internals

A deep dive into the `trade run` route planner: the engines that search for
trade routes and the machinery they share. Written for a developer or an AI
agent who needs to understand how the planner works before changing it, without
reverse-engineering the modules from scratch.

---

## 1. Purpose and scope

This document covers the **core** of the planner:

- the request/result boundary and how a request is dispatched to an engine;
- the route engines, one per route shape;
- the shared multi-hop expansion engine they sit on;
- the cargo optimiser, reachability, and scoring that every engine calls.

It deliberately leaves out the **peripheral surface**: the station and commodity
filters, name resolution, the bulk-sale-tax cap, and the per-option edge cases.
Those are either self-evident from the code or documented elsewhere. This is the
guts — the routing machinery, not the dials bolted to it.

Where the text points at code it uses `module.py:symbol`, so you can jump
straight there. File and line references are entry points ("start reading
here"), not a contract — line numbers drift, names are stable.

---

## 2. Background and the boundary

### Why the planner was rewritten

The original tool planned routes with two modules: `tradedb.py` and
`tradecalc.py`. Between them they ran a **preload-first** design.

`TradeDB` built an in-memory model of the galaxy. `TradeDB.load()` calls
`_loadSystems()`, `_loadStations()`, and `_loadItems()`, pulling systems,
stations, and market data up into Python objects before any planning began.
`TradeCalc` then searched routes (`getBestHops`) and fitted cargo
(`bruteForceFit` / `fastFit` / `simpleFit`) over that in-memory model.

That worked when the dataset was small. It stopped working as the game and its
data grew. A live database runs on the order of **800k stations, 19M
station-item (market) rows, and ~3 GB** on disk (the exact size varies — the
MariaDB backend is larger, and it moves with how often the DB is optimised and
which optional data, such as ship vendors, has been pulled). Loading that into
memory to plan one route is not viable: the preload alone dwarfs the route you
actually asked for, and most of what it loads is never looked at.

The rewrite removes the preload. The new planner **queries the database
directly** and pulls only the rows a given search needs, narrowing in SQL before
anything reaches Python. *"Do not load the galaxy"* is the single constraint the
whole design turns on, and most of the engine and fetch machinery exists to
honour it. The legacy modules are retired; `trade run` is served entirely by the
new planner.

### The boundary

The planner sits inside a fixed pipeline:

```
CLI parser → RunRequest → planner → RunResult → renderer
```

Two plain data objects form the boundary. Nothing planner-internal and nothing
command-layer-specific crosses them.

- **`RunRequest`** (`planner/run_request.py`) — a frozen dataclass holding the
  parsed, normalised inputs of one run: capacity, credits, endpoints, hop count,
  jump range, filters, and the *resolved-once* state (endpoint DTOs, avoid/via id
  sets, the towards target). `run_request_from_cmdenv()` is the only place the
  command environment is read; everything past it works from the DTO.
- **`RunResult`** (`planner/run_result.py`) — a frozen dataclass holding the
  planned `routes` (a tuple — the planner can return up to N), plus `diagnostics`
  and any partial-route `warnings`. The renderer consumes this and nothing else.

The DTOs that travel between them are worth knowing up front, because every
engine speaks in these terms:

| DTO | What it is |
|-----|------------|
| `ResolvedSystem` / `ResolvedStation` | A system / station hydrated from the DB with the fields the planner needs — coordinates, pad size, ls-distance, freshness. |
| `TradeCandidate` | One buy-here-sell-there opportunity: an item, its source and destination station, prices, profit per unit, available supply and demand. The atom the search reasons about. |
| `CargoPlan` / `CargoLine` | A filled hold — which commodities, how many units, the cost and profit. The cargo optimiser's output. |
| `JumpPath` | The jump route between two systems: the systems flown through, the polyline distance, the jump count. Reachability's output. |
| `PlannedHop` | One hop: source station, destination station, the cargo plan, the jump path, raw profit and practical score. |
| `PlannedRoute` | A sequence of hops with its stations, totals, and start/end credits. |

By the time an engine runs, the request carries **resolved state, not raw text**.
`--from` / `--to` / `--towards` / `--avoid` / `--via` are resolved to ids and
endpoint DTOs once at dispatch, so the planner never holds a database handle for
the purpose of resolving names. (Resolution itself is out of scope here — the
point that matters downstream is that engines consume canonical state and never
re-resolve.)

---

## 3. Module map

The planner is the `tradedangerous/planner/` package. The modules fall into five
roles.

**Boundary and DTOs**

| Module | Responsibility |
|--------|----------------|
| `run_request.py` | The `RunRequest` DTO and `run_request_from_cmdenv()` — parse and normalise the command-layer args once. |
| `run_result.py` | The `RunResult` DTO and the route/hop/cargo/jump DTOs the engines build. |

**Dispatch**

| Module | Responsibility |
|--------|----------------|
| `run_route.py` | `plan_route()` — validate, pick an engine by request shape, run post-processing. The single entry point. |

**Route engines — one per route shape**

| Module | Responsibility |
|--------|----------------|
| `route_onehop.py` | Single-hop planning: fixed pair, open-ended (one side chosen), and unanchored. |
| `route_anchored.py` | Fully-anchored multi-hop (`--from X --to Y`), grown toward a fixed destination; also serves `--loop`. |
| `route_single_anchor.py` | Part-anchored multi-hop (one open end): resolve the anchor, build a seed, hand off to the shared engine. |
| `route_unanchored.py` | Fully-unanchored multi-hop (both ends omitted): seed the shared engine galaxy-wide, grow forward. |
| `route_via.py` | `--via` waypoint routing — owns every via shape itself. |

**Shared engine machinery**

| Module | Responsibility |
|--------|----------------|
| `route_common.py` | The frontier/beam machinery, the shared open-anchor expansion engine, and the generic helpers the engines reuse. |

**Core services — called by every engine**

| Module | Responsibility |
|--------|----------------|
| `data_gateway.py` | All read-only SQL: candidate-trade queries, station hydration, the qualify-once temps. The only module that issues planning queries. |
| `cargo.py` | The bounded multi-commodity cargo optimiser. |
| `reachability.py` | Jump-path building and the reachable-systems bubble. |
| `score.py` | Practical-value scoring and the protected ls-penalty curve. |

**Edges** (mostly out of scope here, listed for orientation): `resolver.py`
(endpoint name resolution at dispatch), `validation.py` (request validation),
`failures.py` (typed exceptions), `render_text.py` / `render_rich.py` (renderers,
which consume the `RunResult`).

**Dependency direction is one-way:**

```
core services (data_gateway, cargo, reachability, score)
        ↑
route_common  →  the route engines  →  run_route (dispatch)
```

The engines depend on the shared machinery and the core services; dispatch
depends on the engines. Nothing in `route_common` or the core services imports an
engine or the dispatcher, so the dependency graph has no cycles. This is a
deliberate rule (see §12): engines may specialise their *search*, but they must
not each grow their own version of an option's *meaning* — shared meaning lives
below them, in `route_common` and the request DTO.

---

## 4. Dispatch

`run_route.plan_route(session, request)` is the one entry point. It does three
things: validate, dispatch, post-process.

**Validate once.** `validate_run_request(request)` runs here, so single-hop and
multi-hop share one input contract. Then `reset_cargo_counters()` zeroes the
diagnostics counters for this run.

**One reachability bubble cache per request.** A single `bubble_cache` dict is
created here and threaded into every engine. A "bubble" is the set of systems
reachable from one source system under the run's jump rules (see §9). Caching it
per request means a search that evaluates many destinations from a fixed origin
pays for that origin's reachability walk **once**, not once per destination.

**Dispatch by shape.** The engine is chosen from two things: whether `--via` is
present, the hop count, and which endpoints are named.

`--via` short-circuits ahead of everything — if any via waypoint is set, the run
goes to `route_via._plan_via_route`, which handles every via shape itself (and
requires an anchor; validation rejects a fully-unanchored via).

Otherwise the choice is a grid of **hop count × which endpoints are named**:

| | `--from` & `--to` | `--from` only | `--to` only | neither |
|---|---|---|---|---|
| **single-hop** (`hops == 1`) | `route_onehop._plan_fixed_endpoints` | `_best_open_ended_plan` (open_role=`destination`) | `_best_open_ended_plan` (open_role=`source`) | `route_onehop._plan_unanchored` |
| **multi-hop** (`hops > 1`) | `route_anchored._plan_multi_hop` | `route_single_anchor._plan_open_anchor_multi_hop` (open_role=`destination`) | `…_plan_open_anchor_multi_hop` (open_role=`source`) | `route_unanchored._plan_unanchored_multi_hop` |

`--loop` is dispatched with the fully-anchored multi-hop engine: a loop is a
fixed-terminal route whose terminal is its own origin, so the same engine serves
it.

**`open_role` — the key idea for the open shapes.** When exactly one endpoint is
named, *one* engine serves both directions, keyed by which side the planner is
choosing:

- `open_role="destination"` — `--from` is fixed, the planner picks the
  destination (the open-destination shape).
- `open_role="source"` — `--to` is fixed, the planner picks the origin (the
  open-origin shape), and the search grows the chain **backward** from the fixed
  end.

The same `open_role` keying appears in both single-hop (`route_onehop`) and
multi-hop (`route_single_anchor`), so neither side duplicates the other's logic.

**Post-process.** After an engine returns, `plan_route` applies the cross-cutting
touches no single engine should own:

- **`--towards` arrival** — `_annotate_towards_arrival` flags any route whose last
  station sits in the target system, recording how many hops it took. A
  `--towards` run that finds nothing is re-raised as `NoTowardsProgress` (naming
  the target), because every candidate the search saw was already filtered to
  forward progress.
- **Positioning legs** — for `--start-jumps` / `--end-jumps`,
  `_attach_positioning_legs` computes the empty repositioning flight between the
  named anchor and the route's real trading endpoints, using the unladen range
  (`--empty-ly`, else `--ly-per`) and a private bubble cache kept separate from
  the per-hop one.

---

## 5. Core concepts

Three ideas underpin every engine: the **trade candidate** (what the search
reasons about), the **score** (what "best" means), and the **beam** (how a
multi-hop search stays bounded). Defining them once here keeps the per-engine
sections short.

### 5.1 The trade candidate

A `TradeCandidate` (`run_result.py`) is one buy-here-sell-there opportunity: an
item, a source station, a destination station, the buy and sell prices, the
profit per unit, and the available supply and demand. It is the atom the whole
search works in — every engine ultimately assembles routes out of candidates,
and the data gateway's job is to produce the *right* candidates as cheaply as
possible (§10).

A candidate is a per-unit opportunity, not yet a plan. Turning a candidate (or
several, for a mixed hold) into an actual cargo load — how many units of each,
given capacity, credits, supply and demand — is the cargo optimiser's job (§8).

### 5.2 Scoring: raw profit vs practical score

Two numbers describe any hop or route, and the distinction runs through the DTOs
and the search:

- **Raw profit** — the credits actually made. `score.raw_profit_score(profit)` is
  just `float(profit)`. Carried as `raw_profit` on a hop, `total_raw_profit` on a
  route.
- **Practical score** — raw profit adjusted by an arrival-distance penalty. This
  is what the search **ranks by**. Carried as `practical_score` /
  `total_practical_score`.

The adjustment is the **ls-penalty** (`score.ls_penalty_multiplier`). It returns
a multiplier applied to raw profit, based on the destination station's distance
in light-seconds from its arrival star — the supercruise haul you fly after the
jump. The shape:

- A penalty percentage of **0 or less returns a flat `1.0`** — no effect.
- Above 0, a fixed sigmoid-based curve mildly **favours nearby** stations and
  increasingly **penalises distant** ones, scaled by the percentage (the CLI
  default is `--ls-penalty 12.5`). Far-flung stations score worse than their raw
  profit alone would suggest, so the search stops preferring a few extra credits
  that cost ten minutes of supercruise.

Treat this curve as **fixed by decision, not as gospel.** It is not claimed to be
optimal — it is the best the dev team could arrive at, and it was written into the
spec as a fixed point deliberately, so it stops being re-questioned and re-tweaked
on every revisit. Change it only as a conscious decision — a genuinely better
curve from someone with the maths would be taken gladly — not as an incidental
tweak in passing. That is also why `score.py` is small and stands alone: nothing
else should reach in and bend the curve ad hoc.

**`--sco`** plugs into this cleanly. It declares a Supercruise Overcharge drive,
where arrival distance barely matters. Rather than touch the protected curve,
`--sco` forces the penalty *input* to 0 (`run_request.py` sets
`ls_penalty_percent = 0.0` when the flag is set, overriding any `--ls-penalty`),
so the multiplier is always `1.0` and distant stations are no longer penalised.
The curve is untouched; it is simply fed a zero. This is the pattern for tuning
scoring: change what feeds the curve, not the curve.

### 5.3 The beam

A multi-hop search cannot enumerate every route — the branching is enormous. It
uses a **beam search**: at each hop it keeps only a bounded set of the most
promising partial routes and discards the rest. Three pieces of vocabulary:

- **Frontier** — the set of partial routes carried from one hop layer into the
  next. The search advances the whole frontier one hop at a time.
- **Expansion width** (`_MULTIHOP_EXPANSION_WIDTH = 50`) — the per-node fan-out
  cap: how many onward candidates a single partial route is allowed to spawn at
  one layer.
- **Frontier width** (`_MULTIHOP_FRONTIER_WIDTH = 50`) — how many partial routes
  survive the trim into the next layer.

Both widths are **50** — a settled value, not a guess: it comes from an end-to-end
value-versus-time sweep. Do not tune them casually; the figures and the decision
are in the tuning-evidence appendix (§13).

Two shared mechanics keep the beam honest:

- **The trim and the ranking key.** After a layer expands, the partial routes are
  deduplicated (see below) and sorted, and only the top `_MULTIHOP_FRONTIER_WIDTH`
  are kept. The sort uses one shared ranking key —
  `_route_progress_rank` / `_node_progress_rank` (`route_common.py`). Without
  `--towards` the key is *accumulated practical score* (best profit wins). With
  `--towards` it is *progress-first*: closest to the target wins, then fewer
  hops, then profit only as a tie-break. Because every selection point calls the
  same key, the `--towards` ordering is defined in exactly one place, not
  re-implemented per engine.
- **The kept-score floor.** A search tracks the practical score of the worst route
  in its current top-K (`_KeptScoreThreshold`). Any candidate whose *optimistic
  ceiling* — the best it could possibly score — cannot reach that floor is
  skipped before the expensive work (cargo solve, jump-path plan) is done; it
  could never enter the kept set. With K=1 this collapses to "the single best so
  far", which is exactly what the one-hop planners keep. This floor is what makes
  the cargo pre-filter (§8) and the streaming fetch's early stop (§10) possible.

**Deduplication ("coalescing").** Two partial routes that have arrived at the
*same place in the same state* are redundant — keeping both wastes frontier slots
on near-identical chains. The frontier therefore collapses partial routes by a
key, keeping the best-ranked one. The key is broadly "where the chain is now",
but it carries enough extra state not to wrongly merge chains that genuinely
differ — for example the visited-station history under `--unique` /
`--loop-interval`, so a chain that can still legally complete is not coalesced
away by one that cannot. The exact key is engine-specific (§6, §7); the principle
is uniform.

---

## 6. The shared open-anchor engine

`route_common._plan_open_anchor_route` is the heart of the multi-hop planner.
Most route shapes are a thin seeding layer on top of it, so understanding this one
function carries most of the planner.

### 6.1 What it serves, and `open_role`

The engine grows a pre-built **seed frontier** into the best open-ended N-hop
route. It does not know or care who built the seed — the caller does that, then
hands it over:

| Shape | Caller | Seed |
|-------|--------|------|
| Open destination (`--from X`) | `route_single_anchor` | the fixed origin's stations |
| Open origin (`--to Y`) | `route_single_anchor` | the fixed destination's stations |
| Fully unanchored | `route_unanchored` | a galaxy-wide candidate set |
| `--via` | `route_via` | anchor stations, with a waypoint mask (§7) |

One parameter, **`open_role`**, keys the direction — it names the trade role of
the endpoint the planner is *choosing*:

- **`open_role="destination"`** — grow **forward**. Each layer asks "what can this
  node sell onward?". The chosen destination emerges at the last layer. (`--from X`
  with `--to` omitted; also the unanchored search.)
- **`open_role="source"`** — grow **backward**. Each layer asks "who sells *into*
  this node?". The chosen origin emerges at the last layer. (`--to Y` with `--from`
  omitted.)

From the seed onward the engine is caller-agnostic: it expands one hop's reach at
a time, beam-trimmed, so no large sphere of open-side stations is ever built up
front.

### 6.2 The central trick: optimistic expansion, then forward correction

This is the idea that makes the open shapes tractable, and it is worth getting
straight.

**The problem.** How much cargo you can afford on hop 3 depends on the profit you
banked on hops 1–2. During a beam search you are juggling dozens of partial
chains at once; computing each one's *real* affordable cargo at every step is
expensive. Worse, for an open-origin search the chain is grown **backward** from
the fixed destination, but money flows **forward** — so at expansion time you do
not even know the running budget in the right order yet.

**The solution — two phases.**

1. **Expansion is credit-optimistic.** While growing the beam, cargo is fitted as
   if money were no object: `optimistic_credits = capacity ×
   _OPTIMISTIC_PRICE_PER_TON`, and that constant is one billion — effectively
   infinite. So the beam ranks chains on an *upper bound* of their profit. This
   decouples expansion from the real budget and from the direction money flows,
   which is what lets one engine grow either forward or backward.

2. **Correction is a forward re-fit.** Once a chain reaches N hops, the
   credit-correction pass (`_correct_open_anchor_chain`) puts it in money order
   (origin → destination, reversing the chain if the search grew it backward) and
   re-fits each hop's cargo against the **real running budget** — the base trade
   budget (`credits − insurance`) plus the margin-adjusted profit banked so far.
   If any hop cannot be afforded, the whole chain is rejected. A chain survives
   only if *every* hop re-fits, and finalists are then ranked by their
   **corrected** score, not the optimistic one.

Each non-seed node remembers the trade candidates and jump path of the hop that
made it, so correction can re-fit a hop without re-running any search.

The two phases fit together because **a corrected score can never exceed its
optimistic score** (less money can only buy less cargo). That single fact makes
the final early-stop exact (below).

### 6.3 The layer loop (expansion)

The engine walks hop layers `1 .. N`:

**Intermediate layers (`1 .. N-1`)** call `best_open_ended_hop_candidates(...,
terminal_hop=False, top_k=50)` for each frontier node. `terminal_hop=False` means
every emerged station must stay viable for the *next* hop (onward demand for an
open source, onward supply for an open destination), so a one-sided station
cannot hold an intermediate slot. Each returned trade becomes a child node. After
a layer:

- **Coalesce** per emerged station — keep the best optimistic chain that reached
  each station (the dedupe key from §5.3; under a revisit rule it also carries the
  visited-history fragment).
- **Trim** the survivors to `_MULTIHOP_FRONTIER_WIDTH` (50) by progress rank.
- If the layer produced **nothing**, the search is out of road: return the best
  completed *shorter* chain as a partial route (§6.5), or fail in the no-route
  family (as `NoUniqueRoute` if a revisit rule did the blocking).

**Final layer (hop N)** calls the same helper with `terminal_hop=True` — the route
end needs no onward-viability check. Unlike an intermediate layer it hands
**several** candidates per node into correction, not one: correction may reject a
chain whose best optimistic endpoint turns out unaffordable, and a lower-ranked
but affordable endpoint from the same node should still get its chance. Under
`--towards`, chains that reached the target on an earlier layer (collected in
`arrivals`) are folded in here so they compete in the final selection — an
arrival outranks any route that only got close.

### 6.4 The correction loop and top-N selection

The finalists are sorted best-first by progress rank, then corrected into a
bounded best-N collector (`_KeptRoutes`, sized by `request.routes`):

```
for each finalist (best optimistic first):
    if we already hold N corrected routes
       and this finalist's OPTIMISTIC rank can't beat the Nth-best CORRECTED:
        break                       # exact N-aware early-stop
    if we've already attempted _OPEN_SHAPE_CORRECTION_WIDTH (200) finalists:
        break                       # correction budget cap
    corrected = correct(finalist)
    if corrected is not None:
        kept.offer(corrected)
```

Two stopping rules, for two regimes:

- **The exact early-stop** relies on optimistic ≥ corrected (§6.2). Once N routes
  are held, any finalist whose *optimistic* rank cannot beat the *worst corrected
  route held* cannot possibly enter the set, and neither can anything ranked below
  it — so the loop stops. At `--routes 1` (`keep=1`) this is exactly the original
  single-best early-stop. It fires when credits are loose (correction barely
  changes the ranking).
- **The correction-budget cap** (`_OPEN_SHAPE_CORRECTION_WIDTH = 200`) is the
  backstop for the *credit-bound* regime: when money binds hard, correction
  reshuffles the order and the exact early-stop rarely fires, so this cap keeps
  the number of re-fits bounded.

`kept.best()` returns the top-N corrected routes; `routes[0]` is the winner and
the rest ride along as the `--routes N` extras. `--routes 1` collapses the whole
mechanism back to "track the single best corrected route" — byte-identical to the
pre-`--routes` behaviour.

### 6.5 The shorter-chain fallback

`_best_open_anchor_partial` is a **zero-results safety net**, not a padder. If no
full-length chain survives correction, it corrects every completed shorter chain
in the frontier and returns the best survivor, tagged with a
`PartialRouteWarning` so the renderer can say "got N of M hops". It draws only
from full-length finalists in the normal path: if `--routes 3` is asked and only
one full-length route corrects, the result is one route, not three.

### 6.6 Run-scoped caches

For the lifetime of one call the engine holds three caches, released in a
`finally`: a `QualificationCache` (the qualify-once temps, §10), a station-DTO
cache (immutable station rows are hydrated once), and a reachable-systems memo.
Frontier bubbles overlap heavily from layer to layer, so these turn repeated work
into lookups. They are central to why the fetch is fast (§10) but incidental to
the routing logic itself.

---

## 7. The engines

With §6 in hand, the rest of the engines are quick. There are really **two
multi-hop engines**, and the difference between them is the single most useful
thing to hold onto:

- The **open-anchor engine** (§6) grows toward an *open* end. It cannot fit real
  cargo as it goes (it does not yet know the budget in money order), so it expands
  optimistically and corrects afterward.
- The **fixed-terminal engine** (§7.2) grows forward from a known origin toward a
  known destination, in money order. It therefore fits **real cargo during
  expansion** and needs no correction pass.

Around those sit the one-hop paths, two thin seeders for the open-anchor engine,
and `--via` as a specialised owner.

### 7.1 One-hop (`route_onehop.py`)

Single-hop planning does not use a multi-hop engine at all — there is no frontier
to grow. It has three subpaths, all of which end by keeping the best-N pairs
(`_KeptPairs`) and building a route per pair (`_assemble_result`):

- **Fixed pair** (`_plan_fixed_endpoints`) — both endpoints named. Each expands to
  its eligible stations, and `_best_pair_plan` walks the **station-pair matrix**:
  for every (source, destination) pair, check reachability (skipped under
  `--direct`), fetch the candidate trades, fit real cargo, score, and offer to the
  kept-N. The no-winner path classifies the failure in aggregate — two probe
  queries for the whole matrix, not two per empty pair.
- **Open-ended** (`_best_open_ended_plan`) — one endpoint fixed, the planner picks
  the other. It streams the open-ended candidate fetch (§10) behind a kept-score
  floor (`_KeptScoreThreshold`, sized to N), so a pair that cannot beat the kept
  set is dropped before its cargo solve.
- **Unanchored** (`_plan_unanchored`) — neither endpoint named. The same
  kept-score-floor selection, fed by the galaxy-wide candidate fetch.

`--routes 1` makes `_KeptPairs` a single slot, so each path keeps exactly the
winner it always did.

### 7.2 Fixed-terminal multi-hop (`route_anchored.py`)

`_plan_multi_hop` is the second multi-hop engine: both endpoints named, grow
forward from the origin, end on one of `Y`'s eligible stations. Its defining
trait is **real-budget forward expansion** — credits propagate hop to hop
(`available_credits = base_trade_budget + floor((1 - margin) ×
accumulated_raw_profit)`), so cargo is fitted against the true budget at each
layer and there is no optimistic/correction dance.

Three mechanics are worth knowing:

- **System-diverse beam trim.** After each layer is rescored, it is trimmed to
  `_MULTIHOP_FRONTIER_WIDTH` (50) with **at most one node per destination
  system**, so a cluster of near-identical chains into one system cannot crowd the
  beam out of genuinely different options.
- **Destination-envelope pruning.** Each intermediate layer's candidate fetch is
  restricted *in SQL* to destination systems within `remaining_hops × jumps_per ×
  ly_per` of `Y`. A system the route could never reach `Y` from in the hops left
  never leaves the database. (When that envelope provably contains the anchor's
  entire reach bubble it is *dropped* for the call — `_envelope_is_provably_loose`
  — restoring a faster query path. Pure performance.) The final hop is a
  per-node fixed-pair evaluation against `Y`'s stations, with the close helper
  `best_fixed_pair_trades_from` contributing up to K terminal trades per prefix so
  several strong closes from one prefix can all reach the global top-N.
- **`--loop` rides here.** A loop carries no `--to`; each chain must close on its
  own origin station. Roots are pre-qualified as valid *destinations* (not just
  sources) — avoided places dropped, usable return demand confirmed — before the
  width-50 frontier is seeded, so an unclosable root cannot crowd out a closable
  one. Partial routes are suppressed: an unclosed loop is not a loop, so those
  sites raise `NoLoopRoute`.

### 7.3 Single-anchor open multi-hop (`route_single_anchor.py`)

Thin — under 100 lines. `_plan_open_anchor_multi_hop` resolves the fixed
endpoint, builds the hop-0 seed frontier from its eligible stations, and hands off
to `_plan_open_anchor_route` with the right `open_role`. All the work is in §6;
this module's job is just to seed it from one named endpoint.

### 7.4 Fully-unanchored multi-hop (`route_unanchored.py`)

Also thin, with one extra step. It runs the unanchored *one-hop* candidate fetch
— the expensive, SQL-narrowed galaxy scan — which returns a bounded, ranked set
of (source, destination) trades. The **source stations** of those trades are good
places to start a route, so it ranks them by a realisable-profit proxy
(profit/unit × the tonnage actually realisable), trims to the beam width (50), and
seeds the forward open-anchor engine on them. The galaxy-scan counters are
attached to the diagnostics afterward, since the engine never saw that scan.

The trim before seeding matters: the engine expands *every* seed node, so handing
it hundreds of un-trimmed sources would blow up the first layer.

### 7.5 `--via` (`route_via.py`)

`_plan_via_route` is a **specialised owner** built on the credit-optimistic
open-anchor machinery, but it manages its own frontier because routing through
waypoints needs state the plain engine does not carry. Two mechanics define it:

- **The satisfied-via mask.** Each chain tracks which waypoints it has already
  visited. Only a finalist carrying the *full* mask — every waypoint visited — can
  win. There is no partial-via route: any collapse raises `NoViaRoute`.
- **The lane-diversity frontier.** Instead of a single best-N trim, the frontier
  keeps **one search lane per owed waypoint**, so every visit order is explored
  and a high-profit lane cannot starve a waypoint of frontier slots. The terminal
  lane reserves a slot for the chain nearest the destination, so a distant `--to`
  still closes rather than the route stalling on the last waypoint.

Direction follows the shape (forward from `--from`, backward for the `--to`-only
case), exactly as the open-anchor engine does, and `--via` requires an anchor —
a fully-unanchored via is rejected.

---

## 8. The cargo optimiser

`cargo.optimise_cargo` answers one question for a single hop: **given these
candidate trades, what mix of commodities and quantities makes the most profit?**
Every engine calls it — it is the inner loop of the whole planner, run once per
candidate pair, so its speed matters as much as its correctness.

### 8.1 What it computes

The objective is **maximum total profit** subject to:

- **shared cargo capacity** — all commodities share one hold (`--capacity`);
- **the credit budget** — you cannot spend more than you have;
- **source supply and destination demand as hard quantity caps** — you cannot buy
  more than is stocked, nor sell more than is demanded.

The caps are folded in up front by `_build_bounded_candidates`, which turns each
`TradeCandidate` into a `_BoundedCandidate` carrying a `max_quantity` —
`min(supply, effective_demand, capacity, budget ÷ buy_price [, --limit])` — and
drops anything unprofitable. Note **demand is a hard cap, not just an eligibility
test**: `effective_destination_demand_units` (the demand after the bulk-sale-tax
cap, where that applies) bounds how much can be sold. This is a deliberate
contract decision — demand limits the load, it does not merely qualify the trade.

### 8.2 Two solve paths

The optimiser picks one of two paths:

- **Exact greedy fast path.** When the credit budget *cannot bind* — filling the
  whole hold with the most expensive available candidate still costs no more than
  the budget (`_credit_cannot_bind`) — the problem collapses. With unit cargo
  weights and money no object, taking the highest profit-per-unit commodities
  first until the hold is full is provably optimal: the same answer
  branch-and-bound would reach, in one pass, no recursion. This is the **common
  case** for the open-anchor engine, which fits cargo against a deliberately
  non-binding optimistic budget (§6.2), so most cargo solves never recurse.
- **Branch-and-bound.** When credits bind, the real combinatorial solve runs.

### 8.3 Branch-and-bound and the admissible bound

Branch-and-bound explores a tree of choices (how many units of candidate 1, then
candidate 2, …) but uses an **upper bound** on the best any subtree could yield to
prune whole branches that cannot beat the best plan found so far. It is only as
good as that bound, and the bound here is the careful part
(`optimistic_upper_bound`).

There are two shared constraints, capacity and credits. The bound **relaxes each
in turn** and takes the smaller result:

- **Capacity relaxed away** — solve the credit-only knapsack: greedy by
  profit-per-unit, integer fill (exact, because cargo weights are one unit each).
- **Credits relaxed away** — solve the capacity-only knapsack as a *fractional*
  knapsack on the budget, greedy by profit-per-credit. Letting the last item be
  taken fractionally is what makes this an over-estimate, not an achievable value.

Dropping a constraint can only raise the optimum, so each half is a true
over-estimate of the subtree's real best; the **minimum of two over-estimates** is
the tighter one and still an over-estimate — so `bound ≤ best ⇒ prune` is always
safe (this property is called *admissibility*). Both halves are needed: the
capacity bound is far too loose when credits bind, and vice versa; whichever
constraint actually bites supplies the tight number.

One subtlety worth preserving if you touch this: the bound must **relax**, never
**spend**. A greedy that actually spends the budget gives a *feasible* value — a
lower bound — which can dip below the true subtree optimum and prune the best
plan. The real credit constraint is still enforced in the search itself, which
only ever generates affordable combinations.

The search is also **seeded** before it starts: the incumbent begins at the better
of two cheap feasible greedies (by profit-per-unit and by profit-per-credit), so
the admissible bound has a strong floor to prune against from the very first node.
Starting from a zero incumbent is what used to let the search explode when credits
bound hard.

### 8.4 The caller pre-filter (`prune_below_raw`)

This is where the kept-score floor (§5.3) cashes out. A caller that is keeping the
best-N pairs passes `prune_below_raw` — the score of the worst pair it currently
holds. Before any solving, the optimiser computes the **admissible root bound**
(the most this pair could *ever* yield). If even that cannot reach the floor, the
pair can never enter the kept set, so the whole solve is skipped and `None` is
returned (counted separately as a "pruned" solve). The comparison is strict, so a
pair that merely ties the floor is still solved and left to the caller's
tie-break. This pre-filter is the single biggest reason the real-budget shapes are
fast — most candidate pairs are dismissed before the expensive work.

(`None` here means "skipped, could not have won" and is distinct from a
`NoProfitableTrades` raise, which means "no viable plan exists at all".)

### 8.5 The confident stop

When branch-and-bound *does* run, it does not insist on proving the optimum. A
tightly-bounded, seeded search typically *finds* the best plan early, then spends
thousands of nodes only **proving** nothing better exists — wasted work, and there
is one solve per candidate pair, so it multiplies. Two stops cut it short:

- **No-improvement stop** (`_SEARCH_NO_IMPROVEMENT_LIMIT = 500`) — the primary
  one. Give up 500 nodes after the last time the incumbent improved, confident in
  the answer in hand rather than paying to certify it.
- **Outer fuse** (`_SEARCH_NODE_LIMIT = 2000`) — a hard ceiling so a pathological
  commodity mix can never hang the planner.

Either stop returns the best feasible plan found so far — always at least the
greedy seed — so the result is always valid, at worst very slightly under-optimal
on a pathological instance.

Both limits are **empirical, not guesses** — sized from an extended testing run,
with deliberate margin over what the winning solves actually need. The figures and
what they showed are in the tuning-evidence appendix (§13); do not change either
without reading it.

A final detail: `ignore_credits` drops the credit constraint entirely for the
`--via` optimistic pass, so that even under `--max-price 0` (no finite price
ceiling) the via search cannot accidentally fall into branch-and-bound. The result
is identical to the fast path; it just guarantees the path.

---

## 9. Reachability

Reachability answers a geometric question, separate from anything about trade:
**can you fly from system A to system B under the run's jump rules**
(`--jumps-per` jumps, each at most `--ly-per` LY), and if so by what path? It knows
nothing about markets or profit. A jump is interstellar; moving within one system
is supercruise, not a jump.

The module (`reachability.py`) exposes three entry points, all sharing the same
machinery:

| Function | Answers |
|----------|---------|
| `plan_jump_path` | The actual path A → B (for a chosen hop — to display and measure). Returns a `JumpPath`, or raises `NoReachableRoute`. |
| `is_system_pair_reachable` | A cheap yes/no, when the path itself is not needed. |
| `reachable_systems_from` | *Every* system reachable from an anchor within the cap — returned with coordinates so the caller can bulk-insert them into a reachable-systems temp table and keep the candidate query composing in SQL (§10). |

### 9.1 The cheap early-outs come first

`plan_jump_path` is ordered cheapest-first, and **most pairs resolve before any
database query runs**:

1. **Same system** → supercruise, zero jumps.
2. **`--jumps-per 0`** → reject; the caller asked for no jumps.
3. **Direct single hop** → destination within one `--ly-per` of source → one jump,
   done.
4. **Triangle-inequality reject** → the widest path of N jumps at max `--ly-per`
   each spans `N × ly` LY. If the destination is farther than that, no path of the
   requested depth can exist — reject without touching the database.
5. Only if all four miss does it build the bubble and run BFS.

Distances are kept **squared** throughout — a square root is only taken when a
result is actually reported — because squared distance is monotonic with real
distance and the SQL bubble fetch uses the same form.

### 9.2 The local bubble — the core structure

When a real search is needed, the work is done inside a **local bubble**
(`_LocalBubble`): every system within `max_jumps_per_hop × max_ly_per_jump` of the
anchor, with its full adjacency table. The radius is the load-bearing idea — by the
triangle inequality, *any* path of up to N jumps from the anchor stays inside that
radius. So the bubble is a self-contained universe for the search: **if there is no
path inside the bubble, there is no path in the galaxy under these limits.**

Building one (`_load_local_bubble`) follows the query-discipline rule — narrow in
SQL first, compute in Python second:

1. **SQL bounding box → sphere.** An indexed `pos_x/pos_y/pos_z` bounding-box
   `BETWEEN` predicate does the coarse cut on the database side, refined to a true
   sphere by a squared-distance term — no rows leave the database that the sphere
   would not keep. `--avoid` systems are dropped here (`NOT IN`) so no path can
   route *through* one (the permit case), with the anchor itself always kept (the
   explicit-origin carve-out: you may leave an avoided `--from`, but every other
   bubble still excludes it, so the route never returns).
2. **One scipy call for adjacency.** `cKDTree.query_ball_tree(self,
   max_ly_per_jump)` computes every system's within-one-jump neighbour list in a
   single C-side call. From that point on the bubble is plain Python tuples.

So there is a one-time scipy cost per anchor to build the adjacency, and every
search after that is **pure-Python BFS** over those neighbour lists — no further
scipy work. `_bfs_jump_path` walks breadth-first to the depth cap and returns the
shortest-in-hops system sequence (or `None`); `_bfs_collect_reachable` is the
variant that gathers *every* reachable system, for `reachable_systems_from`.

### 9.3 Two caches

Reachability is asked the same things over and over, so two caches matter:

- **`bubble_cache`** — the per-request dict created at dispatch (§4). One bubble per
  anchor system, loaded once and reused by every hop and every destination that
  walks from that anchor. This is why a candidate matrix evaluating many
  destinations from a fixed origin pays for that origin's bubble exactly once.
- **`path_cache`** — carried *on* each bubble, keyed by destination. A station-pair
  matrix asks the same (source-system, destination-system) question repeatedly
  (many stations share a system), so each repeat becomes a dict lookup. It stores
  the **path tuple**, not just a yes/no, so a cheap `is_system_pair_reachable`
  check and a later full `plan_jump_path` for the same pair share one BFS result.
  Cached `None` means "computed unreachable"; absent means "not computed yet".

### 9.4 Polyline distance

A `JumpPath`'s `distance_ly` is the **polyline length** — the sum of the leg
lengths actually flown — not the straight-line distance between the endpoints. A
multi-jump path that bends off the direct line is genuinely longer than the
crow-flies distance, and the polyline is the honest figure to display and to feed
the score.

---

## 10. The candidate-fetch strategy

`data_gateway.py` is the only module that issues planning SQL, and it is where
"don't load the galaxy" (§2) becomes concrete. Every technique here exists to
honour one rule: **narrow in SQL, then compute in Python on an already-small
result** — never pull rows into Python to filter them, and never materialise a
column of ids only to hand it back to the next query as a giant `IN (...)`. At
~19M market rows, getting this wrong is the difference between a sub-second fetch
and a multi-minute one. This section is the *strategy*; the per-filter SQL is out
of scope.

Four techniques carry it.

### 10.1 Spatial-first narrowing

A spatial constraint must shrink the candidate set *before* any join to market
data. The pattern (`_reachable_station_query`): resolve the anchor → build the set
of reachable systems (the bubble BFS from §9) into a **reachable-systems temp
table** carrying `pos_x/y/z` → and only then query `StationItem` for stations in
those systems, by joining against the temp as a subquery. The candidate set never
leaves SQL as a Python list. The temp is memoised per request (the
`reachable_memo` from §6.6), so repeated callers for the same
`(system, jumps, ly)` reuse one built table.

Two SQL-side restrictions ride on this same query rather than filtering in Python:
the **destination envelope** (the fixed-terminal "must still be able to reach `Y`
in the hops left" box from §7.2) and the **`--towards` progress rule** (restrict
to systems strictly closer to the target). Both drop systems before they ever
become rows.

### 10.2 Qualify-once temps (`QualificationCache`)

Many row predicates are **run-constant** — price and unit thresholds, `--age`,
`--max-price`, avoided commodities all give the same answer for a station whatever
anchor is asking. But frontier bubbles overlap heavily, so a naive fetch
re-derives those answers for the same station many times over.

The cache answers them **once per station**. The first anchor to reach a station
qualifies its rows into a run-scoped temp; every later anchor's pairing query reads
the temp instead of re-walking `StationItem`. It stays in SQL end to end — a
seen-stations temp records who is already in, each fetch inserts only the unseen
slice of its bubble with one `INSERT ... SELECT`, and no id list round-trips
through Python. Two details worth knowing:

- **One frozen `--age` cutoff.** The age cutoff is fixed at first use, so the temps
  and every anchor's query share a single "now" for the whole run — the window does
  not drift with the wall clock across a long search.
- **Stale stations are never walked.** With `--age` set, the fresh-station set is
  derived once from the `modified`-led covering index; stale stations never enter
  the qualification at all. This is what makes `--age` a genuine cost lever, not
  just a filter.

### 10.3 Price-bound narrowing of the open side

In an open-ended search one side is fixed (a named endpoint, a handful of stations)
and the other is open (everything reachable). The fixed side is cheap to
summarise, so `_build_open_fixed_bounds` aggregates its **per-item price extremes**
into a small bounds temp. The open-side query then joins that temp 1:1 on item: an
open-side row survives only if the fixed side trades that item *at all*, at a price
that could clear `--gain-per-ton` against the fixed side's best. Rows that could
never pair with the fixed end never leave the database. (If the fixed endpoint has
no usable rows at all, the bounds temp is empty and the open-side query is skipped
entirely.)

### 10.4 Bound-ordered streaming with a provable early stop

This is the technique that ties the fetch to the search. The open-ended fetch
(`iter_open_ended_station_groups`) does not return a list — it is a **generator**
that yields candidate groups one open station at a time, **ordered by descending
ceiling**. A station's ceiling is an upper bound on the per-unit profit of any pair
it could form, computed in SQL against the fixed side's price extremes; ceilings
are non-increasing down the stream.

Because the consumer is an engine holding a kept-score floor (§5.3, §8.4), it can
**stop the moment the next ceiling cannot beat what it already holds** — close the
generator, and the rest of the stream is never read off the cursor, never converted
to candidates, never paired. This is exact: an exhausted stream yields every
candidate the filters admit, and a stopped stream omits only stations the consumer
*proved* unbeatable. The ceiling is necessary-condition ordering, nothing more — no
ranking or selection happens in the gateway.

One more efficiency on intermediate hops: a mid-route station must stay viable
onward (§6.3). Rather than a per-row correlated `EXISTS`, that check becomes a
**per-station semi-join** against the opposite side's qualification temp — the
temp's predicates *are* the onward conditions, so a station has rows there exactly
when the per-row test would have passed, and the cost amortises across every anchor
that shares the bubble.

### 10.5 The unanchored galaxy scan

One fetch genuinely has to cast wide: `fetch_unanchored_trade_candidates`, the seed
for the fully-unanchored shapes (§7.4). Even this never loads the galaxy — it
narrows with temp tables, aggregates and ranks pairs *in SQL*, and resolves
reachability on demand for the survivors rather than up front. It is the most
expensive fetch in the planner, which is exactly why the galaxy-wide shapes sit
behind a confirmation prompt.

---

## 11. A run, end to end

To tie the pieces together, here is one concrete run traced through the whole
pipeline:

```
trade run --from sol --to lave --hops 5 --jumps-per 2 \
          --capacity 200 --credits 5000000 --ly-per 20
```

Both endpoints are named and `--hops > 1`, so this is the **fixed-terminal
multi-hop** engine — chosen for the walkthrough because it fits real cargo as it
goes, exercising the most machinery in one pass.

1. **Parse → `RunRequest`** (§2). The command layer builds the request DTO once via
   `run_request_from_cmdenv`: `from_text="sol"`, `to_text="lave"`, `hops=5`,
   `max_jumps_per_hop=2`, `capacity_units=200`, `starting_credits=5_000_000`,
   `max_ly_per_jump=20`. Nothing planner-side runs yet.

2. **Dispatch** (§4). `plan_route` validates once, resets the cargo counters, and
   creates the per-request `bubble_cache`. No `--via`; `hops ≠ 1`; both endpoints
   present → `route_anchored._plan_multi_hop`. (Names are resolved to endpoint DTOs
   here, once.)

3. **Seed** (§7.2). Sol's eligible source stations become the hop-0 frontier;
   Lave's eligible stations are the terminal the route must end on, and their system
   coordinates become the **destination envelope** anchor. The trade budget is
   `5_000_000 − insurance`.

4. **Grow the frontier, hops 1–4** (§7.2). Each layer expands every surviving
   partial route:
   - **Fetch** the onward candidates (§10): the reachable-systems temp restricts to
     stations within `--jumps-per × --ly-per` of the node (§9, §10.1), narrowed
     further to the **envelope** — systems that could still reach Lave in the hops
     remaining — and to the **price bounds** of the fixed side; rows stream
     best-ceiling-first (§10.4).
   - **Fit cargo** (§8) for each candidate destination against this node's *real*
     running budget (`base + ⌊(1 − margin) × profit so far⌋`). The kept-score floor
     pre-filters pairs that cannot beat what is already held (§8.4), so most never
     reach the branch-and-bound solve.
   - **Score** each child by practical score (§5.2) — profit bent by the
     destination's ls-penalty.
   - **Trim** the rescored layer to 50, at most one node per destination system
     (§7.2), and carry it forward.

5. **Close on Lave, hop 5** (§7.2). Each surviving prefix runs a fixed-pair
   evaluation against Lave's stations: reachability (§9) gates which are actually
   reachable, and the close helper lets one prefix offer several terminal trades, so
   strong closes are not thrown away. Real cargo is fit for each.

6. **Select** (§5.3). The completed routes are ranked by practical score and the
   best is the winner; `--routes N` would return the top N (here N defaults to 1).

7. **Assemble `RunResult`** (§2). The winner becomes a `PlannedRoute` — five
   `PlannedHop`s, each carrying its source/destination stations, `CargoPlan`,
   `JumpPath`, raw profit and practical score — with route totals and start/end
   credits, plus the diagnostics. Control returns to `plan_route`, which has no
   `--towards` or positioning legs to attach here, so it returns the result
   unchanged.

8. **Render.** The renderer consumes the `RunResult` and nothing else (out of scope
   for this document).

Had `--to` been omitted instead, steps 3–6 would run on the **open-anchor engine**
(§6): the same fetch and beam, but cargo fitted *optimistically* during expansion
and a forward correction pass re-fitting the finalists against the real budget
before selection. That single swap — real-budget-forward versus
optimistic-then-correct — is the whole difference between the two multi-hop
engines.

---

## 12. Invariants and key constants

### 12.1 Invariants — the rules that bind future work

Breaking one of these does not raise an error. It quietly produces a slow planner,
a wrong route, or a tangle the next maintainer inherits. Treat them as
load-bearing.

1. **Do not load the galaxy.** The planner queries the database for the rows a
   search needs and no more (§2, §10). A spatial constraint narrows the candidate
   set in SQL *before* any join to market data; filtering, joins, and set
   membership stay in SQL; an id column is never materialised into a Python list to
   be handed back as a large `IN (...)`. The moment a change starts pulling broad
   row sets into Python to work on them, it has rebuilt the exact problem the
   rewrite exists to remove.

2. **Shared meaning, specialised engines.** The engines may differ freely in search
   strategy, SQL shape, pruning, and frontier management — that specialisation is
   deliberate, not a smell to refactor away. What they must *not* do is each define
   the meaning of a user option. An option's meaning is resolved once into canonical
   request state (the `RunRequest`); engines consume that state, they do not
   re-interpret the option. Short form: **do not unify the engines; do unify the
   contract.** If you find yourself writing both `route_onehop._avoid()` and
   `route_anchored._avoid()`, stop.

3. **The boundary holds.** Nothing command-layer-specific crosses into the planner,
   and nothing planner-internal crosses out except the `RunResult`. Engines consume
   resolved endpoint / avoid / via state and never hold a database handle to resolve
   a name themselves — resolution happens once, at dispatch (§2, §4).

4. **Demand is a hard cap.** Destination demand limits how much can be sold, not
   merely whether a trade qualifies (§8.1). A settled contract decision, not an
   implementation convenience.

5. **The ls-penalty curve is fixed by decision.** Not because it is optimal —
   because it was deliberately frozen to stop being re-litigated (§5.2). Tune
   scoring by changing what you *feed* the curve (as `--sco` does); do not edit the
   curve except as a conscious, deliberate change.

6. **A new lever must leave the old behaviour untouched when it is off.** Every
   option here was added with an *inert proof*: with the option absent or at its
   identity value (`--routes 1`, no `--towards`, no `--unique`) the planner produces
   byte-identical routes to before. That is how features were added without
   destabilising the existing shapes, and it is the cheapest regression check there
   is. Keep it.

### 12.2 Key constants

| Constant | Value | Module | What it does | Evidence |
|----------|-------|--------|--------------|----------|
| `_MULTIHOP_EXPANSION_WIDTH` | 50 | `route_common` | Per-node fan-out at one hop layer (§5.3). | §13.1 |
| `_MULTIHOP_FRONTIER_WIDTH` | 50 | `route_common` | Partial routes carried into the next layer (§5.3). | §13.1 |
| `_OPEN_SHAPE_CORRECTION_WIDTH` | 200 | `route_common` | Max finalists re-fitted in the open-anchor correction pass — the credit-bound backstop (§6.4). | — |
| `_OPTIMISTIC_PRICE_PER_TON` | 1,000,000,000 | `route_common` | The "money is no object" price for optimistic expansion (§6.2) — effectively infinite. | — |
| `_SEARCH_NO_IMPROVEMENT_LIMIT` | 500 | `cargo` | Cargo confident-stop: bail this many nodes after the last improvement (§8.5). | §13.2 |
| `_SEARCH_NODE_LIMIT` | 2,000 | `cargo` | Cargo outer fuse: hard node ceiling (§8.5). | §13.2 |
| `_MIN_MEANINGFUL_DEMAND` | 2 | `data_gateway` | A destination market counts only at demand ≥ 2 (a stocked good reports its dormant buy side as 0 or 1). | — |
| `DEFAULT_MAX_PRICE` | 1,500,000 | `run_request` | Absolute cr/t cap clipping carrier-fiction rows; `--max-price 0` disables. | — |
| `_SHORT_RANGE_LY` | 12.5 | `run_request` | The `--jumps-per` keyed default threshold: `--ly-per` ≤ this defaults to 2 jumps/hop, else 1. | — |
| `_MULTIHOP_MAX_HOPS` | 25 | `validation` | The `--hops` ceiling. | — |

Below these sit a few internal batch sizes (streaming cursor partition, on-demand
reach batch, via lane floor, unanchored match limit) that are implementation tuning
rather than behavioural levers. The four with a §13 pointer are the ones set from
measurement; the rest are structural or contract decisions.

---

## 13. Appendix — the tuning evidence

The four constants flagged in §12.2 were set from measurement, not feel. The
figures below are the durable record of that work; the probe scripts behind them
were development scratch and are not kept. Both studies carry the same caveat:
route values and timings drift with every data refresh, so it is the *shape* of the
results that matters, not the exact credits — re-measure on current data before
re-arguing from these numbers.

### 13.1 Beam width — value versus time

Both beam widths were swept end to end at 10 / 25 / 50 / 100 / 200, on three
shapes: a mid route, a worst-case long open route, and that same worst case under a
fleet-carrier filter — the control, because it reflects real station-to-station
trading rather than carrier arbitrage. One database snapshot throughout.

| width | mid (open) | worst (open) | worst (filtered) |
|-------|-----------|--------------|------------------|
| 10  | 11.0s / 72.1M  | 14.2s / 87.4M   | 12.2s / 50.6M  |
| 25  | 15.1s / 72.1M  | 26.7s / 132.0M  | 26.0s / 57.1M  |
| 50  | 26.8s / 72.1M  | 57.7s / 375.3M  | 48.3s / 84.0M  |
| 100 | 49.5s / 107.1M | 111.3s / 456.3M | 93.0s / 84.2M  |
| 200 | 114.7s / 137.8M | 258.8s / 456.3M | 207.7s / 103.3M |

(Each cell is `wall time / winning route profit`; M = millions of credits.)

What it showed:

- **Time is linear in width.** Every doubling of the beam roughly doubles wall
  time, on every shape — search cost tracks the anchor count, which scales with the
  frontier.
- **Value is a staircase, not a curve with a knee.** Each shape goes flat, then
  jumps at a *different* width; there is no single width at which all three plateau.
  The jumps are structural — a wider beam keeps a mid-rank station whose
  *descendants* two hops later are excellent — which is why no single-layer measure
  predicts them.
- **Narrowing below 50 is not safe.** Width 10 gives up 77% of the worst shape's
  value and 40% of the filtered shape's.
- **Widening past 50 mostly buys carrier-tail arbitrage.** The realistic (filtered)
  economy gains ~0.3% going 50 → 100 while wall time doubles; the dramatic
  open-filter climb is owner-set fleet-carrier prices, not the background economy.

**Decision: 50 for both.** It sits at the filtered economy's knee, and no measured
width dominates it — narrower loses real value, wider pays double-plus time for
shape-dependent gains that are mostly carrier arbitrage. Exposing the width as a
user knob was considered and rejected: it would break route reproducibility between
users for a gain the default should not chase.

### 13.2 Cargo confident-stop and fuse

The cargo branch-and-bound stops (§8.5) were set from an overnight, multi-wave run
across hop counts 4–12, credits 500k–5M, several endpoints, and hold sizes. The
driving finding: with the old 100,000-node fuse the slow shapes were *hitting it* —
grinding ~100,000 nodes per solve to **prove** an optimum found in under 25 nodes.
About 99% of the cargo time bought nothing.

A node-cap sweep on the worst shape (sol → achenar, 8 hops, 720 t, 5M cr):

| node cap | wall | cargo time | route profit |
|----------|------|-----------|--------------|
| 500 | 92s | 3.6s | 105,181,521 |
| 2,000 | 95s | 7.3s | 105,181,521 |
| 10,000 | 116s | 27s | 105,181,521 |
| 50,000 | 222s | 133s | 105,181,521 |
| 100,000 (old) | 354s | 264s | 105,181,521 |

Route profit is **identical at every cap** — the search finds the optimum early and
spends the rest proving it. A floor probe was still route-exact at cap-25; the old
100,000 was oversized roughly 4,000× for the route's sake. The result held across
six diverse shapes (hops 4–12, the tightest credits, two endpoints): identical route
profit for 3.5–6× less wall.

Two forms shipped together:

- the **no-improvement stop (500)** is the principled one — it bails 500 nodes after
  the last improvement, so it never cuts a *still-improving* solve;
- the **lowered fuse (2,000)** is the hard backstop against a pathological mix.

Both, because a blanket hard cap *alone* was measured to cost 0.31% on the open
engine's finalist-correction pass (it can nudge which finalist wins) — the
no-improvement stop avoids that, and the fuse only catches genuine pathologies. The
500 / 2,000 values carry deliberate margin over the ~25 nodes the winning solves
actually need.
