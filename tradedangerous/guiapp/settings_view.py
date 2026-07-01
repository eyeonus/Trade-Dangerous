"""GUI-only settings workspace."""

from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

from .profiles import LAUNCHER_PORT_MAX, LAUNCHER_PORT_MIN

THEME_OPTIONS: dict[str, str] = {
    'default': 'Default',
    'elite': 'Elite Dark',
}
DEFAULT_PORT = 8542

class SettingsWorkspace:
    """Render settings that affect the shell itself rather than TD commands."""
    
    def __init__(
        self,
        *,
        selected_theme: str,
        selected_launcher_port: int | None,
        selected_journal_dir: str | None,
        on_theme_changed: Callable[[str], None],
        on_launcher_port_changed: Callable[[int | None], None],
        on_journal_dir_changed: Callable[[str | None], None],
    ) -> None:
        self.selected_theme = selected_theme
        self.selected_launcher_port = selected_launcher_port
        self.selected_journal_dir = selected_journal_dir
        self.on_theme_changed = on_theme_changed
        self.on_launcher_port_changed = on_launcher_port_changed
        self.on_journal_dir_changed = on_journal_dir_changed
        self.theme_select = None
        self.launcher_port_input = None
        self.journal_dir_input = None
        self.advanced_dialog = None
    
    def build(self) -> None:
        self.advanced_dialog = ui.dialog()
        with self.advanced_dialog:
            with ui.card().classes('gap-2').style(
                'min-width: 32rem; max-width: 90vw;'
            ):
                ui.label('Advanced Settings')
                ui.label(
                    'Set the application port used when Trade Dangerous '
                    'starts. If you choose a custom value, it must be between '
                    f'{LAUNCHER_PORT_MIN} and {LAUNCHER_PORT_MAX}. Changes '
                    'apply on the next launch.'
                ).classes('text-sm text-gray-700 whitespace-pre-wrap')
                self.launcher_port_input = ui.input(
                    'Application Port',
                    value=(
                        ''
                        if self.selected_launcher_port is None
                        else str(self.selected_launcher_port)
                    ),
                    placeholder=f'Use default ({DEFAULT_PORT})',
                    validation=self._validate_launcher_port,
                    on_change=self._on_launcher_port_changed,
                ).props('clearable inputmode=numeric').classes('w-64').tooltip(
                    'Set the local application port used on the next launch. '
                    'Leave blank to try 8542 first.'
                )
                ui.label(
                    f'Leave this blank to try {DEFAULT_PORT} first. If '
                    f'{DEFAULT_PORT} is unavailable, Trade Dangerous will ask '
                    'Windows for a random open local port.'
                ).classes('text-sm text-gray-700 whitespace-pre-wrap')
                ui.label(
                    'Only change advanced settings if you know why you need '
                    'them.'
                ).classes('text-sm text-amber-700 whitespace-pre-wrap')
                ui.button('Close', on_click=self.advanced_dialog.close)
        
        with ui.column().classes('w-full gap-3'):
            with ui.card().classes('w-full gap-3'):
                ui.label('Settings')
                ui.label(
                    'Basic GUI preferences for Trade Dangerous.'
                ).classes('text-sm text-gray-600')
                # Theme changes apply immediately to the live shell instead of
                # waiting for an Execute-style action.
                self.theme_select = ui.select(
                    THEME_OPTIONS,
                    value=self.selected_theme,
                    label='Theme',
                    on_change=self._on_theme_changed,
                ).classes('w-64').tooltip(
                    'Choose the live GUI theme for this session and future '
                    'launches.'
                )
                self.journal_dir_input = ui.input(
                    'Journal directory',
                    value=self.selected_journal_dir or '',
                    placeholder='Auto-detect',
                    on_change=self._on_journal_dir_changed,
                ).props('clearable').classes('w-full max-w-xl').tooltip(
                    'Folder holding your Elite Dangerous journal files. Leave '
                    'blank to let Trade Dangerous find it automatically; set it '
                    'only if auto-detection picks the wrong place.'
                )
                ui.button(
                    'Advanced Settings',
                    on_click=self.advanced_dialog.open,
                )
    
    def _on_theme_changed(self, event: Any) -> None:
        value = getattr(event, 'value', None)
        if value is None:
            return
        self.on_theme_changed(str(value))

    def _on_journal_dir_changed(self, event: Any) -> None:
        value = getattr(event, 'value', None)
        text = str(value or '').strip()
        # Blank (or a cleared field) means "auto"; report None so the shell
        # stores nothing and the CLI keeps its normal journal discovery.
        self.on_journal_dir_changed(text or None)
    
    def _on_launcher_port_changed(self, event: Any) -> None:
        value = getattr(event, 'value', None)
        if value in {None, ''}:
            self.on_launcher_port_changed(None)
            return
        text = str(value).strip()
        if text == '':
            self.on_launcher_port_changed(None)
            return
        try:
            port = int(text)
        except (TypeError, ValueError):
            return
        if port < LAUNCHER_PORT_MIN or port > LAUNCHER_PORT_MAX:
            return
        self.on_launcher_port_changed(port)
    
    @staticmethod
    def _validate_launcher_port(value: Any) -> str | None:
        if value in {None, ''}:
            return None
        text = str(value).strip()
        if text == '':
            return None
        try:
            numeric_value = float(text)
        except (TypeError, ValueError):
            return 'Port must be a whole number.'
        if not numeric_value.is_integer():
            return 'Port must be a whole number.'
        port = int(numeric_value)
        if port < LAUNCHER_PORT_MIN or port > LAUNCHER_PORT_MAX:
            return (
                f'Port must be between {LAUNCHER_PORT_MIN} '
                f'and {LAUNCHER_PORT_MAX}.'
            )
        return None
