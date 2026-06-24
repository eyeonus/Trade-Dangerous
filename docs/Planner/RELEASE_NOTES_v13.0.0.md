# Trade Run Route Planner — Release Notes

**Version 13.0.0**

---

## Scope of this document

These release notes describe version 13.0.0 of the `trade run` route planner, and
that version alone. They are published as a one-off because the planner has been
rebuilt in full: the search engine, its database access, and substantial parts of
its behavioural contract are new. Working knowledge of how `trade run` previously
planned routes should be set aside — this document, not prior experience, is the
current description of record.

These notes are not a living document. They will not be revised for later
versions. Every change after 13.0.0 is recorded in the project CHANGELOG, not
here.

---

## Overview

`trade run` plans profitable trade routes through the Elite Dangerous galaxy: it
chooses what to buy, where to sell it, and the jumps between, subject to your
ship, your credits, and the filters you set.

The planner queries the database directly and materialises only the rows a given
search needs, narrowing in SQL before anything reaches Python. It never builds an
in-memory model of the galaxy to plan one route. This is the single fact the whole
design turns on — it is what lets the planner work against a live dataset on the
order of 800,000 stations and 19 million market rows without choking on its own
preamble.

The command contract is stable: the options below are the surface. How the planner
searches behind that surface is covered, for developers, in
`docs/dev/planner-internals.md`.

---

## Route shapes

A route is defined by how many hops it has and which of its ends you name. Either
end may be a fixed point you supply or an open end the planner chooses, at any hop
count, giving a full grid:

| | `--from` and `--to` | `--from` only | `--to` only | neither |
|---|---|---|---|---|
| **one hop** | fixed pair | open destination | open origin | unanchored |
| **multi-hop** | fixed terminal | open destination | open origin | fully unanchored |

- An endpoint may be a **station or a system**. Name a system and the planner
  expands it to its eligible stations and picks the best pair; name a station and
  that station is used directly.
- **Multiple jumps per hop** are supported (`--jumps-per`), so a single trading
  hop can cross several jumps of empty space to reach the next market.
- Movement **within one system is supercruise**, not a jump, and is treated as
  such throughout.
- The two **galaxy-wide** shapes (both ends omitted, at one hop or many) are
  inherently broad searches and sit behind an interactive confirmation prompt. A
  non-affirmative answer, or a non-interactive invocation, exits cleanly without
  planning.

---

## Shaping the route

These options steer the shape of the route the planner builds.

- **`--hops`** — the number of trading hops, 1 to 25. An excessive count is
  rejected.

- **`--towards SYSTEM`** — steers an open-destination route toward a target
  system without forcing arrival. Requires `--from`; it cannot be combined with
  `--to`. Every hop must land strictly closer to the target, and routes are ranked
  progress-first: closest wins, then fewer hops, with profit only breaking ties.
  A hop that reaches the target ends the route; if the hops run out first, the
  route gets as close as it can.

- **`--loop`** — an anchored round trip that returns to its own starting station.
  It requires a named **`--from`** and at least two hops. The galaxy-wide loop —
  `--loop` with `--from` omitted, letting the planner choose the loop's origin —
  is **not supported**; `--loop` without `--from` is rejected.

- **`--via`** — forces the route through one or more named waypoints, which may be
  systems or stations, visited in any order. Every waypoint must be visited or the
  run fails; there is no partial-via route. At most six waypoints, and the route
  must have an anchor: at least one of `--from` / `--to` is required. A
  fully-unanchored via is rejected.

- **`--direct`** — the relocation run. It plans the single most profitable trade
  between a named `--from` and a named `--to`, with no jump-path or distance
  checks — you fly the route yourself. It requires **both endpoints** and is a
  **single hop only** (it cannot be combined with `--hops`). `--ly-per` and
  `--jumps-per` are accepted but ignored, since reachability is not checked.

- **`--avoid`** — excludes a commodity, a system, or a station. Tokens may be
  repeated or comma-separated, and are fuzzy-matched like the endpoints. An avoided
  commodity is never bought; an avoided station is never used as a route station;
  an avoided system is barred both as a route station and from jump-path transit —
  the route will not even pass through it (the permit case). An explicitly named
  `--from` is exempt as the origin: you may start in an avoided system, but the
  route never returns to it.

- **`--unique` / `--loop-interval N`** — the no-revisit constraints. `--unique`
  forbids visiting any station more than once. `--loop-interval N` is the bounded
  form: a station may not be revisited until `N` hops have passed (so `N=2` permits
  the immediate there-and-back and `N=3` is the first value that forbids it).
  `--unique` cannot be combined with `--loop` or `--loop-interval`; `--loop` with
  `--loop-interval` is allowed.

