from __future__ import annotations

import re

import pytest

from tradedangerous.commands.exceptions import CommandLineError

from .test_trade import isolated_trade_env, strip_ansi

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
        assert "Burnell Station" in output
        assert "Hydrogen Fuel" in output
        assert re.search(r"\b\d[\d,]*cr \(\d+/ton\)", output)

    def test_run_rejects_stale_explicit_destination_with_age(
        self,
        isolated_trade_env,
        capsys,
        monkeypatch,
    ):
        trade = isolated_trade_env["trade"]

        import tradedangerous.tradedb as tradedb_module

        original_load_stations = tradedb_module.TradeDB._loadStations

        def patched_load_stations(self):
            original_load_stations(self)
            stale_station = self.lookupStation(
                "Burnell Station",
                self.lookupSystem("Sol"),
            )
            stale_station.dataAge = 999.0

        monkeypatch.setattr(
            tradedb_module.TradeDB,
            "_loadStations",
            patched_load_stations,
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