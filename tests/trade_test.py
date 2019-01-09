import re

import pytest

from tradedangerous.core import trade
from tradedangerous.commands.exceptions import UsageError
from .helpers import copy_fixtures, regex_findin

PROG = "trade"

def setup_module():
    copy_fixtures()

class TestTrade(object):
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
        #"Dekker's Yard"
        trade([PROG, "station", "-rm", "sol/dekkers"])
        captured = capsys.readouterr()
        assert regex_findin("NOTE: Sol/Dekker's Yard \(#\d+\) removed", captured.out)


    def test_station_add(self, capsys):
        #"Dekker's Yard"
        trade([PROG, "station", "--add", "--ls-from-star=5",
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
        assert regex_findin("NOTE: Sol/Dangerous Delight \(#\d+\) added", captured.out)


    def test_nav(self, capsys):
        trade([PROG, "nav", "--ly-per=50", "sol", "Shinrarta Dezhra"])
        captured = capsys.readouterr()
        assert "System            JumpLy" in captured.out
        assert "Shinrarta Dezhra   47" in captured.out


    def test_market(self, capsys):
        trade([PROG, "market", "sol/abr"])
        captured = capsys.readouterr()
        assert "Item                          Buying Selling   Supply" in captured.out
        assert "Hydrogen Fuel" in captured.out
        assert "Water                            323" in captured.out


    def test_run(self, capsys):
        trade([PROG, "run", "--capacity=10", "--credits=10000", "--from=sol/abr", "--jumps-per=3", "--ly-per=10.5", "--no-planet"])
        captured = capsys.readouterr()
        assert "Sol/Abraham Lincoln: 10 x Hydrogen Fuel," in captured.out
        assert "Sol/Burnell Station: 2 x Silver," in captured.out
        assert "560cr (213/ton)" in captured.out


    @pytest.mark.slow
    def test_import_eddblink(self, capsys):
        trade([PROG, "import", "-P=eddblink", '--opt=clean,skipvend,force'])
        captured = capsys.readouterr()
        # with capsys.disabled():
        #     print("Here")
        #     print(captured.out)
        #     print("to Here")
        assert "NOTE: Import completed." in captured.out


    def test_import_edcd(self, capsys):
        #trade import -P=edcd --opt=commodity
        trade([PROG, "import", "-P=edcd", "--opt=commodity"])
        captured = capsys.readouterr()
        # with capsys.disabled():
        #     print("Here")
        #     print(captured.out)
        #     print("to Here")
        assert "NOTE: Nothing had to be done" in captured.out
        assert regex_findin(r"NOTE: Found \d+ item\(s\)", captured.out)


    def test_import_maddavo(self, capsys):
        #trade import -P maddavo -i -O use2d
        trade([PROG, "import", "-P=maddavo", "-i", "--opt=use2d"])
        captured = capsys.readouterr()
        # with capsys.disabled():
        #     print("Here")
        #     print(captured.out)
        #     print("to Here")
        assert regex_findin(r"NOTE: Import complete: \d+ items over \d+ stations in \d+ systems", captured.out)


    def test_pyproj_run(self, capsys):
        trade([PROG, "run", "-vv", "--progress", "--empty=82",
            "--cap=212", "--jumps=4", "--cr=2153796", "--from=sol/abr",
            "--hops=6", "--ls-m=8000", "--sup=10000",
            "--pad=L", "--ly=25", "--prune-hop=3", "--prune-sc=40"])
        captured = capsys.readouterr()
        # with capsys.disabled():
        #     print("Here")
        #     print(captured.out)
        #     print("to Here")
        assert regex_findin(r"=> est [\d\s,]+cr total", captured.out)
