"""
Tests for tradedangerous.db.station_types — canonical station type registry.
"""

import pytest
from tradedangerous.db import station_types as st


class TestTypeIdConstants:
    def test_unknown_is_zero(self):
        assert st.UNKNOWN == 0

    def test_all_constants_in_range(self):
        constants = [
            st.UNKNOWN, st.ASTEROID_BASE, st.CORIOLIS_STARPORT,
            st.DOCKABLE_PLANET_STATION, st.DODEC_STARPORT,
            st.DRAKE_CLASS_CARRIER, st.MEGA_SHIP, st.OCELLUS_STARPORT,
            st.ORBIS_STARPORT, st.OUTPOST, st.PLANETARY_CONSTRUCTION_DEPOT,
            st.PLANETARY_OUTPOST, st.PLANETARY_PORT, st.SETTLEMENT,
            st.SPACE_CONSTRUCTION_DEPOT, st.SURFACE_SETTLEMENT,
        ]
        assert sorted(constants) == list(range(16))


class TestDisplayNames:
    def test_all_type_ids_have_display_names(self):
        for type_id in range(16):
            assert type_id in st.DISPLAY_NAMES, f"type_id {type_id} missing from DISPLAY_NAMES"

    def test_no_extra_type_ids(self):
        assert set(st.DISPLAY_NAMES.keys()) == set(range(16))

    def test_unknown_display_name(self):
        assert st.DISPLAY_NAMES[st.UNKNOWN] == "Unknown"

    def test_drake_display_name(self):
        assert st.DISPLAY_NAMES[st.DRAKE_CLASS_CARRIER] == "Drake-Class Carrier"


class TestExternalMapping:
    @pytest.mark.parametrize("type_name,expected", [
        ("asteroid base",                st.ASTEROID_BASE),
        ("coriolis starport",            st.CORIOLIS_STARPORT),
        ("dockable planet station",      st.DOCKABLE_PLANET_STATION),
        ("dodec starport",               st.DODEC_STARPORT),
        ("drake-class carrier",          st.DRAKE_CLASS_CARRIER),
        ("mega ship",                    st.MEGA_SHIP),
        ("ocellus starport",             st.OCELLUS_STARPORT),
        ("orbis starport",               st.ORBIS_STARPORT),
        ("outpost",                      st.OUTPOST),
        ("planetary construction depot", st.PLANETARY_CONSTRUCTION_DEPOT),
        ("planetary outpost",            st.PLANETARY_OUTPOST),
        ("planetary port",               st.PLANETARY_PORT),
        ("settlement",                   st.SETTLEMENT),
        ("space construction depot",     st.SPACE_CONSTRUCTION_DEPOT),
        ("surface settlement",           st.SURFACE_SETTLEMENT),
    ])
    def test_canonical_external_strings(self, type_name, expected):
        assert st.station_type_id_from_external(type_name) == expected

    def test_alias_drake_no_hyphen(self):
        assert st.station_type_id_from_external("drake class carrier") == st.DRAKE_CLASS_CARRIER

    def test_none_returns_unknown(self):
        assert st.station_type_id_from_external(None) == st.UNKNOWN

    def test_integer_returns_unknown(self):
        assert st.station_type_id_from_external(5) == st.UNKNOWN

    def test_unrecognised_string_returns_unknown(self):
        assert st.station_type_id_from_external("space station") == st.UNKNOWN

    def test_empty_string_returns_unknown(self):
        assert st.station_type_id_from_external("") == st.UNKNOWN

    def test_whitespace_normalised(self):
        assert st.station_type_id_from_external("  outpost  ") == st.OUTPOST

    def test_case_normalised(self):
        assert st.station_type_id_from_external("OUTPOST") == st.OUTPOST
        assert st.station_type_id_from_external("Orbis Starport") == st.ORBIS_STARPORT


class TestClassificationSets:
    def test_fleet_carrier_set_contains_drake(self):
        assert st.DRAKE_CLASS_CARRIER in st.FLEET_CARRIER_TYPE_IDS

    def test_fleet_carrier_set_excludes_unknown(self):
        assert st.UNKNOWN not in st.FLEET_CARRIER_TYPE_IDS

    def test_settlement_set_members(self):
        assert st.PLANETARY_CONSTRUCTION_DEPOT in st.SETTLEMENT_TYPE_IDS
        assert st.SETTLEMENT in st.SETTLEMENT_TYPE_IDS
        assert st.SURFACE_SETTLEMENT in st.SETTLEMENT_TYPE_IDS

    def test_settlement_set_excludes_unknown(self):
        assert st.UNKNOWN not in st.SETTLEMENT_TYPE_IDS

    def test_settlement_set_excludes_space_stations(self):
        for type_id in (st.CORIOLIS_STARPORT, st.ORBIS_STARPORT, st.OCELLUS_STARPORT,
                        st.DODEC_STARPORT, st.OUTPOST, st.MEGA_SHIP):
            assert type_id not in st.SETTLEMENT_TYPE_IDS

    def test_planetary_set_members(self):
        for type_id in (st.DOCKABLE_PLANET_STATION, st.PLANETARY_CONSTRUCTION_DEPOT,
                        st.PLANETARY_OUTPOST, st.PLANETARY_PORT,
                        st.SETTLEMENT, st.SURFACE_SETTLEMENT):
            assert type_id in st.PLANETARY_BY_TYPE_IDS

    def test_planetary_set_excludes_space_types(self):
        for type_id in (st.CORIOLIS_STARPORT, st.ORBIS_STARPORT, st.DRAKE_CLASS_CARRIER):
            assert type_id not in st.PLANETARY_BY_TYPE_IDS


class TestFleetCarrierState:
    def test_drake_is_Y(self):
        assert st.fleet_carrier_state(st.DRAKE_CLASS_CARRIER) == "Y"

    def test_unknown_is_question(self):
        assert st.fleet_carrier_state(st.UNKNOWN) == "?"

    def test_outpost_is_N(self):
        assert st.fleet_carrier_state(st.OUTPOST) == "N"

    def test_all_non_carrier_non_unknown_are_N(self):
        for type_id in range(16):
            if type_id == st.UNKNOWN:
                continue
            if type_id in st.FLEET_CARRIER_TYPE_IDS:
                assert st.fleet_carrier_state(type_id) == "Y"
            else:
                assert st.fleet_carrier_state(type_id) == "N"


class TestSettlementState:
    def test_planetary_construction_depot_is_Y(self):
        assert st.settlement_state(st.PLANETARY_CONSTRUCTION_DEPOT) == "Y"

    def test_settlement_is_Y(self):
        assert st.settlement_state(st.SETTLEMENT) == "Y"

    def test_surface_settlement_is_Y(self):
        assert st.settlement_state(st.SURFACE_SETTLEMENT) == "Y"

    def test_unknown_is_question(self):
        assert st.settlement_state(st.UNKNOWN) == "?"

    def test_outpost_is_N(self):
        assert st.settlement_state(st.OUTPOST) == "N"

    def test_all_non_settlement_non_unknown_are_N(self):
        for type_id in range(16):
            if type_id == st.UNKNOWN:
                continue
            if type_id in st.SETTLEMENT_TYPE_IDS:
                assert st.settlement_state(type_id) == "Y"
            else:
                assert st.settlement_state(type_id) == "N"
