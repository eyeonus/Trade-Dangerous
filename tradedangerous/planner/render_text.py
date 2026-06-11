"""Plain text renderer for trade run planner results."""

from __future__ import annotations

from .run_result import (
    JumpPath,
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
    """Render one route: a header block followed by one block per hop.

    The header carries the figures that scope the route as a whole — endpoints,
    starting credits, total profit, final credits, and the practical score when
    it differs from raw profit. Per-hop blocks repeat the same shape so a
    multi-hop route is readable straight through. Cumulative profit and the
    running credit balance are tracked here and threaded into each hop.
    """

    lines = [
        "Route:",
        (
            f"  {route.stations[0].dbname} -> "
            f"{route.stations[-1].dbname}"
        ),
        f"  Starting credits: {route.starting_credits:n} cr",
        f"  Total route profit: {route.total_raw_profit:n} cr",
        f"  Final credits: {route.ending_credits:n} cr",
    ]

    if route.total_practical_score != route.total_raw_profit:
        lines.append(
            f"  Practical score: {route.total_practical_score:,.0f}"
        )

    # --towards: the route reached the target system. Report the arrival and the
    # hop count, since the route may have stopped before using every --hops.
    if route.arrival_hops is not None:
        hop_word = "hop" if route.arrival_hops == 1 else "hops"
        lines.append(
            f"  Arrived at {route.stations[-1].system_name} after "
            f"{route.arrival_hops} {hop_word}"
        )

    if route.start_positioning is not None:
        lines.append(
            _render_positioning(
                "Empty jumps to start", route.start_positioning
            )
        )

    cumulative_profit = 0
    for hop_index, hop in enumerate(route.hops, start=1):
        lines.append("")
        lines.extend(
            _render_hop(
                hop,
                hop_index,
                route.starting_credits,
                cumulative_profit,
            )
        )
        cumulative_profit += hop.raw_profit

    if route.end_positioning is not None:
        lines.append("")
        lines.append(
            _render_positioning("Empty jumps from end", route.end_positioning)
        )

    return lines


def _render_positioning(label: str, leg: JumpPath) -> str:
    """Render one empty repositioning leg (--start-jumps / --end-jumps).

    A single readable line in the same shape as a hop's Travel line. Same-system
    means the chosen trade station shares the anchor's system, so no empty jump
    is flown; an unreachable leg is reported softly rather than dropped.
    """

    if leg.is_same_system:
        system = leg.systems[0].name if leg.systems else ""
        return f"  {label}: same system ({system}), no positioning jump"
    if not leg.is_reachable:
        return f"  {label}: no empty path found within range"
    path = " -> ".join(system.name for system in leg.systems)
    return (
        f"  {label}: {leg.jumps:n} jump(s), "
        f"{leg.distance_ly:.2f} ly: {path}"
    )


def _render_hop(
    hop: PlannedHop,
    hop_index: int,
    starting_credits: int,
    cumulative_before: int,
) -> list[str]:
    """Render one hop: From, Buy, Travel, To, Sell, Hop totals.

    The blocks read top to bottom in the order a Cmdr would actually fly the
    hop. starting_credits and cumulative_before are passed in so the hop
    totals block can show the post-sale credit balance — raw, not margin-
    adjusted, since the displayed figure should match what shows up in the
    in-game balance.
    """

    lines = [
        f"Hop {hop_index}:",
        f"  From: {hop.source_station.dbname}",
        "",
        "  Buy:",
    ]
    for line in hop.cargo.lines:
        lines.append(
            f"    {line.quantity:n} t {line.item_name} "
            f"@ {line.buy_price:n} cr/t = {line.total_cost:n} cr"
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

    lines.append("")
    lines.append("  Travel:")
    if hop.jump_path is None:
        # --direct carries no jump path: the commander plots the route.
        lines.append("    Direct: plot your own jump route")
    elif hop.jump_path.is_same_system:
        lines.append("    Same-system supercruise")
    else:
        path = " -> ".join(system.name for system in hop.jump_path.systems)
        lines.append(
            f"    {hop.jump_path.jumps:n} jump(s), "
            f"{hop.jump_path.distance_ly:.2f} ly: {path}"
        )

    lines.append("")
    lines.append(f"  To: {hop.destination_station.dbname}")
    lines.append("")
    lines.append("  Sell:")
    total_sale_value = 0
    for line in hop.cargo.lines:
        sale_value = line.quantity * line.sell_price
        total_sale_value += sale_value
        lines.append(
            f"    {line.quantity:n} t {line.item_name} "
            f"@ {line.sell_price:n} cr/t = {sale_value:n} cr"
        )
        lines.append(
            f"      Profit: {line.profit_per_unit:n} cr/t, "
            f"{line.total_profit:n} cr total"
        )

    cumulative_after = cumulative_before + hop.raw_profit
    credits_after_sale = starting_credits + cumulative_after

    lines.append("")
    lines.append("  Hop totals:")
    lines.append(f"    Buy cost: {hop.cargo.total_cost:n} cr")
    lines.append(f"    Sale value: {total_sale_value:n} cr")
    lines.append(f"    Hop profit: {hop.raw_profit:n} cr")
    lines.append(f"    Cumulative profit: {cumulative_after:n} cr")
    lines.append(f"    Credits after sale: {credits_after_sale:n} cr")

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
        # Single-hop runs have no frontier/layer machinery, but the same phase
        # timings, candidate count, and cargo split a multi-hop run reports are
        # all tracked — surface them so a ticket from any route shape carries
        # comparable diagnostics.
        lines = [
            "",
            "Diagnostics:",
            f"  Total: {diagnostics.total_planner_ms:.0f}ms "
            f"(station-filter {diagnostics.station_filter_ms:.0f}ms, "
            f"market {diagnostics.market_query_ms:.0f}ms, "
            f"reachability {diagnostics.reachability_ms:.0f}ms, "
            f"cargo {diagnostics.cargo_optimisation_ms:.0f}ms)",
        ]
        if diagnostics.candidate_trade_count:
            lines.append(
                f"  Candidates: {diagnostics.candidate_trade_count:n} trades"
            )
        lines.append(
            f"  Cargo: {diagnostics.cargo_fast_path_hits:n} fast-path, "
            f"{diagnostics.cargo_recursive_hits:n} branch-and-bound, "
            f"{diagnostics.cargo_pruned_solves:n} pruned, "
            f"{diagnostics.cargo_optimisation_ms:.0f}ms"
        )
        if (
            diagnostics.unanchored_pairs_examined
            or diagnostics.unanchored_pairs_accepted
        ):
            lines.append(
                f"  Unanchored: "
                f"{diagnostics.unanchored_pairs_examined:n} examined, "
                f"{diagnostics.unanchored_pairs_accepted:n} accepted, "
                f"{diagnostics.unanchored_bubble_systems:n} bubble systems, "
                f"{diagnostics.unanchored_per_commodity_cap_hits:n} cap hits"
            )
        return lines

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
        lines.append(
            f"  Expansion phases: "
            f"fetch {expansion.fetch_ms:.0f}ms, "
            f"cargo {expansion.cargo_ms:.0f}ms, "
            f"jump {expansion.jump_ms:.0f}ms"
        )
        if expansion.qual_ms > 0 or expansion.qual_stations:
            lines.append(
                f"  Qualification: {expansion.qual_stations:n} stations, "
                f"{expansion.qual_rows:n} rows cached, "
                f"{expansion.qual_ms:.0f}ms"
            )

    if (
        diagnostics.cargo_fast_path_hits
        or diagnostics.cargo_recursive_hits
        or diagnostics.cargo_pruned_solves
    ):
        lines.append(
            f"  Cargo: {diagnostics.cargo_fast_path_hits:n} fast-path, "
            f"{diagnostics.cargo_recursive_hits:n} branch-and-bound, "
            f"{diagnostics.cargo_pruned_solves:n} pruned, "
            f"{diagnostics.cargo_optimisation_ms:.0f}ms"
        )

    correction = diagnostics.multihop_correction_stats
    if correction is not None and correction.finalists_generated > 0:
        lines.append(
            f"  Correction: {correction.finalists_generated} finalists, "
            f"{correction.finalists_attempted} attempted, "
            f"{correction.finalists_corrected} corrected, "
            f"{correction.cargo_calls:n} cargo calls "
            f"({correction.fast_path_hits:n} fast-path, "
            f"{correction.branch_and_bound_hits:n} b&b), "
            f"{correction.elapsed_ms:.0f}ms"
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