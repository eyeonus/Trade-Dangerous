import sys
import os
import re
from pathlib import Path
from contextlib import contextmanager
from io import StringIO

from tradedangerous import fs, TradeEnv

__all__ = ['tdenv', 'captured_output', 'is_initialized']

_ROOT = os.path.abspath(os.path.dirname(__file__))
tdenv = TradeEnv(debug=3)

@contextmanager
def captured_output():
    new_out, new_err = StringIO(), StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = old_out, old_err

def file_exists(filename):
    return Path(filename).is_file()

def is_initialized():
    return Path(tdenv.dataDir, 'TradeDangerous.db').is_file()

def copy_fixtures(toDir=None):
    if not toDir:
        toDir = tdenv.dataDir
    toPath = Path(toDir)
    print("will copy fixures to {}".format(toPath))
    # clean old
    def empty_p(p):
        if p.exists() and p.is_dir():
            print("cleaning up", p)
            for entry in p.glob('*'):
                if entry.is_file():
                    print("removing file", entry)
                    entry.unlink()
                elif entry.is_dir() and entry != p:
                    empty_p(entry)
            print("removing directory", entry)
            p.rmdir()
        elif p.is_file():
            print("removing file p", entry)
            p.unlink()
    print("but first clean old")
    empty_p(toPath)
    fs.ensurefolder(toDir)

    fs.copyallfiles(tdenv.templateDir, tdenv.dataDir)
    fs.copyallfiles(Path(_ROOT, 'fixtures'), tdenv.dataDir)
    fs.ensureflag(Path(tdenv.dataDir, '.tddata'))
    touch(Path(tdenv.dataDir, 'TradeDangerous.db'))


def touch(*args):
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
