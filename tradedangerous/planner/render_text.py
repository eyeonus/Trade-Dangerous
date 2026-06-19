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

# Block layout. Every detail line under a hop is a label in a fixed-width
# field followed by its data, so the data columns line up down the block and a
# multi-commodity hop reads like a small ledger. Continuation lines (extra
# commodities, a wrapped note, an overflowing total) indent to the same data
# column with no label.
_INDENT = 2
_LABEL_W = 8
_DATA_COL = _INDENT + _LABEL_W
_WIDTH = 80


def _fmt(value: int) -> str:
    """Group an integer with thousands separators (``1,289,880``).

    Uses an explicit comma rather than locale-aware ``:n`` so grouping is
    consistent regardless of the environment's locale (``:n`` silently groups
    nothing when the locale is unset). Centralised so a column's computed width
    and its rendered text always use the same formatting — otherwise the
    padding would drift from the real text.
    """

    return f"{value:,}"


def _labelled(label: str, data: str) -> str:
    """First line of a block — ``  Label:   data`` — with the label padded so
    every block's data column starts in the same place."""

    return f"{' ' * _INDENT}{label + ':':<{_LABEL_W}}{data}"


def _cont(data: str) -> str:
    """Continuation line: indented to the data column, no label."""

    return f"{' ' * _DATA_COL}{data}"


def render_run_result(result: RunResult, *, debug: int = 0) -> str:
    """Render route results as human-readable trade instructions.

    The diagnostics block is debug output, not normal or verbose output, so it
    is emitted only at debug level 2 and up (``-ww``). ``debug`` defaults to 0,
    so a caller that does not pass it gets a clean, diagnostics-free render.
    """

    lines: list[str] = []

    # Surface planner warnings (e.g. partial multi-hop routes) before the route
    # block so the reader sees them before reading the trade plan.
    for warning in result.warnings:
        lines.append(f"WARNING: {_render_warning(warning)}")
    if result.warnings and result.routes:
        lines.append("")

    # --routes N can return several routes; number them when there is more than
    # one and separate them with a blank line.
    multi = len(result.routes) > 1
    for route_index, route in enumerate(result.routes, start=1):
        lines.extend(
            _render_route(route, route_index if multi else None, debug)
        )
        if route_index < len(result.routes):
            lines.append("")

    # Diagnostics are debug output: noisy, useful in development, not for the
    # ordinary user. Gate them behind -ww (debug level 2) and up.
    if debug >= 2:
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


def _render_route(
    route: PlannedRoute, number: int | None = None, debug: int = 0
) -> list[str]:
    """Render one route: a header line, one block per hop, then a summary.

    Each hop is a complete deal — buy at its source, fly, sell at its
    destination — so the block names both endpoints and the hop count matches
    --hops exactly. The shared dock between consecutive hops shows up as the
    end of one hop and the start of the next. Cumulative profit and the running
    credit balance are threaded across the hops here.

    The closing summary (multi-hop only) restates the route totals at the foot,
    where a journey's bottom line belongs. A single hop needs no summary — its
    own profit line already is the total — so any route-level note (practical
    score, --towards arrival) is appended on its own instead.
    """

    hop_count = len(route.hops)
    hop_word = "hop" if hop_count == 1 else "hops"
    label = "Route" if number is None else f"Route {number}"
    lines = [
        f"{label}: {route.stations[0].dbname} -> "
        f"{route.stations[-1].dbname}   ({hop_count} {hop_word})"
    ]

    if route.start_positioning is not None:
        lines.append("")
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
                hop, hop_index, route.starting_credits, cumulative_profit
            )
        )
        cumulative_profit += hop.raw_profit

    if route.end_positioning is not None:
        lines.append("")
        lines.append(
            _render_positioning("Empty jumps from end", route.end_positioning)
        )

    conditionals = _route_conditionals(route, debug)
    if hop_count > 1:
        lines.append("")
        lines.extend(_render_summary(route, conditionals))
    else:
        # No summary for a one-hop route, but route-level notes still need a
        # home, so trail them under the single hop.
        for note in conditionals:
            lines.append("")
            lines.append(f"  {note}")

    return lines


