"""Render structured TD command results into NiceGUI widgets."""

from __future__ import annotations

from typing import Any

from nicegui import ui

# Run-route colours come straight from the CLI rich renderer so the GUI table
# and the terminal output share one palette (the packet's design target). The
# *_ALT pairs alternate a medium/light shade row to row, in sync, exactly as the
# CLI does. render_rich._CAP is a rich style name ("yellow"); the GUI maps it to
# a softer amber that reads against the gold load colour.
from tradedangerous.planner.render_rich import (
    _CHROME as _RUN_CHROME,
    _ORIGIN as _RUN_ORIGIN,
    _DEST as _RUN_DEST,
    _PROFIT as _RUN_PROFIT,
    _DEST_ALT as _RUN_STATION_ALT,
    _LOAD_ALT as _RUN_LOAD_ALT,
    _PROFIT_ALT as _RUN_PROFIT_ALT,
)

_RUN_CAP = '#f5c518'   # GUI amber for the bulk-cap flag (render_rich._CAP)
_RUN_DIM = '#9aa0a6'   # muted grey for nav sublines and empty-trade dashes

def _field(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _station_name(value: Any) -> str:
    dbname = _field(value, 'dbname')
    if callable(dbname):
        try:
            return str(dbname())
        except TypeError:
            pass
    if dbname not in (None, ''):
        return str(dbname)
    named = _named_result_value(value)
    if named is not None:
        return named
    return _format_result_value(value)


def _station_ls_text(value: Any) -> str:
    ls_text = _field(value, 'lsText')
    if ls_text not in (None, ''):
        return str(ls_text)
    dist_from_star = _field(value, 'distFromStar')
    if callable(dist_from_star):
        return str(dist_from_star())
    if dist_from_star not in (None, ''):
        return str(dist_from_star)
    return ''

# Run is the only command that currently returns a nested route/hop payload.
# The other command renderers mostly work with flattened summary/rows shapes.

def render_command_results(
    command: str,
    structured_result: Any,
    raw_output: str,
) -> None:
    """Render the best available result representation for a command."""
    
    # Prefer structured renderers when the executor captured them; raw text is
    # the fallback for unsupported payloads or legacy command paths.
    if command == 'run' and isinstance(structured_result, dict) \
            and 'routes' in structured_result:
        # Render whenever there is something route-shaped to show; an empty,
        # warning-free result falls through to the raw/guidance text below.
        if structured_result.get('routes') or structured_result.get('warnings'):
            _render_run_results(structured_result)
            return

    if command in {'buy', 'sell'} and structured_result:
        _render_generic_structured_results(command, structured_result)
        return
    
    if command == 'trade' and structured_result:
        _render_trade_results(structured_result)
        return
    
    if command == 'local' and structured_result:
        _render_local_results(structured_result)
        return
    
    if command == 'nav' and structured_result:
        _render_nav_results(structured_result)
        return
    
    if command == 'olddata' and structured_result:
        _render_olddata_results(structured_result)
        return
    
    if command == 'market' and structured_result:
        _render_market_results(structured_result)
        return
    
    if raw_output:
        ui.label(raw_output).classes('font-mono text-sm whitespace-pre-wrap')
        return
    
    ui.label('Nothing has been executed yet.')

def _render_run_results(payload: dict[str, Any]) -> None:
    """Render a post-L RunResult snapshot.

    The payload is the plain-dict shape produced by td_exec._snapshot_run_routes:
    ``{'routes': [...], 'warnings': [...]}``. Each route becomes a station-centric
    table (Station / Sell / Buy / Profit / Balance) following the CLI rich
    renderer; multiple routes are shown as tabs.
    """
    for warning in payload.get('warnings') or []:
        ui.label(f'⚠ {warning}').classes('text-sm').style(
            f'color: {_RUN_CAP}; white-space: pre-wrap'
        )

    routes = payload.get('routes') or []
    if not routes:
        ui.label('No profitable routes were found.').classes(
            'text-sm text-gray-600'
        )
        return

    if len(routes) == 1:
        _render_run_route(routes[0])
        return

    # Multiple routes: one tab each, the first shown by default.
    ui.label(f'{len(routes)} routes found.').classes('text-sm text-gray-600')
    with ui.tabs() as tabs:
        tab_refs = [
            ui.tab(f'route-{index}', label=f'Route {index}')
            for index in range(1, len(routes) + 1)
        ]
    with ui.tab_panels(tabs, value=tab_refs[0]).classes('w-full'):
        for index, route in enumerate(routes, start=1):
            with ui.tab_panel(f'route-{index}'):
                _render_run_route(route)

def _render_run_route(route: dict[str, Any]) -> None:
    with ui.column().classes('w-full gap-2'):
        _render_run_route_header(route)
        _render_run_route_table(route)
        if route.get('capped'):
            ui.label(
                '⚑ Metals/Minerals capped at 25% of demand to avoid the '
                'bulk-sale tax.'
            ).classes('text-sm').style(f'color: {_RUN_CAP}')
        arrival = route.get('arrival_hops')
        if arrival is not None:
            ui.label(
                f'Arrived at the target system after {arrival} hop(s).'
            ).classes('text-sm').style(f'color: {_RUN_DIM}')
        # A single hop's profit already sits in its row, so it needs no totals.
        if route.get('hop_count', 0) > 1:
            _render_run_route_totals(route)

def _render_run_route_header(route: dict[str, Any]) -> None:
    hops = route.get('hop_count', 0)
    jumps = route.get('total_jumps', 0)
    ly = route.get('total_ly', 0.0) or 0.0
    hop_word = 'hop' if hops == 1 else 'hops'
    jump_word = 'jump' if jumps == 1 else 'jumps'
    with ui.row().classes('items-baseline gap-2 flex-wrap'):
        ui.label(str(route.get('origin', ''))).classes('text-lg').style(
            f'color: {_RUN_ORIGIN}; font-weight: 600'
        )
        ui.label('→').style(f'color: {_RUN_DIM}')
        ui.label(str(route.get('destination', ''))).classes('text-lg').style(
            f'color: {_RUN_DEST}; font-weight: 600'
        )
        ui.label(
            f'{hops} {hop_word} · {jumps} {jump_word} · {ly:.2f} ly'
        ).style(f'color: {_RUN_CHROME}')

def _render_run_route_table(route: dict[str, Any]) -> None:
    stops = route.get('stops') or []
    # Scroll wrapper: wide priced cargo cells size to content and scroll
    # horizontally rather than fold (the packet rules out an 80-column mode).
    with ui.element('div').classes('w-full').style('overflow-x: auto'):
        grid = ui.grid().style(
            'grid-template-columns: auto auto auto auto auto; '
            'column-gap: 1.5rem; row-gap: 0.5rem; align-items: start; '
            'width: max-content; min-width: 100%'
        )
        with grid:
            for title, align in (
                ('Station', 'start'), ('Sell', 'start'), ('Buy', 'start'),
                ('Profit', 'end'), ('Balance', 'end'),
            ):
                ui.label(title).style(
                    f'color: {_RUN_CHROME}; font-weight: 700; '
                    f'justify-self: {align}; '
                    f'border-bottom: 1px solid {_RUN_CHROME}; '
                    'padding-bottom: 0.15rem'
                )
            for index, stop in enumerate(stops):
                shade = index % 2
                _render_run_station_cell(stop, shade)
                _render_run_cargo_cell(stop.get('sell') or [], shade)
                _render_run_cargo_cell(stop.get('buy') or [], shade)
                _render_run_profit_cell(stop.get('profit'), shade)
                _render_run_balance_cell(stop.get('balance'), shade)

def _render_run_station_cell(stop: dict[str, Any], shade: int) -> None:
    with ui.column().classes('gap-0'):
        ui.label(str(stop.get('station', ''))).style(
            f'color: {_RUN_STATION_ALT[shade]}; font-weight: 600'
        )
        nav = stop.get('nav')
        if nav:
            ui.label(f'↓ {nav}').classes('text-xs').style(
                f'color: {_RUN_DIM}'
            )

def _render_run_cargo_cell(lines: list[dict[str, Any]], shade: int) -> None:
    if not lines:
        ui.label('—').style(f'color: {_RUN_DIM}')
        return
    with ui.column().classes('gap-0'):
        for line in lines:
            qty = int(line.get('qty', 0) or 0)
            item = str(line.get('item', ''))
            price = int(line.get('price', 0) or 0)
            text = f'{qty:,} t {item} @ {price:,} cr/t'
            if line.get('capped'):
                with ui.row().classes('items-baseline gap-1 no-wrap'):
                    ui.label(text).style(f'color: {_RUN_LOAD_ALT[shade]}')
                    ui.label('⚑').style(f'color: {_RUN_CAP}')
            else:
                ui.label(text).style(f'color: {_RUN_LOAD_ALT[shade]}')

def _render_run_profit_cell(profit: Any, shade: int) -> None:
    if profit is None:
        ui.label('—').style(f'color: {_RUN_DIM}; justify-self: end')
        return
    ui.label(f'+{int(profit):,} cr').style(
        f'color: {_RUN_PROFIT_ALT[shade]}; justify-self: end; '
        'white-space: nowrap'
    )

def _render_run_balance_cell(balance: Any, shade: int) -> None:
    ui.label(f'{int(balance or 0):,} cr').style(
        f'color: {_RUN_PROFIT_ALT[shade]}; justify-self: end; '
        'white-space: nowrap'
    )

def _render_run_route_totals(route: dict[str, Any]) -> None:
    with ui.row().classes('items-baseline gap-2 flex-wrap'):
        ui.label('Total Profit').style(
            f'color: {_RUN_CHROME}; font-weight: 700'
        )
        ui.label(f'{int(route.get("total_profit", 0) or 0):,} cr').style(
            f'color: {_RUN_PROFIT}; font-weight: 600'
        )
        ui.label(
            f'· start {int(route.get("starting_credits", 0) or 0):,} cr '
            f'→ final {int(route.get("ending_credits", 0) or 0):,} cr'
        ).style(f'color: {_RUN_CHROME}')

def _render_generic_structured_results(
    command: str,
    structured_result: Any,
) -> None:
    """Render flat summary-plus-row payloads such as buy/sell results."""
    payload = _structured_payload(structured_result)
    summary = payload.get('summary')
    rows = payload.get('rows', [])
    
    summary_text = _human_result_summary(summary)
    if summary_text:
        ui.label(summary_text).classes('text-sm text-gray-600')
    
    if not rows:
        ui.label(f'No {command} rows returned.').classes(
            'text-sm text-gray-600'
        )
        return
    
    table_rows = [_row_to_dict(row) for row in rows]
    columns = [
        {
            'name': key,
            'label': key.replace('_', ' ').title(),
            'field': key,
            'align': 'left',
        }
        for key in table_rows[0]
    ]
    
    for row in table_rows:
        for key, value in row.items():
            row[key] = _format_result_value(value)
    
    ui.table(
        columns=columns,
        rows=table_rows,
        row_key=next(iter(table_rows[0])),
    ).classes('w-full')

def _render_trade_results(structured_result: Any) -> None:
    payload = _structured_payload(structured_result)
    summary = payload.get('summary')
    rows = payload.get('rows', [])
    
    from_station = _field(summary, 'fromStation')
    to_station = _field(summary, 'toStation')
    origin_multi = bool(_field(summary, 'originMulti'))
    dest_multi = bool(_field(summary, 'destMulti'))
    
    def station_name(value: Any) -> str | None:
        dbname = _field(value, 'dbname')
        if callable(dbname):
            return str(dbname())
        if dbname not in (None, ''):
            return str(dbname)
        return _named_result_value(value)
    
    from_name = station_name(from_station)
    to_name = station_name(to_station)
    
    if from_name and to_name:
        ui.label(
            f'{len(rows)} trades found between {from_name} and {to_name}.'
        ).classes('text-sm text-gray-600')
    elif rows:
        ui.label(f'{len(rows)} trades found.').classes('text-sm text-gray-600')
    
    if not rows:
        ui.label('No trade rows returned.').classes('text-sm text-gray-600')
        return
    
    def format_int(value: Any) -> str:
        if value is None:
            return ''
        return f'{int(value):n}'
    
    table_rows = []
    for index, row in enumerate(rows, start=1):
        values = _row_to_dict(row)
        table_rows.append(
            {
                'row_id': f'trade-{index}',
                'from': _format_result_value(values.get('from_station')),
                'item': _format_result_value(values.get('item')),
                'to': _format_result_value(values.get('to_station')),
                'profit': format_int(values.get('gain')),
                'cost': format_int(values.get('sup_price')),
                'buying': format_int(values.get('dem_price')),
                'src_age': _format_result_value(values.get('sup_age')),
                'dst_age': _format_result_value(values.get('dem_age')),
            }
        )
    
    # From/To mirror the CLI: shown only when that endpoint spans multiple
    # stations (a system); redundant for a single concrete station.
    columns = []
    if origin_multi:
        columns.append(
            {'name': 'from', 'label': 'From', 'field': 'from', 'align': 'left'}
        )
    columns.append(
        {'name': 'item', 'label': 'Item', 'field': 'item', 'align': 'left'}
    )
    if dest_multi:
        columns.append(
            {'name': 'to', 'label': 'To', 'field': 'to', 'align': 'left'}
        )
    columns.extend([
        {'name': 'profit', 'label': 'Profit', 'field': 'profit', 'align': 'right'},
        {'name': 'cost', 'label': 'Cost', 'field': 'cost', 'align': 'right'},
        {'name': 'buying', 'label': 'Buying', 'field': 'buying', 'align': 'right'},
        {'name': 'src_age', 'label': 'SrcAge', 'field': 'src_age', 'align': 'right'},
        {'name': 'dst_age', 'label': 'DstAge', 'field': 'dst_age', 'align': 'right'},
    ])
    
    ui.table(
        columns=columns,
        rows=table_rows,
        row_key='row_id',
    ).classes('w-full')

def _render_local_results(structured_result: Any) -> None:
    payload = _structured_payload(structured_result)
    summary = payload.get('summary')
    rows = payload.get('rows', [])
    
    near_name = _named_result_value(_field(summary, 'near'))
    ly = _field(summary, 'ly')
    station_total = int(_field(summary, 'stations', 0) or 0)
    
    if near_name and ly is not None:
        ui.label(
            f'{len(rows)} system(s), {station_total} station(s) '
            f'within {float(ly):g} ly of {near_name}.'
        ).classes('text-sm text-gray-600')
    elif rows:
        ui.label(f'{len(rows)} system(s) returned.').classes(
            'text-sm text-gray-600'
        )
    
    if not rows:
        ui.label('No local rows returned.').classes('text-sm text-gray-600')
        return
    
    def yes_no_unknown(value: Any) -> str:
        return {'Y': 'Yes', 'N': 'No', '?': '?'}.get(str(value or ''), '')
    
    def pad_text(value: Any) -> str:
        return {'S': 'Sml', 'M': 'Med', 'L': 'Lrg', '?': '?'}.get(
            str(value or ''),
            '',
        )
    
    columns = [
        {'name': 'station', 'label': 'Station', 'field': 'station', 'align': 'left'},
        {'name': 'ls', 'label': 'StnLs', 'field': 'ls', 'align': 'right'},
        {'name': 'age', 'label': 'Age/days', 'field': 'age', 'align': 'right'},
        {'name': 'market', 'label': 'Mkt', 'field': 'market', 'align': 'right'},
        {'name': 'black_market', 'label': 'BMk', 'field': 'black_market', 'align': 'right'},
        {'name': 'shipyard', 'label': 'Shp', 'field': 'shipyard', 'align': 'right'},
        {'name': 'outfitting', 'label': 'Out', 'field': 'outfitting', 'align': 'right'},
        {'name': 'rearm', 'label': 'Arm', 'field': 'rearm', 'align': 'right'},
        {'name': 'refuel', 'label': 'Ref', 'field': 'refuel', 'align': 'right'},
        {'name': 'repair', 'label': 'Rep', 'field': 'repair', 'align': 'right'},
        {'name': 'pad', 'label': 'Pad', 'field': 'pad', 'align': 'right'},
        {'name': 'planetary', 'label': 'Plt', 'field': 'planetary', 'align': 'right'},
        {'name': 'fleet', 'label': 'Flc', 'field': 'fleet', 'align': 'right'},
        {'name': 'settlement', 'label': 'Stl', 'field': 'settlement', 'align': 'right'},
        {'name': 'items', 'label': 'Itms', 'field': 'items', 'align': 'right'},
    ]
    
    for system_index, row in enumerate(rows, start=1):
        values = _row_to_dict(row)
        system = values.get('system')
        system_name = _named_result_value(system) or _format_result_value(system)
        dist = values.get('dist')
        dist_text = '' if dist is None else f'{float(dist):.2f}'
        stations = list(values.get('stations') or [])
        
        expansion = ui.expansion().classes('w-full')
        with expansion.add_slot('header'):
            with ui.row().classes('w-full items-center no-wrap'):
                ui.label(
                    f'{system_name} ({dist_text} ly) — {len(stations)} station(s)'
                )
                ui.space()
                ui.label('click to expand').classes(
                    'text-sm text-gray-500'
                )
        with expansion:
            table_rows = []
            for station_index, station_row in enumerate(stations, start=1):
                station_values = _row_to_dict(station_row)
                station = station_values.get('station')

                table_rows.append(
                    {
                        'row_id': f'local-{system_index}-{station_index}',
                        'station': _station_name(station),
                        'ls': _station_ls_text(station),
                        'age': _format_result_value(station_values.get('age')),
                        'market': yes_no_unknown(_field(station, 'market')),
                        'black_market': yes_no_unknown(_field(station, 'blackMarket')),
                        'shipyard': yes_no_unknown(_field(station, 'shipyard')),
                        'outfitting': yes_no_unknown(_field(station, 'outfitting')),
                        'rearm': yes_no_unknown(_field(station, 'rearm')),
                        'refuel': yes_no_unknown(_field(station, 'refuel')),
                        'repair': yes_no_unknown(_field(station, 'repair')),
                        'pad': pad_text(_field(station, 'maxPadSize')),
                        'planetary': yes_no_unknown(_field(station, 'planetary')),
                        'fleet': yes_no_unknown(_field(station, 'fleet')),
                        'settlement': yes_no_unknown(_field(station, 'settlement')),
                        'items': _format_result_value(station_values.get('item_count')),
                    }
                )
            
            ui.table(
                columns=columns,
                rows=table_rows,
                row_key='row_id',
            ).classes('w-full')

def _render_nav_results(structured_result: Any) -> None:
    payload = _structured_payload(structured_result)
    summary = payload.get('summary')
    rows = payload.get('rows', [])
    
    from_name = _named_result_value(_field(summary, 'fromSys'))
    to_name = _named_result_value(_field(summary, 'toSys'))
    max_ly = _field(summary, 'maxLy')
    
    if from_name and to_name and max_ly is not None:
        ui.label(
            f'Route from {from_name} to {to_name} '
            f'with max {float(max_ly):g} ly per jump.'
        ).classes('text-sm text-gray-600')
    elif rows:
        ui.label(f'{len(rows)} nav hop(s) returned.').classes(
            'text-sm text-gray-600'
        )
    
    ui.label(
        'Expand a system to view the matching stations for that hop.'
    ).classes('text-sm text-gray-600')
    
    if not rows:
        ui.label('No nav rows returned.').classes('text-sm text-gray-600')
        return
    
    def yes_no_unknown(value: Any) -> str:
        return {'Y': 'Yes', 'N': 'No', '?': '?'}.get(str(value or ''), '')
    
    def pad_text(value: Any) -> str:
        return {'S': 'Sml', 'M': 'Med', 'L': 'Lrg', '?': '?'}.get(
            str(value or ''),
            '',
        )
    
    columns = [
        {'name': 'station', 'label': 'Station', 'field': 'station', 'align': 'left'},
        {'name': 'ls', 'label': 'StnLs', 'field': 'ls', 'align': 'right'},
        {'name': 'age', 'label': 'Age/days', 'field': 'age', 'align': 'right'},
        {'name': 'market', 'label': 'Mkt', 'field': 'market', 'align': 'right'},
        {'name': 'black_market', 'label': 'BMk', 'field': 'black_market', 'align': 'right'},
        {'name': 'shipyard', 'label': 'Shp', 'field': 'shipyard', 'align': 'right'},
        {'name': 'outfitting', 'label': 'Out', 'field': 'outfitting', 'align': 'right'},
        {'name': 'rearm', 'label': 'Arm', 'field': 'rearm', 'align': 'right'},
        {'name': 'refuel', 'label': 'Ref', 'field': 'refuel', 'align': 'right'},
        {'name': 'repair', 'label': 'Rep', 'field': 'repair', 'align': 'right'},
        {'name': 'pad', 'label': 'Pad', 'field': 'pad', 'align': 'right'},
        {'name': 'planetary', 'label': 'Plt', 'field': 'planetary', 'align': 'right'},
        {'name': 'fleet', 'label': 'Flc', 'field': 'fleet', 'align': 'right'},
        {'name': 'settlement', 'label': 'Stl', 'field': 'settlement', 'align': 'right'},
        {'name': 'items', 'label': 'Itms', 'field': 'items', 'align': 'right'},
    ]
    
    for system_index, row in enumerate(rows, start=1):
        values = _row_to_dict(row)
        action = _format_result_value(values.get('action'))
        system = values.get('system')
        system_name = _named_result_value(system) or _format_result_value(system)
        jump_ly = values.get('jumpLy')
        total_ly = values.get('totalLy')
        dir_ly = values.get('dirLy')
        stations = list(values.get('stations') or [])
        
        jump_text = '' if jump_ly is None else f'{float(jump_ly):.2f}'
        total_text = '' if total_ly is None else f'{float(total_ly):.2f}'
        dir_text = '' if dir_ly is None else f'{float(dir_ly):.2f}'
        
        expansion = ui.expansion().classes('w-full')
        with expansion.add_slot('header'):
            with ui.row().classes('w-full items-center no-wrap'):
                ui.label(
                    f'{action}: {system_name} '
                    f'(Jump {jump_text} ly, Total {total_text} ly, '
                    f'Remaining {dir_text} ly) — {len(stations)} station(s)'
                )
                ui.space()
                ui.label('click to expand').classes(
                    'text-sm text-gray-500'
                )
        with expansion:
            table_rows = []
            for station_index, station_row in enumerate(stations, start=1):
                station_values = _row_to_dict(station_row)
                station = station_values.get('station')

                table_rows.append(
                    {
                        'row_id': f'nav-{system_index}-{station_index}',
                        'station': _station_name(station),
                        'ls': _station_ls_text(station),
                        'age': _format_result_value(station_values.get('age')),
                        'market': yes_no_unknown(_field(station, 'market')),
                        'black_market': yes_no_unknown(_field(station, 'blackMarket')),
                        'shipyard': yes_no_unknown(_field(station, 'shipyard')),
                        'outfitting': yes_no_unknown(_field(station, 'outfitting')),
                        'rearm': yes_no_unknown(_field(station, 'rearm')),
                        'refuel': yes_no_unknown(_field(station, 'refuel')),
                        'repair': yes_no_unknown(_field(station, 'repair')),
                        'pad': pad_text(_field(station, 'maxPadSize')),
                        'planetary': yes_no_unknown(_field(station, 'planetary')),
                        'fleet': yes_no_unknown(_field(station, 'fleet')),
                        'settlement': yes_no_unknown(_field(station, 'settlement')),
                        'items': _format_result_value(station_values.get('item_count')),
                    }
                )
            
            ui.table(
                columns=columns,
                rows=table_rows,
                row_key='row_id',
            ).classes('w-full')

def _render_olddata_results(structured_result: Any) -> None:
    payload = _structured_payload(structured_result)
    rows = payload.get('rows', [])
    near = str(payload.get('near') or '').strip()
    
    if near:
        ui.label(
            f'{len(rows)} old-data station(s) returned near {near}.'
        ).classes('text-sm text-gray-600')
    elif rows:
        ui.label(f'{len(rows)} old-data station(s) returned.').classes(
            'text-sm text-gray-600'
        )
    
    if not rows:
        ui.label('No old-data rows returned.').classes('text-sm text-gray-600')
        return
    
    def yes_no_unknown(value: Any) -> str:
        return {'Y': 'Yes', 'N': 'No', '?': '?'}.get(str(value or ''), '?')
    
    def pad_text(value: Any) -> str:
        return {'S': 'Sml', 'M': 'Med', 'L': 'Lrg', '?': '?'}.get(
            str(value or ''),
            '?',
        )
    
    def station_text(value: Any) -> str:
        return _station_name(value)
    
    columns = [
        {'name': 'station', 'label': 'Station', 'field': 'station', 'align': 'left'},
    ]
    if near:
        columns.append(
            {'name': 'dist', 'label': 'DistLy', 'field': 'dist', 'align': 'right'}
        )
    columns.extend(
        [
            {'name': 'age', 'label': 'Age/days', 'field': 'age', 'align': 'right'},
            {'name': 'ls', 'label': 'StnLs', 'field': 'ls', 'align': 'right'},
            {'name': 'pad', 'label': 'Pad', 'field': 'pad', 'align': 'right'},
            {'name': 'planetary', 'label': 'Plt', 'field': 'planetary', 'align': 'right'},
            {'name': 'fleet', 'label': 'Flc', 'field': 'fleet', 'align': 'right'},
            {'name': 'settlement', 'label': 'Stl', 'field': 'settlement', 'align': 'right'},
        ]
    )
    
    table_rows = []
    for index, row in enumerate(rows, start=1):
        values = _row_to_dict(row)
        station = values.get('station')
        
        table_row = {
            'row_id': f'olddata-{index}',
            'station': station_text(station),
            'age': _format_result_value(values.get('age')),
            'ls': _station_ls_text(station),
            'pad': pad_text(_field(station, 'maxPadSize')),
            'planetary': yes_no_unknown(_field(station, 'planetary')),
            'fleet': yes_no_unknown(_field(station, 'fleet')),
            'settlement': yes_no_unknown(_field(station, 'settlement')),
        }
        if near:
            dist = values.get('dist')
            table_row['dist'] = '' if dist in (None, '') else f'{float(dist):.2f}'
        table_rows.append(table_row)
    
    ui.table(
        columns=columns,
        rows=table_rows,
        row_key='row_id',
    ).classes('w-full')

def _render_market_results(structured_result: Any) -> None:
    payload = _structured_payload(structured_result)
    summary = payload.get('summary')
    rows = payload.get('rows', [])
    origin = _field(summary, 'origin')
    origin_name = _named_result_value(origin)
    
    if _field(summary, 'buying', False):
        mode_text = 'buying'
    elif _field(summary, 'selling', False):
        mode_text = 'selling'
    else:
        mode_text = 'buying and selling'
    
    if origin_name:
        ui.label(
            f'{len(rows)} market row(s) for {origin_name} ({mode_text}).'
        ).classes('text-sm text-gray-600')
    elif rows:
        ui.label(f'{len(rows)} market row(s) returned.').classes(
            'text-sm text-gray-600'
        )
    
    ui.label(
        'Demand/Supply suffixes: H = high, M = medium, L = low, '
        '- = none, ? = unknown.'
    ).classes('text-sm text-gray-600')
    
    if not rows:
        ui.label('No market rows returned.').classes('text-sm text-gray-600')
        return
    
    buying_only = bool(_field(summary, 'buying', False))
    selling_only = bool(_field(summary, 'selling', False))
    
    def format_price(value: Any) -> str:
        if value in (None, 0):
            return ''
        return f'{int(value):n}'
    
    table_rows = []
    for index, row in enumerate(rows, start=1):
        values = _row_to_dict(row)
        table_rows.append(
            {
                'row_id': f'market-{index}',
                'item': _format_result_value(values.get('item')),
                'buying': format_price(values.get('buyCr')),
                'avg_buy': format_price(values.get('avgBuy')),
                'demand': _format_result_value(values.get('demand')),
                'selling': format_price(values.get('sellCr')),
                'avg_sell': format_price(values.get('avgSell')),
                'supply': _format_result_value(values.get('supply')),
                'age': _format_result_value(values.get('age')),
            }
        )
    
    columns = [
        {'name': 'item', 'label': 'Item', 'field': 'item', 'align': 'left'},
    ]
    if not selling_only:
        columns.extend(
            [
                {'name': 'buying', 'label': 'Buying', 'field': 'buying', 'align': 'right'},
                {'name': 'avg_buy', 'label': 'Avg', 'field': 'avg_buy', 'align': 'right'},
                {'name': 'demand', 'label': 'Demand', 'field': 'demand', 'align': 'right'},
            ]
        )
    if not buying_only:
        columns.extend(
            [
                {'name': 'selling', 'label': 'Selling', 'field': 'selling', 'align': 'right'},
                {'name': 'avg_sell', 'label': 'Avg', 'field': 'avg_sell', 'align': 'right'},
                {'name': 'supply', 'label': 'Supply', 'field': 'supply', 'align': 'right'},
            ]
        )
    columns.append(
        {'name': 'age', 'label': 'Age/Days', 'field': 'age', 'align': 'right'}
    )
    
    ui.table(
        columns=columns,
        rows=table_rows,
        row_key='row_id',
    ).classes('w-full')

def _human_result_summary(summary: Any) -> str | None:
    """Return displayable summary text and suppress opaque object repr noise."""
    if summary is None:
        return None
    
    if isinstance(summary, str):
        text = summary.strip()
        if not text or _looks_like_object_repr(text):
            return None
        return text
    
    if isinstance(summary, (int, float)):
        return _format_result_value(summary)
    
    named_value = _named_result_value(summary)
    if named_value:
        return named_value
    
    return None

def _looks_like_object_repr(text: str) -> bool:
    return (
        text.startswith('<')
        and ' object at 0x' in text
        and text.endswith('>')
    )

# Subprocess workers now return plain snapshot payloads instead of live TD
# objects. Keep the renderer tolerant of both so transport changes stay local
# to the execution boundary.
def _structured_payload(structured_result: Any) -> dict[str, Any]:
    """Normalize TD result adapters onto the summary/rows mapping the UI expects."""
    if isinstance(structured_result, dict):
        return structured_result
    # TD command adapters do not all return the same shape yet; normalise both
    # dict-like and attribute-based payloads before rendering.
    return {
        'summary': getattr(structured_result, 'summary', None),
        'rows': list(getattr(structured_result, 'rows', [])),
    }

def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert result rows into plain mappings that tables can render uniformly."""
    if isinstance(row, dict):
        return dict(row)

    mapping = getattr(row, '_mapping', None)
    if mapping is not None:
        return {str(key): value for key, value in mapping.items()}

    if hasattr(row, '__dict__'):
        # Treat simple result objects like lightweight records and skip private
        # attributes that are not meaningful to the UI.
        return {
            key: value
            for key, value in vars(row).items()
            if not key.startswith('_')
        }

    return {'value': row}

def _format_result_value(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, float):
        return f'{value:g}'
    
    named_value = _named_result_value(value)
    if named_value is not None:
        return named_value
    
    return str(value)

# Result tables may now contain either original TD helper objects or the plain
# dict snapshots produced for multiprocessing transport. Keep name extraction in
# one place so command-specific renderers do not care which side produced them.
def _named_result_value(value: Any) -> str | None:
    """Best-effort extraction for TD model objects and GUI snapshots."""
    if isinstance(value, dict):
        for key in ('name', 'dbname', 'fullname', 'text'):
            named = value.get(key)
            if callable(named):
                try:
                    return str(named(0))
                except TypeError:
                    return str(named())
            if named not in (None, ''):
                return str(named)
        return None

    name = getattr(value, 'name', None)
    if callable(name):
        # TD model objects are inconsistent about whether name() expects a
        # detail level argument, so tolerate both call styles.
        try:
            return str(name(0))
        except TypeError:
            return str(name())
    if name not in (None, ''):
        return str(name)

    dbname = getattr(value, 'dbname', None)
    if callable(dbname):
        try:
            return str(dbname())
        except TypeError:
            try:
                return str(dbname(0))
            except TypeError:
                return str(dbname)
    if dbname not in (None, ''):
        return str(dbname)

    return None