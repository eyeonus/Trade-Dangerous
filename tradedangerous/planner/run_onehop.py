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

    reachability_started = time.perf_counter()
    jump_path = plan_jump_path(
        _system_from_station(source_station),
        _system_from_station(destination_station),
        max_jumps_per_hop=int(request.max_jumps_per_hop or 0),
        max_ly_per_jump=float(request.max_ly_per_jump or 0.0),
    )
    reachability_ms = _elapsed_ms(reachability_started)

    market_query_started = time.perf_counter()
    candidates = fetch_station_pair_candidates(
        session,
        source_station,
        destination_station,
        request,
    )
    market_query_ms = _elapsed_ms(market_query_started)

    if not candidates:
        raise NoProfitableTrades(
            "No profitable trades were found for the selected station pair.",
            details={
                "source_station": source_station.dbname,
                "destination_station": destination_station.dbname,
            },
        )

    cargo_started = time.perf_counter()
    available_credits = int(request.starting_credits or 0) - request.insurance_reserve
    cargo = optimise_cargo(
        candidates,
        capacity_units=int(request.capacity_units or 0),
        available_credits=available_credits,
        cargo_limit_per_item=request.cargo_limit_per_item,
    )
    cargo_optimisation_ms = _elapsed_ms(cargo_started)

    practical_score = score_with_destination_penalty(
        cargo.total_profit,
        destination_distance_ls=destination_station.ls_from_star,
        penalty_percent=request.ls_penalty_percent,
    )

    hop = PlannedHop(
        source_station=source_station,
        destination_station=destination_station,
        cargo=cargo,
        raw_profit=cargo.total_profit,
        practical_score=practical_score,
        jump_path=jump_path,
    )
    route = PlannedRoute(
        stations=(source_station, destination_station),
        hops=(hop,),
        total_raw_profit=cargo.total_profit,
        total_practical_score=practical_score,
        starting_credits=int(request.starting_credits or 0),
        ending_credits=int(request.starting_credits or 0) + cargo.total_profit,
    )

    diagnostics = PlannerDiagnostics(
        validation_ms=validation_ms,
        resolution_ms=resolution_ms,
        station_filter_ms=station_filter_ms,
        market_query_ms=market_query_ms,
        reachability_ms=reachability_ms,
        cargo_optimisation_ms=cargo_optimisation_ms,
        total_planner_ms=_elapsed_ms(started),
        candidate_trade_count=len(candidates),
    )

    return RunResult(
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


def _system_from_station(
    station: run_result.ResolvedStation,
) -> run_result.ResolvedSystem:
    return ResolvedSystem(
        system_id=station.system_id,
        name=station.system_name,
        dbname=f"{station.system_name.upper()}/",
        x=station.x,
        y=station.y,
        z=station.z,
    )


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000.0