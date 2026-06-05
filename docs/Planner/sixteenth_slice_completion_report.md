# Slice 16 — Empty-jump endpoint positioning (`--start-jumps` / `--end-jumps`) — Completion Report

## Status

Complete. `--start-jumps`, `--end-jumps`, and `--empty-ly` are live and verified
against live data. The implementation followed the agreed plan
(`sixteenth_slice_implementation_plan.md`) without deviation in scope.

## What was delivered

The two empty-positioning options. A named `--from` / `--to` is now treated as a
physical anchor rather than a forced trade endpoint: the planner expands eligible
trade origins (or destinations) from the anchor's parent system, out to N empty
jumps, and picks the best trade station in that neighbourhood. `--empty-ly`,
which parsed but never reached the planner before, now supplies the unladen
fan-out range and falls back to `--ly-per` when absent.

The empty repositioning flight is also shown in the route output: an inbound
line in the header (anchor -> first trade station) for `--start-jumps`, and an
outbound line after the last hop (last trade station -> anchor) for
`--end-jumps`.

## How it was built

Four steps, reviewed one at a time.

1. **`--empty-ly` onto the request.** Added the `empty_ly_per` field to
   `RunRequest` and mapped `emptyLyPer` in `run_request_from_cmdenv`
   (`run_request.py`). It stays `None` when omitted — the meaningful "not
   supplied" state — so the fan-out can fall through to `--ly-per`.
2. **Both gates opened.** Dropped `--start-jumps` / `--end-jumps` from the
   `unsupported_non_zero` lists in the parser (`run_cmd.py`) and in
   `validation.py`. The pairing checks (`--start-jumps` requires `--from`,
   `--end-jumps` requires `--to`) were already present and stayed.
3. **Expansion at the shared seam.** `_stations_from_endpoint`
   (`route_common.py`) now checks the role's positioning count first
   (`start_jumps` for source, `end_jumps` for destination). Count 0 → behaviour
   is byte-for-byte as before. Count > 0 → `_positioning_stations` derives the
   anchor's parent system, computes the reachable systems via
   `reachable_systems_from` with `(count, empty_ly)`, and fetches eligible
   stations across the set with the new data-gateway helper. The anchor station
   is never validate-and-raised in this branch — it is a positioning point, so
   it appears in the result only if the expansion fetch independently admits it.
4. **Failure path.** When the expansion yields no eligible station,
   `_positioning_stations` raises the role-appropriate ineligibility failure with
   a message naming the side (origin / destination) and the empty-jump reach.

### New shared helper

`fetch_eligible_stations_in_reachable_systems` (`data_gateway.py`) — the
multi-system sibling of `fetch_eligible_stations_in_system`. It bulk-inserts the
precomputed reachable-system set into a `td_positioning_systems` temp table via
the existing `_bulk_insert_reachable_systems`, then selects eligible stations
with the membership test kept as a SQL subquery — never a large `IN (...)`
literal. The same `_station_attribute_predicates` filters apply as for
single-system expansion; market-quote eligibility is still checked later per
station pair. Station DTOs are built from the in-memory system set, which already
carries coordinates, so no second `System` join is paid.

`_positioning_anchor_system` (`route_common.py`) derives the anchor system
(station → parent system; system → itself; unresolved → `None`). It is the
positioning-specific sibling of `route_onehop._anchor_system_from_endpoint`,
inlined in `route_common` to respect the one-way dependency direction
(`route_common` must not import from the engines).

### Repositioning legs in the output

`PlannedRoute` gained optional `start_positioning` / `end_positioning`
(`JumpPath`) fields (`run_result.py`). `_attach_positioning_legs`
(`run_route.py`) computes them once in dispatch after the winning route exists —
`plan_jump_path` from the anchor to the route's first station (start) and from
the last station to the anchor (end), on a private bubble cache at the
positioning radius. No route engine grew its own leg logic. The renderer
(`render_text.py`) draws one line each: inbound in the route header, outbound
after the last hop, with a same-system / unreachable fallback wording.

## Architecture compliance

