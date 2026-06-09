"""Trade run planner orchestration and dispatch."""

from __future__ import annotations

import dataclasses
import time

from sqlalchemy.orm import Session

from . import failures, run_result
from .cargo import reset_cargo_counters
from .reachability import plan_jump_path
from .route_anchored import _plan_multi_hop
from .route_common import (
    _elapsed_ms,
    _positioning_anchor_system,
    _system_from_station,
)
from .route_onehop import (
    _best_open_ended_plan,
    _plan_fixed_endpoints,
    _plan_unanchored,
)
from .route_single_anchor import _plan_open_anchor_multi_hop
from .route_unanchored import _plan_unanchored_multi_hop
from .run_request import RunRequest
from .validation import validate_run_request


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

    try:
        if request.hops == 1:
            result = _plan_single_hop(
                session, request, started, validation_ms, bubble_cache
            )
        # Multi-hop endpoint dispatch, mirroring the single-hop dispatcher
        # above. Both endpoints set keeps the fixed-terminal planner (envelope,
        # real budget); one endpoint set runs the single-anchor open engine
        # keyed on which side the planner chooses; both omitted seeds that same
        # open engine from a galaxy-wide set of origins.
        elif request.from_text and request.to_text:
            result = _plan_multi_hop(
                session, request, started, validation_ms, bubble_cache
            )
        elif request.from_text:
            result = _plan_open_anchor_multi_hop(
                session, request, started, validation_ms, bubble_cache,
                open_role="destination",
            )
        elif request.to_text:
            result = _plan_open_anchor_multi_hop(
                session, request, started, validation_ms, bubble_cache,
                open_role="source",
            )
        else:
            result = _plan_unanchored_multi_hop(
                session, request, started, validation_ms, bubble_cache
            )
    except (failures.NoProfitableTrades, failures.NoReachableRoute) as exc:
        # --towards: every candidate the search saw was already filtered to
        # forward progress, so an empty result means no profitable trade moved
        # the route closer to the target. Re-raise in the towards failure
        # family, naming the target. Non-towards runs re-raise unchanged.
        # Partial routes (some progressing hops, then no continuation) are
        # returned by the engines rather than raised, so they are unaffected.
        target = request.towards_target
        if target is not None:
            raise failures.NoTowardsProgress(
                "No profitable trade made forward progress toward "
                f"{target.name} within the supplied constraints.",
                option_name="--towards",
                entity_name=target.name,
            ) from exc
        raise

    # --towards: flag any route that reached the target system, so the renderer
    # can report the arrival and how many hops it took.
    if request.towards_target is not None:
        result = _annotate_towards_arrival(request, result)

    # Surface the empty repositioning legs once the trade route is chosen, so
    # every anchored shape shows them without each engine owning the logic.
    if request.start_jumps or request.end_jumps:
        result = _attach_positioning_legs(session, request, result)
    return result


def _annotate_towards_arrival(
    request: RunRequest,
    result: run_result.RunResult,
) -> run_result.RunResult:
    """Flag any route that reached the --towards target with its hop count.

    Checked here, once, after the winning route exists, so neither route engine
    owns the arrival check. A route has arrived when its last station sits in the
    target system; arrival_hops records how many trade hops it took, which the
    renderer turns into "arrived after N hops".
    """

    target = request.towards_target
    if target is None:
        return result
    new_routes = []
    changed = False
    for route in result.routes:
        if route.stations and route.stations[-1].system_id == target.system_id:
            new_routes.append(
                dataclasses.replace(route, arrival_hops=len(route.hops))
            )
            changed = True
        else:
            new_routes.append(route)
    if not changed:
        return result
    return dataclasses.replace(result, routes=tuple(new_routes))


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


def _attach_positioning_legs(
    session: Session,
    request: RunRequest,
    result: run_result.RunResult,
) -> run_result.RunResult:
    """Attach the empty repositioning legs for --start-jumps / --end-jumps.

    The trade route is already chosen; this surfaces the unladen flight the
    commander actually flies between the named anchor and the route's trading
    endpoints — anchor -> first station for --start-jumps, last station ->
    anchor for --end-jumps. Computed once here so no route engine grows its own
    positioning-leg logic.

    Empty jumps use the unladen range (--empty-ly, else --ly-per) and the
    positioning count, which differ from the per-hop bubble. A private cache
    keeps those positioning-radius bubbles out of the per-hop cache shared
    across the search.
    """

    empty_ly = float(request.empty_ly_per or request.max_ly_per_jump or 0.0)
    leg_cache: dict[int, object] = {}

    start_anchor = None
    if request.start_jumps and request.from_endpoint is not None:
        start_anchor = _positioning_anchor_system(request.from_endpoint)

    end_anchor = None
    if request.end_jumps and request.to_endpoint is not None:
        end_anchor = _positioning_anchor_system(request.to_endpoint)

    new_routes = []
    for route in result.routes:
        start_leg = None
        end_leg = None
        if start_anchor is not None and route.stations:
            start_leg = plan_jump_path(
                start_anchor,
                _system_from_station(route.stations[0]),
                max_jumps_per_hop=request.start_jumps,
                max_ly_per_jump=empty_ly,
                session=session,
                bubble_cache=leg_cache,
                avoid_system_ids=request.avoid_system_ids,
            )
        if end_anchor is not None and route.stations:
            end_leg = plan_jump_path(
                _system_from_station(route.stations[-1]),
                end_anchor,
                max_jumps_per_hop=request.end_jumps,
                max_ly_per_jump=empty_ly,
                session=session,
                bubble_cache=leg_cache,
                avoid_system_ids=request.avoid_system_ids,
            )
        new_routes.append(
            dataclasses.replace(
                route,
                start_positioning=start_leg,
                end_positioning=end_leg,
            )
        )
    return dataclasses.replace(result, routes=tuple(new_routes))
