import sys
import os
import re
from time import sleep
from io import StringIO
from pathlib import Path
from contextlib import contextmanager

from tradedangerous.tradedb import TradeDB
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

@contextmanager
def replace_stdin(target):
    orig = sys.stdin
    sys.stdin = target
    yield
    sys.stdin = orig


def tdfactory():
    """Generates a usable environment with debug
    Returns
    -------
    [TradeEnv, TradeDB]
        list with instances of TradeEnv and TradeDB
    """
    return [TradeDB(tdenv=tdenv, load=True, debug=3), tdenv]


def file_exists(filename):
    return Path(filename).is_file()

def is_initialized():
    return Path(tdenv.dataDir, 'TradeDangerous.db').is_file()

def empty_path(p):
    """Deletes a directory tree including files
    """
    if p.exists() and p.is_dir():
        # print("cleaning up", p)
        for entry in p.glob('*'):
            if entry.is_file():
                # print("removing file", entry)
                entry.unlink()
            elif entry.is_dir() and entry != p:
                empty_path(entry)
        # print("removing directory", entry)
        p.rmdir()
    elif p.is_file():
        # print("removing file p", entry)
        p.unlink()


def remove_fixtures(toDir=None):
    if not toDir:
        toDir = tdenv.dataDir
    toPath = Path(toDir)
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
