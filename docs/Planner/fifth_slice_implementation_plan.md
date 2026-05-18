# trade run Fifth Slice Plan — Unanchored Galaxy Search

## Purpose

Extend the one-hop planner so a hop can be planned when **both** endpoints are
left open — neither `--from` nor `--to` supplied. The planner selects the
origin and the destination, finding the single best one-hop trade anywhere in
reachable range.

Slices 3 and 4 delivered the open-ended search anchored on a fixed endpoint:
one endpoint named, the other chosen by the planner, the named endpoint
anchoring a bounded spatial query. That anchor is the reason those searches are
fast. This slice removes it. With neither endpoint named there is nothing to
anchor on, so the search is genuinely galaxy-wide and needs a different
algorithm — not a parameterisation of the anchored one.

This is the last one-hop shape. After it the one-hop family is complete and
`--old` no longer holds any one-hop shape the new planner cannot serve.

The architecture boundary is unchanged:

```text
RunRequest -> planner -> RunResult -> renderer
```

## Absolute Source Quarantine

The quarantine remains mandatory. Do not inspect, import, call, subclass,
adapt, translate, summarise, or ask another tool to summarise:

```text
tradedangerous/tradecalc.py
tradedangerous/tradedb.py
```

Do not use legacy route-planning objects, legacy database facade objects, or
private route/cache/frontier structures, and do not convert planner results
into legacy route objects. `tradedangerous/commands/run_cmd.py` remains
permitted — it is the command entry surface, not a quarantined module.

The legacy planner supports the unanchored search today. It is **not** a
reference for this slice. The new planner's unanchored search must be designed
from the behavioural spec and the planner's own Slice 1-4 code, not from how
`--old` does it.

Permitted implementation sources:

```text
- black-box trade run behavioural specification
- first through fourth slice implementation plans and completion reports
- this plan
- the current planner package
- ORM models and resolver surfaces
- public command parser metadata
- local_cmd.py as the reference spatial-query pattern
- official Python / SQLAlchemy / database documentation
```

## Slice Name

```text
Unanchored Galaxy Search
```

## Goal

Support one-hop planning with both `--from` and `--to` omitted, by adding a
**separate, additive** planner path — not a generalisation of the anchored
open-ended search.

The planner selects both stations: the best one-hop trade between any source
station and any destination station reachable from it in a single loaded jump
(`--jumps-per 1`) or within the same system (`--jumps-per 0`).

Because the search is galaxy-wide it is materially slower than any anchored
shape. The slice ships it behind a confirmation prompt (see Confirmation
Prompt), so the user opts into the wait knowingly.

## Design Decisions Carried In

These were settled with the supervisor (Tromador) and eyeonus before this plan
was written. They are inputs, not open questions.

```text
1. The genuinely unanchored case is implemented, not permanently rejected.
   --old retires at v13 and the new planner must cover every one-hop shape
   before then.

2. The anchored shapes (Slices 1-4) must not be degraded — not in speed, not
   in output, not in behaviour. This is a hard constraint on the slice, not an
   aspiration. See Design Constraint — Anchored Path Untouched.

3. The unanchored search runs behind an interactive confirmation prompt: it
   warns the search is slow and asks the user to confirm before planning
   begins. (eyeonus's call. It also resolves black-box spec open decision #5 —
   "whether broad unseeded galaxy-wide searches should require user
   confirmation".)

4. With no interactive terminal (stdin is not a TTY) the unanchored search
   aborts cleanly instead of prompting. It is a guard against non-interactive
   use, not support for it.

5. GUI integration is owned outside this slice. The GUI hooks commands
   in-process and will handle the unanchored shape its own way (preflight
   refusal, or its own warning). This slice adds no GUI-facing hook, flag, or
   suppression path, and makes no assumption about the GUI.
```

## Design Constraint — Anchored Path Untouched

Decision 2 is structural, and the structure is what enforces it.

