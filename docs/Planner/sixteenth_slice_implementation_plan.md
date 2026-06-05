# Slice 16 — Empty-jump endpoint positioning (`--start-jumps` / `--end-jumps`)

## Status

Planned, not yet implemented. This document is the agreed design; code proceeds
one step at a time with review between steps, per the project workflow.

## What Slice 16 is

The two **empty-positioning** options. They let a commander declare a physical
start (or end) location and a willingness to travel *empty* a few jumps from it
before the trading begins (or after it ends), so the planner can pick the best
trade station in that neighbourhood rather than being pinned to the named one.

One slice, both ends — `--end-jumps` is the exact mirror of `--start-jumps`, so
they share a mechanism and land together. The work also makes `--empty-ly` live;
it parses today but never reaches the planner, and these two options are the only
things that consume it.

## Semantics — the contract

`--start-jumps N` means **empty positioning jumps before the first trade hop.**

- If `--from` names a station, that station is the commander's starting physical
  location / anchor — **not** the forced first trade origin.
- The planner expands eligible trade origins from the **parent system** of the
  anchor, using up to `N` empty jumps. The first cargo pickup may be any eligible
  station reachable within that expansion, **including the named station only if
  it independently qualifies.**
- Worked example: `--from "Sol/Galileo" --start-jumps 2` = "I am at Galileo. I
  will travel empty up to 2 jumps from Sol before buying. Find the best route
  starting from any eligible station reachable that way." It does **not** mean
  "force Galileo as the first buy, then ignore `--start-jumps`."

`--end-jumps N` is the mirror: the `--to` station is the final positioning
anchor, not necessarily the final cargo-sale station. Eligible final
destinations expand from the anchor's parent system within `N` empty jumps.

Two further facts that bind the build:

- **Empty jumps use the unladen range.** The fan-out jump distance is
  `--empty-ly` if supplied, else `--ly-per` (spec lines 293 / 307). It is the
  unladen range because positioning carries no cargo — an empty ship jumps
  further than a laden one.
- **This is a different jump count from `--jumps-per`.** `--start-jumps` /
  `--end-jumps` size the *positioning net* around an anchor; `--jumps-per` is
  per-trade-hop laden reachability. They must not be conflated.
- **`--empty-ly` is meaningful only alongside start/end-jumps.** It is accepted
  on the command line and parses without error, but it is consumed in exactly one
  place — the positioning fan-out. Supplied on its own, with neither
  `--start-jumps` nor `--end-jumps` set, it has no positioning to size, so it is
  quietly ignored: a deliberate no-op, not an error. That is the correct end
  state after this slice, not a loose end.

## Where it plugs in

One seam serves every anchored shape. `_stations_from_endpoint`
(`route_common.py:258`) turns a resolved `--from` / `--to` into its candidate
station set, and it is already keyed by `role` ("source" / "destination"). Every
anchored shape routes through it — fixed pair (`route_anchored`), fixed-terminal
and one-hop (`route_onehop`), and the anchored side of a single-anchor open
search (`route_single_anchor`). The role each shape passes already lines up with
which option applies: source → `--start-jumps`, destination → `--end-jumps`. No
per-shape changes; the one helper carries it.

Open ends (omitted `--from` / `--to`) never reach this helper, which is correct:
`--start-jumps` requires `--from`, `--end-jumps` requires `--to`, so an open end
has no anchor to position from.

## Mechanism — reuse, not new invention

The fan-out machinery already exists, because the open-ended shapes need the same
"stations within N jumps of an anchor" capability:

- **`reachable_systems_from`** (`reachability.py:312`) — returns every system
  within N jumps of an anchor, computed in memory from the Slice 6 cKDTree
  bubble. It takes the jump count and the ly-per-jump as parameters, so the
  positioning fan-out is the same call with `(start_jumps|end_jumps,
  empty_ly|ly_per)` in place of `(jumps_per, ly_per)`.
- **`_reachable_station_query` + `_bulk_insert_reachable_systems`**
  (`data_gateway.py:225` / `:422`) — take a precomputed system set, bulk-insert
  it into the `td_reachable_systems` temp table, and fetch eligible stations
  joined against it as a subquery. This is the query-discipline-clean path
  already in use; no large `IN (...)`, no id-column round-trip.
- The parent-system lookup (station → its system; system → itself) is the shape
  `_anchor_system_from_endpoint` (`route_onehop.py:564`) already implements;
  reuse or lift it so both anchor forms collapse to one expansion path.

So a station anchor and a system anchor run the *same* expansion: derive the
parent system, fan out, fetch eligible stations. The station case carries no
extra logic beyond getting its system.

## Architecture — one shared meaning, no per-engine option logic

