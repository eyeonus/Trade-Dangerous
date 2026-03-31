from types import SimpleNamespace

from tradedangerous.guiapp.import_runtime import (
    ImportMonitor,
    ImportWorkerMessage,
    _apply_worker_message,
    begin_import_stop_confirmation,
    build_import_request,
    cancel_import_stop_confirmation,
    request_import_stop,
)
from tradedangerous.guiapp.profiles import CommandDraft, GuiStore
from tradedangerous.guiapp.session import SessionState


class _Runner:
    def __init__(self):
        self.messages = []
        self.active = True

    def is_active(self):
        return self.active

    def terminate(self, message):
        self.messages.append(message)
        self.active = False


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
