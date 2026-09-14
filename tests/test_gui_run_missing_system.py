from functools import partial
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import tradedangerous.guiapp.run_view as run_view_module
import tradedangerous.guiapp.shell as shell_module
from tradedangerous.guiapp.gui_search import GuiSearchDatabaseError
from tradedangerous.guiapp.profiles import (
    CommandDraft,
    GuiStore,
    load_gui_store,
    save_gui_store,
)
from tradedangerous.guiapp.run_view import RunWorkspace
from tradedangerous.guiapp.shell import AppShell, _safe_resolve_system


START_FIELD = {
    'system_key': 'startSystem',
    'station_key': 'startStation',
    'combined_key': 'starting',
    'selected_attr': 'selected_start_system_id',
    'station_autocomplete_attr': 'start_station_autocomplete',
    'missing_attr': 'missing_start_system_name',
    'warning_label_attr': 'start_system_warning_label',
}

END_FIELD = {
    'system_key': 'endSystem',
    'station_key': 'endStation',
    'combined_key': 'ending',
    'selected_attr': 'selected_end_system_id',
    'station_autocomplete_attr': 'end_station_autocomplete',
    'missing_attr': 'missing_end_system_name',
    'warning_label_attr': 'end_system_warning_label',
}


def _workspace(*, data_mode, draft, resolve_system, database_search_failed=None):
    return RunWorkspace(
        draft,
        on_changed=MagicMock(),
        on_execute=MagicMock(),
        on_copy_from_profile=MagicMock(),
        resolve_system=resolve_system,
        data_mode=data_mode,
        database_search_failed=database_search_failed,
    )


def _attach_warning_labels(workspace):
    workspace.start_system_warning_label = MagicMock()
    workspace.start_system_warning_label.text = ''
    workspace.start_system_warning_label_row = MagicMock()

    workspace.end_system_warning_label = MagicMock()
    workspace.end_system_warning_label.text = ''
    workspace.end_system_warning_label_row = MagicMock()


def _fake_ui_element():
    element = MagicMock()
    element.classes.return_value = element
    element.props.return_value = element
    element.__enter__.return_value = element
    return element


def _patch_warning_ui(monkeypatch):
    rendered = SimpleNamespace(
        dialog=_fake_ui_element(),
        labels=[],
        rows=[],
        buttons=[],
    )

    def make_label(text):
        label = _fake_ui_element()
        label.text = text
        rendered.labels.append(label)
        return label

    def make_row():
        row = _fake_ui_element()
        rendered.rows.append(row)
        return row

    def make_button(text, **kwargs):
        button = _fake_ui_element()
        rendered.buttons.append((text, kwargs, button))
        return button

    monkeypatch.setattr(
        run_view_module.ui,
        'dialog',
        MagicMock(return_value=rendered.dialog),
    )
    monkeypatch.setattr(
        run_view_module.ui,
        'card',
        MagicMock(side_effect=_fake_ui_element),
    )
    monkeypatch.setattr(run_view_module.ui, 'label', make_label)
    monkeypatch.setattr(run_view_module.ui, 'row', make_row)
    monkeypatch.setattr(run_view_module.ui, 'button', make_button)
    return rendered


@pytest.mark.parametrize('data_mode', ['crowdsourced', 'solo'])
def test_missing_from_system_shows_concise_warning(data_mode):
    draft = CommandDraft(main_values={'startSystem': 'Unknown Place'})
    workspace = _workspace(
        data_mode=data_mode,
        draft=draft,
        resolve_system=lambda _text: None,
    )
    _attach_warning_labels(workspace)
    workspace._normalize_run_state()
    assert workspace.selected_start_system_id is None
    assert workspace.missing_start_system_name == 'Unknown Place'
    assert workspace.start_system_warning_label.text == (
        'System "Unknown Place" not found.'
    )
    assert draft.main_values['startSystem'] == 'Unknown Place'
    workspace.start_system_warning_label_row.set_visibility.assert_called_with(
        True
    )


