"""Runtime helpers for import progress streaming and killable subprocess execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import multiprocessing
from queue import Empty
from threading import Lock
from typing import Any, Callable, Protocol


@dataclass(slots=True)
class ImportProgressState:
    status_text: str = ''
    log_lines: list[str] = field(default_factory=list)
    parent_label: str | None = None
    parent_value: int | None = None
    parent_total: int | None = None
    child_label: str | None = None
    child_value: int | None = None
    child_total: int | None = None
    stop_requested: bool = False
    finished: bool = False


class ImportMonitorProtocol(Protocol):
    def append_log(self, line: str) -> None:
        ...

    def set_status(self, text: str) -> None:
        ...

    def set_parent_progress(
        self,
        label: str | None,
        value: int | None,
        total: int | None,
    ) -> None:
        ...

    def set_child_progress(
        self,
        label: str | None,
        value: int | None,
        total: int | None,
    ) -> None:
        ...

    def request_stop(self) -> None:
        ...

    def stop_requested(self) -> bool:
        ...

    def finish(self) -> None:
        ...

    def snapshot(self) -> ImportProgressState:
        ...


class ImportMonitor:
    """Thread-safe local progress store mirrored into the import pane."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._state = ImportProgressState()

    def append_log(self, line: str) -> None:
        text = str(line).rstrip()
        if not text:
            return
        with self._lock:
            self._state.log_lines.append(text)

    def set_status(self, text: str) -> None:
        with self._lock:
            self._state.status_text = str(text)

    def set_parent_progress(
        self,
        label: str | None,
        value: int | None,
        total: int | None,
    ) -> None:
        with self._lock:
            self._state.parent_label = label
            self._state.parent_value = value
            self._state.parent_total = total

    def set_child_progress(
        self,
        label: str | None,
        value: int | None,
        total: int | None,
    ) -> None:
        with self._lock:
            self._state.child_label = label
            self._state.child_value = value
            self._state.child_total = total

    def request_stop(self) -> None:
        with self._lock:
            self._state.stop_requested = True

    def stop_requested(self) -> bool:
        with self._lock:
            return self._state.stop_requested

    def finish(self) -> None:
        with self._lock:
            self._state.finished = True

    def snapshot(self) -> ImportProgressState:
        with self._lock:
            return ImportProgressState(
                status_text=self._state.status_text,
                log_lines=list(self._state.log_lines),
                parent_label=self._state.parent_label,
                parent_value=self._state.parent_value,
                parent_total=self._state.parent_total,
                child_label=self._state.child_label,
                child_value=self._state.child_value,
                child_total=self._state.child_total,
                stop_requested=self._state.stop_requested,
                finished=self._state.finished,
            )


@dataclass(slots=True)
class ImportWorkerMessage:
    kind: str
    payload: Any = None


class ImportProcessMonitor:
    """Child-process adapter that forwards import progress events to the GUI."""

    def __init__(self, event_queue: Any) -> None:
        self._event_queue = event_queue

    def append_log(self, line: str) -> None:
        text = str(line).rstrip()
        if text:
            self._send('log_line', text)

    def set_status(self, text: str) -> None:
        self._send('status_text', str(text))

    def set_parent_progress(
        self,
        label: str | None,
        value: int | None,
        total: int | None,
    ) -> None:
        self._send('parent_progress', (label, value, total))

    def set_child_progress(
        self,
        label: str | None,
        value: int | None,
        total: int | None,
    ) -> None:
        self._send('child_progress', (label, value, total))

    def request_stop(self) -> None:
        # Import termination is now handled by killing the subprocess directly.
        return None

    def stop_requested(self) -> bool:
        return False

    def finish(self) -> None:
        self._send('finished')

    def snapshot(self) -> ImportProgressState:
        return ImportProgressState()

    def _send(self, kind: str, payload: Any = None) -> None:
        self._event_queue.put(ImportWorkerMessage(kind=kind, payload=payload))


