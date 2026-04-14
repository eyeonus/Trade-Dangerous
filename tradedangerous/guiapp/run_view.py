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
        suggest_run_avoid: Callable[[str], list[object]] | None = None,
        resolve_system: Callable[[str], object | None] | None = None,
    ) -> None:
        self.draft = draft
        self.on_changed = on_changed
        self.on_execute = on_execute
        self.on_copy_from_profile = on_copy_from_profile
        self.suggest_systems = suggest_systems
        self.suggest_stations = suggest_stations
        self.suggest_run_avoid = suggest_run_avoid
        self.resolve_system = resolve_system
        self.selected_start_system_id: int | None = None
        self.selected_end_system_id: int | None = None
        self.start_station_autocomplete = None
        self.end_station_autocomplete = None
        self.run_via_dialog = None
        self.run_via_summary_label = None
        self.run_via_list_host = None
        self.run_via_system_input_control = None
        self.run_via_station_input_control = None
        self.run_via_candidate_system_text = ''
        self.run_via_candidate_station_text = ''
        self.run_via_selected_system_id: int | None = None
        self.run_avoid_dialog = None
        self.run_avoid_summary_label = None
        self.run_avoid_list_host = None
        self.run_avoid_value_input_control = None
        self.run_avoid_station_input_control = None
        self.run_avoid_candidate_value_text = ''
        self.run_avoid_candidate_station_text = ''
        self.run_avoid_candidate_kind: str | None = None
        self.run_avoid_selected_system_id: int | None = None

    def build(self) -> None:
        self._normalize_run_state()
        # Keep the always-visible pane focused on route-shaping fields and the
        # most common overrides; niche knobs live in the extended dialog.
        self.run_via_dialog = self._build_via_editor_dialog()
        self.run_avoid_dialog = self._build_avoid_editor_dialog()
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
        self.selected_start_system_id = self._resolve_run_system_id(start_system)
        self.selected_end_system_id = self._resolve_run_system_id(end_system)

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

    @staticmethod
    def _control_target(control: Any) -> Any:
        if control is None:
            return None
        return getattr(control, 'input', control)

    def _set_control_value(self, control: Any, value: str) -> None:
        if control is None:
            return
        set_text = getattr(control, 'set_text', None)
        if callable(set_text):
            set_text(value)
            return
        clear = getattr(control, 'clear', None)
        if callable(clear) and value == '':
            clear()
            return
        target = self._control_target(control)
        if target is None:
            return
        set_value = getattr(target, 'set_value', None)
        if callable(set_value):
            set_value(value)
            return
        if hasattr(target, 'value'):
            target.value = value

    def _set_control_enabled(self, control: Any, enabled: bool) -> None:
        target = self._control_target(control)
        if target is None:
            return
        method_name = 'enable' if enabled else 'disable'
        method = getattr(target, method_name, None)
        if callable(method):
            method()

    def _entry_values(self, key: str) -> list[str]:
        entries: list[str] = []
        raw = self._text_value(self.draft.advanced_values, key)
        for line in raw.splitlines():
            for part in line.split(','):
                cleaned = part.strip()
                if cleaned:
                    entries.append(cleaned)
        return entries

    def _set_entry_values(self, key: str, entries: list[str]) -> None:
        cleaned_entries = [entry.strip() for entry in entries if entry.strip()]
        if cleaned_entries:
            self.draft.advanced_values[key] = '\n'.join(cleaned_entries)
        else:
            self.draft.advanced_values.pop(key, None)
        self.on_changed()

    @staticmethod
    def _entries_summary(entries: list[str], prefix: str) -> str:
        if not entries:
            return f'No {prefix} entries selected.'
        preview = ', '.join(entries[:3])
        if len(entries) > 3:
            preview += ', ...'
        noun = 'entry' if len(entries) == 1 else 'entries'
        return f'{len(entries)} {prefix} {noun}: {preview}'

    def _refresh_entry_list(
        self,
        *,
        host: Any,
        entries: list[str],
        empty_text: str,
        heading_text: str,
        remove_handler: Callable[[int], None],
    ) -> None:
        if host is None:
            return
        host.clear()
        with host:
            if not entries:
                ui.label(empty_text).classes('text-sm text-gray-600')
                return
            ui.label(heading_text).classes('text-sm text-gray-600')
            for index, entry in enumerate(entries):
                with ui.row().classes('w-full items-center gap-3 no-wrap'):
                    ui.label(entry).classes('min-w-0 flex-1')
                    ui.button(
                        'Remove',
                        on_click=lambda idx=index: remove_handler(idx),
                    ).props('outline dense')

    def _clear_candidate_text(
        self,
        *,
        text_attr: str,
        control_attr: str,
    ) -> None:
        setattr(self, text_attr, '')
        self._set_control_value(getattr(self, control_attr), '')

    def _build_route_station_pair(
        self,
        *,
        system_label: str,
        station_label: str,
        system_key: str,
        station_key: str,
        combined_key: str,
        selected_attr: str,
        station_autocomplete_attr: str,
        system_tooltip: str,
        station_tooltip: str,
    ) -> None:
        system_value = self._run_system_value(
            system_key=system_key,
            station_key=station_key,
            combined_key=combined_key,
        )
        station_value = self._run_station_value(
            system_key=system_key,
            station_key=station_key,
            combined_key=combined_key,
        )

        if self.suggest_systems is None:
            ui.input(
                system_label,
                value=system_value,
                on_change=lambda event: self._set_run_system_text(
                    event.value,
                    system_key=system_key,
                    station_key=station_key,
                    combined_key=combined_key,
                    selected_attr=selected_attr,
                    station_autocomplete_attr=station_autocomplete_attr,
                ),
            ).classes('min-w-0 w-full').tooltip(system_tooltip)
        else:
            AutocompleteInput(
                label=system_label,
                value=system_value,
                fetch_suggestions=self.suggest_systems,
                on_text_changed=lambda value: self._set_run_system_text(
                    value,
                    system_key=system_key,
                    station_key=station_key,
                    combined_key=combined_key,
                    selected_attr=selected_attr,
                    station_autocomplete_attr=station_autocomplete_attr,
                ),
                on_selected=lambda suggestion: self._set_run_system_selected(
                    suggestion,
                    selected_attr=selected_attr,
                ),
                tooltip=system_tooltip,
                input_classes='min-w-0 w-full',
            ).build()

        if self.suggest_stations is None:
            ui.input(
                station_label,
                value=station_value,
                on_change=lambda event: self._set_run_station_text(
                    event.value,
                    system_key=system_key,
                    station_key=station_key,
                    combined_key=combined_key,
                ),
            ).classes('min-w-0 w-full').tooltip(station_tooltip)
            return

        autocomplete = AutocompleteInput(
            label=station_label,
            value=station_value,
            fetch_suggestions=lambda text: self._suggest_run_stations(
                text,
                selected_attr=selected_attr,
            ),
            on_text_changed=lambda value: self._set_run_station_text(
                value,
                system_key=system_key,
                station_key=station_key,
                combined_key=combined_key,
            ),
            selection_text=lambda suggestion: str(
                getattr(suggestion, 'station_name', suggestion.value)
            ),
            tooltip=station_tooltip,
            input_classes='min-w-0 w-full',
        )
        setattr(self, station_autocomplete_attr, autocomplete)
        autocomplete.build()

    def _build_route_section(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('Route')
            ui.label(
                'Use one of To, Towards, or Loop. '
                'Use either Direct or Hops.'
            ).classes('text-sm text-gray-600')

            with ui.grid(columns=3).classes('w-full gap-3'):
                self._build_route_station_pair(
                    system_label='From System',
                    station_label='From Station',
                    system_key='startSystem',
                    station_key='startStation',
                    combined_key='starting',
                    selected_attr='selected_start_system_id',
                    station_autocomplete_attr='start_station_autocomplete',
                    system_tooltip='System containing your starting station.',
                    station_tooltip='Station you are starting from.',
                )

                ui.element('div')

                self._build_route_station_pair(
                    system_label='To System',
                    station_label='To Station',
                    system_key='endSystem',
                    station_key='endStation',
                    combined_key='ending',
                    selected_attr='selected_end_system_id',
                    station_autocomplete_attr='end_station_autocomplete',
                    system_tooltip='System containing your destination station.',
                    station_tooltip='Station you are heading to.',
                )

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
                    ).tooltip('Create a looping route.')
                    ui.checkbox(
                        'Unique',
                        value=self._bool_value(self.draft.main_values, 'unique'),
                        on_change=lambda event: self._set_bool(
                            self.draft.main_values,
                            'unique',
                            event.value,
                        ),
                    ).tooltip('Only visit each station once in route.')

    def _build_via_editor_dialog(self) -> ui.dialog:
        dialog = ui.dialog()
        with dialog, ui.card().classes('gap-3').style(
            'min-width: 56rem; max-width: 95vw; min-height: 34rem;'
        ):
            ui.label('Edit Via Waypoints')
            ui.label(
                'Add systems or system/station pairs that must appear in the route.'
            ).classes('text-sm text-gray-600')
            with ui.row().classes('w-full items-end gap-6 no-wrap'):
                if self.suggest_systems is None:
                    self.run_via_system_input_control = ui.input(
                        'System',
                        value=self.run_via_candidate_system_text,
                        on_change=lambda event: self._set_run_via_candidate_system_text(
                            event.value,
                        ),
                    ).classes('min-w-80 flex-1').tooltip(
                        'Add a required system waypoint.'
                    )
                else:
                    self.run_via_system_input_control = AutocompleteInput(
                        label='System',
                        value=self.run_via_candidate_system_text,
                        fetch_suggestions=self.suggest_systems,
                        on_text_changed=self._set_run_via_candidate_system_text,
                        on_selected=lambda suggestion: self._set_run_system_selected(
                            suggestion,
                            selected_attr='run_via_selected_system_id',
                        ),
                        tooltip='Add a required system waypoint.',
                        input_classes='min-w-80 flex-1',
                    )
                    self.run_via_system_input_control.build()
                self.run_via_station_input_control = AutocompleteInput(
                    label='Station',
                    value=self.run_via_candidate_station_text,
                    fetch_suggestions=lambda text: self._suggest_run_stations(
                        text,
                        selected_attr='run_via_selected_system_id',
                    ),
                    on_text_changed=self._set_run_via_candidate_station_text,
                    selection_text=lambda suggestion: str(
                        getattr(suggestion, 'station_name', suggestion.value)
                    ),
                    tooltip='Optional station within the selected system.',
                    input_classes='min-w-80 flex-1',
                )
                self.run_via_station_input_control.build()
                ui.button('Add', on_click=self._on_add_run_via)
            self.run_via_list_host = ui.column().classes('w-full gap-2')
            self._refresh_run_via_list()
            with ui.row().classes('w-full justify-end'):
                ui.button('Close', on_click=dialog.close)
        return dialog

    def _run_via_entries(self) -> list[str]:
        return self._entry_values('via')

    def _set_run_via_entries(self, entries: list[str]) -> None:
        self._set_entry_values('via', entries)
        self._refresh_run_via_summary()
        self._refresh_run_via_list()

    def _run_via_summary(self) -> str:
        return self._entries_summary(self._run_via_entries(), 'via')

    def _set_run_via_candidate_system_text(self, value: str) -> None:
        cleaned = str(value or '').strip()
        if cleaned != self.run_via_candidate_system_text:
            self._clear_run_via_station_candidate_text()
        self.run_via_candidate_system_text = cleaned
        self.run_via_selected_system_id = self._resolve_run_system_id(cleaned)

    def _set_run_via_candidate_station_text(self, value: str) -> None:
        self.run_via_candidate_station_text = str(value or '').strip()

    def _clear_run_via_system_candidate_text(self) -> None:
        self._clear_candidate_text(
            text_attr='run_via_candidate_system_text',
            control_attr='run_via_system_input_control',
        )
        self.run_via_selected_system_id = None

    def _clear_run_via_station_candidate_text(self) -> None:
        self._clear_candidate_text(
            text_attr='run_via_candidate_station_text',
            control_attr='run_via_station_input_control',
        )

    def _resolve_run_via_system_name(self, value: str) -> str | None:
        cleaned = str(value or '').strip()
        if cleaned == '':
            return None
        resolved = self.resolve_system(cleaned) if self.resolve_system else None
        if resolved is not None:
            system_name = getattr(resolved, 'system_name', None) or getattr(
                resolved,
                'value',
                None,
            )
            if system_name:
                return str(system_name).strip()
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

    def _resolve_run_via_station_name(self, value: str) -> str | None:
        cleaned = str(value or '').strip()
        if cleaned == '':
            return None
        if self.suggest_stations is None:
            return cleaned
        suggestions = self._suggest_run_stations(
            cleaned,
            selected_attr='run_via_selected_system_id',
        )
        for suggestion in suggestions:
            station_name = getattr(suggestion, 'station_name', None)
            if station_name is None:
                station_name = getattr(suggestion, 'value', None)
            if station_name is None:
                station_name = getattr(suggestion, 'label', None)
            if str(station_name or '').strip().casefold() == cleaned.casefold():
                return str(station_name).strip()
        return None

    def _on_add_run_via(self) -> None:
        system_name = self._resolve_run_via_system_name(
            self.run_via_candidate_system_text
        )
        if system_name is None:
            ui.notify(
                'Choose a valid system for Via.',
                color='warning',
            )
            return
        station_text = self.run_via_candidate_station_text.strip()
        station_name = self._resolve_run_via_station_name(station_text)
        if station_text and station_name is None:
            ui.notify(
                'Choose a valid station for Via.',
                color='warning',
            )
            return
        entry = f'{system_name}/{station_name}' if station_name else system_name
        entries = self._run_via_entries()
        if any(existing.casefold() == entry.casefold() for existing in entries):
            ui.notify(
                f'{entry} is already in Via.',
                color='warning',
            )
            return
        entries.append(entry)
        self._set_run_via_entries(entries)
        self._clear_run_via_system_candidate_text()
        self._clear_run_via_station_candidate_text()

    def _remove_run_via(self, index: int) -> None:
        entries = self._run_via_entries()
        if index < 0 or index >= len(entries):
            return
        entries.pop(index)
        self._set_run_via_entries(entries)

    def _refresh_run_via_summary(self) -> None:
        if self.run_via_summary_label is None:
            return
        self.run_via_summary_label.text = self._run_via_summary()

    def _refresh_run_via_list(self) -> None:
        self._refresh_entry_list(
            host=self.run_via_list_host,
            entries=self._run_via_entries(),
            empty_text='No via entries selected.',
            heading_text='Each entry must appear somewhere in the route.',
            remove_handler=self._remove_run_via,
        )

    def _run_avoid_entries(self) -> list[str]:
        return self._entry_values('avoid')

    def _set_run_avoid_entries(self, entries: list[str]) -> None:
        self._set_entry_values('avoid', entries)
        self._refresh_run_avoid_summary()
        self._refresh_run_avoid_list()

    def _run_avoid_summary(self) -> str:
        return self._entries_summary(self._run_avoid_entries(), 'avoid')

    def _classify_run_avoid_candidate(
        self,
        value: str,
    ) -> tuple[str | None, int | None]:
        cleaned = str(value or '').strip()
        if cleaned == '':
            return None, None
        if self.suggest_run_avoid is not None:
            try:
                suggestions = self.suggest_run_avoid(cleaned)
            except TypeError:
                suggestions = []
            for suggestion in suggestions:
                suggestion_value = str(
                    getattr(suggestion, 'value', '') or ''
                ).strip()
                if suggestion_value.casefold() != cleaned.casefold():
                    continue
                kind = str(getattr(suggestion, 'kind', '') or '').strip()
                if kind == 'item':
                    return 'item', None
                if kind == 'system':
                    system_id = getattr(suggestion, 'system_id', None)
                    return 'system', int(system_id) if system_id is not None else None
        resolved = self.resolve_system(cleaned) if self.resolve_system else None
        if resolved is not None:
            system_id = getattr(resolved, 'system_id', None)
            return 'system', int(system_id) if system_id is not None else None
        return None, None

    def _set_run_avoid_candidate_value_text(self, value: str) -> None:
        cleaned = str(value or '').strip()
        if cleaned != self.run_avoid_candidate_value_text:
            self._clear_run_avoid_station_candidate_text()
        self.run_avoid_candidate_value_text = cleaned
        candidate_kind, system_id = self._classify_run_avoid_candidate(cleaned)
        self.run_avoid_candidate_kind = candidate_kind
        self.run_avoid_selected_system_id = system_id
        self._update_run_avoid_station_input_state()

    def _set_run_avoid_candidate_station_text(self, value: str) -> None:
        self.run_avoid_candidate_station_text = str(value or '').strip()

    def _clear_run_avoid_value_candidate_text(self) -> None:
        self._clear_candidate_text(
            text_attr='run_avoid_candidate_value_text',
            control_attr='run_avoid_value_input_control',
        )
        self.run_avoid_candidate_kind = None
        self.run_avoid_selected_system_id = None
        self._update_run_avoid_station_input_state()

    def _clear_run_avoid_station_candidate_text(self) -> None:
        self._clear_candidate_text(
            text_attr='run_avoid_candidate_station_text',
            control_attr='run_avoid_station_input_control',
        )

    def _resolve_run_avoid_value_name(
        self,
        value: str,
    ) -> tuple[str | None, str | None, int | None]:
        cleaned = str(value or '').strip()
        if cleaned == '':
            return None, None, None
        if self.suggest_run_avoid is not None:
            try:
                suggestions = self.suggest_run_avoid(cleaned)
            except TypeError:
                suggestions = []
            for suggestion in suggestions:
                suggestion_value = str(
                    getattr(suggestion, 'value', '') or ''
                ).strip()
                if suggestion_value.casefold() != cleaned.casefold():
                    continue
                kind = str(getattr(suggestion, 'kind', '') or '').strip()
                if kind == 'item':
                    return 'item', suggestion_value, None
                if kind == 'system':
                    system_id = getattr(suggestion, 'system_id', None)
                    system_name = getattr(suggestion, 'system_name', None)
                    return (
                        'system',
                        str(system_name or suggestion_value).strip(),
                        int(system_id) if system_id is not None else None,
                    )
        resolved = self.resolve_system(cleaned) if self.resolve_system else None
        if resolved is not None:
            system_id = getattr(resolved, 'system_id', None)
            system_name = getattr(resolved, 'system_name', None)
            value_name = getattr(resolved, 'value', None)
            return (
                'system',
                str(system_name or value_name or cleaned).strip(),
                int(system_id) if system_id is not None else None,
            )
        return None, None, None

    def _resolve_run_avoid_station_name(self, value: str) -> str | None:
        cleaned = str(value or '').strip()
        if cleaned == '':
            return None
        if self.suggest_stations is None:
            return cleaned
        suggestions = self._suggest_run_stations(
            cleaned,
            selected_attr='run_avoid_selected_system_id',
        )
        for suggestion in suggestions:
            station_name = getattr(suggestion, 'station_name', None)
            if station_name is None:
                station_name = getattr(suggestion, 'value', None)
            if station_name is None:
                station_name = getattr(suggestion, 'label', None)
            if str(station_name or '').strip().casefold() == cleaned.casefold():
                return str(station_name).strip()
        return None

    def _refresh_run_avoid_summary(self) -> None:
        if self.run_avoid_summary_label is None:
            return
        self.run_avoid_summary_label.text = self._run_avoid_summary()

    def _update_run_avoid_station_input_state(self) -> None:
        control = self.run_avoid_station_input_control
        if control is None:
            return
        should_enable = (
            self.run_avoid_candidate_kind == 'system'
            and self.run_avoid_selected_system_id is not None
        )
        if should_enable:
            self._set_control_enabled(control, True)
            return
        self._clear_run_avoid_station_candidate_text()
        self._set_control_enabled(control, False)

    def _build_avoid_editor_dialog(self) -> ui.dialog:
        dialog = ui.dialog()
        with dialog, ui.card().classes('gap-3').style(
            'min-width: 56rem; max-width: 95vw; min-height: 34rem;'
        ):
            ui.label('Edit Avoid Entries')
            ui.label(
                'Add systems, optional system/station pairs, or items to exclude.'
            ).classes('text-sm text-gray-600')
            with ui.row().classes('w-full items-end gap-6 no-wrap'):
                if self.suggest_run_avoid is None:
                    self.run_avoid_value_input_control = ui.input(
                        'System or Item',
                        value=self.run_avoid_candidate_value_text,
                        on_change=lambda event: self._set_run_avoid_candidate_value_text(
                            event.value,
                        ),
                    ).classes('min-w-80 flex-1').tooltip(
                        'Choose a system or item to avoid.'
                    )
                else:
                    self.run_avoid_value_input_control = AutocompleteInput(
                        label='System or Item',
                        value=self.run_avoid_candidate_value_text,
                        fetch_suggestions=self.suggest_run_avoid,
                        on_text_changed=self._set_run_avoid_candidate_value_text,
                        tooltip='Choose a system or item to avoid.',
                        input_classes='min-w-80 flex-1',
                    )
                    self.run_avoid_value_input_control.build()
                if self.suggest_stations is None:
                    self.run_avoid_station_input_control = ui.input(
                        'Station',
                        value=self.run_avoid_candidate_station_text,
                        on_change=lambda event: self._set_run_avoid_candidate_station_text(
                            event.value,
                        ),
                    ).classes('min-w-80 flex-1').tooltip(
                        'Optional station within the selected system.'
                    )
                else:
                    self.run_avoid_station_input_control = AutocompleteInput(
                        label='Station',
                        value=self.run_avoid_candidate_station_text,
                        fetch_suggestions=lambda text: self._suggest_run_stations(
                            text,
                            selected_attr='run_avoid_selected_system_id',
                        ),
                        on_text_changed=self._set_run_avoid_candidate_station_text,
                        selection_text=lambda suggestion: str(
                            getattr(suggestion, 'station_name', suggestion.value)
                        ),
                        tooltip='Optional station within the selected system.',
                        input_classes='min-w-80 flex-1',
                    )
                    self.run_avoid_station_input_control.build()
                ui.button('Add', on_click=self._on_add_run_avoid)
            self.run_avoid_list_host = ui.column().classes('w-full gap-2')
            self._refresh_run_avoid_list()
            with ui.row().classes('w-full justify-end'):
                ui.button('Close', on_click=dialog.close)
        self._update_run_avoid_station_input_state()
        return dialog

    def _on_add_run_avoid(self) -> None:
        kind, value_name, system_id = self._resolve_run_avoid_value_name(
            self.run_avoid_candidate_value_text
        )
        if kind is None or value_name is None:
            ui.notify(
                'Choose a valid system or item for Avoid.',
                color='warning',
            )
            return
        self.run_avoid_candidate_kind = kind
        self.run_avoid_selected_system_id = system_id
        if kind == 'item':
            entry = value_name
        else:
            station_text = self.run_avoid_candidate_station_text.strip()
            station_name = self._resolve_run_avoid_station_name(station_text)
            if station_text and station_name is None:
                ui.notify(
                    'Choose a valid station for Avoid.',
                    color='warning',
                )
                return
            entry = f'{value_name}/{station_name}' if station_name else value_name
        entries = self._run_avoid_entries()
        if any(existing.casefold() == entry.casefold() for existing in entries):
            ui.notify(
                f'{entry} is already in Avoid.',
                color='warning',
            )
            return
        entries.append(entry)
        self._set_run_avoid_entries(entries)
        self._clear_run_avoid_value_candidate_text()
        self._clear_run_avoid_station_candidate_text()

    def _remove_run_avoid(self, index: int) -> None:
        entries = self._run_avoid_entries()
        if index < 0 or index >= len(entries):
            return
        entries.pop(index)
        self._set_run_avoid_entries(entries)

    def _refresh_run_avoid_list(self) -> None:
        self._refresh_entry_list(
            host=self.run_avoid_list_host,
            entries=self._run_avoid_entries(),
            empty_text='No avoid entries selected.',
            heading_text='Selected entries are excluded from trading.',
            remove_handler=self._remove_run_avoid,
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
                ).classes('w-40').tooltip('Maximum capacity of cargo hold.')
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
                ).classes('w-48').tooltip('Starting credits.')
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
                ).classes('w-40').tooltip('Maximum light years per jump.')
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
            ).tooltip('Summary layout of route instructions.')

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

            with ui.row().classes('w-full items-end gap-3'):
                with ui.column().classes('min-w-96 flex-1 gap-1'):
                    ui.label('Via')
                    self.run_via_summary_label = ui.label(
                        self._run_via_summary()
                    ).classes('text-sm text-gray-600')
                ui.button(
                    'Edit Via...',
                    on_click=self.run_via_dialog.open,
                ).tooltip('Edit the list of required route waypoints.')

            with ui.row().classes('w-full items-end gap-3'):
                with ui.column().classes('min-w-96 flex-1 gap-1'):
                    ui.label('Avoid')
                    self.run_avoid_summary_label = ui.label(
                        self._run_avoid_summary()
                    ).classes('text-sm text-gray-600')
                ui.button(
                    'Edit Avoid...',
                    on_click=self.run_avoid_dialog.open,
                ).tooltip(
                    'Edit the list of excluded systems, stations, and items.'
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
                ).tooltip('Show detail of jumps between hops.')
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
                ).tooltip('Require stations to be in space.')
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
                ).tooltip('Require stations known to have a black market.')

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
                ).tooltip('Show hop progress.')

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
                ).tooltip('Provide a checklist flow for the route.')
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
                ).tooltip('Enable experimental X52 Pro MFD output.')
