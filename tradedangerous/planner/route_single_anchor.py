"""Part-anchored multi-hop planning (one open end): resolve the anchor, build the seed, hand off to the shared open-anchor engine."""

from __future__ import annotations

import time

from sqlalchemy.orm import Session

from . import run_result
from .run_request import RunRequest

from .route_common import (
    _FrontierNode,
    _elapsed_ms,
    _plan_open_anchor_route,
    _revisit_seed,
    _stations_from_endpoint,
)


def _plan_open_anchor_multi_hop(
    session: Session,
    request: RunRequest,
    started: float,
    validation_ms: float,
    bubble_cache: dict[int, object],
    *,
    open_role: str,
    progress=None,
) -> run_result.RunResult:
    """Plan an N-hop route with one fixed endpoint and the other open.

    The single-anchor front for both open multi-hop shapes, keyed on
    ``open_role`` — the trade role of the endpoint the planner selects:

      open_role="source"       --to Y, --from omitted: the route grows backward
                               from Y; the emerged origin is the last layer.
      open_role="destination"  --from X, --to omitted: the route grows forward
                               from X; the emerged destination is the last layer.

    This front resolves the fixed endpoint, builds the seed frontier from its
    eligible stations, and hands off to the shared open-anchor engine
    (_plan_open_anchor_route), which runs the credit-optimistic expansion and the
    forward credit-correction pass. The fully-unanchored planner reuses that same
    engine with a galaxy-wide seed.
    """

    # The fixed endpoint (the seed) is the one the user supplied; its trade role
    # is the opposite of open_role. open_role="source" anchors on --to as the
    # destination; open_role="destination" anchors on --from as the source.
    # The anchor endpoint was resolved once at dispatch; read the canonical DTO.
    if open_role == "source":
        anchor_endpoint = request.to_endpoint
        anchor_role = "destination"
    else:
        anchor_endpoint = request.from_endpoint
        anchor_role = "source"
    resolution_ms = 0.0

    station_filter_started = time.perf_counter()
    anchor_stations = _stations_from_endpoint(
        session,
        anchor_endpoint,
        request,
        role=anchor_role,
    )
    station_filter_ms = _elapsed_ms(station_filter_started)

    # Seed: the fixed endpoint's eligible stations at hop_index 0, no cargo.
    seed_frontier: list[_FrontierNode] = [
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
            visited_order=_revisit_seed(station.station_id, request),
        )
        for station in anchor_stations
    ]

    return _plan_open_anchor_route(
        session,
        request,
        started,
        validation_ms,
        resolution_ms,
        station_filter_ms,
        bubble_cache,
        seed_frontier=seed_frontier,
        open_role=open_role,
        progress=progress,
    )
