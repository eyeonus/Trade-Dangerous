# K4 — First-principles trade run architecture review

## Purpose

K4 exists to examine whether the current `trade run` architecture is still the
right architecture.

This is not just another TradeCalc optimisation packet.

K2 and K3A made the existing preload path less wasteful. That work was useful,
but it also exposed the deeper issue: `trade run` still behaves as though
building a broad Python-side market cache is the natural first step for answering
a route query.

That assumption must now be challenged directly.

---

## Historical context

The original `TradeDB()` design made sense in a different usage model.

The original idea was broadly:

```text
create/load TradeDB
keep it around
answer many questions from the populated object
maybe never exit
```

In that world, paying a high up-front cost to hydrate the database into Python
objects and indexes could be justified. The cost would be amortised over many
queries.

That is not how normal CLI use now behaves.

Current command-line use is usually closer to:

```text
start process
construct command/backend state
answer one query
exit
```

Under that model, the old cache-first architecture becomes expensive in the
wrong place. We pay the cache construction cost for a single command and then
throw the cache away.

This was already recognised in discussion #245, "Ask not for whom the bell
tolls, it tolls for TradeDB()". That discussion identified `TradeDB()` as a
large compatibility object that had accumulated multiple responsibilities:

```text
DB lifecycle/access
legacy wrapper objects
large in-memory indexes
lookup semantics
CommandEnv integration
routing/range support
```

Earlier checkpoints addressed parts of that problem:

```text
F — resolver contract and parity tests
G — resolver-first execution flow
H/I — migrate several commands to resolver/ORM paths
J — split TradeDB by capability
K1/K2/K3A — reduce TradeCalc setup cost inside the remaining run path
```

Those checkpoints were useful and should not be discarded.

But they did not answer the central `trade run` question:

```text
Should route generation still begin by materialising a large market subset into
Python?
```

---

## Architectural diagnosis

The current `trade run` path still effectively does this:

```text
SQL database
→ select many StationItem rows
→ copy them into Python
→ build Python maps/indexes
→ perform database-like filtering and joining in Python
→ answer one command
→ discard the Python-side cache
```

That is a bad default cost model unless the cache is reused.

In effect, `TradeCalc` is creating a secondary query engine in Python space,
then running route-search logic over that secondary structure.

The database engine is already built to perform set filtering, joins, grouping,
ordering, and pruning. K4 should examine which work genuinely belongs in Python
and which work should be pushed back into the database.

A trade edge is fundamentally a database join:

```text
source StationItem with supply
JOIN destination StationItem for the same item with demand
WHERE demand_price > supply_price
```

The real route logic adds constraints and scoring, but the basic candidate-edge
generation is relational data work.

The question is whether Python should receive:

```text
millions of raw market rows
```

or:

```text
candidate trade edges for the current route frontier
```

---

## Why this matters now

Further K3 work would continue polishing the preload/cache path.

Examples of possible K3-style work include:

```text
more SQL filters before preload
SQL-side age calculation
chunking the row scan
item-level pruning
```

Some of that might still be useful, but it is lower-value until K4 answers the
larger design question.

If K4 concludes that the preload-first architecture should be replaced or
substantially demoted, then extra K3 preload polishing risks optimising a cache
that should not survive in its current form.

Therefore:

```text
K3A remains useful tactical containment.
Further K3 preload work is paused pending K4.
```

---

## Current known state

K1 showed that `TradeCalc.__init__()` row scanning dominated setup time.

K2 proved that exact station-to-station one-hop runs can be dramatically
narrowed before `TradeCalc` construction.

K3A pushed station capability filters into the preload SQL:

```text
pad
planetary / no-planet
fleet carrier
settlement
black market
max LS
```

K3A also preserved explicit anchor station rows so that
`checkStationSuitability()` can still produce correct user-facing errors.

Live validation showed that K3A reduces row scans for constrained runs and that
explicit anchor mismatch errors still work for pad, planetary, and no-planet
cases.

