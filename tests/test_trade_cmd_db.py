from __future__ import annotations

import re

from .helpers import isolated_trade_env, strip_ansi

PROG = "trade"

class TestTradeCommand:
    def test_trade_command_returns_profitable_rows_for_real_station_pair(
        self,
        isolated_trade_env,
        capsys,
    ):
        trade = isolated_trade_env["trade"]
        
        trade([
            PROG, "trade",
            "Sol/Abraham Lincoln",
            "Sol/Burnell Station",
        ])
        captured = capsys.readouterr()
        output = strip_ansi(captured.out)
        
        assert "From: Sol/Abraham Lincoln" in output
        assert "To: Sol/Burnell Station" in output
        assert "trades found" in output
        assert "Hydrogen Fuel" in output
        assert re.search(r"\bHydrogen Fuel\b", output)
        assert re.search(r"\bProfit\b", output)
        assert re.search(r"\bCost\b", output)
        assert re.search(r"\bBuying\b", output)
    
    def test_trade_command_limit_restricts_result_rows(
        self,
        isolated_trade_env,
        capsys,
    ):
        trade = isolated_trade_env["trade"]
        
        trade([
            PROG, "trade",
            "--limit", "1",
            "Sol/Abraham Lincoln",
            "Sol/Burnell Station",
        ])
        captured = capsys.readouterr()
        output = strip_ansi(captured.out)
        
        data_lines = [
            line
            for line in output.splitlines()
            if line.strip()
            and "trades found" not in line
            and "From:" not in line
            and "Item" not in line
            and set(line.strip()) != {"-"}
        ]

        assert "From: Sol/Abraham Lincoln" in output
        assert "To: Sol/Burnell Station" in output
        assert len(data_lines) == 1
        assert "Hydrogen Fuel" in data_lines[0]
    
    def test_trade_command_load_and_full_load_use_game_cargo_values(
        self,
        isolated_trade_env,
        capsys,
        monkeypatch,
    ):
        from types import SimpleNamespace
        
        import tradedangerous.commands.direct_cmd as direct_cmd_module
        
        class FakeGame:
            def __init__(self, tdenv=None, extra_jsons=None):
                self.tdenv = tdenv
                self.extra_jsons = extra_jsons or []
            
            def get_status(self):
                return SimpleNamespace(cargo_space=7, cargo_load=2)
        
        monkeypatch.setattr(direct_cmd_module, "EliteGame", FakeGame)
        monkeypatch.setattr(direct_cmd_module, "require_game_data", lambda *args, **kwargs: None)
        
        trade = isolated_trade_env["trade"]
        
        trade([
            PROG, "trade",
            "--load",
            "Sol/Abraham Lincoln",
            "Sol/Burnell Station",
        ])
        load_output = strip_ansi(capsys.readouterr().out)
        
        trade([
            PROG, "trade",
            "--full-load",
            "Sol/Abraham Lincoln",
            "Sol/Burnell Station",
        ])
        full_load_output = strip_ansi(capsys.readouterr().out)
        
        assert re.search(r"\bUnits\b", load_output)
        assert "Total Units: 5." in load_output
        
        assert re.search(r"\bUnits\b", full_load_output)
        assert "Total Units: 7." in full_load_output
