"""GUI Run checklist stepper, shared between a detached window and a dialog.

Following a planned Run route hop by hop, with no terminal/stdin stepping. The
step rendering lives in ChecklistView so the same rules drive both the detached
native window (the /run-checklist/<token> page) and the in-window dialog
fallback (RunChecklist). Data is the structured Run snapshot the GUI already
produces (td_exec._snapshot_run_routes -> route/stops/cargo/nav); no CLI text is
scraped and no planner/CLI behaviour changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nicegui import ui

# Reuse the CLI route palette so the checklist reads like the table/CLI output.
from tradedangerous.planner.render_rich import (
    _CHROME,
    _DEST,
    _LOAD_ALT,
    _ORIGIN,
    _PROFIT,
)

from .checklist_store import get_checklist

_GOLD = _LOAD_ALT[0]
_DIM = '#9aa0a6'
_CAP = '#f5c518'
_SELECT = 'user-select: text; -webkit-user-select: text'

class ChecklistView:
    """Render a step-through view of one Run's routes into the current context.

    Builds a route selector (when >1 route), a position label, a step body, and
    Previous/Next controls, and owns its own transient step/route state. The
    embedding container supplies its own Close (dialog) or relies on the window
    chrome (detached page).
    """

    def __init__(self, routes: list[dict[str, Any]]) -> None:
        self._routes = list(routes or [])
        self._route_index = 0
        self._step = 0
        self._position_label = None
        self._content = None
        self._prev_button = None
        self._next_button = None

    def build(self) -> None:
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('Run Checklist').classes('text-lg').style(
                f'color: {_CHROME}; font-weight: 700'
            )
            self._position_label = ui.label('').classes('text-sm')
        if len(self._routes) > 1:
            ui.select(
                {index: f'Route {index + 1}' for index in range(len(self._routes))},
                value=0,
                label='Route',
                on_change=self._on_route_changed,
            ).classes('w-72').tooltip('Choose which route to step through.')
        self._content = ui.column().classes('w-full gap-1')
        with ui.row().classes('w-full items-center gap-2'):
            self._prev_button = ui.button(
                'Previous',
                on_click=self._on_prev,
            ).props('outline').tooltip('Go to the previous step.')
            self._next_button = ui.button(
                'Next',
                on_click=self._on_next,
            ).tooltip('Go to the next step.')
        self._render_step()

    def _on_route_changed(self, event: Any) -> None:
        value = getattr(event, 'value', None)
        if value is None:
            return
        self._route_index = int(value)
        self._step = 0
        self._render_step()

    def _on_prev(self) -> None:
        if self._step > 0:
            self._step -= 1
            self._render_step()

    def _on_next(self) -> None:
        if self._step < self._total_steps() - 1:
            self._step += 1
            self._render_step()

    def _current_route(self) -> dict[str, Any]:
        return self._routes[self._route_index]

    def _total_steps(self) -> int:
        # One step per stop, plus a closing summary step.
        stops = self._current_route().get('stops') or []
        return len(stops) + 1

    def _render_step(self) -> None:
        route = self._current_route()
        stops = route.get('stops') or []
        total = len(stops) + 1
        self._step = max(0, min(self._step, total - 1))

        self._content.clear()
        with self._content:
            if self._step < len(stops):
                self._render_stop(stops[self._step], self._step, len(stops))
            else:
                self._render_finish(route)

        self._position_label.text = f'Step {self._step + 1} of {total}'
        self._prev_button.set_enabled(self._step > 0)
        self._next_button.set_enabled(self._step < total - 1)

    def _render_stop(
        self,
        stop: dict[str, Any],
        index: int,
        stop_count: int,
    ) -> None:
        ui.label(str(stop.get('station', ''))).classes('text-lg').style(
            f'color: {_DEST}; font-weight: 600; {_SELECT}'
        )
        ui.label(f'Stop {index + 1} of {stop_count}').classes('text-sm').style(
            f'color: {_DIM}'
        )
        self._render_cargo('Sell here', stop.get('sell') or [])
        self._render_cargo('Buy here', stop.get('buy') or [])

        nav = stop.get('nav') or []
        if nav:
            ui.label('Fly').classes('text-sm').style(
                f'color: {_DIM}; margin-top: 0.25rem'
            )
            for nav_line in nav:
                ui.label(f'↓ {nav_line}').style(f'color: {_DIM}; {_SELECT}')

        profit = stop.get('profit')
        if profit is not None:
            ui.label(f'Profit  +{int(profit):,} cr').style(
                f'color: {_PROFIT}; margin-top: 0.25rem; {_SELECT}'
            )
        balance = stop.get('balance')
        if balance is not None:
            ui.label(f'Balance  {int(balance):,} cr').style(
                f'color: {_PROFIT}; {_SELECT}'
            )

    def _render_cargo(self, heading: str, lines: list[dict[str, Any]]) -> None:
        if not lines:
            return
        ui.label(heading).classes('text-sm').style(
            f'color: {_DIM}; margin-top: 0.25rem'
        )
        for line in lines:
            qty = int(line.get('qty', 0) or 0)
            item = str(line.get('item', ''))
            price = int(line.get('price', 0) or 0)
            text = f'{qty:,} t {item} @ {price:,} cr/t'
            if line.get('capped'):
                with ui.row().classes('items-baseline gap-1 no-wrap'):
                    ui.label(text).style(f'color: {_GOLD}; {_SELECT}')
                    ui.label('⚑').style(f'color: {_CAP}')
            else:
                ui.label(text).style(f'color: {_GOLD}; {_SELECT}')

    def _render_finish(self, route: dict[str, Any]) -> None:
        ui.label('Route complete').classes('text-lg').style(
            f'color: {_CHROME}; font-weight: 700; {_SELECT}'
        )
        with ui.row().classes('items-baseline gap-2 flex-wrap'):
            ui.label(str(route.get('origin', ''))).style(
                f'color: {_ORIGIN}; font-weight: 600; {_SELECT}'
            )
            ui.label('→').style(f'color: {_DIM}')
            ui.label(str(route.get('destination', ''))).style(
                f'color: {_DEST}; font-weight: 600; {_SELECT}'
            )
        hops = route.get('hop_count', 0)
        jumps = route.get('total_jumps', 0)
        ly = route.get('total_ly', 0.0) or 0.0
        ui.label(
            f'{hops} {"hop" if hops == 1 else "hops"} · '
            f'{jumps} {"jump" if jumps == 1 else "jumps"} · {ly:.2f} ly'
        ).classes('text-sm').style(f'color: {_DIM}; {_SELECT}')
        ui.label(
            f'Total profit  +{int(route.get("total_profit", 0) or 0):,} cr'
        ).style(f'color: {_PROFIT}; font-weight: 600; {_SELECT}')
        ui.label(
            f'Start {int(route.get("starting_credits", 0) or 0):,} cr  →  '
            f'final {int(route.get("ending_credits", 0) or 0):,} cr'
        ).style(f'color: {_CHROME}; {_SELECT}')

class RunChecklist:
    """In-window dialog fallback that embeds a ChecklistView.

    Built once during shell construction so a results-pane refresh never
    destroys it. Used when a detached native window is unavailable.
    """

    def __init__(self) -> None:
        self.dialog = None
        self._content = None

    def build(self) -> None:
        self.dialog = ui.dialog().props('persistent')
        with self.dialog, ui.card().style(
            'min-width: 34rem; max-width: 95vw;'
        ).classes('gap-3'):
            self._content = ui.column().classes('w-full gap-3')
            with ui.row().classes('w-full justify-end'):
                ui.button(
                    'Close',
                    on_click=self.dialog.close,
                ).props('outline').tooltip('Close the checklist.')

    def open_for(self, routes: list[dict[str, Any]] | None) -> None:
        routes = list(routes or [])
        if not routes:
            return
        self._content.clear()
        with self._content:
            ChecklistView(routes).build()
        self.dialog.open()

def _apply_elite_theme() -> None:
    # The detached page is its own client, so it carries none of the shell's
    # theme. Apply the same Elite CSS + body class for a consistent look.
    css = Path(__file__).with_name('themes.css').read_text(encoding='utf-8')
    ui.add_head_html(f'<style>\n{css}\n</style>')
    ui.query('body').classes('td-theme-elite')

@ui.page('/run-checklist/{token}')
def checklist_page(token: str) -> None:
    """Detached checklist window contents, keyed by a transient store token."""
    _apply_elite_theme()
    routes = get_checklist(token)
    with ui.column().classes('w-full p-4 gap-3 td-theme-elite'):
        if not routes:
            ui.label('Checklist data is no longer available.').classes(
                'text-lg'
            ).style(f'color: {_CHROME}; {_SELECT}')
            ui.label(
                'Reopen the checklist from the Trade Dangerous results pane.'
            ).style(f'color: {_DIM}')
            return
        ChecklistView(routes).build()
