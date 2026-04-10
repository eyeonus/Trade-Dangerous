"""Run-command workspace widgets and draft mutation helpers."""

from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

from .autocomplete import AutocompleteInput, build_system_autocomplete_input
from .profiles import CommandDraft
from .shared_draft_helpers import DraftValueHelper
from .shared_filter_view import build_shared_filter_section

class RunWorkspace(DraftValueHelper):
    """Edit a `run` command draft without knowing anything about persistence."""
    
    def __init__(
        self,
        draft: CommandDraft,
        *,
        on_changed: Callable[[], None],
        on_execute: Callable[[], None],
        on_copy_from_profile: Callable[[], None],
        suggest_systems: Callable[[str], list[object]] | None = None,
        suggest_stations: Callable[..., list[object]] | None = None,
        resolve_system: Callable[[str], object | None] | None = None,
    ) -> None:
        self.draft = draft
        self.on_changed = on_changed
        self.on_execute = on_execute
        self.on_copy_from_profile = on_copy_from_profile
        self.suggest_systems = suggest_systems
        self.suggest_stations = suggest_stations
        self.resolve_system = resolve_system
        self.selected_start_system_id: int | None = None
        self.selected_end_system_id: int | None = None
    
    def build(self) -> None:
        self._normalize_run_state()
        # Keep the always-visible pane focused on route-shaping fields and the
        # most common overrides; niche knobs live in the extended dialog.
        extended_dialog = self._build_extended_dialog()
        
        with ui.column().classes('w-full gap-3'):
            ui.label(
                'Leave a field empty to use the values from Commander '
                'Details. Use copy from profile to fill these fields with '
                'your current Commander Details and ship values.'
            ).classes('text-sm text-gray-600')
            
            self._build_route_section()
            self._build_override_section()
            self._build_filter_section()
            
            with ui.row().classes('gap-2'):
                ui.button('Copy from profile', on_click=self.on_copy_from_profile)
                ui.button('Extended Options', on_click=extended_dialog.open)
                ui.button('Execute Run', on_click=self.on_execute)
    
    def _normalize_run_state(self) -> None:
        start_system, _start_station = self._normalize_station_pair_value(
            self.draft.main_values,
            system_key='startSystem',
            station_key='startStation',
            combined_key='starting',
        )
        end_system, _end_station = self._normalize_station_pair_value(
            self.draft.main_values,
            system_key='endSystem',
            station_key='endStation',
            combined_key='ending',
        )
        self.selected_start_system_id = self._resolve_run_system_id(
            start_system,
        )
        self.selected_end_system_id = self._resolve_run_system_id(
            end_system,
        )
    
    def _resolve_run_system_id(self, system_name: str | None) -> int | None:
        return self._resolve_suggestion_id(
            system_name,
            resolver=self.resolve_system,
            id_attr='system_id',
        )
    
    def _run_system_value(
        self,
        *,
        system_key: str,
        station_key: str,
        combined_key: str,
    ) -> str:
        system_name, _station_name = self._station_pair_values(
            self.draft.main_values,
            system_key=system_key,
            station_key=station_key,
            combined_key=combined_key,
        )
        return system_name
    
    def _run_station_value(
        self,
        *,
        system_key: str,
        station_key: str,
        combined_key: str,
    ) -> str:
        _system_name, station_name = self._station_pair_values(
            self.draft.main_values,
            system_key=system_key,
            station_key=station_key,
            combined_key=combined_key,
        )
        return station_name
    
    def _set_run_system_text(
        self,
        value: str,
        *,
        system_key: str,
        station_key: str,
        combined_key: str,
        selected_attr: str,
        station_autocomplete_attr: str,
    ) -> None:
        cleaned = str(value or '').strip()
        current = self._run_system_value(
            system_key=system_key,
            station_key=station_key,
            combined_key=combined_key,
        ).strip()
        if cleaned == '':
            self.draft.main_values.pop(system_key, None)
            self.draft.main_values.pop(station_key, None)
            self.draft.main_values.pop(combined_key, None)
            setattr(self, selected_attr, None)
            station_autocomplete = getattr(self, station_autocomplete_attr, None)
            if station_autocomplete is not None:
                station_autocomplete.clear()
            self.on_changed()
            return
        self.draft.main_values[system_key] = cleaned
        if cleaned != current:
            self.draft.main_values.pop(station_key, None)
            station_autocomplete = getattr(self, station_autocomplete_attr, None)
            if station_autocomplete is not None:
                station_autocomplete.clear()
        setattr(self, selected_attr, self._resolve_run_system_id(cleaned))
        self._sync_station_pair_value(
            self.draft.main_values,
            system_key=system_key,
            station_key=station_key,
            combined_key=combined_key,
        )
        self.on_changed()
    
    def _set_run_system_selected(
        self,
        suggestion: object,
        *,
        selected_attr: str,
    ) -> None:
        setattr(self, selected_attr, getattr(suggestion, 'system_id', None))
    
    def _set_run_station_text(
        self,
        value: str,
        *,
        system_key: str,
        station_key: str,
        combined_key: str,
    ) -> None:
        cleaned = str(value or '').strip()
        if cleaned == '':
            self.draft.main_values.pop(station_key, None)
        else:
            self.draft.main_values[station_key] = cleaned
        self._sync_station_pair_value(
            self.draft.main_values,
            system_key=system_key,
            station_key=station_key,
            combined_key=combined_key,
        )
        self.on_changed()
    
    def _suggest_run_stations(
        self,
        text: str,
        *,
        selected_attr: str,
    ) -> list[object]:
        if self.suggest_stations is None:
            return []
        system_id = getattr(self, selected_attr)
        if system_id is None:
            return []
        try:
            suggestions = self.suggest_stations(text, system_id)
        except TypeError:
            suggestions = self.suggest_stations(text)
        relabeled: list[object] = []
        for suggestion in suggestions:
            station_name = getattr(suggestion, 'station_name', None)
            if not station_name:
                relabeled.append(suggestion)
                continue
            relabeled.append(
                suggestion.__class__(
                    key=getattr(suggestion, 'key'),
                    kind=getattr(suggestion, 'kind'),
                    value=getattr(suggestion, 'value'),
                    label=str(station_name),
                    system_id=getattr(suggestion, 'system_id'),
                    system_name=getattr(suggestion, 'system_name'),
                    station_id=getattr(suggestion, 'station_id'),
                    station_name=getattr(suggestion, 'station_name'),
                )
            )
        return relabeled
    
    def _build_route_section(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('Route')
            ui.label(
                'Use one of To, Towards, or Loop. '
                'Use either Direct or Hops.'
            ).classes('text-sm text-gray-600')
            
            with ui.grid(columns=3).classes('w-full gap-3'):
                if self.suggest_systems is None:
                    ui.input(
                        'From System',
                        value=self._run_system_value(
                            system_key='startSystem',
                            station_key='startStation',
                            combined_key='starting',
                        ),
                        on_change=lambda event: self._set_run_system_text(
                            event.value,
                            system_key='startSystem',
                            station_key='startStation',
                            combined_key='starting',
                            selected_attr='selected_start_system_id',
                            station_autocomplete_attr='start_station_autocomplete',
                        ),
                    ).classes('min-w-0 w-full').tooltip(
                        'System containing your starting station.'
                    )
                else:
                    AutocompleteInput(
                        label='From System',
                        value=self._run_system_value(
                            system_key='startSystem',
                            station_key='startStation',
                            combined_key='starting',
                        ),
                        fetch_suggestions=self.suggest_systems,
                        on_text_changed=lambda value: self._set_run_system_text(
                            value,
                            system_key='startSystem',
                            station_key='startStation',
                            combined_key='starting',
                            selected_attr='selected_start_system_id',
                            station_autocomplete_attr='start_station_autocomplete',
                        ),
                        on_selected=lambda suggestion: self._set_run_system_selected(
                            suggestion,
                            selected_attr='selected_start_system_id',
                        ),
                        tooltip='System containing your starting station.',
                        input_classes='min-w-0 w-full',
                    ).build()
                
                if self.suggest_stations is None:
                    ui.input(
                        'From Station',
                        value=self._run_station_value(
                            system_key='startSystem',
                            station_key='startStation',
                            combined_key='starting',
                        ),
                        on_change=lambda event: self._set_run_station_text(
                            event.value,
                            system_key='startSystem',
                            station_key='startStation',
                            combined_key='starting',
                        ),
                    ).classes('min-w-0 w-full').tooltip(
                        'Station you are starting from.'
                    )
                else:
                    self.start_station_autocomplete = AutocompleteInput(
                        label='From Station',
                        value=self._run_station_value(
                            system_key='startSystem',
                            station_key='startStation',
                            combined_key='starting',
                        ),
                        fetch_suggestions=lambda text: self._suggest_run_stations(
                            text,
                            selected_attr='selected_start_system_id',
                        ),
                        on_text_changed=lambda value: self._set_run_station_text(
                            value,
                            system_key='startSystem',
                            station_key='startStation',
                            combined_key='starting',
                        ),
                        selection_text=lambda suggestion: str(
                            getattr(suggestion, 'station_name', suggestion.value)
                        ),
                        tooltip='Station you are starting from.',
                        input_classes='min-w-0 w-full',
                    )
                    self.start_station_autocomplete.build()
                
                ui.element('div')
                
                if self.suggest_systems is None:
                    ui.input(
                        'To System',
                        value=self._run_system_value(
                            system_key='endSystem',
                            station_key='endStation',
                            combined_key='ending',
                        ),
                        on_change=lambda event: self._set_run_system_text(
                            event.value,
                            system_key='endSystem',
                            station_key='endStation',
                            combined_key='ending',
                            selected_attr='selected_end_system_id',
                            station_autocomplete_attr='end_station_autocomplete',
                        ),
                    ).classes('min-w-0 w-full').tooltip(
                        'System containing your destination station.'
                    )
                else:
                    AutocompleteInput(
                        label='To System',
                        value=self._run_system_value(
                            system_key='endSystem',
                            station_key='endStation',
                            combined_key='ending',
                        ),
                        fetch_suggestions=self.suggest_systems,
                        on_text_changed=lambda value: self._set_run_system_text(
                            value,
                            system_key='endSystem',
                            station_key='endStation',
                            combined_key='ending',
                            selected_attr='selected_end_system_id',
                            station_autocomplete_attr='end_station_autocomplete',
                        ),
                        on_selected=lambda suggestion: self._set_run_system_selected(
                            suggestion,
                            selected_attr='selected_end_system_id',
                        ),
                        tooltip='System containing your destination station.',
                        input_classes='min-w-0 w-full',
                    ).build()
                
                if self.suggest_stations is None:
                    ui.input(
                        'To Station',
                        value=self._run_station_value(
                            system_key='endSystem',
                            station_key='endStation',
                            combined_key='ending',
                        ),
                        on_change=lambda event: self._set_run_station_text(
                            event.value,
                            system_key='endSystem',
                            station_key='endStation',
                            combined_key='ending',
                        ),
                    ).classes('min-w-0 w-full').tooltip(
                        'Station you are heading to.'
                    )
                else:
                    self.end_station_autocomplete = AutocompleteInput(
                        label='To Station',
                        value=self._run_station_value(
                            system_key='endSystem',
                            station_key='endStation',
                            combined_key='ending',
                        ),
                        fetch_suggestions=lambda text: self._suggest_run_stations(
                            text,
                            selected_attr='selected_end_system_id',
                        ),
                        on_text_changed=lambda value: self._set_run_station_text(
                            value,
                            system_key='endSystem',
                            station_key='endStation',
                            combined_key='ending',
                        ),
                        selection_text=lambda suggestion: str(
                            getattr(suggestion, 'station_name', suggestion.value)
                        ),
                        tooltip='Station you are heading to.',
                        input_classes='min-w-0 w-full',
                    )
                    self.end_station_autocomplete.build()
                
                build_system_autocomplete_input(
                    label='Towards',
                    value=self._text_value(self.draft.main_values, 'goalSystem'),
                    on_text_changed=lambda value: self._set_text(
                        self.draft.main_values,
                        'goalSystem',
                        value,
                    ),
                    tooltip=(
                        'Choose a route that continually reduces the distance '
                        'towards this system.'
                    ),
                    suggest_systems=self.suggest_systems,
                    input_classes='min-w-0 w-full',
                )
                            
            with ui.row().classes('w-full items-end gap-3'):
                ui.number(
                    'Hops',
                    value=self._number_value(self.draft.main_values, 'hops'),
                    min=1,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.main_values,
                        'hops',
                        event.value,
                        'Hops',
                    ),
                ).classes('w-32').tooltip(
                    'Number of hops (station-to-station) to run.'
                )
                ui.number(
                    'Jumps / hop',
                    value=self._number_value(
                        self.draft.main_values,
                        'maxJumpsPer',
                    ),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.main_values,
                        'maxJumpsPer',
                        event.value,
                        'Jumps / hop',
                    ),
                ).classes('w-40').tooltip(
                    'Maximum number of jumps (system-to-system) per hop.'
                )
                with ui.row().classes('items-center gap-4 pl-2'):
                    ui.checkbox(
                        'Direct',
                        value=self._bool_value(self.draft.main_values, 'direct'),
                        on_change=lambda event: self._set_bool(
                            self.draft.main_values,
                            'direct',
                            event.value,
                        ),
                    ).tooltip(
                        'Assume destinations are reachable without worrying '
                        'about jumps/hops.'
                    )
                    ui.checkbox(
                        'Loopback',
                        value=self._bool_value(self.draft.main_values, 'loop'),
                        on_change=lambda event: self._set_bool(
                            self.draft.main_values,
                            'loop',
                            event.value,
                        ),
                    ).tooltip(
                        'Create a looping route.'
                    )
                    ui.checkbox(
                        'Unique',
                        value=self._bool_value(self.draft.main_values, 'unique'),
                        on_change=lambda event: self._set_bool(
                            self.draft.main_values,
                            'unique',
                            event.value,
                        ),
                    ).tooltip(
                        'Only visit each station once in route.'
                    )
    
    def _build_override_section(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('Run Overrides')
            ui.label(
                'These override ship/global baseline values for this run only. '
                'Clear a field to return to inherited behaviour.'
            ).classes('text-sm text-gray-600')
            
            with ui.row().classes('w-full gap-3'):
                ui.number(
                    'Capacity',
                    value=self._number_value(
                        self.draft.context_overrides,
                        'capacity',
                    ),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.context_overrides,
                        'capacity',
                        event.value,
                        'Capacity',
                    ),
                ).classes('w-40').tooltip(
                    'Maximum capacity of cargo hold.'
                )
                ui.number(
                    'Credits',
                    value=self._number_value(
                        self.draft.context_overrides,
                        'credits',
                    ),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.context_overrides,
                        'credits',
                        event.value,
                        'Credits',
                    ),
                ).classes('w-48').tooltip(
                    'Starting credits.'
                )
                ui.number(
                    'LY / jump',
                    value=self._number_value(
                        self.draft.context_overrides,
                        'jump_range_full_ly',
                    ),
                    min=0,
                    step=0.1,
                    precision=2,
                    on_change=lambda event: self._set_float(
                        self.draft.context_overrides,
                        'jump_range_full_ly',
                        event.value,
                    ),
                ).classes('w-40').tooltip(
                    'Maximum light years per jump.'
                )
                ui.number(
                    'Empty LY / jump',
                    value=self._number_value(
                        self.draft.context_overrides,
                        'jump_range_empty_ly',
                    ),
                    min=0,
                    step=0.1,
                    precision=2,
                    on_change=lambda event: self._set_float(
                        self.draft.context_overrides,
                        'jump_range_empty_ly',
                        event.value,
                    ),
                ).classes('w-40').tooltip(
                    'Maximum light years ship can jump when empty.'
                )
    
    def _build_filter_section(self) -> None:
        # Summary changes how results are presented often enough to keep it in
        # the main pane; the rest of the output flags stay in the dialog.
        def build_run_extra_filters() -> None:
            ui.checkbox(
                'Summary output',
                value=self._bool_value(self.draft.main_values, 'summary'),
                on_change=lambda event: self._set_bool(
                    self.draft.main_values,
                    'summary',
                    event.value,
                ),
            ).tooltip(
                'Summary layout of route instructions.'
            )
        
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
            extra_builder=build_run_extra_filters,
        )
    
    def _build_extended_dialog(self) -> ui.dialog:
        # Everything in this dialog writes to advanced_values so uncommon run
        # switches stay distinct from the route and override fields above.
        dialog = ui.dialog()
        with dialog:
            with ui.card().style('min-width: 72rem; max-width: 95vw;'):
                ui.label('Extended Options')
                ui.label(
                    'These are the less common run options. '
                    'Leave a field blank to omit it.'
                ).classes('text-sm text-gray-600')
                
                with ui.column().classes('w-full gap-5'):
                    self._build_extended_routing_section()
                    self._build_extended_market_section()
                    self._build_extended_trade_section()
                    self._build_extended_search_section()
                    self._build_extended_output_section()
                
                with ui.row().classes('justify-end'):
                    ui.button('Close', on_click=dialog.close)
        
        return dialog
    
    def _build_extended_routing_section(self) -> None:
        with ui.column().classes('w-full gap-3'):
            ui.label('Routing and path constraints')
            
            with ui.row().classes('w-full gap-3'):
                ui.input(
                    'Via',
                    value=self._text_value(self.draft.advanced_values, 'via'),
                    on_change=lambda event: self._set_text(
                        self.draft.advanced_values,
                        'via',
                        event.value,
                    ),
                ).classes('min-w-80 flex-1').tooltip(
                    'Require specified systems/stations to be en-route.'
                )
                ui.input(
                    'Avoid',
                    value=self._text_value(self.draft.advanced_values, 'avoid'),
                    on_change=lambda event: self._set_text(
                        self.draft.advanced_values,
                        'avoid',
                        event.value,
                    ),
                ).classes('min-w-80 flex-1').tooltip(
                    'Exclude an item, system or station from trading. '
                    'Partial matches allowed.'
                )
            
            with ui.row().classes('w-full gap-3'):
                ui.number(
                    'Start jumps',
                    value=self._number_value(
                        self.draft.advanced_values,
                        'startJumps',
                    ),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.advanced_values,
                        'startJumps',
                        event.value,
                        'Start jumps',
                    ),
                ).classes('w-40').tooltip(
                    'Consider stations within this many jumps of the origin '
                    '(requires From).'
                )
                ui.number(
                    'End jumps',
                    value=self._number_value(
                        self.draft.advanced_values,
                        'endJumps',
                    ),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.advanced_values,
                        'endJumps',
                        event.value,
                        'End jumps',
                    ),
                ).classes('w-40').tooltip(
                    'Consider stations within this many jumps of the '
                    'destination (requires To).'
                )
                ui.number(
                    'Loop interval',
                    value=self._number_value(
                        self.draft.advanced_values,
                        'loopInt',
                    ),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.advanced_values,
                        'loopInt',
                        event.value,
                        'Loop interval',
                    ),
                ).classes('w-40').tooltip(
                    'Require this many hops between visits to the same '
                    'station. 2 is the minimum useful value.'
                )
                ui.checkbox(
                    'Show jumps',
                    value=self._bool_value(
                        self.draft.advanced_values,
                        'showJumps',
                    ),
                    on_change=lambda event: self._set_bool(
                        self.draft.advanced_values,
                        'showJumps',
                        event.value,
                    ),
                ).tooltip(
                    'Show detail of jumps between hops.'
                )
                ui.checkbox(
                    'Shorten',
                    value=self._bool_value(
                        self.draft.advanced_values,
                        'shorten',
                    ),
                    on_change=lambda event: self._set_bool(
                        self.draft.advanced_values,
                        'shorten',
                        event.value,
                    ),
                ).tooltip(
                    'Requires To. Find the shortest route with the best gain '
                    'per ton.'
                )
    
    def _build_extended_market_section(self) -> None:
        with ui.column().classes('w-full gap-3'):
            ui.label('Market and station constraints')
            
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
    
    def _build_extended_trade_section(self) -> None:
        with ui.column().classes('w-full gap-3'):
            ui.label('Trade and profit constraints')
            
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
                    'Maximum units of any one cargo item to buy (0: '
                    'unlimited).'
                )
                ui.number(
                    'Min gain / ton',
                    value=self._number_value(
                        self.draft.advanced_values,
                        'minGainPerTon',
                    ),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.advanced_values,
                        'minGainPerTon',
                        event.value,
                        'Min gain / ton',
                    ),
                ).classes('w-40').tooltip(
                    'Specify the minimum gain per ton of cargo.'
                )
                ui.number(
                    'Max gain / ton',
                    value=self._number_value(
                        self.draft.advanced_values,
                        'maxGainPerTon',
                    ),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.advanced_values,
                        'maxGainPerTon',
                        event.value,
                        'Max gain / ton',
                    ),
                ).classes('w-40').tooltip(
                    'Specify the maximum gain per ton of cargo.'
                )
                ui.number(
                    'Margin',
                    value=self._number_value(
                        self.draft.advanced_values,
                        'margin',
                    ),
                    min=0,
                    step=0.01,
                    precision=2,
                    on_change=lambda event: self._set_float(
                        self.draft.advanced_values,
                        'margin',
                        event.value,
                    ),
                ).classes('w-32').tooltip(
                    'Reduce gains on each hop to leave a margin for market '
                    'fluctuations.'
                )
                ui.number(
                    'Insurance',
                    value=self._number_value(
                        self.draft.advanced_values,
                        'insurance',
                    ),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.advanced_values,
                        'insurance',
                        event.value,
                        'Insurance',
                    ),
                ).classes('w-40').tooltip(
                    'Reserve at least this many credits to cover insurance.'
                )
            
            with ui.row().classes('w-full gap-3'):
                # Mirror TD's implicit default of one route so the widget never
                # suggests that zero is a meaningful starting value.
                ui.number(
                    'Routes',
                    value=self._number_value(
                        self.draft.advanced_values,
                        'routes',
                    ) or 1,
                    min=1,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.advanced_values,
                        'routes',
                        event.value,
                        'Routes',
                    ),
                ).classes('w-32').tooltip(
                    'Maximum number of routes to show. Default: 1.'
                )
                ui.number(
                    'Supply',
                    value=self._number_value(
                        self.draft.advanced_values,
                        'supply',
                    ),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.advanced_values,
                        'supply',
                        event.value,
                        'Supply',
                    ),
                ).classes('w-32').tooltip(
                    'Only considers items which have at least this many '
                    'units.'
                )
                ui.number(
                    'Demand',
                    value=self._number_value(
                        self.draft.advanced_values,
                        'demand',
                    ),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.advanced_values,
                        'demand',
                        event.value,
                        'Demand',
                    ),
                ).classes('w-32').tooltip(
                    'Only considers items which have at least this much '
                    'demand.'
                )
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
                ).classes('w-32').tooltip(
                    'Only consider stations up to this many ls from their '
                    'star.'
                )
                ui.number(
                    'LS penalty',
                    value=self._number_value(
                        self.draft.advanced_values,
                        'lsPenalty',
                    ),
                    min=0,
                    step=0.1,
                    precision=2,
                    on_change=lambda event: self._set_float(
                        self.draft.advanced_values,
                        'lsPenalty',
                        event.value,
                    ),
                ).classes('w-32').tooltip(
                    'Penalty applied per 1 kls of station distance from its '
                    'star.'
                )
    
    def _build_extended_search_section(self) -> None:
        with ui.column().classes('w-full gap-3'):
            ui.label('Search breadth and pruning')
            
            with ui.row().classes('w-full gap-3'):
                ui.number(
                    'Max routes',
                    value=self._number_value(
                        self.draft.advanced_values,
                        'maxRoutes',
                    ),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.advanced_values,
                        'maxRoutes',
                        event.value,
                        'Max routes',
                    ),
                ).classes('w-40').tooltip(
                    'After each hop, continue only the top N highest-scoring '
                    'routes.'
                )
                ui.number(
                    'Prune score',
                    value=self._number_value(
                        self.draft.advanced_values,
                        'pruneScores',
                    ),
                    min=0,
                    step=0.1,
                    precision=2,
                    on_change=lambda event: self._set_float(
                        self.draft.advanced_values,
                        'pruneScores',
                        event.value,
                    ),
                ).classes('w-40').tooltip(
                    'From the third hop onward, keep only routes at or above '
                    'this percentage of the current best score.'
                )
                ui.number(
                    'Prune hops',
                    value=self._number_value(
                        self.draft.advanced_values,
                        'pruneHops',
                    ),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.advanced_values,
                        'pruneHops',
                        event.value,
                        'Prune hops',
                    ),
                ).classes('w-40').tooltip(
                    'Changes which hop Prune score takes effect from.'
                )
    
    def _build_extended_output_section(self) -> None:
        with ui.column().classes('w-full gap-3'):
            ui.label('Output and devices')
            
            with ui.row().classes('w-full gap-4'):
                ui.checkbox(
                    'Progress',
                    value=self._bool_value(
                        self.draft.advanced_values,
                        'progress',
                    ),
                    on_change=lambda event: self._set_bool(
                        self.draft.advanced_values,
                        'progress',
                        event.value,
                    ),
                ).tooltip(
                    'Show hop progress.'
                )
                
                ui.checkbox(
                    'Checklist',
                    value=self._bool_value(
                        self.draft.advanced_values,
                        'checklist',
                    ),
                    on_change=lambda event: self._set_bool(
                        self.draft.advanced_values,
                        'checklist',
                        event.value,
                    ),
                ).tooltip(
                    'Provide a checklist flow for the route.'
                )
                ui.checkbox(
                    'X52 Pro',
                    value=self._bool_value(
                        self.draft.advanced_values,
                        'x52pro',
                    ),
                    on_change=lambda event: self._set_bool(
                        self.draft.advanced_values,
                        'x52pro',
                        event.value,
                    ),
                ).tooltip(
                    'Enable experimental X52 Pro MFD output.'
                )
