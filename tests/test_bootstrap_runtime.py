import configparser
import importlib
import os
import sys
from types import ModuleType, SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def restore_bootstrap_env():
    keys = ('TD_DB_CONFIG', 'TD_DATA', 'TD_TMP')
    saved = {key: os.environ.get(key) for key in keys}
    for key in keys:
        os.environ.pop(key, None)

    yield

    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture()
def bootstrap_module():
    import tradebootstrap

    module = importlib.reload(tradebootstrap)
    module._BOOTSTRAP_RESULT = None
    yield module
    module._BOOTSTRAP_RESULT = None


def _fake_winreg(value, reg_type, *, should_raise=False):
    class _Key:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    def open_key(*_args, **_kwargs):
        if should_raise:
            raise OSError('missing')
        return _Key()

    def query_value_ex(_key, _name):
        return value, reg_type

    return SimpleNamespace(
        HKEY_LOCAL_MACHINE=object(),
        REG_SZ=1,
        OpenKey=open_key,
        QueryValueEx=query_value_ex,
    )


def test_bootstrap_runtime_non_packaged_is_noop(bootstrap_module, monkeypatch):
    monkeypatch.delenv('TD_DB_CONFIG', raising=False)
    monkeypatch.delenv('TD_DATA', raising=False)
    monkeypatch.delenv('TD_TMP', raising=False)
    monkeypatch.setattr(bootstrap_module, '_detect_packaged_mode', lambda: False)

    result = bootstrap_module.bootstrap_runtime()

    assert result == {
        'packaged_mode': False,
        'app_root': None,
        'db_config': None,
        'data_dir': None,
        'tmp_dir': None,
        'logs_dir': None,
    }
    assert 'TD_DB_CONFIG' not in sys.modules['os'].environ
    assert 'TD_DATA' not in sys.modules['os'].environ
    assert 'TD_TMP' not in sys.modules['os'].environ


def test_bootstrap_runtime_packaged_sets_env_and_creates_paths(bootstrap_module, monkeypatch, tmp_path):
    app_root = tmp_path / 'TradeDangerous'
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.setattr(bootstrap_module, '_detect_packaged_mode', lambda: True)
    monkeypatch.setattr(bootstrap_module, '_get_packaged_root', lambda: app_root)

    result = bootstrap_module.bootstrap_runtime()

    assert result['packaged_mode'] is True
    assert result['app_root'] == app_root
    assert result['data_dir'] == app_root / 'data'
    assert result['tmp_dir'] == app_root / 'tmp'
    assert result['logs_dir'] == app_root / 'logs'
    assert result['db_config'] == app_root / 'db_config.ini'
    assert (app_root / 'data').is_dir()
    assert (app_root / 'tmp').is_dir()
    assert (app_root / 'logs').is_dir()
    assert sys.modules['os'].environ['TD_DB_CONFIG'] == str(app_root / 'db_config.ini')
    assert sys.modules['os'].environ['TD_DATA'] == str(app_root / 'data')
    assert sys.modules['os'].environ['TD_TMP'] == str(app_root / 'tmp')

    cfg = configparser.ConfigParser()
    cfg.read(app_root / 'db_config.ini', encoding='utf-8')
    assert cfg.get('database', 'backend') == 'sqlite'
    assert cfg.get('sqlite', 'sqlite_filename') == 'TradeDangerous.db'
    assert cfg.get('paths', 'data_dir') == str(app_root / 'data')
    assert cfg.get('paths', 'tmp_dir') == str(app_root / 'tmp')


def test_bootstrap_runtime_is_cached(bootstrap_module, monkeypatch, tmp_path):
    app_root = tmp_path / 'TradeDangerous'
    calls = {'root': 0, 'write': 0}
    real_write = bootstrap_module._write_packaged_config

    def fake_root():
        calls['root'] += 1
        return app_root

    def fake_write(*args, **kwargs):
        calls['write'] += 1
        return real_write(*args, **kwargs)

    monkeypatch.setattr(bootstrap_module, '_detect_packaged_mode', lambda: True)
    monkeypatch.setattr(bootstrap_module, '_get_packaged_root', fake_root)
    monkeypatch.setattr(bootstrap_module, '_write_packaged_config', fake_write)

    first = bootstrap_module.bootstrap_runtime()
    second = bootstrap_module.bootstrap_runtime()

    assert first == second
    assert calls == {'root': 1, 'write': 1}


