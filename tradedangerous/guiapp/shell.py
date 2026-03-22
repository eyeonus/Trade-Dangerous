"""Top-level NiceGUI shell for the new Trade Dangerous GUI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nicegui import run, ui

from .profiles import GuiStore, save_gui_store
from .run_view import RunWorkspace
from .buy_sell_view import BuySellWorkspace
from .trade_view import TradeWorkspace
from .local_view import LocalWorkspace
from .market_view import MarketWorkspace
from .rares_view import RaresWorkspace
from .session import ExecutionStatus, SessionState
from .td_exec import GuiCommandRequest, TdExecutor

COMMAND_OPTIONS: dict[str, str] = {
    'run': 'Run',
    'buy': 'Buy',
    'sell': 'Sell',
    'trade': 'Trade',
    'local': 'Local',
    'market': 'Market',
    'rares': 'Rares',
    'nav': 'Nav',
    'olddata': 'Old Data',
    'import': 'Import',
    'settings': 'Settings',
}


class AppShell:
    """Own the long-lived widgets and coordinate session/store updates."""

    def __init__(self, store: GuiStore) -> None:
        self.store = store
        self.session = SessionState.from_store(store)
        self.executor = TdExecutor()

        self.command_select = None
        self.status_label = None
        self.profile_select = None
        self.ship_name_input = None
        self.commander_name_input = None
        self.credits_input = None
        self.max_data_age_input = None
        self.capacity_input = None
        self.reserved_capacity_input = None
        self.effective_capacity_label = None
        self.jump_range_full_input = None
        self.jump_range_empty_input = None
        self.workspace_host = None
        self.right_pane_toggle = None
        self.right_pane_host = None
        self.right_pane_view = 'setup'
        self.root_container = None
        self.body_query = None

    def build(self) -> None:
        ui.add_head_html(
            f'<style>\n{self._theme_css_text()}\n</style>'
        )

        self.body_query = ui.query('body')
        self.root_container = ui.column().classes(
            'w-full gap-2 p-4 td-theme-default'
        )
        with self.root_container:
            self._build_top_bar()
            with ui.splitter(value=27).classes('w-full') as splitter:
                with splitter.before:
                    self._build_left_pane()
                with splitter.after:
                    self._build_right_pane()

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
        with ui.row().classes('w-full items-center gap-4'):
            self.command_select = ui.select(
                COMMAND_OPTIONS,
                value=self.session.selected_command,
                label='Command',
                on_change=self._on_command_changed,
            ).classes('min-w-40')
            self.status_label = ui.label('Status: Idle')

    def _build_left_pane(self) -> None:
        with ui.column().classes('w-full gap-3 pr-2 box-border').style(
            'min-width: 23rem;'
        ):
            ui.label('Commander Baseline')
            self.commander_name_input = ui.input(
                'Commander Name',
                on_change=self._on_global_changed,
            ).classes('w-full')
            self.credits_input = ui.input(
                'Credits',
                on_change=self._on_global_changed,
            ).classes('w-full')
            self.max_data_age_input = ui.input(
                'Max data age (days)',
                on_change=self._on_global_changed,
            ).classes('w-full')

            ui.separator()
            ui.label('Ship Profile')
            self.profile_select = ui.select(
                self._profile_options(),
                value=self.session.selected_profile_id,
                label='Ship Profile',
                on_change=self._on_profile_changed,
            ).classes('w-full')
            self.ship_name_input = ui.input(
                'Ship Name',
                on_change=self._on_ship_changed,
            ).classes('w-full')
            self.capacity_input = ui.input(
                'Capacity',
                on_change=self._on_ship_changed,
            ).classes('w-full')
            self.reserved_capacity_input = ui.input(
                'Reserved Capacity',
                on_change=self._on_ship_changed,
            ).classes('w-full')
            self.effective_capacity_label = ui.label('Effective Capacity:')
            self.jump_range_full_input = ui.input(
                'Jump Range (Full)',
                on_change=self._on_ship_changed,
            ).classes('w-full')
            self.jump_range_empty_input = ui.input(
                'Jump Range (Empty)',
                on_change=self._on_ship_changed,
            ).classes('w-full')

            ui.separator()
            with ui.row().classes('w-full gap-2'):
                ui.button('New', on_click=self._on_new_profile)
                ui.button('Save', on_click=self._on_save_profile)
                ui.button('Revert', on_click=self._on_revert_profile)
                
    def _build_right_pane(self) -> None:
        with ui.column().classes('w-full gap-2 pl-2'):
            self.right_pane_toggle = ui.toggle(
                {
                    'setup': 'Input',
                    'results': 'Results',
                    'diagnostics': 'Diagnostics',
                },
                value=self.right_pane_view,
                on_change=self._on_right_pane_view_changed,
            ).classes('self-start')
            self.right_pane_host = ui.column().classes('w-full gap-3')

    def _on_right_pane_view_changed(self, event: Any) -> None:
        value = getattr(event, 'value', None)
        if value is None:
            return
        self.right_pane_view = str(value)
        self._refresh_ui()

    def _on_command_changed(self, event: Any) -> None:
        value = getattr(event, 'value', None)
        if value is None:
            return
        self.session.set_command(self.store, str(value))
        save_gui_store(self.store)
        self._refresh_ui()

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
        save_gui_store(self.store)

    def _selected_theme(self) -> str:
        value = self.store.layout.get('theme')
        if value in {'default', 'elite'}:
            return str(value)
        return 'default'

    def _on_theme_changed(self, theme_name: str) -> None:
        theme = str(theme_name)
        if theme not in {'default', 'elite'}:
            return
        self.store.layout['theme'] = theme
        save_gui_store(self.store)
        self._apply_theme()
        self._refresh_ui()

    def _on_begin_import_stop_confirmation(self) -> None:
        from .import_runtime import begin_import_stop_confirmation

        if begin_import_stop_confirmation(session=self.session):
            self._refresh_ui()

    def _on_cancel_import_stop_confirmation(self) -> None:
        from .import_runtime import cancel_import_stop_confirmation

        if cancel_import_stop_confirmation(session=self.session):
            self._refresh_ui()

    def _on_request_import_stop(self) -> None:
        from .import_runtime import request_import_stop

        if request_import_stop(session=self.session):
            self._refresh_ui()
            return

        ui.notify('No import is currently running.', color='warning')

    def _on_copy_from_profile(self) -> None:
        # Copy the effective cargo capacity rather than raw capacity so the
        # draft sees the same usable tonnage that execution will later use.
        context = {
            'capacity': self.session.ship_state.effective_capacity,
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
        from .import_runtime import (
            build_import_request,
            consume_one_shot_import_flags,
            run_import_execution,
        )

        if self.session.selected_command == 'settings':
            ui.notify(
                'Settings is a GUI workspace and cannot be executed.',
                color='warning',
            )
            return

        if self.session.selected_command == 'import':
            # Import runs through a separate polling loop so progress can stream
            # back into the session while the blocking worker is active.
            request = build_import_request(draft=self.session.draft)
            if consume_one_shot_import_flags(draft=self.session.draft):
                save_gui_store(self.store)
                self._refresh_ui()
            await run_import_execution(
                session=self.session,
                executor=self.executor,
                request=request,
                refresh_ui=self._refresh_ui,
            )
            return

        if not self._capture_global_inputs():
            return
        if not self._capture_ship_inputs():
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
                'jump_range_full_ly': self.session.ship_state.jump_range_full_ly,
                'jump_range_empty_ly': self.session.ship_state.jump_range_empty_ly,
            },
        )

        # Clear the previous result immediately to avoid showing stale output
        # while the worker thread is still spinning up.
        self.session.set_execution(
            status=ExecutionStatus.RUNNING,
            active_command=self.session.selected_command,
            error_message=None,
            raw_output='',
            diagnostics_output='',
            structured_result=None,
        )
        self._refresh_ui()

        try:
            result = await run.io_bound(self.executor.execute, request)
        except Exception as exc:
            self.session.set_execution(
                status=ExecutionStatus.FAILED,
                active_command=self.session.selected_command,
                error_message=str(exc),
                raw_output='',
                diagnostics_output=repr(exc),
                structured_result=None,
            )
            self._refresh_ui()
            return

        status = ExecutionStatus.SUCCEEDED if result.ok else ExecutionStatus.FAILED
        self.session.set_execution(
            status=status,
            active_command=result.command,
            error_message=result.error_message,
            raw_output=result.raw_output,
            diagnostics_output=result.diagnostics_output,
            structured_result=result.structured_result,
        )
        self._refresh_ui()
        
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
        self.session.ship_state.jump_range_full_ly = jump_range_full
        self.session.ship_state.jump_range_empty_ly = jump_range_empty
        self.session.mark_ship_dirty()
        return True

    def _render_workspace(self) -> None:
        self.workspace_host.clear()
        with self.workspace_host:
            if self.session.selected_command == 'run':
                workspace = RunWorkspace(
                    self.session.draft,
                    on_changed=self._on_run_draft_changed,
                    on_execute=self._on_execute_command,
                    on_copy_from_profile=self._on_copy_from_profile,
                )
                workspace.build()
            elif self.session.selected_command in {'buy', 'sell'}:
                workspace = BuySellWorkspace(
                    self.session.selected_command,
                    self.session.draft,
                    on_changed=self._on_run_draft_changed,
                    on_execute=self._on_execute_command,
                    on_copy_from_profile=self._on_copy_from_profile,
                )
                workspace.build()
            elif self.session.selected_command == 'trade':
                workspace = TradeWorkspace(
                    self.session.draft,
                    on_changed=self._on_run_draft_changed,
                    on_execute=self._on_execute_command,
                )
                workspace.build()
            elif self.session.selected_command == 'local':
                workspace = LocalWorkspace(
                    self.session.draft,
                    on_changed=self._on_run_draft_changed,
                    on_execute=self._on_execute_command,
                )
                workspace.build()
            elif self.session.selected_command == 'market':
                workspace = MarketWorkspace(
                    self.session.draft,
                    on_changed=self._on_run_draft_changed,
                    on_execute=self._on_execute_command,
                )
                workspace.build()
            elif self.session.selected_command == 'rares':
                workspace = RaresWorkspace(
                    self.session.draft,
                    on_changed=self._on_run_draft_changed,
                    on_execute=self._on_execute_command,
                )
                workspace.build()
            elif self.session.selected_command == 'settings':
                from .settings_view import SettingsWorkspace

                workspace = SettingsWorkspace(
                    selected_theme=self._selected_theme(),
                    on_theme_changed=self._on_theme_changed,
                )
                workspace.build()
            else:
                ui.label(
                    f'{self.session.selected_command} workspace '
                    'is not wired yet.'
                )    
    def _render_right_pane(self) -> None:
        from .import_view import ImportWorkspace
        from .results_view import render_command_results
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
            if self.right_pane_view == 'results':
                if self.session.execution.error_message:
                    ui.label(
                        self.session.execution.error_message
                    ).classes('text-negative whitespace-pre-wrap')
                else:
                    render_command_results(
                        self.session.selected_command,
                        self.session.execution.structured_result,
                        self.session.execution.raw_output,
                    )
                return
            ui.label(
                self.session.execution.diagnostics_output
            ).classes('whitespace-pre-wrap')
    
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
