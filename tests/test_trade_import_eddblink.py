import os

import pytest

from tradedangerous.cli import trade
from tradedangerous.plugins import eddblink_plug as module
from .helpers import copy_fixtures, tdfactory

PROG = "trade"


@pytest.fixture
def td():
    copy_fixtures()
    tdb, tdenv = tdfactory()
    yield tdb, tdenv
    # this will happen when the fixture goes out of use
    tdb.close()


class TestTradeImportEddblink(object):
    def test_create_instance(self, monkeypatch, td):
        tdb, tdenv = td
        plug = module.ImportPlugin(tdb, tdenv)
        assert module.UPGRADES == "modules.json"
        assert os.path.join('data', 'eddb') in str(plug.dataPath)

        monkeypatch.setitem(os.environ, 'TD_EDDB', '/my/testdir')
        plug = module.ImportPlugin(tdb, tdenv)
        assert os.path.join('my', 'testdir') in str(plug.dataPath)

    def test_upgrades(self, capsys, td):
        tdb, tdenv = td
        plug = module.ImportPlugin(tdb, tdenv)
        assert module.UPGRADES == "modules.json"
        assert os.path.join('data', 'eddb') in str(plug.dataPath)
        plug.downloadFile(module.UPGRADES, plug.upgradesPath)
        assert (plug.dataPath / plug.upgradesPath).is_file()
    
    @pytest.mark.superslow
    def test_import_clean(self, capsys):
        trade([PROG, "import", "-P=eddblink", '--opt=clean,skipvend,force'])
        captured = capsys.readouterr()
        # with capsys.disabled():
        #     print("Here")
        #     print(captured.out)
        #     print("to Here")
        assert "NOTE: Import completed." in captured.out

    @pytest.mark.superslow
    def test_import_upgrade(self, capsys):
        trade([PROG, "import", "-P=eddblink", '--opt=upgrade'])
        captured = capsys.readouterr()
        with capsys.disabled():
            print("Here")
            print(captured.out)
            print("to Here")
        assert "NOTE: Import completed." in captured.out
