import asyncio
from functools import partial
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest

import tradedangerous.guiapp.shell as shell_module
from tradedangerous.guiapp.autocomplete import AutocompleteInput
from tradedangerous.guiapp.gui_search import GuiSearchDatabaseError
from tradedangerous.guiapp.profiles import (
    GuiStore,
    load_gui_store,
    save_gui_store,
)
from tradedangerous.guiapp.shell import (
    AppShell,
    _safe_resolve_system,
    _safe_suggest_buy_search,
    _safe_suggest_items,
    _safe_suggest_run_avoid,
    _safe_suggest_stations,
    _safe_suggest_systems,
)


SEARCH_METHOD_NAMES = (
    'suggest_systems',
    'resolve_system',
    'suggest_items',
    'suggest_buy_search',
    'suggest_run_avoid',
    'suggest_stations',
)


def _search_service():
    return SimpleNamespace(**{
        method_name: MagicMock()
        for method_name in SEARCH_METHOD_NAMES
    })


def _shell(*, data_mode, search_service):
    shell = AppShell.__new__(AppShell)
    shell.store = GuiStore.default()
    shell.store.data_mode = data_mode
    shell.search_service = search_service
    shell.search_database_error = None
    shell.search_database_error_label = MagicMock()
    shell.search_database_error_label.text = ''
    return shell


@pytest.mark.parametrize(
    ('safe_callback', 'service_method', 'args', 'fallback'),
    [
        (_safe_resolve_system, 'resolve_system', ('Lave',), None),
        (_safe_suggest_systems, 'suggest_systems', ('Lav',), []),
        (_safe_suggest_items, 'suggest_items', ('Gold',), []),
        (_safe_suggest_buy_search, 'suggest_buy_search', ('Gold',), []),
        (_safe_suggest_run_avoid, 'suggest_run_avoid', ('Gold',), []),
        (_safe_suggest_stations, 'suggest_stations', ('Lave Station', 7), []),
    ],
)
def test_safe_search_callbacks_translate_database_failure(
    safe_callback,
    service_method,
    args,
    fallback,
):
    error = GuiSearchDatabaseError('search failed')
    service = _search_service()
    getattr(service, service_method).side_effect = error
    shell = _shell(data_mode='crowdsourced', search_service=service)
    assert safe_callback(shell, *args) == fallback
    assert shell.search_database_error is error
    assert 'search_database_error' not in shell.store.to_dict()


def test_ordinary_no_result_does_not_create_database_failure():
    service = _search_service()
    service.resolve_system.return_value = None
    service.suggest_systems.return_value = []
    shell = _shell(data_mode='crowdsourced', search_service=service)
    assert _safe_resolve_system(shell, 'Missing') is None
    assert _safe_suggest_systems(shell, 'Missing') == []
    assert shell.search_database_error is None
    shell.search_database_error_label.set_visibility.assert_not_called()


def test_repeated_search_failures_show_one_persistent_diagnostic():
    error = GuiSearchDatabaseError('search failed')
    service = _search_service()
    service.suggest_systems.side_effect = error
    shell = _shell(data_mode='crowdsourced', search_service=service)
    autocomplete = AutocompleteInput(
        label='System',
        fetch_suggestions=partial(_safe_suggest_systems, shell),
        on_text_changed=lambda _text: None,
        debounce_seconds=0,
    )
    autocomplete.overlay = MagicMock()
    for query in ('L', 'La'):
        autocomplete._latest_query = query
        asyncio.run(autocomplete._run_search(expected_query=query))
    assert service.suggest_systems.call_count == 2
    assert autocomplete.overlay.clear.call_count == 2
    assert shell.search_database_error_label.set_visibility.call_args_list == [
        call(True),
    ]


def test_successful_search_clears_transient_database_failure():
    error = GuiSearchDatabaseError('search failed')
    service = _search_service()
    service.suggest_systems.side_effect = [error, []]
    shell = _shell(data_mode='crowdsourced', search_service=service)
    assert _safe_suggest_systems(shell, 'L') == []
    assert _safe_suggest_systems(shell, 'La') == []
    assert shell.search_database_error is None
    assert shell.search_database_error_label.set_visibility.call_args_list == [
        call(True),
        call(False),
    ]


@pytest.mark.parametrize(
    ('data_mode', 'expected_text'),
    [
        ('crowdsourced', 'initialise or rebuild the crowdsourced data'),
        ('solo', 'use Solo to initialise or rebuild'),
        (None, 'Complete the initial Import setup'),
    ],
)
def test_database_failure_guidance_matches_data_mode(
    data_mode,
    expected_text,
):
    error = GuiSearchDatabaseError('search failed')
    service = _search_service()
    service.resolve_system.side_effect = error
    shell = _shell(data_mode=data_mode, search_service=service)
    assert _safe_resolve_system(shell, 'Lave') is None
    assert expected_text in shell.search_database_error_label.text
    if data_mode == 'solo':
        assert 'EDMC + UpdateTD' in shell.search_database_error_label.text
        assert 'crowdsourced' not in shell.search_database_error_label.text


def test_safe_boundary_does_not_catch_unexpected_errors():
    service = _search_service()
    service.resolve_system.side_effect = RuntimeError('unexpected')
    shell = _shell(data_mode='crowdsourced', search_service=service)
    with pytest.raises(RuntimeError, match='unexpected'):
        _safe_resolve_system(shell, 'Lave')
    assert shell.search_database_error is None


def test_persisted_run_system_survives_failed_startup_resolution(
    monkeypatch,
    tmp_path,
):
    store = GuiStore.default()
    store.data_mode = 'crowdsourced'
    store.drafts['run'].main_values['startSystem'] = 'Shinrarta Dezhra'
    state_path = tmp_path / 'tradegui_state.json'
    save_gui_store(store, state_path)
    loaded_store = load_gui_store(state_path)
    error = GuiSearchDatabaseError('search failed')
    service = _search_service()
    service.resolve_system.side_effect = error
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
    built_workspaces = []
    monkeypatch.setattr(
        shell_module.RunWorkspace,
        'build',
        lambda workspace: (
            built_workspaces.append(workspace),
            workspace._normalize_run_state(),
        ),
    )
    shell._render_workspace()
    assert len(built_workspaces) == 1
    assert built_workspaces[0].selected_start_system_id is None
    assert loaded_store.drafts['run'].main_values['startSystem'] == (
        'Shinrarta Dezhra'
    )
    assert shell.search_database_error is error
    shell.search_database_error_label.set_visibility.assert_called_once_with(
        True
    )
