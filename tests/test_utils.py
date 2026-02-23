import pytest   # noqa: F401

from tradedangerous import utils


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
