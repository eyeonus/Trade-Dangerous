"""Shared multi-hop frontier machinery and generic planner helpers."""

from __future__ import annotations

import heapq
import time
from dataclasses import dataclass, replace

from sqlalchemy.orm import Session

from . import data_gateway, failures, resolver, run_result
from .cargo import cargo_counters, cargo_pruned, cargo_time_ms, optimise_cargo
from .reachability import plan_jump_path, reachable_systems_from
from .run_request import RunRequest
from .score import ls_penalty_multiplier, score_with_destination_penalty


@dataclass(frozen=True, slots=True)
class _FrontierNode:
    """A partial route ending at one station after K trade hops.

    Multi-hop search builds a layered frontier: each layer is the set of
    nodes ending at hop K, ranked and trimmed by accumulated practical
    score. A node carries the cargo and jump path of the hop that brought
    it here so the surviving winner can walk its parent chain back to the
    origin and emit a full route. available_credits is the post-margin
    budget for the next hop's buy.

    The open-anchor search reuses this struct for both open shapes. There
    available_credits is unused (open-anchor expansion is credit-optimistic;
    the real budget is applied by the forward credit-correction pass), and
    hop_candidates is populated so that pass can re-fit each hop. The
    open-origin shape additionally grows the chain backward, from the
    destination toward the origin.
    """

    station: run_result.ResolvedStation
    parent: _FrontierNode | None
    hop_index: int
    accumulated_raw_profit: int
    accumulated_practical_score: float
    available_credits: int
    hop_cargo: run_result.CargoPlan | None
    hop_jump_path: run_result.JumpPath | None
    hop_practical_score: float
    hop_raw_profit: int
    # Open-anchor expansion only: the per-pair TradeCandidate tuple
    # for the hop that arrived at this node, kept so the forward credit-
    # correction pass can re-fit cargo against the real running budget. None on
    # the forward path.
    hop_candidates: tuple[run_result.TradeCandidate, ...] | None = None
    # --via tracking: the via places this chain has visited so far, each tagged
    # ('system', id) / ('station', id). Empty for non-via runs, so it is an
    # inert marker there — it never changes the dedupe key or any comparison.
    # Carried so the beam can keep chains that have satisfied different vias from
    # crowding one another out, and accept only a chain that has visited them all.
    via_satisfied: frozenset = frozenset()


@dataclass(frozen=True, slots=True)
class _HopCandidate:
    """One viable forward trade from a known source station.

    Multi-hop expansion calls best_open_ended_trades_from once per frontier
    node; that helper returns the per-node top-K candidates as _HopCandidate
    rows. The frontier loop turns each into a child node by attaching the
    parent and accumulating profit/score and the post-hop credit budget.

    Open-anchor expansion reuses this struct via
    best_open_ended_hop_candidates for both open shapes; hop_candidates is
    populated so the forward credit-correction pass can re-fit cargo against
    the real budget. In the open-origin shape destination_station carries the
    chosen *source* — the station the route reaches when the chain is walked
    backward from a node.
    """

    destination_station: run_result.ResolvedStation
    cargo: run_result.CargoPlan
    jump_path: run_result.JumpPath
    practical_score: float
    raw_profit: int
    # Open-anchor expansion only: the per-pair TradeCandidate tuple
    # the optimistic cargo was fitted from, kept so the credit-correction pass
    # can re-fit against the real running budget. None on the forward path,
    # which fits cargo against the correct budget at expansion time.
    hop_candidates: tuple[run_result.TradeCandidate, ...] | None = None


# Beam widths for multi-hop frontier search. Expansion width caps the per-node
# fan-out at one hop layer; frontier width caps the number of partial routes
# carried into the next layer. Both are kept at 50: the
# top-100 score curve for representative Bubble runs is smooth out past rank
# 50, well above the 25%-of-#1 threshold that would justify trimming.
_MULTIHOP_EXPANSION_WIDTH = 50


_MULTIHOP_FRONTIER_WIDTH = 50


class _KeptScoreThreshold:
    """Running practical-score floor for the top-K pairs a search keeps.

    A pair whose optimistic ceiling cannot reach current() can skip its cargo
    solve — it could never enter the kept set. K=1 collapses to "the single best
    so far", which is exactly what the one-hop planners keep.

    current() returns None (prune nothing) until the kept set is full, or when
    pruning is disabled — e.g. --towards ranks by progress toward the target,
    not by score, so a score floor would be meaningless there.
    """

    __slots__ = ("_k", "_enabled", "_heap")

    def __init__(self, keep_k: int, *, enabled: bool = True):
        self._k = keep_k
        self._enabled = enabled
        self._heap: list[float] = []          # min-heap of kept practical scores

    def current(self) -> float | None:
        if not self._enabled or len(self._heap) < self._k:
            return None
        return self._heap[0]

    def offer(self, score: float) -> None:
        """Record a solved pair's practical score into the kept set."""
        if not self._enabled:
            return
        if len(self._heap) < self._k:
            heapq.heappush(self._heap, score)
        elif score > self._heap[0]:
            heapq.heapreplace(self._heap, score)


def cargo_prune_floor(
    threshold: float | None,
    destination_ls: int | None,
    penalty_percent: float,
) -> float | None:
    """Raw-profit floor a pair to this destination must clear to place.

    The kept set ranks by practical score = raw profit * ls multiplier, so the
    practical threshold converts to a raw-profit floor by dividing out this
    destination's exact multiplier (cheap — it needs only ls distance and the
    penalty, both known before any solve). Handed to optimise_cargo as
    prune_below_raw.

    Returns None — meaning do not prune — when the threshold is not set yet, or
    when the multiplier is non-positive (an extreme-distance station whose
    practical score is <= 0 regardless of profit; rare, left for the solve).
    """
    if threshold is None:
        return None
    multiplier = ls_penalty_multiplier(destination_ls, penalty_percent)
    if multiplier <= 0:
        return None
    return threshold / multiplier


def cargo_order_key(
    pair_candidates: tuple[run_result.TradeCandidate, ...],
    destination_ls: int | None,
    capacity_units: int,
    penalty_percent: float,
) -> float:
    """Cheap best-first ordering score for a candidate pair.

    Sorting pairs by this descending solves the most promising first, so the
    kept-score threshold rises fast and the long tail prunes hard. It is a loose
    optimistic estimate (a full hold of the best per-unit margin, scaled by the
    destination multiplier); ordering affects only prune efficiency, never the
    result, so it need not be admissible.
    """
    best_ppu = max(candidate.profit_per_unit for candidate in pair_candidates)
    return (
        capacity_units
        * best_ppu
        * ls_penalty_multiplier(destination_ls, penalty_percent)
    )