```text
- The unanchored search is a new planner function and a new data_gateway
  query function. The anchored planner functions (_plan_fixed_endpoints,
  _best_open_ended_plan) and the anchored query functions
  (fetch_open_ended_trade_candidates, fetch_station_pair_candidates,
  fetch_eligible_stations_in_system) are not modified.

- Because the anchored query functions are untouched, the SQL they emit is
  textually unchanged, so SQLite computes the identical query plan for them.
  Anchored speed is unchanged by construction.

- The dispatch and validation edits are additive. Anchored requests traverse
  them on exactly the path they take today; only a both-omitted request
  reaches new code.

- No shared persistent state is introduced — no precomputed trade-edge table,
  no cache, no derived index the importer must maintain. The unanchored search
  is a query path, not a materialised structure. A query path an anchored
  request never enters costs that request nothing.

- An anchored request never sees the confirmation prompt and never has its TTY
  inspected. The prompt fires on the both-omitted shape only.

Shared *pure helpers* — optimise_cargo, score_with_destination_penalty,
_group_pairs, _pair_is_better, _assemble_result — are reused by the unanchored
path. That is reuse, not coupling: they are pure functions over candidates and
pairs, they touch no SQL and no query plan, and reusing them cannot affect an
anchored request.

The separation is mandatory, not stylistic. Folding the unanchored search into
_best_open_ended_plan would run anchored requests through a generalised query
builder, and Slice 3-4 history shows how little it takes for a generalised
builder to shift SQL shape and flip SQLite off the primary-key plan (the
--pad-size S self-join; the IN(...) literal scan). Keeping the path separate
keeps the anchored SQL identical, which is the guarantee.
```

The Implementation Order captures the anchored timing back to back across the
change as the evidence that this held.

## Supported Command Shapes

Continue supporting every Slice 1-4 shape. Add:

```text
trade run   [--from omitted]   [--to omitted]   --capacity N --credits N --hops 1 --ly-per N
```

Endpoint meanings, complete after this slice:

```text
--from station   fixed origin station                    (Slice 1-2)
--from system    expand to eligible origin stations       (Slice 2)
--from omitted   planner selects the origin               (Slice 4)
--to   station   fixed destination station                (Slice 1-2)
--to   system    expand to eligible destination stations  (Slice 2)
--to   omitted   planner selects the destination          (Slice 3)
both   omitted   planner selects both                     (NEW)
```

Still `--hops 1` and `--routes 1`. With the `--jumps-per` default of 1
(unchanged since Slice 3), the both-omitted shape works without the user
supplying `--jumps-per`.

## Still Out of Scope

```text
- --jumps-per >= 2 with any endpoint omitted   (multi-jump reachability — later slice)
- --jumps-per default keyed to --ly-per        (deferred — see roadmap note)
- --hops > 1, --start-jumps, --end-jumps
- --direct, --towards, --via, --avoid, --loop, --unique, --loop-interval, --shorten
- --routes > 1, --checklist, --x52-pro
- multi-hop search, route frontier, pruning
- --progress
```

Unsupported shapes must continue to fail explicitly when the new planner path
runs.

`--progress` is worth a word. It is the natural companion to a slow search and
the Slice 4 plan parked it "with" the unanchored work. It is still deferred: it
is separable, it is not in the agreed decisions for this slice, and the
confirmation prompt already tells the user the search will take a while. It can
follow as a small additive slice once the unanchored search's real runtime is
known.

## The Central Problem — Bounded Materialisation

This is the one genuinely new problem in the slice, and the rest of the design
turns on it.

Every anchored slice could afford to materialise its full candidate set into
Python, because a fixed endpoint bounded that set. Slice 3-4's open-ended
search anchored one side on a fixed station set and reached the other through
a spatial box around the anchor — both market queries ran off bounded
station-id sets through the `StationItem` primary key, and the candidate count
stayed small.

The unanchored search has no anchor. Both sides are galaxy-wide. The set of
*every profitable reachable trade in the galaxy* is potentially enormous —
materialising it into Python would be the legacy preload failure rebuilt in
miniature, and is not acceptable.

