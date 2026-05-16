"""One-hop trade run planner orchestration."""

from __future__ import annotations

import time
from dataclasses import dataclass, replace

from sqlalchemy.orm import Session

from . import data_gateway, failures, resolver, run_result
from .cargo import optimise_cargo
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


def plan_onehop_route(session: Session, request: RunRequest) -> run_result.RunResult:
    """Plan one station-to-station trade hop."""

    started = time.perf_counter()

    validation_started = time.perf_counter()
    validate_run_request(request)
    validation_ms = _elapsed_ms(validation_started)

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
    )

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


def _best_pair_plan(
    session: Session,
    source_stations: tuple[run_result.ResolvedStation, ...],
    destination_stations: tuple[run_result.ResolvedStation, ...],
    request: RunRequest,
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
                )
            except failures.ReachabilityImplementationMissing:
                raise
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
                    available_credits=int(request.starting_credits or 0)
                    - request.insurance_reserve,
                    cargo_limit_per_item=request.cargo_limit_per_item,
                )
            except failures.NoAffordableCargo:
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
    raise failures.NoAffordableCargo(
        "Profitable trades exist, but no cargo can be afforded."
    )


def _pair_is_better(pair: _PairPlan, best_pair: _PairPlan | None) -> bool:
    if best_pair is None:
        return True
    if pair.practical_score != best_pair.practical_score:
        return pair.practical_score > best_pair.practical_score
    return pair.cargo.total_profit > best_pair.cargo.total_profit


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