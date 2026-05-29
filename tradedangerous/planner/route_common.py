"""Shared multi-hop frontier machinery and generic planner helpers."""

from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from . import data_gateway, failures, resolver, run_result
from .cargo import cargo_counters
from .run_request import RunRequest


@dataclass(frozen=True, slots=True)
class _FrontierNode:
    """A partial route ending at one station after K trade hops.

    Multi-hop search builds a layered frontier: each layer is the set of
    nodes ending at hop K, ranked and trimmed by accumulated practical
    score. A node carries the cargo and jump path of the hop that brought
    it here so the surviving winner can walk its parent chain back to the
    origin and emit a full route. available_credits is the post-margin
    budget for the next hop's buy.

    The open-origin (backward) search reuses this struct but grows the chain
    from the destination toward the origin. There available_credits is unused
    (backward expansion is credit-optimistic; the real budget is applied by the
    forward credit-correction pass), and hop_candidates is populated so that
    pass can re-fit each hop.
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
    # Open-origin (backward) expansion only: the per-pair TradeCandidate tuple
    # for the hop that arrived at this node, kept so the forward credit-
    # correction pass can re-fit cargo against the real running budget. None on
    # the forward path.
    hop_candidates: tuple[run_result.TradeCandidate, ...] | None = None


@dataclass(frozen=True, slots=True)
class _HopCandidate:
    """One viable forward trade from a known source station.

    Multi-hop expansion calls best_open_ended_trades_from once per frontier
    node; that helper returns the per-node top-K candidates as _HopCandidate
    rows. The frontier loop turns each into a child node by attaching the
    parent and accumulating profit/score and the post-hop credit budget.

    Open-origin (backward) expansion reuses this struct via
    best_open_ended_hop_candidates. There destination_station carries the
    chosen *source* — the station the route reaches when the chain is walked
    backward from a node — and hop_candidates is populated so the forward
    credit-correction pass can re-fit cargo against the real budget.
    """

    destination_station: run_result.ResolvedStation
    cargo: run_result.CargoPlan
    jump_path: run_result.JumpPath
    practical_score: float
    raw_profit: int
    # Open-origin (backward) expansion only: the per-pair TradeCandidate tuple
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
    """

    if endpoint.station is not None:
        data_gateway.validate_station_filters(endpoint.station, request, role=role)
        return (endpoint.station,)

    if endpoint.system is None:
        raise failures.UnknownPlace(
            f"{endpoint.option_name} could not be resolved.",
            option_name=endpoint.option_name,
            entity_name=endpoint.original_text,
        )

    stations = data_gateway.fetch_eligible_stations_in_system(
        session,
        endpoint.system,
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
    raise failure_type(
        f"{endpoint.option_name} system has no eligible {role} stations.",
        option_name=endpoint.option_name,
        entity_name=endpoint.original_text,
    )


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
