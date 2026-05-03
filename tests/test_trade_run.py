from __future__ import annotations

import re

import pytest

from tradedangerous.commands.exceptions import CommandLineError

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
    
    def test_run_rejects_stale_explicit_destination_with_age(
        self,
        isolated_trade_env,
        capsys,
        monkeypatch,
    ):
        trade = isolated_trade_env["trade"]
        
        import tradedangerous.tradedb as tradedb_module
        import tradedangerous.tradecalc as tradecalc_module
        
        original_load_station_summaries = tradedb_module.TradeDB._loadStationSummaries
        original_tradecalc_init = tradecalc_module.TradeCalc.__init__

        def patched_load_station_summaries(self):
            original_load_station_summaries(self)
            stale_station = self.lookupStation(
                "Burnell Station",
                self.lookupSystem("Sol"),
            )
            stale_station.dataAge = 999.0

        def patched_tradecalc_init(self, tdb, tdenv=None, *args, **kwargs):
            active_tdenv = tdenv or tdb.tdenv
            original_max_age = active_tdenv.maxAge
            active_tdenv.maxAge = 0
            try:
                return original_tradecalc_init(
                    self,
                    tdb,
                    tdenv=tdenv,
                    *args,
                    **kwargs,
                )
            finally:
                active_tdenv.maxAge = original_max_age

        monkeypatch.setattr(
            tradedb_module.TradeDB,
            "_loadStationSummaries",
            patched_load_station_summaries,
        )
        monkeypatch.setattr(
            tradecalc_module.TradeCalc,
            "__init__",
            patched_tradecalc_init,
        )
        
        with pytest.raises(
            CommandLineError,
            match=r"does not meet --age requirement",
        ):
            trade([
                PROG, "run",
                "--capacity=10", "--credits=10000",
                "--from=sol/abr", "--to=sol/burnell",
                "--jumps-per=3", "--ly-per=10.5",
                "--age=1",
            ])
        
        capsys.readouterr()
