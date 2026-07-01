# Trade Dangerous v13 — Changelog

The detailed, human-written history of the v13 line. Changes are bundled by *what
actually changed* — one entry per real change, drawing together the many commits,
checkpoints, and planner slices that produced it — and grouped by area rather than
logged in commit order.

It sits alongside two other documents:

- [`RELEASE_NOTES_v13.0.0.md`](RELEASE_NOTES_v13.0.0.md) describes what v13 *is*, as
  an introduction to the application. This changelog describes what *changed* to get
  there, and why.
- The auto-generated [`CHANGELOG.md`](../CHANGELOG.md) at the repo root is the
  machine ledger — one terse entry per release, built from commit messages. Because
  v13 lands as a single squashed commit, that ledger cannot hold this detail; this
  document fills the gap.

A note on what is *not* here: the work took several hundred commits, many of them
process and documentation steps, interim corrections, or five small commits that add
up to one real change. Those are deliberately collapsed. What follows is the set of
changes a user or a developer would actually care about.

---

## v13.0.0

v13 is not an incremental release. The `trade run` route engine was rebuilt from
scratch as a database-driven planner; every other command was moved off the old
"load the whole galaxy into memory, then work on it in Python" model onto a new
ORM-backed core; the schema was trimmed of dead weight; and the graphical interface
was reworked to match. The result is an application that answers the same questions
far faster, against far larger live data, with a rebuilt `trade run`.

The thread running through every change below is the same: the old design paid a
large, fixed setup cost — a full preload and reshape of the dataset — before doing
even a small piece of work. v13 removes that obligation. Constraints now narrow the
work inside the database before any market data is touched, and commands materialise
only the rows they need.

**A clean database rebuild is required to run v13.** See *Breaking changes*.

---

### Breaking changes

**A full database rebuild is required.** The schema changed in several ways (below),
and v13 does not upgrade an existing database in place. The supported path is a clean
import. There is deliberately no migration logic, old-schema detection, or runtime
babysitting of a pre-v13 database — later refactor stages were always going to force
a rebuild, so the rebuild is the contract.

**The data feed is v13-only.** The companion listener server
(`Tromador/TradeDangerous-listener`) no longer emits data that a v12 client can
import; the published CSV contract changed with the schema. There is no overlap
period: update the client to v13 first, then do a clean import, in that order.

**The `Added` table is gone.** The obsolete `Added` table and the `System.added_id`
column were removed from the ORM, the canonical SQLite schema, the importers, the CSV
export contract, and every runtime path. The exported `System.csv` no longer carries
an `added_id` column.

**The `RareItem` table is gone.** Rarity is no longer a separate table. It is now a
property of the item itself — an item is rare when `Item.rare_station_id` is set,
which also identifies its canonical home station — and `is_rare` is computed from
that rather than stored. A rare's live market is treated as ordinary market data like
any other commodity. `Festive Gifts` is deliberately excluded from canonical rare
handling.

**The outfitting tables are gone.** `Upgrade`, `UpgradeVendor`, and the
`FDevOutfitting` EDCD bridge were dropped, and the importer no longer downloads the
EDCD `outfitting.csv`. Nothing queried them — `UpgradeVendor` was a long-standing
placeholder for a `buy --upgrade` mode that was never built — and at roughly 3.6 GiB
it cost hours of import time for data nothing used. Ships are unaffected:
`Ship`, `ShipVendor`, `FDevShipyard`, and the `Station.outfitting` yes/no flag all
remain.

**Several commands and options were removed.** See the dedicated *Removed* section.

---

### The route planner (`trade run`)

`trade run` is the heart of the release. The previous engine built a full in-memory
model of the galaxy (`TradeDB` preload plus a `TradeCalc` scan that rebuilt
Python-side buy/sell maps) on *every* run before it could plan a single route — a
cost measured in tens of seconds against live data, and one that scanned every market
row regardless of how tightly the route was constrained. That model is retired.
`trade run` is now served by a clean-room planner (`tradedangerous/planner/`) that
queries the database directly and materialises only the rows a given search needs.

