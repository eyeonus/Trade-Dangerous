"""Buy/Sell workspace widgets and draft mutation helpers."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from .autocomplete import build_system_autocomplete_input
from .autocomplete import AutocompleteInput, build_system_autocomplete_input
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
        suggest_items: Callable[[str], list[object]] | None = None,
        suggest_buy_search: Callable[[str], list[object]] | None = None,
    ) -> None:
        self.command = command
        self.draft = draft
        self.on_changed = on_changed
        self.on_execute = on_execute
        self.suggest_systems = suggest_systems
        self.suggest_items = suggest_items
        self.suggest_buy_search = suggest_buy_search
        self.buy_search_dialog = None
        self.buy_search_summary_label = None
        self.buy_search_list_host = None
        self.buy_search_input_control = None
        self.buy_search_candidate_text = ''
    
    def build(self) -> None:
        action = 'Buy' if self.command == 'buy' else 'Sell'
        # Keep the main pane focused on the common search inputs; the dialog
        # carries the less-frequent CLI switches.
        extended_dialog = self._build_extended_dialog()
        self.buy_search_dialog = (
            self._build_buy_search_dialog()
            if self.command == 'buy' else
            None
        )
        
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
                    'Use the search editor to add categories, items, or ships. '
                    'Max data age is inherited from the left pane.'
                ).classes('text-sm text-gray-600')
            else:
                ui.label(
                    'Sell searches a single item. '
                    'Max data age is inherited from the left pane.'
                ).classes('text-sm text-gray-600')
            
            with ui.row().classes('w-full gap-3'):
                if self.command == 'buy':
                    with ui.column().classes('min-w-96 flex-1 gap-1'):
                        ui.label('Search')
                        with ui.row().classes('w-full items-center gap-3 no-wrap'):
                            self.buy_search_summary_label = ui.label(
                                self._buy_search_summary()
                            ).classes('min-w-0 flex-1 text-sm text-gray-600')
                            ui.button(
                                'Edit Search...',
                                on_click=self.buy_search_dialog.open,
                            ).tooltip(
                                'Add categories, items, or ships to search for.'
                            )
                elif self.suggest_items is not None:
                    AutocompleteInput(
                        label='Item search',
                        value=self._text_value(self.draft.main_values, 'search'),
                        fetch_suggestions=self.suggest_items,
                        on_text_changed=lambda value: self._set_text(
                            self.draft.main_values,
                            'search',
                            value,
                        ),
                        tooltip='Name of the item you want to sell. One item only.',
                        input_classes='min-w-96 flex-1',
                    ).build()
                else:
                    ui.input(
                        'Item search',
                        value=self._text_value(self.draft.main_values, 'search'),
                        on_change=lambda event: self._set_text(
                            self.draft.main_values,
                            'search',
                            event.value,
                        ),
                    ).classes('min-w-96 flex-1').tooltip(
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
                    'demand.'
                )
    
    def _build_buy_search_dialog(self) -> ui.dialog:
        dialog = ui.dialog()
        with dialog, ui.card().classes('gap-3').style(
            'min-width: 52rem; max-width: 95vw; min-height: 34rem;'
        ):
            ui.label('Edit Buy Search')
            ui.label(
                'Add categories, items, or ships to search for.'
            ).classes('text-sm text-gray-600')
            
            with ui.row().classes('w-full items-end gap-6 no-wrap'):
                if self.suggest_buy_search is None:
                    self.buy_search_input_control = ui.input(
                        'Search term',
                        value=self.buy_search_candidate_text,
                        on_change=lambda event: self._set_buy_search_candidate_text(
                            event.value,
                        ),
                    ).classes('min-w-96 flex-1').tooltip(
                        'Add a category, item, or ship.'
                    )
                else:
                    self.buy_search_input_control = AutocompleteInput(
                        label='Search term',
                        value=self.buy_search_candidate_text,
                        fetch_suggestions=self.suggest_buy_search,
                        on_text_changed=self._set_buy_search_candidate_text,
                        tooltip='Add a category, item, or ship.',
                        input_classes='min-w-96 flex-1',
                    )
                    self.buy_search_input_control.build()
                
                ui.button('Add', on_click=self._on_add_buy_search)
            
            self.buy_search_list_host = ui.column().classes('w-full gap-2')
            self._refresh_buy_search_list()
            
            with ui.row().classes('w-full justify-end'):
                ui.button('Close', on_click=dialog.close)
        
        return dialog
    
    def _buy_search_entries(self) -> list[str]:
        entries: list[str] = []
        raw = self._text_value(self.draft.main_values, 'search')
        
        for line in raw.splitlines():
            for part in line.split(','):
                cleaned = part.strip()
                if cleaned:
                    entries.append(cleaned)
        
        return entries
    
    def _set_buy_search_entries(self, entries: list[str]) -> None:
        cleaned_entries = [entry.strip() for entry in entries if entry.strip()]
        
        if cleaned_entries:
            self.draft.main_values['search'] = '\n'.join(cleaned_entries)
        else:
            self.draft.main_values.pop('search', None)
        
        self.on_changed()
        self._refresh_buy_search_summary()
        self._refresh_buy_search_list()
    
    def _buy_search_summary(self) -> str:
        entries = self._buy_search_entries()
        if not entries:
            return 'No search entries selected.'
        
        preview = ', '.join(entries[:3])
        if len(entries) > 3:
            preview += ', ...'
        
        noun = 'entry' if len(entries) == 1 else 'entries'
        return f'{len(entries)} {noun}: {preview}'
    
    def _refresh_buy_search_summary(self) -> None:
        if self.buy_search_summary_label is None:
            return
        self.buy_search_summary_label.text = self._buy_search_summary()
    
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
    
    def _set_buy_search_candidate_text(self, value: str) -> None:
        self.buy_search_candidate_text = str(value or '').strip()
    
    def _clear_buy_search_candidate_text(self) -> None:
        self.buy_search_candidate_text = ''
        control = self.buy_search_input_control
        
        if control is None:
            return
        
        clear = getattr(control, 'clear', None)
        if callable(clear):
            clear()
            return
        
        set_value = getattr(control, 'set_value', None)
        if callable(set_value):
            set_value('')
            return
        
        if hasattr(control, 'value'):
            control.value = ''
    
    def _resolve_buy_search_value(self, value: str) -> str | None:
        cleaned = str(value or '').strip()
        if cleaned == '':
            return None
        
        if self.suggest_buy_search is None:
            return cleaned
        
        try:
            suggestions = self.suggest_buy_search(cleaned)
        except TypeError:
            suggestions = []
        
        for suggestion in suggestions:
            suggestion_value = str(
                getattr(suggestion, 'value', '') or ''
            ).strip()
            if suggestion_value.casefold() == cleaned.casefold():
                return suggestion_value
        
        return None
    
    def _on_add_buy_search(self) -> None:
        entry = self._resolve_buy_search_value(self.buy_search_candidate_text)
        if entry is None:
            ui.notify(
                'Choose a valid category, item, or ship for Buy Search.',
                color='warning',
            )
            return
        
        entries = self._buy_search_entries()
        if any(existing.casefold() == entry.casefold() for existing in entries):
            ui.notify(
                f'{entry} is already in Search.',
                color='warning',
            )
            return
        
        entries.append(entry)
        self._set_buy_search_entries(entries)
        self._clear_buy_search_candidate_text()
    
    def _remove_buy_search(self, index: int) -> None:
        entries = self._buy_search_entries()
        if index < 0 or index >= len(entries):
            return
        
        entries.pop(index)
        self._set_buy_search_entries(entries)
    
    def _refresh_buy_search_list(self) -> None:
        if self.buy_search_list_host is None:
            return
        
        entries = self._buy_search_entries()
        self.buy_search_list_host.clear()
        
        with self.buy_search_list_host:
            if not entries:
                ui.label('No search entries selected.').classes(
                    'text-sm text-gray-600'
                )
                return
            
            ui.label(
                'Selected entries are passed to the buy command as a list.'
            ).classes('text-sm text-gray-600')
            
            for index, entry in enumerate(entries):
                with ui.row().classes('w-full items-center gap-3 no-wrap'):
                    ui.label(entry).classes('min-w-0 flex-1')
                    ui.button(
                        'Remove',
                        on_click=lambda idx=index: self._remove_buy_search(idx),
                    ).props('outline dense')
    
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
                        'Rares only',
                        value=self._bool_value(
                            self.draft.advanced_values,
                            'rare',
                        ),
                        on_change=lambda event: self._set_bool(
                            self.draft.advanced_values,
                            'rare',
                            event.value,
                        ),
                    ).tooltip(
                        'Only show rare commodities with stock available.'
                    )
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
