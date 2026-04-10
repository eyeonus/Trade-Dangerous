from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from nicegui import ui

from .gui_search import Suggestion

class AutocompleteInput:
    """Reusable debounced autocomplete input backed by suggestion records."""
    
    def __init__(
        self,
        *,
        label: str,
        value: str = '',
        fetch_suggestions: Callable[[str], list[Suggestion]],
        on_text_changed: Callable[[str], None],
        on_selected: Callable[[Suggestion], None] | None = None,
        selection_text: Callable[[Suggestion], str] | None = None,
        tooltip: str | None = None,
        input_classes: str = 'w-full',
        input_props: str = '',
        min_chars: int = 1,
        limit: int = 10,
        debounce_seconds: float = 0.15,
    ) -> None:
        self.label = label
        self.value = value
        self.fetch_suggestions = fetch_suggestions
        self.on_text_changed = on_text_changed
        self.on_selected = on_selected
        self.selection_text = selection_text
        self.tooltip = tooltip
        self.input_classes = input_classes
        self.input_props = input_props
        self.min_chars = max(0, int(min_chars))
        self.limit = max(1, int(limit))
        self.debounce_seconds = max(0.0, float(debounce_seconds))
        
        self.root = None
        self.input = None
        self.overlay = None
        self._search_task: asyncio.Task | None = None
        self._suppress_next_change = False
        self._latest_query = ''
    
    def build(self) -> Any:
        self.root = ui.element('div').classes(self.input_classes).style(
            'position: relative;'
        )
        
        with self.root:
            self.input = ui.input(
                self.label,
                value=self.value,
                on_change=self._on_text_changed,
            ).classes('w-full')
            
            if self.input_props:
                self.input.props(self.input_props)
            
            if self.tooltip:
                self.input.tooltip(self.tooltip)
            
            self.overlay = ui.element('div').style(
                'position: absolute; '
                'left: 0; '
                'right: 0; '
                'top: calc(100% + 0.25rem); '
                'z-index: 2000;'
            )
        
        return self.root
    
    def set_text(self, value: str) -> None:
        text = str(value or '')
        
        if self._search_task is not None and not self._search_task.done():
            self._search_task.cancel()
        
        self._clear_overlay()
        self._latest_query = text
        self._suppress_next_change = True
        self.value = text
        
        if self.input is not None:
            set_value = getattr(self.input, 'set_value', None)
            if callable(set_value):
                set_value(text)
            else:
                self.input.value = text
    
    def clear(self) -> None:
        self.set_text('')
    
    def _on_text_changed(self, event: Any) -> None:
        value = str(getattr(event, 'value', '') or '')
        
        if self._suppress_next_change:
            self._suppress_next_change = False
            return
        
        self.on_text_changed(value)
        self._latest_query = value
        
        if self._search_task is not None and not self._search_task.done():
            self._search_task.cancel()
        
        if len(value.strip()) < self.min_chars:
            self._clear_overlay()
            return
        
        self._search_task = asyncio.create_task(
            self._run_search(expected_query=value)
        )
    
    async def _run_search(self, *, expected_query: str) -> None:
        try:
            if self.debounce_seconds > 0:
                await asyncio.sleep(self.debounce_seconds)
            
            if expected_query != self._latest_query:
                return
            
            text = expected_query.strip()
            if len(text) < self.min_chars:
                self._clear_overlay()
                return
            
            suggestions = self.fetch_suggestions(text)[:self.limit]
            if expected_query != self._latest_query:
                return
            
            self._render_suggestions(suggestions)
        except asyncio.CancelledError:
            return
    
    def _render_suggestions(self, suggestions: list[Suggestion]) -> None:
        if self.overlay is None:
            return
        
        self.overlay.clear()
        
        if not suggestions:
            return
        
        with self.overlay:
            with ui.element('div').classes('w-full').style(
                'background: #050505; '
                'border: 1px solid #f07b05; '
                'border-radius: 0.5rem; '
                'box-shadow: 0 8px 18px rgba(0, 0, 0, 0.45); '
                'max-height: 18rem; '
                'overflow-y: auto; '
                'overflow-x: hidden;'
            ):
                for suggestion in suggestions:
                    ui.button(
                        suggestion.label,
                        on_click=lambda selected=suggestion: self._apply_selection(
                            selected
                        ),
                    ).props(
                        'flat no-caps align=left'
                    ).classes(
                        'w-full justify-start rounded-none'
                    ).style(
                        'background: transparent; '
                        'color: #f2f2f2; '
                        'padding: 0.75rem 1rem; '
                        'margin: 0;'
                    )
    
    def _apply_selection(self, suggestion: Suggestion) -> None:
        if self._search_task is not None and not self._search_task.done():
            self._search_task.cancel()
        
        selected_text = self._selection_text_for(suggestion)
        
        self._clear_overlay()
        self._latest_query = selected_text
        self._suppress_next_change = True
        
        if self.input is not None:
            set_value = getattr(self.input, 'set_value', None)
            if callable(set_value):
                set_value(selected_text)
            else:
                self.input.value = selected_text
        
        self.on_text_changed(selected_text)
        
        if self.on_selected is not None:
            self.on_selected(suggestion)
    
    def _selection_text_for(self, suggestion: Suggestion) -> str:
        if self.selection_text is not None:
            return str(self.selection_text(suggestion))
        return suggestion.value
    
    def _clear_overlay(self) -> None:
        if self.overlay is None:
            return
        self.overlay.clear()

def build_system_autocomplete_input(
    *,
    label: str,
    value: str,
    on_text_changed: Callable[[str], None],
    tooltip: str,
    suggest_systems: Callable[[str], list[object]] | None,
    input_classes: str = 'min-w-96 flex-1',
) -> None:
    """Render a system-only input with optional autocomplete support."""
    if suggest_systems is None:
        ui.input(
            label,
            value=value,
            on_change=lambda event: on_text_changed(event.value),
        ).classes(input_classes).tooltip(tooltip)
        return
    
    AutocompleteInput(
        label=label,
        value=value,
        fetch_suggestions=suggest_systems,
        on_text_changed=on_text_changed,
        tooltip=tooltip,
        input_classes=input_classes,
    ).build()
