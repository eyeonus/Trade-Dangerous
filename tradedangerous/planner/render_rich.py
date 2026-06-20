"""Rich (formatted) renderer for trade run planner results.

This is the default ``trade run`` output: a colour table built on the ``rich``
library, pinned to 80 columns by the caller. The plain-text renderer in
``render_text`` is the ``--raw`` alternative; the warning, positioning,
diagnostics, and route-note text is shared from there so the two formats stay
in step.

Three rich tiers share one table; they differ only in how much each cell holds.
``--summary`` is the bare glance — destination, a comma-separated load, jump
count, profit. ``standard`` (the default) stacks the load with buy prices, adds
the nav route under each destination, and leaves a blank line between hops.
``-v`` verbose switches to a station-centric layout — a row per stop, showing
what you sell on arrival and what you buy before leaving, with the jumps under
each station — so it reads the way the route is actually flown.
(``--raw`` is the plain-text format, handled in ``render_text``.) All three
share the route header, the totals line, and the route notes.
"""

from __future__ import annotations

import math

from rich import box
from rich.console import Group
from rich.table import Table
from rich.text import Text

from .render_text import (
    _render_multihop_diagnostics,
    _render_positioning,
    _render_warning,
    _route_conditionals,
)
from .run_result import CargoLine, PlannedHop, PlannedRoute, RunResult

# Styles mirror the route styles defined on the rich theme in tradeenv
# (text_seq_first / text_seq_last / text_itm_name …). Hardcoded here for now;
# wiring them to the live tdenv theme is a later refinement.
_ORIGIN = "#6cd5e5"
_DEST = "#6aadf0"
_PROFIT = "#45d380"
_HEADING = "bold"
_DIM = "dim"

# Data colours derived from the Elite orange chrome (_CHROME) on the colour
# wheel: gold is analogous to orange, azure is its complement, emerald a
# balanced tetrad partner — so the palette harmonises rather than just sharing
# screen space. Origin is a soft cyan beside the azure destinations. The three
# coloured columns (To, Load, Profit) alternate a medium and a lighter shade of
# their hue row to row, in sync, so a row reads as a whole and a folded name
# stays with its hop. Truecolor hex; rich downgrades on terminals without
# 24-bit. _DEST / _PROFIT (header destination, totals figure) reuse the medium.
_DEST_ALT = ("#6aadf0", "#a3ccf5")    # azure — orange's complement
_LOAD_ALT = ("#edcb45", "#f7e497")    # gold — analogous to orange
_PROFIT_ALT = ("#45d380", "#98e1b7")  # emerald — tetrad with orange + azure

# Elite's signature HUD orange, matched to the GUI's Elite theme
# (guiapp/themes.css --q-primary). Used as chrome — the table frame, the column
# headers, and the Total label — so the data glows inside an orange frame the
# way the in-game HUD does, without taking a data colour off the red-green axis.
_CHROME = "#f07b05"

# Advisory amber for the bulk-sale-tax cap — the flag marker on a capped Load
# line and its footnote. Matches the yellow used for warnings, and stands clear
# of the gold Load colour so the flag still reads against it.
_CAP = "yellow"

# A dimmed chrome for the rule between verbose hops — the same HUD orange as the
# frame, attenuated so the inter-hop rules read as quiet dividers rather than
# competing with the header. rich applies the dim attribute over the truecolour.
_CHROME_DIM = f"dim {_CHROME}"

# A light grid: HORIZONTALS frames the table and underlines the header without
# vertical bars, and show_lines stays off so there is no rule between every hop
# — enough structure to break the route up, not a line per row. The box style
# is the easiest knob to make it heavier (MINIMAL/SQUARE/ROUNDED add verticals)
# or lighter (SIMPLE_HEAD drops the frame to just the header rule).
_BOX = box.HORIZONTALS


def render_run_result_rich(
    result: RunResult, *, debug: int = 0, tier: str = "standard"
) -> Group:
    """Build the rich renderable for a planner result.

    ``tier`` selects how much each cell of the hop table carries. ``"summary"``
    is the lean glance; ``"standard"`` (the default) adds the nav route, buy
    prices, and a gap between hops; ``"verbose"`` switches to a station-centric
    table — a row per stop, what you sell and buy there, with a rule between
    stops. All share the header, totals, and notes.

    Returns a rich ``Group`` the caller prints through the shared console. A
    string is never returned here — that is the ``--raw`` path's job.
    """

    blocks: list = []

    for warning in result.warnings:
        blocks.append(
            Text(f"WARNING: {_render_warning(warning)}", style="yellow")
        )
    if result.warnings and result.routes:
        blocks.append(Text(""))

    multi = len(result.routes) > 1
    for index, route in enumerate(result.routes, start=1):
        blocks.extend(
            _route_block(route, index if multi else None, debug, tier)
        )
        if index < len(result.routes):
            blocks.append(Text(""))

    # Diagnostics stay debug-only (-ww) and plain even here — they are dev
    # instrumentation, not part of the formatted route.
    if debug >= 2:
        for line in _render_multihop_diagnostics(result.diagnostics):
            blocks.append(Text(line, style=_DIM))

    # A trailing blank line so the route doesn't butt up against the shell
    # prompt that follows.
    blocks.append(Text(""))

    return Group(*blocks)


