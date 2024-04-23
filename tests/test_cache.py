import pytest
from collections import namedtuple

from tradedangerous import cache

FakeFile = namedtuple('FakeFile', ['name'])

class TestCache:
    def test_parseSupply(self):
        fil = FakeFile('faked-file.prices')
        reading = '897H'
        demandUnits, demandLevel = cache.parseSupply(
            fil,
            10,
            'demand',
            reading)
        
        assert demandUnits == 897
        assert demandLevel == 3
    
    def test_parseSupply_bad_level(self):
        fil = FakeFile('faked-file.prices')
        reading = '897X'
        with pytest.raises(cache.SupplyError, match='Unrecognized level suffix'):
            cache.parseSupply(
                fil,
                10,
                'demand',
                reading)
    
    def test_parseSupply_bad_units(self):
        fil = FakeFile('faked-file.prices')
        reading = '-10H'
        with pytest.raises(cache.SupplyError, match='Unrecognized units/level value'):
            cache.parseSupply(
                fil,
                10,
                'demand',
                reading)