So the unanchored search must be **exhaustive in consideration but bounded in
materialisation**: the database considers every reachable profitable trade, and
hands back only a bounded top set small enough for the existing Python-side
pair evaluation. The slice's target (per Decision 1) is the true global best —
not an approximation — so the bounded top set must be **provably sufficient**:
it must be guaranteed to contain the real winner.

A sound cutoff exists, which is why "exhaustive-correct with bounded
materialisation" is a credible target and not hand-waving:

```text
- A pair's total profit is bounded above by
      capacity_units  x  (best profit-per-unit available to that pair).
  So once any pair has been concretely evaluated to a known total profit T,
  every pair whose capacity x best-per-unit-profit is below T is provably
  unable to win and need never be materialised.

- Without --ls-penalty (the default — --ls-penalty is opt-in) the practical
  score equals raw profit exactly, so ranking is on raw profit with no
  distortion.

- With --ls-penalty the score is raw profit times a multiplier, and the
  protected curve makes that multiplier bounded (curve is a bounded composite;
  weight is clamped to [0,1]; multiplier stays within a known finite range).
  A bounded multiplier means a raw-profit-ranked cutoff can be widened by a
  known factor and still provably retain the penalty-adjusted winner.
```

The *exact* cutoff mechanism — a single generous-cutoff pass, a two-pass
evaluate-then-refine, per-commodity top-N union, or another shape — depends on
what the measurement probe shows is fast on real data. It is fixed at the
post-probe checkpoint, not in this plan. What this plan fixes is the
requirement: the candidate query narrows and ranks in SQL and returns a
bounded, provably-sufficient top set. It never materialises the galaxy.

## Behavioural Requirements

### Dispatch

`plan_onehop_route` becomes an explicit four-way dispatch. Validation no longer
guarantees at least one endpoint, so the current bare-`return` fallthrough must
become a guarded branch:

```text
--from and --to present   -> _plan_fixed_endpoints                  (Slice 1-2)
--from present only        -> _best_open_ended_plan(open_role="destination")  (Slice 3)
--to   present only        -> _best_open_ended_plan(open_role="source")       (Slice 4)
neither present            -> _plan_unanchored                       (NEW)
```

The first three branches keep their exact conditions and behaviour. The third
changes only from a bare `return` to an `if request.to_text:` guard; the new
fourth branch is the final `return`. The block comment above the dispatch
(which currently states both-omitted is rejected by validation) is updated to
describe the four-way shape.

### The unanchored planner path

`_plan_unanchored(session, request, started, validation_ms)` is the new planner
function. It is **not** parameterised by `open_role` and shares no body with
`_best_open_ended_plan`. It:

```text
1. runs the unanchored candidate query (below), which returns a bounded,
   provably-sufficient top set of trade candidates
2. materialises the ResolvedStation DTOs for the stations appearing in that
   set (both sides), via fetch_stations_by_id
3. groups candidates into station pairs with _group_pairs (self-pairs dropped)
4. evaluates each pair with the existing optimise_cargo and
   score_with_destination_penalty, retaining the best via _pair_is_better
5. builds one JumpPath for the winning pair via plan_jump_path
6. assembles the RunResult via _assemble_result
```

Steps 2-6 reuse the existing pure helpers unchanged. Step 1 is the new query.
The exact division of step 1 between SQL and Python — in particular whether the
bounded cutoff needs a first evaluation pass to establish the bound — is fixed
at the post-probe checkpoint.

### The unanchored candidate query

`fetch_unanchored_trade_candidates(session, request, ...)` is the new
`data_gateway` query function. `fetch_open_ended_trade_candidates` is **not**
modified or called.

What the query must achieve, fixed now:

