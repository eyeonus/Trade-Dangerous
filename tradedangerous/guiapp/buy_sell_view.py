"""Buy/Sell workspace widgets and draft mutation helpers."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from .autocomplete import build_system_autocomplete_input
from .profiles import CommandDraft
from .shared_draft_helpers import DraftValueHelper
from .shared_filter_view import build_shared_filter_section

class BuySellWorkspace(DraftValueHelper):
    """Edit a `buy` or `sell` draft using the same field semantics as `run`."""
    
    def __init__(
        self,
        command: str,
        draft: CommandDraft,
        *,
        on_changed: Callable[[], None],
        on_execute: Callable[[], None],
        suggest_systems: Callable[[str], list[object]] | None = None,
    ) -> None:
        self.command = command
        self.draft = draft
        self.on_changed = on_changed
        self.on_execute = on_execute
        self.suggest_systems = suggest_systems
    
    def build(self) -> None:
        action = 'Buy' if self.command == 'buy' else 'Sell'
        # Keep the main pane focused on the common search inputs; the dialog
        # carries the less-frequent CLI switches.
        extended_dialog = self._build_extended_dialog()
        
        with ui.column().classes('w-full gap-3'):
            self._build_search_section(action)
            self._build_filter_section()
            
            with ui.row().classes('gap-2'):
                ui.button('Extended Options', on_click=extended_dialog.open)
                ui.button(f'Execute {action}', on_click=self.on_execute)
    
    def _build_search_section(self, action: str) -> None:
        with ui.card().classes('w-full'):
            ui.label(f'{action} Search')
            
            if self.command == 'buy':
                ui.label(
                    'Enter one item name, or a comma-separated list.'
                ).classes('text-sm text-gray-600')
            else:
                ui.label(
                    'Sell searches a single item. '
                    'Use Near like the same kind of location anchor as Run From.'
                ).classes('text-sm text-gray-600')
            
            with ui.row().classes('w-full gap-3'):
                ui.input(
                    'Item search',
                    value=self._text_value(self.draft.main_values, 'search'),
                    on_change=lambda event: self._set_text(
                        self.draft.main_values,
                        'search',
                        event.value,
                    ),
                ).classes('min-w-96 flex-1').tooltip(
                    'Items or ships to look for. Enter one name or a '
                    'comma-separated list.' if self.command == 'buy' else
                    'Name of the item you want to sell. One item only.'
                )
                
                build_system_autocomplete_input(
                    label='Near',
                    value=self._text_value(self.draft.main_values, 'near'),
                    on_text_changed=lambda value: self._set_text(
                        self.draft.main_values,
                        'near',
                        value,
                    ),
                    tooltip=(
                        'Find sellers within jump range of this system.'
                        if self.command == 'buy' else
                        'Find buyers within jump range of this system.'
                    ),
                    suggest_systems=self.suggest_systems,
                    input_classes='min-w-80 flex-1',
                )
            
            with ui.row().classes('w-full items-end gap-3'):
                ui.number(
                    'Distance (ly)',
                    value=self._number_value(self.draft.main_values, 'distance'),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.main_values,
                        'distance',
                        event.value,
                        'Distance',
                    ),
                ).classes('w-40').tooltip(
                    'Requires Near. Systems within this range of Near.'
                    if self.command == 'buy' else
                    'Maximum light years per jump when searching buyers '
                    'near the specified system.'
                )
                ui.number(
                    'Supply' if self.command == 'buy' else 'Demand',
                    value=self._number_value(
                        self.draft.main_values,
                        'supply' if self.command == 'buy' else 'demand',
                    ),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.main_values,
                        'supply' if self.command == 'buy' else 'demand',
                        event.value,
                        'Supply' if self.command == 'buy' else 'Demand',
                    ),
                ).classes('w-40').tooltip(
                    'Limit to stations known to have at least this much '
                    'supply.' if self.command == 'buy' else
                    'Limit to stations known to have at least this much '
                    'demand.'
                )
    
    def _build_filter_section(self) -> None:
        # Reuse the same tri-state and pad-size UI so command workspaces stay
        # aligned on the shared TD filtering semantics.
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
    
    def _build_extended_dialog(self) -> ui.dialog:
        # Dialog-only switches land in advanced_values so the executor can layer
        # them on top of the basic search fields without special cases.
        dialog = ui.dialog()
        with dialog:
            with ui.card().style('min-width: 64rem; max-width: 95vw;'):
                ui.label('Extended Options')
                ui.label(
                    'These are the less common Buy/Sell options. '
                    'Leave a field blank to omit it.'
                ).classes('text-sm text-gray-600')
                
                with ui.column().classes('w-full gap-5'):
                    self._build_extended_constraint_section()
                    self._build_extended_station_section()
                    self._build_extended_output_section()
                
                with ui.row().classes('justify-end'):
                    ui.button('Close', on_click=dialog.close)
        
        return dialog
    
    def _build_extended_constraint_section(self) -> None:
        with ui.column().classes('w-full gap-3'):
            ui.label('Search constraints')
            
            with ui.row().classes('w-full gap-3'):
                ui.number(
                    'Limit',
                    value=self._number_value(
                        self.draft.advanced_values,
                        'limit',
                    ),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.advanced_values,
                        'limit',
                        event.value,
                        'Limit',
                    ),
                ).classes('w-32').tooltip(
                    'Maximum number of results to list.'
                )
                if self.command == 'buy':
                    ui.number(
                        'LS max',
                        value=self._number_value(
                            self.draft.advanced_values,
                            'maxLs',
                        ),
                        min=0,
                        step=1,
                        precision=0,
                        on_change=lambda event: self._set_int(
                            self.draft.advanced_values,
                            'maxLs',
                            event.value,
                            'LS max',
                        ),
                    ).classes('w-40').tooltip(
                        'Only consider stations up to this many ls from '
                        'their star.'
                    )
                ui.number(
                    'GT',
                    value=self._number_value(
                        self.draft.advanced_values,
                        'gt',
                    ),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.advanced_values,
                        'gt',
                        event.value,
                        'GT',
                    ),
                ).classes('w-32').tooltip(
                    'Limit to prices above Ncr.'
                )
                ui.number(
                    'LT',
                    value=self._number_value(
                        self.draft.advanced_values,
                        'lt',
                    ),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.advanced_values,
                        'lt',
                        event.value,
                        'LT',
                    ),
                ).classes('w-32').tooltip(
                    'Limit to prices below Ncr.'
                )
    
    def _build_extended_station_section(self) -> None:
        with ui.column().classes('w-full gap-3'):
            ui.label('Station constraints')
            
            with ui.row().classes('w-full gap-4'):
                ui.checkbox(
                    'Space stations only',
                    value=self._bool_value(
                        self.draft.advanced_values,
                        'noPlanet',
                    ),
                    on_change=lambda event: self._set_bool(
                        self.draft.advanced_values,
                        'noPlanet',
                        event.value,
                    ),
                ).tooltip(
                    'Require stations to be in space.'
                )
                ui.checkbox(
                    'Black market only',
                    value=self._bool_value(
                        self.draft.advanced_values,
                        'blackMarket',
                    ),
                    on_change=lambda event: self._set_bool(
                        self.draft.advanced_values,
                        'blackMarket',
                        event.value,
                    ),
                ).tooltip(
                    'Require stations known to have a black market.'
                )
    
    def _build_extended_output_section(self) -> None:
        with ui.column().classes('w-full gap-3'):
            ui.label('Sorting and output')
            
            with ui.row().classes('w-full gap-4'):
                ui.checkbox(
                    'Sort by price',
                    value=self._bool_value(
                        self.draft.advanced_values,
                        'sortByPrice',
                    ),
                    on_change=lambda event: self._set_bool(
                        self.draft.advanced_values,
                        'sortByPrice',
                        event.value,
                    ),
                ).tooltip(
                    'When using Near, sort by price instead of distance.'
                )
                
                if self.command == 'buy':
                    ui.checkbox(
                        'One stop',
                        value=self._bool_value(
                            self.draft.advanced_values,
                            'oneStop',
                        ),
                        on_change=lambda event: self._set_bool(
                            self.draft.advanced_values,
                            'oneStop',
                            event.value,
                        ),
                    ).tooltip(
                        'Only list stations that carry all items listed.'
                    )
                    ui.checkbox(
                        'Sort by units',
                        value=self._bool_value(
                            self.draft.advanced_values,
                            'sortByUnits',
                        ),
                        on_change=lambda event: self._set_bool(
                            self.draft.advanced_values,
                            'sortByUnits',
                            event.value,
                        ),
                    ).tooltip(
                        'Sort by available units followed by price.'
                    )
