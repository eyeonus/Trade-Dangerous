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
        sirius_station = isolated_tdb.lookupStation(
            "Blanco Manufacturing Forge",
            "Sirius",
        )

        assert lushertha_station.dbname == "Blanco Manufacturing Forge"
        assert lushertha_station.system.dbname == "Lushertha"

        assert sirius_station.dbname == "Blanco Manufacturing Forge"
        assert sirius_station.system.dbname == "Sirius"

        assert lushertha_station.ID != sirius_station.ID
    
    def test_lookup_station_from_system_handles_single_and_multi_station_cases(
        self,
        isolated_tdb,
    ):
        test_sys = isolated_tdb.lookupSystem("Test")
        metallic = isolated_tdb.lookupStation(test_sys)

        assert metallic.dbname == "Metallic Base 2"
        assert metallic.system is test_sys
        
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
        sirius_station = isolated_tdb.lookupPlace(
            "Sirius/Blanco Manufacturing Forge",
        )

        assert lushertha_station.dbname == "Blanco Manufacturing Forge"
        assert lushertha_station.system.dbname == "Lushertha"

        assert sirius_station.dbname == "Blanco Manufacturing Forge"
        assert sirius_station.system.dbname == "Sirius"

        assert lushertha_station.ID != sirius_station.ID
    
    def test_lookup_place_system_names_resolve_to_system_objects(
        self,
        isolated_tdb,
    ):
        sol = isolated_tdb.lookupPlace("Sol")
        sol_explicit = isolated_tdb.lookupPlace("@Sol")
        test_sys = isolated_tdb.lookupPlace("Test")

        assert sol is sol_explicit
        assert sol.dbname == "Sol"
        assert test_sys.dbname == "Test"

        assert isolated_tdb.lookupStation(test_sys).dbname == "Metallic Base 2"
    
    def test_lookup_place_explicit_station_and_legacy_backslash_forms_resolve(
        self,
        isolated_tdb,
    ):
        explicit_station = isolated_tdb.lookupPlace("/Grandin Gateway")
        legacy_path_station = isolated_tdb.lookupPlace("Sol\\Abraham Lincoln")
        slash_path_station = isolated_tdb.lookupPlace("Sol/Abraham Lincoln")

        assert explicit_station.dbname == "Grandin Gateway"
        assert explicit_station.system.dbname == "Altair"
        
        assert legacy_path_station is slash_path_station
        assert legacy_path_station.dbname == "Abraham Lincoln"
        assert legacy_path_station.system.dbname == "Sol"
    
    def test_lookup_place_raises_lookup_error_for_unknown_place(
        self,
        isolated_tdb,
    ):
        with pytest.raises(LookupError):
            isolated_tdb.lookupPlace("__definitely_not_a_real_place__")