def _route_conditionals(route: PlannedRoute, debug: int = 0) -> list[str]:
    """Route-level notes that only appear when they apply.

    The practical score is a debug extra (``-w`` and up): the planner's
    route-ranking value — raw profit weighted by the ls-distance curve, which
    rewards stations close to the arrival star and penalises distant ones, so
    it can sit either side of raw profit. Not credits the Cmdr banks, so it
    stays out of normal output. The arrival line is shown whenever --towards
    reached its target, since the route may have stopped before spending every
    --hops.
    """

    notes: list[str] = []
    if (
        debug >= 1
        and route.total_practical_score != route.total_raw_profit
    ):
        notes.append(
            f"Practical score: {route.total_practical_score:,.0f}"
        )
    if route.arrival_hops is not None:
        hop_word = "hop" if route.arrival_hops == 1 else "hops"
        notes.append(
            f"Arrived at {route.stations[-1].system_name} after "
            f"{route.arrival_hops} {hop_word}"
        )
    return notes


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
    """Render one complete hop: header, Buy, Travel, Sell, Profit.

    The block reads top to bottom in the order a Cmdr flies it — load at the
    source, fly, sell at the destination, bank the profit. starting_credits and
    cumulative_before thread through so the closing line can show the post-sale
    balance raw (what shows up in the in-game balance), not the planner-internal
    margin-adjusted figure.
    """

    lines = [
        f"Hop {hop_index}:  {hop.source_station.dbname} -> "
        f"{hop.destination_station.dbname}"
    ]

    cargo = hop.cargo.lines
    # Quantity and name columns are shared between the Buy and Sell blocks (same
    # commodities, same amounts), so width them once.
    qty_w = max(len(_fmt(line.quantity)) for line in cargo)
    name_w = max(len(line.item_name) for line in cargo)

    # Buy block — one line per commodity, columns aligned.
    bprice_w = max(len(_fmt(line.buy_price)) for line in cargo)
    btotal_w = max(len(_fmt(line.total_cost)) for line in cargo)
    for index, line in enumerate(cargo):
        data = (
            f"{_fmt(line.quantity):>{qty_w}} t {line.item_name:<{name_w}} "
            f"@ {_fmt(line.buy_price):>{bprice_w}} cr/t "
            f"= {_fmt(line.total_cost):>{btotal_w}} cr"
        )
        lines.append(_labelled("Buy", data) if index == 0 else _cont(data))

    # The bulk-sale-tax cap binds when a sensitive commodity's loaded quantity
    # equals the (already 25%-capped) destination demand. Note it under Buy,
    # wrapped to stay inside 80 columns.
    if any(
        line.bulk_sale_tax_sensitive
        and line.quantity == line.effective_destination_demand_units
        for line in cargo
    ):
        lines.append(
            _labelled(
                "Note",
                "Metals/Minerals capped at 25% of destination demand to",
            )
        )
        lines.append(_cont("avoid the bulk-sale price reduction."))

    # Travel — direct (no path), same-system supercruise, or a jump path.
    if hop.jump_path is None:
        travel = "Direct: plot your own jump route"
    elif hop.jump_path.is_same_system:
        travel = "Same-system supercruise"
    else:
        path = " -> ".join(system.name for system in hop.jump_path.systems)
        jump_word = "jump" if hop.jump_path.jumps == 1 else "jumps"
        travel = (
            f"{_fmt(hop.jump_path.jumps)} {jump_word}, "
            f"{hop.jump_path.distance_ly:.2f} ly  ({path})"
        )
    lines.append(_labelled("Travel", travel))

    # Sell block — mirrors Buy, with per-tonne and line profit folded onto the
    # line; the profit note drops to its own line if it would overflow 80.
    sprice_w = max(len(_fmt(line.sell_price)) for line in cargo)
    svalue_w = max(
        len(_fmt(line.quantity * line.sell_price)) for line in cargo
    )
    for index, line in enumerate(cargo):
        sale_value = line.quantity * line.sell_price
        data = (
            f"{_fmt(line.quantity):>{qty_w}} t {line.item_name:<{name_w}} "
            f"@ {_fmt(line.sell_price):>{sprice_w}} cr/t "
            f"= {_fmt(sale_value):>{svalue_w}} cr"
        )
        profit = (
            f"(+{_fmt(line.profit_per_unit)} cr/t "
            f"= {_fmt(line.total_profit)} cr)"
        )
        head = _labelled("Sell", data) if index == 0 else _cont(data)
        if len(head) + 2 + len(profit) <= _WIDTH:
            lines.append(f"{head}  {profit}")
        else:
            lines.append(head)
            lines.append(_cont(profit))

    # Hop close — profit banked this hop, the running cumulative, and the
    # post-sale credit balance. Split across two lines if the figures would
    # push past 80 columns.
    cumulative_after = cumulative_before + hop.raw_profit
    credits_after = starting_credits + cumulative_after
    close = (
        f"hop {_fmt(hop.raw_profit)} "
        f"| cumulative profit {_fmt(cumulative_after)} cr "
        f"| balance {_fmt(credits_after)} cr"
    )
    head = _labelled("Profit", close)
    if len(head) <= _WIDTH:
        lines.append(head)
    else:
        lines.append(
            _labelled(
                "Profit",
                f"hop {_fmt(hop.raw_profit)} "
                f"| cumulative profit {_fmt(cumulative_after)} cr",
            )
        )
        lines.append(_cont(f"balance {_fmt(credits_after)} cr"))

    return lines


def _render_summary(
    route: PlannedRoute, conditionals: list[str]
) -> list[str]:
    """The closing route summary — totals at the foot of a multi-hop route.

    Carries the route shape (hops, jumps, total distance) and the bottom line
    (start to final credits, total profit), plus any route-level conditional
    notes folded in. Same-system supercruise and --direct legs are not jumps,
    so they contribute nothing to the jump and distance totals.
    """

    hop_count = len(route.hops)
    total_jumps = 0
    total_ly = 0.0
    for hop in route.hops:
        leg = hop.jump_path
        if leg is not None and not leg.is_same_system:
            total_jumps += leg.jumps
            total_ly += leg.distance_ly

    hop_word = "hop" if hop_count == 1 else "hops"
    jump_word = "jump" if total_jumps == 1 else "jumps"
    lines = [
        "Summary:",
        f"  {hop_count} {hop_word}, {total_jumps} {jump_word}, "
        f"{total_ly:.2f} ly",
        f"  Start {_fmt(route.starting_credits)} cr  ->  "
        f"Final {_fmt(route.ending_credits)} cr",
        f"  Total profit {_fmt(route.total_raw_profit)} cr",
    ]
    for note in conditionals:
        lines.append(f"  {note}")
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
        if expansion.stream_stations_read or expansion.stream_stops:
            lines.append(
                f"  Stream: {expansion.stream_rows_read:n} rows read, "
                f"{expansion.stream_stations_read:n} stations consumed, "
                f"{expansion.stream_stops:n} early stops"
            )
        if expansion.loose_envelopes_dropped:
            lines.append(
                f"  Envelope: dropped as provably loose on "
                f"{expansion.loose_envelopes_dropped:n} of "
                f"{expansion.expansion_calls:n} expansion calls"
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