The command-line surface is largely **retained** — most options work as they did in
the legacy router — but every one was reimplemented on the new engine. The genuinely
new options are few: `--sco`, `--max-price`, `--no-bulk-cap`, and the rewritten output
(`--raw` and the rich tables). Several options were removed; those are listed under
*Removed*. The entries below note, for each area, what is new, what changed in
behaviour, and what carried over.

#### Route shapes

**All four anchoring shapes, single-hop and multi-hop.** A route is defined by how
many hops it has and which ends you name; either end can be a fixed point you supply
or an open end the planner chooses. That gives a full grid — fixed pair,
open-destination, open-origin, and fully-unanchored — at one hop or many. The
single-hop forms were built first (fixed pair, then open destination, open origin,
and unanchored galaxy search); the multi-hop forms followed, unified onto a shared
open-anchor engine so the open-origin and open-destination directions are one
direction-keyed implementation rather than two.

**Multi-hop search runs over a shared beam/frontier engine**, with the route-planning
code split into one module per shape (`route_onehop`, `route_anchored`,
`route_single_anchor`, `route_unanchored`, `route_via`) sitting over common machinery
in `route_common`. The split keeps each shape's search strategy clear while the
*meaning* of every option is resolved once into the request and consumed from there.

**Endpoints may be a station or a whole system.** Name a station and it is used
directly; name a system and the planner expands it to its eligible stations and picks
the best pair. This expansion groundwork underpins every shape.

**Partial multi-hop routes are returned** when a full-length route cannot be
completed, so a search that runs out of viable hops still gives you the best
shorter route it found rather than nothing.

**Galaxy-wide searches are guarded.** The two shapes with both ends open (one-hop and
multi-hop unanchored) are inherently broad, so they sit behind an interactive
confirmation prompt and exit cleanly on a non-affirmative answer or a non-interactive
invocation — they never run unguarded.

#### Route modifiers

Every route modifier below **carries over from the legacy router** — none is new in
v13 — but each was reimplemented on the new engine, and several had their edges
tightened or settled in the process. What is worth recording:

**`--towards SYSTEM`** steers an open-destination route toward a target system
without forcing arrival. It requires `--from`, cannot be combined with `--to`, and
makes every hop land strictly closer to the target. Routes are ranked progress-first:
closest to the target wins, then fewer hops, with profit only breaking ties. A hop
that reaches the target ends the route; if the hops run out first, it gets as close
as it can.

**`--loop`** plans an anchored round trip that returns to its own starting station. It
requires a named `--from` and at least two hops. The galaxy-wide loop — letting the
planner choose the loop's origin — was considered and deliberately *not* supported (a
decision taken with the upstream maintainer); `--loop` without `--from` is rejected.

**`--via`** forces the route through up to six named waypoints, which may be systems or
stations, visited in any order. Every waypoint must be visited or the run fails —
there is no partial-via route — and the route must have at least one anchor (`--from`
or `--to`); a fully-unanchored via is rejected.

**`--direct`** is the relocation run: the single most profitable trade between a named
`--from` and a named `--to`, with no jump-path or distance checks, because you fly the
route yourself. It needs both endpoints and is single-hop only; `--ly-per` and
`--jumps-per` are accepted but ignored since reachability is not checked.

**`--avoid`** excludes a commodity, a system, or a station, fuzzy-matched like the
endpoints. An avoided commodity is never bought; an avoided station is never used; an
avoided system is barred both as a route station and from jump-path transit — the
route will not even pass through it, which covers the permit case. An explicitly named
`--from` is exempt as the origin, so you can start in an avoided system but the route
never returns to it.

**`--unique` / `--loop-interval N`** are the no-revisit constraints. `--unique` forbids
visiting any station twice; `--loop-interval N` is the bounded form, allowing a revisit
only after N hops have passed. They are now enforced across every engine
(fixed-terminal, open-anchor, and via), threading a per-chain visited history, and an
impossible revisit route fails with a specific `NoUniqueRoute` message rather than an
empty result.

