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