```text
- Find profitable trades between a source station and a destination station
  where the destination system is reachable from the source system in a single
  loaded jump (--jumps-per 1) or is the same system (--jumps-per 0). A loaded
  jump is symmetric in distance, so reachability is "destination system within
  --ly-per of source system".

- Apply the same per-trade filters the open-ended search applies, SQL-side:
  positive source supply price and units, positive destination demand price,
  _MIN_MEANINGFUL_DEMAND on the destination, gain-per-ton range, --supply /
  --demand thresholds, --age cutoff, affordability of at least one unit, and
  the station-attribute filters (pad size, planetary, no-planet, black-market,
  fleet-carrier, settlement, --ls-max).

- Narrow and rank in SQL. Return a bounded top set, not the galaxy. Never
  materialise a column of ids into Python to hand back as a literal IN(...).
  Never run the galaxy-wide market self-join.

- Each returned TradeCandidate carries source_station_id and
  destination_station_id, as in the anchored path.
```

What is **not** fixed now — settled at the post-probe checkpoint:

```text
- the query's internal shape (per-commodity decomposition, staged
  system-pair-then-market, single statement, or another form)
- whether the bounded cutoff is one pass or two
- the exact cutoff constant / top-set size
```

See The Measurement Probe.

### Reachability

The candidate query's spatial predicate is itself the reachability filter, as
in Slices 3-4. `plan_jump_path` is called exactly once — for the winning pair —
to build the `JumpPath` for output. Same-system pairs are reported as
supercruise.

`--jumps-per 0` restricts the search to same-system pairs (source and
destination in one system). `--jumps-per 1` allows a single loaded jump.
`--jumps-per >= 2` with any endpoint omitted is rejected in validation, so
`_plan_unanchored` only ever sees 0 or 1.

### Cargo and scoring

Unchanged and reused. `optimise_cargo` and all its constraints (capacity,
credits minus insurance reserve, per-item limit, source supply, destination
demand as a hard cap, gain filters, exact arithmetic) apply per pair.
`score_with_destination_penalty` applies the protected `--ls-penalty` curve
using the destination station's `ls_from_star`. The unanchored path supports
`--ls-penalty` for free through this reuse.

### Confirmation prompt

The confirmation gate lives in `run_cmd.py` — the permitted command entry
surface. The planner stays non-interactive: it never prompts and never
inspects the TTY.

```text
- run_cmd.py detects the both-omitted shape (neither --from nor --to supplied)
  from the parsed request, before invoking the planner.

- Interactive (stdin is a TTY): print a warning that an unanchored search is
  galaxy-wide and slow, and ask the user to confirm. On a non-affirmative
  answer (including a bare Enter — the default is "no"), exit cleanly without
  invoking the planner. On confirmation, proceed.

- Non-interactive (stdin is not a TTY): do not prompt. Exit cleanly with a
  message explaining the unanchored search needs interactive confirmation and
  how to proceed (anchor it with --from / --to, or re-run interactively).

- A declined prompt and a non-TTY abort are both clean exits at the command
  surface — a clear message, no traceback, the planner never invoked. They do
  not need a planner failure class; they are handled in run_cmd.py.
```

Draft wording (adjustable; the warning's specifics are finalised once the
probe gives a real runtime figure):

```text
interactive:
  "Searching with neither --from nor --to scans the whole galaxy for the
   single best trade. This is much slower than an anchored search. Continue? [y/N]"

non-TTY:
  "trade run with neither --from nor --to runs a slow galaxy-wide search and
   needs interactive confirmation. Re-run in an interactive terminal, or
   anchor the search with --from and/or --to."
```

The prompt fires whenever both endpoints are omitted — it is not refined by
`--jumps-per`. `--jumps-per 0` (same-system unanchored) is the cheaper
sub-case, but folding it into one unconditional rule keeps the behaviour
predictable; refining the prompt by jump count is explicitly not done here.

The prompt fires on the both-omitted *shape*, which is known as soon as the
request is parsed. Deep numeric validation (`--capacity`, `--credits`, etc.)
remains inside the planner and runs after a confirmed prompt. The minor
consequence — a malformed both-omitted command is warned before it is rejected
— is accepted; reordering validation to avoid it is not worth the scope.

