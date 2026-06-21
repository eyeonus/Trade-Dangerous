"""Trade run planner orchestration and dispatch."""

from __future__ import annotations

import dataclasses
import time

from sqlalchemy.orm import Session

from ..misc import progress as pbar
from . import failures, run_result
from .cargo import reset_cargo_counters
from .reachability import plan_jump_path, reverse_jump_path
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
from .route_via import _plan_via_route
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

    # Two request-scoped positioning caches, owned here, one per role. Each is
    # pinned to its role's single (jumps, empty_ly, avoid) configuration:
    # --start-jumps fans the source side out, --end-jumps the destination side.
    # Kept separate from the per-hop bubble_cache (a different radius) and from
    # each other (so a start and end leg sharing a source system cannot reuse
    # each other's wrong-count bubble), and reused by _attach_positioning_legs
    # so each anchor's bubble is built once, not rebuilt for the rendered legs.
    positioning_caches: dict[str, dict] = {"source": {}, "destination": {}}

    # plan_route owns the search progress bar for its whole life: build it once
    # here, hand it to whichever engine runs, and clear it in the finally before
    # any result is rendered. Every multi-hop search — and any --via search —
    # has a known hop count, so the spine is a CountingBar (M of N hops +
    # elapsed). Single-hop has nothing to count and is wired separately, so its
    # bar stays disabled; a disabled bar's methods are all no-ops.
    multi_hop_search = bool(
        request.via_system_ids
        or request.via_station_ids
        or request.hops > 1
    )
    if multi_hop_search:
        # Known hop count → a CountingBar hop spine (M of N hops + elapsed),
        # with a per-node sub-row the engines fill as each layer expands.
        prog = pbar.Progress(
            max_value=request.hops,
            label="Planning route",
            style=pbar.CountingBar,
            show=request.progress,
        )
    else:
        # Single-hop: the candidate scan has no known total, so a spinner +
        # elapsed that counts candidate stations as they stream past.
        prog = pbar.Progress(
            label="Planning route",
            style=pbar.ElapsedBar,
            show=request.progress,
        )

    try:
        # --via routes through named waypoints with its own lane-diversity
        # owner, ahead of the ordinary shape dispatch. It requires --from or
        # --to (validation rejects a fully-unanchored via), and handles every
        # via shape — fixed-terminal, single-anchor open, and loop — itself.
        if request.via_system_ids or request.via_station_ids:
            result = _plan_via_route(
                session, request, started, validation_ms, bubble_cache,
                progress=prog, positioning_caches=positioning_caches,
            )
        elif request.hops == 1:
            result = _plan_single_hop(
                session, request, started, validation_ms, bubble_cache,
                progress=prog, positioning_caches=positioning_caches,
            )
        # Multi-hop endpoint dispatch, mirroring the single-hop dispatcher
        # above. Both endpoints set keeps the fixed-terminal planner (envelope,
        # real budget); --loop runs that same planner with each chain closing
        # on its own origin; one endpoint set runs the single-anchor open
        # engine keyed on which side the planner chooses; both omitted seeds
        # that same open engine from a galaxy-wide set of origins.
        elif (request.from_text and request.to_text) or request.loop:
            result = _plan_multi_hop(
                session, request, started, validation_ms, bubble_cache,
                progress=prog, positioning_caches=positioning_caches,
            )
        elif request.from_text:
            result = _plan_open_anchor_multi_hop(
                session, request, started, validation_ms, bubble_cache,
                open_role="destination",
                progress=prog, positioning_caches=positioning_caches,
            )
        elif request.to_text:
            result = _plan_open_anchor_multi_hop(
                session, request, started, validation_ms, bubble_cache,
                open_role="source",
                progress=prog, positioning_caches=positioning_caches,
            )
        else:
            result = _plan_unanchored_multi_hop(
                session, request, started, validation_ms, bubble_cache,
                progress=prog,
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
    finally:
        prog.clear()

    # --towards: flag any route that reached the target system, so the renderer
    # can report the arrival and how many hops it took.
    if request.towards_target is not None:
        result = _annotate_towards_arrival(request, result)

    # Surface the empty repositioning legs once the trade route is chosen, so
    # every anchored shape shows them without each engine owning the logic.
    if request.start_jumps or request.end_jumps:
        # The positioning BFS runs after the hop spine has cleared, and on a
        # wide --empty-ly bubble it can stall long enough to look like a hang —
        # the failure mode is hitting ^C and binning a finished search. A
        # bounded "working" spinner (no known total, so ElapsedBar) covers the
        # gap so the step reads as alive. It animates on rich's own refresh
        # thread while the BFS blocks; we never tick it, just open and clear it.
        reposition_prog = pbar.Progress(
            label="Repositioning empty jumps",
            style=pbar.ElapsedBar,
            show=request.progress,
        )
        try:
            result = _attach_positioning_legs(
                session, request, result,
                start_cache=positioning_caches["source"],
                end_cache=positioning_caches["destination"],
            )
        finally:
            reposition_prog.clear()
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
    progress=None,
    positioning_caches: dict[str, dict] | None = None,
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
            session, request, started, validation_ms, bubble_cache,
            positioning_caches=positioning_caches,
        )
    if request.from_text:
        return _best_open_ended_plan(
            session, request, started, validation_ms,
            open_role="destination", bubble_cache=bubble_cache,
            progress=progress, positioning_caches=positioning_caches,
        )
    if request.to_text:
        return _best_open_ended_plan(
            session, request, started, validation_ms,
            open_role="source", bubble_cache=bubble_cache,
            progress=progress, positioning_caches=positioning_caches,
        )
    return _plan_unanchored(
        session, request, started, validation_ms, bubble_cache,
        progress=progress,
    )


