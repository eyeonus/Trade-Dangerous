from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

from .profiles import CommandDraft
from .shared_filter_view import build_shared_filter_section


class BuySellWorkspace:
    def __init__(
        self,
        command: str,
        draft: CommandDraft,
        *,
        on_changed: Callable[[], None],
        on_execute: Callable[[], None],
        on_copy_from_profile: Callable[[], None],
    ) -> None:
        self.command = command
        self.draft = draft
        self.on_changed = on_changed
        self.on_execute = on_execute
        self.on_copy_from_profile = on_copy_from_profile

    def build(self) -> None:
        action = 'Buy' if self.command == 'buy' else 'Sell'
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
                ).classes('min-w-96 flex-1')

                ui.input(
                    'Near',
                    value=self._text_value(self.draft.main_values, 'near'),
                    on_change=lambda event: self._set_text(
                        self.draft.main_values,
                        'near',
                        event.value,
                    ),
                ).classes('min-w-80 flex-1')

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
                ).classes('w-40')
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
                ).classes('w-40')

    def _build_override_section(self, action: str) -> None:
        with ui.card().classes('w-full'):
            ui.label(f'{action} Overrides')
            ui.label(
                'These override inherited commander / ship baseline values '
                'for this search only. Clear a field to return to inherited '
                'behaviour.'
            ).classes('text-sm text-gray-600')

            with ui.row().classes('w-full gap-3'):
                if self.command == 'buy':
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
                    ).classes('w-40')
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
                    ).classes('w-48')

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

    def _build_extended_dialog(self) -> ui.dialog:
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
                ).classes('w-32')
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
                    ).classes('w-40')
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
                ).classes('w-32')
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
                ).classes('w-32')

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
                    )

    def _set_text(
        self,
        payload: dict[str, Any],
        key: str,
        value: Any,
    ) -> None:
        cleaned = str(value or '').strip()
        if cleaned == '':
            payload.pop(key, None)
        else:
            payload[key] = cleaned
        self.on_changed()

    def _set_int(
        self,
        payload: dict[str, Any],
        key: str,
        value: Any,
        label: str,
    ) -> None:
        if value is None or value == '':
            payload.pop(key, None)
            self.on_changed()
            return

        if isinstance(value, float):
            if value.is_integer():
                payload[key] = int(value)
                self.on_changed()
                return
            ui.notify(f'{label} must be an integer.', color='negative')
            return

        if isinstance(value, int):
            payload[key] = value
            self.on_changed()
            return

        ui.notify(f'{label} must be an integer.', color='negative')

    def _set_float(
        self,
        payload: dict[str, Any],
        key: str,
        value: Any,
    ) -> None:
        if value is None or value == '':
            payload.pop(key, None)
        else:
            payload[key] = value
        self.on_changed()

    def _set_bool(
        self,
        payload: dict[str, Any],
        key: str,
        value: Any,
    ) -> None:
        payload[key] = bool(value)
        self.on_changed()

    def _set_tri_state(
        self,
        payload: dict[str, Any],
        key: str,
        value: Any,
    ) -> None:
        cleaned = str(value or '')
        if cleaned == '':
            payload.pop(key, None)
        else:
            payload[key] = cleaned
        self.on_changed()

    def _set_pad_size_flag(self, pad_size: str, enabled: Any) -> None:
        current_raw = self.draft.main_values.get('padSize')
        current = set('SML') if current_raw in (None, '') else set(str(current_raw))

        if enabled:
            current.add(pad_size)
        else:
            current.discard(pad_size)

        ordered = ''.join(size for size in 'SML' if size in current)
        if ordered == 'SML':
            self.draft.main_values.pop('padSize', None)
        else:
            self.draft.main_values['padSize'] = ordered

        self.on_changed()

    @staticmethod
    def _text_value(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        return '' if value is None else str(value)

    @staticmethod
    def _number_value(payload: dict[str, Any], key: str) -> int | float | None:
        value = payload.get(key)
        if value in (None, ''):
            return None
        return value

    @staticmethod
    def _bool_value(payload: dict[str, Any], key: str) -> bool:
        return bool(payload.get(key))

    @staticmethod
    def _tri_state_value(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if value in ('Y', 'N', '?'):
            return value
        return ''

    def _pad_size_enabled(self, pad_size: str) -> bool:
        current = self.draft.main_values.get('padSize')
        if current in (None, ''):
            return True
        return pad_size in str(current)