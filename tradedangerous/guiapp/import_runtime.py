"""Runtime helpers for import progress polling and cooperative stop handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable, Protocol

from nicegui import run

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
    
    def finish(self) -> None:
        ...
    
    def snapshot(self) -> ImportProgressState:
        ...

class ImportMonitor:
    """Thread-safe bridge for progress updates coming from the import worker."""
    
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

def build_import_request(*, draft: Any) -> Any:
    from .td_exec import GuiCommandRequest
    
    return GuiCommandRequest(
        command='import',
        main_values=dict(draft.main_values),
        advanced_values=dict(draft.advanced_values),
        context_overrides=dict(draft.context_overrides),
        global_values={},
        ship_profile_values={},
        import_monitor=ImportMonitor(),
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
    # ImportMonitor owns worker-side progress state. Copy a point-in-time
    # snapshot into SessionState so the rest of the GUI can render it through
    # the same execution object used for normal command results.
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
        # shell value instead of expecting the worker monitor to track it.
        import_stop_confirming=session.execution.import_stop_confirming,
    )

async def run_import_execution(
    *,
    session: Any,
    executor: Any,
    request: Any,
    refresh_ui: Callable[[], None],
) -> None:
    import asyncio
    
    from .session import ExecutionStatus
    
    monitor = request.import_monitor
    session.active_import_monitor = monitor
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
        # `executor.execute()` is blocking and may run for minutes. Keep it off
        # the event loop and poll the shared monitor for fresh snapshots.
        worker = asyncio.create_task(run.io_bound(executor.execute, request))
        while not worker.done():
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
            await asyncio.sleep(0.2)
        
        try:
            result = await worker
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
        
        status = ExecutionStatus.SUCCEEDED if result.ok else ExecutionStatus.FAILED
        _apply_snapshot_to_session(
            session=session,
            status=status,
            active_command=result.command,
            error_message=result.error_message,
            raw_output=result.raw_output,
            diagnostics_output=result.diagnostics_output,
            structured_result=result.structured_result,
            snapshot=monitor.snapshot(),
        )
        refresh_ui()
    finally:
        session.active_import_monitor = None

def begin_import_stop_confirmation(*, session: Any) -> bool:
    monitor = getattr(session, 'active_import_monitor', None)
    if monitor is None:
        return False
    
    session.execution.import_stop_confirming = True
    return True

def cancel_import_stop_confirmation(*, session: Any) -> bool:
    monitor = getattr(session, 'active_import_monitor', None)
    if monitor is None:
        return False
    
    session.execution.import_stop_confirming = False
    return True

def request_import_stop(*, session: Any) -> bool:
    monitor = getattr(session, 'active_import_monitor', None)
    if monitor is None:
        return False
    
    session.execution.import_stop_confirming = False
    # This is a cooperative stop: the worker checks the flag between import
    # steps, so the UI only promises that the request has been recorded.
    monitor.request_stop()
    snapshot = monitor.snapshot()
    _apply_snapshot_to_session(
        session=session,
        status=session.execution.status,
        active_command=session.execution.active_command,
        error_message=session.execution.error_message,
        raw_output=session.execution.raw_output,
        diagnostics_output=session.execution.diagnostics_output,
        structured_result=session.execution.structured_result,
        snapshot=snapshot,
    )
    return True
