from __future__ import annotations
from typing import Callable
from nicegui import ui
from .profiles import CommandDraft
from .shared_draft_helpers import DraftValueHelper
from .shared_filter_view import build_shared_filter_section

class OldDataWorkspace(DraftValueHelper):
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
                ui.button('Execute Old Data', on_click=self.on_execute)
                ui.button('Extended Options', on_click=dialog.open)
    def _build_search_section(self) -> None:
        values = self.draft.main_values
        with ui.card().classes('w-full'):
            ui.label('Old Data Search')
            ui.label(
                'Find stations with stale market data so you can revisit and '
                'refresh them. Left-pane max data age is not used here.'
            ).classes('text-sm text-gray-600')
            ui.input('Near', value=self._text_value(values, 'near'), on_change=lambda event: self._set_text(values, 'near', event.value)).classes('w-full')
            with ui.row().classes('w-full items-end gap-3'):
                ui.number('Distance (ly)', value=self._number_value(values, 'ly'), min=0, step=0.1, precision=2, on_change=lambda event: self._set_float(values, 'ly', event.value)).classes('w-40')
                ui.number(
                    'Minimum age (days)',
                    value=self._number_value(values, 'minAge'),
                    min=0,
                    step=0.1,
                    precision=2,
                    on_change=lambda event: self._set_float(values, 'minAge', event.value),
                ).classes('w-48')
                ui.checkbox(
                    'Sort to shortest path',
                    value=self._bool_value(values, 'route'),
                    on_change=lambda event: self._set_bool(values, 'route', event.value),
                )
    def _build_filter_section(self) -> None:
        values = self.draft.main_values
        build_shared_filter_section(
            get_bool=lambda key: self._bool_value(values, key),
            get_tri_state=lambda key: self._tri_state_value(values, key),
            set_bool=lambda key, value: self._set_bool(values, key, value),
            set_tri_state=lambda key, value: self._set_tri_state(values, key, value),
            pad_size_enabled=self._pad_size_enabled,
            set_pad_size_flag=self._set_pad_size_flag,
        )
    def _build_extended_dialog(self) -> ui.dialog:
        values = self.draft.advanced_values
        dialog = ui.dialog()
        with dialog, ui.card().style('min-width: 48rem; max-width: 95vw;'):
            ui.label('Extended Options')
            with ui.row().classes('w-full items-center gap-3'):
                ui.number('Limit', value=self._number_value(values, 'limit'), min=0, step=1, precision=0, on_change=lambda event: self._set_int(values, 'limit', event.value, 'Limit')).classes('w-32')
                ui.label(
                    'Maximum number of stations to return.'
                ).classes('text-sm text-gray-600')
            with ui.row().classes('w-full items-center gap-3'):
                ui.number('LS max', value=self._number_value(values, 'lsMax'), min=0, step=1, precision=0, on_change=lambda event: self._set_int(values, 'lsMax', event.value, 'LS max')).classes('w-40')
                ui.label(
                    'Only include stations within this many ls of arrival.'
                ).classes('text-sm text-gray-600')
        return dialog