def test_write_packaged_config_writes_expected_sections(bootstrap_module, tmp_path):
    cfg_path = tmp_path / 'db_config.ini'
    data_dir = tmp_path / 'data'
    tmp_dir = tmp_path / 'tmp'

    bootstrap_module._write_packaged_config(cfg_path, data_dir, tmp_dir)

    cfg = configparser.ConfigParser()
    cfg.read(cfg_path, encoding='utf-8')
    assert cfg.sections() == ['database', 'sqlite', 'paths']
    assert cfg.get('database', 'backend') == 'sqlite'
    assert cfg.get('sqlite', 'sqlite_filename') == 'TradeDangerous.db'
    assert cfg.get('paths', 'data_dir') == str(data_dir)
    assert cfg.get('paths', 'tmp_dir') == str(tmp_dir)


def test_detect_packaged_mode_false_when_registry_missing_or_wrong(bootstrap_module, monkeypatch):
    monkeypatch.setattr(bootstrap_module, 'winreg', _fake_winreg('packaged', 1, should_raise=True))
    assert bootstrap_module._detect_packaged_mode() is False

    monkeypatch.setattr(bootstrap_module, 'winreg', _fake_winreg('not-packaged', 1))
    assert bootstrap_module._detect_packaged_mode() is False

    monkeypatch.setattr(bootstrap_module, 'winreg', _fake_winreg('packaged', 999))
    assert bootstrap_module._detect_packaged_mode() is False


def test_get_packaged_root_requires_LOCALAPPDATA(bootstrap_module, monkeypatch):
    monkeypatch.delenv('LOCALAPPDATA', raising=False)

    with pytest.raises(RuntimeError, match='LOCALAPPDATA'):
        bootstrap_module._get_packaged_root()


def test_trade_main_bootstraps_then_calls_cli_main(monkeypatch):
    import trade
    import tradedangerous

    module = importlib.reload(trade)
    calls = []

    monkeypatch.setattr(module, 'bootstrap_runtime', lambda: calls.append('bootstrap'))
    fake_cli = ModuleType('tradedangerous.cli')
    fake_cli.main = lambda argv: calls.append(('cli', list(argv)))
    monkeypatch.setitem(sys.modules, 'tradedangerous.cli', fake_cli)
    monkeypatch.setattr(tradedangerous, 'cli', fake_cli, raising=False)

    module.main(['trade.py', 'local', 'sol'])

    assert calls == ['bootstrap', ('cli', ['trade.py', 'local', 'sol'])]


def test_tradegui_main_unpacked_delegates_to_gui_main(monkeypatch):
    import tradegui

    module = importlib.reload(tradegui)
    calls = []

    monkeypatch.setattr(module, 'bootstrap_runtime', lambda: {'packaged_mode': False})
    fake_gui_main = ModuleType('tradedangerous.guiapp.main')
    fake_gui_main.main = lambda argv: calls.append(list(argv)) or 99
    monkeypatch.setitem(sys.modules, 'tradedangerous.guiapp.main', fake_gui_main)

    result = module.main(['tradegui.py', '--test'])

    assert result == 99
    assert calls == [['tradegui.py', '--test']]


def test_write_crash_log_includes_runtime_context(tmp_path):
    import tradegui

    module = importlib.reload(tradegui)
    runtime = {
        'packaged_mode': True,
        'db_config': tmp_path / 'db_config.ini',
        'data_dir': tmp_path / 'data',
        'tmp_dir': tmp_path / 'tmp',
        'logs_dir': tmp_path / 'logs',
    }

    try:
        raise RuntimeError('boom')
    except RuntimeError:
        log_path = module._write_crash_log(runtime)

    text = log_path.read_text(encoding='utf-8')
    assert 'timestamp:' in text
    assert 'python:' in text
    assert 'platform:' in text
    assert 'packaged_mode: True' in text
    assert f"db_config: {runtime['db_config']}" in text
    assert f"data_dir: {runtime['data_dir']}" in text
    assert f"tmp_dir: {runtime['tmp_dir']}" in text
    assert 'RuntimeError: boom' in text