**Empty-jump positioning — `--start-jumps` / `--end-jumps` / `--empty-ly`** — treats a
named endpoint as a positioning anchor rather than a forced trade endpoint.
`--start-jumps N` expands the eligible origins to every station within N empty jumps
of the `--from` anchor's system; `--end-jumps N` does the same for destinations around
`--to`; `--empty-ly` sets the unladen jump range for that fan-out, falling back to
`--ly-per`. The repositioning flight is shown in the route output.

#### Reachability and ships

**Multi-jump per hop** (controlled by `--jumps-per`, retained) was reimplemented:
reachability is now computed on demand against an in-memory bubble of reachable
systems with KDTree spatial adjacency (this is why `scipy` is a new dependency), and
the distance is reported as polyline length rather than straight-line.

**`--jumps-per` defaults by range.** When omitted it is 2 jumps if `--ly-per` is 12.5
or less, otherwise 1. Short-range ships reach too little on a single jump, so the
default opens up for them; the practical note is that at a typical `--ly-per` of 20
you will want `--jumps-per 2` for real multi-hop routes.

**`--pad-size` is now a ship-fit threshold** rather than an exact filter: `L` keeps
only large-pad stations, `M` keeps medium and large plus unknowns, `S` keeps
everything. A station whose pad size is unknown is admitted unless `--pad-size L` is
set, so you are not silently denied a viable stop on missing data.

#### Trade, cargo, and pricing

**The cargo optimiser** fills the hold for maximum total profit across several
commodities at once, bounded by capacity, credits, source supply, and destination
demand. Crucially, destination demand is treated as a *hard quantity cap* on how much
you can sell, not merely a test of whether a trade qualifies — the plan will not
assume it can offload more than the market will take.

**A destination counts only at demand of 2 or more.** A stocked commodity reports its
dormant buy side as 0 or 1, so a demand of 1 is an unfillable sale dressed up as a
trade; the planner declines it rather than planning a sale that cannot happen.

**Bulk-sale-tax cap (new, on by default).** For Metals and Minerals the planned sale
quantity at a destination is capped at 25% of demand, to stay clear of the in-game
bulk-sale price penalty that would otherwise make the projected profit fictional.
`--no-bulk-cap` turns this off and fills full demand at the headline price.

**`--max-price` (new, default 1,500,000 cr/t).** An absolute price ceiling that clips
the fictional multi-million-credit rows owner-set fleet-carrier prices can produce, so
a single absurd listing cannot dominate the search. `--max-price 0` disables it.

**`--sco` (new)** declares a Supercruise Overcharge drive, where arrival distance
barely matters; it removes the arrival-distance penalty so distant stations are no
longer scored down, overriding any `--ls-penalty`.

**Trade filters** — `--gain-per-ton`, `--max-gain-per-ton`, `--supply`, `--demand` —
and the budget controls `--insurance` (a reserve not spent on cargo), `--limit` (a
per-commodity unit cap), and `--margin` (the fraction of projected profit not trusted
as later buying power) shape what the optimiser will consider.

#### Name resolution

**Endpoints resolve by syntax, not cross-namespace guessing.** A bare name is tried
as a system, then as a station; `@name` forces a system; `/name` forces a station;
`system/station` is a station within a system; `system/` is the system. This is the
same place-resolution contract the rest of the tool uses, so a name means the same
thing in `run` as it does in `buy` or `nav`.

**Partial matching with `@N` disambiguation.** Names match exact-first, then prefix,
then substring, with no typo tolerance. Duplicate-name systems are disambiguated with
`@N` and their coordinates. Matching is backed by a normalised `lookup_name` key, so
punctuation in your token no longer blocks a match — `CD37` resolves `CD-37 15492`.

**Resolution is visible.** A non-exact match is echoed back as `… resolved as …` so
you can see what was chosen, and a no-trade error names the resolved endpoints rather
than the raw input.

#### Output

