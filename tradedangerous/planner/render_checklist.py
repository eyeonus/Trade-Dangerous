"""Interactive checklist renderer for trade run planner results.

``--checklist`` walks a single planned route one hop at a time. Each hop becomes
a self-contained panel: where you are, what to buy before you leave, the jumps to
fly, and what to sell when you arrive — spelled out in full, the way you would
read it back to yourself at the keyboard. The print-and-wait loop that reveals
the panels one at a time lives in the command layer; this module only builds
them, in order, and hands back the list.

It is the verbose, human-facing companion to the rich table renderer
(``render_rich``) and borrows that module's palette and jump-leg helpers so the
two read alike. Empty-jump positioning legs (``--start-jumps`` / ``--end-jumps``)
become their own steps, and a closing panel carries the route totals.

``verbose`` (the command's ``-v``) thickens each step with the supply/demand
behind every trade, a dock/refuel/repair reminder, and any arrival note — the
"detail mode" the spec calls for. The base checklist already prices both sides,
lists every jump, and tracks the running balance.
"""

from __future__ import annotations

from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from .render_rich import (
    _CAP,
    _CHROME,
    _DEST,
    _DIM,
    _LOAD_ALT,
    _ORIGIN,
    _PROFIT,
    _bulk_capped,
    _jump_legs,
)
from .render_text import _render_positioning, _render_warning
from .run_result import (
    CargoLine,
    JumpPath,
    PlannedHop,
    PlannedRoute,
    ResolvedStation,
    RunResult,
)

# One gold for commodity loads. The table renderer alternates two shades row to
# row to hold a row together; a checklist shows one hop per panel, so a single
# shade is enough.
_GOLD = _LOAD_ALT[0]


def render_checklist(result: RunResult, *, verbose: bool = False) -> list:
    """Build the ordered list of checklist step renderables for one route.

    Checklist mode is only valid for a single displayed route, so the first
    route is the one walked. Returns a list the driver reveals one entry at a
    time: any partial-route warning, an optional start-positioning panel, one
    panel per hop, an optional end-positioning panel, and a closing totals
    panel. An empty result (nothing planned) yields an empty list.
    """

    if not result.routes:
        return []

    route = result.routes[0]
    steps: list = []

    # A partial route still walks what it found; lead with the warning so the
    # commander knows the run stops short before they start flying it.
    for warning in result.warnings:
        steps.append(Text(f"WARNING: {_render_warning(warning)}", style="yellow"))

    if route.start_positioning is not None:
        steps.append(
            _positioning_panel(
                "Reposition to the first trade stop",
                "Empty jumps to start",
                route.start_positioning,
                verbose,
            )
        )

    running = route.starting_credits
    hop_count = len(route.hops)
    for number, hop in enumerate(route.hops, start=1):
        steps.append(_hop_panel(hop, number, hop_count, running, verbose))
        running += hop.raw_profit

    if route.end_positioning is not None:
        steps.append(
            _positioning_panel(
                "Reposition to finish",
                "Empty jumps from end",
                route.end_positioning,
                verbose,
            )
        )

    steps.append(_summary_panel(route))
    return steps


def _hop_panel(
    hop: PlannedHop, number: int, hop_count: int, running_before: int,
    verbose: bool,
) -> Panel:
    """One hop as a numbered, three-step panel: buy at the origin, fly the jumps,
    sell at the destination — then the hop's profit and the running balance."""

    running_after = running_before + hop.raw_profit
    body: list = []

    # The hop at a glance: origin to destination.
    overview = Text()
    overview.append(hop.source_station.dbname, style=_ORIGIN)
    overview.append("   →   ", style=_DIM)
    overview.append(hop.destination_station.dbname, style=_DEST)
    body.append(overview)
    body.append(Text(""))

    # ① Buy at the origin.
    body.append(_step_heading("①", "BUY at", hop.source_station.dbname, _ORIGIN))
    body.append(_station_detail(hop.source_station))
    for line in hop.cargo.lines:
        body.append(_trade_line(line, "buy", verbose))
    cargo = hop.cargo
    body.append(
        Text(
            f"     loaded {cargo.units_loaded:,} t · spend "
            f"{cargo.total_cost:,} cr · {cargo.unused_capacity:,} t hold free "
            f"· {cargo.unspent_capital:,} cr in reserve",
            style=_DIM,
        )
    )
    body.append(Text(""))

    # ② Fly to the destination.
    body.extend(_fly_lines(hop.jump_path))
    body.append(Text(""))

    # ③ Sell at the destination.
    body.append(
        _step_heading("③", "SELL at", hop.destination_station.dbname, _DEST)
    )
    body.append(_station_detail(hop.destination_station))
    for line in hop.cargo.lines:
        body.append(_trade_line(line, "sell", verbose))
    body.append(Text(""))

    # The hop's bottom line: profit booked and the balance it leaves you on.
    bottom = Text("     hop profit  ", style=_DIM)
    bottom.append(f"+{hop.raw_profit:,} cr", style=_PROFIT)
    bottom.append("   →   balance ", style=_DIM)
    bottom.append(f"{running_after:,} cr", style=_PROFIT)
    body.append(bottom)

    if verbose:
        body.append(
            Text(
                "     Dock, refuel, repair and restock as needed before you "
                "leave.",
                style=_DIM,
            )
        )

    return Panel(
        Group(*body),
        title=f"Hop {number} of {hop_count}",
        title_align="left",
        border_style=_CHROME,
        padding=(1, 2),
    )


