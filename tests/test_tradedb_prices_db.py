from __future__ import annotations

from .helpers import isolated_tdb


class TestTradeDBPrices:
    def test_average_price_maps_are_populated_and_cached(self, isolated_tdb):
        hydrogen_fuel = isolated_tdb.lookupItem("Hydrogen Fuel")

        avg_selling_first = isolated_tdb.getAverageSelling()
        avg_buying_first = isolated_tdb.getAverageBuying()

        assert hydrogen_fuel.ID in avg_selling_first
        assert hydrogen_fuel.ID in avg_buying_first

        assert avg_selling_first[hydrogen_fuel.ID] > 0
        assert avg_buying_first[hydrogen_fuel.ID] > 0

        avg_selling_second = isolated_tdb.getAverageSelling()
        avg_buying_second = isolated_tdb.getAverageBuying()

        assert avg_selling_second is avg_selling_first
        assert avg_buying_second is avg_buying_first