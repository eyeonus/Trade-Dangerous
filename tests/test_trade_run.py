import io

import pytest

from tradedangerous.cli import trade

from .helpers import copy_fixtures, regex_findin, replace_stdin

PROG = "trade"


def setup_module():
    copy_fixtures()


class TestTradeRun:
    def test_run1(self, capsys):
        trade([PROG, "run", "--capacity=10", "--credits=10000", "--from=sol/abr", "--jumps-per=3", "--ly-per=10.5", "--no-planet"])
        captured = capsys.readouterr()
        assert "Sol/Abraham Lincoln: 10 x Hydrogen Fuel," in captured.out
        assert "Sol/Burnell Station: 2 x Silver," in captured.out
        assert "560cr (213/ton)" in captured.out
    
    @pytest.mark.slow
    def test_run2(self, capsys):
        trade([
            PROG, "run", "-vv", "--progress", "--empty=82",
            "--cap=212", "--jumps=4", "--cr=2153796", "--from=sol/abr",
            "--hops=6", "--ls-m=8000", "--sup=10000",
            "--pad=L", "--ly=25", "--prune-hop=3", "--prune-sc=40"])
        captured = capsys.readouterr()
        assert regex_findin(r"=> est [\d\s,]+cr total", captured.out)
    
    @pytest.mark.slow
    def test_run3(self, capsys):
        """Testing --checklist
        """
        # monkeypatch.setattr('sys.stdin', io.StringIO('100'))
        STEPS = 37
        with replace_stdin(io.StringIO('\n' * STEPS)):
            trade([
                PROG, "run", "-vv", "--progress", "--empty=82", "--checklist",
                "--cap=212", "--jumps=4", "--cr=2153796", "--from=sol/abr",
                "--hops=6", "--ls-m=8000", "--sup=10000",
                "--pad=L", "--ly=25", "--prune-hop=3", "--prune-sc=40"])
        captured = capsys.readouterr()
        # with capsys.disabled():
        #      print("Here")
        #      print(captured.out)
        #      print("to Here")
        assert "BEGINNING CHECKLIST FOR Sol/Abraham Lincoln -> LHS 449/Fisher Point" in captured.out
        assert "35 : Sell 212 x Polymers"
    
    def test_run4(self, capsys):
        trade([PROG, "run", "--capacity=10", "--credits=10000", "--from=sol/abr", "--jumps-per=3", "--ly-per=10.5", "--start-jumps=2"])
        captured = capsys.readouterr()
        # with capsys.disabled():
        #      print("Here")
        #      print(captured.out)
        #      print("to Here")
        assert "Sol/Haberlandt Survey -> Sol/Durrance Camp" in captured.out
        assert "  Sol/Haberlandt Survey: 5 x Reactive Armour," in captured.out
        assert "  Sol/Ehrlich City: 10 x Building Fabricators," in captured.out
        assert "  Sol/Durrance Camp +10 925cr (728/ton)"