def _route_block(
    route: PlannedRoute, number: int | None, debug: int, tier: str
) -> list:
    """One route: a header line, the hop table, then a totals line."""

    hop_count = len(route.hops)
    total_jumps, total_ly = _jump_totals(route)

    blocks: list = [_header_line(route, number, total_jumps, total_ly)]

    if route.start_positioning is not None:
        blocks.append(
            Text(
                _render_positioning(
                    "Empty jumps to start", route.start_positioning
                ),
                style=_DIM,
            )
        )

    if tier == "verbose":
        # Verbose renders station-centric: a row per stop (what you sell on
        # arrival, what you buy before leaving), which reads the way the route
        # is flown. The hop-centric layout in _hop_table is the alternative
        # under evaluation.
        blocks.append(_stops_table(route))
    else:
        blocks.append(_hop_table(route, tier))
        # On the standard tier, flag below the table when the bulk-sale-tax cap
        # shaped any hop's cargo — the flag in the Load column points at which
        # commodity, this line says why.
        if tier == "standard" and any(
            _bulk_capped(line)
            for hop in route.hops
            for line in hop.cargo.lines
        ):
            blocks.append(
                Text(
                    "  ⚑ Metals/Minerals capped at 25% of demand to avoid the "
                    "bulk-sale tax.",
                    style=_CAP,
                )
            )

    if route.end_positioning is not None:
        blocks.append(
            Text(
                _render_positioning(
                    "Empty jumps from end", route.end_positioning
                ),
                style=_DIM,
            )
        )

    # A single hop's profit is already in its row, so it needs no totals line.
    if hop_count > 1:
        blocks.append(_total_line(route))

    # Route-level notes (practical score at -w, --towards arrival).
    for note in _route_conditionals(route, debug):
        blocks.append(Text(f"  {note}", style=_DIM))

    return blocks


def _header_line(
    route: PlannedRoute, number: int | None, total_jumps: int, total_ly: float
) -> Text:
    """The route header: endpoints, then the route shape."""

    hop_count = len(route.hops)
    hop_word = "hop" if hop_count == 1 else "hops"
    jump_word = "jump" if total_jumps == 1 else "jumps"
    label = "" if number is None else f"Route {number}:  "
    header = Text(label, style=_HEADING)
    header.append(route.stations[0].dbname, style=_ORIGIN)
    header.append("  →  ", style=_DIM)
    header.append(route.stations[-1].dbname, style=_DEST)
    header.append(
        f"    {hop_count} {hop_word} · {total_jumps} {jump_word} "
        f"· {total_ly:.2f} ly",
        style=_CHROME,
    )
    return header


def _hop_table(route: PlannedRoute, tier: str) -> Table:
    """The hop table — one row a hop. The same five columns at every tier; what
    changes is how much each cell holds, and the location column is headed "To"
    (the destination) for summary and standard, "Trip" for verbose.

    The location and Load cells fold long text within their column so nothing
    strays to the next line. ``summary`` is the bare row: destination, a comma
    load, jump count, profit. ``standard`` stacks each commodity with its buy
    price and adds the nav route (systems + distance) on a dim line under the
    destination; a blank line (``leading``) keeps the taller rows apart.
    ``verbose`` goes further — the Trip cell names the source you buy at, the
    destination you sell at, and the jumps one per line; the Load cell shows
    every commodity's buy and sell price — and ``show_lines`` rules the hops
    apart in dim chrome rather than a blank gap. Cell building lives in
    ``_to_cell`` / ``_trip_cell`` and ``_load_cell``.
    """

    is_standard = tier == "standard"
    is_verbose = tier == "verbose"

    table = Table(
        box=_BOX,
        show_lines=is_verbose,
        header_style=_CHROME,
        border_style=_CHROME_DIM if is_verbose else _CHROME,
        padding=(0, 1),
        pad_edge=False,
        leading=1 if is_standard else 0,
    )
    table.add_column("Hop", justify="center", no_wrap=True)
    table.add_column("Trip" if is_verbose else "To", overflow="fold")
    table.add_column("Load", overflow="fold")
    # "Jmp" not "Jumps": the count is one or two digits, so the long header was
    # the only thing widening the column. Trimming it hands width back to the
    # cramped To and Load text columns.
    table.add_column("Jmp", justify="center", no_wrap=True)
    table.add_column("Profit", justify="right", no_wrap=True)

    for hop_index, hop in enumerate(route.hops, start=1):
        shade = (hop_index - 1) % 2
        table.add_row(
            Text(str(hop_index), style=_CHROME),
            _to_cell(hop, tier, shade),
            _load_cell(hop, tier, shade),
            Text(_jumps_text(hop), style=_CHROME),
            Text(f"+{hop.raw_profit:,} cr", style=_PROFIT_ALT[shade]),
        )
    return table


