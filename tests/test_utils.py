import pytest   # noqa: F401

from tradedangerous import utils
from tradedangerous import TradeEnv


class TestUtils:    # should inherit from TestCase
    # TODO: Test 'von' etc.
    
    def test_titleFixup_s(self):
        assert "Smith's" == utils.titleFixup("smith's")
    
    def test_titleFixup_mc(self):
        assert 'McDonald' == utils.titleFixup('mcdonald')
        assert 'McKilroy' == utils.titleFixup('mckilroy')
    
    def test_titleFixup_mac(self):
        assert 'MacNair' == utils.titleFixup('macnair')
        # Needs to be > 3 characters after Mac
        assert 'Macnai' == utils.titleFixup('macnai')


    def test_checkForOcrDerp(self, capsys):
        tdenv = TradeEnv()
        utils.checkForOcrDerp(tdenv, 'some', 'Aquire0')
        captured = capsys.readouterr()
        assert "Ignoring 'some/Aquire0' because it looks like OCR derp." in captured.out