# Import keeps its own process wrapper because it has an event queue as well as
# a final result payload. Ordinary commands only need one result pipe; import
# needs streaming progress events plus the same hard-stop semantics.
class ImportCommandProcess:
    """Run import in a child process so stop/switch can terminate it immediately."""

    def __init__(self, request: Any) -> None:
        # Match the ordinary command runner: explicit spawn keeps behaviour
        # consistent on Windows, in frozen builds, and under NiceGUI native mode.
        context = multiprocessing.get_context('spawn')
        self.command = request.command
        self._event_queue = context.Queue()
        self._process = context.Process(
            target=_execute_import_request_worker,
            args=(request, self._event_queue),
            name='td-gui-import',
        )
        self._pending_messages: list[ImportWorkerMessage] = []
        self._finished = False
        self._result = None
        self._result_consumed = False
        self._termination_message: str | None = None

    @classmethod
    def launch(cls, request: Any) -> 'ImportCommandProcess':
        runner = cls(request)
        runner.start()
        return runner

    @property
    def termination_message(self) -> str | None:
        return self._termination_message

    @property
    def pid(self) -> int | None:
        return self._process.pid

    def start(self) -> None:
        self._process.start()

    def is_active(self) -> bool:
        self._drain_messages()
        return (
            not self._result_consumed
            and self._result is None
            and not self._finished
            and self._process.is_alive()
        )

    # Drain queued progress messages first, then surface the final GUI result
    # once the worker sends it or exits. The parent never blocks on the queue;
    # it stays in the asyncio poll loop so the import pane can keep refreshing.
    def poll(self) -> tuple[list[ImportWorkerMessage], Any | None]:
        self._drain_messages()
        messages = list(self._pending_messages)
        self._pending_messages.clear()

        if self._result_consumed:
            return messages, None
        if self._result is not None:
            self._result_consumed = True
            self._process.join(timeout=0.1)
            return messages, self._result
        if self._process.is_alive():
            return messages, None

        self._result_consumed = True
        self._process.join(timeout=0.1)
        return messages, self._build_process_exit_result()

    def _drain_messages(self) -> None:
        while True:
            try:
                message = self._event_queue.get_nowait()
            except Empty:
                break
            if message.kind == 'result':
                self._result = message.payload
                continue
            if message.kind == 'finished':
                self._finished = True
            self._pending_messages.append(message)

    def terminate(self, message: str) -> None:
        if self._result_consumed:
            return
        self._termination_message = message
        if self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=0.2)

    def close(self) -> None:
        self._event_queue.close()
        self._event_queue.join_thread()
        if hasattr(self._process, 'close'):
            try:
                self._process.close()
            except ValueError:
                pass

    def _build_process_exit_result(self) -> Any:
        from .td_exec import GuiCommandResult

        if self._termination_message:
            return GuiCommandResult(
                command=self.command,
                ok=False,
                error_message=self._termination_message,
                diagnostics_output=self._termination_message,
            )

        exit_code = self._process.exitcode
        return GuiCommandResult(
            command=self.command,
            ok=False,
            error_message='Import stopped before returning a result.',
            diagnostics_output=(
                'The import worker exited before returning a GUI result '
                f'payload (exit code {exit_code}).'
            ),
        )


def build_import_request(*, draft: Any) -> Any:
    from .td_exec import GuiCommandRequest

    return GuiCommandRequest(
        command='import',
        main_values=dict(draft.main_values),
        advanced_values=dict(draft.advanced_values),
        context_overrides=dict(draft.context_overrides),
        global_values={},
        ship_profile_values={},
    )


def consume_one_shot_import_flags(*, draft: Any) -> bool:
    changed = False

    for key in ('clean', 'optimize', 'force'):
        if draft.main_values.pop(key, None):
            changed = True

    return changed


def _apply_snapshot_to_session(
    *,
    session: Any,
    status: Any,
    active_command: str | None,
    error_message: str | None,
    raw_output: str,
    diagnostics_output: str,
    structured_result: Any,
    snapshot: ImportProgressState,
) -> None:
    # Import progress is mirrored into the shared execution state so the right
    # pane keeps one rendering path for both ordinary commands and import.
    session.set_execution(
        status=status,
        active_command=active_command,
        error_message=error_message,
        raw_output=raw_output,
        diagnostics_output=diagnostics_output,
        structured_result=structured_result,
        import_log_lines=snapshot.log_lines,
        import_status_text=snapshot.status_text,
        import_parent_label=snapshot.parent_label,
        import_parent_value=snapshot.parent_value,
        import_parent_total=snapshot.parent_total,
        import_child_label=snapshot.child_label,
        import_child_value=snapshot.child_value,
        import_child_total=snapshot.child_total,
        import_stop_requested=snapshot.stop_requested,
        # Stop confirmation is purely local UI state, so preserve the current
        # shell value instead of expecting the worker process to track it.
        import_stop_confirming=session.execution.import_stop_confirming,
    )


def _apply_worker_message(
    *,
    monitor: ImportMonitor,
    message: ImportWorkerMessage,
) -> None:
    if message.kind == 'log_line':
        monitor.append_log(str(message.payload))
        return
    if message.kind == 'status_text':
        monitor.set_status(str(message.payload))
        return
    if message.kind == 'parent_progress':
        label, value, total = message.payload
        monitor.set_parent_progress(label, value, total)
        return
    if message.kind == 'child_progress':
        label, value, total = message.payload
        monitor.set_child_progress(label, value, total)
        return
    if message.kind == 'finished':
        monitor.finish()


