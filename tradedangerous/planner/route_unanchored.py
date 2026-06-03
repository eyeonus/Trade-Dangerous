"""Fully-unanchored multi-hop planning (both endpoints omitted): seed the shared open-anchor engine from galaxy-wide origins and grow forward."""

from __future__ import annotations

import time
from dataclasses import replace

from sqlalchemy.orm import Session

from . import data_gateway, failures, run_result
from .run_request import RunRequest

from .route_common import (
    _FrontierNode,
    _MULTIHOP_FRONTIER_WIDTH,
    _elapsed_ms,
    _plan_open_anchor_route,
)


def _plan_unanchored_multi_hop(
    session: Session,
    request: RunRequest,
    started: float,
    validation_ms: float,
    bubble_cache: dict[int, object],
) -> run_result.RunResult:
    """Plan an N-hop route with neither endpoint named — the planner picks all.

    This is the fully-unanchored multi-hop search — neither --from nor --to
    given — seeded from galaxy-wide origins instead of one named system. The unanchored
    one-hop candidate fetch already does the expensive, narrowed galaxy scan
    and returns a bounded, ranked set of (source, destination) trades; the
    source stations of those trades are good places to start a route. Seed the
    forward open-anchor engine on them and let it grow toward destinations.

    The seed is far wider than the beam (hundreds of sources against a width of
    fifty), so it is trimmed here before the engine sees it: the engine expands
    every seed node, so an untrimmed seed would blow up the first layer. The
    trim ranks each source by a realisable-profit proxy — its best candidate's
    per-unit profit times the tonnage actually realisable on that trade — which
    mirrors how the fetch ranks pairs in SQL (_realisable_profit_expression).
    """

    market_started = time.perf_counter()
    candidates, unanchored_counters = (
        data_gateway.fetch_unanchored_trade_candidates(
            session, request, bubble_cache
        )
    )
    if not candidates:
        raise failures.NoProfitableTrades(
            "No profitable trades were found anywhere within range."
        )

    # Rank each source by the best realisable-profit proxy among its
    # candidates: profit_per_unit times the realisable tonnage — the smaller of
    # supply, effective demand, and the per-request ceiling (capacity, narrowed
    # by --limit when set). Recomputed from fields the TradeCandidate already
    # carries; no extra query and no cargo fit just to rank the seed.
    ceiling = int(request.capacity_units or 0)
    per_item_limit = request.cargo_limit_per_item
    if per_item_limit and per_item_limit > 0:
        ceiling = min(ceiling, per_item_limit)

    best_rank_by_source: dict[int, int] = {}
    for candidate in candidates:
        realisable = min(
            ceiling,
            candidate.source_supply_units,
            candidate.effective_destination_demand_units,
        )
        seed_rank = candidate.profit_per_unit * realisable
        source_id = candidate.source_station_id
        if seed_rank > best_rank_by_source.get(source_id, -1):
            best_rank_by_source[source_id] = seed_rank

    # Only the source stations are materialised — the engine resolves the rest
    # as it expands forward.
    station_map = data_gateway.fetch_stations_by_id(
        session, tuple(best_rank_by_source)
    )
    station_filter_ms = _elapsed_ms(market_started)

    # Trim to the beam width on the seed rank, station-id breaking ties so the
    # cut is deterministic. The hop-0 nodes start zeroed: a route has no profit
    # before its first hop, and the forward credit-correction pass re-derives
    # the real figures from the running budget regardless.
    seed_sources = sorted(
        best_rank_by_source,
        key=lambda sid: (-best_rank_by_source[sid], sid),
    )[:_MULTIHOP_FRONTIER_WIDTH]
    seed_frontier: list[_FrontierNode] = [
        _FrontierNode(
            station=station_map[source_id],
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
        for source_id in seed_sources
    ]

    result = _plan_open_anchor_route(
        session,
        request,
        started,
        validation_ms,
        0.0,                # resolution_ms: nothing to resolve, no named endpoint
        station_filter_ms,  # the galaxy seed-fetch cost
        bubble_cache,
        seed_frontier=seed_frontier,
        open_role="destination",
    )

    # The engine builds the multi-hop diagnostics but never saw the galaxy
    # scan, so the planner that did that work attaches its counters here.
    return replace(
        result,
        diagnostics=replace(
            result.diagnostics,
            unanchored_pairs_examined=unanchored_counters.pairs_examined,
            unanchored_pairs_accepted=unanchored_counters.pairs_accepted,
            unanchored_bubble_systems=unanchored_counters.bubble_systems,
            unanchored_per_commodity_cap_hits=(
                unanchored_counters.per_commodity_cap_hits
            ),
        ),
    )
