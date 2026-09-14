import asyncio
from queue import Empty
from types import SimpleNamespace

import tradedangerous.guiapp.import_runtime as import_runtime
import tradedangerous.guiapp.shell as shell_module
from tradedangerous.guiapp.import_runtime import (
    ImportCommandProcess,
    ImportMonitor,
    ImportWorkerMessage,
    _apply_worker_message,
    begin_import_stop_confirmation,
    build_import_request,
    cancel_import_stop_confirmation,
    request_import_stop,
    run_import_execution,
)
from tradedangerous.guiapp.profiles import CommandDraft, GuiStore
from tradedangerous.guiapp.session import ExecutionStatus, SessionState
from tradedangerous.guiapp.shell import AppShell
from tradedangerous.guiapp.td_exec import GuiCommandResult

class _Runner:
    def __init__(self):
        self.messages = []
        self.active = True
    
    def is_active(self):
        return self.active
    
    def terminate(self, message):
        self.messages.append(message)
        self.active = False

class _Queue:
    def __init__(self, *messages):
        self._messages = list(messages)
    
    def get_nowait(self):
        if not self._messages:
            raise Empty
        return self._messages.pop(0)

class _Process:
    def __init__(self, *, alive):
        self._alive = alive
    
    def is_alive(self):
        return self._alive
    
    def join(self, timeout=None):
        return None

class _WindowCloseState:
    def __init__(self):
        self.history = []
    
    def mark_running(self, *, kind, command, pid):
        self.history.append(('mark_running', kind, command, pid))
    
    def clear(self):
        self.history.append(('clear',))

class _ImportRunner:
    def __init__(self):
        self.command = 'import'
        self.pid = 4321
        self.termination_message = None
        self._poll_count = 0
    
    def poll(self):
        self._poll_count += 1
        if self._poll_count == 1:
            return [ImportWorkerMessage(kind='finished')], None
        return [], GuiCommandResult(
            command='import',
            ok=True,
            diagnostics_output='NOTE: Import completed',
        )
    
    def close(self):
        return None

def _run_import_mode_case(
    monkeypatch,
    *,
    data_mode,
    request_solo,
    final_status,
    draft_solo_after_start=None,
):
    store = GuiStore.default()
    store.data_mode = data_mode
    store.selected_command = 'import'
    store.drafts['import'] = CommandDraft(
        main_values={'solo': True} if request_solo else {},
    )
    session = SessionState.from_store(store)
    shell = AppShell.__new__(AppShell)
    shell.store = store
    shell.session = session
    shell.window_close_state = None
    executed_requests = []
    saved_modes = []

    async def _fake_run_import_execution(
        *,
        session,
        request,
        refresh_ui,
        window_close_state,
    ):
        executed_requests.append(request)
        if draft_solo_after_start is True:
            session.draft.main_values['solo'] = True
        elif draft_solo_after_start is False:
            session.draft.main_values.pop('solo', None)
        session.set_execution(
            status=final_status,
            active_command='import',
        )

    monkeypatch.setattr(
        shell_module,
        'run_import_execution',
        _fake_run_import_execution,
    )
    monkeypatch.setattr(
        shell_module,
        'save_gui_store',
        lambda current_store: saved_modes.append(current_store.data_mode),
    )

    asyncio.run(shell._on_execute_command())

    return store, executed_requests[0], saved_modes

def test_build_import_request_copies_draft_fields():
    draft = CommandDraft(
        main_values={'all': True},
        advanced_values={'force': True},
        context_overrides={'source': 'gui'},
    )
    
    request = build_import_request(draft=draft)
    
    assert request.command == 'import'
    assert request.main_values == {'all': True}
    assert request.advanced_values == {'force': True}
    assert request.context_overrides == {'source': 'gui'}
    assert request.global_values == {}
    assert request.ship_profile_values == {}

def test_import_runtime_stop_confirmation_and_stop_request_flags():
    session = SessionState.from_store(GuiStore.default())
    runner = _Runner()
    session.active_import_runner = runner
    
    assert begin_import_stop_confirmation(session=session) is True
    assert session.execution.import_stop_confirming is True
    
    assert cancel_import_stop_confirmation(session=session) is True
    assert session.execution.import_stop_confirming is False
    
    assert request_import_stop(session=session, reason='Stop now') is True
    assert session.execution.import_status_text == 'Stopping import...'
    assert session.execution.import_stop_requested is True
    assert session.execution.import_stop_confirming is False
    assert runner.messages == ['Stop now']

