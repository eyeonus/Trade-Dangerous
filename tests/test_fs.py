
from shutil import rmtree
from pathlib import Path
import pytest

from tradedangerous import fs, TradeEnv

def setup_module():
    tdenv = TradeEnv()
    p = Path(tdenv.tmpDir)
    if p.exists() and p.is_dir():
        rmtree(tdenv.tmpDir)
    fs.ensurefolder(tdenv.tmpDir)

@pytest.fixture
def tdenv():
    return TradeEnv()


class TestFS:
    
    def test_copy(self, tdenv):
        src = fs.pathify(tdenv.templateDir, 'TradeDangerous.sql')
        dst = fs.pathify(tdenv.tmpDir, src.name)
        fs.copy(src, dst)
        assert dst.exists() and dst.is_file()
    
    def test_ensureflag(self, tdenv):
        self.result = False
        flagfile = fs.pathify(tdenv.tmpDir, 'flagtest')
        if flagfile.exists():
            flagfile.unlink()
        
        def action():
            self.result = True
        
        flag = fs.ensureflag(flagfile, action)
        assert self.result is True
        assert flag is not None
    
    def test_copyallfiles(self, tdenv):
        setup_module()
        fs.copyallfiles(tdenv.templateDir, tdenv.tmpDir)
        test = Path(tdenv.tmpDir, 'Added.csv')
        assert test.exists() and test.is_file()
