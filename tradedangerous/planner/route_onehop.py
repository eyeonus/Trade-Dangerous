"""Single-hop planning: fixed endpoints, open-ended, and unanchored."""

from __future__ import annotations

import time
from dataclasses import dataclass, replace

from sqlalchemy.orm import Session

from . import data_gateway, failures, resolver, run_result
from .cargo import cargo_counters, cargo_pruned, optimise_cargo
from .reachability import plan_jump_path, reachable_systems_from
from .run_request import RunRequest
from .score import score_with_destination_penalty
from ..misc import progress as pbar

from .route_common import (
    _KeptScoreThreshold,
    _distance_sq_to_target,
    _elapsed_ms,
    _group_pairs,
    _stations_from_endpoint,
    _system_from_station,
    cargo_order_key,
    cargo_prune_floor,
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
    positioning_caches: dict[str, dict] | None = None,
) -> run_result.RunResult:
    """Plan one hop when both endpoints are supplied by the user."""

    # Endpoints were resolved once at dispatch; the planner reads the canonical
    # DTOs rather than resolving names again.
    source_endpoint = request.from_endpoint
    destination_endpoint = request.to_endpoint
    resolution_ms = 0.0

    station_filter_started = time.perf_counter()
    source_stations = _stations_from_endpoint(
        session,
        source_endpoint,
        request,
        role="source",
        positioning_caches=positioning_caches,
    )
    destination_stations = _stations_from_endpoint(
        session,
        destination_endpoint,
        request,
        role="destination",
        positioning_caches=positioning_caches,
    )
    station_filter_ms = _elapsed_ms(station_filter_started)

    (
        best_pairs,
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

    cargo_fast_hits, cargo_recursive_hits = cargo_counters()
    diagnostics = run_result.PlannerDiagnostics(
        validation_ms=validation_ms,
        resolution_ms=resolution_ms,
        station_filter_ms=station_filter_ms,
        market_query_ms=market_query_ms,
        reachability_ms=reachability_ms,
        cargo_optimisation_ms=cargo_optimisation_ms,
        cargo_fast_path_hits=cargo_fast_hits,
        cargo_recursive_hits=cargo_recursive_hits,
        cargo_pruned_solves=cargo_pruned(),
        total_planner_ms=_elapsed_ms(started),
        candidate_trade_count=candidate_trade_count,
    )
    return _assemble_result(request, best_pairs, diagnostics)


def _best_open_ended_plan(
    session: Session,
    request: RunRequest,
    started: float,
    validation_ms: float,
    *,
    open_role: str,
    bubble_cache: dict[int, object],
    progress=None,
    positioning_caches: dict[str, dict] | None = None,
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

    # A disabled bar stands in when the caller passes none, so the progress
    # calls below are safe no-ops off the --progress path.
    if progress is None:
        progress = pbar.Progress(show=False)

    # The fixed endpoint is the one the user supplied; its role is the inverse
    # of open_role. It was resolved once at dispatch, so read the canonical DTO.
    if open_role == "source":
        fixed_role = "destination"
        fixed_endpoint = request.to_endpoint
    else:
        fixed_role = "source"
        fixed_endpoint = request.from_endpoint
    resolution_ms = 0.0

    station_filter_started = time.perf_counter()
    fixed_stations = _stations_from_endpoint(
        session,
        fixed_endpoint,
        request,
        role=fixed_role,
        positioning_caches=positioning_caches,
    )
    station_filter_ms = _elapsed_ms(station_filter_started)

    anchor_system = _anchor_system_from_endpoint(fixed_endpoint)
    fixed_station_ids = tuple(station.station_id for station in fixed_stations)

    market_started = time.perf_counter()
    available_credits = (
        int(request.starting_credits or 0) - request.insurance_reserve
    )

    capacity_units = int(request.capacity_units or 0)
    penalty_percent = request.ls_penalty_percent

    # Station groups stream in best-ceiling-first; pairs are solved as their
    # group arrives, and once the next ceiling cannot beat the best score
    # held the stream is abandoned — the remaining stations are never read.
    # The single-best selection (_pair_is_better) breaks ties
    # deterministically by station id, and the stop only fires strictly
    # below the held score, so reordering, pruning, and the stop change
    # only the work done. Pruning is by score, so it is disabled under
    # --towards, which ranks by progress toward the target rather than
    # score — the stream then runs to completion.
    threshold = _KeptScoreThreshold(request.routes, enabled=request.towards_target is None)
    # The stop converts the held score to raw profit at the most permissive
    # destination the stream could still produce: the closest fixed station
    # when the open side is the source (the fixed side is the destination),
    # the curve's maximum (ls 0) when the destination varies per station.
    if open_role == "source":
        stop_conversion_ls = min(
            (station.ls_from_star or 0) for station in fixed_stations
        )
    else:
        stop_conversion_ls = 0

    # Fixed-side and open-side stations may overlap (a same-system search
    # reaches the fixed system's own stations); keying by id keeps the map
    # correct — a shared station resolves to one DTO either way. Open-side
    # DTOs are materialised per consumed group, so abandoned stations are
    # never hydrated.
    station_map = {station.station_id: station for station in fixed_stations}

    def _order_key(item):
        (_src, dest_id), candidates_for_pair = item
        destination = station_map.get(dest_id)
        if destination is None:
            return float("-inf")
        return cargo_order_key(
            candidates_for_pair,
            destination.ls_from_star,
            capacity_units,
            penalty_percent,
        )

    kept = _KeptPairs(request.routes, request)
    cargo_optimisation_ms = 0.0
    candidate_trade_count = 0
    group_iter = data_gateway.iter_open_ended_station_groups(
        session,
        fixed_station_ids,
        anchor_system,
        request,
        open_role=open_role,
        available_credits=available_credits,
        terminal_hop=True,
    )
    scanned_stations = 0
    try:
        for open_station_id, ceiling_ppu, station_candidates in group_iter:
            # Streaming fetch with no known total, so the bar counts stations as
            # they arrive rather than filling to a percentage. Refresh every 50
            # to keep the forced redraw off the hot path.
            scanned_stations += 1
            if scanned_stations % 50 == 0:
                progress.increment(
                    50,
                    description=(
                        f"scanning candidates · {scanned_stations:,} stations"
                    ),
                )
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
                    # no unread station can reach the held score.
                    break
            if open_station_id not in station_map:
                open_station = data_gateway.fetch_stations_by_id(
                    session,
                    (open_station_id,),
                ).get(open_station_id)
                if open_station is None:
                    # Lost its DTO during the fetch — defensive skip.
                    continue
                station_map[open_station_id] = open_station
            candidate_trade_count += len(station_candidates)
            grouped_pairs = _group_pairs(station_candidates)
            for (source_id, destination_id), pair_candidates in sorted(
                grouped_pairs.items(), key=_order_key, reverse=True
            ):
                source_station = station_map[source_id]
                destination_station = station_map[destination_id]
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
                    cargo_optimisation_ms += _elapsed_ms(cargo_started)
                    continue
                cargo_optimisation_ms += _elapsed_ms(cargo_started)
                if cargo is None:
                    # Pruned: cannot beat the best pair found so far.
                    continue
                practical_score = score_with_destination_penalty(
                    cargo.total_profit,
                    destination_distance_ls=destination_station.ls_from_star,
                    penalty_percent=penalty_percent,
                )
                threshold.offer(practical_score)
                pair = _PairPlan(
                    source_station=source_station,
                    destination_station=destination_station,
                    jump_path=None,
                    cargo=cargo,
                    practical_score=practical_score,
                )
                kept.offer(pair)
    finally:
        group_iter.close()
    # The stream interleaves fetch and solve, so the cargo share accumulated
    # inside the loop is subtracted to keep the market figure a fetch cost.
    market_query_ms = _elapsed_ms(market_started) - cargo_optimisation_ms

    if candidate_trade_count == 0:
        _raise_empty_open_search(
            session,
            anchor_system,
            request,
            fixed_station_ids,
            open_role=open_role,
        )
    best_pairs = kept.best()
    if not best_pairs:
        raise failures.NoProfitableTrades(
            "No viable cargo plan was available."
        )

    reachability_started = time.perf_counter()
    best_pairs = [
        replace(
            pair,
            jump_path=plan_jump_path(
                _system_from_station(pair.source_station),
                _system_from_station(pair.destination_station),
                max_jumps_per_hop=int(request.max_jumps_per_hop or 0),
                max_ly_per_jump=float(request.max_ly_per_jump or 0.0),
                session=session,
                bubble_cache=bubble_cache,
                avoid_system_ids=request.avoid_system_ids,
            ),
        )
        for pair in best_pairs
    ]
    reachability_ms = _elapsed_ms(reachability_started)

    cargo_fast_hits, cargo_recursive_hits = cargo_counters()
    diagnostics = run_result.PlannerDiagnostics(
        validation_ms=validation_ms,
        resolution_ms=resolution_ms,
        station_filter_ms=station_filter_ms,
        market_query_ms=market_query_ms,
        reachability_ms=reachability_ms,
        cargo_optimisation_ms=cargo_optimisation_ms,
        cargo_fast_path_hits=cargo_fast_hits,
        cargo_recursive_hits=cargo_recursive_hits,
        cargo_pruned_solves=cargo_pruned(),
        total_planner_ms=_elapsed_ms(started),
        candidate_trade_count=candidate_trade_count,
    )
    return _assemble_result(request, best_pairs, diagnostics)


def _plan_unanchored(
    session: Session,
    request: RunRequest,
    started: float,
    validation_ms: float,
    bubble_cache: dict[int, object],
    progress=None,
) -> run_result.RunResult:
    """Plan one hop with neither endpoint named — the planner selects both.

    With no anchor the search is genuinely galaxy-wide. The unanchored
    candidate query narrows and ranks in SQL and returns a bounded top set of
    profitable trades; this function reuses the shared pair-evaluation helpers
    over that set exactly as the open-ended path does over its own candidates.
    It shares no body with _best_open_ended_plan: the unanchored search differs
    in kind, not in a parameter.
    """

    # A disabled bar stands in when the caller passes none, so the progress
    # calls below are safe no-ops off the --progress path.
    if progress is None:
        progress = pbar.Progress(show=False)

    market_started = time.perf_counter()
    # One blocking galaxy-wide fetch with nothing to count, so just show it is
    # alive — the spinner and elapsed animate on rich's refresh thread while the
    # query runs.
    progress.increment(0, description="scanning galaxy-wide candidates")
    candidates, unanchored_counters = data_gateway.fetch_unanchored_trade_candidates(
        session, request, bubble_cache
    )
    if not candidates:
        raise failures.NoProfitableTrades(
            "No profitable trades were found anywhere within range."
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

    capacity_units = int(request.capacity_units or 0)
    penalty_percent = request.ls_penalty_percent
    available_credits = (
        int(request.starting_credits or 0) - request.insurance_reserve
    )

    # Solve best-first and prune pairs that cannot beat the best so far;
    # _pair_is_better breaks ties by station id, so the result is independent of
    # solve order. Unanchored has no --from, so --towards never applies, but the
    # disabled-under-towards guard is kept uniform with the open-ended path.
    threshold = _KeptScoreThreshold(request.routes, enabled=request.towards_target is None)

    def _order_key(item):
        (_src, dest_id), candidates_for_pair = item
        destination = station_map.get(dest_id)
        if destination is None:
            return float("-inf")
        return cargo_order_key(
            candidates_for_pair,
            destination.ls_from_star,
            capacity_units,
            penalty_percent,
        )

    kept = _KeptPairs(request.routes, request)
    cargo_optimisation_ms = 0.0
    for (source_id, destination_id), pair_candidates in sorted(
        grouped_pairs.items(), key=_order_key, reverse=True
    ):
        source_station = station_map[source_id]
        destination_station = station_map[destination_id]
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
            cargo_optimisation_ms += _elapsed_ms(cargo_started)
            continue
        cargo_optimisation_ms += _elapsed_ms(cargo_started)
        if cargo is None:
            # Pruned: cannot beat the best pair found so far.
            continue
        practical_score = score_with_destination_penalty(
            cargo.total_profit,
            destination_distance_ls=destination_station.ls_from_star,
            penalty_percent=penalty_percent,
        )
        threshold.offer(practical_score)
        pair = _PairPlan(
            source_station=source_station,
            destination_station=destination_station,
            jump_path=None,
            cargo=cargo,
            practical_score=practical_score,
        )
        kept.offer(pair)

    best_pairs = kept.best()
    if not best_pairs:
        raise failures.NoProfitableTrades(
            "No viable cargo plan was available."
        )

    reachability_started = time.perf_counter()
    best_pairs = [
        replace(
            pair,
            jump_path=plan_jump_path(
                _system_from_station(pair.source_station),
                _system_from_station(pair.destination_station),
                max_jumps_per_hop=int(request.max_jumps_per_hop or 0),
                max_ly_per_jump=float(request.max_ly_per_jump or 0.0),
                session=session,
                bubble_cache=bubble_cache,
                avoid_system_ids=request.avoid_system_ids,
            ),
        )
        for pair in best_pairs
    ]
    reachability_ms = _elapsed_ms(reachability_started)

    cargo_fast_hits, cargo_recursive_hits = cargo_counters()
    diagnostics = run_result.PlannerDiagnostics(
        validation_ms=validation_ms,
        resolution_ms=0.0,
        station_filter_ms=0.0,
        market_query_ms=market_query_ms,
        reachability_ms=reachability_ms,
        cargo_optimisation_ms=cargo_optimisation_ms,
        cargo_fast_path_hits=cargo_fast_hits,
        cargo_recursive_hits=cargo_recursive_hits,
        cargo_pruned_solves=cargo_pruned(),
        total_planner_ms=_elapsed_ms(started),
        candidate_trade_count=candidate_trade_count,
        unanchored_pairs_examined=unanchored_counters.pairs_examined,
        unanchored_pairs_accepted=unanchored_counters.pairs_accepted,
        unanchored_bubble_systems=unanchored_counters.bubble_systems,
        unanchored_per_commodity_cap_hits=unanchored_counters.per_commodity_cap_hits,
    )
    return _assemble_result(request, best_pairs, diagnostics)


def _best_pair_plan(
    session: Session,
    source_stations: tuple[run_result.ResolvedStation, ...],
    destination_stations: tuple[run_result.ResolvedStation, ...],
    request: RunRequest,
    bubble_cache: dict[int, object],
) -> tuple[list[_PairPlan], float, float, float, int]:
    """Best one-hop station pair(s) for fixed or expanded endpoints.

    --direct skips reachability entirely (the commander plots the jumps), so it
    keeps the simple per-pair evaluation. Every other one-hop fixed shape goes
    through the batched path: reachability gates candidates per source system and
    the whole expanded destination set is paired in one streamed query per source
    system, rather than one market query per (source, destination) pair.
    """

    if request.direct:
        return _direct_pair_plan(
            session, source_stations, destination_stations, request
        )
    return _batched_pair_plan(
        session, source_stations, destination_stations, request, bubble_cache
    )


def _direct_pair_plan(
    session: Session,
    source_stations: tuple[run_result.ResolvedStation, ...],
    destination_stations: tuple[run_result.ResolvedStation, ...],
    request: RunRequest,
) -> tuple[list[_PairPlan], float, float, float, int]:
    """--direct: best trade per fixed pair, no reachability and no jump path.

    The commander flies the jumps, so every non-self pair is treated as
    reachable and carries no jump path. The matrix is small (named endpoints; no
    positioning — validation forbids it under --direct), so the per-pair fetch is
    kept rather than batched.
    """

    kept = _KeptPairs(request.routes, request)
    market_query_ms = 0.0
    cargo_optimisation_ms = 0.0
    candidate_trade_count = 0
    saw_profitable_pair = False
    reachable_source_ids: set[int] = set()
    reachable_destination_ids: set[int] = set()
    available_credits = (
        int(request.starting_credits or 0) - request.insurance_reserve
    )
    for source_station in source_stations:
        for destination_station in destination_stations:
            if source_station.station_id == destination_station.station_id:
                continue
            reachable_source_ids.add(source_station.station_id)
            reachable_destination_ids.add(destination_station.station_id)
            market_started = time.perf_counter()
            candidates = data_gateway.fetch_station_pair_candidates(
                session,
                source_station,
                destination_station,
                request,
                available_credits=available_credits,
                classify_zero_result=False,
            )
            market_query_ms += _elapsed_ms(market_started)
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
            kept.offer(
                _PairPlan(
                    source_station=source_station,
                    destination_station=destination_station,
                    jump_path=None,
                    cargo=cargo,
                    practical_score=practical_score,
                )
            )
    best_pairs = kept.best()
    if best_pairs:
        return (
            best_pairs,
            0.0,
            market_query_ms,
            cargo_optimisation_ms,
            candidate_trade_count,
        )
    _raise_pair_failure(
        session,
        request,
        saw_reachable_pair=bool(reachable_source_ids),
        reachable_source_ids=reachable_source_ids,
        reachable_destination_ids=reachable_destination_ids,
        saw_profitable_pair=saw_profitable_pair,
    )


def _batched_pair_plan(
    session: Session,
    source_stations: tuple[run_result.ResolvedStation, ...],
    destination_stations: tuple[run_result.ResolvedStation, ...],
    request: RunRequest,
    bubble_cache: dict[int, object],
) -> tuple[list[_PairPlan], float, float, float, int]:
    """Reachability-gated one-hop pairing, batched by source system.

    Per source system the reachable systems are computed once (respecting
    --avoid transit, via reachable_systems_from so the avoid-blind SQL fallback
    is never used) and every profitable (source, destination) pair is streamed
    through one iter_open_ended_station_groups call, the open destination side
    restricted to the expanded destination set. Cargo is solved per pair and
    offered to the same bounded best-N collector, so kept-pair selection and ties
    match the per-pair matrix exactly. Jump paths are plotted only for the kept
    winners — reachability is already the candidate gate.
    """

    kept = _KeptPairs(request.routes, request)
    reachability_ms = 0.0
    market_query_ms = 0.0
    cargo_optimisation_ms = 0.0
    candidate_trade_count = 0
    available_credits = (
        int(request.starting_credits or 0) - request.insurance_reserve
    )
    capacity_units = int(request.capacity_units or 0)
    max_jumps = int(request.max_jumps_per_hop or 0)
    max_ly = float(request.max_ly_per_jump or 0.0)

    source_by_id = {s.station_id: s for s in source_stations}
    destination_by_id = {d.station_id: d for d in destination_stations}
    destination_ids = frozenset(destination_by_id)

    # Reachability is a per-system fact: group the source stations by system and
    # compute each system's reachable set once.
    source_by_system: dict[int, list] = {}
    source_system_by_id: dict[int, run_result.ResolvedSystem] = {}
    for station in source_stations:
        source_by_system.setdefault(station.system_id, []).append(station)
        if station.system_id not in source_system_by_id:
            source_system_by_id[station.system_id] = _system_from_station(
                station
            )

    reach_started = time.perf_counter()
    reachable_by_system: dict[int, tuple] = {}
    reachable_ids_by_system: dict[int, frozenset] = {}
    for system_id, system in source_system_by_id.items():
        reachable = reachable_systems_from(
            session,
            system,
            max_jumps_per_hop=max_jumps,
            max_ly_per_jump=max_ly,
            bubble_cache=bubble_cache,
            avoid_system_ids=request.avoid_system_ids,
        )
        reachable_by_system[system_id] = reachable
        reachable_ids_by_system[system_id] = frozenset(
            r.system_id for r in reachable
        )
    reachability_ms += _elapsed_ms(reach_started)

    # Failure classification comes from the reachable relation itself, not from
    # the profitable stream output: which sources can reach a non-self
    # destination, and which destinations are reachable from a non-self source.
    dests_by_system: dict[int, list] = {}
    for station in destination_stations:
        dests_by_system.setdefault(station.system_id, []).append(station)
    reachable_source_ids: set[int] = set()
    reachable_destination_ids: set[int] = set()
    for system_id, sources_here in source_by_system.items():
        reach_ids = reachable_ids_by_system[system_id]
        dests_reachable = [
            d
            for dest_system_id, group in dests_by_system.items()
            if dest_system_id in reach_ids
            for d in group
        ]
        if not dests_reachable:
            continue
        dest_ids_here = frozenset(d.station_id for d in dests_reachable)
        for station in sources_here:
            if dest_ids_here - {station.station_id}:
                reachable_source_ids.add(station.station_id)
        source_ids_here = frozenset(s.station_id for s in sources_here)
        for d in dests_reachable:
            if source_ids_here - {d.station_id}:
                reachable_destination_ids.add(d.station_id)
    saw_reachable_pair = bool(reachable_source_ids)

    # Stream candidates per source system, pairing against the expanded
    # destination set. The destination restriction is materialised once and
    # reused across every stream (amendment), small sets staying a literal IN.
    connection = session.connection()
    dest_temp, restrict_kwargs = data_gateway.build_open_restriction(
        connection, destination_ids
    )
    pair_candidates: dict[tuple[int, int], list] = {}
    try:
        for system_id, sources_here in source_by_system.items():
            reachable = reachable_by_system[system_id]
            if not reachable:
                continue
            market_started = time.perf_counter()
            stream = data_gateway.iter_open_ended_station_groups(
                session,
                tuple(s.station_id for s in sources_here),
                source_system_by_id[system_id],
                request,
                open_role="destination",
                available_credits=available_credits,
                terminal_hop=True,
                precomputed_reachable_systems=reachable,
                **restrict_kwargs,
            )
            try:
                for _open_id, _ceiling, candidates in stream:
                    for candidate in candidates:
                        if (
                            candidate.source_station_id
                            == candidate.destination_station_id
                        ):
                            continue
                        key = (
                            candidate.source_station_id,
                            candidate.destination_station_id,
                        )
                        pair_candidates.setdefault(key, []).append(candidate)
                        candidate_trade_count += 1
            finally:
                stream.close()
            market_query_ms += _elapsed_ms(market_started)
    finally:
        if dest_temp is not None:
            dest_temp.drop(connection, checkfirst=True)

    saw_profitable_pair = bool(pair_candidates)

    # Cargo per pair, offered to the bounded collector. Offer order does not
    # matter: it keeps the top-N under a deterministic total order, so the
    # batched result matches the per-pair matrix exactly.
    for (source_id, dest_id), candidates in pair_candidates.items():
        cargo_started = time.perf_counter()
        try:
            cargo = optimise_cargo(
                tuple(candidates),
                capacity_units=capacity_units,
                available_credits=available_credits,
                cargo_limit_per_item=request.cargo_limit_per_item,
            )
        except failures.NoProfitableTrades:
            cargo_optimisation_ms += _elapsed_ms(cargo_started)
            continue
        cargo_optimisation_ms += _elapsed_ms(cargo_started)
        destination_station = destination_by_id[dest_id]
        practical_score = score_with_destination_penalty(
            cargo.total_profit,
            destination_distance_ls=destination_station.ls_from_star,
            penalty_percent=request.ls_penalty_percent,
        )
        kept.offer(
            _PairPlan(
                source_station=source_by_id[source_id],
                destination_station=destination_station,
                jump_path=None,
                cargo=cargo,
                practical_score=practical_score,
            )
        )

    best_pairs = kept.best()
    if best_pairs:
        # Jump paths for the winners only — each is reachable (the candidate
        # gate), and its source bubble is already cached from the reach compute.
        reach_started = time.perf_counter()
        resolved = [
            replace(
                pair,
                jump_path=plan_jump_path(
                    _system_from_station(pair.source_station),
                    _system_from_station(pair.destination_station),
                    max_jumps_per_hop=max_jumps,
                    max_ly_per_jump=max_ly,
                    session=session,
                    bubble_cache=bubble_cache,
                    avoid_system_ids=request.avoid_system_ids,
                ),
            )
            for pair in best_pairs
        ]
        reachability_ms += _elapsed_ms(reach_started)
        return (
            resolved,
            reachability_ms,
            market_query_ms,
            cargo_optimisation_ms,
            candidate_trade_count,
        )

    _raise_pair_failure(
        session,
        request,
        saw_reachable_pair=saw_reachable_pair,
        reachable_source_ids=reachable_source_ids,
        reachable_destination_ids=reachable_destination_ids,
        saw_profitable_pair=saw_profitable_pair,
    )


def _raise_pair_failure(
    session: Session,
    request: RunRequest,
    *,
    saw_reachable_pair: bool,
    reachable_source_ids: set[int],
    reachable_destination_ids: set[int],
    saw_profitable_pair: bool,
) -> None:
    """Raise the right no-result failure for a one-hop pair search.

    Shared by the direct and batched paths. The reachable flags and id sets
    describe the reachable relation (not the profitable stream), so the family is
    correct even when no pair produced a candidate. Two aggregate probes
    classify selling/buying-data gaps for the whole matrix rather than per pair.
    """

    if not saw_reachable_pair:
        raise failures.NoReachableRoute(
            "No station pair within range was found for the chosen endpoints."
        )
    if not data_gateway.station_set_has_selling_data(
        session, tuple(reachable_source_ids), request
    ):
        raise failures.SourceHasNoSellingData(
            "No source station within range had usable selling data.",
            option_name="--from",
        )
    if not data_gateway.station_set_has_buying_data(
        session, tuple(reachable_destination_ids), request
    ):
        raise failures.DestinationHasNoBuyingData(
            "No destination station within range had usable buying data.",
            option_name="--to",
        )
    if not saw_profitable_pair:
        raise failures.NoProfitableTrades(
            "No profitable trades were found across station pairs in range."
        )
    raise failures.NoProfitableTrades(
        "No viable cargo plan was available."
    )


def _pair_is_better(
    pair: _PairPlan,
    best_pair: _PairPlan | None,
    request: RunRequest,
) -> bool:
    if best_pair is None:
        return True
    target = request.towards_target
    if target is not None:
        # --towards: progress-first. The pair whose destination is closest to
        # the target wins; practical score and profit only break the tie.
        pair_dist = _distance_sq_to_target(pair.destination_station, target)
        best_dist = _distance_sq_to_target(best_pair.destination_station, target)
        if pair_dist != best_dist:
            return pair_dist < best_dist
    if pair.practical_score != best_pair.practical_score:
        return pair.practical_score > best_pair.practical_score
    if pair.cargo.total_profit != best_pair.cargo.total_profit:
        return pair.cargo.total_profit > best_pair.cargo.total_profit
    # Deterministic tie-break: lower source ID, then lower destination ID.
    if pair.source_station.station_id != best_pair.source_station.station_id:
        return pair.source_station.station_id < best_pair.source_station.station_id
    return pair.destination_station.station_id < best_pair.destination_station.station_id


class _KeptPairs:
    """Bounded best-N collector for one-hop pair plans, ordered by _pair_is_better.

    Holds up to ``keep`` pairs, best-first. keep=1 reduces to the single-best
    selection the one-hop paths used before --routes, so --routes 1 keeps exactly
    the same winner.
    """

    __slots__ = ("_keep", "_request", "_pairs")

    def __init__(self, keep: int, request: RunRequest):
        self._keep = max(int(keep), 1)
        self._request = request
        self._pairs: list[_PairPlan] = []

    def offer(self, pair: _PairPlan) -> None:
        pairs = self._pairs
        index = 0
        while index < len(pairs) and not _pair_is_better(
            pair, pairs[index], self._request
        ):
            index += 1
        pairs.insert(index, pair)
        if len(pairs) > self._keep:
            del pairs[self._keep:]

    def best(self) -> list[_PairPlan]:
        return list(self._pairs)


def _assemble_result(
    request: RunRequest,
    best_pairs: list[_PairPlan],
    diagnostics: run_result.PlannerDiagnostics,
) -> run_result.RunResult:
    """Build the RunResult from the chosen pair plans, best-first.

    One pair under --routes 1 (the default), up to --routes N otherwise. Shared
    by all three one-hop paths.
    """

    routes = tuple(_route_from_pair(request, pair) for pair in best_pairs)
    return run_result.RunResult(
        routes=routes,
        diagnostics=diagnostics,
    )


def _route_from_pair(
    request: RunRequest, pair: _PairPlan
) -> run_result.PlannedRoute:
    """Build one PlannedRoute from a chosen pair plan."""

    hop = run_result.PlannedHop(
        source_station=pair.source_station,
        destination_station=pair.destination_station,
        cargo=pair.cargo,
        raw_profit=pair.cargo.total_profit,
        practical_score=pair.practical_score,
        jump_path=pair.jump_path,
    )
    return run_result.PlannedRoute(
        stations=(pair.source_station, pair.destination_station),
        hops=(hop,),
        total_raw_profit=pair.cargo.total_profit,
        total_practical_score=pair.practical_score,
        starting_credits=int(request.starting_credits or 0),
        ending_credits=int(request.starting_credits or 0)
        + pair.cargo.total_profit,
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
                "station within range."
            )
        raise failures.NoProfitableTrades(
            "No profitable trades were found from the origin to any "
            "station within range."
        )
    anchored_noun = "destination" if open_role == "source" else "origin"
    raise failures.NoReachableRoute(
        "No station was found within range of the "
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