**Rewritten output.** The default is a rich, colour, station-by-station table — a row
per stop showing what you sell on arrival and what you buy before leaving, so it reads
the way the route is flown. It comes in three verbosity tiers: `--summary` (both
sides, no prices, no nav, plus profit), standard (prices the buy side, shows the jump
route), and `-v` verbose (prices both sides, lists every jump). Each tier adapts to
terminal width, shedding columns rather than wrapping into a mess, so Profit survives
even at 80 columns.

**`--raw`** selects a plain-text, hop-centric, 80-column format for grep, pipes,
scripts, diagnostics, and the GUI's intercept path; **`--80col`** and **`--narrow`**
force the portable layout (a piped or redirected run falls back to 80 columns anyway).

**`--progress` (`-P`)** (retained) shows a live, transient search display that is
cleared before the result prints: an "M of N hops" bar with a per-node sub-row for
searches of known length, a spinner with a candidate counter for open-ended ones. It
cannot be combined with `--raw`.

**`--checklist`** (retained) steps through the planned route interactively, stop by
stop. Its old companion modes are gone — it replaces what the removed X52 Pro MFD mode
and `--show-jumps` option used to do — and it cannot be combined with `--routes`
greater than 1.

**`--routes N`** (retained) returns up to N routes, numbered best-first, instead of
just the winner, for both single-hop and multi-hop shapes. N is a maximum, not a
quota.

**Failure messages are specific.** A search that finds nothing now says *why* in
actionable terms, and the old internal-detail footer was dropped.

#### Planner performance

The planner is built to stay fast on a full live dataset, and the techniques shape
what the options cost. Spatial constraints narrow the candidate set in SQL before any
join to market data — candidate ids never leave SQL as a Python list to be handed back
as a giant `IN (…)`. Open-ended searches stream candidates best-first and stop the
moment the remaining tail cannot beat the best result held, so the tail is never read.
Cargo solves that provably cannot improve on the best route so far are skipped
entirely, and the ones that run stop once confident rather than grinding to prove the
optimum. Market rows are qualified once per run into run-scoped temporary tables and
reused, and `--age` is a genuine cost lever — stale stations are dropped before the
search walks them, so a tighter window is a faster run.

---

### Commands

Every command was moved off the full-preload model. The pattern is shared: resolve the
inputs through the resolver first, narrow by any spatial or attribute constraint in
SQL, and hydrate only the surviving rows.

**`local`** previously loaded the full galaxy and filtered stations in Python over the
hydrated objects. It now resolves the origin through the resolver, bounds the search
with an SQL `BETWEEN` box on system coordinates followed by an exact sphere check in
Python, and pushes every station filter into SQL — fleet and settlement state resolved
through the station-type registry, `--trading` as an `EXISTS` subquery over market
data, and age/count fetched in a single aggregate gated on whether they are needed.
The result is roughly 8× faster warm (about 0.85 s against a ~7 s baseline) — "effectively
instant". One deliberate behaviour change: the `Mkt` column in `--detail` reads the
station's stored market flag directly, where the old preload coerced it; the `--trading`
filter itself is unaffected.

**`market`** now reads a station's market through a single parameterised query on the
ORM session and resolves item metadata by primary-key lookup, with no in-memory
commodity index or station-dict traversal. Basic queries are effectively instantaneous;
`--detail` (which adds average buy/sell per visible item) runs in well under a second.

**`buy`** was the trickiest migration. The first cut regressed because it expanded
broad candidate sets before filtering and ran an unconditional station-wide age
aggregation. The fix constrains the search to nearby stations *before* probing markets
or ship vendors, applies `--age` during the lookup rather than after, removes the
blanket age aggregation, chunks station hydration against the bind-parameter ceiling,
and tolerates unknown ship costs while sorting. Canonical buy now runs around 3.9 s
cold and ~1 s warm, faster than the old cold *and* warm baselines; ship-availability
search uses the same near-station-first narrowing. A `lookup_ship` resolver was added
to support it.