def _multihop_result(
    *,
    request: RunRequest,
    route: run_result.PlannedRoute,
    started: float,
    validation_ms: float,
    resolution_ms: float,
    station_filter_ms: float,
    market_query_ms: float,
    candidate_trade_count: int,
    frontier_widths: list[int],
    expansions_examined: int,
    layer_stats: list[run_result.LayerStats],
    expansion_stats: run_result.ExpansionStats,
    final_hop_stats: run_result.FinalHopStats | None,
    correction_stats: run_result.CorrectionStats | None = None,
    warning: run_result.PartialRouteWarning | None = None,
) -> run_result.RunResult:
    """Build a multi-hop RunResult with diagnostics and optional warning."""
    
    # Complete and partial multi-hop routes use the same diagnostics builder.
    # Partial-route handling should only change the warning payload, not lose
    # the search counters that explain how far the frontier progressed.
    #
    # market_query_ms here is the whole forward-expansion cost (fetch,
    # cargo, scoring, jump-path lookup). The richer breakdown lives in
    # multihop_layers / multihop_expansion_stats / multihop_final_hop_stats
    # — see the diagnostic renderer for a compact summary.
    cargo_fast_hits, cargo_recursive_hits = cargo_counters()
    diagnostics = run_result.PlannerDiagnostics(
        validation_ms=validation_ms,
        resolution_ms=resolution_ms,
        station_filter_ms=station_filter_ms,
        market_query_ms=market_query_ms,
        total_planner_ms=_elapsed_ms(started),
        candidate_trade_count=candidate_trade_count,
        hops_planned=request.hops,
        multihop_frontier_widths=tuple(frontier_widths),
        multihop_expansions_examined=expansions_examined,
        multihop_layers=tuple(layer_stats),
        multihop_expansion_stats=expansion_stats,
        multihop_final_hop_stats=final_hop_stats,
        cargo_fast_path_hits=cargo_fast_hits,
        cargo_recursive_hits=cargo_recursive_hits,
        cargo_pruned_solves=cargo_pruned(),
        cargo_optimisation_ms=cargo_time_ms(),
        multihop_correction_stats=correction_stats,
    )
    
    # The planner emits structured facts; renderer wording belongs in
    # render_text.py so CLI output can change without rewriting planner state.
    warnings = () if warning is None else (warning,)
    return run_result.RunResult(
        routes=(route,),
        diagnostics=diagnostics,
        warnings=warnings,
    )


def _best_partial_node(frontier: list[_FrontierNode]) -> _FrontierNode | None:
    """Return the best completed partial route in a frontier, if any.
    
    Origin nodes have hop_index 0 and cannot be rendered as useful partial
    trade routes: there is no cargo, no destination, and no completed hop to
    show. Once hop_index is at least 1, the node has a complete parent chain
    and _reconstruct_route() can turn it into a normal PlannedRoute without
    re-running any search work.
    """
    
    completed = [node for node in frontier if node.hop_index > 0]
    if not completed:
        return None
    return max(
        completed,
        key=lambda node: node.accumulated_practical_score,
    )


def _distance_sq_to_target(
    station: run_result.ResolvedStation,
    target: run_result.ResolvedSystem,
) -> float:
    """Squared straight-line distance from a station's system to the target."""

    dx = station.x - target.x
    dy = station.y - target.y
    dz = station.z - target.z
    return dx * dx + dy * dy + dz * dz


def _node_progress_rank(node: _FrontierNode, request: RunRequest) -> tuple:
    """Ranking key for a frontier node / chain; higher sorts as better.

    Without --towards: rank by accumulated practical score (profit) — today's
    behaviour, returned as a one-tuple so every sort and comparison stays
    identical. With --towards the rule is progress-first: the chain whose latest
    station is closest to the target wins; among equally close chains the
    shorter one wins (do not meander to chase profit); profit only breaks the
    remaining tie.
    """

    target = request.towards_target
    if target is None:
        return (node.accumulated_practical_score,)
    return (
        -_distance_sq_to_target(node.station, target),
        -node.hop_index,
        node.accumulated_practical_score,
    )


def _route_progress_rank(
    route: run_result.PlannedRoute, request: RunRequest
) -> tuple:
    """Ranking key for a completed/corrected route, matching _node_progress_rank.

    The route's last station is the endpoint it reached, so --towards ranks
    routes by how close that endpoint is to the target, then by fewer hops, then
    by practical score. An arrival (distance zero, fewest hops) therefore wins.
    """

    target = request.towards_target
    if target is None:
        return (route.total_practical_score,)
    return (
        -_distance_sq_to_target(route.stations[-1], target),
        -len(route.hops),
        route.total_practical_score,
    )


def _candidate_progress_rank(scored_item: tuple, request: RunRequest) -> tuple:
    """Ranking key for one node's per-hop candidates (open station + score).

    A single node's candidates are all one hop away, so depth is equal across
    them; --towards ranks by the open station's closeness to the target, profit
    breaking ties. Without --towards, profit alone — today's behaviour.
    """

    practical_score = scored_item[0]
    open_station = scored_item[1]
    target = request.towards_target
    if target is None:
        return (practical_score,)
    return (-_distance_sq_to_target(open_station, target), practical_score)


def _via_satisfied_by(
    station: run_result.ResolvedStation,
    request: RunRequest,
) -> frozenset:
    """Return the via places a single station visit satisfies.

    A via place is tagged ('system', id) or ('station', id) so the system and
    station id spaces never collide. A station satisfies the via for its own
    system and the via for itself, each when that place was named. Returns the
    empty set when no via was requested, so non-via runs carry an inert marker.
    """

    if not request.via_system_ids and not request.via_station_ids:
        return frozenset()
    satisfied = set()
    if station.system_id in request.via_system_ids:
        satisfied.add(("system", station.system_id))
    if station.station_id in request.via_station_ids:
        satisfied.add(("station", station.station_id))
    return frozenset(satisfied)


def _via_full_set(request: RunRequest) -> frozenset:
    """The complete set of via places a finished route must have visited.

    Empty when no --via was requested, so "every via satisfied" is trivially
    true and the non-via path is unaffected.
    """

    return frozenset(
        [("system", s) for s in request.via_system_ids]
        + [("station", t) for t in request.via_station_ids]
    )


def _root_node(node: _FrontierNode) -> _FrontierNode:
    """Walk a chain's parent links back to its hop-0 origin node.

    Loop and via routes need each chain's root for the terminal rule, the
    envelope anchor, and the frontier dedupe / lane keys. Hops are capped at 25,
    so the walk is trivial.
    """

    while node.parent is not None:
        node = node.parent
    return node


def _make_child_node(
    parent: _FrontierNode,
    trade: _HopCandidate,
    request: RunRequest,
    base_trade_budget: int,
) -> _FrontierNode:
    """Extend a frontier node by one hop using a chosen trade.

    Credits roll forward with the margin haircut applied: only
    ``(1 - margin)`` of accumulated raw profit is trusted as future buying
    power, integer-floored so the cargo optimiser is never handed a float.
    Accumulated raw profit and raw credits at the end of the route remain
    untouched by margin; only the per-hop budget shrinks.
    """

    new_profit = parent.accumulated_raw_profit + trade.raw_profit
    new_score = parent.accumulated_practical_score + trade.practical_score
    trusted_profit = int((1.0 - request.margin) * new_profit)
    new_credits = base_trade_budget + trusted_profit
    return _FrontierNode(
        station=trade.destination_station,
        parent=parent,
        hop_index=parent.hop_index + 1,
        accumulated_raw_profit=new_profit,
        accumulated_practical_score=new_score,
        available_credits=new_credits,
        hop_cargo=trade.cargo,
        hop_jump_path=trade.jump_path,
        hop_practical_score=trade.practical_score,
        hop_raw_profit=trade.raw_profit,
        via_satisfied=parent.via_satisfied | _via_satisfied_by(
            trade.destination_station, request,
        ),
    )


