"""Top-level NiceGUI shell for the new Trade Dangerous GUI."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from nicegui import ui

from .profiles import GuiStore, save_gui_store
from .run_view import RunWorkspace
from .buy_sell_view import BuySellWorkspace
from .command_views import (
    LocalWorkspace,
    MarketWorkspace,
    OldDataWorkspace,
    TradeWorkspace,
)
from .nav_view import NavWorkspace
from .settings_view import SettingsWorkspace
from .import_runtime import (
    begin_import_stop_confirmation,
    build_import_request,
    cancel_import_stop_confirmation,
    consume_one_shot_import_flags,
    is_import_running,
    request_import_stop,
    run_import_execution,
)
from .import_view import ImportWorkspace
from .journal_import import read_journal_facts
from .results_view import render_command_results
from .session import ExecutionStatus, SessionState
from .td_exec import GuiCommandRequest, TdCommandProcess, TdExecutor
from .gui_search import get_gui_search_service
from tradedangerous import TradeException

COMMAND_OPTIONS: dict[str, str] = {
    'run': 'Run',
    'buy': 'Buy',
    'sell': 'Sell',
    'trade': 'Direct',
    'local': 'Local',
    'market': 'Market',
    'nav': 'Nav',
    'olddata': 'Old Data',
    'import': 'Import',
    'settings': 'Settings',
}

class AppShell:
    """Own the long-lived widgets and coordinate session/store updates."""
    
    def __init__(
        self,
        store: GuiStore,
        *,
        window_close_state: Any | None = None,
    ) -> None:
        
        self.store = store
        self.window_close_state = window_close_state
        self.session = SessionState.from_store(store)
        self.executor = TdExecutor()
        self.search_service = get_gui_search_service()
        self.active_command_process: TdCommandProcess | None = None
        self.active_command_task: asyncio.Task | None = None
        
        self.command_select = None
        self.status_label = None
        self.profile_select = None
        self.ship_name_input = None
        self.commander_name_input = None
        self.credits_input = None
        self.max_data_age_input = None
        self.capacity_input = None
        self.reserved_capacity_input = None
        self.insurance_input = None
        self.effective_capacity_label = None
        self.jump_range_full_input = None
        self.jump_range_empty_input = None
        self.workspace_host = None
        self.right_pane_toggle = None
        self.right_pane_host = None
        self.right_pane_view = 'setup'
        self.root_container = None
        self.body_query = None
        self.command_switch_dialog = None
        self.command_switch_message = None
    
    def build(self) -> None:
        # Themes are pure CSS overrides loaded once into the page head; runtime
        # theme switching only swaps classes on the body and root container.
        ui.add_head_html(
            '<style>\n'
            'html, body {\n'
            '    margin: 0;\n'
            '    height: 100%;\n'
            '    overflow: hidden;\n'
            '}\n'
            f'{self._theme_css_text()}\n'
            '</style>'
        )
        
        self._build_command_switch_dialog()
        self.body_query = ui.query('body')
        self.root_container = ui.column().classes(
            'w-full h-screen min-h-0 gap-2 p-2 box-border overflow-hidden '
            'td-theme-default'
        )
        with self.root_container:
            self._build_top_bar()
            with ui.splitter(value=27).classes(
                'w-full min-h-0 flex-1 overflow-hidden'
            ) as splitter:
                with splitter.before:
                    with ui.column().classes(
                        'w-full h-full min-h-0 pr-2 box-border overflow-hidden'
                    ):
                        with ui.scroll_area().classes(
                            'w-full h-full min-h-0'
                        ).props(
                            'visible '
                            ':vertical-thumb-style="{'
                            "right: '2px', "
                            "width: '12px', "
                            "borderRadius: '6px', "
                            "backgroundColor: 'rgba(240, 123, 5, 0.9)', "
                            "opacity: 1"
                            '}" '
                            ':vertical-bar-style="{'
                            "right: '2px', "
                            "width: '12px', "
                            "borderRadius: '6px', "
                            "backgroundColor: 'rgba(255, 255, 255, 0.14)', "
                            "opacity: 1"
                            '}"'
                        ):
                            self._build_left_pane()
                with splitter.after:
                    with ui.scroll_area().classes(
                        'w-full h-full min-h-0'
                    ).props(
                        'visible '
                        ':vertical-thumb-style="{'
                        "right: '2px', "
                        "width: '12px', "
                        "borderRadius: '6px', "
                        "backgroundColor: 'rgba(240, 123, 5, 0.9)', "
                        "opacity: 1"
                        '}" '
                        ':vertical-bar-style="{'
                        "right: '2px', "
                        "width: '12px', "
                        "borderRadius: '6px', "
                        "backgroundColor: 'rgba(255, 255, 255, 0.14)', "
                        "opacity: 1"
                        '}"'
                    ):
                        self._build_right_pane()
            ui.element('div').classes('w-full shrink-0').style(
                'height: 0.75rem;'
            )
        
        self._apply_theme()
        self._refresh_ui()
    
    @staticmethod
    def _theme_css_text() -> str:
        return Path(__file__).with_name('themes.css').read_text(
            encoding='utf-8',
        )
    
    def _apply_theme(self) -> None:
        theme_class = f'td-theme-{self._selected_theme()}'
        
        if self.root_container is not None:
            self.root_container.classes(
                remove='td-theme-default td-theme-elite',
            )
            self.root_container.classes(
                add=theme_class,
            )
        
        if self.body_query is not None:
            self.body_query.classes(
                remove='td-theme-default td-theme-elite',
            )
            self.body_query.classes(
                add=theme_class,
            )
    
    def _build_top_bar(self) -> None:
        with ui.row().classes('w-full items-center gap-0'):
            with ui.row().classes('items-center gap-4 pr-2 box-border').style(
                'width: 27%; min-width: 23rem;'
            ):
                self.command_select = ui.select(
                    COMMAND_OPTIONS,
                    value=self.session.selected_command,
                    label='Command',
                    on_change=self._on_command_changed,
                ).classes('min-w-40').tooltip(
                    'Select which Trade Dangerous command to use.'
                )
                self.status_label = ui.label('Status: Idle')
            with ui.row().classes('items-center gap-3 pl-2'):
                self.right_pane_toggle = ui.toggle(
                    {
                        'setup': 'Input',
                        'results': 'Results',
                        'diagnostics': 'Diagnostics',
                    },
                    value=self.right_pane_view,
                    on_change=self._on_right_pane_view_changed,
                ).tooltip(
                    'Show input dialog, recent results, or diagnostics '
                    'for the selected command.'
                )
    
    def _build_left_pane(self) -> None:
        with ui.column().classes('w-full gap-3 pr-2 box-border').style(
            'min-width: 23rem;'
        ):
            with ui.row().classes('w-full'):
                ui.button(
                    'Import from Journal',
                    on_click=self._on_import_from_journal,
                ).classes('w-full').tooltip(
                    'Read your commander and current ship from the Elite '
                    'Dangerous journal and fill the fields below. If the '
                    'journal cannot be found, set its folder in Settings.'
                )
            ui.label('Commander Details')
            self.commander_name_input = ui.input(
                'Commander Name',
                on_change=self._on_global_changed,
            ).classes('w-full').tooltip(
                'Commander Name (Remembered between sessions)'
            )
            self.credits_input = ui.input(
                'Credits',
                on_change=self._on_global_changed,
            ).classes('w-full').tooltip(
                'Credits (Remembered between sessions)'
            )
            self.max_data_age_input = ui.input(
                'Max data age (days)',
                on_change=self._on_global_changed,
            ).classes('w-full').tooltip(
                'Default age of data to use in queries. '
                '(Remembered between sessions)'
            )
            
            ui.separator()
            ui.label('Ship Profile')
            self.profile_select = ui.select(
                self._profile_options(),
                value=self.session.selected_profile_id,
                label='Ship Profile',
                on_change=self._on_profile_changed,
            ).classes('w-full').tooltip(
                'Select the active ship profile.'
            )
            self.ship_name_input = ui.input(
                'Ship Name',
                on_change=self._on_ship_changed,
            ).classes('w-full').tooltip(
                'Display name for the selected ship profile.'
            )
            with ui.row().classes('w-full gap-3 no-wrap'):
                self.capacity_input = ui.input(
                    'Capacity',
                    on_change=self._on_ship_changed,
                ).classes('min-w-0 flex-1').tooltip(
                    'Maximum cargo space of selected ship.'
                )
                self.reserved_capacity_input = ui.input(
                    'Reserved Capacity',
                    on_change=self._on_ship_changed,
                ).classes('min-w-0 flex-1').tooltip(
                    'Cargo capacity to keep in reserve. Effective Capacity '
                    'is Capacity minus Reserved Capacity.'
                )
            self.effective_capacity_label = ui.label('Effective Capacity:')
            self.insurance_input = ui.input(
                'Insurance',
                on_change=self._on_ship_changed,
            ).classes('w-full').tooltip(
                'Credits to keep in reserve for ship insurance rebuy.'
            )
            self.jump_range_full_input = ui.input(
                'Jump Range (Full)',
                on_change=self._on_ship_changed,
            ).classes('w-full').tooltip(
                'Stored laden jump-range baseline for the selected '
                'ship profile.'
            )
            self.jump_range_empty_input = ui.input(
                'Jump Range (Empty)',
                on_change=self._on_ship_changed,
            ).classes('w-full').tooltip(
                'Stored empty jump-range baseline for the selected '
                'ship profile.'
            )
            
            ui.separator()
            with ui.row().classes('w-full gap-2'):
                ui.button('New', on_click=self._on_new_profile)
                ui.button('Save', on_click=self._on_save_profile)
                ui.button('Revert', on_click=self._on_revert_profile)    
    
    def _build_right_pane(self) -> None:
        self.right_pane_host = ui.column().classes('w-full gap-3 pl-2')
    
    def _build_command_switch_dialog(self) -> None:
        self.command_switch_dialog = ui.dialog().props('persistent')
        with self.command_switch_dialog, ui.card().style(
            'min-width: 30rem; max-width: 95vw;'
        ).classes('gap-3'):
            ui.label('Stop running command?').classes('text-lg')
            self.command_switch_message = ui.label('').classes(
                'whitespace-pre-wrap'
            )
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button(
                    'Let It Finish',
                    on_click=lambda: self.command_switch_dialog.submit(False),
                )
                ui.button(
                    'Switch and Stop',
                    on_click=lambda: self.command_switch_dialog.submit(True),
                ).props('color=negative')
    
    @staticmethod
    def _command_label(command: str | None) -> str:
        if not command:
            return 'Command'
        return COMMAND_OPTIONS.get(command, str(command).title())
    
    def _command_process_is_busy(self) -> bool:
        runner = self.active_command_process
        return runner is not None and runner.is_active()
    
    def _has_pending_command_process(self) -> bool:
        return self.active_command_process is not None
    
    def _mark_window_close_worker(
        self,
        *,
        kind: str,
        command: str,
        pid: int | None,
    ) -> None:
        if self.window_close_state is None:
            return
        self.window_close_state.mark_running(
            kind=kind,
            command=command,
            pid=pid,
        )
    
    def _clear_window_close_worker(self) -> None:
        if self.window_close_state is None:
            return
        self.window_close_state.clear()
    
    def _switch_command(self, command: str) -> None:
        self.session.set_command(self.store, command)
        self.right_pane_view = 'setup'
        save_gui_store(self.store)
        self._refresh_ui()
    
    def _restore_command_selection(self) -> None:
        self._refreshing_ui = True
        # Ordinary commands no longer run inside NiceGUI threads. Launch a
        # dedicated child process so tool switch and native window close can
        # stop work immediately without killing the whole GUI process.
        try:
            self.command_select.value = self.session.selected_command
        finally:
            self._refreshing_ui = False
    
    async def _confirm_stop_before_switch(self, message: str) -> bool:
        if self.command_switch_message is None or self.command_switch_dialog is None:
            return True
        self.command_switch_message.text = message
        return bool(await self.command_switch_dialog)
    
    def _stop_active_command_for_switch(self, target_command: str) -> None:
        runner = self.active_command_process
        if runner is None:
            return
        runner.terminate(
            f'{self._command_label(runner.command)} was stopped when '
            f'switching to {self._command_label(target_command)}.'
        )
    
    def _on_right_pane_view_changed(self, event: Any) -> None:
        value = getattr(event, 'value', None)
        if value is None:
            return
        self.right_pane_view = str(value)
        self._refresh_ui()
    
    async def _on_command_changed(self, event: Any) -> None:
        if getattr(self, '_refreshing_ui', False):
            return
        
        value = getattr(event, 'value', None)
        if value is None:
            return
        
        new_command = str(value)
        if new_command == self.session.selected_command:
            return
        
        if is_import_running(session=self.session):
            confirmed = await self._confirm_stop_before_switch(
                'Import is still running. Switching to '
                f'{self._command_label(new_command)} will stop it '
                'immediately and may leave your local Trade Dangerous '
                'database inconsistent. Switch anyway?'
            )
            if not confirmed:
                self._restore_command_selection()
                return
            request_import_stop(
                session=self.session,
                reason=(
                    'Import was stopped when switching to '
                    f'{self._command_label(new_command)}. Your local '
                    'Trade Dangerous database may be inconsistent until '
                    'import is run again.'
                ),
            )
            self._switch_command(new_command)
            return
        
        if self._command_process_is_busy():
            runner = self.active_command_process
            message = (
                f'{self._command_label(runner.command)} is still running. '
                f'Switch to {self._command_label(new_command)} and stop it, '
                'or let it finish?'
            )
            confirmed = await self._confirm_stop_before_switch(message)
            if not confirmed:
                self._restore_command_selection()
                return
            self._stop_active_command_for_switch(new_command)
        
        self._switch_command(new_command)
    
    def _on_profile_changed(self, event: Any) -> None:
        value = getattr(event, 'value', None)
        if value is None:
            return
        self.session.load_profile(self.store, str(value))
        save_gui_store(self.store)
        self._refresh_ui()
    
    def _on_new_profile(self) -> None:
        if not self._capture_ship_inputs():
            return
        self.session.create_new_ship_profile(self.store)
        save_gui_store(self.store)
        self._refresh_ui()
    
    def _on_save_profile(self) -> None:
        if not self._capture_ship_inputs():
            return
        self.session.save_ship_profile(self.store)
        save_gui_store(self.store)
        ui.notify('Ship profile saved.')
        self._refresh_ui()
    
    def _on_revert_profile(self) -> None:
        self.session.revert_ship_profile(self.store)
        self._refresh_ui()
        ui.notify('Ship profile reverted.')

    def _on_import_from_journal(self) -> None:
        # Read current commander/ship facts from the configured (or
        # auto-discovered) journal and pre-fill the left-pane fields.
        try:
            facts = read_journal_facts(self.store.journal_dir)
        except TradeException as exc:
            self._show_journal_dialog(
                'Journal not found',
                str(exc),
                show_fix_hint=True,
            )
            return
        except Exception as exc:  # noqa: BLE001 - surface anything unexpected
            self._show_journal_dialog(
                'Could not read the journal',
                f'{type(exc).__name__}: {exc}',
                show_fix_hint=True,
            )
            return

        imported, unchanged = self._apply_journal_facts(facts)
        save_gui_store(self.store)
        self._refresh_ui()
        self._show_import_summary(imported, unchanged)

    def _apply_journal_facts(self, facts) -> tuple[list[str], list[str]]:
        # Fill only the fields the journal actually provided; everything else
        # keeps its current value. Commander/credits persist immediately;
        # ship fields land in the working profile (marked dirty) for Save.
        imported: list[str] = []
        unchanged: list[str] = []
        state = self.session.global_state
        commander = (facts.commander_name if facts.commander_name is not None
                     else state.commander_name)
        credits = facts.credits if facts.credits is not None else state.credits
        self.session.set_global_state(
            self.store,
            commander_name=commander,
            credits=credits,
            max_data_age_days=state.max_data_age_days,
        )
        (imported if facts.commander_name is not None else unchanged).append(
            'Commander Name'
        )
        (imported if facts.credits is not None else unchanged).append('Credits')

        ship = self.session.ship_state
        if facts.ship_name is not None:
            ship.ship_name = facts.ship_name
            imported.append('Ship Name')
        else:
            unchanged.append('Ship Name')
        if facts.cargo_capacity is not None:
            ship.capacity = facts.cargo_capacity
            imported.append('Capacity')
        else:
            unchanged.append('Capacity')
        if facts.insurance is not None:
            ship.insurance = facts.insurance
            imported.append('Insurance')
        else:
            unchanged.append('Insurance')
        self.session.mark_ship_dirty()
        return imported, unchanged

    def _show_import_summary(
        self,
        imported: list[str],
        unchanged: list[str],
    ) -> None:
        lines: list[str] = []
        if imported:
            lines.append('Imported: ' + ', '.join(imported) + '.')
        else:
            lines.append('Nothing was imported.')
        if unchanged:
            lines.append(
                'Left unchanged (not found in journal): '
                + ', '.join(unchanged) + '.'
            )
        lines.append(
            'Ship fields are filled in the form. Click Save to keep them in '
            'the profile.'
        )
        self._show_journal_dialog('Imported from journal', '\n'.join(lines))

    def _show_journal_dialog(
        self,
        title: str,
        body: str,
        *,
        show_fix_hint: bool = False,
    ) -> None:
        # The profile area has no result pane, so report import outcomes and
        # errors in a dialog. Text is selectable so the message can be copied.
        dialog = ui.dialog()
        with dialog, ui.card().style('min-width: 28rem; max-width: 90vw;'):
            ui.label(title).classes('text-lg')
            ui.label(body).classes('whitespace-pre-wrap').style(
                'user-select: text; -webkit-user-select: text;'
            )
            if show_fix_hint:
                ui.label(
                    'Fix: open Settings and set "Journal directory" to your '
                    'Elite Dangerous saved-games folder, then try again. You '
                    'can also set the ELITE_JOURNAL_PATH environment variable.'
                ).classes('text-sm whitespace-pre-wrap').style(
                    'user-select: text; -webkit-user-select: text;'
                )
            with ui.row().classes('w-full justify-end'):
                ui.button('OK', on_click=dialog.close)
        dialog.open()
    
    def _on_global_changed(self, _event: Any) -> None:
        if getattr(self, '_refreshing_ui', False):
            return
        if not self._capture_global_inputs():
            return
        save_gui_store(self.store)
        self._refresh_ui()
    
    def _on_ship_changed(self, _event: Any) -> None:
        if getattr(self, '_refreshing_ui', False):
            return
        if self._capture_ship_inputs():
            self._refresh_ui()
    
    def _on_run_draft_changed(self) -> None:
        # Draft widgets mutate the persisted draft objects directly, so this
        # handler only needs to flush the latest snapshot to disk.
        save_gui_store(self.store)
    
    def _selected_theme(self) -> str:
        # Layout is persisted as loose JSON, so tolerate stale or unknown
        # values and fall back to the stock theme.
        value = self.store.layout.get('theme')
        if value in {'default', 'elite'}:
            return str(value)
        return 'default'
    
    def _selected_launcher_port(self) -> int | None:
        return self.store.launcher_port

    def _selected_journal_dir(self) -> str | None:
        return self.store.journal_dir
    
    def _on_theme_changed(self, theme_name: str) -> None:
        theme = str(theme_name)
        if theme not in {'default', 'elite'}:
            return
        self.store.layout['theme'] = theme
        save_gui_store(self.store)
        self._apply_theme()
        self._refresh_ui()
        self._register_native_window_size_handler()
    
    def _on_launcher_port_changed(self, port: int | None) -> None:
        self.store.launcher_port = port
        save_gui_store(self.store)

    def _on_journal_dir_changed(self, journal_dir: str | None) -> None:
        self.store.journal_dir = self._clean_text(journal_dir)
        save_gui_store(self.store)

    def _run_is_unanchored(self) -> bool:
        # No From and no To means run will search the whole galaxy. Read the
        # same draft keys build_run_argv maps onto --from/--to.
        main = self.session.draft.main_values
        has_from = bool(str(main.get('starting') or '').strip())
        has_to = bool(str(main.get('ending') or '').strip())
        return not has_from and not has_to

    async def _confirm_unanchored_run(self) -> bool:
        # Native GUI stand-in for run's terminal 'Continue?' prompt. The GUI
        # never reads stdin; on confirmation the worker answers run's prompt.
        dialog = ui.dialog()
        with dialog, ui.card().style('min-width: 28rem; max-width: 90vw;'):
            ui.label('Search the whole galaxy?').classes('text-lg')
            ui.label(
                'No From or To system is set. Trade Dangerous will search the '
                'whole galaxy for the best trades, which can take several '
                'minutes. You can stop it from the command controls.'
            ).classes('whitespace-pre-wrap')
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button(
                    'Cancel', on_click=lambda: dialog.submit(False)
                ).props('outline')
                ui.button('Search', on_click=lambda: dialog.submit(True))
        return bool(await dialog)

    def _on_begin_import_stop_confirmation(self) -> None:
        if begin_import_stop_confirmation(session=self.session):
            self._refresh_ui()
    
    def _on_cancel_import_stop_confirmation(self) -> None:
        if cancel_import_stop_confirmation(session=self.session):
            self._refresh_ui()
    
    def _on_request_import_stop(self) -> None:
        if request_import_stop(session=self.session):
            self._refresh_ui()
            return
        
        ui.notify('No import is currently running.', color='warning')
    
    def _on_copy_from_profile(self) -> None:
        # Copy the effective cargo capacity rather than raw capacity so the
        # draft sees the same usable tonnage that execution will later use.
        context = {
            'capacity': self.session.ship_state.effective_capacity,
            'insurance': self.session.ship_state.insurance,
            'jump_range_full_ly': self.session.ship_state.jump_range_full_ly,
            'jump_range_empty_ly': self.session.ship_state.jump_range_empty_ly,
            'credits': self.session.global_state.credits,
            'max_data_age_days': self.session.global_state.max_data_age_days,
        }
        copied = {
            key: value
            for key, value in context.items()
            if value is not None
        }
        self.session.draft.context_overrides.update(copied)
        save_gui_store(self.store)
        ui.notify(f'Copied {len(copied)} profile values into draft overrides.')
        self._refresh_ui()
    
    async def _on_execute_command(self) -> None:
        if self.session.selected_command == 'settings':
            ui.notify(
                'Settings is a GUI workspace and cannot be executed.',
                color='warning',
            )
            return
        
        if self.session.selected_command == 'import':
            # Import runs through a subprocess-backed polling loop so progress
            # can stream back into the session while the worker stays killable.
            request = build_import_request(draft=self.session.draft)
            if consume_one_shot_import_flags(draft=self.session.draft):
                save_gui_store(self.store)
                self._refresh_ui()
            await run_import_execution(
                session=self.session,
                request=request,
                refresh_ui=self._refresh_ui_if_alive,
                window_close_state=self.window_close_state,
            )
            return
        
        if self._has_pending_command_process():
            active_command = None
            if self.active_command_process is not None:
                active_command = self.active_command_process.command
            ui.notify(
                (
                    f'{self._command_label(active_command)} is already running. '
                    'Let it finish or switch commands to stop it.'
                ),
                color='warning',
            )
            return
        
        if not self._capture_global_inputs():
            return
        if not self._capture_ship_inputs():
            return

        # An unanchored run (no From and no To) is a whole-galaxy search that TD
        # gates behind a confirmation. Confirm it here in the GUI; the worker
        # then answers run's prompt so it proceeds. Declining stops cleanly.
        confirm_unanchored = False
        if (
            self.session.selected_command == 'run'
            and self._run_is_unanchored()
        ):
            confirm_unanchored = await self._confirm_unanchored_run()
            if not confirm_unanchored:
                ui.notify('Galaxy-wide search cancelled.')
                return

        # Drafts only store per-command fields. Snapshot the current left-pane
        # commander and ship context so execution is self-contained.
        request = GuiCommandRequest(
            command=self.session.selected_command,
            main_values=dict(self.session.draft.main_values),
            advanced_values=dict(self.session.draft.advanced_values),
            context_overrides=dict(self.session.draft.context_overrides),
            global_values={
                'commander_name': self.session.global_state.commander_name,
                'credits': self.session.global_state.credits,
                'max_data_age_days': self.session.global_state.max_data_age_days,
            },
            ship_profile_values={
                'ship_name': self.session.ship_state.ship_name,
                'capacity': self.session.ship_state.capacity,
                'reserved_capacity': self.session.ship_state.reserved_capacity,
                'insurance': self.session.ship_state.insurance,
                'jump_range_full_ly': self.session.ship_state.jump_range_full_ly,
                'jump_range_empty_ly': self.session.ship_state.jump_range_empty_ly,
            },
            journal_dir=self.store.journal_dir,
            confirm_unanchored=confirm_unanchored,
        )
        
        self.session.set_execution(
            status=ExecutionStatus.RUNNING,
            active_command=request.command,
            error_message=None,
            raw_output='',
            diagnostics_output='',
            structured_result=None,
        )
        self._refresh_ui()
        
        try:
            # Launch the ordinary command in its own child process. The GUI
            # keeps only the request/result contract locally; all TD work now
            # happens in the worker so switch/close can stop it cleanly.
            runner = TdCommandProcess.launch(request)
        except Exception as exc:
            self.session.set_execution(
                status=ExecutionStatus.FAILED,
                active_command=request.command,
                error_message=str(exc),
                raw_output='',
                diagnostics_output=repr(exc),
                structured_result=None,
            )
            self._refresh_ui()
            return
        
        self.active_command_process = runner
        self._mark_window_close_worker(
            kind='command',
            command=request.command,
            pid=runner.pid,
        )
        self.active_command_task = asyncio.create_task(
            self._monitor_command_process(request=request, runner=runner)
        )
    
    # The shell polls one child process from asyncio rather than awaiting a
    # thread-pool future. That keeps the UI responsive while still letting us
    # deliver one final result snapshot or stop message into session state.
    async def _monitor_command_process(
        self,
        *,
        request: GuiCommandRequest,
        runner: TdCommandProcess,
    ) -> None:
        result = None
        try:
            while result is None:
                result = runner.poll_result()
                if result is None:
                    await asyncio.sleep(0.1)
        except Exception as exc:
            self.session.set_execution(
                status=ExecutionStatus.FAILED,
                active_command=request.command,
                error_message=str(exc),
                raw_output='',
                diagnostics_output=repr(exc),
                structured_result=None,
            )
        else:
            status = (
                ExecutionStatus.SUCCEEDED
                if result.ok
                else ExecutionStatus.FAILED
            )
            self.session.set_execution(
                status=status,
                active_command=result.command,
                error_message=result.error_message,
                raw_output=result.raw_output,
                diagnostics_output=result.diagnostics_output,
                structured_result=result.structured_result,
            )
        finally:
            runner.close()
            if self.active_command_process is runner:
                self.active_command_process = None
            self._clear_window_close_worker()
            if self.active_command_task is asyncio.current_task():
                self.active_command_task = None
            self._refresh_ui_if_alive()
    
    def _capture_global_inputs(self) -> bool:
        credits = self._parse_optional_int(self.credits_input.value, 'Credits')
        if credits is None and self._has_text(self.credits_input.value):
            return False
        
        max_data_age_days = self._parse_optional_float(
            self.max_data_age_input.value,
            'Max data age',
        )
        if (
            max_data_age_days is None
            and self._has_text(self.max_data_age_input.value)
        ):
            return False
        
        self.session.set_global_state(
            self.store,
            commander_name=self._clean_text(self.commander_name_input.value),
            credits=credits,
            max_data_age_days=max_data_age_days,
        )
        return True
    
    def _capture_ship_inputs(self) -> bool:
        capacity = self._parse_optional_int(self.capacity_input.value, 'Capacity')
        if capacity is None and self._has_text(self.capacity_input.value):
            return False
        
        reserved_capacity = self._parse_optional_int(
            self.reserved_capacity_input.value,
            'Reserved Capacity',
        )
        if (
            reserved_capacity is None
            and self._has_text(self.reserved_capacity_input.value)
        ):
            return False
        
        insurance = self._parse_optional_int(
            self.insurance_input.value,
            'Insurance',
        )
        if (
            insurance is None
            and self._has_text(self.insurance_input.value)
        ):
            return False
        
        jump_range_full = self._parse_optional_float(
            self.jump_range_full_input.value,
            'Jump Range (Full)',
        )
        if (
            jump_range_full is None
            and self._has_text(self.jump_range_full_input.value)
        ):
            return False
        
        jump_range_empty = self._parse_optional_float(
            self.jump_range_empty_input.value,
            'Jump Range (Empty)',
        )
        if (
            jump_range_empty is None
            and self._has_text(self.jump_range_empty_input.value)
        ):
            return False
        
        if (
            capacity is not None
            and reserved_capacity is not None
            and reserved_capacity > capacity
        ):
            ui.notify(
                'Reserved Capacity cannot exceed Capacity.',
                color='negative',
            )
            return False
        
        # Left-pane edits apply to the working session immediately, but the
        # underlying profile is only updated when the user explicitly saves it.
        self.session.ship_state.ship_name = self._clean_text(
            self.ship_name_input.value
        )
        self.session.ship_state.capacity = capacity
        self.session.ship_state.reserved_capacity = reserved_capacity
        self.session.ship_state.insurance = insurance
        self.session.ship_state.jump_range_full_ly = jump_range_full
        self.session.ship_state.jump_range_empty_ly = jump_range_empty
        self.session.mark_ship_dirty()
        return True
    
    def _render_workspace(self) -> None:
        # Import keeps long-lived progress widgets and is rendered separately in
        # `_render_right_pane`; every other workspace can be rebuilt cheaply.
        self.workspace_host.clear()
        with self.workspace_host:
            if self.session.selected_command == 'run':
                workspace = RunWorkspace(
                    self.session.draft,
                    on_changed=self._on_run_draft_changed,
                    on_execute=self._on_execute_command,
                    on_copy_from_profile=self._on_copy_from_profile,
                    suggest_systems=lambda text: self.search_service.suggest_systems(
                        text,
                        limit=10,
                    ),
                    suggest_stations=lambda text, system_id=None: self.search_service.suggest_stations(
                        text,
                        limit=10,
                        system_id=system_id,
                    ),
                    suggest_run_avoid=lambda text: self.search_service.suggest_run_avoid(
                        text,
                        limit=10,
                    ),
                    resolve_system=self.search_service.resolve_system,
                )
                workspace.build()
            elif self.session.selected_command in {'buy', 'sell'}:
                workspace = BuySellWorkspace(
                    self.session.selected_command,
                    self.session.draft,
                    on_changed=self._on_run_draft_changed,
                    on_execute=self._on_execute_command,
                    suggest_systems=lambda text: self.search_service.suggest_systems(
                        text,
                        limit=10,
                    ),
                    suggest_items=lambda text: self.search_service.suggest_items(
                        text,
                        limit=10,
                    ),
                    suggest_buy_search=lambda text: self.search_service.suggest_buy_search(
                        text,
                        limit=10,
                    ),
                )
                workspace.build()
            elif self.session.selected_command == 'trade':
                workspace = TradeWorkspace(
                    self.session.draft,
                    on_changed=self._on_run_draft_changed,
                    on_execute=self._on_execute_command,
                    suggest_systems=lambda text: self.search_service.suggest_systems(
                        text,
                        limit=10,
                    ),
                    suggest_stations=lambda text, system_id=None: self.search_service.suggest_stations(
                        text,
                        limit=10,
                        system_id=system_id,
                    ),
                    resolve_system=self.search_service.resolve_system,
                )
                workspace.build()
            elif self.session.selected_command == 'local':
                workspace = LocalWorkspace(
                    self.session.draft,
                    on_changed=self._on_run_draft_changed,
                    on_execute=self._on_execute_command,
                    suggest_systems=lambda text: self.search_service.suggest_systems(
                        text,
                        limit=10,
                    ),
                )
                workspace.build()
            elif self.session.selected_command == 'market':
                workspace = MarketWorkspace(
                    self.session.draft,
                    on_changed=self._on_run_draft_changed,
                    on_execute=self._on_execute_command,
                    suggest_systems=lambda text: self.search_service.suggest_systems(
                        text,
                        limit=10,
                    ),
                    suggest_stations=lambda text, system_id=None: (
                        []
                        if system_id is None
                        else self.search_service.suggest_stations(
                            text,
                            limit=10,
                            system_id=system_id,
                        )
                    ),
                    resolve_system=lambda text: self.search_service.resolve_system(
                        text,
                    ),
                )
                workspace.build()
            elif self.session.selected_command == 'nav':
                workspace = NavWorkspace(
                    self.session.draft,
                    on_changed=self._on_run_draft_changed,
                    on_execute=self._on_execute_command,
                    suggest_systems=lambda text: self.search_service.suggest_systems(
                        text,
                        limit=10,
                    ),
                )
                workspace.build()
            elif self.session.selected_command == 'olddata':
                workspace = OldDataWorkspace(
                    self.session.draft,
                    on_changed=self._on_run_draft_changed,
                    on_execute=self._on_execute_command,
                    suggest_systems=lambda text: self.search_service.suggest_systems(
                        text,
                        limit=10,
                    ),
                )
                workspace.build()
            elif self.session.selected_command == 'settings':
                workspace = SettingsWorkspace(
                    selected_theme=self._selected_theme(),
                    selected_launcher_port=self._selected_launcher_port(),
                    selected_journal_dir=self._selected_journal_dir(),
                    on_theme_changed=self._on_theme_changed,
                    on_launcher_port_changed=self._on_launcher_port_changed,
                    on_journal_dir_changed=self._on_journal_dir_changed,
                )
                workspace.build()
            else:
                ui.label(
                    f'{self.session.selected_command} workspace '
                    'is not wired yet.'
                ) 
    
    def _render_right_pane(self) -> None:
        is_import = self.session.selected_command == 'import'
        is_input_only = self.session.selected_command in {
            'import',
            'settings',
        }
        if is_input_only:
            self.right_pane_view = 'setup'
        self.right_pane_toggle.set_visibility(not is_input_only)
        
        if is_import:
            # Import owns its entire pane because setup, live progress, and stop
            # confirmation all live inside the same workspace component.
            workspace = getattr(self, 'import_workspace', None)
            if workspace is None:
                self.right_pane_host.clear()
                with self.right_pane_host:
                    workspace = ImportWorkspace(
                        self.session.draft,
                        self.session.execution,
                        on_changed=self._on_run_draft_changed,
                        on_execute=self._on_execute_command,
                        on_arm_stop=self._on_begin_import_stop_confirmation,
                        on_cancel_stop=self._on_cancel_import_stop_confirmation,
                        on_stop=self._on_request_import_stop,
                    )
                    workspace.build()
                    self.import_workspace = workspace
            else:
                # Reuse the existing import workspace so its log/progress
                # widgets keep their identity across frequent refreshes.
                workspace.refresh(self.session.execution)
            return
        
        self.import_workspace = None
        self.right_pane_host.clear()
        with self.right_pane_host:
            if self.right_pane_view == 'setup':
                self.workspace_host = ui.column().classes('w-full gap-3')
                self._render_workspace()
                return
            # Results and diagnostics belong to the command that produced them,
            # so switching workspaces should not relabel another command's last
            # output as if it came from the newly selected workspace.
            current_command_has_output = (
                self.session.execution.active_command
                == self.session.selected_command
            )
            if self.right_pane_view == 'results':
                if not current_command_has_output:
                    command_label = COMMAND_OPTIONS.get(
                        self.session.selected_command,
                        str(self.session.selected_command).title(),
                    ).lower()
                    ui.label(
                        f'No {command_label} results yet.'
                    ).classes('text-sm text-gray-600')
                elif self.session.execution.error_message:
                    error_text = self.session.execution.error_message
                    with ui.row().classes('w-full items-center gap-2'):
                        ui.button(
                            'Copy Error',
                            on_click=lambda: self._copy_text_to_clipboard(
                                error_text, 'Error'
                            ),
                        ).props('dense').tooltip(
                            'Copy the error message to the clipboard'
                        )
                    ui.label(
                        error_text
                    ).classes('text-negative whitespace-pre-wrap').style(
                        'user-select: text; -webkit-user-select: text'
                    )
                else:
                    render_command_results(
                        self.session.selected_command,
                        self.session.execution.structured_result,
                        self.session.execution.raw_output,
                    )
                return
            if not current_command_has_output:
                command_label = COMMAND_OPTIONS.get(
                    self.session.selected_command,
                    str(self.session.selected_command).title(),
                ).lower()
                ui.label(
                    f'No {command_label} diagnostics yet.'
                ).classes('text-sm text-gray-600')
                return
            diagnostics_text = self.session.execution.diagnostics_output
            if diagnostics_text:
                with ui.row().classes('w-full items-center gap-2'):
                    ui.button(
                        'Copy Diagnostics',
                        on_click=lambda: self._copy_text_to_clipboard(
                            diagnostics_text, 'Diagnostics'
                        ),
                    ).props('dense').tooltip(
                        'Copy the diagnostics output to the clipboard'
                    )
            ui.label(
                diagnostics_text
            ).classes('whitespace-pre-wrap').style(
                'user-select: text; -webkit-user-select: text'
            )
    
    async def _copy_text_to_clipboard(self, text: str, label: str) -> None:
        # Copy on the client so it works in the native (pywebview) window. Try
        # the modern async clipboard API first, then fall back to a hidden
        # textarea + execCommand('copy') where it is unavailable. The script
        # returns whether the copy actually happened, so success is only
        # reported when the client confirms it. json.dumps safely escapes the
        # arbitrary text into a JS string literal. The displayed panes are never
        # touched, so a failure leaves the text on screen to copy by hand.
        script = (
            'const text = ' + json.dumps(text) + ';\n'
            'try {\n'
            '  if (navigator.clipboard && window.isSecureContext) {\n'
            '    await navigator.clipboard.writeText(text);\n'
            '    return true;\n'
            '  }\n'
            '} catch (e) {}\n'
            'try {\n'
            '  const ta = document.createElement("textarea");\n'
            '  ta.value = text;\n'
            '  ta.style.position = "fixed";\n'
            '  ta.style.top = "-1000px";\n'
            '  ta.style.opacity = "0";\n'
            '  document.body.appendChild(ta);\n'
            '  ta.focus();\n'
            '  ta.select();\n'
            '  const ok = document.execCommand("copy");\n'
            '  document.body.removeChild(ta);\n'
            '  return ok;\n'
            '} catch (e) {\n'
            '  return false;\n'
            '}'
        )
        try:
            copied = await ui.run_javascript(script)
        except Exception:
            copied = False
        if copied:
            ui.notify(f'{label} copied to clipboard.')
        else:
            ui.notify(
                f'Could not copy {label.lower()}. '
                'Select the text and copy it manually.',
                color='negative',
            )
    
    # Native close can delete the NiceGUI client while background polling is
    # still unwinding. Treat that specific case as shutdown noise, not a fresh
    # UI error, so the worker cleanup path can finish quietly.
    def _refresh_ui_if_alive(self) -> None:
        try:
            self._refresh_ui()
        except RuntimeError as exc:
            if 'has been deleted' in str(exc):
                return
            raise
    
    def _refresh_ui(self) -> None:
        # Pushing values back into NiceGUI widgets can fire change handlers;
        # suppress those callbacks while the shell is reflecting session state.
        self._refreshing_ui = True
        try:
            self.command_select.value = self.session.selected_command
            self.profile_select.set_options(self._profile_options())
            self.profile_select.value = self.session.selected_profile_id
            
            self.commander_name_input.value = self._display_text(
                self.session.global_state.commander_name
            )
            self.credits_input.value = self._display_text(
                self.session.global_state.credits
            )
            self.max_data_age_input.value = self._display_text(
                self.session.global_state.max_data_age_days
            )
            self.ship_name_input.value = self._display_text(
                self.session.ship_state.ship_name
            )
            self.capacity_input.value = self._display_text(
                self.session.ship_state.capacity
            )
            self.reserved_capacity_input.value = self._display_text(
                self.session.ship_state.reserved_capacity
            )
            self.insurance_input.value = self._display_text(
                self.session.ship_state.insurance
            )
            self.jump_range_full_input.value = self._display_text(
                self.session.ship_state.jump_range_full_ly
            )
            self.jump_range_empty_input.value = self._display_text(
                self.session.ship_state.jump_range_empty_ly
            )
            
            effective_capacity = self.session.ship_state.effective_capacity
            if effective_capacity is None:
                effective_text = 'Effective Capacity:'
            else:
                effective_text = (
                    f'Effective Capacity: {effective_capacity}'
                )
            self.effective_capacity_label.text = effective_text
            
            status = self.session.execution.status.value.capitalize()
            self.status_label.text = f'Status: {status}'
            
            if self.right_pane_toggle.value != self.right_pane_view:
                self.right_pane_toggle.value = self.right_pane_view
            
            if (
                self.session.selected_command == 'import'
                and getattr(self, 'import_workspace', None) is not None
            ):
                # Refresh import in place so log scrollback and progress widgets
                # keep their identity while background polling updates arrive.
                self.import_workspace.refresh(self.session.execution)
            else:
                self._render_right_pane()
        finally:
            self._refreshing_ui = False
    
    def _profile_options(self) -> dict[str, str]:
        return {
            profile.profile_id: profile.ship_name or profile.profile_id
            for profile in self.store.profiles
        }
    
    @staticmethod
    def _display_text(value: Any) -> str:
        return '' if value is None else str(value)
    
    @staticmethod
    def _clean_text(value: Any) -> str | None:
        text = str(value or '').strip()
        return text or None
    
    @staticmethod
    def _has_text(value: Any) -> bool:
        return str(value or '').strip() != ''
    
    def _parse_optional_int(self, value: Any, label: str) -> int | None:
        cleaned = self._clean_text(value)
        if cleaned is None:
            return None
        try:
            parsed = int(cleaned)
        except ValueError:
            ui.notify(f'{label} must be an integer.', color='negative')
            return None
        if parsed < 0:
            ui.notify(f'{label} must be zero or greater.', color='negative')
            return None
        return parsed
    
    def _parse_optional_float(self, value: Any, label: str) -> float | None:
        cleaned = self._clean_text(value)
        if cleaned is None:
            return None
        try:
            parsed = float(cleaned)
        except ValueError:
            ui.notify(f'{label} must be numeric.', color='negative')
            return None
        if parsed < 0:
            ui.notify(f'{label} must be zero or greater.', color='negative')
            return None
        return parsed
