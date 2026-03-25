"""Command workspace widgets for the smaller GUI commands."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

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
    ) -> None:
        self.draft = draft
        self.on_changed = on_changed
        self.on_execute = on_execute

    def build(self) -> None:
        with ui.column().classes('w-full gap-3'):
            self._build_route_section()
            self._build_constraint_section()

            with ui.row().classes('gap-2'):
                ui.button('Execute Trade', on_click=self.on_execute)

    def _build_route_section(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('Trade Route')
            ui.label(
                'Enter the station you buy from and the station you sell to.'
            ).classes('text-sm text-gray-600')

            with ui.row().classes('w-full gap-3'):
                ui.input(
                    'Origin',
                    value=self._text_value(self.draft.main_values, 'origin'),
                    on_change=lambda event: self._set_text(
                        self.draft.main_values,
                        'origin',
                        event.value,
                    ),
                ).classes('min-w-96 flex-1')
                ui.input(
                    'Destination',
                    value=self._text_value(self.draft.main_values, 'dest'),
                    on_change=lambda event: self._set_text(
                        self.draft.main_values,
                        'dest',
                        event.value,
                    ),
                ).classes('min-w-96 flex-1')

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
                ).classes('w-40')
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
                ).classes('w-32')
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
                ).classes('w-32')
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
                ).classes('w-32')

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
                ).classes('w-64')
                ui.checkbox(
                    'Reverse route',
                    value=self._bool_value(self.draft.main_values, 'reverse'),
                    on_change=lambda event: self._set_bool(
                        self.draft.main_values,
                        'reverse',
                        event.value,
                    ),
                )


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
        # Shared filters cover the tri-state station traits and pad sizes.
        # Local adds the simpler service-availability booleans underneath.
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
    ) -> None:
        self.draft = draft
        self.on_changed = on_changed
        self.on_execute = on_execute

    def build(self) -> None:
        with ui.column().classes('w-full gap-3'):
            self._build_station_section()
            self._build_view_section()
            with ui.row().classes('gap-2'):
                ui.button('Execute Market', on_click=self.on_execute)

    def _build_station_section(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('Market Station')
            ui.label(
                'Enter the station whose market data you want to inspect.'
            ).classes('text-sm text-gray-600')
            ui.input(
                'Station',
                value=self._text_value(self.draft.main_values, 'origin'),
                on_change=lambda event: self._set_text(
                    self.draft.main_values,
                    'origin',
                    event.value,
                ),
            ).classes('min-w-96 w-full')

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
                ).classes('w-64')


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
                    value=self._number_value(self.draft.main_values, 'refuelJumps'),
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
            get_tri_state=lambda key: self._tri_state_value(self.draft.main_values, key),
            set_bool=lambda key, value: self._set_bool(self.draft.main_values, key, value),
            set_tri_state=lambda key, value: self._set_tri_state(self.draft.main_values, key, value),
            pad_size_enabled=self._pad_size_enabled,
            set_pad_size_flag=self._set_pad_size_flag,
        )


class OldDataWorkspace(DraftValueHelper):
    """Edit an `olddata` draft using command-local fields only."""

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
        # Old Data keeps the everyday search inputs on the main pane; the dialog
        # owns the less common result-limiting options.
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
                ui.number('Minimum age (days)', value=self._number_value(values, 'minAge'), min=0, step=0.1, precision=2, on_change=lambda event: self._set_float(values, 'minAge', event.value)).classes('w-48')
                ui.checkbox('Sort to shortest path', value=self._bool_value(values, 'route'), on_change=lambda event: self._set_bool(values, 'route', event.value))

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
                ui.number('Limit', value=self._number_value(values, 'limit'), min=0, step=1, precision=0, on_change=lambda event: self._set_int(values, 'limit', event.value, 'Limit')).classes('w-32')
                ui.label('Maximum number of stations to return.').classes('text-sm text-gray-600')
            with ui.row().classes('w-full items-center gap-3'):
                ui.number('LS max', value=self._number_value(values, 'lsMax'), min=0, step=1, precision=0, on_change=lambda event: self._set_int(values, 'lsMax', event.value, 'LS max')).classes('w-40')
                ui.label('Only include stations within this many ls of arrival.').classes('text-sm text-gray-600')
        return dialog


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
            ui.label('Find rare goods near a system. Full detail is always shown.').classes('text-sm text-gray-600')
            with ui.row().classes('w-full items-end gap-3'):
                ui.input('Near', value=self._text_value(self.draft.main_values, 'near'), on_change=lambda event: self._set_text(self.draft.main_values, 'near', event.value)).classes('min-w-96 flex-1')
                ui.number('Distance (ly)', value=self._number_value(self.draft.main_values, 'ly'), min=0, step=0.1, precision=2, on_change=lambda event: self._set_float(self.draft.main_values, 'ly', event.value)).classes('w-40')

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
        # Away-from expands into repeated CLI flags and is easy to mistype, so
        # keep it out of the compact main pane and explain it in the dialog.
        dialog = ui.dialog()
        with dialog, ui.card().style('min-width: 56rem; max-width: 95vw;'):
            ui.label('Extended Options')
            ui.label('Leave fields blank to omit them. Away-from systems may be comma-separated or one per line.').classes('text-sm text-gray-600')
            with ui.row().classes('w-full gap-3'):
                ui.number('Limit', value=self._number_value(self.draft.advanced_values, 'limit'), min=0, step=1, precision=0, on_change=lambda event: self._set_int(self.draft.advanced_values, 'limit', event.value, 'Limit')).classes('w-32')
                ui.select({'': 'Any', 'legal': 'Legal only', 'illegal': 'Illegal only'}, value=self._text_value(self.draft.advanced_values, 'legalMode'), label='Legality', on_change=lambda event: self._set_text(self.draft.advanced_values, 'legalMode', event.value)).classes('w-48')
                ui.checkbox('Sort by price', value=self._bool_value(self.draft.advanced_values, 'sortByPrice'), on_change=lambda event: self._set_bool(self.draft.advanced_values, 'sortByPrice', event.value))
                ui.checkbox('Reverse order', value=self._bool_value(self.draft.advanced_values, 'reverse'), on_change=lambda event: self._set_bool(self.draft.advanced_values, 'reverse', event.value))
            with ui.row().classes('w-full gap-3'):
                ui.number('Away distance (ly)', value=self._number_value(self.draft.advanced_values, 'away'), min=0, step=0.1, precision=2, on_change=lambda event: self._set_float(self.draft.advanced_values, 'away', event.value)).classes('w-48')
                ui.textarea('Away from systems', value=self._text_value(self.draft.advanced_values, 'awayFrom'), on_change=lambda event: self._set_text(self.draft.advanced_values, 'awayFrom', event.value)).classes('min-w-96 flex-1')
            with ui.row().classes('justify-end'):
                ui.button('Close', on_click=dialog.close)
        return dialog