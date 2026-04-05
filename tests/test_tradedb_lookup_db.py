from __future__ import annotations

import pytest

from tradedangerous.tradeexcept import AmbiguityError, SystemNotStationError

from .helpers import isolated_tdb


class TestTradeDBLookup:
    def test_lookup_station_duplicate_name_can_be_disambiguated_by_system(
        self,
        isolated_tdb,
    ):
        lushertha_station = isolated_tdb.lookupStation(
            "Blanco Manufacturing Forge",
            "Lushertha",
        )
        jastreb_station = isolated_tdb.lookupStation(
            "Blanco Manufacturing Forge",
            "Jastreb Sector CL-Y d145",
        )

        assert lushertha_station.dbname == "Blanco Manufacturing Forge"
        assert lushertha_station.system.dbname == "Lushertha"

        assert jastreb_station.dbname == "Blanco Manufacturing Forge"
        assert jastreb_station.system.dbname == "Jastreb Sector CL-Y d145"

        assert lushertha_station.ID != jastreb_station.ID

    def test_lookup_station_from_system_handles_single_and_multi_station_cases(
        self,
        isolated_tdb,
    ):
        lhs_3799 = isolated_tdb.lookupSystem("LHS 3799")
        goo_research = isolated_tdb.lookupStation(lhs_3799)

        assert goo_research.dbname == "Goo Research"
        assert goo_research.system is lhs_3799

        sol = isolated_tdb.lookupSystem("Sol")
        with pytest.raises(SystemNotStationError):
            isolated_tdb.lookupStation(sol)

    def test_lookup_place_duplicate_station_name_requires_system_qualification(
        self,
        isolated_tdb,
    ):
        with pytest.raises(AmbiguityError):
            isolated_tdb.lookupPlace("Blanco Manufacturing Forge")

        lushertha_station = isolated_tdb.lookupPlace(
            "Lushertha/Blanco Manufacturing Forge",
        )
        jastreb_station = isolated_tdb.lookupPlace(
            "Jastreb Sector CL-Y d145/Blanco Manufacturing Forge",
        )

        assert lushertha_station.dbname == "Blanco Manufacturing Forge"
        assert lushertha_station.system.dbname == "Lushertha"

        assert jastreb_station.dbname == "Blanco Manufacturing Forge"
        assert jastreb_station.system.dbname == "Jastreb Sector CL-Y d145"

        assert lushertha_station.ID != jastreb_station.ID
        
    def test_lookup_place_system_names_resolve_to_system_objects(
        self,
        isolated_tdb,
    ):
        sol = isolated_tdb.lookupPlace("Sol")
        sol_explicit = isolated_tdb.lookupPlace("@Sol")
        lhs_3799 = isolated_tdb.lookupPlace("LHS 3799")

        assert sol is sol_explicit
        assert sol.dbname == "Sol"
        assert lhs_3799.dbname == "LHS 3799"

        assert isolated_tdb.lookupStation(lhs_3799).dbname == "Goo Research"
    
    def test_lookup_place_explicit_station_and_legacy_backslash_forms_resolve(
        self,
        isolated_tdb,
    ):
        explicit_station = isolated_tdb.lookupPlace("/Dunyach Enterprise")
        legacy_path_station = isolated_tdb.lookupPlace("Sol\\Abraham Lincoln")
        slash_path_station = isolated_tdb.lookupPlace("Sol/Abraham Lincoln")

        assert explicit_station.dbname == "Dunyach Enterprise"
        assert explicit_station.system.dbname == "Ross 490"

        assert legacy_path_station is slash_path_station
        assert legacy_path_station.dbname == "Abraham Lincoln"
        assert legacy_path_station.system.dbname == "Sol"

    def test_lookup_place_raises_lookup_error_for_unknown_place(
        self,
        isolated_tdb,
    ):
        with pytest.raises(LookupError):
            isolated_tdb.lookupPlace("__definitely_not_a_real_place__")