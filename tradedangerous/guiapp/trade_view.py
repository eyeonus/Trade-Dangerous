"""Trade workspace widgets for the station-to-station trade command."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from .profiles import CommandDraft
from .shared_draft_helpers import DraftValueHelper


class TradeWorkspace(DraftValueHelper):
    """Edit a `trade` draft using command-local fields only."""

    def __init__(
        self,
        draft: CommandDraft,
        *,
        on_changed: Callable[[], None],
        on_execute: Callable[[], None],
    ) -> None:
        self.draft = draft
        self.on_changed = on_changed
        self.on_execute = on_execute

    def build(self) -> None:
        with ui.column().classes('w-full gap-3'):
            self._build_route_section()
            self._build_constraint_section()

            with ui.row().classes('gap-2'):
                ui.button('Execute Trade', on_click=self.on_execute)

    def _build_route_section(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('Trade Route')
            ui.label(
                'Enter the station you buy from and the station you sell to.'
            ).classes('text-sm text-gray-600')

            with ui.row().classes('w-full gap-3'):
                ui.input(
                    'Origin',
                    value=self._text_value(self.draft.main_values, 'origin'),
                    on_change=lambda event: self._set_text(
                        self.draft.main_values,
                        'origin',
                        event.value,
                    ),
                ).classes('min-w-96 flex-1')
                ui.input(
                    'Destination',
                    value=self._text_value(self.draft.main_values, 'dest'),
                    on_change=lambda event: self._set_text(
                        self.draft.main_values,
                        'dest',
                        event.value,
                    ),
                ).classes('min-w-96 flex-1')

    def _build_constraint_section(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('Trade Constraints')

            with ui.row().classes('w-full items-end gap-3'):
                ui.number(
                    'Gain / ton',
                    value=self._number_value(
                        self.draft.main_values,
                        'minGainPerTon',
                    ),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.main_values,
                        'minGainPerTon',
                        event.value,
                        'Gain / ton',
                    ),
                ).classes('w-40')
                ui.number(
                    'Supply',
                    value=self._number_value(self.draft.main_values, 'supply'),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.main_values,
                        'supply',
                        event.value,
                        'Supply',
                    ),
                ).classes('w-32')
                ui.number(
                    'Demand',
                    value=self._number_value(self.draft.main_values, 'demand'),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.main_values,
                        'demand',
                        event.value,
                        'Demand',
                    ),
                ).classes('w-32')
                ui.number(
                    'Limit',
                    value=self._number_value(self.draft.main_values, 'limit'),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.main_values,
                        'limit',
                        event.value,
                        'Limit',
                    ),
                ).classes('w-32')

            with ui.row().classes('w-full items-center gap-4'):
                ui.select(
                    {
                        '': 'Default',
                        'fill': 'Fill to capacity',
                        'load': 'Load free space only',
                        'full': 'Full load from scratch',
                    },
                    value=self._text_value(self.draft.main_values, 'cargoMode'),
                    label='Cargo mode',
                    on_change=lambda event: self._set_text(
                        self.draft.main_values,
                        'cargoMode',
                        event.value,
                    ),
                ).classes('w-64')
                ui.checkbox(
                    'Reverse route',
                    value=self._bool_value(self.draft.main_values, 'reverse'),
                    on_change=lambda event: self._set_bool(
                        self.draft.main_values,
                        'reverse',
                        event.value,
                    ),
                )