The exact integration into `run_cmd.py`'s existing control flow, and a check
for any existing both-omitted handling already in `run_cmd.py`, are done when
the file is read at implementation step 6.

### Output

No renderer change is expected. The selected route carries concrete source and
destination `ResolvedStation` objects, and Slices 2-4 already render
planner-selected stations on both sides. Verify only that output reads sensibly
when the user named neither endpoint.

## Failure Requirements

Reuse the existing failure taxonomy — no new failure classes:

```text
- both endpoints omitted with --jumps-per >= 2   -> UnsupportedRunShape (validation)
- no profitable trade anywhere in reachable range -> NoProfitableTrades
- profitable trades but no affordable cargo        -> NoAffordableCargo
```

`NoReachableRoute` is effectively unreachable for an unanchored search — with
both endpoints free there is always some reachable pair — but the taxonomy
keeps it; it simply will not fire.

`_raise_empty_open_search` is anchored-specific (its messages name "the origin"
/ "the destination") and is **not** reused. An unanchored search that finds no
profitable trade raises `NoProfitableTrades` directly with an unanchored
message, for example "No profitable trades were found anywhere in reachable
range." There is no anchored side to name and no need for the
`any_reachable_station_pair` probe.

All expected failures map cleanly through the existing `run_cmd.py` exception
handling and must not emit tracebacks.

## Suggested Internal Shape

Concrete, minimal-scope change set. Items marked (probe) are shaped by the
measurement probe and finalised at the checkpoint.

```text
commands/run_cmd.py
  - add the confirmation gate: detect the both-omitted shape; if interactive,
    prompt and exit cleanly on a non-affirmative answer; if not a TTY, exit
    cleanly with the guidance message. Exact placement confirmed when the file
    is read (step 6).

planner/run_request.py
  - no change. from_text / to_text are already optional str | None.

planner/validation.py
  - remove the both-omitted UnsupportedRunShape rejection (the
    "Either --from or --to must be supplied." block).
  - the omitted-endpoint --jumps-per guard is unchanged: its condition
    "not from_text or not to_text" already covers both-omitted, so a
    both-omitted request with --jumps-per >= 2 is still rejected. This is
    wanted — multi-jump stays out of scope for every omitted-endpoint shape.
  - no other validation references from_text / to_text; removal is clean.

planner/data_gateway.py
  - add fetch_unanchored_trade_candidates: the new galaxy-wide candidate query
    returning a bounded, provably-sufficient top set. (probe)
  - fetch_open_ended_trade_candidates and the other anchored query functions
    are not modified.

planner/run_onehop.py
  - add _plan_unanchored: the new unanchored planner function, reusing the
    pair-evaluation helpers. (probe — the SQL/Python split of its candidate
    step)
  - plan_onehop_route: four-way dispatch; the bare-return fallthrough becomes
    an "if request.to_text:" guard; new final branch calls _plan_unanchored;
    update the dispatch block comment.
  - _best_open_ended_plan, _plan_fixed_endpoints, _best_pair_plan,
    _raise_empty_open_search: unchanged.

unchanged: cargo.py, score.py, reachability.py, resolver.py,
           render_text.py, run_result.py, failures.py
```

## Design Note — A Separate Path, Not a Generalisation

Slice 4 generalised Slice 3's anchored search because the second caller
differed from the first only in which endpoint was fixed — one parameter,
`open_role`, lifted that difference. Slice 5 is deliberately **not** another
step along that line.

The unanchored search differs from the anchored open-ended search not in a
parameter but in kind. The anchored search's whole shape — a bounded fixed
station set, a spatial box around a known anchor, both market queries on the
`StationItem` primary key, the full candidate set safely materialised — exists
*because* there is an anchor. Remove the anchor and every one of those
properties is gone: the search is galaxy-wide, and its defining new problem
(bounded materialisation of a provably-sufficient top set) does not arise in
the anchored case at all.

