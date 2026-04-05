from __future__ import annotations

from tradedangerous.tradedb import TradeDB, Station, System

from .helpers import isolated_tdb

ORIGIN_SYSTEM = 'Sol'
ORIGIN_STATION = 'Abraham Lincoln'
LOOKUP_STATION = 'Dunyach Enterprise'
LOOKUP_STATION_SYSTEM = 'Ross 490'
DIRECT_ROUTE_TARGETS = (
    "Barnard's Star",
    'Sirius',
    'LHS 380',
)

class TestPeek:
    """
    Deterministic smoke tests for the public TradeDB lookup and routing API.
    """
    
    def test_lookup_system_and_station(self, isolated_tdb: TradeDB):
        origin = isolated_tdb.lookupSystem(ORIGIN_SYSTEM)
        
        assert isinstance(origin, System)
        assert (origin.posX, origin.posY, origin.posZ) == (0.0, 0.0, 0.0)
        
        stations = origin.stations
        assert stations
        assert all(isinstance(station, Station) for station in stations)
        
        abe1 = isolated_tdb.lookupStation(ORIGIN_STATION)
        abe2 = isolated_tdb.lookupStation(ORIGIN_STATION, origin)
        
        assert isinstance(abe1, Station)
        assert abe1 is abe2
        assert abe1.system is origin
        assert abe1.name() == 'Sol/Abraham Lincoln'
        assert abe1.maxPadSize == 'L'
        assert abe1.market == 'Y'
    
    def test_lookup_place_variants(self, isolated_tdb: TradeDB):
        sol = isolated_tdb.lookupPlace('@sol')
        station = isolated_tdb.lookupPlace('dunyach')
        abe = isolated_tdb.lookupPlace('sol/hamlinc')
        abe_explicit = isolated_tdb.lookupPlace('@sol/abrahamlincoln')
        
        assert isinstance(sol, System)
        assert sol.dbname == ORIGIN_SYSTEM
        
        assert isinstance(station, Station)
        assert station.dbname == LOOKUP_STATION
        assert station.system.dbname == LOOKUP_STATION_SYSTEM
        
        assert isinstance(abe, Station)
        assert abe is abe_explicit
        assert abe.dbname == ORIGIN_STATION
        assert abe.system.dbname == ORIGIN_SYSTEM
    
    def test_get_route_returns_direct_hops_for_nearby_systems(self, isolated_tdb: TradeDB):
        origin = isolated_tdb.lookupSystem(ORIGIN_SYSTEM)
        origin_station = isolated_tdb.lookupStation(ORIGIN_STATION, origin)
        
        for target_name in DIRECT_ROUTE_TARGETS:
            target = isolated_tdb.lookupSystem(target_name)
            
            route_from_system = isolated_tdb.getRoute(origin, target, 15)
            route_from_station = isolated_tdb.getRoute(origin_station, target, 15)
            
            assert route_from_system is not None
            assert route_from_station is not None
            assert [system.name() for system, _distance in route_from_system] == [
                ORIGIN_SYSTEM,
                target_name,
            ]
            assert [system.name() for system, _distance in route_from_station] == [
                ORIGIN_SYSTEM,
                target_name,
            ]
            assert route_from_system[0][1] == 0
            assert route_from_system[-1][1] > 0