# Import execution mirrors the ordinary-command pattern at a higher level:
# launch child process, poll it from asyncio, fold progress events into the
# session snapshot, and let stop/close terminate the worker immediately.
async def run_import_execution(
    *,
    session: Any,
    request: Any,
    refresh_ui: Callable[[], None],
    window_close_state: Any = None,
) -> None:
    from .session import ExecutionStatus

    monitor = ImportMonitor()
    monitor.set_status('Starting import...')

    try:
        runner = ImportCommandProcess.launch(request)
    except Exception as exc:
        _apply_snapshot_to_session(
            session=session,
            status=ExecutionStatus.FAILED,
            active_command=request.command,
            error_message=str(exc),
            raw_output='',
            diagnostics_output=repr(exc),
            structured_result=None,
            snapshot=monitor.snapshot(),
        )
        refresh_ui()
        return

    close_state_marked = False

    def clear_window_close_state() -> None:
        nonlocal close_state_marked
        if not close_state_marked or window_close_state is None:
            return
        window_close_state.clear()
        close_state_marked = False

    session.active_import_runner = runner
    if window_close_state is not None:
        window_close_state.mark_running(
            kind='import',
            command=request.command,
            pid=runner.pid,
        )
        close_state_marked = True
    _apply_snapshot_to_session(
        session=session,
        status=ExecutionStatus.RUNNING,
        active_command=request.command,
        error_message=None,
        raw_output='',
        diagnostics_output='',
        structured_result=None,
        snapshot=monitor.snapshot(),
    )
    refresh_ui()

    try:
        result = None
        while result is None:
            # Import progress arrives as small event messages so the GUI can
            # reassure the user that work is still happening without waiting
            # for the final result payload.
            messages, result = runner.poll()
            for message in messages:
                _apply_worker_message(monitor=monitor, message=message)

            snapshot = monitor.snapshot()
            if snapshot.finished:
                clear_window_close_state()
            if result is None:
                if runner.termination_message is not None:
                    snapshot.status_text = 'Stopping import...'
                    snapshot.stop_requested = True
                _apply_snapshot_to_session(
                    session=session,
                    status=ExecutionStatus.RUNNING,
                    active_command=request.command,
                    error_message=None,
                    raw_output='',
                    diagnostics_output='',
                    structured_result=None,
                    snapshot=snapshot,
                )
                refresh_ui()
                await asyncio.sleep(0.1)
                continue

            clear_window_close_state()
            if runner.termination_message is not None:
                snapshot.status_text = 'Import stopped.'
                snapshot.stop_requested = False
            status = (
                ExecutionStatus.SUCCEEDED
                if result.ok
                else ExecutionStatus.FAILED
            )
            _apply_snapshot_to_session(
                session=session,
                status=status,
                active_command=result.command,
                error_message=result.error_message,
                raw_output=result.raw_output,
                diagnostics_output=result.diagnostics_output,
                structured_result=result.structured_result,
                snapshot=snapshot,
            )
            refresh_ui()
    finally:
        if session.active_import_runner is runner:
            session.active_import_runner = None
        clear_window_close_state()
        runner.close()


def is_import_running(*, session: Any) -> bool:
    runner = getattr(session, 'active_import_runner', None)
    return runner is not None and runner.is_active()


def begin_import_stop_confirmation(*, session: Any) -> bool:
    if not is_import_running(session=session):
        return False

    session.execution.import_stop_confirming = True
    return True


def cancel_import_stop_confirmation(*, session: Any) -> bool:
    if not is_import_running(session=session):
        return False

    session.execution.import_stop_confirming = False
    return True


def request_import_stop(
    *,
    session: Any,
    reason: str | None = None,
) -> bool:
    runner = getattr(session, 'active_import_runner', None)
    if runner is None or not runner.is_active():
        return False

    session.execution.import_stop_confirming = False
    session.execution.import_status_text = 'Stopping import...'
    session.execution.import_stop_requested = True
    runner.terminate(
        reason
        or (
            'Import was stopped by user. Your local Trade Dangerous database '
            'may be inconsistent until import is run again.'
        )
    )
    return True


# Child-side import entry point. It attaches the process-backed monitor so deep
# import code can emit progress/log updates without knowing anything about the
# GUI, then returns the final GuiCommandResult through the same queue.
def _execute_import_request_worker(request: Any, event_queue: Any) -> None:
    from .td_exec import GuiCommandResult, TdExecutor

    request.import_monitor = ImportProcessMonitor(event_queue)
    try:
        result = TdExecutor().execute(request)
    except Exception as exc:
        result = GuiCommandResult(
            command=request.command,
            ok=False,
            error_message=str(exc),
            diagnostics_output=repr(exc),
        )

    event_queue.put(ImportWorkerMessage(kind='result', payload=result))
