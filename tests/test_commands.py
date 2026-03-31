#! /usr/bin/env python
# pytest

import pytest

from tradedangerous import commands
from tradedangerous.commands.exceptions import UsageError, CommandLineError


@pytest.fixture
def cmd():
    return commands.CommandIndex()


prog = 'trade.py'


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

    def test_usage_lists_commands(self, cmd):
        usage = cmd.usage([prog])

        assert 'Where <command> is one of:' in usage
        assert 'buildcache' in usage
        assert 'local' in usage
        assert 'run' in usage
        assert f'  {prog} ' in usage

    def test_reports_ambiguous_abbreviation(self, cmd):
        with pytest.raises(CommandLineError, match="Ambiguous command, 's'"):
            cmd.parse([prog, 's'])

    def test_injects_tdrc_for_selected_command(self, cmd, monkeypatch, tmp_path):
        tdrc = tmp_path / '.tdrc_local'
        tdrc.write_text('--ly\n10\nsol\n', encoding='utf-8')
        monkeypatch.chdir(tmp_path)

        parsed = cmd.parse([prog, 'local'])

        assert parsed.argv[2] == f'+{tdrc.resolve()}'
        assert parsed.near == 'sol'
        assert parsed.ly == 10.0
