from typing import Callable

from nicegui import ui

from .autocomplete import AutocompleteInput, build_system_autocomplete_input
from .profiles import CommandDraft
from .shared_draft_helpers import DraftValueHelper
from .shared_filter_view import build_shared_filter_section

class TradeWorkspace(DraftValueHelper):
    """Edit a `trade` draft using command-local fields only."""
    
    def __init__(
        self,
        draft: CommandDraft,
        *,
        on_changed: Callable[[], None],
        on_execute: Callable[[], None],
        suggest_systems: Callable[[str], list[object]] | None = None,
        suggest_stations: Callable[..., list[object]] | None = None,
        resolve_system: Callable[[str], object | None] | None = None,
    ) -> None:
        self.draft = draft
        self.on_changed = on_changed
        self.on_execute = on_execute
        self.suggest_systems = suggest_systems
        self.suggest_stations = suggest_stations
        self.resolve_system = resolve_system
        self.selected_origin_system_id: int | None = None
        self.selected_dest_system_id: int | None = None
    
    def build(self) -> None:
        self._normalize_trade_state()
        with ui.column().classes('w-full gap-3'):
            self._build_route_section()
            self._build_constraint_section()
            
            with ui.row().classes('gap-2'):
                ui.button('Execute Direct', on_click=self.on_execute)
    
    def _normalize_trade_state(self) -> None:
        origin_system, _origin_station = self._normalize_station_pair_value(
            self.draft.main_values,
            system_key='originSystem',
            station_key='originStation',
            combined_key='origin',
            allow_bare_system=True,
        )
        dest_system, _dest_station = self._normalize_station_pair_value(
            self.draft.main_values,
            system_key='destSystem',
            station_key='destStation',
            combined_key='dest',
            allow_bare_system=True,
        )
        self.selected_origin_system_id = self._resolve_trade_system_id(
            origin_system,
        )
        self.selected_dest_system_id = self._resolve_trade_system_id(
            dest_system,
        )
    
    def _resolve_trade_system_id(self, system_name: str | None) -> int | None:
        return self._resolve_suggestion_id(
            system_name,
            resolver=self.resolve_system,
            id_attr='system_id',
        )
    
    def _trade_system_value(
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
    
    def _trade_station_value(
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
    
    def _set_trade_system_text(
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
        current = self._trade_system_value(
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
        setattr(self, selected_attr, self._resolve_trade_system_id(cleaned))
        self._sync_station_pair_value(
            self.draft.main_values,
            system_key=system_key,
            station_key=station_key,
            combined_key=combined_key,
            allow_bare_system=True,
        )
        self.on_changed()
    
    def _set_trade_system_selected(
        self,
        suggestion: object,
        *,
        selected_attr: str,
    ) -> None:
        setattr(self, selected_attr, getattr(suggestion, 'system_id', None))
    
    def _set_trade_station_text(
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
            allow_bare_system=True,
        )
        self.on_changed()
    
    def _suggest_trade_stations(
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
            ui.label('Direct Route')
            ui.label(
                'Enter an origin and a destination. Each side may be a whole '
                'system (every qualifying station) or a single system/station '
                '— the station is optional on either side.'
            ).classes('text-sm text-gray-600')
            
            with ui.row().classes('w-full gap-3'):
                if self.suggest_systems is None:
                    ui.input(
                        'Origin System',
                        value=self._trade_system_value(
                            system_key='originSystem',
                            station_key='originStation',
                            combined_key='origin',
                        ),
                        on_change=lambda event: self._set_trade_system_text(
                            event.value,
                            system_key='originSystem',
                            station_key='originStation',
                            combined_key='origin',
                            selected_attr='selected_origin_system_id',
                            station_autocomplete_attr='origin_station_autocomplete',
                        ),
                    ).classes('min-w-80 flex-1').tooltip(
                        'System containing the station you are purchasing from.'
                    )
                else:
                    AutocompleteInput(
                        label='Origin System',
                        value=self._trade_system_value(
                            system_key='originSystem',
                            station_key='originStation',
                            combined_key='origin',
                        ),
                        fetch_suggestions=self.suggest_systems,
                        on_text_changed=lambda value: self._set_trade_system_text(
                            value,
                            system_key='originSystem',
                            station_key='originStation',
                            combined_key='origin',
                            selected_attr='selected_origin_system_id',
                            station_autocomplete_attr='origin_station_autocomplete',
                        ),
                        on_selected=lambda suggestion: self._set_trade_system_selected(
                            suggestion,
                            selected_attr='selected_origin_system_id',
                        ),
                        tooltip='System containing the station you are purchasing from.',
                        input_classes='min-w-80 flex-1',
                    ).build()
                
                if self.suggest_stations is None:
                    ui.input(
                        'Origin Station (optional)',
                        value=self._trade_station_value(
                            system_key='originSystem',
                            station_key='originStation',
                            combined_key='origin',
                        ),
                        on_change=lambda event: self._set_trade_station_text(
                            event.value,
                            system_key='originSystem',
                            station_key='originStation',
                            combined_key='origin',
                        ),
                    ).classes('min-w-80 flex-1').tooltip(
                        'Station you are purchasing from.'
                    )
                else:
                    self.origin_station_autocomplete = AutocompleteInput(
                        label='Origin Station (optional)',
                        value=self._trade_station_value(
                            system_key='originSystem',
                            station_key='originStation',
                            combined_key='origin',
                        ),
                        fetch_suggestions=lambda text: self._suggest_trade_stations(
                            text,
                            selected_attr='selected_origin_system_id',
                        ),
                        on_text_changed=lambda value: self._set_trade_station_text(
                            value,
                            system_key='originSystem',
                            station_key='originStation',
                            combined_key='origin',
                        ),
                        selection_text=lambda suggestion: str(
                            getattr(suggestion, 'station_name', suggestion.value)
                        ),
                        tooltip='Station you are purchasing from.',
                        input_classes='min-w-80 flex-1',
                    )
                    self.origin_station_autocomplete.build()
            
            with ui.row().classes('w-full gap-3'):
                if self.suggest_systems is None:
                    ui.input(
                        'Destination System',
                        value=self._trade_system_value(
                            system_key='destSystem',
                            station_key='destStation',
                            combined_key='dest',
                        ),
                        on_change=lambda event: self._set_trade_system_text(
                            event.value,
                            system_key='destSystem',
                            station_key='destStation',
                            combined_key='dest',
                            selected_attr='selected_dest_system_id',
                            station_autocomplete_attr='dest_station_autocomplete',
                        ),
                    ).classes('min-w-80 flex-1').tooltip(
                        'System containing the station you are selling to.'
                    )
                else:
                    AutocompleteInput(
                        label='Destination System',
                        value=self._trade_system_value(
                            system_key='destSystem',
                            station_key='destStation',
                            combined_key='dest',
                        ),
                        fetch_suggestions=self.suggest_systems,
                        on_text_changed=lambda value: self._set_trade_system_text(
                            value,
                            system_key='destSystem',
                            station_key='destStation',
                            combined_key='dest',
                            selected_attr='selected_dest_system_id',
                            station_autocomplete_attr='dest_station_autocomplete',
                        ),
                        on_selected=lambda suggestion: self._set_trade_system_selected(
                            suggestion,
                            selected_attr='selected_dest_system_id',
                        ),
                        tooltip='System containing the station you are selling to.',
                        input_classes='min-w-80 flex-1',
                    ).build()
                
                if self.suggest_stations is None:
                    ui.input(
                        'Destination Station (optional)',
                        value=self._trade_station_value(
                            system_key='destSystem',
                            station_key='destStation',
                            combined_key='dest',
                        ),
                        on_change=lambda event: self._set_trade_station_text(
                            event.value,
                            system_key='destSystem',
                            station_key='destStation',
                            combined_key='dest',
                        ),
                    ).classes('min-w-80 flex-1').tooltip(
                        'Station you are selling to.'
                    )
                else:
                    self.dest_station_autocomplete = AutocompleteInput(
                        label='Destination Station (optional)',
                        value=self._trade_station_value(
                            system_key='destSystem',
                            station_key='destStation',
                            combined_key='dest',
                        ),
                        fetch_suggestions=lambda text: self._suggest_trade_stations(
                            text,
                            selected_attr='selected_dest_system_id',
                        ),
                        on_text_changed=lambda value: self._set_trade_station_text(
                            value,
                            system_key='destSystem',
                            station_key='destStation',
                            combined_key='dest',
                        ),
                        selection_text=lambda suggestion: str(
                            getattr(suggestion, 'station_name', suggestion.value)
                        ),
                        tooltip='Station you are selling to.',
                        input_classes='min-w-80 flex-1',
                    )
                    self.dest_station_autocomplete.build()
    
    def _build_constraint_section(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('Trade Constraints')
            
            with ui.row().classes('w-full items-end gap-3'):
                ui.number(
                    'Gain / ton',
                    value=self._number_value(self.draft.main_values, 'minGainPerTon'),
                    min=0,
                    step=1,
                    precision=0,
                    on_change=lambda event: self._set_int(
                        self.draft.main_values,
                        'minGainPerTon',
                        event.value,
                        'Gain / ton',
                    ),
                ).classes('w-40').tooltip(
                    'Specify the minimum gain per ton of cargo.'
                )
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
                ).classes('w-32').tooltip(
                    'Requires at least this many units available at the '
                    'seller.'
                )
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
                ).classes('w-32').tooltip(
                    'Requires at least this many units of demand at the buyer.'
                )
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
                ).classes('w-32').tooltip(
                    'Limit output to the first N results.'
                )
            
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
                ).classes('w-64').tooltip(
                    'Choose how cargo space is interpreted: default '
                    'behavior, fill to capacity, load only free space, or '
                    'full load from scratch.'
                )
                ui.checkbox(
                    'Reverse route',
                    value=self._bool_value(self.draft.main_values, 'reverse'),
                    on_change=lambda event: self._set_bool(
                        self.draft.main_values,
                        'reverse',
                        event.value,
                    ),
                ).tooltip(
                    'Show the reverse trade by swapping origin and '
                    'destination.'
                )

class LocalWorkspace(DraftValueHelper):
    """Edit a `local` draft using command-local fields only."""
    
    def __init__(
        self,
        draft: CommandDraft,
        *,
        on_changed: Callable[[], None],
        on_execute: Callable[[], None],
        suggest_systems: Callable[[str], list[object]] | None = None,
    ) -> None:
        self.draft = draft
        self.on_changed = on_changed
        self.on_execute = on_execute
        self.suggest_systems = suggest_systems
    
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
                build_system_autocomplete_input(
                    label='Near',
                    value=self._text_value(self.draft.main_values, 'near'),
                    on_text_changed=lambda value: self._set_text(
                        self.draft.main_values,
                        'near',
                        value,
                    ),
                    tooltip='Name of the system to query from.',
                    suggest_systems=self.suggest_systems,
                )
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
                ).classes('w-40').tooltip(
                    'Maximum light years from system.'
                )
                ui.checkbox(
                    'Trading only',
                    value=self._bool_value(self.draft.main_values, 'trading'),
                    on_change=lambda event: self._set_bool(
                        self.draft.main_values,
                        'trading',
                        event.value,
                    ),
                ).tooltip(
                    'Limit stations to ones with price data or flagged as '
                    'having a market.'
                )
    
    def _build_filter_section(self) -> None:
        # Shared filters cover the tri-state station traits and pad sizes.
        # Local adds the simpler service-availability booleans underneath.
        def build_service_filters() -> None:
            with ui.row().classes('w-full gap-4'):
                ui.checkbox('Black market', value=self._bool_value(self.draft.main_values, 'blackMarket'), on_change=lambda event: self._set_bool(self.draft.main_values, 'blackMarket', event.value)).tooltip('Require stations known to have a black market.')
                ui.checkbox('Shipyard', value=self._bool_value(self.draft.main_values, 'shipyard'), on_change=lambda event: self._set_bool(self.draft.main_values, 'shipyard', event.value)).tooltip('Require stations known to have a Shipyard.')
                ui.checkbox('Outfitting', value=self._bool_value(self.draft.main_values, 'outfitting'), on_change=lambda event: self._set_bool(self.draft.main_values, 'outfitting', event.value)).tooltip('Require stations known to have Outfitting.')
                ui.checkbox('Rearm', value=self._bool_value(self.draft.main_values, 'rearm'), on_change=lambda event: self._set_bool(self.draft.main_values, 'rearm', event.value)).tooltip('Require stations known to sell munitions.')
                ui.checkbox('Refuel', value=self._bool_value(self.draft.main_values, 'refuel'), on_change=lambda event: self._set_bool(self.draft.main_values, 'refuel', event.value)).tooltip('Require stations known to sell fuel.')
                ui.checkbox('Repair', value=self._bool_value(self.draft.main_values, 'repair'), on_change=lambda event: self._set_bool(self.draft.main_values, 'repair', event.value)).tooltip('Require stations known to offer repairs.')
        
        build_shared_filter_section(
            get_bool=lambda key: self._bool_value(self.draft.main_values, key),
            get_tri_state=lambda key: self._tri_state_value(self.draft.main_values, key),
            set_bool=lambda key, value: self._set_bool(self.draft.main_values, key, value),
            set_tri_state=lambda key, value: self._set_tri_state(self.draft.main_values, key, value),
            pad_size_enabled=self._pad_size_enabled,
            set_pad_size_flag=self._set_pad_size_flag,
            post_builder=build_service_filters,
        )

class MarketWorkspace(DraftValueHelper):
    """Edit a `market` draft using command-local fields only."""
    
    def __init__(
        self,
        draft: CommandDraft,
        *,
        on_changed: Callable[[], None],
        on_execute: Callable[[], None],
        suggest_systems: Callable[[str], list[object]] | None = None,
        suggest_stations: Callable[..., list[object]] | None = None,
        resolve_system: Callable[[str], object | None] | None = None,
    ) -> None:
        self.draft = draft
        self.on_changed = on_changed
        self.on_execute = on_execute
        self.suggest_systems = suggest_systems
        self.suggest_stations = suggest_stations
        self.resolve_system = resolve_system
        self.selected_system_id: int | None = None
    
    def build(self) -> None:
        self._normalize_market_state()
        with ui.column().classes('w-full gap-3'):
            self._build_station_section()
            self._build_view_section()
            with ui.row().classes('gap-2'):
                ui.button('Execute Market', on_click=self.on_execute)
    
    def _build_station_section(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('Market Station')
            ui.label(
                'Select a system, then the station within that system.'
            ).classes('text-sm text-gray-600')
            with ui.row().classes('w-full gap-3'):
                if self.suggest_systems is None:
                    ui.input(
                        'System',
                        value=self._market_system_value(),
                        on_change=lambda event: self._set_market_system_text(
                            event.value,
                        ),
                    ).classes('min-w-80 flex-1').tooltip(
                        'System containing the station being queried.'
                    )
                else:
                    AutocompleteInput(
                        label='System',
                        value=self._market_system_value(),
                        fetch_suggestions=self.suggest_systems,
                        on_text_changed=self._set_market_system_text,
                        on_selected=self._set_market_system_selected,
                        tooltip='System containing the station being queried.',
                        input_classes='min-w-80 flex-1',
                    ).build()
                
                if self.suggest_stations is None:
                    ui.input(
                        'Station',
                        value=self._market_station_value(),
                        on_change=lambda event: self._set_market_station_text(
                            event.value,
                        ),
                    ).classes('min-w-80 flex-1').tooltip(
                        'Station within the selected system being queried.'
                    )
                else:
                    self.station_autocomplete = AutocompleteInput(
                        label='Station',
                        value=self._market_station_value(),
                        fetch_suggestions=self._suggest_market_stations,
                        on_text_changed=self._set_market_station_text,
                        selection_text=lambda suggestion: str(
                            getattr(suggestion, 'station_name', suggestion.value)
                        ),
                        tooltip='Station within the selected system being queried.',
                        input_classes='min-w-80 flex-1',
                    )
                    self.station_autocomplete.build()
    
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
                ).classes('w-64').tooltip(
                    'Choose whether to show items the station is buying, '
                    'selling, or both.'
                )
    
    def _market_system_value(self) -> str:
        current = self._text_value(self.draft.main_values, 'marketSystem')
        if current:
            return current
        system_name, _station_name = self._split_market_origin()
        return system_name
    
    def _market_station_value(self) -> str:
        current = self._text_value(self.draft.main_values, 'marketStation')
        if current:
            return current
        _system_name, station_name = self._split_market_origin()
        return station_name
    
    def _split_market_origin(self) -> tuple[str, str]:
        origin = self._text_value(self.draft.main_values, 'origin').strip()
        if '/' not in origin:
            return origin, ''
        system_name, station_name = origin.split('/', 1)
        return system_name.strip(), station_name.strip()
    
    def _normalize_market_state(self) -> None:
        system_name, _station_name = self._normalize_station_pair_value(
            self.draft.main_values,
            system_key='marketSystem',
            station_key='marketStation',
            combined_key='origin',
        )
        self.selected_system_id = self._resolve_market_system_id(system_name)
    
    def _resolve_market_system_id(
        self,
        system_name: str | None = None,
    ) -> int | None:
        cleaned = (
            self._market_system_value() if system_name is None else system_name
        )
        return self._resolve_suggestion_id(
            cleaned,
            resolver=self.resolve_system,
            id_attr='system_id',
        )
    
    def _set_market_system_text(self, value: str) -> None:
        cleaned = str(value or '').strip()
        current = self._market_system_value().strip()
        if cleaned == '':
            self.draft.main_values.pop('marketSystem', None)
            self.draft.main_values.pop('marketStation', None)
            self.draft.main_values.pop('origin', None)
            self.selected_system_id = None
            self.on_changed()
            return
        self.draft.main_values['marketSystem'] = cleaned
        if cleaned != current:
            self.draft.main_values.pop('marketStation', None)
            station_autocomplete = getattr(self, 'station_autocomplete', None)
            if station_autocomplete is not None:
                station_autocomplete.clear()
        self.selected_system_id = self._resolve_market_system_id(cleaned)
        self._sync_market_origin()
        self.on_changed()
    
    def _set_market_system_selected(self, suggestion: object) -> None:
        self.selected_system_id = getattr(suggestion, 'system_id', None)
    
    def _set_market_station_text(self, value: str) -> None:
        cleaned = str(value or '').strip()
        if cleaned == '':
            self.draft.main_values.pop('marketStation', None)
        else:
            self.draft.main_values['marketStation'] = cleaned
        self._sync_market_origin()
        self.on_changed()
    
    def _sync_market_origin(self) -> None:
        self._sync_station_pair_value(
            self.draft.main_values,
            system_key='marketSystem',
            station_key='marketStation',
            combined_key='origin',
        )
    
    def _suggest_market_stations(self, text: str) -> list[object]:
        if self.suggest_stations is None:
            return []
        
        system_id = self.selected_system_id
        if system_id is None:
            system_id = self._resolve_market_system_id()
            self.selected_system_id = system_id
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

class OldDataWorkspace(DraftValueHelper):
    """Edit an `olddata` draft using command-local fields only."""
    
    def __init__(
        self,
        draft: CommandDraft,
        *,
        on_changed: Callable[[], None],
        on_execute: Callable[[], None],
        suggest_systems: Callable[[str], list[object]] | None = None,
    ) -> None:
        self.draft = draft
        self.on_changed = on_changed
        self.on_execute = on_execute
        self.suggest_systems = suggest_systems
    
    def build(self) -> None:
        dialog = self._build_extended_dialog()
        with ui.column().classes('w-full gap-3'):
            self._build_search_section()
            self._build_filter_section()
            with ui.row().classes('gap-2'):
                ui.button('Execute Old Data', on_click=self.on_execute)
                ui.button('Extended Options', on_click=dialog.open)
    
    def _build_search_section(self) -> None:
        # Old Data keeps the everyday search inputs on the main pane; the dialog
        # owns the less common result-limiting options.
        values = self.draft.main_values
        with ui.card().classes('w-full'):
            ui.label('Old Data Search')
            ui.label(
                'Find stations with stale market data so you can revisit and '
                'refresh them. Left-pane max data age is not used here.'
            ).classes('text-sm text-gray-600')
            build_system_autocomplete_input(
                label='Near',
                value=self._text_value(values, 'near'),
                on_text_changed=lambda value: self._set_text(
                    values,
                    'near',
                    value,
                ),
                tooltip='Limit old-data results to stations near this system.',
                suggest_systems=self.suggest_systems,
                input_classes='w-full',
            )
            with ui.row().classes('w-full items-end gap-3'):
                ui.number('Distance (ly)', value=self._number_value(values, 'ly'), min=0, step=0.1, precision=2, on_change=lambda event: self._set_float(values, 'ly', event.value)).classes('w-40').tooltip('When Near is set, only include systems within this range.')
                ui.number('Minimum age (days)', value=self._number_value(values, 'minAge'), min=0, step=0.1, precision=2, on_change=lambda event: self._set_float(values, 'minAge', event.value)).classes('w-48').tooltip('List data older than this number of days.')
                ui.checkbox('Sort to shortest path', value=self._bool_value(values, 'route'), on_change=lambda event: self._set_bool(values, 'route', event.value)).tooltip('Requires Near. Sort results to the shortest path.')
    
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
        # Limit and LS max are advanced-only knobs, so they live separately from
        # the main near/distance/age search controls.
        values = self.draft.advanced_values
        dialog = ui.dialog()
        with dialog, ui.card().style('min-width: 48rem; max-width: 95vw;'):
            ui.label('Extended Options')
            with ui.row().classes('w-full items-center gap-3'):
                ui.number('Limit', value=self._number_value(values, 'limit'), min=0, step=1, precision=0, on_change=lambda event: self._set_int(values, 'limit', event.value, 'Limit')).classes('w-32').tooltip('Maximum number of results to show.')
                ui.label('Maximum number of stations to return.').classes('text-sm text-gray-600')
            with ui.row().classes('w-full items-center gap-3'):
                ui.number('LS max', value=self._number_value(values, 'lsMax'), min=0, step=1, precision=0, on_change=lambda event: self._set_int(values, 'lsMax', event.value, 'LS max')).classes('w-40').tooltip('Only consider stations up to this many ls from their star.')
                ui.label('Only include stations within this many ls of arrival.').classes('text-sm text-gray-600')
        return dialog