Forcing that into `_best_open_ended_plan` would not be generalisation; it would
be two unrelated algorithms wearing one function, and it would run anchored
requests through a query builder reshaped for the unanchored case — the precise
risk Decision 2 forbids. The Slice 4 plan already mandated this: the unanchored
search "must be built as a separate additive path, never as a generalisation
of an anchored query." This plan honours that.

## Data Access Guidance

```text
- The unanchored candidate query must narrow in SQL and return a bounded top
  set. Materialising every profitable galaxy-wide trade into Python is the
  legacy preload failure and is not acceptable.

- Spatial reachability (the System-to-System distance constraint) is computed
  in SQL against the indexed System.pos_x/pos_y/pos_z columns, using squared
  distance (<= L*L). No sqrt. No Python-side distance filtering.

- Do not materialise a column of station ids into a Python list and pass it
  back as a literal IN(...). Chain queries with subqueries or joins so the
  candidate set never leaves SQL (the Slice 4 lesson).

- Do not run the galaxy-wide market self-join — StationItem joined to itself
  on item_id across the whole table. That is the --pad-size S pathology Slice 3
  diagnosed. Both StationItem accesses must stay on a tractable access path.

- candidate_trade_count and the existing PlannerDiagnostics timing fields are
  reused. No new diagnostics fields are added.

- The probe (below) measures candidate query shapes against the live database
  and settles which shape meets the guidance above at acceptable cost.
```

## The Measurement Probe

The unanchored candidate query is the slice's one real unknown. It is settled
by measurement on real data before any production query is written. This is
implementation step 1, and step 2 onward does not start until the probe's
results have been reviewed with the supervisor.

```text
What the probe does
  - Claude prepares a standalone, read-only measurement script. It uses the
    ORM models and SQLAlchemy session — the same access data_gateway.py uses —
    and runs only SELECT queries. It is throwaway: not part of the planner
    package, not committed with the slice.
  - It exercises candidate query shapes for the unanchored search — at least
    the per-commodity decomposition and the staged system-pair-then-market
    shape, with the single-statement self-join measured as the baseline to
    beat — for both --jumps-per 0 and --jumps-per 1.
  - It measures wall-clock time, and where practical the rows examined and the
    SQLite query plan (EXPLAIN QUERY PLAN), at a representative --ly-per (20,
    matching the benchmark corpus) and at one smaller and one larger value to
    see how the reachable-pair count scales.
  - It probes the bounded-cutoff approach: how large the provably-sufficient
    top set is in practice, and whether establishing the bound needs one pass
    or two.

How it runs
  - Per the project workflow, Claude prepares the probe; Tromador runs it
    against the live database and reports the timings and query plans. The
    live dataset only exists on Tromador's machine, so this is also the only
    place the measurement is meaningful.

The checkpoint
  - The probe's results are reviewed with Tromador. Together they settle:
    the candidate query shape; the bounded-cutoff mechanism and size; whether
    exhaustive-correct is achievable at acceptable cost, or whether a
    documented bounded search is needed instead (Decision 1's fallback — and
    a supervisor decision, not one taken silently in code).
  - Implementation step 2 onward begins only after this checkpoint.
```

## Manual Validation

No automated test harness — per supervisor direction, the new path is
spot-checked against `--old` while results remain comparable. `--old` supports
the unanchored search, so it is a usable baseline. The unanchored galaxy search
may legitimately find a *different* best trade than `--old`; compare route
validity and practical value, not route identity (per the spec).

New unanchored shapes — run each on the new path and with `--old`:

```text
trade run --capacity 64 --credits 1000000 --hops 1 --ly-per 20
trade run --capacity 64 --credits 1000000 --hops 1 --jumps-per 0 --ly-per 20
```

(The new path will prompt; answer "y" to let the search run for the
comparison.)

Confirmation prompt checks:

```text
- both omitted, interactive, answer "y"  -> search runs
- both omitted, interactive, answer "n"  -> clean exit, no planner run, no traceback
- both omitted, interactive, bare Enter   -> treated as "no", clean exit
- both omitted, stdin not a TTY           -> clean abort with guidance, no traceback
                                             (e.g. redirect stdin from /dev/null)
```