Those results are enough to treat K3A as useful and validated.

They do not prove that the broader preload model should continue.

---

## Core K4 question

```text
Should trade run continue to build a broad Python-side market cache,
or should the database generate route candidates directly?
```

This question must be answered before further preload-oriented K3 work.

---

## Scope

K4 should examine the current route data flow:

```text
run_cmd
→ CommandEnv
→ TradeDB / TradeORM
→ TradeCalc
→ Route generation
→ Rendering
```

It should identify:

```text
which data structures TradeCalc currently consumes
which of those structures are TradeDB legacy wrappers
which operations are really SQL filters or joins
which operations are genuinely route-search/scoring logic
which behaviours are user-visible and must be preserved
which behaviours are accidental legacy artefacts
```

Specific structures to inspect include:

```text
TradeCalc.stationsBuying
TradeCalc.stationsSelling
TradeCalc.trades
TradeDB.itemByID
TradeDB station/system/item wrapper expectations
checkStationSuitability() dependencies
Route / Hop construction and rendering dependencies
```

---

## Non-goals

K4 is not immediately a rewrite.

Do not begin by replacing route maths.

Do not start by deleting `TradeCalc`.

Do not continue expanding K3 preload optimisation unless K4 explicitly decides
the preload model remains the right architecture.

Do not assume unknown external consumers or enterprise compatibility burdens
without evidence.

Do not introduce speculative geometry pruning as a general solution. Modern jump
ranges mean geometry often degenerates into "the whole bubble is reachable"
unless the user has already supplied a meaningful geometric constraint.

---

## Design principles

### 1. Let the database do database work

Filtering, joining, grouping, and basic candidate selection should stay in SQL
where practical.

Avoid this pattern:

```text
query IDs/rows from DB
store them in Python
feed them back into another DB-like operation
```

Prefer composable SQL:

```text
subqueries
CTEs
EXISTS predicates
JOINs
VALUES constructs for small explicit sets
```

Temporary tables may be useful later, but they require careful connection/session
lifetime handling. They should not be the first move unless clearly justified.

### 2. Python should own route state, not raw global market state

Python should probably continue to own:

```text
route object construction
hop state
score comparison
branch pruning
user-facing error handling
rendering decisions
```

The database should probably own:

```text
supply/demand row matching
item equality joins
station capability filters
age filters
basic profitable-edge filters
avoid filters
candidate destination narrowing
```

### 3. Prefer frontier-driven candidate generation

Instead of asking:

```text
What does the whole market look like?
```

ask:

```text
From the current route frontier, what viable next trade edges exist?
```

Candidate model:

```text
1. Start with current source/frontier station IDs.
2. Query supply rows for those stations.
3. Join to demand rows for the same items at viable destination stations.
4. Apply active station/item/age/capability filters in SQL.
5. Return candidate edges.
6. Let Python score, prune, and extend routes.
7. Repeat for the next hop.
```

This must be batched by frontier, not implemented as one SQL query per route
branch.

### 4. Keep visible behaviour under control

Some route behaviours are user-facing and must be preserved unless deliberately
changed.

Examples:

```text
explicit --from / --to suitability errors
avoid/via semantics
pad/planetary/fleet/settlement filters
cargo/credit/capacity constraints
route output shape
profit calculations
```

Other behaviours may be implementation accidents. K4 should identify them rather
than preserving them blindly.

---

## Investigation tasks

### K4.1 — Map current run data flow

Document the current path from command invocation to route output.

Minimum questions:

```text
Where is TradeDB constructed?
Which load tier is used?
Where is TradeCalc constructed?
Which TradeDB structures are passed into TradeCalc?
Which structures are read during TradeCalc.__init__()?
Which structures are read during route expansion?
Which structures are only needed for rendering?
```

Output:

```text
a current-flow map, preferably in docs/K4_TRADE_RUN_ARCHITECTURE.md or a
companion note
```

### K4.2 — Inventory Python-side database work

Identify operations currently performed in Python that are logically SQL work.

