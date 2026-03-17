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


def render_command_results(
    command: str,
    structured_result: Any,
    raw_output: str,
) -> None:
    if command == 'run' and structured_result:
        _render_run_results(structured_result)
        return

    if command in {'buy', 'sell'} and structured_result:
        _render_generic_structured_results(command, structured_result)
        return

    if raw_output:
        ui.label(raw_output).classes('font-mono text-sm whitespace-pre-wrap')
        return

    ui.label('Nothing has been executed yet.')


def _render_run_results(routes: list[Any]) -> None:
    ui.label(f'{len(routes)} route(s) returned').classes(
        'text-sm text-gray-600'
    )

    for route_index, route in enumerate(routes, start=1):
        # Each stored jump path includes its endpoints, so subtract the repeated
        # origin system from every segment when presenting a jump count.
        total_jumps = sum(max(0, len(jumps) - 1) for jumps in route.jumps)

        with ui.card().classes('w-full gap-3'):
            ui.label(
                f'Route {route_index}: '
                f'{route.firstStation.name()} → {route.lastStation.name()}'
            ).classes('text-lg')

            with ui.row().classes('w-full gap-4 text-sm'):
                ui.label(f'Gain: {route.gainCr:n} cr')
                ui.label(f'Gain / ton: {int(route.gpt):n} cr')
                ui.label(f'Score: {route.score:.2f}')
                ui.label(f'Hops: {len(route.hops)}')
                ui.label(f'Jumps: {total_jumps}')
                ui.label(
                    f'Est. final credits: {route.startCr + route.gainCr:n} cr'
                )

            for hop_index, hop in enumerate(route.hops, start=1):
                src_station = route.route[hop_index - 1]
                dst_station = route.route[hop_index]

                with ui.expansion(
                    f'Hop {hop_index}: '
                    f'{src_station.name()} → {dst_station.name()}'
                ).classes('w-full'):
                    with ui.row().classes('w-full gap-4 text-sm'):
                        ui.label(f'Units: {hop.units:n}')
                        ui.label(f'Hop gain: {hop.gainCr:n} cr')
                        ui.label(f'Gain / ton: {int(hop.gpt):n} cr')

                    rows = [
                        {
                            'row_id': f'{route_index}-{hop_index}-{item_index}',
                            'commodity': trade.name(0),
                            'qty': qty,
                            'buy': f'{trade.costCr:n} cr',
                            'sell': f'{trade.costCr + trade.gainCr:n} cr',
                            'gain': f'{trade.gainCr:n} cr',
                            'total': f'{trade.gainCr * qty:n} cr',
                        }
                        for item_index, (trade, qty) in enumerate(
                            hop.items,
                            start=1,
                        )
                    ]

                    ui.table(
                        columns=_RUN_COLUMNS,
                        rows=rows,
                        row_key='row_id',
                    ).classes('w-full')

                    if hop_index - 1 < len(route.jumps):
                        path = ' → '.join(
                            system.name()
                            for system in route.jumps[hop_index - 1]
                        )
                        if path:
                            ui.label(f'Jump path: {path}').classes(
                                'text-sm text-gray-600'
                            )


def _render_generic_structured_results(
    command: str,
    structured_result: Any,
) -> None:
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


def _human_result_summary(summary: Any) -> str | None:
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


def _structured_payload(structured_result: Any) -> dict[str, Any]:
    if isinstance(structured_result, dict):
        return structured_result
    # TD command adapters do not all return the same shape yet; normalise both
    # dict-like and attribute-based payloads before rendering.
    return {
        'summary': getattr(structured_result, 'summary', None),
        'rows': list(getattr(structured_result, 'rows', [])),
    }

def _row_to_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)

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

def _named_result_value(value: Any) -> str | None:
    name = getattr(value, 'name', None)
    if not callable(name):
        return None

    # TD model objects are inconsistent about whether name() expects a detail
    # level argument, so tolerate both call styles for display purposes.
    try:
        return str(name(0))
    except TypeError:
        return str(name())