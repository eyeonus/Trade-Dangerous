"""Trade run planner orchestration."""

from __future__ import annotations

import time
from dataclasses import dataclass, replace

from sqlalchemy.orm import Session

from . import data_gateway, failures, resolver, run_result
from .cargo import cargo_counters, optimise_cargo, reset_cargo_counters
from .reachability import plan_jump_path
from .run_request import RunRequest
from .score import score_with_destination_penalty
from .validation import validate_run_request


@dataclass(frozen=True, slots=True)
class _PairPlan:
    """One viable station-pair plan before final best-route selection."""

    source_station: run_result.ResolvedStation
    destination_station: run_result.ResolvedStation
    jump_path: object
    cargo: object
    practical_score: float


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
# carried into the next layer. Probe outcomes (P2) keep both at 50: the
# top-100 score curve for representative Bubble runs is smooth out past rank
# 50, well above the 25%-of-#1 threshold that would justify trimming.
_MULTIHOP_EXPANSION_WIDTH = 50
_MULTIHOP_FRONTIER_WIDTH = 50

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


def plan_route(session: Session, request: RunRequest) -> run_result.RunResult:
    """Plan a single-hop or multi-hop trade run from the request.

    Validation runs once here so single-hop and multi-hop share one input
    contract. Dispatch is by ``request.hops``: 1 routes to the four-way
    single-hop dispatcher; N > 1 routes to the multi-hop frontier search.
    Both branches share the per-request reachability bubble cache so a
    given source system's BFS is paid for once across the entire run.
    """

    started = time.perf_counter()

    validation_started = time.perf_counter()
    validate_run_request(request)
    validation_ms = _elapsed_ms(validation_started)

    # Zero the cargo path counters so the diagnostics reflect only this run.
    reset_cargo_counters()

    # One reachability bubble cache lives for the lifetime of this request.
    # Each anchor's bubble is loaded once and reused across every hop that
    # walks from it, so a candidate matrix evaluating many destinations from
    # a fixed origin pays for the bubble once, not once per destination.
    bubble_cache: dict[int, object] = {}

    if request.hops == 1:
        return _plan_single_hop(
            session, request, started, validation_ms, bubble_cache
        )
    # Multi-hop endpoint dispatch, mirroring the single-hop dispatcher above.
    # Both endpoints set keeps the fixed-terminal planner (envelope, real
    # budget); one endpoint set runs the single-anchor open engine keyed on
    # which side the planner chooses; both omitted is rejected in validation.
    if request.from_text and request.to_text:
        return _plan_multi_hop(
            session, request, started, validation_ms, bubble_cache
        )
    if request.from_text:
        return _plan_open_anchor_multi_hop(
            session, request, started, validation_ms, bubble_cache,
            open_role="destination",
        )
    return _plan_open_anchor_multi_hop(
        session, request, started, validation_ms, bubble_cache,
        open_role="source",
    )


def _plan_single_hop(
    session: Session,
    request: RunRequest,
    started: float,
    validation_ms: float,
    bubble_cache: dict[int, object],
) -> run_result.RunResult:
    """Dispatch a single-hop request by which endpoints the user named.

    Both named: evaluate the station-pair matrix, no spatial search. One
    named: the planner selects the other via the open-ended search,
    open_role being the role of that selected endpoint. Neither named: the
    unanchored search selects both endpoints with a galaxy-wide candidate
    query.
    """

    if request.from_text and request.to_text:
        return _plan_fixed_endpoints(
            session, request, started, validation_ms, bubble_cache
        )
    if request.from_text:
        return _best_open_ended_plan(
            session, request, started, validation_ms,
            open_role="destination", bubble_cache=bubble_cache,
        )
    if request.to_text:
        return _best_open_ended_plan(
            session, request, started, validation_ms,
            open_role="source", bubble_cache=bubble_cache,
        )
    return _plan_unanchored(
        session, request, started, validation_ms, bubble_cache
    )


