"""Rares workspace widgets for the rare-goods lookup command."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from .profiles import CommandDraft
from .shared_draft_helpers import DraftValueHelper
from .shared_filter_view import build_shared_filter_section


class RaresWorkspace(DraftValueHelper):
    """Edit a `rares` draft using command-local fields only."""

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
        dialog = self._build_extended_dialog()
        with ui.column().classes('w-full gap-3'):
            self._build_search_section()
            self._build_filter_section()
            with ui.row().classes('gap-2'):
                ui.button('Execute Rares', on_click=self.on_execute)
                ui.button('Extended Options', on_click=dialog.open)

    def _build_search_section(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('Rare Search')
            ui.label(
                'Find rare goods near a system. Full detail is always shown.'
            ).classes('text-sm text-gray-600')
            with ui.row().classes('w-full items-end gap-3'):
                ui.input(
                    'Near',
                    value=self._text_value(self.draft.main_values, 'near'),
                    on_change=lambda event: self._set_text(
                        self.draft.main_values, 'near', event.value
                    ),
                ).classes('min-w-96 flex-1')
                ui.number(
                    'Distance (ly)',
                    value=self._number_value(self.draft.main_values, 'ly'),
                    min=0,
                    step=0.1,
                    precision=2,
                    on_change=lambda event: self._set_float(
                        self.draft.main_values, 'ly', event.value
                    ),
                ).classes('w-40')

    def _build_filter_section(self) -> None:
        build_shared_filter_section(
            get_bool=lambda key: self._bool_value(self.draft.main_values, key),
            get_tri_state=lambda key: self._tri_state_value(self.draft.main_values, key),
            set_bool=lambda key, value: self._set_bool(self.draft.main_values, key, value),
            set_tri_state=lambda key, value: self._set_tri_state(self.draft.main_values, key, value),
            pad_size_enabled=self._pad_size_enabled,
            set_pad_size_flag=self._set_pad_size_flag,
        )

    def _build_extended_dialog(self) -> ui.dialog:
        dialog = ui.dialog()
        with dialog, ui.card().style('min-width: 56rem; max-width: 95vw;'):
            ui.label('Extended Options')
            ui.label(
                'Leave fields blank to omit them. Away-from systems may be '
                'comma-separated or one per line.'
            ).classes('text-sm text-gray-600')
            with ui.row().classes('w-full gap-3'):
                ui.number(
                    'Limit',
                    value=self._number_value(self.draft.advanced_values, 'limit'),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.advanced_values, 'limit', event.value, 'Limit'
                    ),
                ).classes('w-32')
                ui.select(
                    {'': 'Any', 'legal': 'Legal only', 'illegal': 'Illegal only'},
                    value=self._text_value(self.draft.advanced_values, 'legalMode'),
                    label='Legality',
                    on_change=lambda event: self._set_text(
                        self.draft.advanced_values, 'legalMode', event.value
                    ),
                ).classes('w-48')
                ui.checkbox(
                    'Sort by price',
                    value=self._bool_value(self.draft.advanced_values, 'sortByPrice'),
                    on_change=lambda event: self._set_bool(
                        self.draft.advanced_values, 'sortByPrice', event.value
                    ),
                )
                ui.checkbox(
                    'Reverse order',
                    value=self._bool_value(self.draft.advanced_values, 'reverse'),
                    on_change=lambda event: self._set_bool(
                        self.draft.advanced_values, 'reverse', event.value
                    ),
                )
            with ui.row().classes('w-full gap-3'):
                ui.number(
                    'Away distance (ly)',
                    value=self._number_value(self.draft.advanced_values, 'away'),
                    min=0,
                    step=0.1,
                    precision=2,
                    on_change=lambda event: self._set_float(
                        self.draft.advanced_values, 'away', event.value
                    ),
                ).classes('w-48')
                ui.textarea(
                    'Away from systems',
                    value=self._text_value(self.draft.advanced_values, 'awayFrom'),
                    on_change=lambda event: self._set_text(
                        self.draft.advanced_values, 'awayFrom', event.value
                    ),
                ).classes('min-w-96 flex-1')
            with ui.row().classes('justify-end'):
                ui.button('Close', on_click=dialog.close)
        return dialog
