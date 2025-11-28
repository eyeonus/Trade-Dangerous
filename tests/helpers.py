from pathlib import Path
from contextlib import contextmanager
import gc
import os
import re
import shutil
import sys
import typing

from tradedangerous import fs, TradeEnv

_ROOT = os.path.abspath(os.path.dirname(__file__))
_DEBUG = 5
tdenv = TradeEnv(debug=_DEBUG)

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
    
    def __repr__(self):
        return self._regex.pattern

def regex_findin(pattern, value):
    return bool(re.search(pattern, value))
