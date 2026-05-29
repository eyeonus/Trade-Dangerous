"""Single-hop planning: fixed endpoints, open-ended, and unanchored."""

from __future__ import annotations

import time
from dataclasses import dataclass, replace

from sqlalchemy.orm import Session

from . import data_gateway, failures, resolver, run_result
from .cargo import optimise_cargo
from .reachability import plan_jump_path
from .run_request import RunRequest
from .score import score_with_destination_penalty

from .route_common import (
    _elapsed_ms,
    _group_pairs,
    _stations_from_endpoint,
    _system_from_station,
)


@dataclass(frozen=True, slots=True)
class _PairPlan:
    """One viable station-pair plan before final best-route selection."""

    source_station: run_result.ResolvedStation
    destination_station: run_result.ResolvedStation
    jump_path: object
    cargo: object
    practical_score: float


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