def test_import_runtime_worker_message_updates_monitor_state():
    monitor = ImportMonitor()
    
    _apply_worker_message(monitor=monitor, message=ImportWorkerMessage(kind='log_line', payload='line one'))
    _apply_worker_message(monitor=monitor, message=ImportWorkerMessage(kind='status_text', payload='Working'))
    _apply_worker_message(monitor=monitor, message=ImportWorkerMessage(kind='parent_progress', payload=('Tables', 1, 3)))
    _apply_worker_message(monitor=monitor, message=ImportWorkerMessage(kind='child_progress', payload=('Rows', 5, 10)))
    _apply_worker_message(monitor=monitor, message=ImportWorkerMessage(kind='finished'))
    
    snapshot = monitor.snapshot()
    
    assert snapshot.log_lines == ['line one']
    assert snapshot.status_text == 'Working'
    assert snapshot.parent_label == 'Tables'
    assert snapshot.parent_value == 1
    assert snapshot.parent_total == 3
    assert snapshot.child_label == 'Rows'
    assert snapshot.child_value == 5
    assert snapshot.child_total == 10
    assert snapshot.finished is True

def test_import_command_process_finished_message_stops_busy_state_without_losing_message():
    runner = ImportCommandProcess.__new__(ImportCommandProcess)
    runner.command = 'import'
    runner._event_queue = _Queue(
        ImportWorkerMessage(kind='finished'),
    )
    runner._process = _Process(alive=True)
    runner._pending_messages = []
    runner._finished = False
    runner._result = None
    runner._result_consumed = False
    runner._termination_message = None
    
    assert runner.is_active() is False
    
    messages, result = runner.poll()
    
    assert [message.kind for message in messages] == ['finished']
    assert result is None

def test_run_import_execution_clears_native_close_state_on_finished_before_result(
    monkeypatch,
):
    session = SessionState.from_store(GuiStore.default())
    runner = _ImportRunner()
    window_close_state = _WindowCloseState()
    
    async def _fake_sleep(_delay):
        return None
    
    monkeypatch.setattr(
        import_runtime.ImportCommandProcess,
        'launch',
        classmethod(lambda cls, request: runner),
    )
    monkeypatch.setattr(import_runtime.asyncio, 'sleep', _fake_sleep)
    
    asyncio.run(
        run_import_execution(
            session=session,
            request=SimpleNamespace(command='import'),
            refresh_ui=lambda: None,
            window_close_state=window_close_state,
        )
    )
    
    assert session.execution.status is ExecutionStatus.SUCCEEDED
    assert window_close_state.history == [
        ('mark_running', 'import', 'import', 4321),
        ('clear',),
    ]

def test_initial_successful_normal_import_establishes_crowdsourced(monkeypatch):
    store, request, saved_modes = _run_import_mode_case(
        monkeypatch,
        data_mode=None,
        request_solo=False,
        final_status=ExecutionStatus.SUCCEEDED,
    )

    assert request.main_values.get('solo') is None
    assert store.data_mode == 'crowdsourced'
    assert saved_modes == ['crowdsourced']

def test_initial_successful_solo_import_establishes_solo(monkeypatch):
    store, request, saved_modes = _run_import_mode_case(
        monkeypatch,
        data_mode=None,
        request_solo=True,
        final_status=ExecutionStatus.SUCCEEDED,
    )

    assert request.main_values['solo'] is True
    assert store.data_mode == 'solo'
    assert saved_modes == ['solo']

def test_initial_failed_import_leaves_data_mode_unset(monkeypatch):
    store, _request, saved_modes = _run_import_mode_case(
        monkeypatch,
        data_mode=None,
        request_solo=False,
        final_status=ExecutionStatus.FAILED,
    )

    assert store.data_mode is None
    assert saved_modes == []

def test_later_solo_import_does_not_change_crowdsourced_mode(monkeypatch):
    store, _request, saved_modes = _run_import_mode_case(
        monkeypatch,
        data_mode='crowdsourced',
        request_solo=True,
        final_status=ExecutionStatus.SUCCEEDED,
    )

    assert store.data_mode == 'crowdsourced'
    assert saved_modes == []

def test_later_normal_import_does_not_change_solo_mode(monkeypatch):
    store, _request, saved_modes = _run_import_mode_case(
        monkeypatch,
        data_mode='solo',
        request_solo=False,
        final_status=ExecutionStatus.SUCCEEDED,
    )

    assert store.data_mode == 'solo'
    assert saved_modes == []

def test_initial_import_mode_uses_request_snapshot(monkeypatch):
    store, request, saved_modes = _run_import_mode_case(
        monkeypatch,
        data_mode=None,
        request_solo=False,
        final_status=ExecutionStatus.SUCCEEDED,
        draft_solo_after_start=True,
    )

    assert request.main_values.get('solo') is None
    assert store.drafts['import'].main_values['solo'] is True
    assert store.data_mode == 'crowdsourced'
    assert saved_modes == ['crowdsourced']
