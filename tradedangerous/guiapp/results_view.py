"""Render structured TD command results into NiceGUI widgets."""

from __future__ import annotations

from typing import Any

from nicegui import ui

_RUN_COLUMNS = [
    {'name': 'commodity', 'label': 'Commodity', 'field': 'commodity', 'align': 'left'},
    {'name': 'qty', 'label': 'Qty', 'field': 'qty', 'align': 'right'},
    {'name': 'buy', 'label': 'Buy', 'field': 'buy', 'align': 'right'},
    {'name': 'sell', 'label': 'Sell', 'field': 'sell', 'align': 'right'},
    {'name': 'gain', 'label': 'Gain / unit', 'field': 'gain', 'align': 'right'},
    {'name': 'total', 'label': 'Total gain', 'field': 'total', 'align': 'right'},
]
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
    if command == 'run' and structured_result:
        if _is_run_route_payload(structured_result):
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

def _is_run_route_payload(structured_result: Any) -> bool:
    if not isinstance(structured_result, (list, tuple)):
        return False

    if not structured_result:
        return False

    return all(
        _field(route, 'hops') is not None
        and (
            _field(route, 'first_station') is not None
            or _field(route, 'route') is not None
            or _field(route, 'firstStation') is not None
        )
        for route in structured_result
    )

def _render_run_results(routes: list[Any]) -> None:
    ui.label(f'{len(routes)} route(s) returned').classes(
        'text-sm text-gray-600'
    )

    for route_index, route in enumerate(routes, start=1):
        hop_payloads = list(_field(route, 'hops', []) or [])
        total_jumps = sum(
            max(0, len(_field(hop, 'jump_path', []) or []) - 1)
            for hop in hop_payloads
        )

        first_station = _field(route, 'first_station')
        if first_station is None:
            first_station = _named_result_value(_field(route, 'firstStation'))
        last_station = _field(route, 'last_station')
        if last_station is None:
            last_station = _named_result_value(_field(route, 'lastStation'))

        gain_cr = _field(route, 'gainCr', 0) or 0
        start_cr = _field(route, 'startCr', 0) or 0
        gpt = _field(route, 'gpt', 0) or 0
        score = _field(route, 'score', 0) or 0

        with ui.card().classes('w-full gap-3'):
            ui.label(
                f'Route {route_index}: {first_station} -> {last_station}'
            ).classes('text-lg')

            with ui.row().classes('w-full gap-4 text-sm'):
                ui.label(f'Gain: {int(gain_cr):n} cr')
                ui.label(f'Gain / ton: {int(gpt):n} cr')
                ui.label(f'Score: {float(score):.2f}')
                ui.label(f'Hops: {len(hop_payloads)}')
                ui.label(f'Jumps: {total_jumps}')
                ui.label(
                    f'Est. final credits: {int(start_cr) + int(gain_cr):n} cr'
                )

            route_points = list(_field(route, 'route', []) or [])
            for hop_index, hop in enumerate(hop_payloads, start=1):
                src_station = _field(hop, 'src_station')
                dst_station = _field(hop, 'dst_station')
                if src_station is None and hop_index - 1 < len(route_points):
                    src_station = _named_result_value(route_points[hop_index - 1])
                if dst_station is None and hop_index < len(route_points):
                    dst_station = _named_result_value(route_points[hop_index])

                expansion = ui.expansion().classes('w-full')
                with expansion.add_slot('header'):
                    with ui.row().classes('w-full items-center no-wrap'):
                        ui.label(
                            f'Hop {hop_index}: {src_station} -> {dst_station}'
                        )
                        ui.space()
                        ui.label('Expand for details').classes(
                            'text-sm text-gray-500'
                        )
                with expansion:
                    units = _field(hop, 'units', 0) or 0
                    hop_gain = _field(hop, 'gainCr', 0) or 0
                    hop_gpt = _field(hop, 'gpt', 0) or 0
                    with ui.row().classes('w-full gap-4 text-sm'):
                        ui.label(f'Units: {int(units):n}')
                        ui.label(f'Hop gain: {int(hop_gain):n} cr')
                        ui.label(f'Gain / ton: {int(hop_gpt):n} cr')

                    rows = []
                    for item_index, item in enumerate(
                        list(_field(hop, 'items', []) or []),
                        start=1,
                    ):
                        qty = _field(item, 'qty', 0) or 0
                        buy = _field(item, 'buy')
                        sell = _field(item, 'sell')
                        gain = _field(item, 'gain')
                        total = _field(item, 'total')
                        rows.append(
                            {
                                'row_id': f'{route_index}-{hop_index}-{item_index}',
                                'commodity': _field(item, 'commodity', ''),
                                'qty': qty,
                                'buy': '' if buy is None else f'{int(buy):n} cr',
                                'sell': '' if sell is None else f'{int(sell):n} cr',
                                'gain': '' if gain is None else f'{int(gain):n} cr',
                                'total': '' if total is None else f'{int(total):n} cr',
                            }
                        )

                    ui.table(
                        columns=_RUN_COLUMNS,
                        rows=rows,
                        row_key='row_id',
                    ).classes('w-full')

                    path = ' -> '.join(
                        str(system)
                        for system in list(_field(hop, 'jump_path', []) or [])
                        if system
                    )
                    if path:
                        ui.label(f'Jump path: {path}').classes(
                            'text-sm text-gray-600'
                        )

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
                'item': _format_result_value(values.get('item')),
                'profit': format_int(values.get('gain')),
                'cost': format_int(values.get('sup_price')),
                'buying': format_int(values.get('dem_price')),
                'src_age': _format_result_value(values.get('sup_age')),
                'dst_age': _format_result_value(values.get('dem_age')),
            }
        )
    
    ui.table(
        columns=[
            {'name': 'item', 'label': 'Item', 'field': 'item', 'align': 'left'},
            {'name': 'profit', 'label': 'Profit', 'field': 'profit', 'align': 'right'},
            {'name': 'cost', 'label': 'Cost', 'field': 'cost', 'align': 'right'},
            {'name': 'buying', 'label': 'Buying', 'field': 'buying', 'align': 'right'},
            {'name': 'src_age', 'label': 'SrcAge', 'field': 'src_age', 'align': 'right'},
            {'name': 'dst_age', 'label': 'DstAge', 'field': 'dst_age', 'align': 'right'},
        ],
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
                        'items': _format_result_value(_field(station, 'itemCount')),
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
                        'items': _format_result_value(_field(station, 'itemCount')),
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