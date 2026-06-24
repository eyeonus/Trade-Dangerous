from pathlib import Path
from contextlib import contextmanager
import configparser
import gc
import os
import re
import shutil
import sys
import typing

import pytest

from tradedangerous import fs, TradeEnv

_ROOT = os.path.abspath(os.path.dirname(__file__))
_DEBUG = 5
tdenv = TradeEnv(debug=_DEBUG)

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)

def _copy_fixture_pack(src: Path, dst: Path) -> None:
    for entry in src.iterdir():
        if entry.is_file():
            shutil.copy2(entry, dst / entry.name)

def _write_db_config(cfg_path: Path, data_dir: Path, tmp_dir: Path) -> None:
    cp = configparser.ConfigParser()
    cp["database"] = {"backend": "sqlite"}
    cp["sqlite"] = {"sqlite_filename": "TradeDangerous.db"}
    cp["paths"] = {
        "data_dir": str(data_dir),
        "tmp_dir": str(tmp_dir),
    }
    with cfg_path.open("w", encoding="utf-8") as fh:
        cp.write(fh)

def _build_isolated_trade_env(tmp_path, monkeypatch):
    tests_dir = Path(__file__).resolve().parent
    fixtures_dir = tests_dir / "fixtures"
    
    data_dir = tmp_path / "data"
    tmp_dir = tmp_path / "tmp"
    export_dir = tmp_path / "export"
    data_dir.mkdir()
    tmp_dir.mkdir()
    export_dir.mkdir()
    
    _copy_fixture_pack(fixtures_dir, data_dir)
    
    cfg_path = data_dir / "db_config.ini"
    _write_db_config(cfg_path, data_dir, tmp_dir)
    
    monkeypatch.setenv("TD_DATA", str(data_dir))
    monkeypatch.setenv("TD_CSV", str(data_dir))
    monkeypatch.setenv("TD_TMP", str(tmp_dir))
    monkeypatch.setenv("TD_DB_CONFIG", str(cfg_path))
    
    import tradedangerous.cli as cli_module
    import tradedangerous.commands.exceptions as exceptions_module
    
    return {
        "trade": cli_module.trade,
        "UsageError": exceptions_module.UsageError,
        "data_dir": data_dir,
        "tmp_dir": tmp_dir,
        "export_dir": export_dir,
    }

@pytest.fixture()
def isolated_trade_env(tmp_path, monkeypatch):
    return _build_isolated_trade_env(tmp_path, monkeypatch)

@contextmanager
def replace_stdin(target: typing.TextIO):  
    orig: typing.TextIO = sys.stdin
    sys.stdin = target
    yield
    sys.stdin = orig

def empty_path(p: Path) -> None:
    """Deletes a directory tree including files"""
    # The way we wind down TradeDB and SQLAlchemy may sometimes
    # result in a lingering reference to the database that is waiting
    # to be garbage collected. Force one here.
    gc.collect()  # Ensure we're not holding onto any files
    
    if p.exists() and p.is_dir():
        shutil.rmtree(p)
    elif p.is_file():
        p.unlink()

def remove_fixtures(toDir: str | Path | None = None) -> None:
    toPath = Path(toDir or tdenv.dataDir)
    empty_path(toPath)

def copy_fixtures(toDir=None):
    if not toDir:
        toDir = tdenv.dataDir
    toPath = Path(toDir)
    print("will copy fixures to {}".format(toPath))
    print("but first clean old")
    empty_path(toPath)
    fs.ensurefolder(toDir)
    
    fs.copyallfiles(tdenv.templateDir, tdenv.dataDir)
    fs.copyallfiles(Path(_ROOT, 'fixtures'), tdenv.dataDir)
    touch(Path(tdenv.dataDir, 'TradeDangerous.db'))
    print("copy fixtures done")

def touch(*args: str | Path) -> Path:
    filename = Path(*args)
    return fs.touch(filename)

class pytest_regex:
    """Assert that a given string meets some expectations."""
    
    def __init__(self, pattern, flags=0):
        self._regex = re.compile(pattern, flags)
    
    def __eq__(self, actual):
        return bool(self._regex.match(actual))
    
    def __hash__(self):
        return hash(self._regex)
    
    def __repr__(self):
        return self._regex.pattern

def regex_findin(pattern, value):
    return bool(re.search(pattern, value))
