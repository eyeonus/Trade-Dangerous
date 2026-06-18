"""Via planning (--via): route through one or more waypoints.

The via search owner. It is the credit-optimistic open-anchor backbone
(`route_common._plan_open_anchor_route`) with two additions: a per-chain
satisfied-via mask, and a lane-diversity frontier so every owed waypoint is
pursued in parallel rather than the beam tunnelling on profit and starving a
waypoint.

A frontier entry is ``(node, lane_target)``. The node carries the satisfied-via
mask; the lane target is the persistent steering intent — the one waypoint this
chain is currently heading for, or, once every via is satisfied, the route's
terminal. The label is search state: it is set when a chain enters a lane and
carried forward, never recomputed as "the nearest owed via this layer" (which
would quietly rebuild greedy ordering and lose the orders that only a non-greedy
visit sequence can serve).

This module owns the lane algebra (types, re-fan, the bounded fairness trim) and
the search loop; it imports the shared engine primitives from route_common.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

from . import data_gateway, failures, run_result
from .run_request import RunRequest
from .cargo import cargo_counters
from .route_common import (
    _FrontierNode,
    _MULTIHOP_EXPANSION_WIDTH,
    _MULTIHOP_FRONTIER_WIDTH,
    _OPEN_SHAPE_CORRECTION_WIDTH,
    _OPTIMISTIC_PRICE_PER_TON,
    _correct_open_anchor_chain,
    _elapsed_ms,
    _finalise_correction_stats,
    _make_open_child,
    _multihop_result,
    _node_progress_rank,
    _revisit_active,
    _revisit_forbidden,
    _revisit_key,
    _revisit_seed,
    _root_node,
    _route_progress_rank,
    _stations_from_endpoint,
    _via_full_set,
    _via_satisfied_by,
    best_open_ended_hop_candidates,
)


# Per-lane fairness floor: every admitted (mask, lane_target, root) lane is
# reserved at least this many of the frontier's slots, so no owed-via direction
# is starved by a high-profit zero-progress lane. The rest of the beam is filled
# by global optimistic score. A starting value, tunable on evidence like the
# beam width itself.
_VIA_LANE_FLOOR = 2


class _LaneMode(Enum):
    """What a frontier entry is currently steering toward."""

    VIA = "via"                          # one specific unsatisfied waypoint
    FIXED_TERMINAL = "fixed_terminal"    # all vias met; head for --to / loop root
    OPEN_CONTINUATION = "open"           # all vias met; continue an open route


@dataclass(frozen=True, slots=True)
class _LaneTarget:
    """The persistent steering intent of a frontier entry.

    ``via_tag`` is the ('system'/'station', id) marker of the waypoint a VIA
    lane heads for; it is None for the terminal modes. Frozen and hashable so it
    can key a lane group.
    """

    mode: _LaneMode
    via_tag: tuple | None = None


_LANE_FIXED_TERMINAL = _LaneTarget(_LaneMode.FIXED_TERMINAL)
_LANE_OPEN_CONTINUATION = _LaneTarget(_LaneMode.OPEN_CONTINUATION)


def _lane_via(via_tag: tuple) -> _LaneTarget:
    """A VIA lane steering toward one specific waypoint tag."""

    return _LaneTarget(_LaneMode.VIA, via_tag)


@dataclass(slots=True)
class _LaneEntry:
    """One frontier member: a chain plus the lane it is travelling in."""

    node: _FrontierNode
    target: _LaneTarget


def _lane_targets_for(
    mask: frozenset,
    full_mask: frozenset,
    *,
    fixed_terminal: bool,
) -> list[_LaneTarget]:
    """The lane targets a chain at ``mask`` should occupy.

    One VIA lane per still-owed waypoint while any remain — so every owed via is
    pursued in its own lane — collapsing to a single terminal lane once the mask
    is full: FIXED_TERMINAL for a fixed --to / loop root, OPEN_CONTINUATION for
    an open endpoint.
    """

    owed = full_mask - mask
    if owed:
        return [_lane_via(tag) for tag in owed]
    if fixed_terminal:
        return [_LANE_FIXED_TERMINAL]
    return [_LANE_OPEN_CONTINUATION]


def _child_lane_entries(
    parent: _LaneEntry,
    child: _FrontierNode,
    full_mask: frozenset,
    *,
    fixed_terminal: bool,
) -> list[_LaneEntry]:
    """Place a freshly expanded child into its lane(s).

    Persistent-label rule: if the hop satisfied nothing new, the child stays in
    its parent's lane (one entry, same target). If the mask grew — the chain
    reached its target via, or any other waypoint incidentally — it re-fans into
    a fresh lane per via in its *new* owed set, or the terminal lane once full.
    """

    if child.via_satisfied == parent.node.via_satisfied:
        return [_LaneEntry(child, parent.target)]
    return [
        _LaneEntry(child, target)
        for target in _lane_targets_for(
            child.via_satisfied, full_mask, fixed_terminal=fixed_terminal,
        )
    ]


def _lane_root(node: _FrontierNode, *, loop_mode: bool) -> int | None:
    """The loop-root station id for a chain, or None for non-loop routes.

    Two chains that share a station and a mask but close on different roots are
    different search states, so the root joins the lane and coalesce keys for a
    loop. Non-loop routes carry a neutral None.
    """

    if not loop_mode:
        return None
    return _root_node(node).station.station_id


def _coalesce_key(
    entry: _LaneEntry, *, loop_mode: bool, request: RunRequest, backward: bool,
) -> tuple:
    """Identity for per-(station, mask, lane, root) coalescing.

    Two chains arriving at the same station with the same mask, the same lane
    target and the same root are interchangeable for expansion — keep only the
    higher-scoring one. The lane target is part of the identity: two chains at
    one station with one mask but pursuing different next vias are different
    states and must not be coalesced into one. Under a revisit rule the visited
    history joins the identity too, exactly as on the other engines: two chains
    alike but for where they have been are different search states, and merging
    them could drop the only one that can still complete the route.
    """

    base = (
        entry.node.station.station_id,
        entry.node.via_satisfied,
        entry.target,
        _lane_root(entry.node, loop_mode=loop_mode),
    )
    if _revisit_active(request):
        return base + (_revisit_key(entry.node, request, backward=backward),)
    return base


def _lane_key(entry: _LaneEntry, *, loop_mode: bool) -> tuple:
    """Identity for grouping entries into lanes for the fairness trim."""

    return (
        entry.node.via_satisfied,
        entry.target,
        _lane_root(entry.node, loop_mode=loop_mode),
    )


def _lane_sort_key(lane_key: tuple) -> tuple:
    """Deterministic ordering of lane keys, independent of iteration order.

    Used to break ties between equal-scoring lanes so the surviving via order is
    reproducible rather than dict-iteration dependent. Orders by mask contents,
    then lane target, then root.
    """

    mask, target, root = lane_key
    via_tag = target.via_tag if target.via_tag is not None else ()
    return (
        tuple(sorted(mask)),
        target.mode.value,
        via_tag,
        -1 if root is None else root,
    )


def _terminal_progress_distance(
    node: _FrontierNode,
    terminal_xyz: tuple | None,
    *,
    loop_mode: bool,
) -> float | None:
    """Squared distance from a chain's station to the close it steers for.

    For a fixed --to the reference is the terminal coordinate; for a loop it is
    the chain's own root, which it must return to. Squared distance is enough —
    it is only ever compared, never reported. None when no reference applies.
    """

    if loop_mode:
        ref = _root_node(node).station
        rx, ry, rz = ref.x, ref.y, ref.z
    elif terminal_xyz is not None:
        rx, ry, rz = terminal_xyz
    else:
        return None
    sx, sy, sz = node.station.x, node.station.y, node.station.z
    return (sx - rx) ** 2 + (sy - ry) ** 2 + (sz - rz) ** 2


def _terminal_floor_picks(
    members: list[_LaneEntry],
    take: int,
    terminal_xyz: tuple | None,
    *,
    loop_mode: bool,
) -> tuple[list[_LaneEntry], list[_LaneEntry]]:
    """Floor reservation for a FIXED_TERMINAL lane: score, then progress.

    ``members`` arrive sorted by score, descending. The first reserved slot goes
    to the score leader, so the terminal run can still take a profitable detour;
    the second goes to the chain nearest the terminal/root, so a high-profit
    chain idling on the final waypoint cannot crowd out the one actually closing
    on the destination. Any further floor slots fall back to score order. Returns
    (picked, leftover).
    """

    if take <= 0:
        return [], list(members)
    chosen: list[int] = [0]                       # score leader
    if take >= 2 and len(members) >= 2:
        nearest_i = None
        nearest_d = None
        for i in range(1, len(members)):
            dist = _terminal_progress_distance(
                members[i].node, terminal_xyz, loop_mode=loop_mode,
            )
            if dist is None:
                continue
            if nearest_d is None or dist < nearest_d:
                nearest_d, nearest_i = dist, i
        if nearest_i is not None:
            chosen.append(nearest_i)
    # Any floor slots beyond those two fall back to score order, and members are
    # already score-sorted, so the lowest not-yet-chosen index is next by score.
    for i in range(len(members)):
        if len(chosen) >= take:
            break
        if i not in chosen:
            chosen.append(i)
    chosen_set = set(chosen)
    picked = [members[i] for i in chosen]
    leftover = [
        members[i] for i in range(len(members)) if i not in chosen_set
    ]
    return picked, leftover


def _trim_frontier(
    entries: list[_LaneEntry],
    full_mask: frozenset,
    *,
    loop_mode: bool,
    request: RunRequest,
    backward: bool,
    terminal_xyz: tuple | None = None,
    width: int = _MULTIHOP_FRONTIER_WIDTH,
    floor: int = _VIA_LANE_FLOOR,
) -> list[_LaneEntry]:
    """Coalesce, group into lanes, and trim to the beam width with fairness.

    1. Coalesce by (station, mask, lane, root): keep the best-scoring chain per
       identity.
    2. Group the survivors into lanes by (mask, lane, root); sort each by score.
    3. Leading edge first: lanes whose mask owes the fewest vias are admitted
       before any less-complete lane, so the front never loses ground. Within
       the leading edge, coverage beats depth — every distinct (mask,
       lane_target) direction gets its best root admitted before any direction
       gets a second root, so a waypoint direction is never starved by another
       direction's root fan-out (the loop / system-origin case). Remaining
       lanes follow by score.
    4. Each admitted lane is reserved up to ``floor`` slots; the rest of the
       beam is filled globally by optimistic score across admitted lanes. The
       terminal lane splits its reservation between its score leader and the
       chain nearest the terminal/root, so progress to the destination is never
       crowded out by a profitable chain idling on the final waypoint.

    Admission is deterministic: ties resolve by `_lane_sort_key`, never by dict
    iteration order, so which via order survives a crowded beam is reproducible
    and coverage across masks and lanes is preserved before duplicate roots.
    """

    # 1. Coalesce.
    best: dict[tuple, _LaneEntry] = {}
    for entry in entries:
        key = _coalesce_key(
            entry, loop_mode=loop_mode, request=request, backward=backward,
        )
        current = best.get(key)
        if (
            current is None
            or entry.node.accumulated_practical_score
            > current.node.accumulated_practical_score
        ):
            best[key] = entry

    # 2. Group into lanes.
    lanes: dict[tuple, list[_LaneEntry]] = {}
    for entry in best.values():
        lanes.setdefault(_lane_key(entry, loop_mode=loop_mode), []).append(entry)
    for lane in lanes.values():
        lane.sort(
            key=lambda member: member.node.accumulated_practical_score,
            reverse=True,
        )

    # 3. Admission order. The leading edge (fewest owed vias) is admitted first.
    #    Within it, coverage comes before depth: every distinct (mask,
    #    lane_target) direction contributes its best root before any direction
    #    contributes a second, so root fan-out in one direction cannot starve
    #    another owed-via direction. Less-complete lanes follow by score. Ties
    #    resolve by _lane_sort_key, never by dict iteration order.
    min_owed = min(len(full_mask - lane_key[0]) for lane_key in lanes)

    def _lane_score(members: list[_LaneEntry]) -> float:
        return members[0].node.accumulated_practical_score

    # Leading-edge lanes grouped by direction (mask, lane_target) with the root
    # dropped, so the roots of one direction compete with each other rather than
    # with other directions. Less-complete lanes go straight to the trailing set.
    directions: dict[tuple, list[tuple]] = {}
    trailing: list[tuple] = []
    for lane_key, members in lanes.items():
        if len(full_mask - lane_key[0]) == min_owed:
            directions.setdefault(
                (lane_key[0], lane_key[1]), []
            ).append((lane_key, members))
        else:
            trailing.append((lane_key, members))

    for direction_lanes in directions.values():
        direction_lanes.sort(
            key=lambda item: (-_lane_score(item[1]), _lane_sort_key(item[0]))
        )

    # Directions ordered by their best root's score; a None root in the synthetic
    # key gives a deterministic, root-independent tie-break between directions.
    direction_order = sorted(
        directions,
        key=lambda d: (
            -_lane_score(directions[d][0][1]),
            _lane_sort_key((d[0], d[1], None)),
        ),
    )

    # Round-robin by depth: rank 0 takes every direction's best root, rank 1
    # every direction's second root, and so on — so a direction's second root
    # never precedes another direction's first.
    leading: list[tuple] = []
    depth = max((len(roots) for roots in directions.values()), default=0)
    for rank in range(depth):
        rank_lanes = [
            directions[d][rank]
            for d in direction_order
            if rank < len(directions[d])
        ]
        rank_lanes.sort(
            key=lambda item: (-_lane_score(item[1]), _lane_sort_key(item[0]))
        )
        leading.extend(rank_lanes)

    trailing.sort(
        key=lambda item: (-_lane_score(item[1]), _lane_sort_key(item[0]))
    )
    ordered_lanes = leading + trailing

    # 4. Reserve the floor per admitted lane, then fill the remainder globally.
    #    A FIXED_TERMINAL lane splits its floor between its score leader and the
    #    chain nearest the terminal/root, so a high-profit chain idling on the
    #    last waypoint cannot crowd out the one closing on the destination. Every
    #    other lane reserves its floor by score, unchanged.
    selected: list[_LaneEntry] = []
    leftover: list[_LaneEntry] = []
    remaining = width
    for lane_key_value, members in ordered_lanes:
        if remaining <= 0:
            leftover.extend(members)
            continue
        take = min(floor, len(members), remaining)
        if lane_key_value[1].mode is _LaneMode.FIXED_TERMINAL:
            picked, lane_leftover = _terminal_floor_picks(
                members, take, terminal_xyz, loop_mode=loop_mode,
            )
            selected.extend(picked)
            leftover.extend(lane_leftover)
            remaining -= len(picked)
        else:
            selected.extend(members[:take])
            leftover.extend(members[take:])
            remaining -= take

    if remaining > 0 and leftover:
        leftover.sort(
            key=lambda member: member.node.accumulated_practical_score,
            reverse=True,
        )
        selected.extend(leftover[:remaining])

    return selected


def _via_pos_map(request: RunRequest) -> dict:
    """Map each via tag to the system coordinates the search steers toward."""

    return {
        target.tag: (target.x, target.y, target.z)
        for target in request.via_targets
    }


def _lane_steering(
    entry: _LaneEntry,
    *,
    loop_mode: bool,
    via_pos: dict,
    terminal_xyz: tuple | None,
    terminal_exact_ids: frozenset,
    terminal_system_ids: frozenset,
    envelope_ly: float,
    final_layer: bool,
):
    """Envelope, ranking and reservation inputs for one lane's expansion.

    Returns (envelope_xyz, envelope_ly, distance_first, required_station_ids,
    terminal_system_station_ids) for the seam primitive. The envelope is a
    feasibility bound; distance_first is the ranking heuristic, on only while a
    waypoint is still owed.

      VIA(tag)          — envelope toward the owed waypoint AND distance-first
                          ranking, to actively preserve progress to the via;
                          reserve the exact station when the via names one.
      FIXED_TERMINAL    — envelope toward the fixed --to (or the chain's own
                          loop root) but score-first ranking, so the terminal
                          run can take profitable detours and fill the hop
                          budget rather than beelining and arriving early;
                          reserve the terminal only on the final layer.
      OPEN_CONTINUATION — no envelope, no distance-first; ordinary open ranking.
    """

    target = entry.target
    if target.mode is _LaneMode.VIA:
        # An exact station via is reserved past the trim; a system via is met by
        # any station in it, so the envelope alone steers there. Distance-first
        # keeps the chain making progress toward the owed waypoint.
        required = (
            frozenset({target.via_tag[1]})
            if target.via_tag[0] == "station"
            else frozenset()
        )
        return (
            via_pos.get(target.via_tag),
            envelope_ly,
            True,
            required,
            frozenset(),
        )

    if target.mode is _LaneMode.FIXED_TERMINAL:
        # Vias done — an ordinary terminal-closing run. Keep the envelope as a
        # feasibility bound, but rank by score so the chain can detour for
        # profit and fill the remaining hops, the way the non-via fixed-terminal
        # planner does, instead of beelining the terminal and arriving early.
        if loop_mode:
            root_station = _root_node(entry.node).station
            xyz = (root_station.x, root_station.y, root_station.z)
            required = (
                frozenset({root_station.station_id})
                if final_layer else frozenset()
            )
            return xyz, envelope_ly, False, required, frozenset()
        required = terminal_exact_ids if final_layer else frozenset()
        term_sys = terminal_system_ids if final_layer else frozenset()
        return terminal_xyz, envelope_ly, False, required, term_sys

    return None, None, False, frozenset(), frozenset()


def _at_endpoint(
    node: _FrontierNode,
    *,
    loop_mode: bool,
    terminal_endpoint_ids: frozenset,
    open_endpoint: bool,
) -> bool:
    """Whether a full-mask chain satisfies its route shape's endpoint rule.

    Open shapes accept any emerged end. A loop must close on its own root. A
    fixed --to must finish at one of that endpoint's eligible stations.
    """

    if open_endpoint:
        return True
    if loop_mode:
        return node.station.station_id == _root_node(node).station.station_id
    return node.station.station_id in terminal_endpoint_ids


def _plan_via_route(
    session,
    request: RunRequest,
    started: float,
    validation_ms: float,
    bubble_cache: dict,
) -> run_result.RunResult:
    """Plan an N-hop route through every --via waypoint.

    The credit-optimistic open-anchor search with a satisfied-via mask and a
    lane-diversity frontier. Direction and endpoint follow the anchored shape:
    forward from --from for from+to / from-only / loop, backward from --to for
    to-only; the finalist must carry the full mask and satisfy the shape's
    endpoint rule. No partial-via route is ever returned — any collapse raises
    NoViaRoute.
    """

    full_mask = _via_full_set(request)
    loop_mode = request.loop

    # Search direction, terminal mode, and the seeded (fixed) endpoint.
    if loop_mode or (request.from_endpoint is not None
                     and request.to_endpoint is not None):
        open_role, anchor_role = "destination", "source"
        anchor_endpoint = request.from_endpoint
        fixed_terminal, open_endpoint = True, False
    elif request.from_endpoint is not None:
        open_role, anchor_role = "destination", "source"
        anchor_endpoint = request.from_endpoint
        fixed_terminal, open_endpoint = False, True
    else:
        open_role, anchor_role = "source", "destination"
        anchor_endpoint = request.to_endpoint
        fixed_terminal, open_endpoint = False, True

    resolution_ms = 0.0
    station_filter_started = time.perf_counter()
    seed_stations = _stations_from_endpoint(
        session, anchor_endpoint, request, role=anchor_role,
    )

    if loop_mode:
        # A loop closes on its own root, so every seed station must also be a
        # valid *destination* — settled before the bounded frontier is seeded so
        # an unclosable root never crowds a closable one out of the beam. Drop
        # avoided roots (the --from origin carve-out lets the commander start in
        # an avoided place, but the loop returns there, so it cannot be the
        # terminal), then keep only roots with usable return demand.
        roots = tuple(
            station for station in seed_stations
            if station.station_id not in request.avoid_station_ids
            and station.system_id not in request.avoid_system_ids
        )
        closable = data_gateway.fetch_loop_closable_station_ids(
            session,
            tuple(station.station_id for station in roots),
            request,
        )
        seed_stations = [
            station for station in roots
            if station.station_id in closable
        ]
        if not seed_stations:
            raise failures.NoViaRoute(
                "No starting station can both open and close a loop through "
                "every --via waypoint under the supplied constraints.",
                option_name="--via",
            )

    # A fixed --to (not a loop) supplies the terminal the route must finish at:
    # the eligible Y stations for the endpoint check, the exact station to
    # reserve when --to names one, or the whole eligible set when --to is a
    # system.
    terminal_endpoint_ids: frozenset = frozenset()
    terminal_exact_ids: frozenset = frozenset()
    terminal_system_ids: frozenset = frozenset()
    terminal_xyz: tuple | None = None
    if fixed_terminal and not loop_mode:
        terminal_stations = _stations_from_endpoint(
            session, request.to_endpoint, request, role="destination",
        )
        if not terminal_stations:
            raise failures.NoViaRoute(
                "No eligible --to station could anchor the via route.",
                option_name="--via",
            )
        terminal_endpoint_ids = frozenset(
            s.station_id for s in terminal_stations
        )
        first = terminal_stations[0]
        terminal_xyz = (first.x, first.y, first.z)
        if request.to_endpoint.station is not None:
            terminal_exact_ids = frozenset(
                {request.to_endpoint.station.station_id}
            )
        else:
            terminal_system_ids = terminal_endpoint_ids
    station_filter_ms = _elapsed_ms(station_filter_started)

    base_trade_budget = (
        int(request.starting_credits or 0) - request.insurance_reserve
    )
    optimistic_credits = (
        int(request.capacity_units or 0) * _OPTIMISTIC_PRICE_PER_TON
    )
    via_pos = _via_pos_map(request)
    jumps_per = int(request.max_jumps_per_hop or 0)
    ly_per = float(request.max_ly_per_jump or 0.0)

    # Seed: each eligible anchor station at hop 0, carrying the vias it stands
    # on, fanned into one lane per still-owed via (or the terminal lane if the
    # anchor already satisfies everything).
    frontier: list[_LaneEntry] = []
    for station in seed_stations:
        node = _FrontierNode(
            station=station,
            parent=None,
            hop_index=0,
            accumulated_raw_profit=0,
            accumulated_practical_score=0.0,
            available_credits=0,
            hop_cargo=None,
            hop_jump_path=None,
            hop_practical_score=0.0,
            hop_raw_profit=0,
            hop_candidates=None,
            via_satisfied=_via_satisfied_by(station, request),
            visited_order=_revisit_seed(station.station_id, request),
        )
        for target in _lane_targets_for(
            node.via_satisfied, full_mask, fixed_terminal=fixed_terminal,
        ):
            frontier.append(_LaneEntry(node, target))

    reachable_memo: dict = {}
    qualification = data_gateway.QualificationCache()
    station_cache: dict = {}
    market_query_ms = 0.0
    candidate_trade_count = 0
    frontier_widths: list[int] = []
    expansions_examined = 0
    layer_stats: list = []
    expansion_stats = run_result.ExpansionStats()
    correction_stats = run_result.CorrectionStats()

    def _expand(entry, envelope_ly, *, terminal_hop, final_layer):
        (
            env_xyz, env_ly, distance_first, required_ids, term_sys,
        ) = _lane_steering(
            entry,
            loop_mode=loop_mode,
            via_pos=via_pos,
            terminal_xyz=terminal_xyz,
            terminal_exact_ids=terminal_exact_ids,
            terminal_system_ids=terminal_system_ids,
            envelope_ly=envelope_ly,
            final_layer=final_layer,
        )
        return best_open_ended_hop_candidates(
            session,
            entry.node.station,
            request,
            open_role=open_role,
            optimistic_credits=optimistic_credits,
            top_k=_MULTIHOP_EXPANSION_WIDTH,
            terminal_hop=terminal_hop,
            bubble_cache=bubble_cache,
            reachable_memo=reachable_memo,
            expansion_stats=expansion_stats,
            station_cache=station_cache,
            qualification=qualification,
            envelope_xyz=env_xyz,
            envelope_ly=env_ly,
            distance_first=distance_first,
            no_affordability=True,
            required_station_ids=required_ids,
            terminal_system_station_ids=term_sys,
            forbidden_station_ids=_revisit_forbidden(
                entry.node, request, backward=open_role == "source",
            ),
        )

    try:
        # Intermediate layers 1..N-1: grow toward each owed via, re-fan on every
        # mask change, then trim with lane fairness.
        for hop_layer in range(1, request.hops):
            envelope_ly = float((request.hops - hop_layer) * jumps_per * ly_per)
            layer_started = time.perf_counter()
            layer_frontier_in = len(frontier)
            layer_expansion_calls = 0
            layer_children_generated = 0
            next_entries: list[_LaneEntry] = []
            for entry in frontier:
                expansions_examined += 1
                layer_expansion_calls += 1
                for trade in _expand(
                    entry, envelope_ly, terminal_hop=False, final_layer=False,
                ):
                    child = _make_open_child(entry.node, trade, request, open_role=open_role)
                    candidate_trade_count += 1
                    layer_children_generated += 1
                    next_entries.extend(
                        _child_lane_entries(
                            entry, child, full_mask,
                            fixed_terminal=fixed_terminal,
                        )
                    )
            layer_elapsed_ms = _elapsed_ms(layer_started)
            market_query_ms += layer_elapsed_ms

            if not next_entries:
                layer_stats.append(
                    run_result.LayerStats(
                        layer_index=hop_layer,
                        frontier_size_in=layer_frontier_in,
                        expansion_calls=layer_expansion_calls,
                        children_generated=layer_children_generated,
                        children_kept=0,
                        elapsed_ms=layer_elapsed_ms,
                    )
                )
                raise failures.NoViaRoute(
                    "No route reached every --via waypoint within the supplied "
                    "constraints (jump range, jumps per hop, and hop count).",
                    option_name="--via",
                )

            frontier = _trim_frontier(
                next_entries, full_mask, loop_mode=loop_mode,
                request=request, backward=open_role == "source",
                terminal_xyz=terminal_xyz,
            )
            frontier_widths.append(len(frontier))
            layer_stats.append(
                run_result.LayerStats(
                    layer_index=hop_layer,
                    frontier_size_in=layer_frontier_in,
                    expansion_calls=layer_expansion_calls,
                    children_generated=layer_children_generated,
                    children_kept=len(frontier),
                    elapsed_ms=layer_elapsed_ms,
                )
            )

        # Final layer (hop N): steer to the terminal / open end and keep only
        # full-mask chains that satisfy the endpoint rule.
        final_hop_started = time.perf_counter()
        final_envelope_ly = float(jumps_per * ly_per)
        finalist_nodes: list[_FrontierNode] = []
        for entry in frontier:
            expansions_examined += 1
            for trade in _expand(
                entry, final_envelope_ly, terminal_hop=True, final_layer=True,
            ):
                node = _make_open_child(entry.node, trade, request, open_role=open_role)
                candidate_trade_count += 1
                if node.via_satisfied == full_mask and _at_endpoint(
                    node,
                    loop_mode=loop_mode,
                    terminal_endpoint_ids=terminal_endpoint_ids,
                    open_endpoint=open_endpoint,
                ):
                    finalist_nodes.append(node)
        market_query_ms += _elapsed_ms(final_hop_started)

        if not finalist_nodes:
            raise failures.NoViaRoute(
                "No route visited every --via waypoint and reached the "
                "requested endpoint within the supplied constraints.",
                option_name="--via",
            )

        # End-to-end forward credit correction: re-fit each finalist against the
        # real running budget, keep the best corrected route. Same exact
        # early-stop and width cap as the open-anchor engine.
        correction_stats.finalists_generated = len(finalist_nodes)
        correction_started = time.perf_counter()
        correction_fast_before, correction_bb_before = cargo_counters()
        best_route = None
        finalist_nodes.sort(
            key=lambda candidate: _node_progress_rank(candidate, request),
            reverse=True,
        )
        for node in finalist_nodes:
            if (
                best_route is not None
                and _node_progress_rank(node, request)
                <= _route_progress_rank(best_route, request)
            ):
                break
            if (
                correction_stats.finalists_attempted
                >= _OPEN_SHAPE_CORRECTION_WIDTH
            ):
                break
            correction_stats.finalists_attempted += 1
            corrected = _correct_open_anchor_chain(
                node, request, base_trade_budget, open_role,
            )
            if corrected is None:
                continue
            correction_stats.finalists_corrected += 1
            if (
                best_route is None
                or _route_progress_rank(corrected, request)
                > _route_progress_rank(best_route, request)
            ):
                best_route = corrected
        _finalise_correction_stats(
            correction_stats, correction_started,
            correction_fast_before, correction_bb_before,
        )

        if best_route is None:
            raise failures.NoViaRoute(
                "No route through every --via waypoint was affordable under "
                "the supplied credits.",
                option_name="--via",
            )
        route = best_route
    finally:
        qualification.release(session)
        data_gateway.release_reachable_memo(session, reachable_memo)

    return _multihop_result(
        request=request,
        route=route,
        started=started,
        validation_ms=validation_ms,
        resolution_ms=resolution_ms,
        station_filter_ms=station_filter_ms,
        market_query_ms=market_query_ms,
        candidate_trade_count=candidate_trade_count,
        frontier_widths=frontier_widths,
        expansions_examined=expansions_examined,
        layer_stats=layer_stats,
        expansion_stats=expansion_stats,
        final_hop_stats=None,
        correction_stats=correction_stats,
    )