def _reconstruct_route(
    winner: _FrontierNode,
    request: RunRequest,
) -> run_result.PlannedRoute:
    """Walk a winning frontier node back to the origin and build a route.

    The winner's parent chain ends at the origin node (parent=None,
    hop_index=0). Reversing it yields the station sequence in route order;
    each non-origin node carries the cargo, score, profit, and jump path of
    the hop that arrived there, so a PlannedHop can be built without
    re-running any planning work.
    """

    nodes: list[_FrontierNode] = []
    current: _FrontierNode | None = winner
    while current is not None:
        nodes.append(current)
        current = current.parent
    nodes.reverse()

    hops_built: list[run_result.PlannedHop] = []
    for i in range(1, len(nodes)):
        prev_node = nodes[i - 1]
        node = nodes[i]
        if node.hop_cargo is None or node.hop_jump_path is None:
            # Defensive: every non-origin node is built from a real trade,
            # so cargo and jump_path are always populated. A missing field
            # would mean the frontier was extended by something other than
            # _make_child_node, which would be a bug, not a user failure.
            raise failures.PlannerInternalError(
                "Reconstructed multi-hop route has a hop missing cargo "
                "or jump path."
            )
        hops_built.append(
            run_result.PlannedHop(
                source_station=prev_node.station,
                destination_station=node.station,
                cargo=node.hop_cargo,
                raw_profit=node.hop_raw_profit,
                practical_score=node.hop_practical_score,
                jump_path=node.hop_jump_path,
            )
        )

    stations = tuple(node.station for node in nodes)
    starting_credits = int(request.starting_credits or 0)
    return run_result.PlannedRoute(
        stations=stations,
        hops=tuple(hops_built),
        total_raw_profit=winner.accumulated_raw_profit,
        total_practical_score=winner.accumulated_practical_score,
        starting_credits=starting_credits,
        ending_credits=starting_credits + winner.accumulated_raw_profit,
    )


def _stations_from_endpoint(
    session: Session,
    endpoint: resolver.ResolvedEndpoint,
    request: RunRequest,
    *,
    role: str,
) -> tuple[run_result.ResolvedStation, ...]:
    """Return candidate stations for a fixed station or expanded system endpoint.

    Fixed station endpoints still use the same station-level validation path.
    System endpoints are bounded to stations in that one resolved system; this
    is not broad route expansion or fuzzy endpoint matching.

    With --start-jumps (source) or --end-jumps (destination) set, the endpoint
    is instead treated as a positioning anchor and expanded into the eligible
    stations within that many empty jumps — see _positioning_stations.
    """

    positioning_jumps = (
        request.start_jumps if role == "source" else request.end_jumps
    )
    if positioning_jumps > 0:
        return _positioning_stations(
            session,
            endpoint,
            request,
            role=role,
            positioning_jumps=positioning_jumps,
        )

    if endpoint.station is not None:
        data_gateway.validate_station_filters(endpoint.station, request, role=role)
        return (endpoint.station,)

    if endpoint.system is None:
        raise failures.UnknownPlace(
            f"{endpoint.option_name} could not be resolved.",
            option_name=endpoint.option_name,
            entity_name=endpoint.original_text,
        )

    # Explicit-origin carve-out: a --from system the commander also avoided is
    # still a valid place to START from -- they named it. Drop just that system
    # from the system-avoid set for this origin fetch, so its stations are
    # eligible origins. avoid still applies everywhere else (destinations,
    # transit, later hops) and to any specific avoided station within the system,
    # so the route never returns. Destinations get no carve-out: avoiding where
    # you must end is a genuine contradiction, left to fail.
    origin_request = request
    if role == "source" and endpoint.system.system_id in request.avoid_system_ids:
        origin_request = replace(
            request,
            avoid_system_ids=request.avoid_system_ids
            - {endpoint.system.system_id},
        )

    stations = data_gateway.fetch_eligible_stations_in_system(
        session,
        endpoint.system,
        origin_request,
        role=role,
    )
    if stations:
        return stations

    failure_type = (
        failures.SourceStationIneligible
        if role == "source"
        else failures.DestinationStationIneligible
    )
    raise failure_type(
        f"{endpoint.option_name} system has no eligible {role} stations.",
        option_name=endpoint.option_name,
        entity_name=endpoint.original_text,
    )


def _positioning_stations(
    session: Session,
    endpoint: resolver.ResolvedEndpoint,
    request: RunRequest,
    *,
    role: str,
    positioning_jumps: int,
) -> tuple[run_result.ResolvedStation, ...]:
    """Expand a positioning anchor into eligible stations within N empty jumps.

    --start-jumps / --end-jumps treat the named --from / --to as a physical
    anchor, not a forced trade endpoint. The eligible trade stations are those
    reachable within ``positioning_jumps`` empty jumps of the anchor's parent
    system. The anchor station itself is never validated here — it is a
    positioning point, so it appears in the result only if the expansion fetch
    independently admits it.
    """

    anchor_system = _positioning_anchor_system(endpoint)
    if anchor_system is None:
        raise failures.UnknownPlace(
            f"{endpoint.option_name} could not be resolved.",
            option_name=endpoint.option_name,
            entity_name=endpoint.original_text,
        )

    # Empty jumps carry no cargo, so they use the unladen range: --empty-ly if
    # supplied, else --ly-per. This is a different reach from the per-hop laden
    # --ly-per — it sizes the positioning net, not a trade hop.
    empty_ly = request.empty_ly_per or request.max_ly_per_jump

    # The positioning bubble's radius (positioning_jumps * empty_ly) differs
    # from the per-hop bubble for the same anchor, and reachable_systems_from
    # keys its cache on system_id alone. A private cache keeps the wrong-radius
    # bubble out of the per-hop cache shared across the rest of the plan.
    positioning_bubble_cache: dict = {}
    reachable = reachable_systems_from(
        session,
        anchor_system,
        max_jumps_per_hop=positioning_jumps,
        max_ly_per_jump=float(empty_ly or 0.0),
        bubble_cache=positioning_bubble_cache,
        avoid_system_ids=request.avoid_system_ids,
    )

    stations = data_gateway.fetch_eligible_stations_in_reachable_systems(
        session,
        reachable,
        request,
        role=role,
    )
    if stations:
        return stations

    failure_type = (
        failures.SourceStationIneligible
        if role == "source"
        else failures.DestinationStationIneligible
    )
    reach_noun = "origin" if role == "source" else "destination"
    raise failure_type(
        f"No eligible {reach_noun} station was found within "
        f"{positioning_jumps} empty jump(s) of {endpoint.original_text}.",
        option_name=endpoint.option_name,
        entity_name=endpoint.original_text,
    )


def _positioning_anchor_system(
    endpoint: resolver.ResolvedEndpoint,
) -> run_result.ResolvedSystem | None:
    """Return the anchor system for an endpoint used as a positioning point.

    A station anchor positions on its parent system; a system anchor positions
    on itself. Unlike the fixed-endpoint path, a positioning anchor is never
    station-filter validated, so this returns None for an unresolved endpoint
    and lets the caller raise rather than assuming one side is populated.
    """

    if endpoint.station is not None:
        return _system_from_station(endpoint.station)
    return endpoint.system


def _system_from_station(
    station: run_result.ResolvedStation,
) -> run_result.ResolvedSystem:
    return run_result.ResolvedSystem(
        system_id=station.system_id,
        name=station.system_name,
        dbname=station.system_name,
        x=station.x,
        y=station.y,
        z=station.z,
    )


def _group_pairs(
    candidates: tuple[run_result.TradeCandidate, ...],
) -> dict[tuple[int, int], tuple[run_result.TradeCandidate, ...]]:
    """Group open-ended candidates by station pair, dropping self-pairs.

    A self-pair (origin station equal to destination station) is never a
    valid trade hop, so it is excluded before cargo optimisation.
    """

    grouped: dict[tuple[int, int], list[run_result.TradeCandidate]] = {}
    for candidate in candidates:
        if candidate.source_station_id == candidate.destination_station_id:
            continue
        key = (candidate.source_station_id, candidate.destination_station_id)
        grouped.setdefault(key, []).append(candidate)
    return {key: tuple(group) for key, group in grouped.items()}


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000.0