def _jumps_text(hop: PlannedHop) -> str:
    """Compact per-hop travel — jump count, or the special-leg shorthand."""

    leg = hop.jump_path
    if leg is None:
        return "direct"
    if leg.is_same_system:
        return "sc"
    return str(leg.jumps)


def _nav_route(hop: PlannedHop) -> tuple[str, float] | None:
    """The systems flown on a hop and the leg's flown distance, or None.

    None when the hop carries no jump path to walk — a same-system supercruise
    hop, or a --direct hop the commander plots for themselves.
    """

    leg = hop.jump_path
    if leg is None or leg.is_same_system or len(leg.systems) < 2:
        return None
    chain = " → ".join(system.dbname for system in leg.systems)
    return chain, leg.distance_ly


def _bulk_capped(line: CargoLine) -> bool:
    """Whether the bulk-sale-tax cap bound this cargo line.

    Mirrors the raw renderer: a Metals/Minerals line whose loaded quantity
    equals the already-25%-capped destination demand is one the cap held back.
    A sensitive line below that figure was limited by supply, capacity, or
    credits first, so it is not flagged.
    """

    return (
        line.bulk_sale_tax_sensitive
        and line.quantity == line.effective_destination_demand_units
    )


def _to_cell(hop: PlannedHop, tier: str, shade: int) -> Text:
    """The location cell. Summary and standard show the destination (standard
    adds the nav chain on a dim line beneath it). Verbose shows the whole trip
    — source, destination, then the jumps — so the buy and the sell read as two
    different places; that build lives in ``_trip_cell``."""

    if tier == "verbose":
        return _trip_cell(hop, shade)

    cell = Text(hop.destination_station.dbname, style=_DEST_ALT[shade])
    if tier == "standard":
        nav = _nav_route(hop)
        if nav is not None:
            chain, distance_ly = nav
            cell.append(f"\n↳ {chain} · {distance_ly:.1f} ly", style=_DIM)
    return cell


def _trip_cell(hop: PlannedHop, shade: int) -> Text:
    """Verbose location cell — the hop as a trip: the source station you buy
    at, the destination you sell at, then the jumps one per line. Naming both
    ends stops the buy and the sell reading as one place."""

    cell = Text(hop.source_station.dbname, style=_DEST_ALT[shade])
    cell.append(
        f"\n→ {hop.destination_station.dbname}", style=_DEST_ALT[shade]
    )
    leg = hop.jump_path
    if leg is not None and not leg.is_same_system:
        for system, leg_ly in _jump_legs(leg):
            cell.append(
                f"\n  ↳ {system.dbname} · {leg_ly:.1f} ly", style=_DIM
            )
    return cell


def _load_cell(hop: PlannedHop, tier: str, shade: int) -> Text:
    """The Load cell: the hop's commodities in its gold shade. Summary keeps a
    single comma-separated line; standard puts each on its own line with its
    buy price; verbose stacks the buy and sell price under each commodity. On
    standard, a commodity the bulk-sale-tax cap held back gets an amber flag."""

    gold = _LOAD_ALT[shade]
    cell = Text()
    for position, line in enumerate(hop.cargo.lines):
        if position:
            cell.append(", " if tier == "summary" else "\n", style=gold)
        entry = f"{line.quantity:,} t {line.item_name}"
        if tier == "standard":
            entry += f" @ {line.buy_price:,} cr/t"
        cell.append(entry, style=gold)
        if tier == "standard" and _bulk_capped(line):
            cell.append(" ⚑", style=_CAP)
        if tier == "verbose":
            cell.append(f"\n    buy  {line.buy_price:,} cr/t", style=_DIM)
            cell.append(f"\n    sell {line.sell_price:,} cr/t", style=_DIM)
    return cell