Checked against the planner's shared-semantics / specialised-engines rule
(BASELINE). This slice complies by construction:

- The meaning of `--start-jumps` / `--end-jumps` / `--empty-ly` is resolved once
  into canonical request state (`start_jumps`, `end_jumps`, `empty_ly_per` on the
  `RunRequest`) and applied in exactly **one** shared place — the
  `_stations_from_endpoint` seam in `route_common.py`, plus the shared
  `reachability` and `data_gateway` helpers it calls.
- The route engines (`route_onehop`, `route_anchored`, `route_single_anchor`) do
  **not** each grow their own start/end-jumps handling. They call the one seam
  and consume its result; they differ only in how they then search.
- No parallel `route_*._start_jumps()` helpers are created. The
  `--empty-ly`-or-`--ly-per` fallback is resolved at the single shared point, not
  re-decided per engine.

Do not unify the engines; do unify the contract — this slice unifies the
contract at the seam and leaves each engine's search strategy untouched.

## Steps

One logical step at a time, review between each.

1. **Wire `--empty-ly` onto the request.** Add an `empty_ly_per` field to
   `RunRequest`, map `emptyLyPer` in `from_cmdenv`. The fan-out resolves the
   effective range as `empty_ly_per or ly_per` at the point of use.
2. **Open both gates.** Drop `--start-jumps` / `--end-jumps` from the
   "unsupported non-zero" lists in the parser (`run_cmd.py:407`) and in
   `validation.py:59`. The pairing checks (`--start-jumps` requires `--from`,
   `--end-jumps` requires `--to`) already exist at `run_cmd.py:354-360` and stay.
3. **Expansion in `_stations_from_endpoint`.** When the role's positioning count
   is > 0: derive the anchor's parent system, compute the reachable systems via
   the empty-jump bubble, and fetch eligible stations across that set with the
   existing temp-table query. **Skip the anchor-station validate-and-raise** in
   this branch — the anchor is a positioning point and need not pass trade
   eligibility; it appears in the result only if the expansion fetch admits it.
   When the count is 0 (default), behaviour is exactly as today.
4. **Failure path.** When the expansion yields no eligible station, raise the
   role-appropriate ineligibility failure with a message naming the empty-jump
   reach (origin side / destination side).

## To confirm during implementation

- **Bubble-cache hygiene.** The positioning bubble has radius
  `count * empty_ly`, different from the per-hop bubble (`jumps_per * ly_per`)
  for the same anchor system. The shared `bubble_cache` is keyed by system_id
  alone, so the positioning expansion must use a **separate** cache dict and not
  pollute the per-hop one with a wrong-radius bubble.
- Whether `_anchor_system_from_endpoint` moves to `route_common` for shared use,
  or its few lines are inlined at the seam.
- Performance when a fixed pair carries **both** `--start-jumps` and
  `--end-jumps`: the candidate set becomes (origin neighbourhood) × (destination
  neighbourhood). This is the same combinatorial shape as system-endpoint
  expansion, which already works; bounded by the station filters and the bubble
  radius. Watch it on a spot-check, don't pre-optimise.

## Acceptance — spot-checks, handed to Tromador

```text
--from STATION --start-jumps N    -> origins open to the neighbourhood; the route
                                     may start at a station other than the anchor
--from SYSTEM  --start-jumps N    -> expands beyond the single anchor system
--to   STATION --end-jumps N      -> mirror on the destination side
--empty-ly E                      -> changes the fan-out radius; absent -> uses --ly-per
--start-jumps without --from      -> clean CommandLineError (already enforced)
--end-jumps   without --to        -> clean CommandLineError (already enforced)
default (no start/end-jumps)      -> route identical to today on existing shapes
--jumps-per                       -> unaffected; positioning count is a separate axis
```

## Out of scope

- `--towards` — the next slice, and the reason this one goes first (it grounds
  the endpoint-reachability code that `--towards` leans on).
- `--direct`, the pruning controls, and every other gated option.
- Any reshaping of the per-hop reachability or the search engine — Slice 16
  changes only how the anchored endpoints become candidate station sets.

## Validation posture

No automated test harness (project decision). Validation is spot-check plus
flake8 on touched regions. All test commands are handed to Tromador to run; the
agent does not run them automatically.

## Documentation updates (after code is accepted)

- `docs/Planner/SPEC_STATUS.md` — `--start-jumps`, `--end-jumps`, `--empty-ly`,
  and the Origin/Destination-selection rows move to `[done]`; drop `--empty-ly`
  from the parses-but-inert trap list.
- `docs/Planner/BASELINE.md` — trim the start/end-jumps and `--empty-ly` items
  from "what's still owed".
- Slice 16 completion report.