def _plan_open_anchor_route(
    session: Session,
    request: RunRequest,
    started: float,
    validation_ms: float,
    resolution_ms: float,
    station_filter_ms: float,
    bubble_cache: dict[int, object],
    *,
    seed_frontier: list[_FrontierNode],
    open_role: str,
) -> run_result.RunResult:
    """Grow a pre-built seed frontier into the best open-ended N-hop route.

    The shared engine for every open-ended multi-hop shape, keyed on
    ``open_role`` — the trade role of the endpoint the planner selects:

      open_role="source"       grow the route backward, asking each layer "who
                               sells into this node?". The emerged origin is the
                               last layer. (--to Y, --from omitted.)
      open_role="destination"  grow the route forward, asking each layer "what
                               can this node sell onward?". The emerged
                               destination is the last layer. (--from X, --to
                               omitted; and the fully-unanchored search, whose
                               seed is a galaxy-wide set of source stations.)

    ``seed_frontier`` is the hop-0 frontier the caller has already built — the
    single-anchor front seeds it from one resolved endpoint's stations; the
    unanchored planner seeds it from the galaxy-wide candidate fetch. From there
    the engine is caller-agnostic: it expands one hop's reach at a time via
    best_open_ended_hop_candidates, beam-trimmed, so no large open-side sphere is
    built up front.

    Expansion is credit-optimistic — cargo is fitted as if money is no object,
    so the beam ranks on an upper-bound profit. Money flows forward (origin to
    destination) whichever way the search ran, so once a chain reaches N hops
    the forward credit-correction pass (_correct_open_anchor_chain) walks it in
    money order and re-fits each hop's cargo against the real running budget. A
    chain is returned only if every hop re-fits; finalists are ranked by their
    *corrected* score.

    Per-station coalescing trims each layer: among chains arriving at the same
    emerged open station only the highest-scoring survives, before the
    frontier-width score trim. Expansion from a station depends only on that
    station, so a lower-scoring chain to it is dominated.

    ``resolution_ms`` and ``station_filter_ms`` are measured by the caller and
    passed through to the diagnostics unchanged (zero resolution and the
    seed-fetch time for the unanchored planner; the anchor resolve and station
    filter times for the single-anchor front).
    """

    base_trade_budget = (
        int(request.starting_credits or 0) - request.insurance_reserve
    )
    optimistic_credits = (
        int(request.capacity_units or 0) * _OPTIMISTIC_PRICE_PER_TON
    )

    frontier: list[_FrontierNode] = seed_frontier

    reachable_memo: dict = {}

    # Run-constant row qualification is answered once per station into
    # run-scoped temps; frontier bubbles overlap heavily, so later anchors
    # reuse earlier anchors' work. Released with the memo below.
    qualification = data_gateway.QualificationCache()

    # Station DTOs are immutable for the run; the cache stops frontier
    # layers re-fetching stations earlier layers already hydrated.
    station_cache: dict[int, run_result.ResolvedStation] = {}

    # --towards: chains that reach the target system are captured here as
    # finished routes. An arrived chain has no closer next hop, so the beam
    # would otherwise discard it; collecting it lets it compete in the final
    # selection, where it wins as the most progress possible.
    towards_target = request.towards_target
    arrivals: list[_FrontierNode] = []

    market_query_ms = 0.0
    candidate_trade_count = 0
    frontier_widths: list[int] = []
    expansions_examined = 0
    layer_stats: list[run_result.LayerStats] = []
    expansion_stats = run_result.ExpansionStats()
    # The open end has no fixed terminal, so the fixed-terminal final-hop
    # accounting does not apply in either direction.
    final_hop_stats: run_result.FinalHopStats | None = None

    try:
        # Intermediate layers 1..N-1: terminal_hop=False requires each emerged
        # open station to stay viable for the next hop (onward demand for an
        # open source, onward supply for an open destination), so a one-sided
        # station cannot hold an intermediate slot.
        for hop_layer in range(1, request.hops):
            layer_started = time.perf_counter()
            layer_frontier_in = len(frontier)
            layer_expansion_calls = 0
            layer_children_generated = 0
            next_frontier: list[_FrontierNode] = []
            for node in frontier:
                expansions_examined += 1
                layer_expansion_calls += 1
                children = best_open_ended_hop_candidates(
                    session,
                    node.station,
                    request,
                    open_role=open_role,
                    optimistic_credits=optimistic_credits,
                    top_k=_MULTIHOP_EXPANSION_WIDTH,
                    terminal_hop=False,
                    bubble_cache=bubble_cache,
                    reachable_memo=reachable_memo,
                    expansion_stats=expansion_stats,
                    station_cache=station_cache,
                    qualification=qualification,
                )
                for trade in children:
                    child = _make_open_child(node, trade, request)
                    candidate_trade_count += 1
                    layer_children_generated += 1
                    if (
                        towards_target is not None
                        and child.station.system_id == towards_target.system_id
                    ):
                        # Arrived: keep it as a finished candidate, but do not
                        # give a dead-end node a frontier slot — it can extend
                        # no further, nothing being closer than the target.
                        arrivals.append(child)
                        continue
                    next_frontier.append(child)
            layer_elapsed_ms = _elapsed_ms(layer_started)
            market_query_ms += layer_elapsed_ms

            if not next_frontier:
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
                # No station extended the chain this layer. The current frontier
                # already holds completed shorter chains; return the best one
                # that survives credit correction as a partial route.
                partial = _best_open_anchor_partial(
                    frontier, request, base_trade_budget, open_role
                )
                if partial is not None:
                    route, completed_hops = partial
                    warning = run_result.PartialRouteWarning(
                        completed_hops=completed_hops,
                        requested_hops=request.hops,
                        phase="expansion",
                        reason="no_viable_continuation",
                    )
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
                        final_hop_stats=final_hop_stats,
                        warning=warning,
                    )
                raise failures.NoProfitableTrades(
                    "No viable continuation was found for the requested "
                    "route length."
                )

            # Per-station coalescing: keep the best optimistic chain per emerged
            # open station, then trim to the frontier width by score.
            best_by_station: dict[int, _FrontierNode] = {}
            for node in next_frontier:
                station_id = node.station.station_id
                existing = best_by_station.get(station_id)
                if (
                    existing is None
                    or node.accumulated_practical_score
                    > existing.accumulated_practical_score
                ):
                    best_by_station[station_id] = node
            coalesced = sorted(
                best_by_station.values(),
                key=lambda candidate: _node_progress_rank(candidate, request),
                reverse=True,
            )
            frontier = coalesced[:_MULTIHOP_FRONTIER_WIDTH]
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

        # Final layer (hop N): reach the open endpoint. terminal_hop=True — the
        # route end needs no onward-viability check. Unlike the forward
        # fixed-terminal final hop, this hands correction several candidates per
        # node, not one: credit-correction can reject a chain whose best
        # optimistic endpoint is unaffordable under the real budget, and a
        # lower-ranked but affordable one from the same node should still be
        # allowed to win. Widening is cheap — best_open_ended_hop_candidates
        # already cargo-scores every grouped pair before the top_k trim, so it
        # adds only jump-path lookups and correction attempts, not expansion
        # cargo calls.
        final_hop_started = time.perf_counter()
        finalist_nodes: list[_FrontierNode] = []
        for node in frontier:
            expansions_examined += 1
            children = best_open_ended_hop_candidates(
                session,
                node.station,
                request,
                open_role=open_role,
                optimistic_credits=optimistic_credits,
                top_k=_MULTIHOP_EXPANSION_WIDTH,
                terminal_hop=True,
                bubble_cache=bubble_cache,
                reachable_memo=reachable_memo,
                expansion_stats=expansion_stats,
                station_cache=station_cache,
                qualification=qualification,
            )
            for trade in children:
                finalist_nodes.append(_make_open_child(node, trade, request))
                candidate_trade_count += 1
        # --towards: chains that reached the target before the final layer are
        # finished routes too. Fold them in so the winner selection ranks them
        # against the full-length finalists; an arrival outranks any route that
        # only got close.
        finalist_nodes.extend(arrivals)
        final_hop_elapsed_ms = _elapsed_ms(final_hop_started)
        market_query_ms += final_hop_elapsed_ms

        # Forward credit-correction: re-fit each finalist's hops against the
        # real running budget and keep those that fully re-fit. Correction can
        # reorder them, so the winner is the highest *corrected* score. The
        # phase is instrumented (its own counters and the cargo-counter delta)
        # because it is a distinct cost centre from expansion.
        correction_stats = run_result.CorrectionStats(
            finalists_generated=len(finalist_nodes)
        )
        correction_started = time.perf_counter()
        correction_fast_before, correction_bb_before = cargo_counters()
        best_route: run_result.PlannedRoute | None = None
        finalist_nodes.sort(
            key=lambda candidate: _node_progress_rank(candidate, request),
            reverse=True,
        )
        for node in finalist_nodes:
            # Exact early-stop: a corrected score never exceeds its optimistic
            # score, so once the best corrected route we hold beats this
            # finalist's optimistic score, no lower-ranked finalist can win.
            # Fires when credits do not bind (corrected ~= optimistic).
            if (
                best_route is not None
                and _node_progress_rank(node, request)
                <= _route_progress_rank(best_route, request)
            ):
                break
            # Correction budget: cap how many finalists are re-fitted. When
            # credits bind the early-stop rarely fires, so this bound is what
            # keeps correction under control.
            if correction_stats.finalists_attempted >= _OPEN_SHAPE_CORRECTION_WIDTH:
                break
            correction_stats.finalists_attempted += 1
            corrected = _correct_open_anchor_chain(
                node, request, base_trade_budget, open_role
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

        if best_route is None:
            # No finalist completed N hops under the real budget. Fall back to
            # the best completed shorter chain that survives correction.
            partial = _best_open_anchor_partial(
                frontier, request, base_trade_budget, open_role
            )
            _finalise_correction_stats(
                correction_stats, correction_started,
                correction_fast_before, correction_bb_before,
            )
            if partial is not None:
                route, completed_hops = partial
                warning = run_result.PartialRouteWarning(
                    completed_hops=completed_hops,
                    requested_hops=request.hops,
                    phase="final",
                    reason="no_viable_trade",
                )
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
                    final_hop_stats=final_hop_stats,
                    correction_stats=correction_stats,
                    warning=warning,
                )
            raise failures.NoProfitableTrades(
                "No viable continuation was found for the requested "
                "route length."
            )

        _finalise_correction_stats(
            correction_stats, correction_started,
            correction_fast_before, correction_bb_before,
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
        final_hop_stats=final_hop_stats,
        correction_stats=correction_stats,
    )


