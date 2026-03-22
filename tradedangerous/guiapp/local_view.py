"""Local workspace widgets for nearby-system station searches."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from .profiles import CommandDraft
from .shared_draft_helpers import DraftValueHelper
from .shared_filter_view import build_shared_filter_section


class LocalWorkspace(DraftValueHelper):
    """Edit a `local` draft using command-local fields only."""

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
            self._build_search_section()
            self._build_filter_section()
            with ui.row().classes('gap-2'):
                ui.button('Execute Local', on_click=self.on_execute)

    def _build_search_section(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('Local Search')
            ui.label(
                'Find nearby systems and matching stations around a system. '
                'Max data age is inherited from the left pane.'
            ).classes('text-sm text-gray-600')
            with ui.row().classes('w-full items-end gap-3'):
                ui.input(
                    'Near',
                    value=self._text_value(self.draft.main_values, 'near'),
                    on_change=lambda event: self._set_text(
                        self.draft.main_values,
                        'near',
                        event.value,
                    ),
                ).classes('min-w-96 flex-1')
                ui.number(
                    'Distance (ly)',
                    value=self._number_value(self.draft.main_values, 'ly'),
                    min=0,
                    step=0.1,
                    precision=2,
                    on_change=lambda event: self._set_float(
                        self.draft.main_values,
                        'ly',
                        event.value,
                    ),
                ).classes('w-40')
                ui.checkbox(
                    'Trading only',
                    value=self._bool_value(self.draft.main_values, 'trading'),
                    on_change=lambda event: self._set_bool(
                        self.draft.main_values,
                        'trading',
                        event.value,
                    ),
                )

    def _build_filter_section(self) -> None:
        def build_service_filters() -> None:
            with ui.row().classes('w-full gap-4'):
                ui.checkbox('Black market', value=self._bool_value(self.draft.main_values, 'blackMarket'), on_change=lambda event: self._set_bool(self.draft.main_values, 'blackMarket', event.value))
                ui.checkbox('Shipyard', value=self._bool_value(self.draft.main_values, 'shipyard'), on_change=lambda event: self._set_bool(self.draft.main_values, 'shipyard', event.value))
                ui.checkbox('Outfitting', value=self._bool_value(self.draft.main_values, 'outfitting'), on_change=lambda event: self._set_bool(self.draft.main_values, 'outfitting', event.value))
                ui.checkbox('Rearm', value=self._bool_value(self.draft.main_values, 'rearm'), on_change=lambda event: self._set_bool(self.draft.main_values, 'rearm', event.value))
                ui.checkbox('Refuel', value=self._bool_value(self.draft.main_values, 'refuel'), on_change=lambda event: self._set_bool(self.draft.main_values, 'refuel', event.value))
                ui.checkbox('Repair', value=self._bool_value(self.draft.main_values, 'repair'), on_change=lambda event: self._set_bool(self.draft.main_values, 'repair', event.value))
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
            post_builder=build_service_filters,
        )