New failure check:

```text
- both omitted with --jumps-per 2   -> UnsupportedRunShape, no traceback
```

Anchored regression — Slices 1-4 must be unchanged. This is the Decision 2
evidence:

```text
- the run-short Colonia benchmark, timed; result and timing must match the
  Slice 3-4 figures (route unchanged, ~3s)
- the Slice 3 open-destination and Slice 4 open-origin validation commands
- representative both-endpoint shapes (station/system combinations)
- unsupported-shape and unknown-endpoint failures, no traceback
```

Capture the run-short timing immediately before and after the slice's code
changes; an unchanged figure is the evidence the anchored path was not
degraded.

Record rough manual timings for the unanchored search itself — this feeds the
final wording of the confirmation prompt.

## Performance Expectations

```text
- Anchored shapes (Slices 1-4) remain at their current speed. This is a hard
  requirement, not an expectation — see Design Constraint — Anchored Path
  Untouched, and the run-short before/after timing.

- The unanchored search is the slow shape by nature. It is bounded by the
  galaxy, not by an anchor, and the confirmation prompt exists precisely
  because it is slow. The probe establishes the real figure; the goal is the
  fastest tractable exhaustive-correct shape, with the prompt covering the
  residual wait the user has consented to.

- --jumps-per 0 (same-system unanchored) is expected to be the cheaper
  sub-case — reachability is a System-id equality, not a spatial join — but it
  is still galaxy-wide and still measured.
```

## Deferred Work — Roadmap Note

**Multi-jump per-hop reachability.** `--jumps-per >= 2`. Deferred since
Slice 1; `plan_jump_path` raises `ReachabilityImplementationMissing` for it,
and the omitted-endpoint validation guard rejects it. After this slice the
unanchored shape carries the same restriction as the other omitted-endpoint
shapes — consistent, and lifted for all of them together when multi-jump
reachability is built.

**`--jumps-per` default keyed to `--ly-per`.** Still deferred, still blocked on
multi-jump reachability. The agreed rule sets `--jumps-per 2` for
`--ly-per <= 12.5`, which is meaningless until the planner can fly a 2-jump
hop. It belongs with the multi-jump slice. The flat default of 1 stands.

**`--progress`.** Long-running search feedback. The unanchored search is the
first shape slow enough to want it. Deferred from this slice (see Still Out of
Scope); a candidate for a small additive slice once the unanchored runtime is
known.

**Multi-hop search and the one-hop convergence.** `--hops > 1`, the route
frontier, pruning, `--start-jumps` / `--end-jumps`, and the route-shaping
options. The largest remaining body of work — and the slice that decides
whether the planner stays one application or fragments into several.

A multi-hop route is a frontier search in every case: partial routes extended
hop by hop, scored, pruned — the black-box spec's "Route generation" model. In
a frontier search the endpoint shape is not an algorithm, it is two inputs.
`--from` decides what seeds the frontier — a fixed station seeds one, an open
system seeds a few, an unanchored search seeds the galaxy-wide candidate set.
`--to` decides what terminates it — a fixed station, or anywhere. The fixed /
open-ended / unanchored distinction that splits the one-hop dispatch three ways
collapses, at multi-hop, into seed-set and termination parameters of a single
search. Every one-hop path today — `_plan_fixed_endpoints`,
`_best_open_ended_plan`, `_plan_unanchored` — is a depth-1 case of it. The
three-way one-hop split exists only because a single hop is degenerate: one hop
with both endpoints fixed has nothing to search, which is the sole reason
`_plan_fixed_endpoints` is a station-pair matrix and not a search.