- **Empty-jump positioning (`--start-jumps` / `--end-jumps` / `--empty-ly`)** —
  treats a named `--from` or `--to` as a positioning anchor rather than a forced
  trade endpoint. `--start-jumps N` expands the eligible origins to every station
  within `N` empty jumps of the `--from` anchor's system; `--end-jumps N` does the
  same for destinations around the `--to` anchor. `--empty-ly` sets the unladen
  jump range used for that fan-out, falling back to `--ly-per` when absent. The
  empty repositioning flight is shown in the route output.

---

## Reachability

- **`--ly-per`** — the laden jump range, in light-years. Required, except under
  `--direct`, where it is moot.
- **`--jumps-per`** — jumps allowed per trading hop. When omitted it defaults by
  range: **2 jumps** if `--ly-per` is 12.5 or less, otherwise **1**. Short-range
  ships reach too little on a single jump, so the default opens up for them.

A practical consequence worth stating: at a typical `--ly-per` of 20 the default
is one jump per hop, which often cannot bridge a real interstellar multi-hop
route. Set `--jumps-per 2` (or more) for multi-hop runs at that range.

---

## Trade and cargo

- **`--capacity`** — cargo hold size in tons. Required.
- **`--credits`** — starting credits. Required.
- **`--insurance`** — credits held back as a reserve; they are not spent on cargo,
  and the run must still leave a workable trading budget.
- **`--limit`** — a per-commodity unit cap; `0` means unlimited. It may not exceed
  `--capacity`.
- **`--margin`** — the fraction (0 to 1) of accumulated profit *not* trusted as
  later buying power, so the plan does not assume it can spend money it has only
  projected.

The cargo optimiser fills the hold for maximum total profit across several
commodities at once, within capacity, credits, source supply, and destination
demand. **Destination demand is a hard quantity cap** on how much you can sell —
not merely a test of whether the trade qualifies.

Trade filters:

- **`--gain-per-ton`** — minimum profit per unit; default 1.
- **`--max-gain-per-ton`** — maximum profit per unit; default 0, meaning off.
- **`--supply`** — minimum supply at the source.
- **`--demand`** — minimum demand at the destination.

Two caps protect the search from prices that would otherwise distort it:

- **Bulk-sale-tax cap** — for Metals and Minerals, the quantity sold at a
  destination is capped at `floor(demand × 0.25)`, to stay clear of the in-game
  bulk-sale price penalty. This is the default. **`--no-bulk-cap`** turns it off
  and fills the full demand at the headline price.
- **`--max-price`** — an absolute price ceiling, default 1,500,000 cr/t, which
  clips the fictional multi-million-credit rows that owner-set fleet-carrier prices
  can produce. `--max-price 0` disables it.

- **`--sco`** — declares a Supercruise Overcharge drive, where arrival distance
  barely matters. It removes the arrival-distance penalty so distant stations are
  no longer scored down. It overrides any `--ls-penalty` you set.

---

## Station and market filters

- **`--pad-size`** — a ship-fit threshold: `S` / `M` / `L` mean "the ship needs at
  least this pad". `L` keeps only large-max stations; `M` keeps medium- and
  large-max stations plus those whose pad size is unknown; `S` keeps every station.
  A station whose pad size is unknown is admitted unless `--pad-size L` is set.
- **`--planetary` / `--fleet-carrier` / `--settlement` /
  `--black-market`** — accepted-state filters. Each takes a set drawn from `Y`
  (known yes), `N` (known no), and `?` (unknown) — for example `Y?` for "yes or
  unknown".
- **`--ls-max`** — maximum station distance from the arrival star, in
  light-seconds.
- **`--age`** — a freshness window: exclude market rows older than `N` days. It
  takes fractions (`--age 0.25` is six hours). **There is no default** — absent
  `--age`, every row is used whatever its age, which deliberately supports the
  relight-old-data playstyle. The window is sampled once at the run's first fetch,
  so a single run shares one cut-off instant rather than drifting as the search
  proceeds.

Two facts about the market data the planner respects, and you may need to know:

- **Markets have two independent sides.** A station may legitimately only supply
  (an origin only) or only demand (a destination only). The planner handles
  one-sided stations; a station used mid-route must do both.
- **A destination counts only at demand of 2 or more.** A stocked commodity
  reports its dormant buy side as 0 or 1, so a demand of 1 is an unfillable sale
  rather than a real trade, and is declined.

---

## Name resolution

Endpoint names — `--from`, `--to`, `--towards`, `--avoid`, `--via` — are resolved
once, when the run starts, with partial matching: exact first, then prefix, then
substring, with no typo tolerance. A non-exact match is echoed back as
`… resolved as …` so you can see what was chosen.

Syntax picks the namespace, and a **bare name resolves system-first, then falls
back to a station**:

- a **bare name** is tried as a system, then as a station if no system matches;
- **`@name`** forces a system (no station fallback);
- **`/name`** is a station;
- **`system/station`** is a station within the named system;
- **`system/`** is the named system.

