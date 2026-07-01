import importlib
from types import SimpleNamespace

import pytest

from tradedangerous.guiapp.profiles import GuiStore

settings_view = importlib.import_module('tradedangerous.guiapp.settings_view')
SettingsWorkspace = settings_view.SettingsWorkspace
gui_main = importlib.import_module('tradedangerous.guiapp.main')

class _FakeElement:
    def classes(self, _value):
        return self
    
    def style(self, _value):
        return self
    
    def props(self, _value):
        return self
    
    def tooltip(self, _value):
        return self
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc, tb):
        return False

class _FakeDialog(_FakeElement):
    def open(self):
        return None
    
    def close(self):
        return None

class _FakeUI:
    def __init__(self):
        self.input_calls = []
        self.labels = []
    
    def dialog(self):
        return _FakeDialog()
    
    def card(self):
        return _FakeElement()
    
    def column(self):
        return _FakeElement()
    
    def label(self, text):
        self.labels.append(text)
        return _FakeElement()
    
    def input(self, label, **kwargs):
        self.input_calls.append({'label': label, **kwargs})
        return _FakeElement()
    
    def select(self, *_args, **_kwargs):
        return _FakeElement()
    
    def button(self, *_args, **_kwargs):
        return _FakeElement()

@pytest.mark.parametrize(('selected_port', 'expected_value'), [(None, ''), (8123, '8123')])
def test_settings_workspace_builds_application_port_input(monkeypatch, selected_port, expected_value):
    fake_ui = _FakeUI()
    monkeypatch.setattr(settings_view, 'ui', fake_ui)
    workspace = SettingsWorkspace(
        selected_theme='default',
        selected_launcher_port=selected_port,
        selected_journal_dir=None,
        on_theme_changed=lambda value: None,
        on_launcher_port_changed=lambda value: None,
        on_journal_dir_changed=lambda value: None,
    )
    
    workspace.build()
    
    assert fake_ui.input_calls[0]['label'] == 'Application Port'
    assert fake_ui.input_calls[0]['value'] == expected_value
    assert (
        fake_ui.input_calls[0]['placeholder']
        == f'Use default ({settings_view.DEFAULT_PORT})'
    )
    assert any(
        'it must be between 8000 and 8999' in label
        for label in fake_ui.labels
    )
    assert any(
        'Windows for a random open local port' in label
        for label in fake_ui.labels
    )
    assert any(
        label == 'Only change advanced settings if you know why you need them.'
        for label in fake_ui.labels
    )

def test_gui_store_round_trips_launcher_port():
    store = GuiStore.default()
    store.launcher_port = 8765
    
    restored = GuiStore.from_dict(store.to_dict())
    
    assert restored.launcher_port == 8765

@pytest.mark.parametrize('value', [None, '', 'banana', 7999, 9000])
def test_gui_store_invalid_launcher_port_falls_back_to_none(value):
    payload = GuiStore.default().to_dict()
    payload['launcher_port'] = value
    
    restored = GuiStore.from_dict(payload)
    
    assert restored.launcher_port is None

def test_build_arg_parser_accepts_in_range_port():
    args = gui_main.build_arg_parser().parse_args(['--port', '8765'])
    
    assert args.port == 8765

@pytest.mark.parametrize('port', ['7999', '9000'])
def test_build_arg_parser_rejects_out_of_range_port(port):
    parser = gui_main.build_arg_parser()
    
    with pytest.raises(SystemExit):
        parser.parse_args(['--port', port])

def test_resolve_server_port_prefers_cli_port(monkeypatch):
    store = GuiStore.default()
    store.launcher_port = 8123
    monkeypatch.setattr(gui_main, '_port_bind_error', lambda host, port: None)
    
    resolved = gui_main._resolve_server_port(
        host='127.0.0.1',
        cli_port=8456,
        store=store,
    )
    
    assert resolved == 8456

def test_resolve_server_port_uses_saved_port_when_present(monkeypatch):
    store = GuiStore.default()
    store.launcher_port = 8123
    monkeypatch.setattr(gui_main, '_port_bind_error', lambda host, port: None)
    
    resolved = gui_main._resolve_server_port(
        host='127.0.0.1',
        cli_port=None,
        store=store,
    )
    
    assert resolved == 8123

def test_resolve_server_port_uses_default_when_available(monkeypatch):
    monkeypatch.setattr(
        gui_main,
        '_port_bind_error',
        lambda host, port: None if port == gui_main.DEFAULT_LAUNCHER_PORT else 'busy',
    )
    
    resolved = gui_main._resolve_server_port(
        host='127.0.0.1',
        cli_port=None,
        store=GuiStore.default(),
    )
    
    assert resolved == gui_main.DEFAULT_LAUNCHER_PORT

def test_resolve_server_port_uses_random_fallback_when_default_is_busy(monkeypatch):
    monkeypatch.setattr(
        gui_main,
        '_port_bind_error',
        lambda host, port: 'busy' if port == gui_main.DEFAULT_LAUNCHER_PORT else None,
    )
    monkeypatch.setattr(gui_main, '_find_random_port', lambda host: 52123)
    
    resolved = gui_main._resolve_server_port(
        host='127.0.0.1',
        cli_port=None,
        store=GuiStore.default(),
    )
    
    assert resolved == 52123

def test_resolve_server_port_rejects_busy_saved_port(monkeypatch):
    store = GuiStore.default()
    store.launcher_port = 8765
    monkeypatch.setattr(gui_main, '_port_bind_error', lambda host, port: 'busy')
    
    with pytest.raises(RuntimeError, match='saved port 8765'):
        gui_main._resolve_server_port(
            host='127.0.0.1',
            cli_port=None,
            store=store,
        )

def test_resolve_server_port_rejects_busy_cli_port(monkeypatch):
    monkeypatch.setattr(gui_main, '_port_bind_error', lambda host, port: 'busy')
    
    with pytest.raises(RuntimeError, match='CLI port 8765'):
        gui_main._resolve_server_port(
            host='127.0.0.1',
            cli_port=8765,
            store=GuiStore.default(),
        )

@pytest.mark.parametrize(
    ('value', 'message'),
    [
        (8765, None),
        (None, None),
        ('   ', None),
        (7999, 'Port must be between 8000 and 8999.'),
        (8123.5, 'Port must be a whole number.'),
    ],
)
def test_settings_workspace_validates_launcher_port(value, message):
    assert SettingsWorkspace._validate_launcher_port(value) == message

def test_settings_workspace_change_handler_clears_port_for_blank_text():
    changed = []
    workspace = SettingsWorkspace(
        selected_theme='default',
        selected_launcher_port=8765,
        selected_journal_dir=None,
        on_theme_changed=lambda value: None,
        on_launcher_port_changed=changed.append,
        on_journal_dir_changed=lambda value: None,
    )
    
    workspace._on_launcher_port_changed(SimpleNamespace(value='   '))
    
    assert changed == [None]
