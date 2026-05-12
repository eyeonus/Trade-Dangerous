"""Plain text renderer for trade run planner results."""

from __future__ import annotations

from .run_result import PlannedHop, PlannedRoute, RunResult


def render_run_result(result: RunResult) -> str:
    """Render route results as human-readable trade instructions."""

    lines: list[str] = []

    for route_index, route in enumerate(result.routes, start=1):
        if len(result.routes) > 1:
            lines.append(f"Route {route_index}")

        lines.extend(_render_route(route))

        if route_index < len(result.routes):
            lines.append("")

    return "\n".join(lines)


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