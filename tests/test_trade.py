from __future__ import annotations

import configparser
import importlib
import re
import shutil
from pathlib import Path

import pytest

PROG = "trade"

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)
    
def _copy_fixture_pack(src: Path, dst: Path) -> None:
    for entry in src.iterdir():
        if entry.is_file():
            shutil.copy2(entry, dst / entry.name)


def _write_db_config(cfg_path: Path, data_dir: Path, tmp_dir: Path) -> None:
    cp = configparser.ConfigParser()
    cp["database"] = {"backend": "sqlite"}
    cp["sqlite"] = {"sqlite_filename": "TradeDangerous.db"}
    cp["paths"] = {
        "data_dir": str(data_dir),
        "tmp_dir": str(tmp_dir),
    }
    with cfg_path.open("w", encoding="utf-8") as fh:
        cp.write(fh)


@pytest.fixture()
def isolated_trade_env(tmp_path, monkeypatch):
    tests_dir = Path(__file__).resolve().parent
    fixtures_dir = tests_dir / "fixtures"

    data_dir = tmp_path / "data"
    tmp_dir = tmp_path / "tmp"
    export_dir = tmp_path / "export"
    data_dir.mkdir()
    tmp_dir.mkdir()
    export_dir.mkdir()

    _copy_fixture_pack(fixtures_dir, data_dir)

    cfg_path = data_dir / "db_config.ini"
    _write_db_config(cfg_path, data_dir, tmp_dir)

    monkeypatch.setenv("TD_DATA", str(data_dir))
    monkeypatch.setenv("TD_CSV", str(data_dir))
    monkeypatch.setenv("TD_TMP", str(tmp_dir))
    monkeypatch.setenv("TD_DB_CONFIG", str(cfg_path))

    import tradedangerous.tradeenv as tradeenv_module
    import tradedangerous.tradedb as tradedb_module
    import tradedangerous.cli as cli_module
    import tradedangerous.commands.exceptions as exceptions_module

    return {
        "trade": cli_module.trade,
        "UsageError": exceptions_module.UsageError,
        "data_dir": data_dir,
        "tmp_dir": tmp_dir,
        "export_dir": export_dir,
    }


class TestTrade:
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