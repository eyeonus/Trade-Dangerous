from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

from .profiles import CommandDraft


_TRI_STATE_OPTIONS = {
    '': 'Any',
    'Y': 'Yes only',
    'N': 'No only',
    '?': 'Unknown only',
}


class RunWorkspace:
    def __init__(
        self,
        draft: CommandDraft,
        *,
        on_changed: Callable[[], None],
        on_execute: Callable[[], None],
        on_copy_from_profile: Callable[[], None],
    ) -> None:
        self.draft = draft
        self.on_changed = on_changed
        self.on_execute = on_execute
        self.on_copy_from_profile = on_copy_from_profile

    def build(self) -> None:
        extended_dialog = self._build_extended_dialog()

        with ui.column().classes('w-full gap-3'):
            ui.label(
                'Blank override fields inherit from the left pane. '
                'Copy from profile stamps the current left-pane values '
                'into local overrides.'
            ).classes('text-sm text-gray-600')

            self._build_route_section()
            self._build_override_section()
            self._build_filter_section()

            with ui.row().classes('gap-2'):
                ui.button('Copy from profile', on_click=self.on_copy_from_profile)
                ui.button('Extended Options', on_click=extended_dialog.open)
                ui.button('Execute Run', on_click=self.on_execute)

    def _build_route_section(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('Route')
            ui.label(
                'Use one of To, Towards, or Loop. '
                'Use either Direct or Hops.'
            ).classes('text-sm text-gray-600')

            with ui.row().classes('w-full gap-3'):
                ui.input(
                    'From',
                    value=self._text_value(self.draft.main_values, 'starting'),
                    on_change=lambda event: self._set_text(
                        self.draft.main_values,
                        'starting',
                        event.value,
                    ),
                ).classes('min-w-80 flex-1')
                ui.input(
                    'To',
                    value=self._text_value(self.draft.main_values, 'ending'),
                    on_change=lambda event: self._set_text(
                        self.draft.main_values,
                        'ending',
                        event.value,
                    ),
                ).classes('min-w-80 flex-1')
                ui.input(
                    'Towards',
                    value=self._text_value(self.draft.main_values, 'goalSystem'),
                    on_change=lambda event: self._set_text(
                        self.draft.main_values,
                        'goalSystem',
                        event.value,
                    ),
                ).classes('min-w-80 flex-1')

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
                ).classes('w-32')
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
                ).classes('w-40')
                with ui.row().classes('items-center gap-4 pl-2'):
                    ui.checkbox(
                        'Direct',
                        value=self._bool_value(self.draft.main_values, 'direct'),
                        on_change=lambda event: self._set_bool(
                            self.draft.main_values,
                            'direct',
                            event.value,
                        ),
                    )
                    ui.checkbox(
                        'Loopback',
                        value=self._bool_value(self.draft.main_values, 'loop'),
                        on_change=lambda event: self._set_bool(
                            self.draft.main_values,
                            'loop',
                            event.value,
                        ),
                    )
                    ui.checkbox(
                        'Unique',
                        value=self._bool_value(self.draft.main_values, 'unique'),
                        on_change=lambda event: self._set_bool(
                            self.draft.main_values,
                            'unique',
                            event.value,
                        ),
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
                ).classes('w-40')
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
                ).classes('w-40')

    def _build_filter_section(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('Common Filters')

            with ui.row().classes('w-full gap-3'):
                ui.select(
                    _TRI_STATE_OPTIONS,
                    value=self._tri_state_value(
                        self.draft.main_values,
                        'planetary',
                    ),
                    label='Planetary',
                    on_change=lambda event: self._set_tri_state(
                        self.draft.main_values,
                        'planetary',
                        event.value,
                    ),
                ).classes('w-48')
                ui.select(
                    _TRI_STATE_OPTIONS,
                    value=self._tri_state_value(
                        self.draft.main_values,
                        'fleet',
                    ),
                    label='Fleet Carrier',
                    on_change=lambda event: self._set_tri_state(
                        self.draft.main_values,
                        'fleet',
                        event.value,
                    ),
                ).classes('w-48')
                ui.select(
                    _TRI_STATE_OPTIONS,
                    value=self._tri_state_value(
                        self.draft.main_values,
                        'odyssey',
                    ),
                    label='Odyssey',
                    on_change=lambda event: self._set_tri_state(
                        self.draft.main_values,
                        'odyssey',
                        event.value,
                    ),
                ).classes('w-48')
                ui.checkbox(
                    'Summary output',
                    value=self._bool_value(self.draft.main_values, 'summary'),
                    on_change=lambda event: self._set_bool(
                        self.draft.main_values,
                        'summary',
                        event.value,
                    ),
                )

            with ui.row().classes('w-full items-center gap-4'):
                ui.label('Pad sizes')
                ui.checkbox(
                    'S',
                    value=self._pad_size_enabled('S'),
                    on_change=lambda event: self._set_pad_size_flag(
                        'S',
                        event.value,
                    ),
                )
                ui.checkbox(
                    'M',
                    value=self._pad_size_enabled('M'),
                    on_change=lambda event: self._set_pad_size_flag(
                        'M',
                        event.value,
                    ),
                )
                ui.checkbox(
                    'L',
                    value=self._pad_size_enabled('L'),
                    on_change=lambda event: self._set_pad_size_flag(
                        'L',
                        event.value,
                    ),
                )

            ui.label(
                'All pad sizes checked means unrestricted. '
                'The tri-state filters use Any / Yes / No / Unknown semantics.'
            ).classes('text-sm text-gray-600')

    def _build_extended_dialog(self) -> ui.dialog:
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
                ).classes('min-w-80 flex-1')
                ui.input(
                    'Avoid',
                    value=self._text_value(self.draft.advanced_values, 'avoid'),
                    on_change=lambda event: self._set_text(
                        self.draft.advanced_values,
                        'avoid',
                        event.value,
                    ),
                ).classes('min-w-80 flex-1')

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
                ).classes('w-40')
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
                ).classes('w-40')
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
                ).classes('w-40')
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
                ).classes('w-32')
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
                ).classes('w-40')
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
                ).classes('w-40')
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
                ).classes('w-32')
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
                ).classes('w-40')

            with ui.row().classes('w-full gap-3'):
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
                ).classes('w-32')
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
                ).classes('w-32')
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
                ).classes('w-32')
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
                ).classes('w-32')
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
                ).classes('w-32')

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
                ).classes('w-40')
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
                ).classes('w-40')
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
                ).classes('w-40')

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
                )
                ui.checkbox(
                    'Summary',
                    value=self._bool_value(
                        self.draft.advanced_values,
                        'summary',
                    ),
                    on_change=lambda event: self._set_bool(
                        self.draft.advanced_values,
                        'summary',
                        event.value,
                    ),
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