def _jump_legs(leg) -> list:
    """Per-jump destinations and leg lengths along a jump path. The first
    system is the hop's origin, so each later system is one jump; its leg
    length is the straight-line distance from the system before it — the same
    geometry that built the path's total."""

    systems = leg.systems
    out: list = []
    for position in range(1, len(systems)):
        previous, system = systems[position - 1], systems[position]
        before = (previous.x, previous.y, previous.z)
        after = (system.x, system.y, system.z)
        out.append((system, math.dist(before, after)))
    return out


def _stops_table(route: PlannedRoute) -> Table:
    """Station-centric verbose: a row per stop, not per hop. At each station
    you sell what you arrived carrying and buy what you leave with — different
    commodities at the same place, which is how the route is actually flown.
    The origin has nothing to sell, the final stop nothing to buy; a hop's
    profit and the running balance land on the row where its cargo is sold
    (arrival). The leg leaving a station — its jumps — sits under that station's
    name. Stops are deliberately unnumbered, to avoid clashing with hop numbers.
    """

    table = Table(
        box=_BOX,
        show_lines=True,
        header_style=_CHROME,
        border_style=_CHROME_DIM,
        padding=(0, 1),
        pad_edge=False,
    )
    table.add_column("Station", overflow="fold")
    table.add_column("Sell", overflow="fold")
    table.add_column("Buy", overflow="fold")
    table.add_column("Profit", justify="right", no_wrap=True)
    table.add_column("Balance", justify="right", no_wrap=True)

    # The stop chain: the first hop's origin, then every hop's destination. So
    # at stop ``index`` the arriving hop is ``hops[index - 1]`` (what you sell)
    # and the departing hop is ``hops[index]`` (what you buy and the jumps out).
    hops = route.hops
    stations = [hops[0].source_station]
    stations.extend(hop.destination_station for hop in hops)

    running = route.starting_credits
    for index, station in enumerate(stations):
        shade = index % 2
        sell_hop = hops[index - 1] if index > 0 else None
        buy_hop = hops[index] if index < len(hops) else None

        station_cell = Text(station.dbname, style=_DEST_ALT[shade])
        if buy_hop is not None:
            leg = buy_hop.jump_path
            if leg is not None and not leg.is_same_system:
                for system, leg_ly in _jump_legs(leg):
                    station_cell.append(
                        f"\n  ↓ {system.dbname} · {leg_ly:.1f} ly", style=_DIM
                    )

        if sell_hop is not None:
            running += sell_hop.raw_profit
            sell_cell = _trade_cell(sell_hop, "sell_price", shade)
            profit_cell = Text(
                f"+{sell_hop.raw_profit:,} cr", style=_PROFIT_ALT[shade]
            )
        else:
            sell_cell = Text("—", style=_DIM)
            profit_cell = Text("—", style=_DIM)

        if buy_hop is not None:
            buy_cell = _trade_cell(buy_hop, "buy_price", shade)
        else:
            buy_cell = Text("—", style=_DIM)

        balance_cell = Text(f"{running:,} cr", style=_PROFIT_ALT[shade])

        table.add_row(
            station_cell, sell_cell, buy_cell, profit_cell, balance_cell
        )
    return table


def _trade_cell(hop: PlannedHop, price_attr: str, shade: int) -> Text:
    """One side of a stop's trade — the hop's commodities at the given price
    (``buy_price`` for the buy column, ``sell_price`` for the sell), one per
    line in the hop's gold shade."""

    gold = _LOAD_ALT[shade]
    cell = Text()
    for position, line in enumerate(hop.cargo.lines):
        if position:
            cell.append("\n", style=gold)
        price = getattr(line, price_attr)
        cell.append(
            f"{line.quantity:,} t {line.item_name} @ {price:,} cr/t",
            style=gold,
        )
    return cell


def _total_line(route: PlannedRoute) -> Text:
    """The closing totals line: route profit, with start and final credits."""

    line = Text("  Total Profit   ", style=f"bold {_CHROME}")
    line.append(f"{route.total_raw_profit:,} cr", style=_PROFIT)
    line.append(
        f"  ·  start {route.starting_credits:,} cr  →  "
        f"final {route.ending_credits:,} cr",
        style=_CHROME,
    )
    return line


def _jump_totals(route: PlannedRoute) -> tuple[int, float]:
    """Total jumps and light-years across the route.

    Same-system supercruise and --direct legs are not jumps, so they add
    nothing to either total.
    """

    total_jumps = 0
    total_ly = 0.0
    for hop in route.hops:
        leg = hop.jump_path
        if leg is not None and not leg.is_same_system:
            total_jumps += leg.jumps
            total_ly += leg.distance_ly
    return total_jumps, total_ly
