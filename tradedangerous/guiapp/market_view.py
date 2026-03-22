"""Market workspace widgets for the station inventory command."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from .profiles import CommandDraft
from .shared_draft_helpers import DraftValueHelper


class MarketWorkspace(DraftValueHelper):
    """Edit a `market` draft using command-local fields only."""

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
            self._build_station_section()
            self._build_view_section()
            with ui.row().classes('gap-2'):
                ui.button('Execute Market', on_click=self.on_execute)

    def _build_station_section(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('Market Station')
            ui.label(
                'Enter the station whose market data you want to inspect.'
            ).classes('text-sm text-gray-600')
            ui.input(
                'Station',
                value=self._text_value(self.draft.main_values, 'origin'),
                on_change=lambda event: self._set_text(
                    self.draft.main_values,
                    'origin',
                    event.value,
                ),
            ).classes('min-w-96 w-full')

    def _build_view_section(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('Market View')
            ui.label(
                'Full detail is always shown, including averages and demand.'
            ).classes('text-sm text-gray-600')
            with ui.row().classes('w-full gap-3'):
                ui.select(
                    {
                        '': 'Buying and selling',
                        'buying': 'Buying only',
                        'selling': 'Selling only',
                    },
                    value=self._text_value(self.draft.main_values, 'mode'),
                    label='Side',
                    on_change=lambda event: self._set_text(
                        self.draft.main_values,
                        'mode',
                        event.value,
                    ),
                ).classes('w-64')