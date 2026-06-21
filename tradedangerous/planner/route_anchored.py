"""Fully-anchored multi-hop planning (--from X --to Y), grown toward a fixed destination."""

from __future__ import annotations

import time
from dataclasses import replace

from sqlalchemy.orm import Session

from . import data_gateway, failures, run_result
from .cargo import optimise_cargo
from .reachability import plan_jump_path, reachable_systems_from
from .run_request import RunRequest
from .score import score_with_destination_penalty
from ..misc import progress as pbar

from .route_common import (
    _FrontierNode,
    _HopCandidate,
    _KeptScoreThreshold,
    _MULTIHOP_EXPANSION_WIDTH,
    _MULTIHOP_FRONTIER_WIDTH,
    _best_partial_node,
    _elapsed_ms,
    _group_pairs,
    _make_child_node,
    _multihop_result,
    _no_revisit_route_failure,
    _reconstruct_route,
    _revisit_active,
    _revisit_forbidden,
    _revisit_key,
    _revisit_seed,
    _root_node,
    _stations_from_endpoint,
    _system_from_station,
    _terminal_envelope_centre,
    batched_seed_hop_candidates,
    cargo_prune_floor,
)


def _plan_multi_hop(
    session: Session,
    request: RunRequest,
    started: float,
    validation_ms: float,
    bubble_cache: dict[int, object],
    progress: pbar.Progress | None = None,
    positioning_caches: dict[str, dict] | None = None,
) -> run_result.RunResult:
    """Plan an N-hop route between a named --from origin and --to destination.

    The fixed-terminal multi-hop planner: both endpoints are supplied, so the
    search grows forward from the origin and must end at one of Y's eligible
    stations. (Open-ended multi-hop — one endpoint omitted — runs on the
    single-anchor engine instead; see plan_route's dispatch.)

    --loop runs here too: it carries no --to, the destination side is the
    origin endpoint's destination-eligible view, and each chain must close
    on its own root station. Partial routes are suppressed for loops — an
    unclosed loop is not a loop, so those sites raise NoLoopRoute instead.

    Beam frontier search: each hop layer keeps a bounded set of best-scoring
    partial routes; each surviving partial expands into the next layer via
    best_open_ended_trades_from, the combined layer is rescored, and the layer
    is trimmed back to _MULTIHOP_FRONTIER_WIDTH with at most one node per
    destination system (so near-duplicate clusters do not crowd the beam).

    To keep the frontier pointed at Y rather than wandering, each intermediate
    layer's candidate fetch is restricted in SQL to destination systems within
    ``remaining_hops * --jumps-per * --ly-per`` of Y — out-of-envelope systems
    never leave the database into Python. The final hop runs a per-frontier-node
    fixed-pair evaluation against Y's stations; the graph reach check still
    gates which destinations are actually reachable, the envelope is only a
    necessary feasibility filter.

    Credits propagate hop-to-hop. available_credits at hop K+1 is
    ``base_trade_budget + floor((1 - margin) * accumulated_raw_profit)`` —
    integer-only, so cargo fitting never sees a float. The renderer reports raw
    accumulated profit and the final raw credits; margin only changes what the
    planner is willing to *spend* on a later hop's buy.
    """

    # A disabled bar stands in when the caller passes none, so every tick below
    # is a safe no-op off the --progress path.
    if progress is None:
        progress = pbar.Progress(show=False)

    # Endpoints were resolved once at dispatch; read the canonical DTOs.
    # --loop carries no --to: each chain must close on its own root station, so
    # every root has to be a genuine destination as well as a source (the
    # terminal rule is applied per node at the final hop below).
    loop_mode = request.loop
    origin_endpoint = request.from_endpoint
    resolution_ms = 0.0

    def _loop_failure() -> failures.NoLoopRoute:
        label = origin_endpoint.original_text
        return failures.NoLoopRoute(
            f"No route closed the loop back to {label} within "
            f"{request.hops} hops under the supplied constraints.",
            option_name="--loop",
            entity_name=label,
        )

    station_filter_started = time.perf_counter()
    origin_stations = _stations_from_endpoint(
        session,
        origin_endpoint,
        request,
        role="source",
        positioning_caches=positioning_caches,
    )
    destination_by_id: dict[int, run_result.ResolvedStation] = {}
    if loop_mode:
        # A loop returns to where it started, so each root must be a valid
        # *destination*, not merely a source. Two things disqualify a root, and
        # both must be settled before the bounded (width-50) frontier is seeded
        # so an unclosable root never crowds out one that could close:
        #
        #  1. Avoidance. The explicit-origin exemption lets the commander START
        #     in an avoided place, but the loop's return is a later visit, so an
        #     avoided station or system cannot be the terminal. Tested against
        #     the original avoid sets (not the origin carve-out the source fetch
        #     applies), so an avoided --from still cannot be returned to.
        #  2. Usable demand. A root with no demand good enough to sell into can
        #     never close. fetch_loop_closable_station_ids answers this with the
        #     same row rules the final-hop destination uses (avoided commodities
        #     and the bulk-sale-tax effective-demand floor included).
        roots = tuple(
            station for station in origin_stations
            if station.station_id not in request.avoid_station_ids
            and station.system_id not in request.avoid_system_ids
        )
        demand_qualified = data_gateway.fetch_loop_closable_station_ids(
            session,
            tuple(station.station_id for station in roots),
            request,
        )
        origin_stations = tuple(
            station for station in roots
            if station.station_id in demand_qualified
        )
        if not origin_stations:
            raise failures.NoLoopRoute(
                f"No station at {origin_endpoint.original_text} is eligible "
                "as both the start and the end of a loop under the supplied "
                "constraints.",
                option_name="--loop",
                entity_name=origin_endpoint.original_text,
            )
        # Each surviving root is its own terminal; no separate destination
        # expansion. The envelope anchor varies per chain root in loop mode and
        # is set per node in the expansion loop below.
        destination_by_id = {
            station.station_id: station for station in origin_stations
        }
        to_system_xyz = None
        terminal_spread_ly = 0.0
    else:
        destination_endpoint = request.to_endpoint
        destination_stations = _stations_from_endpoint(
            session,
            destination_endpoint,
            request,
            role="destination",
            positioning_caches=positioning_caches,
        )
        # With --end-jumps the eligible terminals span many systems out to
        # end_jumps empty jumps of the anchor, not one --to system. Centre the
        # closing envelope on the terminal region and widen it by the region's
        # spread, so the bound admits every expanded terminal, not only the
        # first. Without --end-jumps there is one terminal system, the spread is
        # zero, and the envelope is exactly as before.
        to_system_xyz, terminal_spread_ly = _terminal_envelope_centre(
            destination_stations
        )
    station_filter_ms = _elapsed_ms(station_filter_started)

    base_trade_budget = (
        int(request.starting_credits or 0) - request.insurance_reserve
    )

    frontier: list[_FrontierNode] = [
        _FrontierNode(
            station=station,
            parent=None,
            hop_index=0,
            accumulated_raw_profit=0,
            accumulated_practical_score=0.0,
            available_credits=base_trade_budget,
            hop_cargo=None,
            hop_jump_path=None,
            hop_practical_score=0.0,
            hop_raw_profit=0,
            visited_order=_revisit_seed(station.station_id, request),
        )
        for station in origin_stations
    ]

    # Reachability temp tables stay alive across calls so the per-source
    # build cost (the dominant fraction of fetch time) is paid
    # once per (source_system, jumps_per, ly_per) key for the whole run.
    # Released in the finally below so a partial run does not leak tables.
    reachable_memo: dict = {}

    # Run-constant row qualification is answered once per station into
    # run-scoped temps; frontier bubbles overlap heavily, so later anchors
    # reuse earlier anchors' work. Released with the memo below.
    qualification = data_gateway.QualificationCache()

    # Station DTOs are immutable for the run; the cache stops frontier
    # layers re-fetching stations earlier layers already hydrated.
    station_cache: dict[int, run_result.ResolvedStation] = {}

    market_query_ms = 0.0
    candidate_trade_count = 0
    frontier_widths: list[int] = []
    expansions_examined = 0
    layer_stats: list[run_result.LayerStats] = []
    expansion_stats = run_result.ExpansionStats()
    final_hop_stats = run_result.FinalHopStats()

    try:
        # The farthest a single hop can move the ship — the radius of the
        # reach bubble the candidate fetch grows from any anchor. A layer
        # envelope wider than an anchor's whole bubble cannot exclude
        # anything that anchor reaches, and is dropped per call below.
        bubble_reach_ly = (
            int(request.max_jumps_per_hop or 0)
            * float(request.max_ly_per_jump or 0.0)
        )

        # Intermediate hops 1..N-1: terminal_hop=False keeps demand-only
        # destinations off the frontier so they cannot occupy a node that
        # must be a viable onward source.
        for hop_layer in range(1, request.hops):
            # The destinations of this layer's expansion must land within
            # remaining_hops * jumps_per * ly_per of --to so the remaining hops
            # can plausibly close on it. The envelope is pushed into the
            # candidate fetch so out-of-envelope systems never reach Python —
            # the demand-side reachable subquery is narrowed against the temp
            # table's pos columns.
            remaining_hops = request.hops - hop_layer
            envelope_ly = float(
                remaining_hops
                * int(request.max_jumps_per_hop or 0)
                * float(request.max_ly_per_jump or 0.0)
            )

            layer_started = time.perf_counter()
            layer_frontier_in = len(frontier)
            layer_expansion_calls = 0
            layer_children_generated = 0
            next_frontier: list[_FrontierNode] = []
            revisit_skips_before = expansion_stats.revisit_skips
            node_task = progress.open_subtask(
                f"  hop {hop_layer}: expanding stations", layer_frontier_in
            )
            seed_results: dict[int, list] = {}
            batched_seed_layer = hop_layer == 1 and not loop_mode
            if batched_seed_layer:
                # Seed layer (hop zero): the expanded --from origins share one
                # reachable market per system, demultiplexed per seed — one
                # batched expansion per system, not one per seed. The closing
                # envelope is the same for every seed at this layer (centred on
                # the --to region), applied uniformly without the per-node
                # loose-drop, which only ever removes a redundant filter, so the
                # candidate set is unchanged. (--loop forbids --start-jumps, so a
                # loop seed layer is never expanded and keeps the per-node path.)
                seed_results = batched_seed_hop_candidates(
                    session,
                    tuple(node.station for node in frontier),
                    request,
                    open_role="destination",
                    budget_credits=base_trade_budget,
                    ignore_credits=False,
                    top_k=_MULTIHOP_EXPANSION_WIDTH,
                    terminal_hop=False,
                    bubble_cache=bubble_cache,
                    retain_correction=False,
                    reachable_memo=reachable_memo,
                    station_cache=station_cache,
                    qualification=qualification,
                    forbidden_by_seed={
                        node.station.station_id: _revisit_forbidden(
                            node, request, backward=False,
                        )
                        for node in frontier
                    },
                    destination_envelope_xyz=to_system_xyz,
                    destination_envelope_ly=envelope_ly + terminal_spread_ly,
                    expansion_stats=expansion_stats,
                )
                layer_expansion_calls = len(
                    {node.station.system_id for node in frontier}
                )
            for node in frontier:
                progress.update_task(node_task, advance=1)
                expansions_examined += 1
                if batched_seed_layer:
                    children = seed_results.get(node.station.station_id, [])
                else:
                    layer_expansion_calls += 1
                    # Pick this node's envelope anchor and radius, then run the
                    # shared loose-drop check on it.
                    if loop_mode:
                        # The remaining hops must close on this chain's own root
                        # station (same geometry legacy used — distance home
                        # against remaining range).
                        root_station = _root_node(node).station
                        anchor_xyz = (
                            root_station.x, root_station.y, root_station.z,
                        )
                        anchor_ly = envelope_ly
                    else:
                        # The remaining hops must close on some eligible terminal
                        # in the --to region; the envelope is widened by the
                        # region's spread so every expanded terminal stays
                        # admissible (no --end-jumps -> spread zero -> unchanged).
                        anchor_xyz = to_system_xyz
                        anchor_ly = envelope_ly + terminal_spread_ly
                    # An envelope that provably contains this anchor's whole reach
                    # bubble excludes nothing — drop it for the call, so the fetch
                    # keeps the qualification skip-marker and plain reachable SQL
                    # its presence would otherwise disable. The result set is
                    # identical by construction.
                    if _envelope_is_provably_loose(
                        node.station, anchor_xyz, anchor_ly, bubble_reach_ly,
                    ):
                        node_envelope_xyz = None
                        node_envelope_ly = None
                        expansion_stats.loose_envelopes_dropped += 1
                    else:
                        node_envelope_xyz = anchor_xyz
                        node_envelope_ly = anchor_ly
                    children = best_open_ended_trades_from(
                        session,
                        node.station,
                        request,
                        available_credits=node.available_credits,
                        top_k=_MULTIHOP_EXPANSION_WIDTH,
                        terminal_hop=False,
                        bubble_cache=bubble_cache,
                        reachable_memo=reachable_memo,
                        destination_envelope_xyz=node_envelope_xyz,
                        destination_envelope_ly=node_envelope_ly,
                        expansion_stats=expansion_stats,
                        station_cache=station_cache,
                        qualification=qualification,
                        forbidden_station_ids=_revisit_forbidden(
                            node, request, backward=False,
                        ),
                    )
                for trade in children:
                    next_frontier.append(
                        _make_child_node(node, trade, request, base_trade_budget)
                    )
                    candidate_trade_count += 1
                    layer_children_generated += 1
            progress.close_subtask(node_task)
            layer_elapsed_ms = _elapsed_ms(layer_started)
            market_query_ms += layer_elapsed_ms

            if not next_frontier:
                # Record the collapsed layer as well as successful layers.
                # Partial-route diagnostics should show where the search got
                # stuck, not merely the last layer that produced survivors.
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
                
                # An unclosed loop is not a loop — no partial fallback for
                # this shape, whatever the frontier holds.
                if loop_mode:
                    raise _loop_failure()
                # A revisit rule emptied this layer — candidates existed but the
                # rule forbade every continuation: the spec's "unique route
                # impossible" case. Fail clearly rather than fall back to a
                # shorter partial that ignores the requested length.
                if _revisit_active(request) and expansion_stats.revisit_skips > revisit_skips_before:
                    raise _no_revisit_route_failure(request)
                # No child survived this expansion layer. On the first layer
                # that means no trade hop was ever completed, so this is still
                # the normal no-result failure. On later layers, the current
                # frontier already represents useful completed hops; return the
                # best partial route with a structured warning instead of
                # discarding that work through PlannerResultError.
                partial = _best_partial_node(frontier)
                if partial is not None:
                    route = _reconstruct_route(partial, request)
                    warning = run_result.PartialRouteWarning(
                        completed_hops=partial.hop_index,
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

            # Keep at most one node per destination system after the score
            # sort. Without this, frontier slots get spent on near-duplicates —
            # several stations in the same destination system, all with similar
            # per-hop profit — crowding out strategically valuable but
            # lower-scoring alternatives at other systems.
            next_frontier.sort(
                key=lambda candidate: candidate.accumulated_practical_score,
                reverse=True,
            )
            # Loop chains with different roots carry different compulsory
            # terminals, so they are not near-duplicates of each other —
            # dedupe them per (root, system), exactly as chains aimed at
            # different --to anchors would deserve their own slots. Without
            # it a system --from's dominant origin starves every other
            # origin's chains out of the beam.
            revisit_on = _revisit_active(request)
            seen_keys: set = set()
            deduped: list[_FrontierNode] = []
            for node in next_frontier:
                if loop_mode:
                    key = (
                        _root_node(node).station.station_id,
                        node.station.system_id,
                    )
                else:
                    key = node.station.system_id
                if revisit_on:
                    # Two chains at one system with different visited histories
                    # are different states under --unique / --loop-interval: one
                    # may still finish the route where the other cannot. Keep
                    # them distinct so the per-system dedupe cannot drop the only
                    # chain that can complete.
                    key = (key, _revisit_key(node, request, backward=False))
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                deduped.append(node)
                if len(deduped) >= _MULTIHOP_FRONTIER_WIDTH:
                    break
            frontier = deduped
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
            # One spine step per completed hop layer. The M/N column shows the
            # layer count; the description carries the best partial profit so
            # far (frontier is score-sorted, so [0] is the current leader).
            best_profit = frontier[0].accumulated_raw_profit if frontier else 0
            progress.increment(
                1,
                description=f"Planning route  ·  best +{best_profit:,} cr",
            )

        # Final hop: each surviving frontier node is matched against Y's
        # stations as a fixed-pair plan. The destination is the fixed --to, so
        # there is no onward-viability check to apply.
        final_hop_started = time.perf_counter()
        finalists: list[_FrontierNode] = []
        final_revisit_skips_before = expansion_stats.revisit_skips
        final_node_task = progress.open_subtask(
            "  final hop: matching destinations", len(frontier)
        )
        # The fixed --to terminal set is shared across every frontier source, so
        # its restriction is built once and reused across all node-streams. The
        # per-root loop terminal has no shared set (each node closes on its own
        # root), so loops keep the per-pair final hop — one destination per node,
        # no source x destination blow-up to remove.
        terminal_temp = None
        terminal_restriction_kwargs: dict = {}
        terminal_by_id: dict = {}
        terminal_system_ids: frozenset = frozenset()
        if not loop_mode:
            terminal_by_id = {
                station.station_id: station
                for station in destination_stations
            }
            terminal_system_ids = frozenset(
                station.system_id for station in destination_stations
            )
            terminal_temp, terminal_restriction_kwargs = (
                data_gateway.build_open_restriction(
                    session.connection(), frozenset(terminal_by_id)
                )
            )
        try:
            for node in frontier:
                progress.update_task(final_node_task, advance=1)
                expansions_examined += 1
                forbidden = _revisit_forbidden(node, request, backward=False)
                if loop_mode:
                    # The terminal rule: each chain closes on its own root.
                    root_station = _root_node(node).station
                    trades = best_fixed_pair_trades_from(
                        session,
                        node.station,
                        (destination_by_id[root_station.station_id],),
                        request,
                        available_credits=node.available_credits,
                        bubble_cache=bubble_cache,
                        expansion_stats=expansion_stats,
                        final_hop_stats=final_hop_stats,
                        forbidden_station_ids=forbidden,
                        top_k=max(request.routes, 1),
                    )
                else:
                    trades = best_fixed_terminal_trades_streamed(
                        session,
                        node.station,
                        request,
                        available_credits=node.available_credits,
                        bubble_cache=bubble_cache,
                        terminal_by_id=terminal_by_id,
                        terminal_system_ids=terminal_system_ids,
                        restriction_kwargs=terminal_restriction_kwargs,
                        expansion_stats=expansion_stats,
                        final_hop_stats=final_hop_stats,
                        forbidden_station_ids=forbidden,
                        top_k=max(request.routes, 1),
                    )
                for trade in trades:
                    finalists.append(
                        _make_child_node(
                            node, trade, request, base_trade_budget
                        )
                    )
                    candidate_trade_count += 1
        finally:
            if terminal_temp is not None:
                terminal_temp.drop(session.connection(), checkfirst=True)
        progress.close_subtask(final_node_task)
        final_hop_elapsed_ms = _elapsed_ms(final_hop_started)
        market_query_ms += final_hop_elapsed_ms
        final_hop_stats.elapsed_ms = final_hop_elapsed_ms

        if not finalists:
            # An unclosed loop is not a loop — no partial fallback here
            # either.
            if loop_mode:
                raise _loop_failure()
            if _revisit_active(request) and expansion_stats.revisit_skips > final_revisit_skips_before:
                raise _no_revisit_route_failure(request)
            # The final-hop collapse is the canonical partial-route case:
            # the route reached hop N-1 but could not complete the requested
            # terminal hop. Preserve the best completed frontier node as a
            # route and let the renderer explain whether the final hop failed
            # because no destination was reachable or because no viable trade
            # survived. If the frontier somehow contains no completed trade,
            # keep the ordinary no-result failures below.
            partial = _best_partial_node(frontier)
            if partial is not None:
                reason = "no_viable_trade"
                if final_hop_stats.nodes_with_reachable_destination == 0:
                    reason = "no_reachable_route"
                route = _reconstruct_route(partial, request)
                warning = run_result.PartialRouteWarning(
                    completed_hops=partial.hop_index,
                    requested_hops=request.hops,
                    phase="final",
                    reason=reason,
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
            raise failures.NoReachableRoute(
                "No frontier station could complete the route to the "
                "requested destination with the current jump settings."
            )

        # Top-N by practical score. The sort is stable and reverse-ordered, so
        # equal scores keep frontier order and --routes 1 selects the same single
        # winner max() chose. Each chosen finalist becomes one route, best-first.
        finalists.sort(
            key=lambda candidate: candidate.accumulated_practical_score,
            reverse=True,
        )
        routes = [
            _reconstruct_route(node, request)
            for node in finalists[: max(request.routes, 1)]
        ]
        # Final spine step: the terminal hop is done and the winner is known.
        # finalists is score-sorted, so [0] carries the best completed profit.
        progress.increment(
            1,
            description=(
                f"Planning route  ·  best "
                f"+{finalists[0].accumulated_raw_profit:,} cr"
            ),
        )
    finally:
        qualification.release(session)
        data_gateway.release_reachable_memo(session, reachable_memo)

    return _multihop_result(
        request=request,
        route=routes[0],
        extra_routes=tuple(routes[1:]),
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
    )


def _envelope_is_provably_loose(
    station: run_result.ResolvedStation,
    envelope_xyz: tuple[float, float, float],
    envelope_ly: float,
    bubble_reach_ly: float,
) -> bool:
    """True when the destination envelope cannot exclude any reachable system.

    The expansion bubble extends at most ``bubble_reach_ly`` (jumps-per ×
    ly-per) from the anchor, so if the anchor sits within
    ``envelope_ly - bubble_reach_ly`` of the envelope centre, the whole
    bubble lies inside the envelope by the triangle inequality and the
    filter excludes nothing. Conservative: False only ever means the
    envelope stays on, which is always correct.
    """

    slack = envelope_ly - bubble_reach_ly
    if slack < 0.0:
        return False
    dx = station.x - envelope_xyz[0]
    dy = station.y - envelope_xyz[1]
    dz = station.z - envelope_xyz[2]
    return dx * dx + dy * dy + dz * dz <= slack * slack


def best_open_ended_trades_from(
    session: Session,
    source_station: run_result.ResolvedStation,
    request: RunRequest,
    *,
    available_credits: int,
    top_k: int,
    terminal_hop: bool,
    bubble_cache: dict[int, object],
    reachable_memo: dict | None = None,
    destination_envelope_xyz: tuple[float, float, float] | None = None,
    destination_envelope_ly: float | None = None,
    expansion_stats: run_result.ExpansionStats | None = None,
    station_cache: dict[int, run_result.ResolvedStation] | None = None,
    qualification: data_gateway.QualificationCache | None = None,
    forbidden_station_ids: frozenset[int] = frozenset(),
) -> list[_HopCandidate]:
    """Return the top-K best forward trades from a single source station.

    Fixed-terminal multi-hop expansion calls this once per frontier node with
    the node's source station, its post-margin credit budget, the request's
    reachable-set memo, and the destination envelope. It is the real-budget
    forward primitive — distinct from the optimistic
    best_open_ended_hop_candidates the single-anchor open engine uses.

    The helper:
    1. Asks the data gateway for profitable destinations reachable from
       source_station under the current request filters. terminal_hop=False
       adds an onward-source-viability check so demand-only stations cannot
       occupy an intermediate frontier; terminal_hop=True allows them as
       final-route destinations.
    2. Groups candidates by destination station, optimises cargo for each
       pair under the supplied credit budget, scores by practical value.
    3. Sorts by practical score descending and lazily computes the jump
       path for the top-K survivors only — the reachable subquery has
       already guaranteed in-range systems, but plan_jump_path returns the
       actual polyline path needed at render time.

    ``destination_envelope_xyz`` and ``destination_envelope_ly``, when
    supplied, narrow the destination set in SQL so the candidate fetch
    only materialises destinations within that direct-distance envelope
    of the requested anchor. Multi-hop fixed-terminal expansion uses this
    so out-of-envelope candidates are never built, grouped, scored, or
    jump-pathed in Python.

    The returned list is sorted by practical_score descending and capped at
    top_k.
    """

    helper_started = time.perf_counter()
    if expansion_stats is not None:
        expansion_stats.expansion_calls += 1

    source_system = _system_from_station(source_station)

    # Station groups stream in best-ceiling-first, so the kept-score floor
    # rises fast, pairs solve as their group arrives, and once the next
    # ceiling cannot beat the floor the stream is abandoned — the remaining
    # stations are never read out of the database. The jump path is still
    # deferred to the top-K survivors below. Selection happens by
    # (score desc, pair-best order asc), so tied scores resolve by best-pair
    # order — pruning, solve order, and the stop change the work done, never
    # the route chosen. This engine ranks purely by score (it never sees
    # --towards), so pruning is always enabled. The source is one fixed
    # station, so each station group is exactly one pair.
    capacity_units = int(request.capacity_units or 0)
    penalty_percent = request.ls_penalty_percent
    threshold = _KeptScoreThreshold(top_k)

    group_iter = data_gateway.iter_open_ended_station_groups(
        session,
        (source_station.station_id,),
        source_system,
        request,
        open_role="destination",
        available_credits=available_credits,
        terminal_hop=terminal_hop,
        reachable_memo=reachable_memo,
        destination_envelope_xyz=destination_envelope_xyz,
        destination_envelope_ly=destination_envelope_ly,
        expansion_stats=expansion_stats,
        qualification=qualification,
    )

    scored: list[
        tuple[float, tuple, run_result.ResolvedStation, run_result.CargoPlan]
    ] = []
    try:
        for station_id, ceiling_ppu, station_candidates in group_iter:
            floor = threshold.current()
            if floor is not None:
                # Forward: the destination varies per station, so the floor
                # converts at the curve's maximum (ls 0) — admissible.
                stop_floor = cargo_prune_floor(floor, 0, penalty_percent)
                if (
                    stop_floor is not None
                    and capacity_units * ceiling_ppu < stop_floor
                ):
                    # Provable early stop: ceilings are non-increasing and
                    # the floor only rises, so no unread station can place.
                    if expansion_stats is not None:
                        expansion_stats.stream_stops += 1
                    break
            if station_id in forbidden_station_ids:
                # The expanding chain has already visited this station (or
                # within the loop-interval window): a revisit the rule forbids.
                # Skip it before it can consume a top-K slot or raise the kept-
                # score floor, so legal continuations lower in the stream are
                # still read rather than starved by an illegal high scorer.
                if expansion_stats is not None:
                    expansion_stats.revisit_skips += 1
                continue
            hydrate_started = time.perf_counter()
            destination_station = data_gateway.fetch_stations_by_id(
                session,
                (station_id,),
                cache=station_cache,
            ).get(station_id)
            if expansion_stats is not None:
                expansion_stats.fetch_ms += _elapsed_ms(hydrate_started)
                expansion_stats.stream_stations_read += 1
                expansion_stats.candidate_rows += len(station_candidates)
            if destination_station is None:
                # A destination that lost its DTO during the fetch —
                # defensive skip rather than a KeyError.
                continue
            grouped_pairs = _group_pairs(station_candidates)
            if expansion_stats is not None:
                expansion_stats.grouped_pairs += len(grouped_pairs)
            for pair_key, pair_candidates in grouped_pairs.items():
                if expansion_stats is not None:
                    expansion_stats.cargo_calls += 1
                prune_floor = cargo_prune_floor(
                    threshold.current(),
                    destination_station.ls_from_star,
                    penalty_percent,
                )
                cargo_started = time.perf_counter()
                try:
                    cargo = optimise_cargo(
                        pair_candidates,
                        capacity_units=capacity_units,
                        available_credits=available_credits,
                        cargo_limit_per_item=request.cargo_limit_per_item,
                        prune_below_raw=prune_floor,
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
                    destination_distance_ls=destination_station.ls_from_star,
                    penalty_percent=penalty_percent,
                )
                threshold.offer(practical_score)
                scored.append(
                    (
                        practical_score,
                        # Equal-score tie-break: the unstreamed fetch ordered
                        # pairs by their best candidate, so the reconstruction
                        # is (best ppu desc, item name) with the pair key
                        # keeping it deterministic.
                        (
                            -pair_candidates[0].profit_per_unit,
                            pair_candidates[0].item_name,
                            pair_key,
                        ),
                        destination_station,
                        cargo,
                    )
                )
    finally:
        group_iter.close()

    scored.sort(key=lambda item: (-item[0], item[1]))

    hop_candidates: list[_HopCandidate] = []
    for practical_score, _original_index, destination_station, cargo in scored:
        if len(hop_candidates) >= top_k:
            break
        jump_started = time.perf_counter()
        try:
            jump_path = plan_jump_path(
                source_system,
                _system_from_station(destination_station),
                max_jumps_per_hop=int(request.max_jumps_per_hop or 0),
                max_ly_per_jump=float(request.max_ly_per_jump or 0.0),
                session=session,
                bubble_cache=bubble_cache,
                avoid_system_ids=request.avoid_system_ids,
            )
        except failures.NoReachableRoute:
            # The reachable subquery has already filtered to in-range systems,
            # so a NoReachableRoute here is a corner case — fall through and
            # try the next-best candidate.
            continue
        finally:
            if expansion_stats is not None:
                expansion_stats.jump_ms += _elapsed_ms(jump_started)
        hop_candidates.append(
            _HopCandidate(
                destination_station=destination_station,
                cargo=cargo,
                jump_path=jump_path,
                practical_score=practical_score,
                raw_profit=cargo.total_profit,
            )
        )

    if expansion_stats is not None:
        expansion_stats.children_returned += len(hop_candidates)
        expansion_stats.elapsed_ms += _elapsed_ms(helper_started)
    return hop_candidates


def best_fixed_pair_trades_from(
    session: Session,
    source_station: run_result.ResolvedStation,
    destination_stations: tuple[run_result.ResolvedStation, ...],
    request: RunRequest,
    *,
    available_credits: int,
    bubble_cache: dict[int, object],
    expansion_stats: run_result.ExpansionStats | None = None,
    final_hop_stats: run_result.FinalHopStats | None = None,
    forbidden_station_ids: frozenset[int] = frozenset(),
    top_k: int = 1,
) -> list[_HopCandidate]:
    """Return up to ``top_k`` best fixed-pair trades from one source to any of
    the given destinations, best-first, or an empty list if none is viable.

    The multi-hop final hop with --to set calls this once per surviving
    frontier node: source is the node's station, destinations are the
    --to endpoint's eligible stations. Reachability, market data, cargo
    fitting, and scoring all reuse the same helpers as the single-hop
    fixed-pair path; the only difference is that per-pair failures are
    swallowed and the function returns the best candidates, or an empty list,
    rather than raising classified failures.

    When ``final_hop_stats`` is supplied, the helper records per-source
    aggregates so the planner can report which frontier nodes reached
    the destination, how many market candidates were found, and how
    many viable cargo plans the final hop produced.
    """

    source_system = _system_from_station(source_station)
    found: list[_HopCandidate] = []
    saw_reachable = False
    saw_viable_cargo = False
    for destination in destination_stations:
        if destination.station_id == source_station.station_id:
            continue
        if destination.station_id in forbidden_station_ids:
            # An already-visited terminal would revisit a station the rule
            # forbids; another --to station may still complete the route.
            # Count it so a final hop that collapses solely on revisit-blocked
            # terminals is classified as NoUniqueRoute, not the generic failure.
            if expansion_stats is not None:
                expansion_stats.revisit_skips += 1
            continue
        try:
            jump_path = plan_jump_path(
                source_system,
                _system_from_station(destination),
                max_jumps_per_hop=int(request.max_jumps_per_hop or 0),
                max_ly_per_jump=float(request.max_ly_per_jump or 0.0),
                session=session,
                bubble_cache=bubble_cache,
                avoid_system_ids=request.avoid_system_ids,
            )
        except failures.NoReachableRoute:
            continue
        saw_reachable = True
        try:
            candidates = data_gateway.fetch_station_pair_candidates(
                session,
                source_station,
                destination,
                request,
                available_credits=available_credits,
                classify_zero_result=False,
            )
        except failures.StationHasNoUsablePriceData:
            # Either side missing usable data — skip this pair; another
            # destination in the --to set may still produce a viable trade.
            continue
        if final_hop_stats is not None:
            final_hop_stats.market_candidates_found += len(candidates)
        if not candidates:
            continue
        try:
            cargo = optimise_cargo(
                candidates,
                capacity_units=int(request.capacity_units or 0),
                available_credits=available_credits,
                cargo_limit_per_item=request.cargo_limit_per_item,
            )
        except failures.NoProfitableTrades:
            continue
        saw_viable_cargo = True
        practical_score = score_with_destination_penalty(
            cargo.total_profit,
            destination_distance_ls=destination.ls_from_star,
            penalty_percent=request.ls_penalty_percent,
        )
        found.append(
            _HopCandidate(
                destination_station=destination,
                cargo=cargo,
                jump_path=jump_path,
                practical_score=practical_score,
                raw_profit=cargo.total_profit,
            )
        )
    if final_hop_stats is not None:
        final_hop_stats.frontier_nodes_attempted += 1
        if saw_reachable:
            final_hop_stats.nodes_with_reachable_destination += 1
        if saw_viable_cargo:
            final_hop_stats.viable_cargo_plans += 1
    # Stable reverse sort keeps destination order on equal scores, so top_k=1
    # returns the same single best the old keep-strictly-greater logic chose.
    found.sort(key=lambda candidate: candidate.practical_score, reverse=True)
    return found[: max(top_k, 1)]


def best_fixed_terminal_trades_streamed(
    session: Session,
    source_station: run_result.ResolvedStation,
    request: RunRequest,
    *,
    available_credits: int,
    bubble_cache: dict[int, object],
    terminal_by_id: dict[int, run_result.ResolvedStation],
    terminal_system_ids: frozenset[int],
    restriction_kwargs: dict,
    expansion_stats: run_result.ExpansionStats | None = None,
    final_hop_stats: run_result.FinalHopStats | None = None,
    forbidden_station_ids: frozenset[int] = frozenset(),
    top_k: int = 1,
) -> list[_HopCandidate]:
    """Final hop from one source to the expanded --to terminal set, streamed.

    The fixed-terminal final hop, set-based: rather than a reachability check and
    a market query per terminal (source x destination), the source streams the
    whole terminal set in one restricted fetch under real credits, solving cargo
    per terminal as its group arrives. Returns up to ``top_k`` _HopCandidate
    best-first; equal scores keep terminal-station-id order, matching the old
    per-destination path. ``nodes_with_reachable_destination`` is taken from the
    reachable relation, not the stream output, and the terminal restriction is
    built once by the caller and reused across every frontier source.
    """

    max_jumps = int(request.max_jumps_per_hop or 0)
    max_ly = float(request.max_ly_per_jump or 0.0)
    source_system = _system_from_station(source_station)

    # Reachable relation: which terminal systems this source can reach. Same
    # bubble and avoid handling plan_jump_path would use, so a terminal system in
    # the set is exactly one a per-pair reachability check would have admitted.
    if max_jumps >= 1:
        reachable = reachable_systems_from(
            session,
            source_system,
            max_jumps_per_hop=max_jumps,
            max_ly_per_jump=max_ly,
            bubble_cache=bubble_cache,
            avoid_system_ids=request.avoid_system_ids,
        )
    else:
        # --jumps-per 0: same-system only, no jump graph.
        reachable = (source_system,)
    reachable_ids = frozenset(r.system_id for r in reachable)

    # A revisit-blocked terminal cannot close the route: count it (so a final hop
    # that collapses solely on blocked terminals classifies as NoUniqueRoute) and
    # drop it from the reachable-destination signal — the old path checked
    # forbidden before the reach test.
    if forbidden_station_ids:
        blocked = forbidden_station_ids & frozenset(terminal_by_id)
        if blocked and expansion_stats is not None:
            expansion_stats.revisit_skips += len(blocked)
        open_terminal_systems = frozenset(
            station.system_id
            for station_id, station in terminal_by_id.items()
            if station_id not in forbidden_station_ids
        )
    else:
        open_terminal_systems = terminal_system_ids

    saw_reachable = bool(reachable_ids & open_terminal_systems)
    if final_hop_stats is not None:
        final_hop_stats.frontier_nodes_attempted += 1
        if saw_reachable:
            final_hop_stats.nodes_with_reachable_destination += 1
    if not saw_reachable:
        return []

    found: list[_HopCandidate] = []
    saw_viable_cargo = False
    group_iter = data_gateway.iter_open_ended_station_groups(
        session,
        (source_station.station_id,),
        source_system,
        request,
        open_role="destination",
        available_credits=available_credits,
        terminal_hop=True,
        precomputed_reachable_systems=reachable,
        **restriction_kwargs,
    )
    try:
        for dest_station_id, _ceiling, candidates in group_iter:
            if dest_station_id in forbidden_station_ids:
                # Already counted above; just never trade into it.
                continue
            destination = terminal_by_id.get(dest_station_id)
            if destination is None:
                continue
            if final_hop_stats is not None:
                final_hop_stats.market_candidates_found += len(candidates)
            try:
                cargo = optimise_cargo(
                    candidates,
                    capacity_units=int(request.capacity_units or 0),
                    available_credits=available_credits,
                    cargo_limit_per_item=request.cargo_limit_per_item,
                )
            except failures.NoProfitableTrades:
                continue
            saw_viable_cargo = True
            practical_score = score_with_destination_penalty(
                cargo.total_profit,
                destination_distance_ls=destination.ls_from_star,
                penalty_percent=request.ls_penalty_percent,
            )
            found.append(
                _HopCandidate(
                    destination_station=destination,
                    cargo=cargo,
                    jump_path=None,
                    practical_score=practical_score,
                    raw_profit=cargo.total_profit,
                )
            )
    finally:
        group_iter.close()
    if final_hop_stats is not None and saw_viable_cargo:
        final_hop_stats.viable_cargo_plans += 1

    # Best-first; equal scores keep terminal-station-id order — the old stable
    # reverse sort over station-id-ordered destinations.
    found.sort(
        key=lambda c: (-c.practical_score, c.destination_station.station_id)
    )
    winners = found[: max(top_k, 1)]
    # Jump paths for the winners only — each is reachable (the gate above), and
    # the source bubble is already cached from the reachable compute.
    return [
        replace(
            candidate,
            jump_path=plan_jump_path(
                source_system,
                _system_from_station(candidate.destination_station),
                max_jumps_per_hop=max_jumps,
                max_ly_per_jump=max_ly,
                session=session,
                bubble_cache=bubble_cache,
                avoid_system_ids=request.avoid_system_ids,
            ),
        )
        for candidate in winners
    ]
