"""Trade run planner orchestration and dispatch."""

from __future__ import annotations

import time

from sqlalchemy.orm import Session

from . import run_result
from .cargo import reset_cargo_counters
from .route_anchored import _plan_multi_hop
from .route_common import _elapsed_ms
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

    if request.hops == 1:
        return _plan_single_hop(
            session, request, started, validation_ms, bubble_cache
        )
    # Multi-hop endpoint dispatch, mirroring the single-hop dispatcher above.
    # Both endpoints set keeps the fixed-terminal planner (envelope, real
    # budget); one endpoint set runs the single-anchor open engine keyed on
    # which side the planner chooses; both omitted seeds that same open engine
    # from a galaxy-wide set of origins.
    if request.from_text and request.to_text:
        return _plan_multi_hop(
            session, request, started, validation_ms, bubble_cache
        )
    if request.from_text:
        return _plan_open_anchor_multi_hop(
            session, request, started, validation_ms, bubble_cache,
            open_role="destination",
        )
    if request.to_text:
        return _plan_open_anchor_multi_hop(
            session, request, started, validation_ms, bubble_cache,
            open_role="source",
        )
    return _plan_unanchored_multi_hop(
        session, request, started, validation_ms, bubble_cache
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
