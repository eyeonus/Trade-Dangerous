from pathlib import Path
from types import SimpleNamespace

from tradedangerous import corrections
from tradedangerous.db import paths as db_paths
from tradedangerous.tradeenv import BaseColorTheme, NonUtf8ConsoleIOMixin, TradeEnv


class _Recorder:
    def __init__(self, *, fail_once=False):
        self.calls = []
        self.fail_once = fail_once

    def print(self, *args, **kwargs):
        if self.fail_once:
            self.fail_once = False
            raise UnicodeEncodeError('ascii', 'é', 0, 1, 'fail')
        self.calls.append((args, kwargs))


class _NonUtf8Dummy(NonUtf8ConsoleIOMixin):
    def __init__(self, console, stderr):
        self.console = console
        self.stderr = stderr
        self.quiet = 0
        self.theme = BaseColorTheme()


def test_corrections_are_case_insensitive():
    assert corrections.correctSystem('pandamonium') == 'PANDEMONIUM'
    assert corrections.correctItem('void opals') == 'Void Opal'
    assert corrections.correctCategory('foods') == 'foods'
    assert corrections.correctStation('sol', 'abraham lincoln') == 'abraham lincoln'


def test_tradeenv_debug_note_warn_methods_respect_quiet_and_debug():
    console = _Recorder()
    stderr = _Recorder()
    env = TradeEnv(console=console, stderr=stderr, debug=1, quiet=0, color=False)
    env.theme = BaseColorTheme()

    note = env.NOTE
    assert note is env.NOTE

    env.DEBUG0('debug {}', 'line')
    env.DEBUG1('hidden debug')
    env.NOTE('note line')
    env.WARN('warn line')

    rendered = [args[0] for args, _kwargs in console.calls]
    assert '#0: debug line' in rendered
    assert 'NOTE: note line' in rendered
    assert 'WARNING: warn line' in rendered
    assert not any('hidden debug' in line for line in rendered)

    quiet_console = _Recorder()
    quiet_env = TradeEnv(console=quiet_console, stderr=_Recorder(), quiet=1, color=False)
    quiet_env.theme = BaseColorTheme()
    quiet_env.NOTE('silenced')
    assert quiet_console.calls == []


def test_tradeenv_non_utf8_fallback_replaces_unencodable_output(monkeypatch):
    console = _Recorder(fail_once=True)
    stderr = _Recorder()
    dummy = _NonUtf8Dummy(console, stderr)
    monkeypatch.setattr(TradeEnv, 'encoding', 'ascii', raising=False)

    dummy.uprint('café')

    assert console.calls == [(('caf?',), {'style': None})]
    assert 'CAUTION:' in stderr.calls[0][0][0]


def test_paths_resolve_data_tmp_and_db_config_precedence(monkeypatch, tmp_path):
    monkeypatch.delenv('TD_DATA', raising=False)
    monkeypatch.delenv('TD_TMP', raising=False)
    monkeypatch.delenv('TD_DB_CONFIG', raising=False)
    monkeypatch.chdir(tmp_path)
    cfg = {
        'paths': {
            'data_dir': 'cfg-data',
            'tmp_dir': 'cfg-tmp',
        },
        'sqlite': {
            'sqlite_filename': 'custom.db',
        },
    }

    data_dir = db_paths.resolve_data_dir(cfg)
    tmp_dir = db_paths.resolve_tmp_dir(cfg)
    db_path = db_paths.get_sqlite_db_path(cfg)
    cfg_path = db_paths.resolve_db_config_path('db_config.ini')

    assert data_dir == (tmp_path / 'cfg-data')
    assert tmp_dir == (tmp_path / 'cfg-tmp')
    assert db_path == (tmp_path / 'cfg-data' / 'custom.db').resolve()
    assert cfg_path == (tmp_path / 'db_config.ini')

    monkeypatch.setenv('TD_DATA', str(tmp_path / 'env-data'))
    monkeypatch.setenv('TD_TMP', str(tmp_path / 'env-tmp'))
    monkeypatch.setenv('TD_DB_CONFIG', str(tmp_path / 'env-db.ini'))

    assert db_paths.resolve_data_dir(cfg) == (tmp_path / 'env-data')
    assert db_paths.resolve_tmp_dir(cfg) == (tmp_path / 'env-tmp')
    assert db_paths.resolve_db_config_path() == (tmp_path / 'env-db.ini')