def _plan_fixed_endpoints(
    session: Session,
    request: RunRequest,
    started: float,
    validation_ms: float,
    bubble_cache: dict[int, object],
) -> run_result.RunResult:
    """Plan one hop when both endpoints are supplied by the user."""

    resolution_started = time.perf_counter()
    source_endpoint = resolver.resolve_endpoint(
        session,
        str(request.from_text),
        option_name="--from",
    )
    destination_endpoint = resolver.resolve_endpoint(
        session,
        str(request.to_text),
        option_name="--to",
    )
    resolution_ms = _elapsed_ms(resolution_started)

    station_filter_started = time.perf_counter()
    source_stations = _stations_from_endpoint(
        session,
        source_endpoint,
        request,
        role="source",
    )
    destination_stations = _stations_from_endpoint(
        session,
        destination_endpoint,
        request,
        role="destination",
    )
    station_filter_ms = _elapsed_ms(station_filter_started)

    (
        best_pair,
        reachability_ms,
        market_query_ms,
        cargo_optimisation_ms,
        candidate_trade_count,
    ) = _best_pair_plan(
        session,
        source_stations,
        destination_stations,
        request,
        bubble_cache,
    )

    diagnostics = run_result.PlannerDiagnostics(
        validation_ms=validation_ms,
        resolution_ms=resolution_ms,
        station_filter_ms=station_filter_ms,
        market_query_ms=market_query_ms,
        reachability_ms=reachability_ms,
        cargo_optimisation_ms=cargo_optimisation_ms,
        total_planner_ms=_elapsed_ms(started),
        candidate_trade_count=candidate_trade_count,
    )
    return _assemble_result(request, best_pair, diagnostics)


