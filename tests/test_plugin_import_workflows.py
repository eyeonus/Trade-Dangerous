import io
import sys
from types import SimpleNamespace

import pytest

from tradedangerous.commands import buildcache_cmd, import_cmd
from tradedangerous.commands.exceptions import CommandLineError
from tradedangerous.plugins import PluginBase, PluginException
import tradedangerous.plugins as plugins


class ExamplePlugin(PluginBase):
    """Example plugin used to exercise shared plugin option behaviour."""

    pluginOptions = {
        'alpha': 'Enable the alpha behaviour.',
        'beta': 'Enable the beta behaviour.',
    }

    def run(self):
        return True

    def finish(self):
        return True


class NoOptionsPlugin(PluginBase):
    """Plugin with no options."""

    def run(self):
        return True

    def finish(self):
        return True


def test_plugin_base_unknown_option_lists_valid_choices():
    tdenv = SimpleNamespace(pluginOptions=['gamma=1'])

    with pytest.raises(PluginException, match='Valid options for this plugin'):
        ExamplePlugin(None, tdenv)


def test_plugin_base_help_option_emits_usage():
    tdenv = SimpleNamespace(pluginOptions=['help'])

    with pytest.raises(SystemExit) as excinfo:
        ExamplePlugin(None, tdenv)

    message = str(excinfo.value)
    assert 'Example plugin used to exercise shared plugin option behaviour.' in message
    assert '--opt=alpha' in message
    assert '--opt=beta' in message


def test_plugin_base_reports_no_options_when_none_supported():
    tdenv = SimpleNamespace(pluginOptions=['alpha'])

    with pytest.raises(PluginException, match='does not support any options'):
        NoOptionsPlugin(None, tdenv)


def test_plugin_loader_resolves_expected_module_name(monkeypatch):
    calls = []

    def fake_import_module(name):
        calls.append(name)
        return SimpleNamespace(ImportPlugin=ExamplePlugin)

    monkeypatch.setattr(plugins.importlib, 'import_module', fake_import_module)

    plugin_class = plugins.load('SpAnSh', 'ImportPlugin')

    assert plugin_class is ExamplePlugin
    assert calls == ['tradedangerous.plugins.spansh_plug']


def _fake_tdb(tmp_path):
    return SimpleNamespace(
        dataPath=tmp_path,
        dbPath=tmp_path / 'TradeDangerous.db',
        dbFilename='TradeDangerous.db',
        sqlPath=tmp_path / 'TradeDangerous.sql',
        sqlFilename='TradeDangerous.sql',
        engine=SimpleNamespace(dialect=SimpleNamespace(name='sqlite')),
        reloadCache=lambda: None,
        close=lambda: None,
        removePerist=lambda: None,
    )


def test_import_cmd_plugin_path_skips_legacy_banner_when_plugin_handles_work(monkeypatch, capsys, tmp_path):
    class _ImportPlugin:
        def __init__(self, _tdb, _cmdenv):
            pass

        def run(self):
            return False

    monkeypatch.setattr(import_cmd.plugins, 'load', lambda name, type_name: _ImportPlugin)
    cmdenv = SimpleNamespace(
        plug='spansh',
        pluginOptions=[],
        filename=None,
        url=None,
        download=False,
    )

    result = import_cmd.run(None, cmdenv, _fake_tdb(tmp_path))
    captured = capsys.readouterr()

    assert result is False
    assert 'DEPRECATION NOTICE' not in captured.out


def test_import_cmd_http_filename_is_treated_as_url(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(import_cmd.transfers, 'download', lambda tdenv, url, filename: calls.append((url, filename)))
    monkeypatch.setattr(import_cmd.cache, 'importDataFromFile', lambda *args, **kwargs: pytest.fail('legacy import should not run'))

    cmdenv = SimpleNamespace(
        plug=None,
        pluginOptions=[],
        filename='https://example.invalid/import.prices',
        url=None,
        download=True,
        reset=False,
    )

    result = import_cmd.run(None, cmdenv, _fake_tdb(tmp_path))

    assert result is False
    assert cmdenv.url == 'https://example.invalid/import.prices'
    assert cmdenv.filename == 'import.prices'
    assert calls == [('https://example.invalid/import.prices', 'import.prices')]


def test_import_cmd_download_only_short_circuits_after_transfer(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(import_cmd.transfers, 'download', lambda tdenv, url, filename: calls.append((url, filename)))
    monkeypatch.setattr(import_cmd.cache, 'importDataFromFile', lambda *args, **kwargs: pytest.fail('legacy import should not run'))

    cmdenv = SimpleNamespace(
        plug=None,
        pluginOptions=[],
        filename='batch.prices',
        url='https://example.invalid/batch.prices',
        download=True,
        reset=False,
    )

    result = import_cmd.run(None, cmdenv, _fake_tdb(tmp_path))

    assert result is False
    assert calls == [('https://example.invalid/batch.prices', 'batch.prices')]


def test_import_cmd_stdin_path_is_accepted(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(import_cmd.cache, 'importDataFromFile', lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(sys, 'stdin', io.StringIO('Station data'))

    cmdenv = SimpleNamespace(
        plug=None,
        pluginOptions=[],
        filename='-',
        url=None,
        download=False,
        reset=False,
    )

    result = import_cmd.run(None, cmdenv, _fake_tdb(tmp_path))

    assert result is False
    assert calls[0][0][2] == 'stdin'
    assert calls[0][1]['pricesFh'] is sys.stdin
    assert calls[0][1]['reset'] is False


def test_buildcache_cmd_requires_force_if_db_exists(tmp_path):
    tdb = _fake_tdb(tmp_path)
    tdb.dbPath.touch()
    tdb.sqlPath.write_text('-- sql', encoding='utf-8')
    cmdenv = SimpleNamespace(force=False)

    with pytest.raises(CommandLineError, match='already exists'):
        buildcache_cmd.run(None, cmdenv, tdb)


def test_buildcache_cmd_requires_sql_file(tmp_path):
    tdb = _fake_tdb(tmp_path)
    cmdenv = SimpleNamespace(force=True)

    with pytest.raises(CommandLineError, match='SQL File does not exist'):
        buildcache_cmd.run(None, cmdenv, tdb)


def test_buildcache_cmd_delegates_to_lifecycle(monkeypatch, tmp_path):
    calls = []
    tdb = _fake_tdb(tmp_path)
    cmdenv = SimpleNamespace(force=True)
    tdb.sqlPath.write_text('-- sql', encoding='utf-8')
    monkeypatch.setattr(buildcache_cmd, 'ensure_fresh_db', lambda **kwargs: calls.append(kwargs))

    result = buildcache_cmd.run(None, cmdenv, tdb)

    assert result is False
    assert calls[0]['backend'] == 'sqlite'
    assert calls[0]['engine'] is tdb.engine
    assert calls[0]['data_dir'] == tdb.dataPath
    assert calls[0]['mode'] == 'force'
    assert calls[0]['tdb'] is tdb
    assert calls[0]['tdenv'] is cmdenv
    assert calls[0]['rebuild'] is True