So a bare `hamlinc` with no matching system resolves to the station
`Sol/Abraham Lincoln`, exactly as the non-planner commands resolve it — `trade
run` shares one place-resolution contract with the rest of the tool rather than a
strict system-only namespace. An unresolved name reports the kind it ended on.
Where two real systems share a name, they are disambiguated with `@N` and their
coordinates: a bare collision lists the candidates, and `Name@2` selects the
second.

---

## Output

The default output is a **rich colour table**, organised station-by-station: a row
per stop showing what you sell on arrival and what you buy before leaving, so it
reads the way the route is flown. It comes in three verbosity tiers:

- **`--summary`** — the lean glance: both sides of each stop, no prices, no nav,
  and the profit.
- **standard** (the default) — prices the buy side and shows the jump route under
  each stop.
- **`-v` (verbose)** — prices both sides, lists every jump, and rules the stops
  apart.

Each tier adapts to the terminal width, shedding columns rather than wrapping into
a mess: Balance goes first, then Profit, and on a narrow terminal the standard tier
drops its Sell column while the verbose tier folds Sell and Buy into a single
tagged Trade column — so Profit survives even at 80 columns.

Other output controls:

- **`--80col`** — forces the portable 80-column layout. (A piped or redirected run
  falls back to 80 columns anyway.)
- **`--raw`** — selects a plain-text format instead of the rich table:
  hop-centric, 80-column, verbosity-gated, with thousands-grouped figures. It is
  the format for grep, pipes, scripts, diagnostics, and the GUI's intercept path.
- **`--progress` (`-P`)** — shows a live, transient progress display while the
  route is being planned, cleared before the result is printed. A multi-hop or
  `--via` search has a known hop count, so it shows an "M of N hops" bar with
  elapsed time and a per-node sub-row as each layer expands; a single-hop search
  has no known total, so it shows a spinner and elapsed time, counting candidate
  stations as they stream past. It cannot be combined with `--raw`.
- **`--checklist`** — steps through the planned route interactively, stop by stop.
  It cannot be combined with `--routes` greater than 1.
- **`--routes N`** — returns up to `N` routes, numbered best-first, instead of just
  the winner. `N` is a maximum, not a quota — fewer are returned if fewer exist.
  `--routes 1` is the single-winner default.

There is no structured (for example JSON) output mode in 13.0.0; `--raw` is the
machine-readable path.

---

## Performance

The planner is built to stay fast on a full live dataset, and the techniques are
worth knowing because they shape what the options cost:

- **Spatial constraints narrow the search in SQL first.** A `--from` / `--near`
  bound resolves to a candidate set inside the database before any join to market
  data — the candidate ids never leave SQL as a Python list to be handed back as a
  giant `IN (…)`.
- **Open-ended searches stream and stop early.** When one end is open, candidates
  are read best-first and the search stops the moment what remains cannot beat what
  it already holds; the tail is never read out of the database.
- **Cargo solves are pruned and confidently stopped.** A candidate that provably
  cannot improve on the best route so far skips its cargo solve entirely, and the
  solves that do run stop once they are confident rather than grinding to prove the
  optimum.
- **`--age` is a genuine cost lever.** With `--age` set, stale stations are dropped
  before the search walks them, so a tighter window is a faster run, not just a
  stricter filter.

The galaxy-wide shapes are the one place a search must genuinely cast wide; that is
why they sit behind a confirmation prompt rather than running unguarded.

---

## Architecture at a glance

The planner sits inside a fixed pipeline, with two plain data objects forming the
boundary:

```
CLI parser → RunRequest → planner → RunResult → renderer
```

The parsed, normalised inputs of one run cross in as a `RunRequest`; the planned
routes cross back out as a `RunResult`. Nothing else passes either way — no
in-memory galaxy model, no command-layer objects reaching into the planner.

Route planning is split by shape — one module per route shape — over a shared
multi-hop expansion engine and a small set of shared core services: database
access, the cargo optimiser, reachability, and scoring. The engines may specialise
how they *search*, but the *meaning* of an option is resolved once into the request
and consumed from there, never re-interpreted per engine.

| Module | Responsibility |
|--------|----------------|
| `run_route.py` | Dispatch: validate, choose an engine by route shape, post-process. |
| `route_onehop.py` | Single-hop planning (fixed / open-ended / unanchored). |
| `route_anchored.py` | Fully-anchored multi-hop, and `--loop`. |
| `route_single_anchor.py` | Part-anchored multi-hop (one open end). |
| `route_unanchored.py` | Fully-unanchored multi-hop. |
| `route_via.py` | `--via` waypoint routing. |
| `route_common.py` | Shared frontier/beam machinery and the open-anchor engine. |
| `data_gateway.py` | All read-only planning SQL. |
| `cargo.py` | The cargo optimiser. |
| `reachability.py` | Jump paths and the reachable-systems bubble. |
| `score.py` | Practical-value scoring and the ls-penalty curve. |

For the engines, the shared expansion machinery, the cargo optimiser, and the
candidate-fetch strategy in depth, see **`docs/dev/planner-internals.md`**.
