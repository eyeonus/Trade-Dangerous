#! /usr/bin/env python
# pytest

import pytest
from tradedangerous import commands
from tradedangerous.commands.exceptions import UsageError, CommandLineError

@pytest.fixture
def cmd():
    return commands.CommandIndex()


prog = "trade.py"


class TestCommands:
    
    def test_dashh(self, cmd):
        with pytest.raises(UsageError):
            cmd.parse([prog, '-h'])
    
    def test_local_dashh(self, cmd):
        with pytest.raises(UsageError):
            cmd.parse([prog, 'local', '-h'])
    
    def test_invalid_cmd(self, cmd):
        with pytest.raises(CommandLineError):
            cmd.parse([prog, 'fnarg'])
    
    def test_local_no_args(self, cmd):
        with pytest.raises(CommandLineError):
            cmd.parse([prog, 'local'])
    
    def test_local_dashv(self, cmd):
        with pytest.raises(CommandLineError):
            cmd.parse([prog, 'local', '-v'])
    
    def test_local_validsys(self, cmd):
        cmd.parse([prog, 'local', 'ibootis'])
    
    def test_local_validsys_dashv(self, cmd):
        cmd.parse([prog, 'local', 'ibootis', '-v'])
