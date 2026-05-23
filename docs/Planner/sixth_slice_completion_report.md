# Trade Run Sixth Slice — Completion Report

## Status

Sixth slice implementation is complete within the agreed scope. The planner
code is committed on `release/v1` (range `eee84aa3..940811f7`); this report
and the `SLICE_SUMMARY.md` update are the closing record.

Slice name:

```text
Multi-Jump Per-Hop Reachability
```

Repository: Tromador/Trade-Dangerous
Branch: release/v1

---

## Purpose

This slice makes `--jumps-per >= 2` work for every trade run shape — both
endpoints fixed, one endpoint omitted, and both omitted — so `--jumps-per`
becomes a real user knob rather than one validation-clipped to 0 or 1 for
two of the three shapes. With multi-jump live across every shape, the
slice also lands the deferred default rule that keys `--jumps-per` to
`--ly-per` (2 jumps when the ship's jump range is low, 1 otherwise), and
clears up the failure messages users see when a no-result run is the
honest answer.

Slices 1–5 delivered the full one-hop family at `--jumps-per` in `{0, 1}`.
Slice 6 lifts the `--jumps-per` ceiling. Multi-hop routing (`--hops > 1`)
remains the larger body of work ahead.

---

## Scope Completed

### Piece A — Fixed-endpoint pair reachability

`plan_jump_path` keeps its same-system fast path and its `--jumps-per 0`
rejection, and replaces the old single-jump-only branch with one general
walk that returns the actual jump path for any depth up to `--jumps-per`.
Probe P2 settled the shape: a pre-fetched local bubble within
`(--jumps-per × --ly-per)` of the source, in-memory adjacency built once
with `scipy.spatial.cKDTree.query_ball_tree`, and a Python BFS over that
bounded graph (A2). A direct-distance early-out covers the
"destination is one jump away" case at microsecond cost — every corner
A1 won in probing collapses to the early-out.

A per-RunRequest `_LocalBubble` cache (keyed by source system) carries
two things the walk needs more than once: the adjacency, and a
`path_cache` mapping destination system id to the resolved path tuple
(or `None`). The cache makes a 10×10 station-pair matrix at Sol cost
about 130 ms of bubble work instead of ~7.7 s of repeated bubble fetches.

`is_system_pair_reachable` exposes the single-pair reach check as the
public surface for callers that need a yes/no with the path retained for
later use. The unanchored search (Piece C) reuses this; the answer it
caches is the same one `plan_jump_path` consults when the winning pair
is later asked for its path.

`JumpPath.distance_ly` is now the polyline length (sum of leg distances),
not the straight-line source-to-destination distance. The straight-line
reading lost meaning the moment a path could bend.

### Piece B — Open-ended reachable-station query

`_reachable_station_query` keeps its N=0 branch and replaces the
single-bounding-box N=1 branch with a general layer-by-layer widening
into a per-RunRequest temporary table `td_reachable_systems`. The
composed candidate query then joins to that table by system id.

Probe P3 ruled out a recursive CTE (B1) on the strength of Sol-region
high-depth cost (~140 s at `--ly-per 50, --jumps-per 5`). P3b confirmed
the iterative widening (B2) is faster than B1 at every heavy case by
1.5–1.7×; at low depth or small frontiers the two are within
measurement noise. P3c then sized the production picture with an age
filter and showed that geographic widening (which produces hundreds of
thousands of stations in dense space) is decoupled from the freshness
filter (which keeps ~2 % of them), so age stays in the composed
candidate query rather than being folded into the temp-table build.

### Piece C — Unanchored reach map

The legacy plan called for widening the unanchored reach map to handle
multi-jump pairs; probe P4 made it clear that any pre-materialised
multi-jump map dies on the scale of the live data (C1 timed out at
every multi-jump profile, C2 timed out at engineered jump ranges). C3
won by not building the map at all: each per-commodity match streams
candidate `(supply, demand)` pairs through a direct-distance prefilter
and a per-pair reach check using Piece A's bubble cache. Production
N=1 is 2–9× faster than the previous cross-join shape because the
44 M-row map is never built; the same shape handles every N ≥ 1
without specialisation.

`fetch_unanchored_trade_candidates` was reorganised around this
streaming pattern. `_match_via_on_demand_reach` is the N ≥ 1 path;
`_match_same_system_trades` handles N=0. The old `_populate_reach_map`
and `_system_reach_predicates` are gone; `td_unanchored_supply` and
`td_unanchored_demand` remain as the per-commodity scratch staging,
indexed for the reach walk.

`UnanchoredCounters` rides alongside the candidate set with four
diagnostics: pairs examined, pairs accepted, bubble-cache source-system
count, and per-commodity cap-hit count. The first three were the probe
instrumentation lifting to production; the fourth was a small addition
to detect future truncation pressure cheaply.

### Default rule (`--jumps-per` keyed to `--ly-per`)

Argparse's default for `--jumps-per` is now `None` so the request
builder can tell "omitted" from explicit `--jumps-per 1`.
`_resolve_jumps_per_hop` in `run_request.py` applies the keyed rule:
`--ly-per <= 12.5` defaults to 2 jumps per hop, anything longer keeps
the historical default of 1. Explicit values — including 0 and 1 — pass
through untouched.

The legacy `--old` branch in `run_cmd.py` reads `cmdenv.maxJumpsPer` in
many arithmetic and comparison sites that expect an int, so it restores
the historical default of 1 at the top of its branch when the value
arrives as `None`. The keyed default is new-planner only by design;
`--old` is the comparison path and keeps its prior behaviour.

### Validation pin removal

The omitted-endpoint `--jumps-per` guard at the head of `validation.py`
is gone. The non-negative-integer check remains.

### Failure-message cleanup

The new planner has enough context to name what actually failed on a
no-result run, so its known failure classes no longer route through
`NoDataError`'s legacy "possible causes" footer. A new
`PlannerResultError` in `commands/exceptions.py` prints
`Error: <message>` with no footer; `_planner_result_message` in
`run_cmd.py` builds one of five user-facing wordings from the failure
type and the endpoints the user named:

```text
both endpoints named, unreachable:    "No route was found from X to Y..."
both endpoints named, no profit:      "No profitable trade was found from X to Y..."
--from only, no result:               "No profitable trade was found from X..."
--to only, no result:                 "No profitable trade was found to Y..."
neither named, no result:             "No profitable trade was found..."
```

Wording follows the failure spec: "with the current jump settings"
rather than internal terms ("origin", "anchor", "selected endpoints"),
and only recommends `--jumps-per` where increasing it is plausibly the
fix. `StationHasNoUsablePriceData` and its subclasses keep their
planner-supplied messages but are surfaced as `PlannerResultError`,
so the footer is gone there too.

The implementation plan called for these messages to be updated at the
planner raise sites in `run_onehop.py`. The work landed at the command
layer instead: the failure classes the planner raises stayed structural;
the human-readable wording is built at the boundary where the request
shape is known. Same user-facing outcome, less coupling between the
planner's internal messages and what the user sees.

### Unanchored confirmation prompt

The Slice 5 prompt was sharpened. The lead paragraph was rewritten away
from "anchored / unanchored" terminology — internal vocabulary that
average users do not need to learn — toward "Searching with neither
--from nor --to". The "this may take several minutes" understatement was
replaced with "anywhere from minutes to substantially longer depending
on the data and filters in play", which is closer to the truth on the
slowest shapes. The text recommends naming an endpoint or applying
filters (`--age`, `--pad-size`, `--planetary`, `--fc N`) explicitly,
since either narrows the search substantially. Both the non-TTY abort
message and the TTY prompt are wrapped to 80-column output.

### Cleanup-on-`^C`

A `^C` deep inside SQLite can leave the session's transaction in a
broken state. The unanchored search's `finally` block previously called
`_drop_unanchored_temps` directly, which then raised
`PendingRollbackError` against the already-broken transaction, masking
the original `KeyboardInterrupt`. The drop call is now wrapped in
`try / except Exception: pass`; the temp tables are session-scoped and
the run is being torn down anyway, so a cleanup failure is the right
thing to swallow.

---

## Verified Behaviour

### Routes

Multi-jump was exercised against `--old` across all three shapes:
fixed-endpoint pair routing (Piece A), open-ended one-side-anchored
search (Piece B), and unanchored galaxy search (Piece C). Route
validity is the gate, not route identity; the new planner is free to
find a different best trade, and at the multi-jump scale it sometimes
does so substantially more profitably (e.g. LP 547-159 → Lave under
the open-ended path returned a ~32× faster result vs `--old`, because
`--old` excludes carriers that lack both supply and demand at the same
station while the new planner does not).

A polyline-arithmetic spot-check confirmed that
`JumpPath.distance_ly` reads as the sum of leg distances — Sol → Lave
at `--ly-per 30` came back as 144.47 LY of polyline against a 114.54 LY
straight line, ratio ~1.26×.

### Default rule

Sol-anchored runs with `--ly-per 12` (no `--jumps-per`) found a 2-jump
route; `--ly-per 30` found a 1-jump route. The boundary value `12.5`
defaulted to 2 jumps (verified at Sol; Lave is too sparse to
differentiate). Explicit `--jumps-per 0` produced a same-system result
at Sol; explicit `--jumps-per 1` produced a single-jump route at Lave.
The `--old` path was unaffected.

### Failure messages

The five message-family cases were exercised in turn:

- `--from Lave --jumps-per 0`: from-only no-profit wording, no footer.
- `--from Lave --to Sol --ly-per 12.5`: both-named-unreachable wording,
  no footer.
- `--gain-per-ton 999999999 --age 4` (no endpoints): unanchored
  no-profit wording, no footer.

The to-only case was verified by inspection — it is the symmetric
branch of the from-only case in the same builder, and the from-only
case prints the spec wording cleanly.

### Performance

The unanchored multi-jump search is the slow shape by nature. Without
filters the run is interactively prohibitive on dense space — the
existing confirmation prompt continues to gate it for exactly that
reason. With realistic filters (`--age 5`, `--pad-size L`,
`--planetary N`) the same run completed in roughly 2–3 minutes during
validation. Anchored multi-jump shapes returned within seconds. The
N=1 unanchored shape is faster after this slice than before, because
C3 removes the cross-join reach map (probe P4: 132 s → 14.6 s at
Profile E).

A separate observation surfaced during multi-jump validation: a small
number of stations report sell prices roughly two orders of magnitude
above the commodity's normal ceiling, and those rows both pollute top
results and accelerate the descending-bound cutoff artificially. This
is dirty data, not a planner defect, and is recorded in
`SLICE_SUMMARY.md` for a separate eyeonus conversation about a possible
`--max-gain-per-ton` default cap.

### Failure behaviour

- `--jumps-per` set to any non-negative integer is now accepted for
  every endpoint shape (the omitted-endpoint pin is gone).
- Planner-known failures (`NoReachableRoute`, `NoProfitableTrades`,
  `NoAffordableCargo`, `StationHasNoUsablePriceData`) surface as
  `PlannerResultError` — `Error: <specific message>`, no footer.
- A `^C` during the unanchored search now produces a clean
  `KeyboardInterrupt`; the previous `PendingRollbackError` mask is
  closed.

### Anchored regression

Slice 1–5 shapes were re-run; behaviour is unchanged at N=0 (the
same-system fast path is untouched) and equivalent at N=1 (the unified
`>= 1` implementation produces the same routes the previous single-jump
code produced).

---

## Quarantine Status

Intact.

```text
tradedangerous/tradecalc.py
tradedangerous/tradedb.py
```

Neither module was opened or used as an implementation source. `trade
run --old` remains the comparison path only.

---

## Outstanding / Deferred

Carried forward, not cut:

- **Multi-hop routing** (`--hops > 1`) — the route frontier, pruning,
  and route shaping. The next major body of work.
- **`--start-jumps` / `--end-jumps`.** Origin/destination expansion by
  jump radius. Distinct piece of work, separate slice when it surfaces.
- **`SourceHasNoSellingData` / `DestinationHasNoBuyingData` wording.**
  Surfaced footerless via `PlannerResultError`, but the raise text in
  `run_onehop.py` still uses internal phrasing ("reachable source
  station had usable selling data"). Recorded under Cleanup Candidates
  in `SLICE_SUMMARY.md`.
- **MariaDB end-to-end on multi-jump shapes** — the production code
  reuses the dialect-portable patterns from Slice 5 (temp tables with
  `BigInteger` keys, `NOT EXISTS` for set difference), and the probes
  ran on the live SQLite database. A full MariaDB run across the three
  multi-jump shapes against the Linux VM is the natural follow-on
  before this work goes upstream.
- **Runaway unit-profit prices and a possible default
  `--max-gain-per-ton` cap.** Surfaced during validation; recorded
  separately in `SLICE_SUMMARY.md` for an eyeonus conversation.

---

## Commits

On `release/v1`:

```text
cc7fb21d  docs(planner): plan multi-jump per-hop reachability
34d33290  docs(planner): record bubble cardinality measurements for multi-jump reachability
2e6e7147  docs(planner): record per-frontier vs pre-fetch reachability comparison
ef08ae9f  docs(planner): select temp-table widening for reachable-system subquery
57efbae9  docs(planner): record age-filter impact on reachable candidate generation
71e4c567  docs(planner): select on-demand reach checks for unanchored multi-jump matching
4423e363  docs(planner): soften P4 cap-hit instrumentation claim
14bca8bc  fix(deps): bump pythonnet to 3.1.0rc1 for Python 3.14
7f8b5df4  build(deps): add scipy for KDTree adjacency in the route planner
01c6c535  feat(planner): add multi-jump reachability for the run command
c9c3979f  fix(planner): report multi-jump distance as polyline length
f32b5b45  feat(planner): widen reachable-station query for multi-jump open-ended
45828728  docs(planner): Fix trivial typo.
a2e84890  feat(planner): on-demand unanchored expansion with multi-jump reach
d9a8d952  docs(planner): note runaway unit-profit prices and possible cap option
14c21353  feat(planner): key --jumps-per default to --ly-per
f3d81560  feat(planner): surface planner failures with specific messages, no footer
940811f7  docs(planner): note internal phrasing in two planner failure messages
```

The plan-and-probe range (`cc7fb21d..4423e363`) preceded any code
change; the implementation range (`14bca8bc..f3d81560`) lands the three
pieces, the keyed default, and the failure-message cleanup; the closing
`940811f7` records the deferred-wording cleanup candidate.

---

## Assessment

`--jumps-per` is a real knob across every supported one-hop shape. The
implementation is the same shape end-to-end: a pre-fetched local bubble
around an anchor, in-memory adjacency over its systems, and a bounded
BFS walk that the per-RunRequest cache memoises both for routing and
for reachability checks. The unanchored search no longer materialises a
multi-jump pair map at all — that scale risk was settled in the probe
phase before any production query was written.

The failure-message family is the user-facing closing of the slice.
The planner's failure classes still distinguish unreachable from
unprofitable, but the wording the user sees is built at the command
boundary from the request shape, without the legacy footer that was
misleading on planner-specific failures.

Multi-hop routing is the larger body of work still ahead.