@pytest.mark.parametrize(
    ('data_mode', 'expected_text', 'unexpected_text'),
    [
        (
            'crowdsourced',
            'run Import to refresh the crowdsourced data',
            'solo database',
        ),
        (
            'solo',
            'EDMC + UpdateTD is the recommended and supported solo workflow',
            'refresh the crowdsourced data',
        ),
    ],
)
def test_missing_system_help_guidance_matches_data_mode(
    monkeypatch,
    data_mode,
    expected_text,
    unexpected_text,
):
    workspace = _workspace(
        data_mode=data_mode,
        draft=CommandDraft(),
        resolve_system=lambda _text: None,
    )
    workspace.missing_start_system_name = 'Unknown Place'
    rendered = _patch_warning_ui(monkeypatch)
    workspace._build_missing_system_warning(
        missing_attr='missing_start_system_name',
        warning_label_attr='start_system_warning_label',
    )
    rendered_text = ' '.join(label.text for label in rendered.labels)
    assert 'System not found' in rendered_text
    assert expected_text in rendered_text
    assert unexpected_text not in rendered_text
    assert workspace.start_system_warning_label.text == (
        'System "Unknown Place" not found.'
    )
    help_button = next(
        kwargs for text, kwargs, _button in rendered.buttons
        if text == 'Help'
    )
    help_button['on_click']()
    rendered.dialog.open.assert_called_once_with()


def test_changed_and_cleared_from_system_updates_warning():
    draft = CommandDraft(main_values={'startSystem': 'First Missing'})
    workspace = _workspace(
        data_mode='crowdsourced',
        draft=draft,
        resolve_system=lambda _text: None,
    )
    _attach_warning_labels(workspace)
    workspace._normalize_run_state()
    workspace._set_run_system_text('Second Missing', **START_FIELD)
    assert workspace.missing_start_system_name == 'Second Missing'
    assert 'Second Missing' in workspace.start_system_warning_label.text
    assert 'First Missing' not in workspace.start_system_warning_label.text
    workspace._set_run_system_text('', **START_FIELD)
    assert workspace.missing_start_system_name is None
    assert workspace.selected_start_system_id is None
    assert 'startSystem' not in draft.main_values
    workspace.start_system_warning_label_row.set_visibility.assert_called_with(
        False
    )


def test_successful_exact_resolution_clears_from_system_warning():
    draft = CommandDraft(main_values={'startSystem': 'Missing'})
    resolver = MagicMock(side_effect=[None, SimpleNamespace(system_id=42)])
    workspace = _workspace(
        data_mode='crowdsourced',
        draft=draft,
        resolve_system=resolver,
    )
    _attach_warning_labels(workspace)
    workspace._normalize_run_state()
    workspace._set_run_system_text('Lave', **START_FIELD)
    assert workspace.selected_start_system_id == 42
    assert workspace.missing_start_system_name is None
    workspace.start_system_warning_label_row.set_visibility.assert_called_with(
        False
    )


def test_from_and_to_missing_system_warnings_remain_independent():
    draft = CommandDraft(main_values={
        'startSystem': 'Missing Start',
        'endSystem': 'Missing End',
    })
    workspace = _workspace(
        data_mode='crowdsourced',
        draft=draft,
        resolve_system=lambda _text: None,
    )
    _attach_warning_labels(workspace)
    workspace._normalize_run_state()
    workspace._set_run_system_text('', **START_FIELD)
    assert workspace.missing_start_system_name is None
    assert workspace.missing_end_system_name == 'Missing End'
    assert 'Missing End' in workspace.end_system_warning_label.text
    workspace.end_system_warning_label_row.set_visibility.assert_called_with(
        True
    )


def test_database_failure_preempts_missing_system_warning():
    error = GuiSearchDatabaseError('search failed')
    service = SimpleNamespace(
        resolve_system=MagicMock(side_effect=error),
    )
    shell = AppShell.__new__(AppShell)
    shell.store = GuiStore.default()
    shell.store.data_mode = 'crowdsourced'
    shell.search_service = service
    shell.search_database_error = None
    shell.search_database_error_label = MagicMock()
    shell.search_database_error_label.text = ''
    draft = CommandDraft(main_values={'startSystem': 'Lave'})
    workspace = _workspace(
        data_mode='crowdsourced',
        draft=draft,
        resolve_system=partial(_safe_resolve_system, shell),
        database_search_failed=lambda: shell.search_database_error is not None,
    )
    _attach_warning_labels(workspace)
    workspace._normalize_run_state()
    assert shell.search_database_error is error
    assert workspace.selected_start_system_id is None
    assert workspace.missing_start_system_name is None
    assert 'not present' not in workspace.start_system_warning_label.text
    workspace.start_system_warning_label_row.set_visibility.assert_called_with(
        False
    )
    shell.search_database_error_label.set_visibility.assert_called_once_with(True)