def best_open_ended_hop_candidates(
    session: Session,
    anchor_station: run_result.ResolvedStation,
    request: RunRequest,
    *,
    open_role: str,
    optimistic_credits: int,
    top_k: int,
    terminal_hop: bool,
    bubble_cache: dict[int, object],
    reachable_memo: dict | None = None,
    expansion_stats: run_result.ExpansionStats | None = None,
    station_cache: dict[int, run_result.ResolvedStation] | None = None,
    qualification: data_gateway.QualificationCache | None = None,
    via_steering_xyz: tuple[float, float, float] | None = None,
    via_steering_ly: float | None = None,
    no_affordability: bool = False,
    required_station_ids: frozenset[int] = frozenset(),
    terminal_system_station_ids: frozenset[int] = frozenset(),
) -> list[_HopCandidate]:
    """Return the top-K best optimistic single-hop trades on the open side.

    The direction-neutral per-node expansion primitive for single-anchor open
    multi-hop. ``anchor_station`` is this hop's fixed endpoint; its trade role
    is the opposite of ``open_role``, and the planner picks the open station:

      open_role="source"       backward: who profitably sells INTO the anchor?
                                the anchor is this hop's destination.
      open_role="destination"  forward:  what can the anchor sell onward, and
                                to where? the anchor is this hop's source.

    Cargo is fitted credit-optimistically: ``optimistic_credits`` is far above
    any real buy price, so affordability never binds and the beam ranks chains
    on an upper-bound profit. The real running budget is applied later by the
    forward credit-correction pass. ``terminal_hop=False`` requires the chosen
    open station to stay viable for the next hop (onward demand for an open
    source, onward supply for an open destination); the route-end layer passes
    ``terminal_hop=True``.

    The ls-penalty scores against the hop's destination distance from its
    arrival star — the anchor when it is the destination (open source), the
    chosen station when it is (open destination) — matching forward semantics.

    Jump paths are computed only for the top-K survivors, anchored on the fixed
    endpoint's bubble (one bubble build per node, reused across every
    candidate). For an open source the path comes back destination -> source
    and is reversed to source -> destination flight order; for an open
    destination it is already in flight order. Leg distances are symmetric, so
    the polyline length is unchanged.

    Each returned _HopCandidate carries the chosen open station in
    destination_station and the per-pair TradeCandidate tuple in hop_candidates
    for the forward credit-correction re-fit.

    The via search drives the optional steering and reservation parameters, all
    defaulting off so non-via callers stay byte-identical. ``via_steering_xyz``
    /``via_steering_ly`` (supplied together) narrow the ordinary stream to the
    owed waypoint's neighbourhood and switch ranking to distance-first; the
    score-ceiling early stop is then unsound and is disabled, the same as
    --towards. ``no_affordability`` runs the optimistic pass with no credit cap
    at either seam. ``required_station_ids`` / ``terminal_system_station_ids``
    are fetched directly and reserved past the top-K trim, so a station the
    route must reach is never trimmed away.
    """

    helper_started = time.perf_counter()
    if expansion_stats is not None:
        expansion_stats.expansion_calls += 1

    anchor_system = _system_from_station(anchor_station)

    # Fetch phase starts here: the reachable-set precompute exists to feed the
    # candidate fetch, so its BFS cost is folded into fetch_ms rather than
    # left in the unattributed overhead remainder.
    fetch_started = time.perf_counter()

    # Compute the reachable-systems set in memory from the cKDTree bubble and
    # hand it to the candidate fetch to bulk-insert, instead of the per-anchor
    # SQL spatial BFS. --jumps-per 0 (same-system) needs no reachable set, so
    # the fetch falls back to its same-system path when none is supplied.
    # When the request memo already holds this anchor's temp table the fetch
    # reuses it directly and never reads a precomputed set, so the BFS is
    # skipped rather than computed and thrown away.
    precomputed_reachable = None
    memo_has_table = (
        reachable_memo is not None
        and data_gateway.reachable_memo_contains(
            reachable_memo, anchor_system, request
        )
    )
    if (request.max_jumps_per_hop or 0) >= 1 and not memo_has_table:
        precomputed_reachable = reachable_systems_from(
            session,
            anchor_system,
            max_jumps_per_hop=int(request.max_jumps_per_hop),
            max_ly_per_jump=float(request.max_ly_per_jump or 0.0),
            bubble_cache=bubble_cache,
            avoid_system_ids=request.avoid_system_ids,
        )

    # The BFS precompute above exists to feed the fetch, so its cost lands in
    # fetch_ms; the streaming fetch itself self-accounts from here on.
    if expansion_stats is not None:
        expansion_stats.fetch_ms += _elapsed_ms(fetch_started)

    # The open side is whichever role the planner chooses; the anchor fills
    # the other. Station groups stream in best-ceiling-first, so the kept-
    # score floor rises fast, pairs are solved as their group arrives, and
    # once the next ceiling cannot beat the floor the stream is abandoned —
    # the remaining stations are never read out of the database at all.
    # Pruning, solve order, and the early stop change the work done, never
    # the children chosen. --towards ranks by progress toward the target
    # rather than by score, so the score floor would be meaningless there —
    # the threshold is disabled, nothing stops early, and every pair solves.
    capacity_units = int(request.capacity_units or 0)
    penalty_percent = request.ls_penalty_percent
    anchor_is_destination = open_role == "source"
    # Distance-first steering and --towards both make practical score a
    # non-primary ranking key, so the score-ceiling early stop and the prune
    # floor are unsound: a closer (steering) or more-forward (--towards) but
    # lower-score station could be stopped out before it is ever read. Both
    # disable the threshold; the steering envelope is then the only spatial
    # bound, and the no-affordability solve keeps each kept pair cheap.
    steering = via_steering_xyz is not None
    threshold = _KeptScoreThreshold(
        top_k,
        enabled=request.towards_target is None and not steering,
    )
    # The stop converts the kept-score floor to raw profit at the most
    # permissive destination the stream could still produce: the anchor's
    # own ls when the anchor is the destination (backward), the curve's
    # maximum (ls 0) when the destination varies per station (forward).
    stop_conversion_ls = (
        anchor_station.ls_from_star if anchor_is_destination else 0
    )

    group_iter = data_gateway.iter_open_ended_station_groups(
        session,
        (anchor_station.station_id,),
        anchor_system,
        request,
        open_role=open_role,
        available_credits=optimistic_credits,
        unbounded_credits=no_affordability,
        terminal_hop=terminal_hop,
        reachable_memo=reachable_memo,
        destination_envelope_xyz=via_steering_xyz,
        destination_envelope_ly=via_steering_ly,
        expansion_stats=expansion_stats,
        precomputed_reachable_systems=precomputed_reachable,
        qualification=qualification,
    )

    def _consume_group(
        open_station_id, station_candidates, dest, *, use_threshold,
    ):
        # Build the scored entries for one open station group, exactly as the
        # ordinary stream always has, so the targeted reserved fetch produces
        # byte-identical candidates. use_threshold=False (the reserved fetch)
        # skips the prune floor and the kept-score offer, since a required
        # station must be retained whatever its score.
        hydrate_started = time.perf_counter()
        open_station = data_gateway.fetch_stations_by_id(
            session,
            (open_station_id,),
            cache=station_cache,
        ).get(open_station_id)
        if expansion_stats is not None:
            expansion_stats.fetch_ms += _elapsed_ms(hydrate_started)
            expansion_stats.stream_stations_read += 1
            expansion_stats.candidate_rows += len(station_candidates)
        if open_station is None:
            # An open station that lost its DTO during the fetch — defensive
            # skip rather than a KeyError.
            return
        # ls-penalty rides on the hop's destination: the anchor when the open
        # side is the source, the chosen station when it is the destination.
        destination_distance_ls = (
            anchor_station.ls_from_star
            if anchor_is_destination
            else open_station.ls_from_star
        )
        # A group spans several pairs only when the fixed endpoint has several
        # stations; solve them best-first by the same cheap optimistic key.
        grouped_pairs = _group_pairs(station_candidates)
        if expansion_stats is not None:
            expansion_stats.grouped_pairs += len(grouped_pairs)
        ordered_pairs = sorted(
            grouped_pairs.items(),
            key=lambda item: cargo_order_key(
                item[1],
                destination_distance_ls,
                capacity_units,
                penalty_percent,
            ),
            reverse=True,
        )
        for pair_key, pair_candidates in ordered_pairs:
            if expansion_stats is not None:
                expansion_stats.cargo_calls += 1
            prune_floor = (
                cargo_prune_floor(
                    threshold.current(),
                    destination_distance_ls,
                    penalty_percent,
                )
                if use_threshold
                else None
            )
            cargo_started = time.perf_counter()
            try:
                cargo = optimise_cargo(
                    pair_candidates,
                    capacity_units=capacity_units,
                    available_credits=optimistic_credits,
                    cargo_limit_per_item=request.cargo_limit_per_item,
                    prune_below_raw=prune_floor,
                    ignore_credits=no_affordability,
                )
            except failures.NoProfitableTrades:
                continue
            finally:
                if expansion_stats is not None:
                    expansion_stats.cargo_ms += _elapsed_ms(cargo_started)
            if cargo is None:
                # Pruned: the pair's ceiling cannot beat the kept top-K.
                continue
            practical_score = score_with_destination_penalty(
                cargo.total_profit,
                destination_distance_ls=destination_distance_ls,
                penalty_percent=penalty_percent,
            )
            if use_threshold:
                threshold.offer(practical_score)
            dest.append(
                (
                    practical_score,
                    open_station,
                    cargo,
                    pair_candidates,
                    # Equal-rank tie-break key: the unstreamed fetch ordered
                    # pairs by their best candidate, so the reconstruction is
                    # (best ppu desc, item name) with the pair key keeping it
                    # deterministic.
                    (
                        -pair_candidates[0].profit_per_unit,
                        pair_candidates[0].item_name,
                        pair_key,
                    ),
                )
            )

    def _materialise_hop_candidates(entries, *, cap):
        # Plan each survivor's jump path (anchored on the fixed endpoint so its
        # bubble builds once) and skip the rare unreachable one. cap=None builds
        # every entry — the steering / reserved set is already sized; an int
        # fills up to cap, skipping unreachable, as the ordinary path has.
        built: list[_HopCandidate] = []
        for practical_score, open_station, cargo, pair_candidates, _ in entries:
            if cap is not None and len(built) >= cap:
                break
            open_system = _system_from_station(open_station)
            jump_started = time.perf_counter()
            try:
                # Anchor reachability on the fixed endpoint so its bubble is
                # built once and reused; plan_jump_path returns anchor -> open.
                jump_path = plan_jump_path(
                    anchor_system,
                    open_system,
                    max_jumps_per_hop=int(request.max_jumps_per_hop or 0),
                    max_ly_per_jump=float(request.max_ly_per_jump or 0.0),
                    session=session,
                    bubble_cache=bubble_cache,
                    avoid_system_ids=request.avoid_system_ids,
                )
            except failures.NoReachableRoute:
                # The reachable subquery already filtered to in-range systems,
                # so this is a corner case — fall through to the next candidate.
                continue
            finally:
                if expansion_stats is not None:
                    expansion_stats.jump_ms += _elapsed_ms(jump_started)
            # Store the hop in source -> destination flight order. For an open
            # source the anchor is the destination, so anchor -> open is
            # destination -> source and is reversed; for an open destination it
            # is already source -> destination.
            hop_jump_path = (
                _reverse_jump_path(jump_path)
                if open_role == "source"
                else jump_path
            )
            built.append(
                _HopCandidate(
                    # destination_station carries the chosen OPEN station — the
                    # station the chain reaches at this node.
                    destination_station=open_station,
                    cargo=cargo,
                    jump_path=hop_jump_path,
                    practical_score=practical_score,
                    raw_profit=cargo.total_profit,
                    hop_candidates=pair_candidates,
                )
            )
        return built

    scored: list[
        tuple[
            float,
            run_result.ResolvedStation,
            run_result.CargoPlan,
            tuple[run_result.TradeCandidate, ...],
            tuple,
        ]
    ] = []
    try:
        for open_station_id, ceiling_ppu, station_candidates in group_iter:
            floor = threshold.current()
            if floor is not None:
                stop_floor = cargo_prune_floor(
                    floor, stop_conversion_ls, penalty_percent
                )
                if (
                    stop_floor is not None
                    and capacity_units * ceiling_ppu < stop_floor
                ):
                    # Provable early stop: ceilings are non-increasing and
                    # the floor only rises, so no unread station can place.
                    if expansion_stats is not None:
                        expansion_stats.stream_stops += 1
                    break
            _consume_group(
                open_station_id, station_candidates, scored,
                use_threshold=True,
            )
    finally:
        group_iter.close()

    # Targeted reserved fetch: a station the owner must retain (an owed station
    # via, the exact terminal, the loop root, or a --to system's eligible set)
    # can lose the distance or score trim, so fetch those stations directly
    # under the same rules — no envelope, no early stop, no prune. Same anchor
    # and reachable temp as the ordinary stream, so the reachable set is reused,
    # not rebuilt.
    reserved_pool: list = []
    reserve_ids = required_station_ids | terminal_system_station_ids
    if reserve_ids:
        reserved_iter = data_gateway.iter_open_ended_station_groups(
            session,
            (anchor_station.station_id,),
            anchor_system,
            request,
            open_role=open_role,
            available_credits=optimistic_credits,
            unbounded_credits=no_affordability,
            terminal_hop=terminal_hop,
            reachable_memo=reachable_memo,
            restrict_open_station_ids=frozenset(reserve_ids),
            expansion_stats=expansion_stats,
            precomputed_reachable_systems=precomputed_reachable,
            qualification=qualification,
        )
        try:
            for open_station_id, _ceiling, station_candidates in reserved_iter:
                _consume_group(
                    open_station_id, station_candidates, reserved_pool,
                    use_threshold=False,
                )
        finally:
            reserved_iter.close()

    if not scored and not reserved_pool:
        if expansion_stats is not None:
            expansion_stats.elapsed_ms += _elapsed_ms(helper_started)
        return []

    # Rank the ordinary envelope pool. Steering makes distance the primary key
    # (closest to the owed via first, score breaking ties); otherwise the
    # established progress rank applies, pair key first so equal-rank candidates
    # resolve by best-pair order as the unstreamed fetch's first-appearance
    # order did.
    if steering:
        centre_x, centre_y, centre_z = via_steering_xyz

        def _distance_first_key(item):
            station = item[1]
            distance_sq = (
                (station.x - centre_x) ** 2
                + (station.y - centre_y) ** 2
                + (station.z - centre_z) ** 2
            )
            return (distance_sq, -item[0])

        ordinary_ranked = sorted(scored, key=_distance_first_key)
    else:
        ordinary_ranked = sorted(scored, key=lambda item: item[4])
        ordinary_ranked.sort(
            key=lambda item: _candidate_progress_rank(item, request),
            reverse=True,
        )

    if steering or reserve_ids:
        # Steering / reservation path: take top_k ordinary by rank, hold one
        # slot for the ordinary pool's score leader so a strong trade is not
        # tunnelled past, then union the reserved stations past the cut.
        selected = ordinary_ranked[:top_k]
        if steering and top_k >= 2 and len(ordinary_ranked) > top_k:
            leader_index = max(
                range(len(ordinary_ranked)),
                key=lambda i: ordinary_ranked[i][0],
            )
            if leader_index >= top_k:
                # The score leader missed the distance cut: occupy the lowest
                # distance-ranked slot with it rather than adding a slot.
                selected = (
                    ordinary_ranked[: top_k - 1]
                    + [ordinary_ranked[leader_index]]
                )
        reserved_selected = _select_reserved(
            reserved_pool,
            required_station_ids,
            terminal_system_station_ids,
        )
        selected_keys = {
            (entry[1].station_id, entry[4][2]) for entry in selected
        }
        for entry in reserved_selected:
            key = (entry[1].station_id, entry[4][2])
            if key not in selected_keys:
                selected.append(entry)
                selected_keys.add(key)
        hop_candidates = _materialise_hop_candidates(selected, cap=None)
    else:
        hop_candidates = _materialise_hop_candidates(
            ordinary_ranked, cap=top_k,
        )

    if expansion_stats is not None:
        expansion_stats.children_returned += len(hop_candidates)
        expansion_stats.elapsed_ms += _elapsed_ms(helper_started)
    return hop_candidates