def _best_open_ended_plan(
    session: Session,
    request: RunRequest,
    started: float,
    validation_ms: float,
    *,
    open_role: str,
    bubble_cache: dict[int, object],
) -> run_result.RunResult:
    """Plan one hop with one fixed endpoint and one chosen by the planner.

    open_role is the trade role of the endpoint the planner selects: "source"
    when --from was omitted, "destination" when --to was omitted. The other
    endpoint is the fixed, anchored one and takes the opposite role. The
    open-ended candidate query produces every profitable trade between the
    fixed stations and any station reachable in a single loaded jump, and the
    best-scoring station pair wins. Both open-ended directions run through this
    one path; only the endpoint derivation below depends on open_role.
    """

    # The fixed endpoint is the one the user supplied; its role, option name,
    # and request text are the inverse of open_role.
    if open_role == "source":
        fixed_role = "destination"
        fixed_option = "--to"
        fixed_text = request.to_text
    else:
        fixed_role = "source"
        fixed_option = "--from"
        fixed_text = request.from_text

    resolution_started = time.perf_counter()
    fixed_endpoint = resolver.resolve_endpoint(
        session,
        str(fixed_text),
        option_name=fixed_option,
    )
    resolution_ms = _elapsed_ms(resolution_started)

    station_filter_started = time.perf_counter()
    fixed_stations = _stations_from_endpoint(
        session,
        fixed_endpoint,
        request,
        role=fixed_role,
    )
    station_filter_ms = _elapsed_ms(station_filter_started)

    anchor_system = _anchor_system_from_endpoint(fixed_endpoint)
    fixed_station_ids = tuple(station.station_id for station in fixed_stations)

    market_started = time.perf_counter()
    available_credits = (
        int(request.starting_credits or 0) - request.insurance_reserve
    )
    candidates = data_gateway.fetch_open_ended_trade_candidates(
        session,
        fixed_station_ids,
        anchor_system,
        request,
        open_role=open_role,
        available_credits=available_credits,
        terminal_hop=True,
    )
    if not candidates:
        _raise_empty_open_search(
            session,
            anchor_system,
            request,
            fixed_station_ids,
            open_role=open_role,
        )

    # Materialise only the open side's stations as DTOs; the fixed side is
    # already in hand. The open side is the source when open_role is "source",
    # the destination otherwise.
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
    market_query_ms = _elapsed_ms(market_started)
    candidate_trade_count = len(candidates)

    # Fixed-side and open-side stations may overlap (a same-system search
    # reaches the fixed system's own stations); merging them keyed by id is
    # still correct — a shared station resolves to one DTO either way.
    station_map = {station.station_id: station for station in fixed_stations}
    station_map.update(open_stations)
    grouped_pairs = _group_pairs(candidates)

    best_pair = None
    cargo_optimisation_ms = 0.0
    for (source_id, destination_id), pair_candidates in grouped_pairs.items():
        source_station = station_map[source_id]
        destination_station = station_map[destination_id]
        cargo_started = time.perf_counter()
        try:
            cargo = optimise_cargo(
                pair_candidates,
                capacity_units=int(request.capacity_units or 0),
                available_credits=available_credits,
                cargo_limit_per_item=request.cargo_limit_per_item,
            )
        except failures.NoProfitableTrades:
            cargo_optimisation_ms += _elapsed_ms(cargo_started)
            continue
        cargo_optimisation_ms += _elapsed_ms(cargo_started)
        practical_score = score_with_destination_penalty(
            cargo.total_profit,
            destination_distance_ls=destination_station.ls_from_star,
            penalty_percent=request.ls_penalty_percent,
        )
        pair = _PairPlan(
            source_station=source_station,
            destination_station=destination_station,
            jump_path=None,
            cargo=cargo,
            practical_score=practical_score,
        )
        if _pair_is_better(pair, best_pair):
            best_pair = pair

    if best_pair is None:
        raise failures.NoProfitableTrades(
            "No viable cargo plan was available."
        )

    reachability_started = time.perf_counter()
    jump_path = plan_jump_path(
        _system_from_station(best_pair.source_station),
        _system_from_station(best_pair.destination_station),
        max_jumps_per_hop=int(request.max_jumps_per_hop or 0),
        max_ly_per_jump=float(request.max_ly_per_jump or 0.0),
        session=session,
        bubble_cache=bubble_cache,
    )
    reachability_ms = _elapsed_ms(reachability_started)
    best_pair = replace(best_pair, jump_path=jump_path)

    diagnostics = run_result.PlannerDiagnostics(
        validation_ms=validation_ms,
        resolution_ms=resolution_ms,
        station_filter_ms=station_filter_ms,
        market_query_ms=market_query_ms,
        reachability_ms=reachability_ms,
        cargo_optimisation_ms=cargo_optimisation_ms,
        total_planner_ms=_elapsed_ms(started),
        candidate_trade_count=candidate_trade_count,
    )
    return _assemble_result(request, best_pair, diagnostics)


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

    candidates = data_gateway.fetch_open_ended_trade_candidates(
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
    )
    if expansion_stats is not None:
        expansion_stats.candidate_rows += len(candidates)
    if not candidates:
        if expansion_stats is not None:
            expansion_stats.elapsed_ms += _elapsed_ms(helper_started)
        return []

    open_station_ids = tuple(
        {candidate.destination_station_id for candidate in candidates}
    )
    destination_stations = data_gateway.fetch_stations_by_id(
        session,
        open_station_ids,
    )

    grouped_pairs = _group_pairs(candidates)
    if expansion_stats is not None:
        expansion_stats.grouped_pairs += len(grouped_pairs)

    # Score every viable pair first; defer the jump-path computation until
    # after the top-K trim so we only pay it for survivors.
    scored: list[tuple[float, run_result.ResolvedStation, run_result.CargoPlan]] = []
    for (_source_id, destination_id), pair_candidates in grouped_pairs.items():
        destination_station = destination_stations.get(destination_id)
        if destination_station is None:
            # A destination that lost its DTO during the fetch — defensive
            # skip rather than a KeyError. fetch_stations_by_id should always
            # cover the ids it was handed; missing entries indicate a data
            # race rather than a planner bug.
            continue
        if expansion_stats is not None:
            expansion_stats.cargo_calls += 1
        try:
            cargo = optimise_cargo(
                pair_candidates,
                capacity_units=int(request.capacity_units or 0),
                available_credits=available_credits,
                cargo_limit_per_item=request.cargo_limit_per_item,
            )
        except failures.NoProfitableTrades:
            continue
        practical_score = score_with_destination_penalty(
            cargo.total_profit,
            destination_distance_ls=destination_station.ls_from_star,
            penalty_percent=request.ls_penalty_percent,
        )
        scored.append((practical_score, destination_station, cargo))

    scored.sort(key=lambda item: item[0], reverse=True)

    hop_candidates: list[_HopCandidate] = []
    for practical_score, destination_station, cargo in scored:
        if len(hop_candidates) >= top_k:
            break
        try:
            jump_path = plan_jump_path(
                source_system,
                _system_from_station(destination_station),
                max_jumps_per_hop=int(request.max_jumps_per_hop or 0),
                max_ly_per_jump=float(request.max_ly_per_jump or 0.0),
                session=session,
                bubble_cache=bubble_cache,
            )
        except failures.NoReachableRoute:
            # The reachable subquery has already filtered to in-range systems,
            # so a NoReachableRoute here is a corner case — fall through and
            # try the next-best candidate.
            continue
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


