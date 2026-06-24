from __future__ import annotations

import re

from .helpers import isolated_trade_env, strip_ansi

PROG = "trade"

class TestTradeRun:
    def test_run_finds_profitable_route(self, isolated_trade_env, capsys):
        trade = isolated_trade_env["trade"]
        
        trade([
            PROG, "run",
            "--capacity=10", "--credits=10000",
            "--from=sol/abr", "--jumps-per=3",
            "--ly-per=10.5", "--no-planet",
        ])
        captured = capsys.readouterr()
        output = strip_ansi(captured.out)
        
        assert "Sol/Abraham Lincoln" in output
        assert re.search(r"Sol/Abraham Lincoln -> .+/.+", output)
        assert re.search(r"^\s{2}.+?: \d+ x .+,$", output, re.MULTILINE)
        assert re.search(r"\+\d[\d,]*cr \(\d[\d,]*/ton\)", output)


class TestRunBareNameResolution:
    """trade run resolves --from through the global place contract: a bare name
    is system-first then station-fallback, and a fuzzy hit echoes 'resolved as'.

    Confirms the planner inherits the shared TradeORM.lookup_place contract —
    the same resolution the non-planner commands use — rather than a strict
    system-only namespace."""

    def test_run_from_bare_station_partial_resolves_and_echoes(self, isolated_trade_env, capsys):
        trade = isolated_trade_env["trade"]
        trade([
            PROG, "run",
            "--capacity=10", "--credits=10000",
            "--from=hamlinc", "--jumps-per=3", "--ly-per=10.5",
        ])
        output = strip_ansi(capsys.readouterr().out)
        # Bare "hamlinc" is no system, so it falls back to the station and the
        # fuzzy expansion is echoed.
        assert "resolved as Sol/Abraham Lincoln" in output
        assert "unknown system" not in output.lower()

    def test_run_from_explicit_station_resolves(self, isolated_trade_env, capsys):
        trade = isolated_trade_env["trade"]
        trade([
            PROG, "run",
            "--capacity=10", "--credits=10000",
            "--from=/hamlinc", "--jumps-per=3", "--ly-per=10.5",
        ])
        output = strip_ansi(capsys.readouterr().out)
        assert "Sol/Abraham Lincoln" in output
        assert "unknown" not in output.lower()
