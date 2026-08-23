import asyncio
from functools import partial
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import tradedangerous.guiapp.import_view as import_view
import tradedangerous.guiapp.shell as shell_module
from tradedangerous.guiapp.import_view import ImportWorkspace
from tradedangerous.guiapp.profiles import GuiStore
from tradedangerous.guiapp.session import ExecutionState, ExecutionStatus
from tradedangerous.guiapp.shell import AppShell


def _fake_element(*, value=None):
    element = MagicMock()
    element.value = value
    element.text = ''
    element.disabled = False
    element.visible = True
    element.classes.return_value = element
    element.style.return_value = element
    element.props.return_value = element
    element.tooltip.return_value = element
    element.disable.side_effect = (
        lambda: setattr(element, 'disabled', True) or element
    )
    element.enable.side_effect = (
        lambda: setattr(element, 'disabled', False) or element
    )
    element.set_visibility.side_effect = (
        lambda visible: setattr(element, 'visible', visible) or element
    )
    element.__enter__.return_value = element
    return element


def _fake_ui():
    fake_ui = SimpleNamespace(
        labels=[],
        checkbox_labels=[],
        links=[],
    )
    fake_ui.dialog = MagicMock(side_effect=lambda: _fake_element())
    fake_ui.card = MagicMock(side_effect=lambda: _fake_element())
    fake_ui.column = MagicMock(side_effect=lambda: _fake_element())
    fake_ui.row = MagicMock(side_effect=lambda: _fake_element())
    fake_ui.label = MagicMock(
        side_effect=lambda value: (
            fake_ui.labels.append(value) or _fake_element()
        )
    )
    fake_ui.link = MagicMock(
        side_effect=lambda text, target, **kwargs: (
            fake_ui.links.append((text, target, kwargs))
            or _fake_element()
        )
    )
    fake_ui.checkbox = MagicMock(
        side_effect=lambda label, **kwargs: (
            fake_ui.checkbox_labels.append(label)
            or _fake_element(value=kwargs.get('value'))
        )
    )
    fake_ui.button = MagicMock(side_effect=lambda *_args, **_kwargs: _fake_element())
    fake_ui.space = MagicMock(side_effect=lambda: _fake_element())
    return fake_ui


async def _complete_import(
    *,
    final_status,
    session,
    request,
    refresh_ui,
    window_close_state,
):
    session.set_execution(
        status=final_status,
        active_command=request.command,
    )


def _make_shell(monkeypatch, *, data_mode, selected_command='run'):
    store = GuiStore.default()
    store.data_mode = data_mode
    store.selected_command = selected_command
    monkeypatch.setattr(shell_module, 'get_gui_search_service', object)
    shell = AppShell(store)
    shell.command_select = _fake_element(
        value=shell.session.selected_command,
    )
    shell._refresh_ui = lambda: None
    return shell, store


def _build_import_workspace(
    monkeypatch,
    *,
    initial_setup,
    draft=None,
):
    fake_ui = _fake_ui()
    monkeypatch.setattr(import_view, 'ui', fake_ui)
    if draft is None:
        draft = GuiStore.default().get_or_create_draft('import')
    workspace = ImportWorkspace(
        draft,
        ExecutionState(),
        initial_setup=initial_setup,
        on_changed=lambda: None,
        on_execute=lambda: None,
        on_arm_stop=lambda: None,
        on_cancel_stop=lambda: None,
        on_stop=lambda: None,
    )
    workspace.build()
    return workspace


def test_unfinished_setup_selects_import_workspace(monkeypatch):
    shell, store = _make_shell(monkeypatch, data_mode=None)
    assert shell.session.selected_command == 'import'
    assert store.selected_command == 'import'
    assert shell.session.draft is store.drafts['import']


def test_unfinished_setup_rejects_ordinary_command_navigation(monkeypatch):
    shell, store = _make_shell(monkeypatch, data_mode=None)
    saved = []
    monkeypatch.setattr(shell_module, 'save_gui_store', saved.append)
    shell.command_select.value = 'run'
    asyncio.run(
        shell._on_command_changed(SimpleNamespace(value='run'))
    )
    assert shell.session.selected_command == 'import'
    assert store.selected_command == 'import'
    assert shell.command_select.value == 'import'
    assert saved == []


