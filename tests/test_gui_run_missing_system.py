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
    workspace.end_system_warning_label = MagicMock()
    workspace.end_system_warning_label.text = ''


@pytest.mark.parametrize(
    ('data_mode', 'expected_text'),
    [
        ('crowdsourced', 'Run Import to update the crowdsourced data'),
        ('solo', 'not present in your solo database'),
    ],
)
def test_missing_from_system_guidance_matches_data_mode(
    data_mode,
    expected_text,
):
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
    assert expected_text in workspace.start_system_warning_label.text
    assert 'Unknown Place' in workspace.start_system_warning_label.text
    assert draft.main_values['startSystem'] == 'Unknown Place'
    workspace.start_system_warning_label.set_visibility.assert_called_with(True)
    if data_mode == 'solo':
        assert 'EDMC + UpdateTD' in workspace.start_system_warning_label.text
        assert 'crowdsourced' not in workspace.start_system_warning_label.text
        assert 'Run Import' not in workspace.start_system_warning_label.text


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
    workspace.start_system_warning_label.set_visibility.assert_called_with(False)


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
    workspace.start_system_warning_label.set_visibility.assert_called_with(False)


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
    workspace.end_system_warning_label.set_visibility.assert_called_with(True)


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
    workspace.start_system_warning_label.set_visibility.assert_called_with(False)
    shell.search_database_error_label.set_visibility.assert_called_once_with(True)


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
    rendered_labels = []

    def build_missing_workspace(workspace):
        workspace._normalize_run_state()
        workspace._build_missing_system_warning(
            missing_attr='missing_start_system_name',
            warning_label_attr='start_system_warning_label',
        )

    def make_label(text):
        label = MagicMock()
        label.text = text
        rendered_labels.append(label)
        return label

    monkeypatch.setattr(shell_module.RunWorkspace, 'build', build_missing_workspace)
    monkeypatch.setattr(run_view_module.ui, 'label', make_label)
    shell._render_workspace()
    assert loaded_store.drafts['run'].main_values['startSystem'] == (
        'Unrecorded System'
    )
    assert shell.search_database_error is None
    assert len(rendered_labels) == 1
    service.resolve_system.assert_called_once_with('Unrecorded System')
    assert 'Unrecorded System' in rendered_labels[0].text
    assert 'solo database' in rendered_labels[0].text
    rendered_labels[0].set_visibility.assert_called_once_with(True)
