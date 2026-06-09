# Slice 21 — `--avoid` (Commodity / System / Station Exclusion)

Implementation plan. `--avoid` lets a commander exclude a commodity, a system, or
a station from a route. It already parses onto `RunRequest.avoid` as a string
tuple and is currently gated as unsupported; this slice resolves those tokens and
applies the exclusions, then un-gates the option.

---

## What the spec requires

From `trade_run_black_box_spec.md` (§Avoid semantics, plus the jump-path and
commodity lines):

- `--avoid` accepts **repeated and comma-separated** values.
- Each token identifies one of three things:
  - **commodity** — must never be bought (recommended for purchase).
  - **system** — must not be a route station *and* must not appear in a jump
    path (transit included).
  - **station** — must not be a route station. Does **not** block travel through
    its parent system unless that system is *also* avoided.
- The explicit `--from` start may still be used as the origin even if avoided —
  the commander chose it. Avoidance still applies to later visits and every other
  position.
- A token that resolves to none of the three types must **fail clearly**.

There is no separate "via conflicts with avoid" work here — `--via` stays gated.

---

## Design decisions (settled with Tromador)

1. **Fuzzy matching is in.** Avoid tokens resolve through the same lookups the
   endpoints use (`TradeORM.lookup_place`, `TradeORM.lookup_item`), so a partial
   name works for `--avoid` exactly as it does for `--from` / `--to`.

2. **Syntax picks the namespace.** Mirrors the endpoint contract:
   - bare `sys` → **system** (or commodity — see ordering)
   - `sys/` → **system**
   - `/station` → **station** (global)
   - `sys/station` → **station** within the named system(s)
   - A station **must** carry the slash. A bare token is never a station.
   - The **commodity** fallback applies to a **bare** token only. Any slash means
     "place", never a commodity (a commodity name never contains a slash).

3. **Resolution order for a bare token — precision first, place wins on a tie:**
   1. exact **system**
   2. exact **commodity**
   3. fuzzy **system**
   4. fuzzy **commodity**
   5. none → fail clearly (`--avoid: unknown avoid token: 'x'`)

   An exact commodity beats a *fuzzy* system, so `--avoid Gold` finds the
   commodity rather than some system with "gold" buried in its name. A place only
   wins over a commodity when both match at the *same* tier — the degenerate
   "a system is named exactly `Hydrogen`" case. That bargain is accepted: place
   wins, no warning needed for the exact-collision case (the place matched
   exactly, so there is nothing surprising to echo).

4. **Approximate-match echo.** A fuzzy (non-exact) match echoes
   `--avoid x resolved as …`, the same style as the endpoint echo. Exact matches
   are silent.

5. **Duplicate-system / `@N` edges mirror endpoints.** No new machinery. A bare
   token naming several systems raises the lookup's own `AmbiguityError`
   (the `@N` candidate list); `@N` selects one. (Avoiding *all* duplicates of a
   name is not a requirement and is not built.)

---

## Canonical state — resolve once, apply many

Per the planner architecture rule (shared meaning resolved once; engines apply
it in engine-specific ways), `--avoid` resolves a single time at dispatch into
canonical request state. The engines read that state and never re-resolve.

**New `RunRequest` fields** (`run_request.py`), filled at dispatch via
`dataclasses.replace`, exactly like `from_endpoint` / `towards_target`:

```python
avoid_system_ids: frozenset[int] = frozenset()
avoid_station_ids: frozenset[int] = frozenset()
avoid_item_ids: frozenset[int] = frozenset()
```

The raw `avoid: tuple[str, ...]` field stays as the parsed input. Defaults are
empty frozensets, so every existing call path is unchanged when `--avoid` is
absent.

---

## Step 1 — Token resolution (resolver.py)

New function `resolve_avoid_tokens(orm_db, tokens, *, option_name="--avoid")`
returning the three id sets plus the list of approximate echoes. It:

- **Flattens** the input: each `--avoid` value may itself be comma-joined, so
  split on commas and strip, dropping empty fragments. Repeated `--avoid` flags
  already arrive as separate tuple entries.