@pytest.mark.parametrize('data_mode', ['crowdsourced', 'solo'])
def test_established_data_mode_retains_normal_navigation(
    monkeypatch,
    data_mode,
):
    shell, store = _make_shell(
        monkeypatch,
        data_mode=data_mode,
        selected_command='run',
    )
    saved = []
    monkeypatch.setattr(shell_module, 'save_gui_store', saved.append)
    asyncio.run(
        shell._on_command_changed(SimpleNamespace(value='market'))
    )
    assert shell.session.selected_command == 'market'
    assert store.selected_command == 'market'
    assert saved == [store]


@pytest.mark.parametrize(
    (
        'final_status',
        'request_solo',
        'expected_mode',
        'expected_disabled',
    ),
    [
        (ExecutionStatus.SUCCEEDED, False, 'crowdsourced', False),
        (ExecutionStatus.SUCCEEDED, True, 'solo', False),
        (ExecutionStatus.FAILED, False, None, True),
        (ExecutionStatus.IDLE, False, None, True),
    ],
)
def test_initial_import_result_controls_navigation_gate(
    monkeypatch,
    final_status,
    request_solo,
    expected_mode,
    expected_disabled,
):
    shell, store = _make_shell(monkeypatch, data_mode=None)
    if request_solo:
        shell.session.draft.main_values['solo'] = True
    saved = []
    monkeypatch.setattr(
        shell_module,
        'run_import_execution',
        partial(_complete_import, final_status=final_status),
    )
    monkeypatch.setattr(shell_module, 'save_gui_store', saved.append)
    asyncio.run(shell._on_execute_command())
    assert store.data_mode == expected_mode
    assert shell.command_select.disabled is expected_disabled
    shell.command_select.value = 'run'
    asyncio.run(
        shell._on_command_changed(SimpleNamespace(value='run'))
    )
    assert shell.session.selected_command == (
        'import' if expected_disabled else 'run'
    )


def test_first_run_import_guidance_uses_existing_solo_option(monkeypatch):
    fake_ui = _fake_ui()
    monkeypatch.setattr(import_view, 'ui', fake_ui)
    workspace = ImportWorkspace(
        GuiStore.default().get_or_create_draft('import'),
        ExecutionState(),
        initial_setup=True,
        on_changed=lambda: None,
        on_execute=lambda: None,
        on_arm_stop=lambda: None,
        on_cancel_stop=lambda: None,
        on_stop=lambda: None,
    )
    workspace.build()
    guidance = ' '.join(fake_ui.labels)
    assert 'Crowdsourced' in fake_ui.labels
    assert 'Solo' in fake_ui.labels
    assert 'normal Trade Dangerous Import' in guidance
    assert 'schema and base data' in guidance
    assert 'recommended and supported workflow' in guidance
    assert 'another data source' in guidance
    assert fake_ui.links == [
        ('EDMC + UpdateTD', import_view.UPDATE_TD_URL, {'new_tab': True}),
    ]
    assert fake_ui.checkbox_labels == [
        'All',
        'Clean',
        'Optimize',
        'Force',
        'Solo',
        'Purge',
        '7 Days',
        'Units',
    ]


def test_incomplete_setup_shows_retained_onboarding_card(monkeypatch):
    workspace = _build_import_workspace(
        monkeypatch,
        initial_setup=True,
    )
    assert workspace.onboarding_card.visible is True


def test_running_import_hides_only_onboarding_and_retains_widgets(monkeypatch):
    workspace = _build_import_workspace(
        monkeypatch,
        initial_setup=True,
    )
    retained_widgets = (
        workspace.onboarding_card,
        workspace.status_label,
        workspace.parent_label,
        workspace.child_label,
        workspace.log_label,
    )
    running = ExecutionState(
        status=ExecutionStatus.RUNNING,
        active_command='import',
        import_status_text='Import running',
        import_log_lines=['progress line'],
    )
    workspace.refresh_onboarding(initial_setup=True, running=True)
    workspace.refresh(running)
    workspace.refresh(running)
    assert workspace.onboarding_card.visible is False
    assert workspace.status_label.text == 'Import running'
    assert workspace.log_label.text == 'progress line'
    assert retained_widgets == (
        workspace.onboarding_card,
        workspace.status_label,
        workspace.parent_label,
        workspace.child_label,
        workspace.log_label,
    )