def _reverse_jump_path(path: run_result.JumpPath) -> run_result.JumpPath:
    """Flip a jump path end for end.

    Backward expansion anchors reachability on the fixed frontier node (the
    hop's destination), so plan_jump_path returns the path in
    destination -> source order. The route is flown source -> destination, so
    the stored path is reversed to match. Leg distances are symmetric, so the
    polyline length and jump count are unchanged.
    """

    return run_result.JumpPath(
        source_system_id=path.destination_system_id,
        destination_system_id=path.source_system_id,
        systems=tuple(reversed(path.systems)),
        distance_ly=path.distance_ly,
        jumps=path.jumps,
        is_same_system=path.is_same_system,
        is_reachable=path.is_reachable,
    )


def _select_reserved(
    reserved_pool,
    required_station_ids,
    terminal_system_station_ids,
):
    """Pick the candidates to reserve from the targeted fetch pool.

    Each exact required station — an owed station via, the exact --to station,
    the loop root — reserves its single best-scoring entry. A --to system's
    eligible terminal set reserves only the one best entry across the whole set,
    so a large terminal system cannot inflate the per-node fan-out. Returns the
    chosen scored entries; the caller dedupes them against the ordinary
    selection by (open station, pair).
    """

    best_by_station: dict[int, tuple] = {}
    for entry in reserved_pool:
        station_id = entry[1].station_id
        current = best_by_station.get(station_id)
        if current is None or entry[0] > current[0]:
            best_by_station[station_id] = entry

    selected = []
    for station_id in required_station_ids:
        entry = best_by_station.get(station_id)
        if entry is not None:
            selected.append(entry)

    terminal_best = None
    for station_id in terminal_system_station_ids:
        entry = best_by_station.get(station_id)
        if entry is not None and (
            terminal_best is None or entry[0] > terminal_best[0]
        ):
            terminal_best = entry
    if terminal_best is not None:
        selected.append(terminal_best)

    return selected


