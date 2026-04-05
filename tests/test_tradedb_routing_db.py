from __future__ import annotations

import pytest

from .helpers import isolated_tdb


class TestTradeDBRouting:
    def test_get_route_rejects_destination_in_avoid_list(self, isolated_tdb):
        origin = isolated_tdb.lookupSystem("Sol")
        destination = isolated_tdb.lookupSystem("Sirius")

        route = isolated_tdb.getRoute(origin, destination, 15)

        assert route is not None
        assert [system.dbname for system, _distance in route] == ["Sol", "Sirius"]

        with pytest.raises(ValueError, match="Destination is in avoidance list"):
            isolated_tdb.getRoute(origin, destination, 15, avoiding=[destination])

    def test_get_destinations_honours_station_filters_and_avoids(self, isolated_tdb):
        origin = isolated_tdb.lookupStation("Abraham Lincoln", "Sol")
        avoided_station = isolated_tdb.lookupStation("Burnell Station", "Sol")

        destinations = list(
            isolated_tdb.getDestinations(
                origin,
                maxJumps=2,
                maxLyPer=15,
                avoidPlaces=[avoided_station],
                maxPadSize="L",
                maxLsFromStar=10000,
                noPlanet=True,
            )
        )

        assert destinations

        for destination in destinations:
            station = destination.station

            assert station.ID != avoided_station.ID
            assert station.maxPadSize == "L"
            assert station.planetary == "N"
            assert 0 < station.lsFromStar <= 10000

    def test_get_route_honours_avoided_intermediate_system(self, isolated_tdb):
        origin = isolated_tdb.lookupSystem("Sol")

        selected_max_jump = None
        selected_route = None

        for max_jump_ly in (5, 10, 15):
            for destination in sorted(
                isolated_tdb.systems(),
                key=lambda system: system.dbname,
            ):
                if destination is origin:
                    continue

                route = isolated_tdb.getRoute(origin, destination, max_jump_ly)
                if route and len(route) > 2:
                    selected_max_jump = max_jump_ly
                    selected_route = route
                    break

            if selected_route is not None:
                break

        assert selected_route is not None
        assert selected_max_jump is not None

        destination = selected_route[-1][0]
        avoided_system = selected_route[1][0]

        rerouted = isolated_tdb.getRoute(
            origin,
            destination,
            selected_max_jump,
            avoiding=[avoided_system],
        )

        if rerouted is None:
            assert rerouted is None
        else:
            rerouted_system_ids = [system.ID for system, _distance in rerouted]

            assert rerouted[0][0] is origin
            assert rerouted[-1][0] is destination
            assert avoided_system.ID not in rerouted_system_ids
            assert rerouted_system_ids != [
                system.ID for system, _distance in selected_route
            ]