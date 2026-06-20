"""Rich (formatted) renderer for trade run planner results.

This is the default ``trade run`` output: a colour table built on the ``rich``
library, pinned to 80 columns by the caller. The plain-text renderer in
``render_text`` is the ``--raw`` alternative; the warning, positioning,
diagnostics, and route-note text is shared from there so the two formats stay
in step.

The standard tier is deliberately lean — a header line, one table row a hop
(where to, what to load, jumps, profit), and a totals line. Fuller detail
(prices, the sell ledger, the full jump path, station data) belongs in the
``--raw`` plain output and the later verbose tier, not here. Each hop is one
row; the row's destination is the next hop's origin, and the route header
carries the overall start, so the chain reads straight down.
"""

from __future__ import annotations

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
from .run_result import PlannedHop, PlannedRoute, RunResult

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

# A light grid: HORIZONTALS frames the table and underlines the header without
# vertical bars, and show_lines stays off so there is no rule between every hop
# — enough structure to break the route up, not a line per row. The box style
# is the easiest knob to make it heavier (MINIMAL/SQUARE/ROUNDED add verticals)
# or lighter (SIMPLE_HEAD drops the frame to just the header rule).
_BOX = box.HORIZONTALS


def render_run_result_rich(result: RunResult, *, debug: int = 0) -> Group:
    """Build the rich renderable for a planner result.

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
        blocks.extend(_route_block(route, index if multi else None, debug))
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
    route: PlannedRoute, number: int | None, debug: int
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

    blocks.append(_hop_table(route))

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


def _hop_table(route: PlannedRoute) -> Table:
    """The hop table — one row a hop. Long station and load text folds within
    its column so nothing strays to the start of the next line."""

    table = Table(
        box=_BOX,
        show_lines=False,
        header_style=_CHROME,
        border_style=_CHROME,
        padding=(0, 1),
        pad_edge=False,
    )
    table.add_column("Hop", justify="center", no_wrap=True)
    table.add_column("To", overflow="fold")
    table.add_column("Load", overflow="fold")
    table.add_column("Jumps", justify="center", no_wrap=True)
    table.add_column("Profit", justify="right", no_wrap=True)

    for hop_index, hop in enumerate(route.hops, start=1):
        load = ", ".join(
            f"{line.quantity:,} t {line.item_name}" for line in hop.cargo.lines
        )
        shade = (hop_index - 1) % 2
        table.add_row(
            Text(str(hop_index), style=_CHROME),
            Text(hop.destination_station.dbname, style=_DEST_ALT[shade]),
            Text(load, style=_LOAD_ALT[shade]),
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
