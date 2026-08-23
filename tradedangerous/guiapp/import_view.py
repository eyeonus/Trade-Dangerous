"""Import workspace widgets for long-running TD import operations."""

from typing import Any, Callable
from nicegui import ui
from .profiles import CommandDraft
from .session import ExecutionState, ExecutionStatus

UPDATE_TD_URL = 'https://github.com/bgol/UpdateTD'

IMPORT_HELP_ROWS: tuple[tuple[str, str], ...] = (
    ('All', 'Update everything with the latest dump files.'),
    ('Clean', 'Erase all data and rebuild it from scratch.'),
    ('Optimize', 'Optimise the database after processing (use this occasionally).'),
    (
        'Force',
        'Regenerate selected data even if the source file has not changed since the previous import.',
    ),
    (
        'Solo',
        'Do not download crowdsourced market listings or ship-vendor data. '
        'On first setup, this still creates the database schema and base data. '
        'Solo overrides All and Clean.',
    ),
    ('Purge', 'Remove empty systems that previously had fleet carriers.'),
    (
        '7 Days',
        'Ignore data more than 7 days old during import, then expire old records after import.',
    ),
    (
        'Units',
        'Treat 0-unit listings as zero-priced supply or demand to avoid false availability.',
    ),
)

class ImportWorkspace:
    """Render import options plus live progress using the shared execution state."""
    
    def __init__(
        self,
        draft: CommandDraft,
        execution: ExecutionState,
        *,
        initial_setup: bool,
        on_changed: Callable[[], None],
        on_execute: Callable[[], None],
        on_arm_stop: Callable[[], None],
        on_cancel_stop: Callable[[], None],
        on_stop: Callable[[], None],
    ) -> None:
        self.draft = draft
        self.execution = execution
        self.initial_setup = initial_setup
        self.on_changed = on_changed
        self.on_execute = on_execute
        self.on_arm_stop = on_arm_stop
        self.on_cancel_stop = on_cancel_stop
        self.on_stop = on_stop
    
    def build(self) -> None:
        self.help_dialog = ui.dialog()
        with self.help_dialog:
            with ui.card().classes('gap-2').style(
                'min-width: 52rem; max-width: 90vw;'
            ):
                ui.label('Import help')
                with ui.column().classes('w-full gap-2'):
                    for label, text in IMPORT_HELP_ROWS:
                        with ui.row().classes('w-full items-start gap-4 no-wrap'):
                            ui.label(label).classes('min-w-32 text-weight-medium')
                            ui.label(text).classes(
                                'text-sm text-gray-700 whitespace-pre-wrap'
                            )
                ui.button('Close', on_click=self.help_dialog.close)
        
        self.option_checkboxes = {}
        # `refresh()` updates checkbox values from execution/session state.
        # Suppress the resulting on_change events so refreshes stay read-only.
        self._syncing_checkboxes = False
        
        with ui.column().classes('w-full gap-2').style(
            'padding: 0.25rem 0.5rem 0.5rem 0.25rem;'
        ):
            if self.initial_setup:
                with ui.card().classes('w-full gap-2'):
                    ui.label('Choose your data workflow').classes('text-lg')
                    ui.label(
                        'Trade Dangerous needs an initial Import before its '
                        'database-backed commands are available. Use the '
                        'existing Solo option below to choose a workflow, '
                        'then select Start Import.'
                    ).classes('text-sm text-gray-700 whitespace-pre-wrap')
                    ui.label('Crowdsourced').classes('text-weight-medium')
                    ui.label(
                        'Leave Solo unticked. The normal Trade Dangerous '
                        'Import initialises and populates the database with '
                        'the standard crowdsourced data.'
                    ).classes('text-sm text-gray-700 whitespace-pre-wrap')
                    ui.label('Solo').classes('text-weight-medium')
                    ui.label(
                        'Tick Solo if you maintain your own observed market '
                        'data. Import creates the schema and base data without '
                        'downloading crowdsourced market listings or '
                        'ship-vendor data.'
                    ).classes('text-sm text-gray-700 whitespace-pre-wrap')
                    ui.label(
                        'I maintain my own solo data with EDMC + UpdateTD '
                        '(or another data source).'
                    ).classes('text-sm text-gray-700 whitespace-pre-wrap')
                    ui.link(
                        'EDMC + UpdateTD',
                        UPDATE_TD_URL,
                        new_tab=True,
                    ).classes('text-sm')
                    ui.label(
                        'EDMC + UpdateTD is the recommended and supported '
                        'workflow for ongoing solo data collection. Another '
                        'data source may be used, but is not specifically '
                        'supported by Trade Dangerous.'
                    ).classes('text-sm text-gray-700 whitespace-pre-wrap')
            with ui.row().classes('w-full gap-2 items-center'):
                self.start_button = ui.button(
                    'Start Import',
                    on_click=self.on_execute,
                )
                self.stop_button = ui.button(
                    'Stop',
                    on_click=self.on_arm_stop,
                )
            
            with ui.card().classes('w-full gap-3'):
                self._build_option_group(
                    'Options',
                    [
                        ('All', 'all'),
                        ('Clean', 'clean'),
                        ('Optimize', 'optimize'),
                        ('Force', 'force'),
                        ('Solo', 'solo'),
                        ('Purge', 'purge'),
                        ('7 Days', '7days'),
                        ('Units', 'units'),
                    ],
                    False,
                    include_help=True,
                )
            
            self.stop_confirm_card = ui.card().classes('w-full gap-2')
            with self.stop_confirm_card:
                ui.label('Stop import?')
                ui.label(
                    'Stopping import now may leave your local Trade Dangerous '
                    'database inconsistent. Run import again before using '
                    'the app normally.'
                ).classes('text-sm text-gray-700 whitespace-pre-wrap')
                with ui.row().classes('gap-2'):
                    ui.button('Cancel', on_click=self.on_cancel_stop)
                    ui.button('Stop Import Anyway', on_click=self.on_stop)
            
            with ui.card().classes('w-full gap-1'):
                self.status_label = ui.label('')
                self.parent_label = ui.label('').classes('text-sm text-gray-700')
                self.child_label = ui.label('').classes('text-sm text-gray-700')
                self.stop_requested_label = ui.label(
                    'Stopping import...'
                ).classes('text-warning')
                self.error_label = ui.label('').classes(
                    'text-negative whitespace-pre-wrap'
                )
            
            with ui.card().classes('w-full p-3'):
                with ui.column().classes('w-full').style(
                    'height: 24rem; overflow-y: auto;'
                ):
                    self.log_label = ui.label('').classes(
                        'font-mono text-sm whitespace-pre-wrap'
                    )
        
        self.refresh(self.execution)
    
    def _build_option_group(
        self,
        title: str,
        options: list[tuple[str, str]],
        running: bool,
        include_help: bool = False,
    ) -> None:
        option_rows = [
            options[index:index + 4]
            for index in range(0, len(options), 4)
        ]
        
        with ui.row().classes('w-full items-stretch gap-4 no-wrap'):
            with ui.column().classes('min-w-36 self-stretch gap-0'):
                ui.label(title).classes('text-base text-gray-700')
                if include_help:
                    ui.space()
                    ui.button('Help', on_click=self.help_dialog.open)
            
            with ui.column().classes('w-full gap-y-2'):
                for row_options in option_rows:
                    with ui.row().classes('w-full gap-x-6 items-center no-wrap'):
                        for label, key in row_options:
                            checkbox = ui.checkbox(
                                label,
                                value=self._bool_value(key),
                                on_change=lambda event, opt=key: self._set_bool(
                                    opt,
                                    event.value,
                                ),
                            ).classes('min-w-40')
                            tooltip_text = next(
                                (
                                    text
                                    for help_label, text in IMPORT_HELP_ROWS
                                    if help_label == label
                                ),
                                '',
                            )
                            if tooltip_text:
                                checkbox.tooltip(tooltip_text)
                            self.option_checkboxes[key] = checkbox
                            if running:
                                checkbox.disable()
    
    def _set_bool(self, key: str, value: Any) -> None:
        if self._syncing_checkboxes:
            return
        
        if value:
            self.draft.main_values[key] = True
        else:
            self.draft.main_values.pop(key, None)
        self.on_changed()
    
    def _bool_value(self, key: str) -> bool:
        return bool(self.draft.main_values.get(key))
    
    def refresh(self, execution: ExecutionState) -> None:
        self.execution = execution
        running = execution.status == ExecutionStatus.RUNNING
        
        self._syncing_checkboxes = True
        try:
            for key, checkbox in self.option_checkboxes.items():
                checkbox.value = self._bool_value(key)
                checkbox.update()
                # Freeze the option set while an import is in flight so the
                # saved draft continues to match the running command.
                if running:
                    checkbox.disable()
                else:
                    checkbox.enable()
        finally:
            self._syncing_checkboxes = False
        
        if running:
            self.start_button.disable()
            self.stop_button.enable()
        else:
            self.start_button.enable()
            self.stop_button.disable()
        
        self.stop_confirm_card.set_visibility(
            running and execution.import_stop_confirming
        )
        
        self.status_label.text = execution.import_status_text or (
            f'Import status: {execution.status.value.capitalize()}'
        )
        self._set_optional_label(
            self.parent_label,
            self._progress_text(
                execution.import_parent_label,
                execution.import_parent_value,
                execution.import_parent_total,
            ),
        )
        self._set_optional_label(
            self.child_label,
            self._progress_text(
                execution.import_child_label,
                execution.import_child_value,
                execution.import_child_total,
            ),
        )
        self.stop_requested_label.set_visibility(
            execution.import_stop_requested
        )
        self._set_optional_label(
            self.error_label,
            execution.error_message or '',
        )
        self.log_label.text = self._log_text(execution)
    
    @staticmethod
    def _set_optional_label(label: Any, text: str) -> None:
        label.text = text
        label.set_visibility(bool(text))
    
    @staticmethod
    def _log_text(execution: ExecutionState) -> str:
        log_text = '\n'.join(execution.import_log_lines)
        if log_text:
            return log_text
        # Fall back to buffered output for failures or non-streaming code paths.
        return '\n'.join(
            part for part in (
                execution.diagnostics_output,
                execution.raw_output,
            ) if part
        ) or 'No import activity yet.'
    
    @staticmethod
    def _progress_text(
        label: str | None,
        value: int | None,
        total: int | None,
    ) -> str:
        if not label:
            return ''
        if value is None:
            return label
        if total is None:
            return f'{label}: {value}'
        return f'{label}: {value}/{total}'
