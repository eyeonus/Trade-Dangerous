from __future__ import annotations

import gc

import pytest

from tradedangerous.tradeexcept import AmbiguityError, SystemNotStationError
from tradedangerous.tradeorm import TradeORM

from .helpers import isolated_trade_env

@pytest.fixture()
def isolated_torm(isolated_trade_env):
    instance = TradeORM()
    yield instance
    instance.session.close()
    instance.engine.dispose()
    del instance
    gc.collect()

class TestTradeORMLookup:
    def test_lookup_station_exact_partial_and_system_only_cases(self, isolated_torm):
        exact_station = isolated_torm.lookup_station("Abraham Lincoln")
        partial_station = isolated_torm.lookup_station("Abraham Lin")
        
        assert exact_station is not None
        assert partial_station is not None
        
        assert exact_station.name == "Abraham Lincoln"
        assert exact_station.system.name == "Sol"
        
        assert partial_station.station_id == exact_station.station_id
        
        with pytest.raises(
            SystemNotStationError,
            match=r'"Sol" is a system name',
        ):
            isolated_torm.lookup_station("Sol")
    
    def test_lookup_place_disambiguates_duplicate_station_names_with_system_prefix(
        self,
        isolated_torm,
    ):
        with pytest.raises(AmbiguityError):
            isolated_torm.lookup_place("/Blanco Manufacturing Forge")
        
        lushertha_station = isolated_torm.lookup_place(
            "Lushertha/Blanco Manufacturing Forge",
        )
        jastreb_station = isolated_torm.lookup_place(
            "Jastreb Sector CL-Y d145/Blanco Manufacturing Forge",
        )
        
        assert lushertha_station is not None
        assert jastreb_station is not None
        
        assert lushertha_station.name == "Blanco Manufacturing Forge"
        assert lushertha_station.system.name == "Lushertha"
        
        assert jastreb_station.name == "Blanco Manufacturing Forge"
        assert jastreb_station.system.name == "Jastreb Sector CL-Y d145"
        
        assert lushertha_station.station_id != jastreb_station.station_id
    
    def test_lookup_system_exact_and_station_qualified_forms_return_system(
        self,
        isolated_torm,
    ):
        exact_system = isolated_torm.lookup_system("Sol")
        qualified_system = isolated_torm.lookup_system("Sol/Abraham Lincoln")
        
        assert exact_system is not None
        assert qualified_system is not None
        
        assert exact_system.name == "Sol"
        assert qualified_system.system_id == exact_system.system_id
    
    def test_lookup_methods_reject_sql_wildcards(self, isolated_torm):
        from tradedangerous import TradeException
        
        with pytest.raises(TradeException, match=r"wildcards \('%'\) are not supported in station names"):
            isolated_torm.lookup_station("%")
        
        with pytest.raises(TradeException, match=r"wildcards \('%'\) are not supported in system names"):
            isolated_torm.lookup_system("%")
        
        with pytest.raises(TradeException, match=r"wildcards \('%'\) are not supported in names"):
            isolated_torm.lookup_place("%")