Examples to look for:

```text
matching supply rows to demand rows by item
filtering stations by capability
filtering by avoid lists
filtering by age
discarding unprofitable trades
building station/item lookup maps solely for later filtering
```

Output:

```text
a list of Python-side operations that are candidates for SQL pushdown
```

### K4.3 — Identify non-negotiable behaviour

Record the behaviours that must survive an architectural change.

At minimum:

```text
explicit anchor error provenance
route result correctness for representative commands
legacy command-line options
avoid/via/filter semantics
credit/capacity/profit calculations
debug/timing observability
```

Output:

```text
a preservation list and a deliberate-change candidate list
```

### K4.4 — Sketch candidate edge-generation SQL

Produce a candidate query shape for one-hop trade edges.

It does not need to be final production SQL.

It should show how to express:

```text
source stations/frontier
destination station candidates
same-item supply/demand join
supply_units > 0
demand_price > supply_price
age constraints
station capability constraints
item filters
avoid filters
```

Output:

```text
candidate SQL or SQLAlchemy Core shape
EXPLAIN output where useful
rough timing against live SQLite if practical
```

### K4.5 — Decide preload, replace, or hybrid

K4 should end with a decision, not drift into indefinite research.

Possible outcomes:

```text
A. Keep preload-first for now, with evidence.
B. Replace preload-first with SQL/frontier-driven candidate generation.
C. Hybridise: use a narrower route-specific provider while keeping some legacy
   structures temporarily for rendering/compatibility.
```

Output:

```text
a written decision and next implementation checkpoint
```

---

## Candidate replacement concept

A likely direction is a route-specific provider, not direct random SQL inside
`TradeCalc`.

Possible name:

```text
RouteMarketProvider
```

Possible responsibility:

```text
accept command constraints
accept current frontier/source station IDs
query SQLAlchemy/Core for viable trade edges
return compact candidate edge records
avoid hydrating broad legacy TradeDB wrapper graphs
```

Possible edge record fields:

```text
source_station_id
dest_station_id
item_id
buy_price
sell_price
gain_per_ton
supply_units
demand_units
modified / age
distance / jump-relevant fields if needed
```

This provider might initially return enough information for current `TradeCalc`
to continue constructing legacy-ish `Trade`/`Hop`/`Route` objects, while moving
candidate generation out of the Python-side market cache.

That would allow migration without a big-bang rewrite.

---

## Relationship to TradeDB vs TradeORM

K4 is also a continuation of the TradeDB retirement discussion.

`TradeDB` is now increasingly a compatibility layer. That is intentional.

The question is whether `trade run` still has a legitimate need for
TradeDB-shaped data, or whether it should consume data through a SQLAlchemy-era
route provider.

If some front-loaded data is still necessary, K4 should ask:

```text
Why is TradeDB the thing constructing it?
```

A modern provider can be narrower, command-specific, and SQL-backed.

---

## Relationship to GUI/session reuse

Long-lived cache semantics may still be valid in GUI or daemon-like contexts.

That is separate from normal CLI command execution.

A future GUI checkpoint may decide to keep a long-lived resolver/session/cache
where repeated queries make it worthwhile.

K4 is concerned with the CLI `trade run` cost model first:

```text
one process
one query
exit
```

Do not reject caching everywhere merely because CLI cache lifetime is poor.

---

## Acceptance criteria

K4 is complete when the project has:

```text
- a documented current data-flow map for trade run
- an inventory of TradeCalc dependencies on TradeDB structures
- a list of Python-side operations that are really SQL filters/joins
- a candidate SQL/frontier edge-generation shape
- timing or EXPLAIN evidence where practical
- a written decision: keep preload, replace preload, or hybridise
- a named next implementation checkpoint
```

K4 is not complete merely because another preload filter was added.

---

## Working decision until K4 closes

Until K4 produces its decision:

```text
K3A is accepted as tactical containment.
Further K3 preload/cache optimisation is paused.
Next workers should start with K4, not K5/K6/K7.
```