def _attach_positioning_legs(
    session: Session,
    request: RunRequest,
    result: run_result.RunResult,
    *,
    start_cache: dict,
    end_cache: dict,
) -> run_result.RunResult:
    """Attach the empty repositioning legs for --start-jumps / --end-jumps.

    The trade route is already chosen; this surfaces the unladen flight the
    commander actually flies between the named anchor and the route's trading
    endpoints — anchor -> first station for --start-jumps, last station ->
    anchor for --end-jumps. Computed once here so no route engine grows its own
    positioning-leg logic.

    Empty jumps use the unladen range (--empty-ly, else --ly-per) and the
    positioning count, which differ from the per-hop bubble. ``start_cache`` and
    ``end_cache`` are the request-scoped positioning caches plan_route already
    populated during endpoint expansion, each pinned to its role's single
    (jumps, empty_ly, avoid) configuration — so the anchor bubble is reused here,
    not rebuilt. The end leg is plotted anchor -> terminal (centred on the
    cached anchor bubble) and reversed, since the jump graph is undirected.
    """

    empty_ly = float(request.empty_ly_per or request.max_ly_per_jump or 0.0)

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
                bubble_cache=start_cache,
                avoid_system_ids=request.avoid_system_ids,
            )
        if end_anchor is not None and route.stations:
            # Plot anchor -> terminal so the cached destination-anchor bubble is
            # reused, then reverse to the flown terminal -> anchor orientation.
            # The end anchor is a destination, not an origin, so it gets no
            # origin carve-out — matching the bubble the destination expansion
            # cached, and so the reversed leg never flies into an avoided --to.
            end_leg = reverse_jump_path(
                plan_jump_path(
                    end_anchor,
                    _system_from_station(route.stations[-1]),
                    max_jumps_per_hop=request.end_jumps,
                    max_ly_per_jump=empty_ly,
                    session=session,
                    bubble_cache=end_cache,
                    avoid_system_ids=request.avoid_system_ids,
                    exempt_anchor_from_avoid=False,
                )
            )
        new_routes.append(
            dataclasses.replace(
                route,
                start_positioning=start_leg,
                end_positioning=end_leg,
            )
        )
    return dataclasses.replace(result, routes=tuple(new_routes))
