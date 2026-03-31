from tradedangerous.guiapp.profiles import GuiStore
from tradedangerous.guiapp.session import ExecutionStatus, SessionState


def test_sessionstate_profile_save_revert_and_create_flows():
    store = GuiStore.default()
    session = SessionState.from_store(store)

    session.ship_state.ship_name = 'Python'
    session.ship_state.capacity = 128
    session.mark_ship_dirty()
    session.save_ship_profile(store)

    assert store.require_profile(session.selected_profile_id).ship_name == 'Python'
    assert session.ship_state.is_dirty is False

    session.ship_state.ship_name = 'Broken'
    session.revert_ship_profile(store)
    assert session.ship_state.ship_name == 'Python'

    original_ids = store.existing_profile_ids()
    session.create_new_ship_profile(store)

    assert session.selected_profile_id in store.existing_profile_ids()
    assert store.existing_profile_ids() != original_ids
    assert session.ship_state.profile_id == session.selected_profile_id


def test_sessionstate_set_execution_replaces_state_atomically():
    session = SessionState.from_store(GuiStore.default())
    first = session.execution

    session.set_execution(
        status=ExecutionStatus.RUNNING,
        active_command='run',
        import_log_lines=['one'],
        import_status_text='Running',
    )
    running = session.execution

    session.set_execution(
        status=ExecutionStatus.SUCCEEDED,
        active_command='trade',
        raw_output='done',
    )

    assert running is not first
    assert session.execution is not running
    assert session.execution.status is ExecutionStatus.SUCCEEDED
    assert session.execution.active_command == 'trade'
    assert session.execution.raw_output == 'done'
    assert session.execution.import_log_lines == []
    assert session.execution.import_status_text == ''