The discipline for the multi-hop slice, stated outright so it is not optional:
the frontier search must **subsume** the one-hop paths, not sit beside them as
a fourth sibling. It handles `--hops 1` as well as `--hops N`; the one-hop
functions become thin depth-1 callers of it, or are retired. A
one-hop-both-fixed matrix may survive as a fast-path shortcut, but only as an
optimisation behind the frontier search, never as a load-bearing parallel
planner. Bolting multi-hop on as an independent path is the one way this
rewrite becomes two applications maintained in parallel — the multi-hop slice
must be planned as the convergence, not as an addition.

Slice 5's galaxy-scale candidate generation with bounded materialisation is the
foundation for this, not parallel to it: a multi-hop route with an open or
unanchored origin seeds its frontier from exactly that galaxy-scale candidate
set, so the bounded-materialisation technique proven here is what multi-hop's
frontier expansion reuses.

**GUI integration of the unanchored shape.** Owned outside the planner rewrite
(Decision 5). Not a loose end of this slice.

## Completion Criteria

```text
- both --from and --to omitted produces a valid one-hop route
- the unanchored search runs behind the confirmation prompt: it warns and asks
  before planning; a non-affirmative answer exits cleanly with no planner run
- a non-TTY invocation of the unanchored shape aborts cleanly with guidance
- the measurement probe has been run and its results reviewed at the
  checkpoint; the candidate query shape was settled there, not guessed
- the candidate query narrows and ranks in SQL and returns a bounded,
  provably-sufficient top set; the galaxy is never materialised into Python
- the best valid one-hop pair is selected; self-pairs are excluded
- the cargo plan obeys all first-slice cargo constraints
- the unanchored search is a separate planner path and a separate query
  function; the anchored planner and query functions are unmodified
- anchored shapes (Slices 1-4) are unchanged in result and speed — evidenced
  by the run-short before/after timing and the Slice 3-4 validation commands
- both omitted with --jumps-per >= 2 fails explicitly with no traceback
- output reports the actual planner-selected stations and cargo
- --old comparison has been run and recorded on the unanchored validation
  commands
```

## Recommended Implementation Order

```text
1. Measurement probe. Claude prepares the read-only probe script; Tromador
   runs it; results reviewed with Tromador at the checkpoint. The candidate
   query shape and the bounded-cutoff mechanism are settled here.

   --- CHECKPOINT: do not proceed to step 2 until the probe is reviewed ---

2. Relax validation.py: remove the both-omitted rejection. Confirm the
   omitted-endpoint --jumps-per guard still covers both-omitted.
3. Widen the plan_onehop_route dispatch to four ways; the bare-return
   fallthrough becomes a guarded branch; update the dispatch comment.
4. Add fetch_unanchored_trade_candidates to data_gateway.py, in the shape
   settled at the checkpoint.
5. Add _plan_unanchored to run_onehop.py, reusing the pair-evaluation helpers.
6. Add the confirmation gate to run_cmd.py (interactive prompt + non-TTY
   abort); read run_cmd.py here to confirm the integration point and check for
   any existing both-omitted handling.
7. Manual validation: the unanchored shapes vs --old; the prompt and non-TTY
   checks; the new failure check; the anchored regression with run-short timed
   before and after. Record unanchored timings for the final prompt wording.
```

Steps 2-6 are executed one logical step at a time, each verified before the
next, per project execution discipline.

## Non-Goals

Do not build multi-hop frontier, pruning, multi-jump reachability, the keyed
`--jumps-per` default, route shaping (`--via` / `--avoid` / `--towards` /
`--loop` / `--unique` / `--loop-interval` / `--shorten`), `--start-jumps` /
`--end-jumps`, multiple displayed routes, `--progress`, or any GUI-facing hook.

Do not fold the unanchored search into `_best_open_ended_plan` or
`fetch_open_ended_trade_candidates`. Do not introduce shared persistent state
(a precomputed edge table, a cache) — the unanchored search is a query path.

This slice proves one thing cleanly:

```text
The one-hop planner can plan a route with neither endpoint named — an
exhaustive galaxy-wide search that narrows in the database, returns a bounded
provably-sufficient candidate set, and never degrades the anchored shapes it
sits beside.
```