def test_database_failure_suppresses_without_forgetting_other_missing_system():
    error = GuiSearchDatabaseError('search failed')
    service = SimpleNamespace(resolve_system=MagicMock(side_effect=[
        None,
        error,
        SimpleNamespace(system_id=42),
    ]))
    shell = AppShell.__new__(AppShell)
    shell.store = GuiStore.default()
    shell.store.data_mode = 'crowdsourced'
    shell.search_service = service
    shell.search_database_error = None
    shell.search_database_error_label = MagicMock()
    shell.search_database_error_label.text = ''
    draft = CommandDraft(main_values={
        'startSystem': 'Missing Start',
        'endSystem': 'Uncheckable End',
    })
    workspace = _workspace(
        data_mode='crowdsourced',
        draft=draft,
        resolve_system=partial(_safe_resolve_system, shell),
        database_search_failed=lambda: shell.search_database_error is not None,
    )
    _attach_warning_labels(workspace)
    shell.search_database_state_listener = (
        workspace._refresh_missing_system_warnings
    )
    workspace._normalize_run_state()
    assert shell.search_database_error is error
    assert workspace.missing_start_system_name == 'Missing Start'
    assert workspace.start_system_warning_label.text == ''
    workspace.start_system_warning_label_row.set_visibility.assert_called_with(
        False
    )
    workspace._set_run_system_text('Lave', **END_FIELD)
    assert shell.search_database_error is None
    assert workspace.selected_end_system_id == 42
    assert workspace.missing_start_system_name == 'Missing Start'
    assert workspace.start_system_warning_label.text == (
        'System "Missing Start" not found.'
    )
    workspace.start_system_warning_label_row.set_visibility.assert_called_with(
        True
    )


def test_persisted_missing_run_system_renders_guidance_on_startup(
    monkeypatch,
    tmp_path,
):
    store = GuiStore.default()
    store.data_mode = 'solo'
    store.drafts['run'].main_values['startSystem'] = 'Unrecorded System'
    state_path = tmp_path / 'tradegui_state.json'
    save_gui_store(store, state_path)
    loaded_store = load_gui_store(state_path)
    service = SimpleNamespace(resolve_system=MagicMock(return_value=None))
    monkeypatch.setattr(
        shell_module,
        'get_gui_search_service',
        lambda: service,
    )
    shell = AppShell(loaded_store)
    shell.search_database_error_label = MagicMock()
    shell.search_database_error_label.text = ''
    shell.workspace_host = MagicMock()
    shell.workspace_host.__enter__.return_value = shell.workspace_host
    rendered = _patch_warning_ui(monkeypatch)
    rendered_workspaces = []

    def build_missing_workspace(workspace):
        rendered_workspaces.append(workspace)
        workspace._normalize_run_state()
        workspace._build_missing_system_warning(
            missing_attr='missing_start_system_name',
            warning_label_attr='start_system_warning_label',
        )

    monkeypatch.setattr(shell_module.RunWorkspace, 'build', build_missing_workspace)
    shell._render_workspace()
    assert loaded_store.drafts['run'].main_values['startSystem'] == (
        'Unrecorded System'
    )
    assert shell.search_database_error is None
    assert shell.search_database_state_listener == (
        rendered_workspaces[0]._refresh_missing_system_warnings
    )
    service.resolve_system.assert_called_once_with('Unrecorded System')
    rendered_text = ' '.join(label.text for label in rendered.labels)
    assert 'System not found' in rendered_text
    assert 'solo database' in rendered_text
    assert 'System "Unrecorded System" not found.' in rendered_text
    assert len(rendered.rows) == 1
    rendered.rows[0].set_visibility.assert_called_once_with(True)
