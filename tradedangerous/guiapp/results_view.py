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

    if raw_output:
        ui.label(raw_output).classes('font-mono text-sm whitespace-pre-wrap')
        return

    ui.label('Nothing has been executed yet.')


def _render_run_results(routes: list[Any]) -> None:
    ui.label(f'{len(routes)} route(s) returned').classes(
        'text-sm text-gray-600'
    )

    for route_index, route in enumerate(routes, start=1):
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
