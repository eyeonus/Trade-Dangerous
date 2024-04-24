import pytest

from tradedangerous.cli import trade
from tradedangerous.commands.exceptions import UsageError
from .helpers import copy_fixtures, regex_findin, remove_fixtures

PROG = "trade"


def setup_module():
    copy_fixtures()


def teardown_module():
    remove_fixtures()


class TestTrade:
    def test_local_help(self):
        with pytest.raises(UsageError):
            trade([PROG, "local", "-h"])
    
    def test_local_sol(self, capsys):
        trade([PROG, "local", "--ly=10", "--detail", "sol"])
        captured = capsys.readouterr()
        assert "Sol       0" in captured.out
        assert "Ehrlich City" in captured.out
    
    def test_sell(self, capsys):
        trade([PROG, "sell", "--near=sol", "hydrogen fuel"])
        captured = capsys.readouterr()
        assert "Sol/Mars High" in captured.out
    
    def test_buy(self, capsys):
        trade([PROG, "buy", "--near=sol", "hydrogen fuel"])
        captured = capsys.readouterr()
        assert "Cost      Units DistLy Age/days" in captured.out
    
    def test_export_station(self, capsys):
        trade([PROG, "export", "-T", "System"])
        captured = capsys.readouterr()
        assert "NOTE: Export Table 'System'" in captured.out
        # TODO: check that System.csv has a fresh date
    
    def test_station_remove(self, capsys):
        # "Dekker's Yard"
        trade([PROG, "station", "-rm", "sol/dekkers"])
        captured = capsys.readouterr()
        assert regex_findin(r"NOTE: Sol/Dekker's Yard \(#\d+\) removed", captured.out)
    
    def test_station_add(self, capsys):
        # "Dekker's Yard"
        trade([
            PROG, "station", "--add", "--ls-from-star=5",
            "--market=Y",
            "--black-market=?",
            "--outfitting=?",
            "--pad-size=s",
            "--rearm=?",
            "--refuel=Y",
            "--repair=?",
            "--no-export",
            "sol/Dangerous Delight"])
        captured = capsys.readouterr()
        assert regex_findin(r"NOTE: Sol/Dangerous Delight \(#\d+\) added", captured.out)
    
    def test_nav(self, capsys):
        trade([PROG, "nav", "--ly-per=50", "sol", "Shinrarta Dezhra"])
        captured = capsys.readouterr()
        assert "System            JumpLy" in captured.out
        assert "Shinrarta Dezhra   47" in captured.out
    
    def test_market(self, capsys):
        trade([PROG, "market", "sol/abr"])
        captured = capsys.readouterr()
        assert regex_findin("Item[ ]{3,}Buying Selling[ ]{2,}Supply", captured.out)
        assert "Hydrogen Fuel" in captured.out
        assert regex_findin("Water[ ]{3,}323", captured.out)
    
    @pytest.mark.slow
    def test_import_edcd(self, capsys):
        trade([PROG, "import", "-P=edcd", "--opt=commodity"])
        captured = capsys.readouterr()
        assert regex_findin(r"NOTE: Found \d+ item\(s\)", captured.out)
