from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

THEME_OPTIONS: dict[str, str] = {
    'default': 'Default',
    'elite': 'Elite Dark',
}


class SettingsWorkspace:
    def __init__(
        self,
        *,
        selected_theme: str,
        on_theme_changed: Callable[[str], None],
    ) -> None:
        self.selected_theme = selected_theme
        self.on_theme_changed = on_theme_changed
        self.theme_select = None
        self.advanced_dialog = None

    def build(self) -> None:
        self.advanced_dialog = ui.dialog()
        with self.advanced_dialog:
            with ui.card().classes('gap-2').style(
                'min-width: 32rem; max-width: 90vw;'
            ):
                ui.label('Advanced Settings')
                ui.label(
                    'Advanced NiceGUI and network settings are not wired yet.'
                ).classes('text-sm text-gray-700 whitespace-pre-wrap')
                ui.button('Close', on_click=self.advanced_dialog.close)

        with ui.column().classes('w-full gap-3'):
            with ui.card().classes('w-full gap-3'):
                ui.label('Settings')
                ui.label(
                    'Basic GUI preferences for Trade Dangerous.'
                ).classes('text-sm text-gray-600')
                self.theme_select = ui.select(
                    THEME_OPTIONS,
                    value=self.selected_theme,
                    label='Theme',
                    on_change=self._on_theme_changed,
                ).classes('w-64')
                ui.button(
                    'Advanced Settings',
                    on_click=self.advanced_dialog.open,
                )

    def _on_theme_changed(self, event: Any) -> None:
        value = getattr(event, 'value', None)
        if value is None:
            return
        self.on_theme_changed(str(value))