def best_fixed_pair_trade_from(
    session: Session,
    source_station: run_result.ResolvedStation,
    destination_stations: tuple[run_result.ResolvedStation, ...],
    request: RunRequest,
    *,
    available_credits: int,
    bubble_cache: dict[int, object],
    final_hop_stats: run_result.FinalHopStats | None = None,
) -> _HopCandidate | None:
    """Return the single best fixed-pair trade from one source to any of the
    given destinations, or None if no viable trade exists.

    The multi-hop final hop with --to set calls this once per surviving
    frontier node: source is the node's station, destinations are the
    --to endpoint's eligible stations. Reachability, market data, cargo
    fitting, and scoring all reuse the same helpers as the single-hop
    fixed-pair path; the only difference is that per-pair failures are
    swallowed and the function returns the best (or None) rather than
    raising classified failures.

    When ``final_hop_stats`` is supplied, the helper records per-source
    aggregates so the planner can report which frontier nodes reached
    the destination, how many market candidates were found, and how
    many viable cargo plans the final hop produced.
    """

    source_system = _system_from_station(source_station)
    best: _HopCandidate | None = None
    saw_reachable = False
    saw_viable_cargo = False
    for destination in destination_stations:
        if destination.station_id == source_station.station_id:
            continue
        try:
            jump_path = plan_jump_path(
                source_system,
                _system_from_station(destination),
                max_jumps_per_hop=int(request.max_jumps_per_hop or 0),
                max_ly_per_jump=float(request.max_ly_per_jump or 0.0),
                session=session,
                bubble_cache=bubble_cache,
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
        if best is None or practical_score > best.practical_score:
            best = _HopCandidate(
                destination_station=destination,
                cargo=cargo,
                jump_path=jump_path,
                practical_score=practical_score,
                raw_profit=cargo.total_profit,
            )
    if final_hop_stats is not None:
        final_hop_stats.frontier_nodes_attempted += 1
        if saw_reachable:
            final_hop_stats.nodes_with_reachable_destination += 1
        if saw_viable_cargo:
            final_hop_stats.viable_cargo_plans += 1
    return best


def _plan_multi_hop(
    session: Session,
    request: RunRequest,
    started: float,
    validation_ms: float,
    bubble_cache: dict[int, object],
) -> run_result.RunResult:
    """Plan an N-hop route between a named --from origin and --to destination.

    The fixed-terminal multi-hop planner: both endpoints are supplied, so the
    search grows forward from the origin and must end at one of Y's eligible
    stations. (Open-ended multi-hop — one endpoint omitted — runs on the
    single-anchor engine instead; see plan_route's dispatch.)

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

    resolution_started = time.perf_counter()
    origin_endpoint = resolver.resolve_endpoint(
        session,
        str(request.from_text),
        option_name="--from",
    )
    destination_endpoint = resolver.resolve_endpoint(
        session,
        str(request.to_text),
        option_name="--to",
    )
    resolution_ms = _elapsed_ms(resolution_started)

    station_filter_started = time.perf_counter()
    origin_stations = _stations_from_endpoint(
        session,
        origin_endpoint,
        request,
        role="source",
    )
    destination_stations = _stations_from_endpoint(
        session,
        destination_endpoint,
        request,
        role="destination",
    )
    # Every --to station shares the same system, so any of them gives the
    # envelope anchor coordinates.
    anchor_station = destination_stations[0]
    to_system_xyz = (anchor_station.x, anchor_station.y, anchor_station.z)
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
        )
        for station in origin_stations
    ]

    # Reachability temp tables stay alive across calls so the per-source
    # build cost (the dominant fraction of fetch_ms per probe P1) is paid
    # once per (source_system, jumps_per, ly_per) key for the whole run.
    # Released in the finally below so a partial run does not leak tables.
    reachable_memo: dict = {}

    market_query_ms = 0.0
    candidate_trade_count = 0
    frontier_widths: list[int] = []
    expansions_examined = 0
    layer_stats: list[run_result.LayerStats] = []
    expansion_stats = run_result.ExpansionStats()
    final_hop_stats = run_result.FinalHopStats()

    try:
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
            for node in frontier:
                expansions_examined += 1
                layer_expansion_calls += 1
                children = best_open_ended_trades_from(
                    session,
                    node.station,
                    request,
                    available_credits=node.available_credits,
                    top_k=_MULTIHOP_EXPANSION_WIDTH,
                    terminal_hop=False,
                    bubble_cache=bubble_cache,
                    reachable_memo=reachable_memo,
                    destination_envelope_xyz=to_system_xyz,
                    destination_envelope_ly=envelope_ly,
                    expansion_stats=expansion_stats,
                )
                for trade in children:
                    next_frontier.append(
                        _make_child_node(node, trade, request, base_trade_budget)
                    )
                    candidate_trade_count += 1
                    layer_children_generated += 1
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
            seen_systems: set[int] = set()
            deduped: list[_FrontierNode] = []
            for node in next_frontier:
                system_id = node.station.system_id
                if system_id in seen_systems:
                    continue
                seen_systems.add(system_id)
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

        # Final hop: each surviving frontier node is matched against Y's
        # stations as a fixed-pair plan. The destination is the fixed --to, so
        # there is no onward-viability check to apply.
        final_hop_started = time.perf_counter()
        finalists: list[_FrontierNode] = []
        for node in frontier:
            expansions_examined += 1
            trade = best_fixed_pair_trade_from(
                session,
                node.station,
                destination_stations,
                request,
                available_credits=node.available_credits,
                bubble_cache=bubble_cache,
                final_hop_stats=final_hop_stats,
            )
            if trade is not None:
                finalists.append(
                    _make_child_node(node, trade, request, base_trade_budget)
                )
                candidate_trade_count += 1
        final_hop_elapsed_ms = _elapsed_ms(final_hop_started)
        market_query_ms += final_hop_elapsed_ms
        final_hop_stats.elapsed_ms = final_hop_elapsed_ms

        if not finalists:
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

        winner = max(
            finalists,
            key=lambda candidate: candidate.accumulated_practical_score,
        )
        route = _reconstruct_route(winner, request)
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


def _plan_unanchored(
    session: Session,
    request: RunRequest,
    started: float,
    validation_ms: float,
    bubble_cache: dict[int, object],
) -> run_result.RunResult:
    """Plan one hop with neither endpoint named — the planner selects both.

    With no anchor the search is genuinely galaxy-wide. The unanchored
    candidate query narrows and ranks in SQL and returns a bounded top set of
    profitable trades; this function reuses the shared pair-evaluation helpers
    over that set exactly as the open-ended path does over its own candidates.
    It shares no body with _best_open_ended_plan: the unanchored search differs
    in kind, not in a parameter.
    """

    market_started = time.perf_counter()
    candidates, unanchored_counters = data_gateway.fetch_unanchored_trade_candidates(
        session, request, bubble_cache
    )
    if not candidates:
        raise failures.NoProfitableTrades(
            "No profitable trades were found anywhere in reachable range."
        )

    # Both sides are planner-selected, so both stations are materialised here
    # from the ids that actually appear in the bounded candidate set.
    station_ids = tuple(
        {candidate.source_station_id for candidate in candidates}
        | {candidate.destination_station_id for candidate in candidates}
    )
    station_map = data_gateway.fetch_stations_by_id(session, station_ids)
    market_query_ms = _elapsed_ms(market_started)
    candidate_trade_count = len(candidates)

    grouped_pairs = _group_pairs(candidates)

    best_pair = None
    cargo_optimisation_ms = 0.0
    for (source_id, destination_id), pair_candidates in grouped_pairs.items():
        source_station = station_map[source_id]
        destination_station = station_map[destination_id]
        cargo_started = time.perf_counter()
        try:
            cargo = optimise_cargo(
                pair_candidates,
                capacity_units=int(request.capacity_units or 0),
                available_credits=int(request.starting_credits or 0)
                - request.insurance_reserve,
                cargo_limit_per_item=request.cargo_limit_per_item,
            )
        except failures.NoProfitableTrades:
            cargo_optimisation_ms += _elapsed_ms(cargo_started)
            continue
        cargo_optimisation_ms += _elapsed_ms(cargo_started)
        practical_score = score_with_destination_penalty(
            cargo.total_profit,
            destination_distance_ls=destination_station.ls_from_star,
            penalty_percent=request.ls_penalty_percent,
        )
        pair = _PairPlan(
            source_station=source_station,
            destination_station=destination_station,
            jump_path=None,
            cargo=cargo,
            practical_score=practical_score,
        )
        if _pair_is_better(pair, best_pair):
            best_pair = pair

    if best_pair is None:
        raise failures.NoProfitableTrades(
            "No viable cargo plan was available."
        )

    reachability_started = time.perf_counter()
    jump_path = plan_jump_path(
        _system_from_station(best_pair.source_station),
        _system_from_station(best_pair.destination_station),
        max_jumps_per_hop=int(request.max_jumps_per_hop or 0),
        max_ly_per_jump=float(request.max_ly_per_jump or 0.0),
        session=session,
        bubble_cache=bubble_cache,
    )
    reachability_ms = _elapsed_ms(reachability_started)
    best_pair = replace(best_pair, jump_path=jump_path)

    diagnostics = run_result.PlannerDiagnostics(
        validation_ms=validation_ms,
        resolution_ms=0.0,
        station_filter_ms=0.0,
        market_query_ms=market_query_ms,
        reachability_ms=reachability_ms,
        cargo_optimisation_ms=cargo_optimisation_ms,
        total_planner_ms=_elapsed_ms(started),
        candidate_trade_count=candidate_trade_count,
        unanchored_pairs_examined=unanchored_counters.pairs_examined,
        unanchored_pairs_accepted=unanchored_counters.pairs_accepted,
        unanchored_bubble_systems=unanchored_counters.bubble_systems,
        unanchored_per_commodity_cap_hits=unanchored_counters.per_commodity_cap_hits,
    )
    return _assemble_result(request, best_pair, diagnostics)


def _assemble_result(
    request: RunRequest,
    best_pair: _PairPlan,
    diagnostics: run_result.PlannerDiagnostics,
) -> run_result.RunResult:
    """Build the single-route RunResult shared by both planning paths."""

    hop = run_result.PlannedHop(
        source_station=best_pair.source_station,
        destination_station=best_pair.destination_station,
        cargo=best_pair.cargo,
        raw_profit=best_pair.cargo.total_profit,
        practical_score=best_pair.practical_score,
        jump_path=best_pair.jump_path,
    )
    route = run_result.PlannedRoute(
        stations=(best_pair.source_station, best_pair.destination_station),
        hops=(hop,),
        total_raw_profit=best_pair.cargo.total_profit,
        total_practical_score=best_pair.practical_score,
        starting_credits=int(request.starting_credits or 0),
        ending_credits=int(request.starting_credits or 0)
        + best_pair.cargo.total_profit,
    )

    return run_result.RunResult(
        routes=(route,),
        diagnostics=diagnostics,
    )


def with_render_timing(
    result: run_result.RunResult,
    render_ms: float,
) -> run_result.RunResult:
    """Return a copy of the result with renderer timing populated."""

    diagnostics = replace(result.diagnostics, render_ms=render_ms)
    return replace(result, diagnostics=diagnostics)


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


def _anchor_system_from_endpoint(
    endpoint: resolver.ResolvedEndpoint,
) -> run_result.ResolvedSystem:
    """Return the single anchor system for a resolved fixed endpoint.

    A station endpoint anchors on its own system; a system endpoint anchors on
    itself. The endpoint has already been validated by _stations_from_endpoint,
    so exactly one of station or system is populated.
    """

    if endpoint.station is not None:
        return _system_from_station(endpoint.station)
    return endpoint.system


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


def _raise_empty_open_search(
    session: Session,
    anchor_system: run_result.ResolvedSystem,
    request: RunRequest,
    fixed_station_ids: tuple[int, ...],
    *,
    open_role: str,
) -> None:
    """Raise the coarse failure for an open-ended search that found no trade.

    A reachable station pair with no profitable trade, and no reachable station
    pair at all, are distinct outcomes — one lightweight probe tells them
    apart. The messages name the anchored endpoint: the origin when the planner
    picks the destination, the destination when it picks the origin.
    """

    if data_gateway.any_reachable_station_pair(
        session,
        anchor_system,
        request,
        fixed_station_ids,
    ):
        if open_role == "source":
            raise failures.NoProfitableTrades(
                "No profitable trades were found to the destination from any "
                "reachable station."
            )
        raise failures.NoProfitableTrades(
            "No profitable trades were found from the origin to any "
            "reachable station."
        )
    anchored_noun = "destination" if open_role == "source" else "origin"
    raise failures.NoReachableRoute(
        "No reachable station was found within range of the "
        f"{anchored_noun} system."
    )


def _best_pair_plan(
    session: Session,
    source_stations: tuple[run_result.ResolvedStation, ...],
    destination_stations: tuple[run_result.ResolvedStation, ...],
    request: RunRequest,
    bubble_cache: dict[int, object],
) -> tuple[_PairPlan, float, float, float, int]:
    best_pair = None
    reachability_ms = 0.0
    market_query_ms = 0.0
    cargo_optimisation_ms = 0.0
    candidate_trade_count = 0
    saw_reachable_pair = False
    saw_source_selling_data = False
    saw_destination_buying_data = False
    saw_profitable_pair = False
    available_credits = (
        int(request.starting_credits or 0) - request.insurance_reserve
    )
    for source_station in source_stations:
        for destination_station in destination_stations:
            if source_station.station_id == destination_station.station_id:
                continue
            reach_started = time.perf_counter()
            try:
                jump_path = plan_jump_path(
                    _system_from_station(source_station),
                    _system_from_station(destination_station),
                    max_jumps_per_hop=int(request.max_jumps_per_hop or 0),
                    max_ly_per_jump=float(request.max_ly_per_jump or 0.0),
                    session=session,
                    bubble_cache=bubble_cache,
                )
            except failures.NoReachableRoute:
                reachability_ms += _elapsed_ms(reach_started)
                continue
            reachability_ms += _elapsed_ms(reach_started)
            saw_reachable_pair = True
            market_started = time.perf_counter()
            try:
                candidates = data_gateway.fetch_station_pair_candidates(
                    session,
                    source_station,
                    destination_station,
                    request,
                    available_credits=available_credits,
                )
            except failures.SourceHasNoSellingData:
                market_query_ms += _elapsed_ms(market_started)
                continue
            except failures.DestinationHasNoBuyingData:
                saw_source_selling_data = True
                market_query_ms += _elapsed_ms(market_started)
                continue
            market_query_ms += _elapsed_ms(market_started)
            saw_source_selling_data = True
            saw_destination_buying_data = True
            candidate_trade_count += len(candidates)
            if not candidates:
                continue
            saw_profitable_pair = True
            cargo_started = time.perf_counter()
            try:
                cargo = optimise_cargo(
                    candidates,
                    capacity_units=int(request.capacity_units or 0),
                    available_credits=available_credits,
                    cargo_limit_per_item=request.cargo_limit_per_item,
                )
            except failures.NoProfitableTrades:
                cargo_optimisation_ms += _elapsed_ms(cargo_started)
                continue
            cargo_optimisation_ms += _elapsed_ms(cargo_started)
            practical_score = score_with_destination_penalty(
                cargo.total_profit,
                destination_distance_ls=destination_station.ls_from_star,
                penalty_percent=request.ls_penalty_percent,
            )
            pair = _PairPlan(
                source_station=source_station,
                destination_station=destination_station,
                jump_path=jump_path,
                cargo=cargo,
                practical_score=practical_score,
            )
            if _pair_is_better(pair, best_pair):
                best_pair = pair
    if best_pair is not None:
        return (
            best_pair,
            reachability_ms,
            market_query_ms,
            cargo_optimisation_ms,
            candidate_trade_count,
        )
    if not saw_reachable_pair:
        raise failures.NoReachableRoute(
            "No reachable station pair was found for the selected endpoints."
        )
    if not saw_source_selling_data:
        raise failures.SourceHasNoSellingData(
            "No reachable source station had usable selling data.",
            option_name="--from",
        )
    if not saw_destination_buying_data:
        raise failures.DestinationHasNoBuyingData(
            "No reachable destination station had usable buying data.",
            option_name="--to",
        )
    if not saw_profitable_pair:
        raise failures.NoProfitableTrades(
            "No profitable trades were found across reachable station pairs."
        )
    raise failures.NoProfitableTrades(
        "No viable cargo plan was available."
    )


def _pair_is_better(pair: _PairPlan, best_pair: _PairPlan | None) -> bool:
    if best_pair is None:
        return True
    if pair.practical_score != best_pair.practical_score:
        return pair.practical_score > best_pair.practical_score
    if pair.cargo.total_profit != best_pair.cargo.total_profit:
        return pair.cargo.total_profit > best_pair.cargo.total_profit
    # Deterministic tie-break: lower source ID, then lower destination ID.
    if pair.source_station.station_id != best_pair.source_station.station_id:
        return pair.source_station.station_id < best_pair.source_station.station_id
    return pair.destination_station.station_id < best_pair.destination_station.station_id


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


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000.0