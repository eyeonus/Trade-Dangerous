import random

import pytest

from tradedangerous.tradedb import TradeDB, Station, System
from .helpers import copy_fixtures

ORIGIN = 'Shinrarta Dezhra'
# tdb = None

def setup_module():
    copy_fixtures()

def route_to_closest(tdb: TradeDB, origin, destinations, maxLy=15):
    closest = min(destinations, key=lambda candidate: candidate.distanceTo(origin))
    print("Closest:", closest.name(), closest.distanceTo(origin))
    route = tdb.getRoute(origin, closest, maxLy)
    if not route:
        print("No route found.")
    else:
        print("Route:", ", ".join(system.name() for system, distance in route))
    return route

def should_skip() -> bool:
    return False  # os.getenv("CI") != None


class TestPeek:
    """
    Tests based on https://github.com/eyeonus/Trade-Dangerous/wiki/Python-Quick-Peek
    """
    
    @pytest.mark.skipif(should_skip(), reason="does not work with CI")
    def test_quick_origin(self, tdb: TradeDB):
        # Look up a particular system
        origin = tdb.lookupSystem(ORIGIN)
        
        assert 55.71875 == origin.posX
        assert 17.59375 == origin.posY
        assert 27.15625, origin.posZ
        
        stations = origin.stations
        assert len(stations) == 5
        for station in stations:
            assert isinstance(station, Station)
        
        # Look up a station
        abe1 = tdb.lookupStation("Abraham Lincoln")
        assert isinstance(abe1, Station)


        # Look up a station in a particular system
        sol = tdb.lookupSystem("sol")
        abe2 = tdb.lookupStation("Abraham Lincoln", sol)
        
        assert abe1 == abe2
    
    @pytest.mark.skipif(should_skip(), reason="does not work with CI")
    def test_quick_lookupPlace(self, tdb):
        # Look up a system or station using the flexible naming mechanism
        phoenix = tdb.lookupPlace("dunyach")
        assert str(type(phoenix)) == "<class 'tradedangerous.tradedb.Station'>"  # tell me what type of thing "phoenix" is...
        
        sol = tdb.lookupPlace("@sol")
        assert str(type(sol)) == "<class 'tradedangerous.tradedb.System'>"
        
        lave = tdb.lookupPlace("stein")
        assert isinstance(lave, System)
        
        abe = tdb.lookupPlace("sol/hamlinc")
        assert isinstance(abe, Station)
    
    @pytest.mark.skipif(should_skip(), reason="does not work with CI")
    def test_quick_five(self, tdb):
        systemTable = tdb.systemByID.values()
        visitMe = random.sample(list(systemTable), 5)
        origin = tdb.lookupPlace(ORIGIN)
        # Call distanceTo(origin) on every member of visitMe and
        # then retrieve the one with the lowest distance.
        closest = min(visitMe, key=lambda candidate: candidate.distanceTo(origin))
        print("{start} -> {dest}: {dist:.2f} ly".format(
            start=origin.name(), dest=closest.name(),
            dist=origin.distanceTo(closest),
        ))
        route = tdb.getRoute(origin, closest, 15)
        if not route:
            print("Shame, couldn't find a route.")
        else:
            # Route is a list of Systems. Turn it into a list of
            # System names...
            routeNames = [system.name() for system, distance in route]
            print("Route:", routeNames)
        
        route_to_closest(tdb, origin, visitMe)
        route_to_closest(tdb, origin, visitMe, 20)
        
        # lets change origin
        origin = tdb.lookupSystem("Toolfa")
        route_to_closest(tdb, origin, visitMe)
    
    @pytest.mark.skipif(should_skip(), reason="does not work with CI")
    def test_three_different(self, tdb):
        # lets try a different route:
        sol = tdb.lookupSystem("sol")
        lhs = tdb.lookupSystem("lhs 380")
        bhr = tdb.lookupSystem("bhritzameno")
        
        route_to_closest(tdb, sol, [lhs, bhr])
 
