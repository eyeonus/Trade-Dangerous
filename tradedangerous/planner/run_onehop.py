"""One-hop trade run planner orchestration."""

from __future__ import annotations

import time
from dataclasses import replace

from sqlalchemy.orm import Session

from .cargo import optimise_cargo
from .data_gateway import fetch_station_pair_candidates, validate_station_filters
from .failures import NoProfitableTrades
from .reachability import plan_jump_path
from .resolver import resolve_station
from .run_request import RunRequest
from .run_result import (
    PlannedHop,
    PlannedRoute,
    PlannerDiagnostics,
    ResolvedStation,
    ResolvedSystem,
    RunResult,
)
from .score import score_with_destination_penalty
from .validation import validate_first_slice_request


def plan_onehop_route(session: Session, request: RunRequest) -> RunResult:
    """Plan one station-to-station trade hop."""

    started = time.perf_counter()

    validation_started = time.perf_counter()
    validate_first_slice_request(request)
    validation_ms = _elapsed_ms(validation_started)

    resolution_started = time.perf_counter()
    source_station = resolve_station(
        session,
        str(request.from_text),
        option_name="--from",
    )
    destination_station = resolve_station(
        session,
        str(request.to_text),
        option_name="--to",
    )
    resolution_ms = _elapsed_ms(resolution_started)

    station_filter_started = time.perf_counter()
    validate_station_filters(source_station, request, role="source")
    validate_station_filters(destination_station, request, role="destination")
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


def with_render_timing(result: RunResult, render_ms: float) -> RunResult:
    """Return a copy of the result with renderer timing populated."""

    diagnostics = replace(result.diagnostics, render_ms=render_ms)
    return replace(result, diagnostics=diagnostics)


def _system_from_station(station: ResolvedStation) -> ResolvedSystem:
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