def _make_open_child(
    parent: _FrontierNode,
    trade: _HopCandidate,
    request: RunRequest,
) -> _FrontierNode:
    """Extend an open-anchor chain by one hop toward the open endpoint.

    ``trade`` comes from best_open_ended_hop_candidates:
    trade.destination_station is the chosen open-side station, and the trade
    carries the hop in source -> destination flight order (optimistic cargo, the
    jump path, and the per-pair candidates for re-fitting). The child node
    stands at the chosen open station; its parent is the node we expanded.
    Credits are not propagated here — expansion is credit-optimistic and the
    real budget is applied by the forward credit-correction pass.

    The via-satisfaction mask rolls forward: the child adds whatever vias its
    open station stands on to the parent's set. Empty for non-via runs, so the
    field stays an inert marker there.
    """

    new_profit = parent.accumulated_raw_profit + trade.raw_profit
    new_score = parent.accumulated_practical_score + trade.practical_score
    return _FrontierNode(
        station=trade.destination_station,
        parent=parent,
        hop_index=parent.hop_index + 1,
        accumulated_raw_profit=new_profit,
        accumulated_practical_score=new_score,
        available_credits=0,
        hop_cargo=trade.cargo,
        hop_jump_path=trade.jump_path,
        hop_practical_score=trade.practical_score,
        hop_raw_profit=trade.raw_profit,
        hop_candidates=trade.hop_candidates,
        via_satisfied=parent.via_satisfied | _via_satisfied_by(
            trade.destination_station, request,
        ),
    )


