# Slice 21 — `--avoid` (Commodity / System / Station Exclusion)

## What and why

`--avoid` lets a commander exclude a commodity, a system, or a station from a
route. It already parsed onto `RunRequest.avoid` and was gated as unsupported;
this slice resolves the tokens and applies the exclusions across every route
shape, then un-gates the option.

## Resolution — once, at dispatch

Each `--avoid` token resolves a single time at dispatch (alongside the endpoints
and `--towards`), through the shared `TradeORM` lookup, into three id sets carried
on `RunRequest`: `avoid_system_ids`, `avoid_station_ids`, `avoid_item_ids`. The
planner consumes the ids; it never sees the token strings or the database handle.

Tokens arrive repeated and/or comma-separated, and are fuzzy-matched exactly like
`--from` / `--to` (the same `lookup_place` / `lookup_item` machinery). Syntax
picks the namespace: a token with a slash is a place (station or system, never a
commodity); a bare token may be a system or a commodity. A bare token resolves
**precision-first** — exact system, exact commodity, fuzzy system, fuzzy
commodity — so an exact commodity beats a merely fuzzy system, and a place wins a
same-tier tie. An unresolvable token fails clearly; an ambiguous name propagates
the lookup's own `@N` / candidate message.

## The exclusions

- **Station / system** — applied at the shared `_station_attribute_predicates`,
  the one seam every attribute-filtered candidate fetch flows through. An avoided
  station is never an eligible route station; an avoided system bars every station
  within it.
- **Commodity (buy side)** — applied at each buy-side filter: the fixed station
  pair, the open-ended supply side and its onward-viability check (the forward
  onward leg is a future buy), and the unanchored candidate item set, plus the
  zero-result diagnostic. Trades are buy→sell pairs matched on the commodity, so
  removing the buy side drops the whole pair — an avoided commodity never enters
  cargo and is never sold.
- **Jump-path transit** — avoided systems are dropped from the local jump-graph
  bubble at build time, so no breadth-first path can route through one. The permit
  case: a permit-locked system cannot be entered even in transit. The set is
  threaded as a **required** argument through the three reachability entry points
  (`plan_jump_path`, `reachable_systems_from`, `is_system_pair_reachable`) to the
  bubble build and passed at every call site, including the empty-jump positioning
  legs (the unladen repositioning flight is a jump path too).

## The explicit-origin carve-out

A `--from` the commander also avoids is still a valid place to start — but the
route never returns. The fixed `--from` **station** case already worked (named
stations are used directly, bypassing the attribute filter). For a `--from`
**system** that is itself avoided, two changes: the jump bubble always keeps its
own anchor (so you can leave the system you started in, while every other bubble
still bars it), and the origin station fetch drops just the from-system from the
system-avoid for the `source` role. Destinations get no carve-out — avoiding a
forced `--to` is a contradiction, left to fail.

## Verification (live data, handed to Tromador)

- A system on a route avoided → dropped as an endpoint; a transit system avoided
  → the path reroutes around it (`Barnard's Star -> LTT 5455 -> LP 911-13` became
  `Barnard's Star -> 61 Virginis -> LP 911-13`, same endpoints and same profit —
  only the stepping stone changed).
- A commodity avoided → never bought or sold; the route falls to the next-best
  (avoid Tritium dropped the route from ~24M to ~15M; avoid Tritium,Cobalt sent
  it back to Silver).
- The invariant held throughout: avoiding more only ever lowered the score, never
  raised it.
- `--from Sol --avoid Sol` starts in Sol and never returns; the station form
  keeps other Sol stations usable; `--to X --avoid X` fails cleanly.

flake8 clean on every touched file. A grep-audit confirmed all eleven
reachability call sites pass the required avoid argument (so a missed site would
have been a loud failure, not a silent permit hole).

## Commits

- resolve `--avoid` tokens to system / station / commodity ids
- exclude avoided stations and systems from candidate selection
- exclude avoided commodities from the buy side
- exclude avoided systems from jump paths
- keep the `--from` origin usable when its system is avoided

## Deferred (unchanged)

`--via` stays gated; its "via conflicts with avoid" cross-check returns with
`--via`. There is no syntax to force the commodity reading of a bare token — a
place wins an exact-tier collision, by decision. `--unique` (avoid
already-visited stations) is a separate, dynamic concern for its own slice.
