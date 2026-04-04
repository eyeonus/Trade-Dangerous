from __future__ import annotations

import re

import pytest

from .helpers import isolated_trade_env, strip_ansi

PROG = "trade"


class TestTrade::
    def test_local_help(self, isolated_trade_env):
        trade = isolated_trade_env["trade"]
        usage_error = isolated_trade_env["UsageError"]

        with pytest.raises(usage_error):
            trade([PROG, "local", "-h"])

    def test_local_sol(self, isolated_trade_env, capsys):
        trade = isolated_trade_env["trade"]

        trade([PROG, "local", "--ly=10", "--detail", "sol"])
        captured = capsys.readouterr()

        assert "Sol" in captured.out
        assert "Ehrlich City" in captured.out

    def test_sell(self, isolated_trade_env, capsys):
        trade = isolated_trade_env["trade"]

        trade([PROG, "sell", "--near=sol", "hydrogen fuel"])
        captured = capsys.readouterr()

        assert "Sol/Mars High" in captured.out

    def test_buy(self, isolated_trade_env, capsys):
        trade = isolated_trade_env["trade"]

        trade([PROG, "buy", "--near=sol", "hydrogen fuel"])
        captured = capsys.readouterr()

        assert "Cost" in captured.out
        assert "Units" in captured.out
        assert "Sol/" in captured.out

    def test_export_system_table_writes_csv(self, isolated_trade_env, capsys):
        trade = isolated_trade_env["trade"]
        export_dir = isolated_trade_env["export_dir"]

        trade([PROG, "export", "-T", "System", "--path", str(export_dir)])
        captured = capsys.readouterr()
        output = strip_ansi(captured.out)

        out_path = export_dir / "System.csv"
        assert "Export Table 'System'" in output
        assert out_path.exists()

        text = out_path.read_text(encoding="utf-8")
        assert "Sol" in text

    def test_nav(self, isolated_trade_env, capsys):
        trade = isolated_trade_env["trade"]

        trade([PROG, "nav", "--ly-per=50", "sol", "Alpha Centauri"])
        captured = capsys.readouterr()

        assert "Sol" in captured.out
        assert "Alpha Centauri" in captured.out

    def test_market(self, isolated_trade_env, capsys):
        trade = isolated_trade_env["trade"]

        trade([PROG, "market", "sol/abr"])
        captured = capsys.readouterr()

        assert "Hydrogen Fuel" in captured.out
        assert "Water" in captured.out
        assert re.search(r"\bBuying\b", captured.out)
        assert re.search(r"\bSelling\b", captured.out)