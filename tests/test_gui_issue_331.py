import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import tradedangerous.guiapp.shell as shell_module
from tradedangerous.guiapp.journal_import import JournalFacts
from tradedangerous.guiapp.profiles import GuiStore
from tradedangerous.guiapp.session import ExecutionStatus
from tradedangerous.guiapp.shell import AppShell


def _command_select(value):
    control = MagicMock()
    control.value = value
    control.disabled = False
    control.disable.side_effect = (
        lambda: setattr(control, 'disabled', True)
    )
    control.enable.side_effect = (
        lambda: setattr(control, 'disabled', False)
    )
    return control


@pytest.mark.parametrize(
    ('solo', 'expected_mode'),
    [
        (False, 'crowdsourced'),
        (True, 'solo'),
    ],
)
def test_issue_331_journal_import_is_not_initial_database_setup(
    monkeypatch,
    solo,
    expected_mode,
):
    store = GuiStore.default()
    assert store.data_mode is None
    monkeypatch.setattr(shell_module, 'get_gui_search_service', object)
    shell = AppShell(store)
    shell.command_select = _command_select(shell.session.selected_command)
    shell._refresh_ui = MagicMock()
    shell._show_import_summary = MagicMock()
    saved_modes = []
    monkeypatch.setattr(
        shell_module,
        'save_gui_store',
        lambda current_store: saved_modes.append(current_store.data_mode),
    )
    monkeypatch.setattr(
        shell_module,
        'read_journal_facts',
        lambda _journal_dir: JournalFacts(
            commander_name='Acceptance Commander',
            credits=12_345_678,
            cargo_capacity=64,
            insurance=765_432,
            ship_name='Acceptance Ship',
        ),
    )
    assert shell.session.selected_command == 'import'
    assert store.selected_command == 'import'
    shell._on_import_from_journal()
    assert shell.session.global_state.commander_name == 'Acceptance Commander'
    assert shell.session.global_state.credits == 12_345_678
    assert store.global_settings.commander_name == 'Acceptance Commander'
    assert store.global_settings.credits == 12_345_678
    assert shell.session.ship_state.ship_name == 'Acceptance Ship'
    assert shell.session.ship_state.capacity == 64
    assert shell.session.ship_state.insurance == 765_432
    assert shell.session.ship_state.is_dirty is True
    assert store.data_mode is None
    assert shell.session.execution.status is ExecutionStatus.IDLE
    assert saved_modes == [None]
    shell.command_select.value = 'run'
    asyncio.run(shell._on_command_changed(SimpleNamespace(value='run')))
    assert shell.session.selected_command == 'import'
    assert store.selected_command == 'import'
    assert shell.command_select.value == 'import'
    assert saved_modes == [None]
    if solo:
        shell.session.draft.main_values['solo'] = True
    executed_requests = []

    async def complete_td_import(
        *,
        session,
        request,
        refresh_ui,
        window_close_state,
    ):
        executed_requests.append(request)
        session.set_execution(
            status=ExecutionStatus.SUCCEEDED,
            active_command='import',
        )

    monkeypatch.setattr(
        shell_module,
        'run_import_execution',
        complete_td_import,
    )
    asyncio.run(shell._on_execute_command())
    assert bool(executed_requests[0].main_values.get('solo')) is solo
    assert store.data_mode == expected_mode
    assert shell.command_select.disabled is False
    assert saved_modes == [None, expected_mode]
    shell.command_select.value = 'run'
    asyncio.run(shell._on_command_changed(SimpleNamespace(value='run')))
    assert shell.session.selected_command == 'run'
    assert store.selected_command == 'run'
    assert saved_modes == [None, expected_mode, expected_mode]
