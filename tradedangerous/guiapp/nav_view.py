"""Nav workspace widgets and nav-specific list editor helpers."""

from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

from .autocomplete import AutocompleteInput, build_system_autocomplete_input
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
        suggest_systems: Callable[[str], list[object]] | None = None,
    ) -> None:
        self.draft = draft
        self.on_changed = on_changed
        self.on_execute = on_execute
        self.suggest_systems = suggest_systems
        self.nav_via_summary_label = None
        self.nav_via_list_host = None
        self.nav_via_input_control = None
        self.nav_via_candidate_text = ''
        self.nav_avoid_summary_label = None
        self.nav_avoid_list_host = None
        self.nav_avoid_input_control = None
        self.nav_avoid_candidate_text = ''

    def build(self) -> None:
        via_dialog = self._build_via_editor_dialog()
        avoid_dialog = self._build_avoid_editor_dialog()
        with ui.column().classes('w-full gap-3'):
            self._build_route_section()
            self._build_option_section(via_dialog, avoid_dialog)
            self._build_filter_section()
            with ui.row().classes('gap-2'):
                ui.button('Execute Nav', on_click=self.on_execute)

    def _build_route_section(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('Navigation Route')
            ui.label(
                'Find a route between two systems.'
            ).classes('text-sm text-gray-600')
            with ui.row().classes('w-full items-end gap-3'):
                build_system_autocomplete_input(
                    label='Start',
                    value=self._text_value(self.draft.main_values, 'starting'),
                    on_text_changed=lambda value: self._set_text(
                        self.draft.main_values,
                        'starting',
                        value,
                    ),
                    tooltip='System to start from.',
                    suggest_systems=self.suggest_systems,
                )
                build_system_autocomplete_input(
                    label='End',
                    value=self._text_value(self.draft.main_values, 'ending'),
                    on_text_changed=lambda value: self._set_text(
                        self.draft.main_values,
                        'ending',
                        value,
                    ),
                    tooltip='System to end at.',
                    suggest_systems=self.suggest_systems,
                )
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
                ).classes('w-40').tooltip(
                    'Maximum light years per jump.'
                )

    def _build_option_section(
        self,
        via_dialog: ui.dialog,
        avoid_dialog: ui.dialog,
    ) -> None:
        with ui.card().classes('w-full'):
            ui.label('Navigation Options')

            with ui.row().classes('w-full items-end gap-3'):
                with ui.column().classes('min-w-96 flex-1 gap-1'):
                    ui.label('Via')
                    self.nav_via_summary_label = ui.label(
                        self._nav_via_summary()
                    ).classes('text-sm text-gray-600')
                ui.button('Edit Via...', on_click=via_dialog.open).tooltip(
                    'Edit the ordered list of systems that must be visited.'
                )

            with ui.row().classes('w-full items-end gap-3'):
                with ui.column().classes('min-w-96 flex-1 gap-1'):
                    ui.label('Avoid')
                    self.nav_avoid_summary_label = ui.label(
                        self._nav_avoid_summary()
                    ).classes('text-sm text-gray-600')
                ui.button(
                    'Edit Avoid...',
                    on_click=avoid_dialog.open,
                ).tooltip(
                    'Edit the list of systems to exclude from routing.'
                )

            with ui.row().classes('w-full items-center gap-3'):
                ui.label(
                    'Jumps between fuel stops (optional)'
                ).classes('text-sm text-gray-600')
                ui.number(
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
                ).classes('w-12').tooltip(
                    'Require a station after this many jumps.'
                )

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

    def _build_via_editor_dialog(self) -> ui.dialog:
        dialog = ui.dialog()
        with dialog, ui.card().classes('gap-3').style(
            'min-width: 52rem; max-width: 95vw; min-height: 34rem;'
        ):
            ui.label('Edit Via Waypoints')
            ui.label(
                'Add systems that must be visited in order.'
            ).classes('text-sm text-gray-600')

            with ui.row().classes('w-full items-end gap-6 no-wrap'):
                if self.suggest_systems is None:
                    self.nav_via_input_control = ui.input(
                        'System',
                        value=self.nav_via_candidate_text,
                        on_change=lambda event: self._set_nav_via_candidate_text(
                            event.value,
                        ),
                    ).classes('min-w-96 flex-1').tooltip(
                        'Add a system waypoint.'
                    )
                else:
                    self.nav_via_input_control = AutocompleteInput(
                        label='System',
                        value=self.nav_via_candidate_text,
                        fetch_suggestions=self.suggest_systems,
                        on_text_changed=self._set_nav_via_candidate_text,
                        tooltip='Add a system waypoint.',
                        input_classes='min-w-96 flex-1',
                    )
                    self.nav_via_input_control.build()

                ui.button('Add', on_click=self._on_add_nav_via)

            self.nav_via_list_host = ui.column().classes('w-full gap-2')
            self._refresh_nav_via_list()

            with ui.row().classes('w-full justify-end'):
                ui.button('Close', on_click=dialog.close)

        return dialog

    def _build_avoid_editor_dialog(self) -> ui.dialog:
        dialog = ui.dialog()
        with dialog, ui.card().classes('gap-3').style(
            'min-width: 52rem; max-width: 95vw; min-height: 34rem;'
        ):
            ui.label('Edit Avoid Systems')
            ui.label(
                'Add systems to exclude from routing.'
            ).classes('text-sm text-gray-600')

            with ui.row().classes('w-full items-end gap-6 no-wrap'):
                if self.suggest_systems is None:
                    self.nav_avoid_input_control = ui.input(
                        'System',
                        value=self.nav_avoid_candidate_text,
                        on_change=lambda event: self._set_nav_avoid_candidate_text(
                            event.value,
                        ),
                    ).classes('min-w-96 flex-1').tooltip(
                        'Add a system to exclude.'
                    )
                else:
                    self.nav_avoid_input_control = AutocompleteInput(
                        label='System',
                        value=self.nav_avoid_candidate_text,
                        fetch_suggestions=self.suggest_systems,
                        on_text_changed=self._set_nav_avoid_candidate_text,
                        tooltip='Add a system to exclude.',
                        input_classes='min-w-96 flex-1',
                    )
                    self.nav_avoid_input_control.build()

                ui.button('Add', on_click=self._on_add_nav_avoid)

            self.nav_avoid_list_host = ui.column().classes('w-full gap-2')
            self._refresh_nav_avoid_list()

            with ui.row().classes('w-full justify-end'):
                ui.button('Close', on_click=dialog.close)

        return dialog

    def _nav_entries(self, key: str) -> list[str]:
        entries: list[str] = []
        raw = self._text_value(self.draft.main_values, key)

        for line in raw.splitlines():
            for part in line.split(','):
                cleaned = part.strip()
                if cleaned:
                    entries.append(cleaned)

        return entries

    def _set_nav_entries(self, key: str, entries: list[str]) -> None:
        cleaned_entries = [entry.strip() for entry in entries if entry.strip()]

        if cleaned_entries:
            self.draft.main_values[key] = '\n'.join(cleaned_entries)
        else:
            self.draft.main_values.pop(key, None)

        self.on_changed()

    def _nav_via_entries(self) -> list[str]:
        return self._nav_entries('via')

    def _set_nav_via_entries(self, entries: list[str]) -> None:
        self._set_nav_entries('via', entries)
        self._refresh_nav_via_summary()
        self._refresh_nav_via_list()

    def _nav_avoid_entries(self) -> list[str]:
        return self._nav_entries('avoid')

    def _set_nav_avoid_entries(self, entries: list[str]) -> None:
        self._set_nav_entries('avoid', entries)
        self._refresh_nav_avoid_summary()
        self._refresh_nav_avoid_list()

    def _nav_via_summary(self) -> str:
        entries = self._nav_via_entries()
        if not entries:
            return 'No waypoints selected.'

        preview = ', '.join(entries[:3])
        if len(entries) > 3:
            preview += ', ...'

        noun = 'waypoint' if len(entries) == 1 else 'waypoints'
        return f'{len(entries)} {noun}: {preview}'

    def _nav_avoid_summary(self) -> str:
        entries = self._nav_avoid_entries()
        if not entries:
            return 'No systems excluded.'

        preview = ', '.join(entries[:3])
        if len(entries) > 3:
            preview += ', ...'

        noun = 'system' if len(entries) == 1 else 'systems'
        return f'{len(entries)} {noun} excluded: {preview}'

    def _set_nav_via_candidate_text(self, value: str) -> None:
        self.nav_via_candidate_text = str(value or '').strip()

    def _set_nav_avoid_candidate_text(self, value: str) -> None:
        self.nav_avoid_candidate_text = str(value or '').strip()

    def _clear_nav_candidate_text(
        self,
        *,
        text_attr: str,
        control_attr: str,
    ) -> None:
        setattr(self, text_attr, '')
        control = getattr(self, control_attr)

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

    def _clear_nav_via_candidate_text(self) -> None:
        self._clear_nav_candidate_text(
            text_attr='nav_via_candidate_text',
            control_attr='nav_via_input_control',
        )

    def _clear_nav_avoid_candidate_text(self) -> None:
        self._clear_nav_candidate_text(
            text_attr='nav_avoid_candidate_text',
            control_attr='nav_avoid_input_control',
        )

    def _resolve_nav_system_name(self, value: str) -> str | None:
        cleaned = str(value or '').strip()
        if cleaned == '':
            return None

        if self.suggest_systems is None:
            return cleaned

        try:
            suggestions = self.suggest_systems(cleaned)
        except TypeError:
            suggestions = []

        for suggestion in suggestions:
            system_name = getattr(suggestion, 'system_name', None)
            if system_name is None:
                system_name = getattr(suggestion, 'value', None)
            if system_name is None:
                system_name = getattr(suggestion, 'label', None)

            if str(system_name or '').strip().casefold() == cleaned.casefold():
                return str(system_name).strip()

        return None

    def _on_add_nav_via(self) -> None:
        system_name = self._resolve_nav_system_name(self.nav_via_candidate_text)
        if system_name is None:
            ui.notify(
                'Choose a valid system for Via.',
                color='warning',
            )
            return

        entries = self._nav_via_entries()
        if any(entry.casefold() == system_name.casefold() for entry in entries):
            ui.notify(
                f'{system_name} is already in Via.',
                color='warning',
            )
            return

        entries.append(system_name)
        self._set_nav_via_entries(entries)
        self._clear_nav_via_candidate_text()

    def _on_add_nav_avoid(self) -> None:
        system_name = self._resolve_nav_system_name(
            self.nav_avoid_candidate_text
        )
        if system_name is None:
            ui.notify(
                'Choose a valid system for Avoid.',
                color='warning',
            )
            return

        entries = self._nav_avoid_entries()
        if any(entry.casefold() == system_name.casefold() for entry in entries):
            ui.notify(
                f'{system_name} is already in Avoid.',
                color='warning',
            )
            return

        entries.append(system_name)
        self._set_nav_avoid_entries(entries)
        self._clear_nav_avoid_candidate_text()

    def _move_nav_via(self, index: int, offset: int) -> None:
        entries = self._nav_via_entries()
        target_index = index + offset

        if index < 0 or index >= len(entries):
            return
        if target_index < 0 or target_index >= len(entries):
            return

        entries[index], entries[target_index] = (
            entries[target_index],
            entries[index],
        )
        self._set_nav_via_entries(entries)

    def _remove_nav_via(self, index: int) -> None:
        entries = self._nav_via_entries()
        if index < 0 or index >= len(entries):
            return

        entries.pop(index)
        self._set_nav_via_entries(entries)

    def _remove_nav_avoid(self, index: int) -> None:
        entries = self._nav_avoid_entries()
        if index < 0 or index >= len(entries):
            return

        entries.pop(index)
        self._set_nav_avoid_entries(entries)

    def _refresh_nav_via_summary(self) -> None:
        if self.nav_via_summary_label is None:
            return
        self.nav_via_summary_label.text = self._nav_via_summary()

    def _refresh_nav_avoid_summary(self) -> None:
        if self.nav_avoid_summary_label is None:
            return
        self.nav_avoid_summary_label.text = self._nav_avoid_summary()

    def _refresh_nav_via_list(self) -> None:
        if self.nav_via_list_host is None:
            return

        entries = self._nav_via_entries()
        self.nav_via_list_host.clear()

        with self.nav_via_list_host:
            if not entries:
                ui.label('No waypoints selected.').classes(
                    'text-sm text-gray-600'
                )
                return

            ui.label('Waypoints are visited in order.').classes(
                'text-sm text-gray-600'
            )

            for index, entry in enumerate(entries):
                with ui.row().classes('w-full items-center gap-3 no-wrap'):
                    ui.label(f'{index + 1}.').classes('w-8 text-right')
                    ui.label(entry).classes('min-w-0 flex-1')

                    up_button = ui.button(
                        '↑',
                        on_click=lambda idx=index: self._move_nav_via(
                            idx,
                            -1,
                        ),
                    ).props('outline dense')
                    if index == 0:
                        up_button.disable()

                    down_button = ui.button(
                        '↓',
                        on_click=lambda idx=index: self._move_nav_via(
                            idx,
                            1,
                        ),
                    ).props('outline dense')
                    if index == len(entries) - 1:
                        down_button.disable()

                    ui.button(
                        'Remove',
                        on_click=lambda idx=index: self._remove_nav_via(idx),
                    ).props('outline dense')

    def _refresh_nav_avoid_list(self) -> None:
        if self.nav_avoid_list_host is None:
            return

        entries = self._nav_avoid_entries()
        self.nav_avoid_list_host.clear()

        with self.nav_avoid_list_host:
            if not entries:
                ui.label('No systems excluded.').classes(
                    'text-sm text-gray-600'
                )
                return

            ui.label(
                'Excluded systems are ignored during routing.'
            ).classes('text-sm text-gray-600')

            for index, entry in enumerate(entries):
                with ui.row().classes('w-full items-center gap-3 no-wrap'):
                    ui.label(entry).classes('min-w-0 flex-1')
                    ui.button(
                        'Remove',
                        on_click=lambda idx=index: self._remove_nav_avoid(idx),
                    ).props('outline dense')