def _positioning_panel(
    title: str, label: str, leg: JumpPath, verbose: bool
) -> Panel:
    """A repositioning step for an empty-jump leg. The shared summary line (jumps,
    distance, the systems flown) heads it; ``verbose`` lists each empty jump's
    leg length underneath."""

    body: list = [Text(_render_positioning(label, leg).strip(), style=_DIM)]
    if verbose and not leg.is_same_system:
        for system, leg_ly in _jump_legs(leg):
            body.append(
                Text(f"     ↓ {system.dbname} · {leg_ly:.1f} ly", style=_DIM)
            )
    return Panel(
        Group(*body),
        title=title,
        title_align="left",
        border_style=_DIM,
        padding=(1, 2),
    )


def _summary_panel(route: PlannedRoute) -> Panel:
    """The closing panel: total profit, start and final credits, and the
    ``--towards`` arrival note when the route reached its target."""

    body: list = []
    total = Text("Total profit  ", style=f"bold {_CHROME}")
    total.append(f"{route.total_raw_profit:,} cr", style=_PROFIT)
    body.append(total)
    body.append(
        Text(
            f"Start {route.starting_credits:,} cr  →  final "
            f"{route.ending_credits:,} cr",
            style=_DIM,
        )
    )
    if route.arrival_hops is not None:
        hop_word = "hop" if route.arrival_hops == 1 else "hops"
        body.append(
            Text(
                f"Arrived at the target after {route.arrival_hops} {hop_word}.",
                style=_PROFIT,
            )
        )
    return Panel(
        Group(*body),
        title="Route summary",
        title_align="left",
        border_style=_CHROME,
        padding=(1, 2),
    )


def _step_heading(marker: str, verb: str, place: str, place_style: str) -> Text:
    """A numbered checklist step heading: the circled step number and the action
    in chrome, then the station it happens at in that station's own colour."""

    heading = Text(f"  {marker} {verb} ", style=_CHROME)
    heading.append(place, style=place_style)
    return heading


def _station_detail(station: ResolvedStation) -> Text:
    """A dim 'know before you dock' line: the station's system, distance from the
    arrival star, largest pad, data age, and any notable flags. The table
    renderer has no room for this; the checklist does."""

    bits = [
        station.system_name,
        f"{station.ls_from_star:,} ls from star",
        f"{station.max_pad_size or '?'} pad",
    ]
    if station.data_age_days is not None:
        bits.append(f"data {station.data_age_days:.1f} d old")

    flags = []
    if (station.fleet_carrier or "").upper() == "Y":
        flags.append("fleet carrier")
    if (station.settlement or "").upper() == "Y":
        flags.append("settlement")
    if (station.planetary or "").upper() == "Y":
        flags.append("planetary")
    if (station.black_market or "").upper() == "Y":
        flags.append("black market")

    detail = "     " + " · ".join(bits)
    if flags:
        detail += "   [" + ", ".join(flags) + "]"
    return Text(detail, style=_DIM)


def _trade_line(line: CargoLine, side: str, verbose: bool) -> Text:
    """One commodity to buy or sell: quantity, name, unit price and line total,
    with supply (buy) or per-unit profit and demand (sell) added under
    ``verbose``. A buy the bulk-sale cap held back carries the amber flag."""

    if side == "buy":
        unit_price, total = line.buy_price, line.total_cost
    else:
        unit_price, total = line.sell_price, line.quantity * line.sell_price

    text = Text("     • ", style=_DIM)
    text.append(f"{line.quantity:,} t {line.item_name}", style=_GOLD)
    text.append(f"  @ {unit_price:,} cr/t", style=_GOLD)
    text.append(f"  =  {total:,} cr", style=_DIM)
    if verbose:
        if side == "buy":
            text.append(
                f"   (supply {line.source_supply_units:,})", style=_DIM
            )
        else:
            text.append(
                f"   (+{line.profit_per_unit:,} cr/t · demand "
                f"{line.destination_demand_units:,})",
                style=_DIM,
            )
    if side == "buy" and _bulk_capped(line):
        text.append("  ⚑ capped to 25% of demand", style=_CAP)
    return text


def _fly_lines(leg: JumpPath | None) -> list:
    """The ② FLY step: a heading with the jump count and distance, then each jump
    on its own line. A same-system hop is a supercruise, not a jump; a
    ``--direct`` hop carries no plan, so the commander plots it."""

    if leg is None:
        return [
            Text(
                "  ② FLY — plot your own route (--direct, no jump plan)",
                style=_CHROME,
            )
        ]
    if leg.is_same_system:
        line = Text("  ② FLY — ", style=_CHROME)
        line.append(
            f"supercruise within the system · {leg.distance_ly:.1f} ly",
            style=_DIM,
        )
        return [line]

    jump_word = "jump" if leg.jumps == 1 else "jumps"
    heading = Text(
        f"  ② FLY — {leg.jumps} {jump_word} · {leg.distance_ly:.1f} ly:",
        style=_CHROME,
    )
    lines = [heading]
    for system, leg_ly in _jump_legs(leg):
        lines.append(
            Text(f"     ↓ {system.dbname} · {leg_ly:.1f} ly", style=_DIM)
        )
    return lines
