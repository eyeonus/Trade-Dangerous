from __future__ import annotations

from tradedangerous.tradecalc import TradeCalc

from .helpers import isolated_tdb


class TestTradeCalc:
    def test_get_trades_returns_sorted_profitable_options(self, isolated_tdb):
        src_station = isolated_tdb.lookupStation("Abraham Lincoln", "Sol")
        dst_station = isolated_tdb.lookupStation("Burnell Station", "Sol")

        calc = TradeCalc(isolated_tdb)
        trades = calc.getTrades(src_station, dst_station)

        assert trades is not None
        assert trades

        trade_names = [trade.item.dbname for trade in trades]
        assert "Hydrogen Fuel" in trade_names

        for trade in trades:
            assert trade.gainCr > 0

        observed_order = [(trade.gainCr, trade.costCr) for trade in trades]
        expected_order = sorted(
            observed_order,
            key=lambda entry: (-entry[0], entry[1]),
        )

        assert observed_order == expected_order
        
    def test_preload_honours_restrict_station_ids(self, isolated_tdb):
        abraham_lincoln = isolated_tdb.lookupStation("Abraham Lincoln", "Sol")
        burnell_station = isolated_tdb.lookupStation("Burnell Station", "Sol")

        calc = TradeCalc(
            isolated_tdb,
            restrict_station_ids=[abraham_lincoln.ID, burnell_station.ID],
        )

        buying_ids = set(calc.stationsBuying.keys())
        selling_ids = set(calc.stationsSelling.keys())

        assert buying_ids
        assert selling_ids

        assert buying_ids <= {abraham_lincoln.ID, burnell_station.ID}
        assert selling_ids <= {abraham_lincoln.ID, burnell_station.ID}

    def test_preload_honours_supply_and_demand_thresholds(self, isolated_tdb):
        abraham_lincoln = isolated_tdb.lookupStation("Abraham Lincoln", "Sol")
        burnell_station = isolated_tdb.lookupStation("Burnell Station", "Sol")
        station_ids = [abraham_lincoln.ID, burnell_station.ID]

        baseline = TradeCalc(
            isolated_tdb,
            restrict_station_ids=station_ids,
        )

        max_supply_units = max(
            values[2]
            for station_id in station_ids
            for values in baseline.stationsSelling.get(station_id, ())
        )
        max_demand_units = max(
            values[2]
            for station_id in station_ids
            for values in baseline.stationsBuying.get(station_id, ())
        )

        isolated_tdb.tdenv.supply = max_supply_units + 1
        isolated_tdb.tdenv.demand = max_demand_units + 1

        filtered = TradeCalc(
            isolated_tdb,
            restrict_station_ids=station_ids,
        )

        assert not filtered.stationsSelling
        assert not filtered.stationsBuying
        assert not filtered.eligible_station_ids
        
    def test_preload_honours_max_age(self, isolated_tdb, monkeypatch):
        import tradedangerous.tradecalc as tradecalc_module

        frozen_now = 2_000_000_000
        monkeypatch.setattr(tradecalc_module.time, "time", lambda: frozen_now)

        baseline = TradeCalc(isolated_tdb)
        baseline_ages = [
            values[4]
            for station_rows in baseline.stationsSelling.values()
            for values in station_rows
        ] + [
            values[4]
            for station_rows in baseline.stationsBuying.values()
            for values in station_rows
        ]

        assert baseline_ages

        unique_ages = sorted(set(baseline_ages))
        gap_pair = None
        for younger_age, older_age in zip(unique_ages, unique_ages[1:]):
            if older_age - younger_age > 7200:
                gap_pair = (younger_age, older_age)
                break

        assert gap_pair is not None

        younger_age, older_age = gap_pair
        cutoff_seconds = younger_age + ((older_age - younger_age) / 2)
        isolated_tdb.tdenv.maxAge = cutoff_seconds / (60 * 60 * 24)

        filtered = TradeCalc(isolated_tdb)
        filtered_ages = [
            values[4]
            for station_rows in filtered.stationsSelling.values()
            for values in station_rows
        ] + [
            values[4]
            for station_rows in filtered.stationsBuying.values()
            for values in station_rows
        ]

        assert filtered_ages
        assert len(filtered_ages) < len(baseline_ages)
        assert younger_age in filtered_ages
        assert older_age not in filtered_ages
        
    def test_get_best_hops_respects_restrict_to_and_unique(self, isolated_tdb):
        import pytest

        from tradedangerous.tradecalc import NoHopsError, Route

        src_station = isolated_tdb.lookupStation("Abraham Lincoln", "Sol")
        calc = TradeCalc(isolated_tdb)

        candidate = None
        for station in isolated_tdb.stationByID.values():
            if station is src_station:
                continue
            if calc.getTrades(src_station, station):
                candidate = station
                break

        assert candidate is not None

        tdenv = isolated_tdb.tdenv
        tdenv.credits = 1_000_000
        tdenv.capacity = 100
        tdenv.margin = 0
        tdenv.maxJumpsPer = 3
        tdenv.maxLyPer = 15
        tdenv.padSize = None
        tdenv.planetary = None
        tdenv.fleet = None
        tdenv.odyssey = None
        tdenv.noPlanet = False
        tdenv.maxLs = 0
        tdenv.blackMarket = False
        tdenv.maxAge = 0
        tdenv.direct = True
        tdenv.unique = False
        tdenv.limit = None
        tdenv.minGainPerTon = 0
        tdenv.maxGainPerTon = 0
        tdenv.avoidPlaces = ()

        base_route = Route((candidate, src_station), (), 0, 0, (), 0)

        unrestricted = calc.getBestHops([base_route], restrictTo={candidate})

        assert unrestricted
        assert unrestricted[0].lastStation is candidate

        tdenv.unique = True
        with pytest.raises(NoHopsError):
            calc.getBestHops([base_route], restrictTo={candidate})
            
    def test_get_best_hops_respects_black_market_flag(self, isolated_tdb):
        from tradedangerous.tradecalc import Route

        src_station = isolated_tdb.lookupStation("Abraham Lincoln", "Sol")
        calc = TradeCalc(isolated_tdb)

        black_market_candidate = None
        regular_candidate = None
        for station in isolated_tdb.stationByID.values():
            if station is src_station:
                continue
            if not calc.getTrades(src_station, station):
                continue
            if station.blackMarket == "Y" and black_market_candidate is None:
                black_market_candidate = station
            if station.blackMarket == "N" and regular_candidate is None:
                regular_candidate = station
            if black_market_candidate and regular_candidate:
                break

        assert black_market_candidate is not None
        assert regular_candidate is not None

        tdenv = isolated_tdb.tdenv
        tdenv.credits = 1_000_000
        tdenv.capacity = 100
        tdenv.margin = 0
        tdenv.maxJumpsPer = 3
        tdenv.maxLyPer = 15
        tdenv.padSize = None
        tdenv.planetary = None
        tdenv.fleet = None
        tdenv.odyssey = None
        tdenv.noPlanet = False
        tdenv.maxLs = 0
        tdenv.maxAge = 0
        tdenv.direct = True
        tdenv.unique = False
        tdenv.limit = None
        tdenv.minGainPerTon = 0
        tdenv.maxGainPerTon = 0
        tdenv.avoidPlaces = ()

        base_route = Route((src_station,), (), 0, 0, (), 0)

        tdenv.blackMarket = False
        unrestricted = calc.getBestHops(
            [base_route],
            restrictTo={black_market_candidate, regular_candidate},
        )

        unrestricted_ids = {route.lastStation.ID for route in unrestricted}
        assert black_market_candidate.ID in unrestricted_ids
        assert regular_candidate.ID in unrestricted_ids

        tdenv.blackMarket = True
        filtered = calc.getBestHops(
            [base_route],
            restrictTo={black_market_candidate, regular_candidate},
        )

        filtered_ids = {route.lastStation.ID for route in filtered}
        assert black_market_candidate.ID in filtered_ids
        assert regular_candidate.ID not in filtered_ids
        assert all(route.lastStation.blackMarket == "Y" for route in filtered)