@pytest.mark.parametrize(
    ('solo', 'expected_mode'),
    [
        (False, 'crowdsourced'),
        (True, 'solo'),
    ],
)
def test_successful_initial_import_hides_onboarding_from_start_to_completion(
    monkeypatch,
    solo,
    expected_mode,
):
    shell, store = _make_shell(monkeypatch, data_mode=None)
    if solo:
        shell.session.draft.main_values['solo'] = True
    workspace = _build_import_workspace(
        monkeypatch,
        initial_setup=True,
        draft=shell.session.draft,
    )
    shell.import_workspace = workspace
    workspace.onboarding_card.set_visibility.reset_mock()
    retained_widgets = (
        workspace.status_label,
        workspace.log_label,
    )

    async def complete_import(
        *,
        session,
        request,
        refresh_ui,
        window_close_state,
    ):
        assert workspace.onboarding_card.visible is False
        assert store.data_mode is None
        assert bool(request.main_values.get('solo')) is solo
        session.set_execution(
            status=ExecutionStatus.RUNNING,
            active_command='import',
            import_status_text='Import running',
            import_log_lines=['working'],
        )
        workspace.refresh(session.execution)
        assert workspace.onboarding_card.visible is False
        session.set_execution(
            status=ExecutionStatus.SUCCEEDED,
            active_command='import',
            import_status_text='Import complete',
            import_log_lines=['working', 'done'],
        )
        workspace.refresh(session.execution)

    saved = []
    monkeypatch.setattr(shell_module, 'run_import_execution', complete_import)
    monkeypatch.setattr(shell_module, 'save_gui_store', saved.append)
    asyncio.run(shell._on_execute_command())
    assert store.data_mode == expected_mode
    assert workspace.onboarding_card.visible is False
    assert all(
        visibility_call.args == (False,)
        for visibility_call in (
            workspace.onboarding_card.set_visibility.call_args_list
        )
    )
    assert workspace.status_label.text == 'Import complete'
    assert workspace.log_label.text == 'working\ndone'
    assert shell.import_workspace is workspace
    assert retained_widgets == (
        workspace.status_label,
        workspace.log_label,
    )
    assert saved == [store]


@pytest.mark.parametrize(
    'status_text',
    ['Import failed.', 'Import stopped.'],
    ids=['failed', 'stopped'],
)
def test_unsuccessful_initial_import_restores_onboarding(
    monkeypatch,
    status_text,
):
    shell, store = _make_shell(monkeypatch, data_mode=None)
    workspace = _build_import_workspace(
        monkeypatch,
        initial_setup=True,
        draft=shell.session.draft,
    )
    shell.import_workspace = workspace
    workspace.onboarding_card.set_visibility.reset_mock()

    async def fail_import(
        *,
        session,
        request,
        refresh_ui,
        window_close_state,
    ):
        assert workspace.onboarding_card.visible is False
        session.set_execution(
            status=ExecutionStatus.RUNNING,
            active_command=request.command,
        )
        workspace.refresh(session.execution)
        session.set_execution(
            status=ExecutionStatus.FAILED,
            active_command=request.command,
            import_status_text=status_text,
        )
        workspace.refresh(session.execution)

    save_store = MagicMock()
    monkeypatch.setattr(shell_module, 'run_import_execution', fail_import)
    monkeypatch.setattr(shell_module, 'save_gui_store', save_store)
    asyncio.run(shell._on_execute_command())
    assert store.data_mode is None
    assert workspace.onboarding_card.visible is True
    assert workspace.onboarding_card.set_visibility.call_args_list[0].args == (
        False,
    )
    assert workspace.onboarding_card.set_visibility.call_args_list[-1].args == (
        True,
    )
    assert workspace.status_label.text == status_text
    assert shell.import_workspace is workspace
    save_store.assert_not_called()


@pytest.mark.parametrize('data_mode', ['crowdsourced', 'solo'])
def test_established_installation_never_shows_import_onboarding(
    monkeypatch,
    data_mode,
):
    workspace = _build_import_workspace(
        monkeypatch,
        initial_setup=(data_mode is None),
    )
    assert workspace.onboarding_card.visible is False
    for status in (
        ExecutionStatus.IDLE,
        ExecutionStatus.RUNNING,
        ExecutionStatus.FAILED,
    ):
        workspace.refresh(
            ExecutionState(status=status, active_command='import'),
        )
        workspace.refresh_onboarding(
            initial_setup=(data_mode is None),
            running=status is ExecutionStatus.RUNNING,
        )
        assert workspace.onboarding_card.visible is False