**`sell`** mirrors `buy`: a bounding box materialises nearby station ids before the
market table is queried, and age, demand, and price filters are pushed into SQL.
Station hydration is chunked via a joined load, the legacy station wrappers were
replaced with ORM attributes and type-id-based fleet/settlement helpers, and the
no-data error is context-aware (it names the item and the near-system). Cold time fell
from ~7.3 s to ~1.2 s and warm from ~7.8 s to ~0.8 s (around 6× and 9.5×).

**`olddata`** was rebuilt SQL-first. It aggregates the most-recent market timestamp per
station into an age, pushes all filters (the `--near` bounding box and exact sphere,
minimum age, pad, planetary, fleet/settlement by type-id, and max distance from star)
into SQL, orders oldest-first and applies the limit *in the database*, then hydrates
only the survivors. Hydration is chunked against the bind-parameter ceiling, and
`--route` is validated at preflight before any query runs.

**`nav`** was rebuilt as a straightforward A-to-B jump-route plotter on the planner's
public reachability surface — no full preload. It uses iterative-deepening from the
straight-line minimum, supports `--via` (ordered waypoints), `--avoid` (systems removed
from the graph, with the avoided-vs-required-waypoint conflict rejected up front and the
initial source exempt), and `--stations` (lists each stop's stations). The old
`--refuel-jumps` option was dropped: a correct fuel/neutron plotter needs a full ship
model `nav` has no business carrying, and Spansh already does it well.

**`direct`** is `trade trade` rebuilt and renamed to the full "Trade 2.0" scope, with
`trade` kept as a first-class compatibility alias (a thin shim that re-exports the
engine and sets its own command name). Either endpoint may be a station or a whole
system, resolved through the shared place resolver. `--best` collapses a system-wide
comparison three ways (per-station, per-item, station) using window functions portable
across SQLite and MariaDB; `--local` lists in-system station-to-station trades from a
single system argument; `--age` filters freshness on both ends. Output gained From/To
station columns (shown when the matching side is a system) and a summary header.
Multi-station output is bounded by a default cap with a notice when neither `--limit`
nor `--best` is set, self-trades are excluded universally, and `--fill` stays valid
per row while `--load`/`--full-load` are rejected in multi-station results.

#### Cross-command changes

**Resolver-first execution model.** Commands now declare a capability — `Needs.NOTHING`
or `Needs.RESOLVER` — and the CLI builds exactly that backend, with no full-preload tier
left to fall back to. The common arguments `--near`, `--from`, `--to`, `--avoid`, and
`--via` are resolved through the ORM before a command's own logic runs, and the GUI
mirrors the same capability-aware backend selection.

**A shared, indexed resolver.** Name resolution was rewritten as self-contained ORM
queries: `lookup_system`, `lookup_station`, `lookup_place`, `lookup_item`,
`lookup_category`, `lookup_ship`, and `item_by_id`. It implements exact, prefix, and
substring matching with two-step (index-friendly) candidate queries, `@N`
disambiguation, and a normalised `lookup_name` column so punctuation no longer blocks a
match. Behaviour is locked by a parity test suite against the documented contract. One
deliberate divergence from the old in-memory matcher: an exact duplicate station name
raises an ambiguity error asking you to disambiguate, rather than silently returning an
arbitrary one of the duplicates.

**Range options standardised.** `--ly` is now consistently the search-bubble radius
(default 64 ly) on the search commands, and `--ly-per` is the per-jump range on the
routing commands (no default — it must be given). The fallback was changed from `x or
default` to `x if x is not None else default`, so `--ly 0` is now honoured as "this
system only" instead of being silently swallowed. The global `--link-ly` switch — a
misused shared default — was removed.

**Settlement filter and station-type registry.** Station classification now uses a
single canonical 0–15 registry owned by Trade Dangerous and mapped from the source data
on import, replacing the old collapsed type-id meanings. The filter is `--settlement`
(it classifies settlements, not Odyssey capability), and fleet/settlement state is
derived as yes/no/unknown — an unknown type is unknown, not silently "no".

---

### Graphical interface

The GUI began this cycle non-functional — it died at import on the retired backend
module and selected its backend through a dead capability model — and was rebuilt over
the course of the release.

**Rebuilt on the ORM core.** The GUI now constructs a `TradeORM` backend through a
shared builder and runs every command through the same
`CommandIndex().parse → cmdenv.run(...)` path the CLI uses, so a GUI result is exactly
the CLI result. Each command runs as its own short-lived process, keeping actions
isolated and instantly cancellable; autocomplete is served by a long-lived engine that
opens a fresh session per query.

**The detached route checklist** is the headline new feature: a movable, native window
that walks a planned route stop by stop — what to sell on arrival, what to buy before
leaving, and the jumps to the next stop — living independently of the main window, with
several route checklists open side by side at once and an in-window dialog fallback in
browser mode.

**Run interactivity.** The command worker was given a non-interactive stdin so it no
longer crashes on prompts; bare From/To systems are accepted as endpoints; and an
unanchored, galaxy-wide route is handled with a confirm-and-run prompt instead of an
end-of-input crash.

**Journal-driven import.** A configurable game-journal directory was added, along with
import of the commander's owned-ship details from the journal.

**Copy from results.** Rendered output and error/diagnostic text carry copy buttons, so
a route or a stack trace is easy to lift out for a forum post or a bug report.

**Reconciled with the v13 CLI.** Every argv builder was aligned with the post-rewrite
option surface, run output now renders as structured tables (with From/To columns for
`direct`, correct item counts for `nav`/`local`, and a tri-state black-market control),
the run renderer was polished to match the CLI layout on the dark theme, and the new
run and direct options were exposed (`--sco` / `--max-price` / `--no-bulk-cap`, and
`--local` / `--best` / `--age`). Controls for removed options were taken out — the
`--no-planet` filter and the obsolete skip/ship-vendor import controls are gone — and
the native launcher was brought up to NiceGUI 3.11.

---

### Data, schema, and importers

Beyond the table removals listed under *Breaking changes*, the data layer changed in
several ways.

**Canonical station-type registry.** A single 0–15 station-type registry replaces the
old collapsed type-id meanings; the Spansh importer maps source station types through
it, listener/EDDN commodity ingestion does not infer station type, and an unknown
listener-created type defaults to a real "unknown" rather than being guessed.

**SQLite template reconciled with the ORM.** The hand-maintained SQLite template was
brought back into step with the ORM schema: the two ORM-only indexes were added, name
columns widened, `FDevShipyard` given a primary key, the unused buying/selling views
dropped, and placeholder-id sentinels and a station-distance check constraint handled.
The point is to keep the two schemas from drifting apart so a consequential mismatch
cannot slip through.

**Index set.** Exact and prefix lookups are backed by `idx_system_by_name` on
`System(name)` and `idx_station_by_system_name` on `Station(system_id, name)`, plus the
category and item name indexes — confirmed present on both SQLite and MariaDB after a
normal rebuild.

**Spansh importer.** It now streams the gzipped galaxy dump rather than loading raw
JSON, writes each station's market and shipyard as a whole snapshot (so a re-import
replaces a station's data cleanly instead of leaving stale rows), guards a station-id
overflow sentinel, and writes rarity onto `Item.rare_station_id` directly. Generic CSV
dialect fallbacks were replaced with explicit guardrails.

**eddblink importer.** It applies the same whole-snapshot station write rule to its
listings, and `.prices` placeholder stations are given a `lookup_name` so they resolve
through the normalised-name matcher like any other station.

**Database engine.** The engine uses `NullPool` — it holds no connection between
queries, so a rebuilt SQLite file or an updated MariaDB row is picked up by the next
query automatically — and the bulk-session tuning was consolidated into one place.

---

### Removed

**`trade rares`** is retired. The useful part of it moved to `buy --rare`, which
filters on the canonical `Item.rare_station_id` predicate. The old command's rich
rare-only metadata (cost/allocation columns, illegal/suppressed flags) was dropped by
deliberate decision, in line with the diminished in-game role of rares; `buy --rare` is
a live-market view, so a rare with no live market row at its home station will not list.

**`update`, `station`, and `shipvendor`** are removed. They had already been reduced to
no-op deprecation stubs (printing a banner and doing nothing); v13 removes the commands
entirely, so their names are no longer registered and a script that calls one now gets
an unknown-command error rather than a deprecation notice.

**`--link-ly`** is removed. It was a misused shared default-radius number rather than a
real reachability filter, and its only legitimate routing meaning is covered by
`--ly-per`.

**`--no-planet`** is removed. It duplicated `--planetary N` exactly — both resolved to
the same filter — through separate plumbing, so it carried no capability of its own.

**`nav --refuel-jumps`** is removed; fuel and neutron routing are left to Spansh (see
the `nav` entry).

**`run --shorten`, `--max-routes`, `--prune-score`, and `--prune-hops`** were removed.
`--shorten` added gated fetch calls for little benefit; the other three were internal
beam-search / partial-route-retention controls (route pruning and the per-hop retained
count) that are not worth exposing on the new engine.

**`run --x52-pro` (the X52 Pro MFD mode) and `--show-jumps`** were removed; the
interactive `--checklist` covers what they did.

**`run --odyssey` / `--od`** was renamed to `--settlement` — the filter classifies
settlements, not Odyssey capability (see *Commands*).

---

### Performance

Representative live-SQLite figures, warm, before → after:

| Command | Before | After |
|---------|--------|-------|
| `local` | ~7.0 s | under 1 s (≈ 8×) |
| `sell` | 7.8 s | 0.8 s (≈ 9.5×) |
| `buy` | ~7.1 s | ~1.0 s (≈ 7×) |
| `market` | ~6–7 s | effectively instant |

`trade run` is a different kind of workload. The old engine spent tens of seconds
preloading and reshaping the whole galaxy before it could plan anything; the planner
does no such preload, and the streaming, pruning, qualify-once, and age-cut techniques
described in its section keep it fast on live data. (`run` is left qualitative here
because its meaningful before/after benchmarks were taken mid-rewrite, so there is no
clean single post-rewrite figure on record.)

The common principle across every one of these: spatial and attribute constraints
narrow the work in SQL before any market data is read, and nothing materialises a
column of ids into Python only to hand it back to a later query.

---

### Under the hood

**The preload model is retired.** `tradedb.py` and `tradecalc.py` — the in-memory
`TradeDB` graph and the `TradeCalc` route maths that scanned every market row per run —
were archived. All data access now goes through the ORM-backed `TradeORM`. The legacy
"handle" backend lane and its tier vocabulary were removed, and `import` and
`buildcache` were moved onto the ORM handle.

**The planner is a fixed pipeline** — `CLI parser → RunRequest → planner → RunResult →
renderer` — with two plain data objects forming the boundary so nothing else crosses
in or out: no in-memory galaxy model, no command-layer objects reaching into the
planner. Route planning is split into per-shape modules over shared core services
(database access, the cargo optimiser, reachability, scoring). The full internal design
is documented in [`Developers/planner-internals.md`](Developers/planner-internals.md).

**Legacy audit and prune.** A reachability audit classified the old codebase, after
which confirmed-dead helpers were removed and retired tooling was archived — the old
`eddb`, `edsm`, and `eddn` scripts, the clipboard and distance-submission utilities, and
the legacy database adapter among them. Post-refactor leftovers (unused imports, an
orphaned preload hook, stale TODOs) and comments that described no-longer-true behaviour
were cleaned up in a closing pass.

**Rendering.** Route detail rendering moved onto Rich text for the colour output.

---

### Dependencies and build

- **`scipy`** was added for the KDTree spatial adjacency the route planner's
  reachability relies on.
- **`pythonnet` 3.1.0** was adopted (for Python 3.14 support), and **NiceGUI** was
  updated (the GUI launcher tracks 3.11).
- Security bumps were taken for `aiohttp`, `cryptography`, `starlette`, and others; the
  dependabot configuration was archived; and the release-automation changelog handling
  was fixed.
