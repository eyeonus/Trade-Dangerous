"""Plain text renderer for trade run planner results."""

from __future__ import annotations

from .run_result import (
    PartialRouteWarning,
    PlannedHop,
    PlannedRoute,
    PlannerDiagnostics,
    RunResult,
)


def render_run_result(result: RunResult) -> str:
    """Render route results as human-readable trade instructions."""

    lines: list[str] = []

    # Surface planner warnings (e.g. partial multi-hop routes) before the route
    # block so the reader sees them before reading the trade plan.
    for warning in result.warnings:
        lines.append(f"WARNING: {_render_warning(warning)}")
    if result.warnings and result.routes:
        lines.append("")

    for route_index, route in enumerate(result.routes, start=1):
        if len(result.routes) > 1:
            lines.append(f"Route {route_index}")

        lines.extend(_render_route(route))

        if route_index < len(result.routes):
            lines.append("")

    # Multi-hop diagnostic summary, appended after the route. Single-hop
    # diagnostics are not surfaced here; the multi-hop fields stay at their
    # defaults for any single-hop run and the block is skipped.
    lines.extend(_render_multihop_diagnostics(result.diagnostics))

    return "\n".join(lines)


def _render_warning(warning: PartialRouteWarning) -> str:
    """Render structured planner warnings as user-facing text."""

    if warning.phase == "final":
        if warning.reason == "no_reachable_route":
            detail = "no reachable final hop was found"
        else:
            detail = "no viable final hop was found"
    else:
        detail = (
            f"no viable continuation was found after hop "
            f"{warning.completed_hops}"
        )

    return (
        f"Requested {warning.requested_hops} hops, but {detail}. "
        f"Showing the best {warning.completed_hops}-hop partial route found."
    )


def _render_route(route: PlannedRoute) -> list[str]:
    lines = [
        (
            f"{route.stations[0].dbname} -> "
            f"{route.stations[-1].dbname}"
        ),
        f"Total gain: {route.total_raw_profit:n} cr",
        f"Final credits: {route.ending_credits:n} cr",
    ]

    if route.total_practical_score != route.total_raw_profit:
        lines.append(f"Practical score: {route.total_practical_score:,.0f}")

    for hop_index, hop in enumerate(route.hops, start=1):
        lines.append("")
        lines.extend(_render_hop(hop, hop_index))

    return lines


def _render_hop(hop: PlannedHop, hop_index: int) -> list[str]:
    lines = [
        f"Hop {hop_index}:",
        f"  Buy at {hop.source_station.dbname}",
    ]

    for line in hop.cargo.lines:
        lines.append(
            "    "
            f"{line.quantity:n} x {line.item_name} "
            f"@ {line.buy_price:n} cr "
            f"-> {line.sell_price:n} cr "
            f"(+{line.total_profit:n} cr)"
        )

    if any(
        line.bulk_sale_tax_sensitive
        and line.quantity == line.effective_destination_demand_units
        for line in hop.cargo.lines
    ):
        lines.append(
            "    Metals/Minerals capped at 25% of destination demand "
            "to avoid the bulk-sale price reduction."
        )

    lines.append(f"  Fly to {hop.destination_station.dbname}")

    if hop.jump_path.is_same_system:
        lines.append("    Same-system supercruise")
    else:
        path = " -> ".join(system.name for system in hop.jump_path.systems)
        lines.append(
            f"    {hop.jump_path.jumps:n} jump(s), "
            f"{hop.jump_path.distance_ly:.2f} ly: {path}"
        )

    lines.append(f"  Sell cargo for {hop.raw_profit:n} cr gain")
    return lines


def _render_multihop_diagnostics(diagnostics: PlannerDiagnostics) -> list[str]:
    """Render the compact multi-hop instrumentation block.

    Multi-hop runs surface their per-layer, per-call, and final-hop counts
    here so the timing and pruning shape is visible in normal output. A
    single-hop run leaves the multi-hop fields at defaults and gets no
    block. The format aims to fit one block on screen rather than dumping
    every counter onto its own line.
    """

    if diagnostics.hops_planned <= 1:
        return []

    lines = ["", "Diagnostics:"]
    lines.append(
        f"  Total: {diagnostics.total_planner_ms:.0f}ms "
        f"(resolution {diagnostics.resolution_ms:.0f}ms, "
        f"station-filter {diagnostics.station_filter_ms:.0f}ms, "
        f"search {diagnostics.market_query_ms:.0f}ms)"
    )

    expansion = diagnostics.multihop_expansion_stats
    if expansion is not None and expansion.expansion_calls > 0:
        lines.append(
            f"  Expansion: {expansion.expansion_calls} calls, "
            f"memo {expansion.memo_hits}/{expansion.memo_misses} hit/miss, "
            f"{expansion.candidate_rows:n} candidate rows, "
            f"{expansion.grouped_pairs:n} pairs, "
            f"{expansion.cargo_calls:n} cargo calls, "
            f"{expansion.children_returned:n} children, "
            f"{expansion.elapsed_ms:.0f}ms"
        )

    for layer in diagnostics.multihop_layers:
        lines.append(
            f"  Layer {layer.layer_index}: "
            f"{layer.frontier_size_in} in, "
            f"{layer.expansion_calls} calls, "
            f"{layer.children_generated:n} children, "
            f"kept {layer.children_kept} "
            f"({layer.elapsed_ms:.0f}ms)"
        )

    final_hop = diagnostics.multihop_final_hop_stats
    if final_hop is not None and final_hop.frontier_nodes_attempted > 0:
        lines.append(
            f"  Final hop: "
            f"{final_hop.frontier_nodes_attempted} attempted, "
            f"{final_hop.nodes_with_reachable_destination} reach destination, "
            f"{final_hop.market_candidates_found:n} market candidates, "
            f"{final_hop.viable_cargo_plans} viable, "
            f"{final_hop.elapsed_ms:.0f}ms"
        )

    return lines