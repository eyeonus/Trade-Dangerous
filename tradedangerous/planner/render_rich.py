"""Rich (formatted) renderer for trade run planner results.

This is the default ``trade run`` output: a colour table built on the ``rich``
library. The plain-text renderer in ``render_text`` is the ``--raw``
alternative; the warning, positioning, diagnostics, and route-note text is
shared from there so the two formats stay in step.

Three rich tiers share one station-centric table — a row per stop, showing what
you sell on arrival and what you buy before leaving, so it reads the way the
route is actually flown. They differ only in how much each cell holds.
``--summary`` is the bare glance — Sell and Buy as comma loads, no prices, no
nav, profit only. ``standard`` (the default) stacks each commodity, prices the
buy side, condenses the flown systems to a line under each station, and
separates stops with a blank line. ``-v`` verbose prices both sides and lists
every jump, with a rule between stops. All three adapt to the terminal width:
the numeric columns (Balance, then Profit) shed on a narrower screen rather than
fold; narrower still the priced tiers each keep Profit their own way — standard
drops its Sell column, verbose folds Sell and Buy into one tagged Trade column —
so the Profit column survives even at 80 columns. Summary, carrying no prices,
keeps both sides throughout. (``--raw`` is the plain-text format, handled in
``render_text``.) All share the route header, the totals line, and the route
notes.
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
# screen space. Origin is a soft cyan beside the azure destinations. The
# coloured columns (Station, the Sell/Buy loads, Profit) alternate a medium and
# a lighter shade of their hue row to row, in sync, so a row reads as a whole
# and a folded name stays with its stop. Truecolor hex; rich downgrades on
# terminals without 24-bit. _DEST / _PROFIT (header destination, totals figure)
# reuse the medium.
_DEST_ALT = ("#6aadf0", "#a3ccf5")    # azure — orange's complement
_LOAD_ALT = ("#edcb45", "#f7e497")    # gold — analogous to orange
_PROFIT_ALT = ("#45d380", "#98e1b7")  # emerald — tetrad with orange + azure

# Elite's signature HUD orange, matched to the GUI's Elite theme
# (guiapp/themes.css --q-primary). Used as chrome — the table frame, the column
# headers, and the Total label — so the data glows inside an orange frame the
# way the in-game HUD does, without taking a data colour off the red-green axis.
_CHROME = "#f07b05"

# Advisory amber for the bulk-sale-tax cap — the flag marker on a capped Buy
# line and its footnote. Matches the yellow used for warnings, and stands clear
# of the gold load colour so the flag still reads against it.
_CAP = "yellow"

# A dimmed chrome for the rule between verbose stops — the same HUD orange as
# the frame, attenuated so the inter-stop rules read as quiet dividers rather
# than competing with the header. rich applies the dim attribute over the
# truecolour.
_CHROME_DIM = f"dim {_CHROME}"

# A light grid: HORIZONTALS frames the table and underlines the header without
# vertical bars. show_lines (a rule between every row) is reserved for verbose;
# standard uses a blank line (leading) and summary a tight grid. The box style
# is the easiest knob to make it heavier (MINIMAL/SQUARE/ROUNDED add verticals)
# or lighter (SIMPLE_HEAD drops the frame to just the header rule).
_BOX = box.HORIZONTALS

# The numeric columns shed as the terminal narrows so the text columns keep
# room rather than folding to mush. Standard and verbose price their loads, so
# their cells are wide: above _PROFIT_MIN they keep separate Sell and Buy
# columns (and Balance too, above _BALANCE_MIN); below it they each keep Profit
# a different way — standard drops its Sell column, verbose folds Sell and Buy
# into one tagged Trade column. Summary's cells carry no prices, so it never
# needs to — it just sheds Profit below its own (lower) width and never carries
# Balance. Tune these by eye once run at real widths.
_PROFIT_MIN = {"summary": 70, "standard": 100, "verbose": 100}
_BALANCE_MIN = {"standard": 120, "verbose": 120}


def render_run_result_rich(
    result: RunResult, *, debug: int = 0, tier: str = "standard",
    width: int = 80,
) -> Group:
    """Build the rich renderable for a planner result.

    ``tier`` selects how much each cell of the station-centric table carries.
    ``"summary"`` is the lean glance — comma loads, no prices; ``"standard"``
    (the default) prices the buy side, condenses the nav under each station, and
    gaps the stops with a blank line; ``"verbose"`` prices both sides, lists
    every jump, and rules the stops apart. All share the header, totals, and
    notes.

    ``width`` is the column budget the output will be printed at; every tier
    uses it to shed or rearrange its columns on a narrow terminal so the table
    degrades rather than folds.

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
            _route_block(route, index if multi else None, debug, tier, width)
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
    route: PlannedRoute, number: int | None, debug: int, tier: str, width: int
) -> list:
    """One route: a header line, the stops table, then a totals line."""

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

    blocks.append(_stops_table(route, tier, width))

    # Flag below the table when the bulk-sale-tax cap shaped any hop's cargo —
    # the ⚑ in the Buy column points at which commodity, this line says why.
    # Summary stays clean (no flag, no note); standard and verbose carry both.
    if tier in ("standard", "verbose") and any(
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


def _append_nav(cell: Text, hop: PlannedHop, tier: str) -> None:
    """Append the leg leaving this station, under its name in dim, in the form
    the tier calls for.

    Summary shows nothing. A same-system hop is a supercruise to another station
    in the same system — no hyperspace jump, so its distance is 0.0 ly — and
    gets a single ``Supercruise`` line so the leg is not silently blank. A
    --direct hop carries no jump path (the commander plots it), so nothing is
    appended. Otherwise standard condenses the flown systems to a single line
    (systems jumped to and the leg's distance) and verbose lists each jump on
    its own line with its leg length.
    """

    if tier == "summary":
        return
    leg = hop.jump_path
    if leg is None:
        return
    if leg.is_same_system:
        cell.append(
            f"\n  ↓ Supercruise · {leg.distance_ly:.1f} ly", style=_DIM
        )
        return
    legs = _jump_legs(leg)
    if tier == "verbose":
        for system, leg_ly in legs:
            cell.append(f"\n  ↓ {system.dbname} · {leg_ly:.1f} ly", style=_DIM)
    else:
        chain = " → ".join(system.dbname for system, _ in legs)
        cell.append(f"\n  ↓ {chain} · {leg.distance_ly:.1f} ly", style=_DIM)


def _stops_table(route: PlannedRoute, tier: str, width: int) -> Table:
    """Station-centric table: a row per stop, not per hop. At each station you
    sell what you arrived carrying and buy what you leave with — different
    commodities at the same place, which is how the route is actually flown. The
    origin has nothing to sell, the final stop nothing to buy; a hop's profit
    and the running balance land on the row where its cargo is sold (arrival).
    The leg leaving a station sits under that station's name. Stops are
    deliberately unnumbered, to avoid clashing with hop numbers.

    The tiers differ by how much each cell holds. ``summary`` is the bare glance
    — Sell and Buy as comma loads, no prices, no nav, profit only; ``standard``
    stacks each commodity, prices the buy side, condenses the flown systems to
    one line under the station, and flags a capped buy; ``verbose`` adds sell
    prices too and lists every jump. The frame: a rule between stops for verbose,
    a blank line for standard, a tight grid for summary.

    The layout adapts to ``width``. Wide, standard and verbose show separate Sell
    and Buy columns with Profit and Balance; as the terminal narrows Balance
    sheds first. Narrower still, each keeps Profit by its own compromise:
    standard drops the Sell column (holding the route and the priced Buy),
    verbose folds Sell and Buy into one tagged Trade column (holding both sides).
    Summary carries no prices, so it fits both sides at any width and only sheds
    Profit when very narrow. The header and totals line always carry the route's
    bottom line.
    """

    is_standard = tier == "standard"
    is_verbose = tier == "verbose"
    priced = tier in ("standard", "verbose")

    # Below the width where Profit would otherwise be dropped, the priced tiers
    # make room for it rather than lose it, each its own way: verbose folds Sell
    # and Buy into one tagged Trade column (keeping both sides), standard drops
    # its Sell column (keeping the priced Buy and the route under each station).
    # Summary carries no prices, so its cells already fit both sides at any width
    # and it never has to.
    narrow_priced = priced and width < _PROFIT_MIN[tier]
    combine = narrow_priced and is_verbose
    drop_sell = narrow_priced and is_standard
    if narrow_priced:
        show_profit = True
        show_balance = False
    else:
        show_profit = width >= _PROFIT_MIN[tier]
        show_balance = tier in _BALANCE_MIN and width >= _BALANCE_MIN[tier]

    # The rule between stops (show_lines) is verbose's alone; standard separates
    # stops with a blank line at every width, summary with nothing.
    table = Table(
        box=_BOX,
        show_lines=is_verbose,
        header_style=_CHROME,
        border_style=_CHROME_DIM if is_verbose else _CHROME,
        padding=(0, 1),
        pad_edge=False,
        leading=1 if is_standard else 0,
    )
    table.add_column("Station", overflow="fold")
    if combine:
        table.add_column("Trade", overflow="fold")
    elif drop_sell:
        table.add_column("Buy", overflow="fold")
    else:
        table.add_column("Sell", overflow="fold")
        table.add_column("Buy", overflow="fold")
    if show_profit:
        table.add_column("Profit", justify="right", no_wrap=True)
    if show_balance:
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
            _append_nav(station_cell, buy_hop, tier)

        if sell_hop is not None:
            running += sell_hop.raw_profit
            profit_cell = Text(
                f"+{sell_hop.raw_profit:,} cr", style=_PROFIT_ALT[shade]
            )
        else:
            profit_cell = Text("—", style=_DIM)

        row = [station_cell]
        if combine:
            row.append(_combined_trade_cell(sell_hop, buy_hop, tier, shade))
        elif drop_sell:
            row.append(_side_cell(buy_hop, "buy", tier, shade))
        else:
            row.append(_side_cell(sell_hop, "sell", tier, shade))
            row.append(_side_cell(buy_hop, "buy", tier, shade))
        if show_profit:
            row.append(profit_cell)
        if show_balance:
            row.append(Text(f"{running:,} cr", style=_PROFIT_ALT[shade]))
        table.add_row(*row)
    return table


def _trade_entry(line: CargoLine, side: str, tier: str) -> str:
    """Commodity text for one cargo line: quantity and name, plus the price when
    the tier shows it. Verbose prices both sides, standard prices only the buy
    side, summary shows no prices."""

    entry = f"{line.quantity:,} t {line.item_name}"
    show_price = tier == "verbose" or (tier == "standard" and side == "buy")
    if show_price:
        attr = "sell_price" if side == "sell" else "buy_price"
        entry += f" @ {getattr(line, attr):,} cr/t"
    return entry


def _flag_capped(line: CargoLine, side: str, tier: str) -> bool:
    """Whether this line earns the bulk-cap ⚑ — a capped buy on standard or
    verbose (summary stays clean, and the cap is a buy-side concern)."""

    return (
        side == "buy"
        and tier in ("standard", "verbose")
        and _bulk_capped(line)
    )


def _trade_cell(hop: PlannedHop, side: str, tier: str, shade: int) -> Text:
    """One side of a stop's trade — the hop's commodities in its gold shade, for
    the wide layout's separate Sell / Buy columns. ``side`` is ``"sell"`` (the
    cargo offloaded on arrival) or ``"buy"`` (the cargo loaded before leaving).
    Summary keeps a comma list; the priced tiers stack one per line. A capped
    buy gets the amber ⚑."""

    gold = _LOAD_ALT[shade]
    separator = ", " if tier == "summary" else "\n"
    cell = Text()
    for position, line in enumerate(hop.cargo.lines):
        if position:
            cell.append(separator, style=gold)
        cell.append(_trade_entry(line, side, tier), style=gold)
        if _flag_capped(line, side, tier):
            cell.append(" ⚑", style=_CAP)
    return cell


def _side_cell(hop, side: str, tier: str, shade: int) -> Text:
    """A Sell or Buy column cell, or a dim dash where there is no trade — the
    origin has nothing to sell, the final stop nothing to buy."""

    if hop is None:
        return Text("—", style=_DIM)
    return _trade_cell(hop, side, tier, shade)


def _combined_trade_cell(sell_hop, buy_hop, tier: str, shade: int) -> Text:
    """Sell and Buy folded into one cell for the narrow priced layout. Each line
    is tagged with a Sell / Buy label so the two trades stay distinct now they
    share a column — the label sits in dim chrome, set off from the gold
    commodity by hue rather than weight. The origin contributes only buy lines,
    the final stop only sell lines. Used for verbose's narrow layout, so loads
    are always stacked one per line. A capped buy still gets the amber ⚑."""

    gold = _LOAD_ALT[shade]
    cell = Text()
    first = True
    for hop, side, tag in (
        (sell_hop, "sell", "Sell"),
        (buy_hop, "buy", "Buy"),
    ):
        if hop is None:
            continue
        for line in hop.cargo.lines:
            if not first:
                cell.append("\n")
            first = False
            cell.append(f"{tag:<4} ", style=_CHROME_DIM)
            cell.append(_trade_entry(line, side, tier), style=gold)
            if _flag_capped(line, side, tier):
                cell.append(" ⚑", style=_CAP)
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