def _correct_open_anchor_chain(
    node: _FrontierNode,
    request: RunRequest,
    base_trade_budget: int,
    open_role: str,
) -> run_result.PlannedRoute | None:
    """Re-fit an open-anchor chain forward against the real running budget.

    Money flows origin -> destination whichever way the search ran, so the
    chain is first put in money order, then each hop is re-fitted against the
    running budget (the base trade budget plus the margin-haircut of profit so
    far). open_role decides the orientation:

      open_role="source"       the seed is the fixed destination and the
                               finalist is the emerged origin, so the parent
                               walk already runs origin -> ... -> destination.
                               Each non-seed node carries the hop departing it
                               toward its parent, so node[i] owns hop i.
      open_role="destination"  the seed is the fixed origin and the finalist is
                               the emerged destination, so the parent walk runs
                               destination -> ... -> origin and is reversed.
                               Each non-seed node carries the hop that arrived
                               from its parent, so after reversing node[i + 1]
                               owns hop i.

    If any hop cannot be afforded (optimise_cargo raises NoProfitableTrades) the
    whole chain is rejected and None returned, so a chain is returned only if
    every hop re-fits.
    """

    nodes: list[_FrontierNode] = []
    current: _FrontierNode | None = node
    while current is not None:
        nodes.append(current)
        current = current.parent
    if len(nodes) < 2:
        # Just the seed — no completed hop to render.
        return None

    # Put the chain in money order (origin first) and pick which node owns each
    # hop's candidates / jump path.
    if open_role == "source":
        chain = nodes
        hop_owner_offset = 0
    else:
        chain = list(reversed(nodes))
        hop_owner_offset = 1

    budget = base_trade_budget
    accumulated_profit = 0
    accumulated_score = 0.0
    hops_built: list[run_result.PlannedHop] = []
    for index in range(len(chain) - 1):
        source_node = chain[index]
        destination_node = chain[index + 1]
        hop_node = chain[index + hop_owner_offset]
        if (
            hop_node.hop_candidates is None
            or hop_node.hop_jump_path is None
        ):
            # Defensive: every non-seed node is built from a real trade, so both
            # are populated. A gap would be a build bug, not a user failure.
            return None
        try:
            cargo = optimise_cargo(
                hop_node.hop_candidates,
                capacity_units=int(request.capacity_units or 0),
                available_credits=budget,
                cargo_limit_per_item=request.cargo_limit_per_item,
            )
        except failures.NoProfitableTrades:
            return None
        practical_score = score_with_destination_penalty(
            cargo.total_profit,
            destination_distance_ls=destination_node.station.ls_from_star,
            penalty_percent=request.ls_penalty_percent,
        )
        hops_built.append(
            run_result.PlannedHop(
                source_station=source_node.station,
                destination_station=destination_node.station,
                cargo=cargo,
                raw_profit=cargo.total_profit,
                practical_score=practical_score,
                jump_path=hop_node.hop_jump_path,
            )
        )
        accumulated_profit += cargo.total_profit
        accumulated_score += practical_score
        budget = base_trade_budget + int(
            (1.0 - request.margin) * accumulated_profit
        )

    stations = tuple(chain_node.station for chain_node in chain)
    starting_credits = int(request.starting_credits or 0)
    return run_result.PlannedRoute(
        stations=stations,
        hops=tuple(hops_built),
        total_raw_profit=accumulated_profit,
        total_practical_score=accumulated_score,
        starting_credits=starting_credits,
        ending_credits=starting_credits + accumulated_profit,
    )


def _best_open_anchor_partial(
    frontier: list[_FrontierNode],
    request: RunRequest,
    base_trade_budget: int,
    open_role: str,
) -> tuple[run_result.PlannedRoute, int] | None:
    """Return the best completed shorter chain that survives credit correction.

    The open-anchor mirror of _best_partial_node, with the forward credit-
    correction pass applied. Credit correction can reorder chains — a lower
    optimistic chain may re-fit better than a higher one — so every completed
    frontier node (hop_index > 0) is corrected and the one with the highest
    *corrected* practical score is returned with its hop count, matching how the
    finalist path chooses its winner. None if no completed node survives.
    """

    best_route: run_result.PlannedRoute | None = None
    best_hops = 0
    for node in frontier:
        if node.hop_index <= 0:
            continue
        route = _correct_open_anchor_chain(
            node, request, base_trade_budget, open_role
        )
        if route is None:
            continue
        if (
            best_route is None
            or _route_progress_rank(route, request)
            > _route_progress_rank(best_route, request)
        ):
            best_route = route
            best_hops = node.hop_index
    if best_route is None:
        return None
    return best_route, best_hops


def _finalise_correction_stats(
    stats: run_result.CorrectionStats,
    started: float,
    fast_before: int,
    bb_before: int,
) -> None:
    """Fill the cargo split and elapsed time on a CorrectionStats.

    The fast/branch-and-bound split is the global cargo-counter delta across the
    correction phase, so it isolates correction's optimise_cargo work from the
    expansion work that ran before it.
    """

    fast_after, bb_after = cargo_counters()
    stats.fast_path_hits = fast_after - fast_before
    stats.branch_and_bound_hits = bb_after - bb_before
    stats.cargo_calls = stats.fast_path_hits + stats.branch_and_bound_hits
    stats.elapsed_ms = _elapsed_ms(started)


# Open-ended expansion ranks chains on an upper-bound,
# credit-optimistic profit; the real running budget is applied later by the
# forward credit-correction pass. To make the optimistic cargo fit ignore
# affordability, each open-side fetch/optimise is handed a per-ton budget far
# above any real or carrier-inflated buy price, scaled by capacity so the
# credit cap never binds. 1 billion cr/ton is an unreachable ceiling — the
# dearest buy price observed in the live data is around 60M cr/ton.
_OPTIMISTIC_PRICE_PER_TON = 1_000_000_000


# How many candidate routes the planner fully costs out before picking the
# winner, when one endpoint is left open (no --from, or no --to).
#
# In an open run the planner searches outward from the fixed endpoint and can
# end up with thousands of complete candidate routes (the code calls them
# "finalists"). To choose between them it has to re-do each route's cargo, hop
# by hop, against your *real* running money — during the search it pretends
# money is unlimited so the search itself stays fast. That re-costing is the
# slow part, and doing it for thousands of routes was what made these runs take
# minutes. So we only re-cost the best 200, ranked by the search's rough score.
#
# 200 is a tuning knob, not a magic number: higher is safer (less chance of
# skipping the real winner) but slower, lower is faster but riskier. ~200 keeps
# the re-costing to a few tens of seconds in the slowest case we measured. The
# early-stop just below also quits sooner, for free, whenever it can prove the
# remaining routes can't win; this cap is what keeps things bounded in the case
# where money is tight and that shortcut can't help.
_OPEN_SHAPE_CORRECTION_WIDTH = 200