The slice complies with the planner's shared-semantics / specialised-engines
rule by construction. The meaning of `--start-jumps` / `--end-jumps` /
`--empty-ly` is resolved once into canonical request state and applied in exactly
one shared place — the `_stations_from_endpoint` seam, plus the shared
`reachability` and `data_gateway` helpers it calls. No route engine grew its own
positioning handling; the engines (`route_onehop`, `route_anchored`,
`route_single_anchor`) call the one seam and consume its result, differing only
in how they then search.

## The bubble-cache point (audit)

`reachable_systems_from` keys its bubble cache on `system_id` alone, so a cache
shared across differing reach parameters would be unsafe. `_positioning_stations`
mints a fresh local cache per call, used in exactly one `reachable_systems_from`
call with one `(count, empty_ly)` pair, then discarded on return. It is never
shared across roles, never shared with the per-hop path, and never reused across
parameter sets — the three unsafe cases are excluded by construction. The
longer-term fix (keying the shared cache on `(system_id, jumps, ly)`) is a
separate, deliberate change to the per-hop primitive and was not folded into this
slice; the call-site comment documents the footgun in the meantime.

## Verification

Spot-checked against live data. Both options demonstrably move the trade endpoint
off the named anchor — the headline behaviour:

- `--from "Lave/Lave Station" --start-jumps 2` and `--from "Lave"
  --start-jumps 2` produce the same route (Leesti → Placet), which is correct:
  a station anchor and a system anchor both collapse to the same Lave-system
  fan-out. The route *starts* at Leesti, not the named Lave station — the origin
  expanded.
- `--to "Lave/Lave Station" --end-jumps 2` *ends* at Placet, not at the named
  Lave station — the destination expanded. The internal search differed from the
  `--start-jumps` run (different candidate-row and pair counts), confirming the
  role was handled as a destination anchor with an open origin, not silently as
  an origin anchor. The two converge on the same Leesti↔Placet route because that
  Gold leg is a dominant local arbitrage and both endpoints sit inside Lave's
  2-jump neighbourhood.
- `--empty-ly 25` (against a `--ly-per 15` run) produced a wholly different,
  richer route from a wider neighbourhood — proof the unladen range widens the
  fan-out and the `--ly-per` fallback / explicit override are both live.
- The guardrails fired clean: `--start-jumps` without `--from`, `--end-jumps`
  without `--to`, and `--to … --start-jumps` all returned a clean
  `CommandLineError`.
- The repositioning legs render correctly: `--from "Lave/Lave Station"
  --start-jumps 2 --empty-ly 25` showed `Empty jumps to start: 2 jump(s),
  48.27 ly: Lave -> Crucis Sector ER-V b2-0 -> HR 4979` in the header, and the
  mirrored `--end-jumps` run showed `Empty jumps from end: 2 jump(s), 48.36 ly:
  Crucis Sector FM-V b2-1 -> Agatavun -> Lave` after the last hop. The
  `--end-jumps`-only run showed no spurious inbound line. The ~48 ly legs over
  two jumps confirm the unladen `--empty-ly 25` range drives the positioning
  flight, distinct from the laden `--ly-per 15` per-hop travel.

Static checks: `py_compile` and `flake8` clean on all touched files
(`run_request.py`, `validation.py`, `run_cmd.py`, `data_gateway.py`,
`route_common.py`, `run_result.py`, `run_route.py`, `render_text.py`).

## Noted, not a Slice 16 concern

The anchored multi-hop spot-checks ran 15–35 s, dominated by the per-hop search
engine (the positioning fan-out itself is the small `station-filter` slice of the
total — 124–217 ms). Search cost is existing-engine behaviour, worth a separate
look but outside this slice.

## Documentation updated

- `SPEC_STATUS.md` — `--start-jumps`, `--end-jumps`, `--empty-ly`, and the
  Origin/Destination-selection rows moved to `[done]`; `--empty-ly` removed from
  the parses-but-inert section (the three remaining entries are output-display
  options).
- `BASELINE.md` — empty-jump positioning added to "what works now"; the
  start/end-jumps and `--empty-ly` items removed from "what's still owed".
- `INDEX.md` — Slice 16 entry added.
