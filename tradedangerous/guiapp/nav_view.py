"""Nav workspace widgets for route planning between two places."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from .profiles import CommandDraft
from .shared_draft_helpers import DraftValueHelper
from .shared_filter_view import build_shared_filter_section


class NavWorkspace(DraftValueHelper):
    """Edit a `nav` draft using command-local fields only."""

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
            self._build_option_section()
            self._build_filter_section()
            with ui.row().classes('gap-2'):
                ui.button('Execute Nav', on_click=self.on_execute)

    def _build_route_section(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('Navigation Route')
            ui.label(
                'Find a route between two places. '
                'The GUI always requests detailed system and station results.'
            ).classes('text-sm text-gray-600')
            with ui.row().classes('w-full items-end gap-3'):
                ui.input(
                    'Start',
                    value=self._text_value(self.draft.main_values, 'starting'),
                    on_change=lambda event: self._set_text(
                        self.draft.main_values,
                        'starting',
                        event.value,
                    ),
                ).classes('min-w-96 flex-1')
                ui.input(
                    'End',
                    value=self._text_value(self.draft.main_values, 'ending'),
                    on_change=lambda event: self._set_text(
                        self.draft.main_values,
                        'ending',
                        event.value,
                    ),
                ).classes('min-w-96 flex-1')
                ui.number(
                    'Max jump (ly)',
                    value=self._number_value(self.draft.main_values, 'lyPer'),
                    min=0,
                    step=0.1,
                    precision=2,
                    on_change=lambda event: self._set_float(
                        self.draft.main_values,
                        'lyPer',
                        event.value,
                    ),
                ).classes('w-40')

    def _build_option_section(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('Navigation Options')
            with ui.row().classes('w-full items-end gap-3'):
                ui.textarea(
                    'Via',
                    value=self._text_value(self.draft.main_values, 'via'),
                    on_change=lambda event: self._set_text(
                        self.draft.main_values,
                        'via',
                        event.value,
                    ),
                ).props('autogrow').classes('min-w-96 flex-1')
                ui.textarea(
                    'Avoid',
                    value=self._text_value(self.draft.main_values, 'avoid'),
                    on_change=lambda event: self._set_text(
                        self.draft.main_values,
                        'avoid',
                        event.value,
                    ),
                ).props('autogrow').classes('min-w-96 flex-1')
                ui.number(
                    'Refuel jumps',
                    value=self._number_value(
                        self.draft.main_values,
                        'refuelJumps',
                    ),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.main_values,
                        'refuelJumps',
                        event.value,
                        'Refuel jumps',
                    ),
                ).classes('w-40')

    def _build_filter_section(self) -> None:
        build_shared_filter_section(
            get_bool=lambda key: self._bool_value(self.draft.main_values, key),
            get_tri_state=lambda key: self._tri_state_value(
                self.draft.main_values,
                key,
            ),
            set_bool=lambda key, value: self._set_bool(
                self.draft.main_values,
                key,
                value,
            ),
            set_tri_state=lambda key, value: self._set_tri_state(
                self.draft.main_values,
                key,
                value,
            ),
            pad_size_enabled=self._pad_size_enabled,
            set_pad_size_flag=self._set_pad_size_flag,
        )