- For each token:
  - **Has a slash** (`/` or `\`) → `lookup_place(token)`. A `Station` result →
    `avoid_station_ids`; a `System` result → `avoid_system_ids`. Never a
    commodity.
  - **Bare** → the precision ladder above. Exact probes are cheap direct queries
    (`System.name == token`, `Item.name == token`); the fuzzy tier delegates to
    `lookup_system` / `lookup_item`, catching `LookupError` for a miss so the
    ladder can fall through.
- Collects the resolved ids into the three sets.
- Records approximate matches for the dispatch echo (reuse the
  `_was_approximate` idea — compare supplied token to the resolved name).
- Raises a planner `UnknownPlace` (clear message naming the token) when a token
  resolves to nothing. An `AmbiguityError` from the lookup propagates with its
  own candidate / `@N` message, as endpoints already do.

No ORM object leaves this module — only ids and echo strings.

---

## Step 2 — Wire resolution at dispatch (run_cmd.py)

In `_resolve_request_endpoints` (or a sibling helper called alongside it), after
the endpoints resolve, resolve `request.avoid` into the three id sets and fold
them onto the request with `dataclasses.replace`. Print each approximate echo,
the same way `_resolve_named_endpoint` does. Resolution happens here so the
planner consumes canonical ids and never touches the DB handle — identical to the
endpoint and `--towards` flow.

---

## Step 3 — Station / system exclusion (data_gateway.py)

Single shared seam: `_station_attribute_predicates` (~251). Every candidate fetch
runs station selection through this builder, so both shapes inherit the exclusion
in one place:

```python
if request.avoid_station_ids:
    predicates.append(Station.station_id.notin_(request.avoid_station_ids))
if request.avoid_system_ids:
    predicates.append(Station.system_id.notin_(request.avoid_system_ids))
```

- Avoided **station** → that station is never an eligible route station.
- Avoided **system** → none of its stations are eligible route stations.

This covers the "not a route station" half for both system and station avoids.
The "not in a jump path" half for systems is Step 5.

---

## Step 4 — Commodity (buy-side) exclusion (data_gateway.py)

An avoided commodity is excluded on the **buy side**. Trades are buy→sell pairs
matched on `item_id`, so excluding the buy side removes the whole pair — the
commodity never enters cargo, so it is never sold. (If the planner ever output a
sale of an avoided commodity, that is a bug, not a tolerated case.)

Apply `item_id NOT IN avoid_item_ids` at each buy-side filter:

1. **`fetch_station_pair_candidates`** (~694) — add
   `source_item.item_id.notin_(request.avoid_item_ids)` to `filters`.
2. **`fetch_open_ended_trade_candidates`** (~975) — add
   `StationItem.item_id.notin_(request.avoid_item_ids)` to `supply_filters`.
3. **The onward-viability EXISTS** (~964) — the `onward` supply branch
   (`open_role == "destination"`, the forward case) is a *future buy*, so it
   must exclude avoided items too; otherwise viability passes on a commodity the
   route would never actually buy. The `open_role == "source"` branch is an
   onward *demand* (a sell) and is left untouched.
4. **Unanchored** — drop avoided items from the candidate item set so they are
   never processed. Cleanest at the per-item loop (~1299) / `_unanchored_item_bounds`,
   with `_reduce_supply_by_system`'s supply filter (~1609) as a backstop. The
   `_match_*` helpers read the supply temp, so they inherit the exclusion with no
   separate change.
5. **Zero-result diagnostic** (~798, `_classify_zero_result_failure`) — apply the
   same exclusion so the "why no trade" classification stays consistent with what
   the real fetch saw.

This is the architecture rule's "engine-specific application of a shared meaning":
one canonical `avoid_item_ids`, the same `NOT IN` predicate, applied at each
engine's own buy-side filter — not a per-engine reimplementation of avoid.

---

## Step 5 — Jump-path exclusion (reachability.py)

The mandatory permit case: an avoided system cannot be entered at all, not even in
transit. Cut avoided systems from the jump graph itself.

**Cleanest seam: exclude at bubble build.** `_load_local_bubble` (~176) is the
only place a bubble is built, and the bubble is what every BFS walks. Add the
avoided-system exclusion to its bounding-box SELECT:

```python
if avoid_system_ids:
    stmt = stmt.where(System.system_id.notin_(avoid_system_ids))
```

With avoided systems absent from the bubble, adjacency is computed without them,
so:

- `_bfs_jump_path` can never route a path *through* an avoided system.
- `_bfs_collect_reachable` / `reachable_systems_from` never return one.
- `is_system_pair_reachable` correctly reports "unreachable" for a destination
  that needed an avoided stepping-stone.

The bubble-sizing invariant ("any path of the requested depth stays inside the
bubble") still holds — removing nodes only removes paths, it never invents one.
A hop that needed a permit-locked stepping-stone correctly becomes "no path",
which is exactly the desired behaviour.

**Plumbing:** thread `avoid_system_ids: frozenset[int] = frozenset()` through the
three public entry points (`plan_jump_path`, `reachable_systems_from`,
`is_system_pair_reachable`) into `_load_local_bubble`. The default empty set
means no behaviour change for any non-avoid call. Callers in the route engines
pass `request.avoid_system_ids`.

The per-request `bubble_cache` is keyed on anchor system id; the avoided set is
constant for the request, so a bubble built once with the exclusion is correct
for every reuse within that request.

---

## Step 6 — The explicit-`--from` carve-out

Spec: an avoided start may still be the origin because the commander explicitly
chose it; avoidance still applies everywhere else.

- **Fixed `--from` station:** automatic. The fixed-pair / single-anchor engines
  use `from_endpoint.station.station_id` directly (e.g. `fetch_station_pair_candidates`
  line 695), not through `_station_attribute_predicates`, so an avoided
  from-station is naturally exempt as the origin while still excluded as a
  destination or a later visit. **Verify** this holds for each from-anchored path.
- **`--from` system that is itself avoided** (`--from Foo --avoid Foo`):
  **decided — start there, never return.** The origin fetch exempts the
  from-endpoint's system from `avoid_system_ids` (origin selection uses
  `avoid_system_ids - {from_system_id}`), so the route starts at the chosen
  origin; the system stays fully avoided as a transit system, a destination, and
  any later visit, so the route never loops back to it.

---

## Step 7 — Un-gate validation (validation.py)

Remove `("--avoid", bool(request.avoid))` from the `unsupported` tuple (~97).
No new validation rule is needed — an unresolvable token already fails clearly at
resolution (Step 1). The "via conflicts with avoid" check stays out (via gated).

---

## Query discipline

The avoid id sets are **small** — a handful of user-typed tokens. A literal
`NOT IN (small list)` is correct and cheap here. This is **not** the anti-pattern
the project rules warn against: that rule forbids materialising a *large* id
column from a prior query and handing it back as a giant `IN (...)`. A few
user-specified ids is the opposite case.

---

## Verification (spot-checks, handed to Tromador)

On live data, with a known route as the baseline:

1. **Avoid a system on the route** → it disappears as both an endpoint and a
   transit system; a route that needed it as a stepping-stone reports no path.
2. **Avoid a commodity** → it is never bought (and so never sold); other trades
   on the same route still appear.
3. **Avoid the `--from` station** → the route still *starts* there, but the
   station is not revisited later.
4. **Avoid a station (not its system)** → the station drops out, but routes still
   pass through / trade elsewhere in its system.
5. **Comma-separated and repeated `--avoid`** → all tokens honoured.
6. **A partial avoid name** → resolves fuzzily and echoes `resolved as …`.
7. **An unresolvable token** → fails clearly.

flake8 clean on every touched file.

---

## Out of scope / deferred

- `--unique` (avoid already-visited stations) — conceptually adjacent but a
  *dynamic* per-route set that lives in multi-hop expansion, not a static
  pre-resolved exclusion. Its own slice. Nothing here blocks it.
- `--via` stays gated; the "via conflicts with avoid" cross-check returns with
  `--via`.
- No new syntax to force the commodity interpretation of a bare token — place
  wins on an exact-tier collision, by decision.

---

## Touched files

| File | Change |
|------|--------|
| `planner/run_request.py` | Three resolved-id frozenset fields. |
| `planner/resolver.py` | `resolve_avoid_tokens` + approximate-echo support. |
| `commands/run_cmd.py` | Resolve avoid at dispatch; echo approximate matches. |
| `planner/data_gateway.py` | Station/system exclusion in `_station_attribute_predicates`; buy-side `item_id NOT IN` at the four seams. |
| `planner/reachability.py` | `avoid_system_ids` threaded into the bubble build. |
| `planner/validation.py` | Un-gate `--avoid`. |
