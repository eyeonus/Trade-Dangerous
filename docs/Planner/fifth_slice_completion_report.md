# Trade Run Fifth Slice — Completion Report

## Status

Fifth slice implementation is complete within the agreed scope. The planner
code is committed and pushed (`release/v1`, `e204ee32` and `f8efe74a`); this
report and the `SLICE_SUMMARY.md` update are the closing record.

Slice name:

```text
Unanchored Galaxy Search
```

Repository: Tromador/Trade-Dangerous
Branch: release/v1

---

## Purpose

This slice extends one-hop planning to the case where *neither* endpoint is
named. With both `--from` and `--to` omitted, the planner selects the origin
and the destination itself: it finds the single best one-hop trade anywhere
in reachable range.

Slices 3 and 4 delivered the open-ended search anchored on a fixed endpoint.
This slice removes the anchor. With no named endpoint there is nothing to
bound a spatial query, so the search is genuinely galaxy-wide and uses a
separate algorithm, not a parameterisation of the anchored one.

Supported one-hop shapes are now complete:

```text
--from station   fixed origin station
--from system    expand to eligible origin stations
--from omitted   planner selects the origin
--to   station   fixed destination station
--to   system    expand to eligible destination stations
--to   omitted   planner selects the destination
both   omitted   planner selects both                  (this slice)
```

`--old` no longer holds any one-hop shape the new planner cannot serve.

---

## Scope Completed

### Dispatch

`plan_onehop_route` dispatches four ways:

- both endpoints supplied — the fixed-endpoint station-pair matrix
  (`_plan_fixed_endpoints`), unchanged;
- one endpoint omitted — the open-ended search (`_best_open_ended_plan`),
  unchanged;
- both omitted — the unanchored search (`_plan_unanchored`), new.

The first three branches keep their exact Slice 1-4 conditions and
behaviour; the bare-`return` fallthrough became an `if request.to_text:`
guard, with the new fourth branch as the final `return`.

### The unanchored planner path

`_plan_unanchored` is a separate, additive planner function. It shares no
body with `_best_open_ended_plan` — the unanchored search differs from the
anchored one in kind, not in a parameter. It runs the candidate query,
materialises the `ResolvedStation` DTOs for the stations in the returned
set, groups candidates into station pairs, evaluates each pair with the
existing `optimise_cargo` and `score_with_destination_penalty`, and
assembles the `RunResult`. The pair-evaluation helpers are reused from
Slices 1-4 unchanged.

### The unanchored candidate query

`fetch_unanchored_trade_candidates` is exhaustive in consideration, bounded
in materialisation. The galaxy is never loaded into Python.

The query shape was settled by a standalone measurement probe run against
the live database before any production query was written:

- A reachable-system map — every ordered system pair within `--ly-per`, or
  same-system only for `--jumps-per 0` — is built once per run as a
  run-scoped temporary table and indexed. Building it once and reusing it
  across the commodity walk is the property that keeps the per-commodity
  cost flat.
- Each commodity is reduced, supply and demand separately, to its cheapest
  supplier and dearest buyer per system, and matched through the
  reachability map. The reduction uses a `ROW_NUMBER` window function —
  standard SQL, with no reliance on any backend's handling of non-grouped
  columns — so the query is backend-portable.
- Commodities are walked in descending order of their galaxy-wide
  profit-per-unit bound. A pair's total profit cannot exceed
  `capacity x best-profit-per-unit`, so once a concrete trade of total
  profit T has been seen, any commodity whose `capacity x bound` is at or
  below T can win nothing and the walk stops — a single pass, since the
  order is descending. In practice only a handful of commodities are
  examined before the cutoff bites.

The anchored query functions (`fetch_open_ended_trade_candidates`,
`fetch_station_pair_candidates`, `fetch_eligible_stations_in_system`) are not
modified, so the SQL they emit is textually unchanged and anchored speed is
unaffected by construction.

### Confirmation prompt

The both-omitted search is galaxy-wide and markedly slower than any anchored
shape, so `run_cmd.py` gates it behind an interactive confirmation: it warns
the search is slow and asks before planning. A non-affirmative answer
(including a bare Enter) exits cleanly; a non-TTY invocation does not prompt
and exits cleanly with guidance. Both are clean exits at the command
surface — a clear message, no traceback, the planner never invoked. The
planner itself stays non-interactive: it never prompts and never inspects
the TTY.

