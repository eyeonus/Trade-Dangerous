"""Part-anchored multi-hop planning (one open end), credit-optimistic expansion with a forward correction pass."""

from __future__ import annotations

import time

from sqlalchemy.orm import Session

from . import data_gateway, failures, resolver, run_result
from .cargo import cargo_counters, optimise_cargo
from .reachability import plan_jump_path
from .run_request import RunRequest
from .score import score_with_destination_penalty

from .route_common import (
    _FrontierNode,
    _HopCandidate,
    _MULTIHOP_EXPANSION_WIDTH,
    _MULTIHOP_FRONTIER_WIDTH,
    _elapsed_ms,
    _group_pairs,
    _multihop_result,
    _stations_from_endpoint,
    _system_from_station,
)


def _plan_open_anchor_multi_hop(
    session: Session,
    request: RunRequest,
    started: float,
    validation_ms: float,
    bubble_cache: dict[int, object],
    *,
    open_role: str,
) -> run_result.RunResult:
    """Plan an N-hop route with one fixed endpoint and the other open.

    The single engine for both single-anchor open multi-hop shapes, keyed on
    ``open_role`` — the trade role of the endpoint the planner selects:

      open_role="source"       --to Y, --from omitted: grow the route backward
                               from Y, asking each layer "who sells into this
                               node?". The emerged origin is the last layer.
      open_role="destination"  --from X, --to omitted: grow the route forward
                               from X, asking each layer "what can this node
                               sell onward?". The emerged destination is last.

    Either way the search seeds on the fixed endpoint's eligible stations and
    expands one hop's reach at a time via best_open_ended_hop_candidates,
    beam-trimmed, so no large open-side sphere is built up front.

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
    """

    # The fixed endpoint (the seed) is the one the user supplied; its trade role
    # is the opposite of open_role. open_role="source" anchors on --to as the
    # destination; open_role="destination" anchors on --from as the source.
    if open_role == "source":
        anchor_text = request.to_text
        anchor_option = "--to"
        anchor_role = "destination"
    else:
        anchor_text = request.from_text
        anchor_option = "--from"
        anchor_role = "source"

    resolution_started = time.perf_counter()
    anchor_endpoint = resolver.resolve_endpoint(
        session,
        str(anchor_text),
        option_name=anchor_option,
    )
    resolution_ms = _elapsed_ms(resolution_started)

    station_filter_started = time.perf_counter()
    anchor_stations = _stations_from_endpoint(
        session,
        anchor_endpoint,
        request,
        role=anchor_role,
    )
    station_filter_ms = _elapsed_ms(station_filter_started)

    base_trade_budget = (
        int(request.starting_credits or 0) - request.insurance_reserve
    )
    optimistic_credits = (
        int(request.capacity_units or 0) * _OPTIMISTIC_PRICE_PER_TON
    )

    # Seed: the fixed endpoint's eligible stations at hop_index 0, no cargo.
    frontier: list[_FrontierNode] = [
        _FrontierNode(
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
        )
        for station in anchor_stations
    ]

    reachable_memo: dict = {}

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
                )
                for trade in children:
                    next_frontier.append(_make_open_child(node, trade))
                    candidate_trade_count += 1
                    layer_children_generated += 1
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
                key=lambda candidate: candidate.accumulated_practical_score,
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
            )
            for trade in children:
                finalist_nodes.append(_make_open_child(node, trade))
                candidate_trade_count += 1
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
            key=lambda candidate: candidate.accumulated_practical_score,
            reverse=True,
        )
        for node in finalist_nodes:
            # Exact early-stop: a corrected score never exceeds its optimistic
            # score, so once the best corrected route we hold beats this
            # finalist's optimistic score, no lower-ranked finalist can win.
            # Fires when credits do not bind (corrected ~= optimistic).
            if (
                best_route is not None
                and node.accumulated_practical_score
                <= best_route.total_practical_score
            ):
                break
            # Correction budget: cap how many finalists are re-fitted. When
            # credits bind the early-stop rarely fires, so this bound is what
            # keeps correction under control.
            if correction_stats.finalists_attempted >= _OPEN_ORIGIN_CORRECTION_WIDTH:
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
                or corrected.total_practical_score
                > best_route.total_practical_score
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
    """

    helper_started = time.perf_counter()
    if expansion_stats is not None:
        expansion_stats.expansion_calls += 1

    anchor_system = _system_from_station(anchor_station)

    candidates = data_gateway.fetch_open_ended_trade_candidates(
        session,
        (anchor_station.station_id,),
        anchor_system,
        request,
        open_role=open_role,
        available_credits=optimistic_credits,
        terminal_hop=terminal_hop,
        reachable_memo=reachable_memo,
        expansion_stats=expansion_stats,
    )
    if expansion_stats is not None:
        expansion_stats.candidate_rows += len(candidates)
    if not candidates:
        if expansion_stats is not None:
            expansion_stats.elapsed_ms += _elapsed_ms(helper_started)
        return []

    # The open side is whichever role the planner chooses; the anchor fills the
    # other. Group on the open station and materialise only those DTOs.
    if open_role == "source":
        open_station_ids = tuple(
            {candidate.source_station_id for candidate in candidates}
        )
    else:
        open_station_ids = tuple(
            {candidate.destination_station_id for candidate in candidates}
        )
    open_stations = data_gateway.fetch_stations_by_id(
        session,
        open_station_ids,
    )

    grouped_pairs = _group_pairs(candidates)
    if expansion_stats is not None:
        expansion_stats.grouped_pairs += len(grouped_pairs)

    # Score every viable pair first; defer the jump-path computation until
    # after the top-K trim so we only pay it for survivors. The anchor is
    # fixed, so _group_pairs keys differ only by the open station.
    scored: list[
        tuple[
            float,
            run_result.ResolvedStation,
            run_result.CargoPlan,
            tuple[run_result.TradeCandidate, ...],
        ]
    ] = []
    for (source_id, destination_id), pair_candidates in grouped_pairs.items():
        open_id = source_id if open_role == "source" else destination_id
        open_station = open_stations.get(open_id)
        if open_station is None:
            # An open station that lost its DTO during the fetch — defensive
            # skip rather than a KeyError, mirroring the forward helper.
            continue
        if expansion_stats is not None:
            expansion_stats.cargo_calls += 1
        try:
            cargo = optimise_cargo(
                pair_candidates,
                capacity_units=int(request.capacity_units or 0),
                available_credits=optimistic_credits,
                cargo_limit_per_item=request.cargo_limit_per_item,
            )
        except failures.NoProfitableTrades:
            continue
        # ls-penalty rides on the hop's destination: the anchor when the open
        # side is the source, the chosen station when it is the destination.
        destination_distance_ls = (
            anchor_station.ls_from_star
            if open_role == "source"
            else open_station.ls_from_star
        )
        practical_score = score_with_destination_penalty(
            cargo.total_profit,
            destination_distance_ls=destination_distance_ls,
            penalty_percent=request.ls_penalty_percent,
        )
        scored.append((practical_score, open_station, cargo, pair_candidates))

    scored.sort(key=lambda item: item[0], reverse=True)

    hop_candidates: list[_HopCandidate] = []
    for practical_score, open_station, cargo, pair_candidates in scored:
        if len(hop_candidates) >= top_k:
            break
        open_system = _system_from_station(open_station)
        try:
            # Anchor reachability on the fixed endpoint so its bubble is built
            # once and reused across every candidate; plan_jump_path returns
            # the path anchor -> open.
            jump_path = plan_jump_path(
                anchor_system,
                open_system,
                max_jumps_per_hop=int(request.max_jumps_per_hop or 0),
                max_ly_per_jump=float(request.max_ly_per_jump or 0.0),
                session=session,
                bubble_cache=bubble_cache,
            )
        except failures.NoReachableRoute:
            # The reachable subquery already filtered to in-range systems, so
            # this is a corner case — fall through to the next-best candidate.
            continue
        # Store the hop in source -> destination flight order. For an open
        # source the anchor is the destination, so anchor -> open is
        # destination -> source and is reversed; for an open destination
        # anchor -> open is already source -> destination.
        hop_jump_path = (
            _reverse_jump_path(jump_path)
            if open_role == "source"
            else jump_path
        )
        hop_candidates.append(
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


def _make_open_child(
    parent: _FrontierNode,
    trade: _HopCandidate,
) -> _FrontierNode:
    """Extend an open-anchor chain by one hop toward the open endpoint.

    ``trade`` comes from best_open_ended_hop_candidates:
    trade.destination_station is the chosen open-side station, and the trade
    carries the hop in source -> destination flight order (optimistic cargo, the
    jump path, and the per-pair candidates for re-fitting). The child node
    stands at the chosen open station; its parent is the node we expanded.
    Credits are not propagated here — expansion is credit-optimistic and the
    real budget is applied by the forward credit-correction pass.
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
            or route.total_practical_score > best_route.total_practical_score
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


# Open-origin (backward) expansion ranks chains on an upper-bound,
# credit-optimistic profit; the real running budget is applied later by the
# forward credit-correction pass. To make the optimistic cargo fit ignore
# affordability, each backward fetch/optimise is handed a per-ton budget far
# above any real or carrier-inflated buy price, scaled by capacity so the
# credit cap never binds. 1 billion cr/ton is an unreachable ceiling — the
# dearest buy price observed in the live data is around 60M cr/ton.
_OPTIMISTIC_PRICE_PER_TON = 1_000_000_000


# How many candidate routes the planner fully costs out before picking the
# winner, when only a destination is given (no --from).
#
# In that mode the planner searches backwards from the destination and can end
# up with thousands of complete candidate routes (the code calls them
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
_OPEN_ORIGIN_CORRECTION_WIDTH = 200