Validation runs before the prompt. A both-omitted command that cannot run —
`--jumps-per >= 2`, a missing `--hops 1`, an unsupported option — is rejected
immediately with its own error and no prompt; the prompt fires only once the
request is known to be runnable. An initial cut prompted first and validated
after; warning the user and then refusing the search was caught during
validation and corrected (commit `f8efe74a`).

### In-memory temporary storage

The reachable-system map runs to millions of rows. SQLite defaults temporary
tables to a disk file, where a map that size dominates the run time.
`prefer_in_memory_temp_storage`, a new dialect helper in `db/utils.py`, moves
them to memory — on SQLite via `PRAGMA temp_store`. The helper is
connection-scoped and SQLite-specific; MySQL/MariaDB and other backends are a
documented no-op, their temporary-storage tuning left as a measurement to
make against a real server. The helper is invoked only by the unanchored
search.

---

## Verified Behaviour

### Routes

The both-omitted shape was exercised for `--jumps-per 1` and `--jumps-per 0`,
spot-checked against `trade run --old`. Both return valid one-hop routes. The
unanchored search may legitimately find a different best trade than `--old`;
the comparison is route validity and practical value, not route identity. In
the validation runs the new planner found a substantially more profitable
trade than `--old` for the same command.

### Performance

The unanchored search is the slow one-hop shape by nature. Measured on an
SSD, the `--ly-per 20` both-omitted search returns in about 83 seconds,
against about 293 seconds for `--old` on the same hardware — roughly 3.5x
faster. The runtime is dominated by the one-time reachable-system map build;
the bounded commodity walk is a small fraction of it. The confirmation
prompt exists precisely because the search is slow.

### Failure behaviour

- both `--from` and `--to` omitted with `--jumps-per >= 2` ->
  `UnsupportedRunShape`, rejected before the prompt, no traceback;
- a declined prompt and a non-TTY invocation -> clean exit, the planner
  never invoked, no traceback;
- the Slice 1-4 unsupported-shape and unknown-endpoint failures -> unchanged,
  no traceback.

### Anchored regression

The run-short Colonia benchmark and the Slice 1-4 fixed and open-ended shapes
were re-run and are unchanged. The anchored planner and query functions were
not modified; the dispatch and validation edits are additive, so anchored
requests traverse them on exactly the path they took before.

---

## Quarantine Status

Intact.

```text
tradedangerous/tradecalc.py
tradedangerous/tradedb.py
```

Neither module was opened or used as an implementation source. `trade run
--old` remains the comparison path only.

---

## Outstanding / Deferred

Deferred, not cut:

- multi-jump per-hop reachability (`--jumps-per >= 2`) — `plan_jump_path`
  raises `ReachabilityImplementationMissing` for it, and the
  omitted-endpoint validation guard rejects it;
- the `--jumps-per` default keyed to `--ly-per` — still blocked on multi-jump
  reachability;
- multi-hop routing (`--hops > 1`) — the route frontier, pruning, and route
  shaping; the larger body of work still ahead. The slice plan's roadmap
  note records the discipline for it: the multi-hop frontier search must
  subsume the one-hop paths, not sit beside them as a fourth sibling.

MySQL/MariaDB temporary-storage tuning for the unanchored search is left for
measurement against a real server (see Scope Completed — In-memory temporary
storage).

---

## Commits

On `release/v1`:

```text
e204ee32  feat(planner): add unanchored one-hop galaxy search
f8efe74a  fix(planner): validate before the unanchored confirmation prompt
```

---

## Assessment

One-hop planning now covers every endpoint shape: fixed station-to-station,
system-endpoint expansion, open-ended destination and origin selection, and
the genuinely unanchored both-endpoints-omitted search. The unanchored search
narrows and ranks in SQL, returns a bounded candidate set, and never
materialises the galaxy; it is a separate planner path and a separate query
function, and the anchored shapes it sits beside are unmodified. Multi-hop
routing is the larger body of work still ahead.
