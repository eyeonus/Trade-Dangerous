from __future__ import annotations

import gc

import pytest

from tradedangerous.db import orm_models as orm
from tradedangerous.tradeexcept import AmbiguityError, SystemNotStationError, TradeException
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

@pytest.fixture()
def torm_with_dupsys(isolated_torm):
    from sqlalchemy import text
    session = isolated_torm.session
    max_id = session.execute(text("SELECT MAX(system_id) FROM System")).scalar()
    session.execute(
        text(
            "INSERT INTO System (system_id, name, pos_x, pos_y, pos_z, modified) "
            "VALUES (:id, 'Zeta Dup', -100.0, 0.0, 0.0, datetime('now'))"
        ),
        {"id": max_id + 1},
    )
    session.execute(
        text(
            "INSERT INTO System (system_id, name, pos_x, pos_y, pos_z, modified) "
            "VALUES (:id, 'Zeta Dup', 100.0, 0.0, 0.0, datetime('now'))"
        ),
        {"id": max_id + 2},
    )
    session.commit()
    session.expire_all()
    yield isolated_torm


@pytest.fixture()
def torm_with_dupsys_and_station(torm_with_dupsys):
    """Adds one station to the first (pos_x=-100) Zeta Dup system."""
    from sqlalchemy import text
    session = torm_with_dupsys.session
    sys_id = session.execute(
        text("SELECT system_id FROM System WHERE name='Zeta Dup' ORDER BY pos_x LIMIT 1")
    ).scalar()
    max_stn_id = session.execute(text("SELECT MAX(station_id) FROM Station")).scalar()
    session.execute(
        text(
            "INSERT INTO Station "
            "(station_id, name, system_id, ls_from_star, blackmarket, max_pad_size, "
            "market, shipyard, outfitting, rearm, refuel, repair, planetary, type_id, modified) "
            "VALUES (:id, 'Zeta Station', :sys_id, 0, '?', '?', '?', '?', '?', '?', '?', '?', '?', 0, datetime('now'))"
        ),
        {"id": max_stn_id + 1, "sys_id": sys_id},
    )
    session.commit()
    session.expire_all()
    yield torm_with_dupsys


@pytest.fixture()
def torm_with_named_station(isolated_torm):
    """Inserts a system 'Namedville' with a station also named 'Namedville'.

    This exercises the dual-scan case 5: exact station match and exact system
    match refer to the same system → station wins.
    """
    from sqlalchemy import text
    session = isolated_torm.session
    max_sys_id = session.execute(text("SELECT MAX(system_id) FROM System")).scalar()
    max_stn_id = session.execute(text("SELECT MAX(station_id) FROM Station")).scalar()
    session.execute(
        text(
            "INSERT INTO System (system_id, name, pos_x, pos_y, pos_z, modified) "
            "VALUES (:id, 'Namedville', 0.0, 0.0, 0.0, datetime('now'))"
        ),
        {"id": max_sys_id + 1},
    )
    session.execute(
        text(
            "INSERT INTO Station "
            "(station_id, name, system_id, ls_from_star, blackmarket, max_pad_size, "
            "market, shipyard, outfitting, rearm, refuel, repair, planetary, type_id, modified) "
            "VALUES (:id, 'Namedville', :sys_id, 0, '?', '?', '?', '?', '?', '?', '?', '?', '?', 0, datetime('now'))"
        ),
        {"id": max_stn_id + 1, "sys_id": max_sys_id + 1},
    )
    session.commit()
    session.expire_all()
    yield isolated_torm


class TestTradeORMLookup:
    def test_lookup_station_exact_and_system_only_cases(self, isolated_torm):
        exact_station = isolated_torm.lookup_station("Abraham Lincoln")

        assert exact_station is not None
        assert exact_station.name == "Abraham Lincoln"
        assert exact_station.system.name == "Sol"

        # Sol has multiple stations — exact system name must raise SystemNotStationError.
        with pytest.raises(SystemNotStationError, match=r"System 'Sol' has"):
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
    
    def test_lookup_system_exact_form_returns_system(self, isolated_torm):
        system = isolated_torm.lookup_system("Sol")
        assert system is not None
        assert system.name == "Sol"
    
    def test_lookup_methods_reject_sql_wildcards(self, isolated_torm):
        from tradedangerous import TradeException
        
        with pytest.raises(TradeException, match=r"wildcards \('%'\) are not supported in station names"):
            isolated_torm.lookup_station("%")
        
        with pytest.raises(TradeException, match=r"wildcards \('%'\) are not supported in system names"):
            isolated_torm.lookup_system("%")
        
        with pytest.raises(TradeException, match=r"wildcards \('%'\) are not supported in names"):
            isolated_torm.lookup_place("%")


class TestLookupSystem:
    def test_lookup_system_case_insensitive(self, isolated_torm):
        # CIString (COLLATE NOCASE / utf8mb4_unicode_ci) must make equality
        # case-insensitive on all supported backends.
        sys_lower = isolated_torm.lookup_system("sol")
        sys_upper = isolated_torm.lookup_system("SOL")
        sys_mixed = isolated_torm.lookup_system("Sol")

        assert sys_lower.name == "Sol"
        assert sys_upper.system_id == sys_lower.system_id
        assert sys_mixed.system_id == sys_lower.system_id

    def test_lookup_system_not_found_raises_lookup_error(self, isolated_torm):
        with pytest.raises(LookupError):
            isolated_torm.lookup_system("xyzzy_no_such_system")

    def test_lookup_system_at_n_with_single_result(self, isolated_torm):
        # @1 on a unique name returns that system; @2 is out of range.
        sys_at_1 = isolated_torm.lookup_system("Sol@1")
        assert sys_at_1.name == "Sol"

        with pytest.raises(TradeException):
            isolated_torm.lookup_system("Sol@2")

    def test_lookup_system_at_n_with_duplicate_systems(self, torm_with_dupsys):
        torm = torm_with_dupsys

        with pytest.raises(AmbiguityError):
            torm.lookup_system("Zeta Dup")

        sys1 = torm.lookup_system("Zeta Dup@1")
        sys2 = torm.lookup_system("Zeta Dup@2")

        # Results ordered by pos_x: -100.0 before 100.0
        assert sys1.pos_x == pytest.approx(-100.0)
        assert sys2.pos_x == pytest.approx(100.0)
        assert sys1.system_id != sys2.system_id

        with pytest.raises(TradeException):
            torm.lookup_system("Zeta Dup@3")

    def test_lookup_system_non_string_raises_type_error(self, isolated_torm):
        with pytest.raises(TypeError):
            isolated_torm.lookup_system(42)

    def test_lookup_system_slash_not_parsed(self, isolated_torm):
        # lookup_system() does not parse place syntax; slash belongs to lookup_place().
        with pytest.raises(LookupError):
            isolated_torm.lookup_system("Sol/Abraham Lincoln")

    def test_lookup_system_leading_at_not_index(self, isolated_torm):
        # "@1" has @ at position 0 — not a valid @N suffix.
        with pytest.raises(LookupError):
            isolated_torm.lookup_system("@1")

    def test_lookup_system_passthrough_orm_objects(self, isolated_torm):
        system = isolated_torm.lookup_system("Sol")
        station = isolated_torm.lookup_station("Abraham Lincoln")

        assert isolated_torm.lookup_system(system) is system
        assert isolated_torm.lookup_system(station).system_id == system.system_id


class TestLookupStation:
    """Station lookup by name, case sensitivity, scoping, and error cases."""

    def test_passthrough_station(self, isolated_torm):
        stn = isolated_torm.lookup_station("Abraham Lincoln")
        assert isolated_torm.lookup_station(stn) is stn

    def test_passthrough_system_single_station(self, isolated_torm):
        # CD-37 15492 has exactly one station in the fixture.
        sys_obj = isolated_torm.lookup_system("CD-37 15492")
        result = isolated_torm.lookup_station(sys_obj)
        assert result.name == "Marianne Station"

    def test_passthrough_system_multiple_stations(self, isolated_torm):
        sys_obj = isolated_torm.lookup_system("Sol")
        with pytest.raises(SystemNotStationError):
            isolated_torm.lookup_station(sys_obj)

    def test_non_str_raises_type_error(self, isolated_torm):
        with pytest.raises(TypeError):
            isolated_torm.lookup_station(42)

    def test_exact_case_insensitive(self, isolated_torm):
        lower = isolated_torm.lookup_station("abraham lincoln")
        upper = isolated_torm.lookup_station("ABRAHAM LINCOLN")
        mixed = isolated_torm.lookup_station("Abraham Lincoln")
        assert lower.name == "Abraham Lincoln"
        assert upper.station_id == lower.station_id
        assert mixed.station_id == lower.station_id

    def test_not_found_raises_lookup_error(self, isolated_torm):
        with pytest.raises(LookupError):
            isolated_torm.lookup_station("xyzzy_no_such_station")

    def test_with_system_arg_scoped(self, isolated_torm):
        stn = isolated_torm.lookup_station("Abraham Lincoln", system="Sol")
        assert stn.name == "Abraham Lincoln"
        assert stn.system.name == "Sol"

    def test_with_system_arg_station_not_found(self, isolated_torm):
        with pytest.raises(LookupError):
            isolated_torm.lookup_station("xyzzy_no_station", system="Sol")

    def test_with_invalid_system_raises_lookup_error(self, isolated_torm):
        with pytest.raises(LookupError):
            isolated_torm.lookup_station("Abraham Lincoln", system="xyzzy_no_system")

    def test_system_name_single_station_returns_that_station(self, isolated_torm):
        # Dual scan: exact station query misses; exact system query hits; 1 station → return it.
        stn = isolated_torm.lookup_station("CD-37 15492")
        assert stn.name == "Marianne Station"

    def test_system_name_multiple_stations_raises_system_not_station_error(self, isolated_torm):
        with pytest.raises(SystemNotStationError, match=r"System 'Sol' has"):
            isolated_torm.lookup_station("Sol")

    def test_dual_scan_station_wins_when_same_system(self, torm_with_named_station):
        # "Namedville" hits both exact station and exact system; station.system == system → station wins.
        result = torm_with_named_station.lookup_station("Namedville")
        assert isinstance(result, orm.Station)
        assert result.name == "Namedville"

    def test_wildcard_guard(self, isolated_torm):
        with pytest.raises(TradeException):
            isolated_torm.lookup_station("%")


class TestLookupPlace:
    """Place lookup by name, syntax variants, scoping, and error cases."""

    def test_passthrough_system(self, isolated_torm):
        sys_obj = isolated_torm.lookup_system("Sol")
        assert isolated_torm.lookup_place(sys_obj) is sys_obj

    def test_passthrough_station(self, isolated_torm):
        stn = isolated_torm.lookup_station("Abraham Lincoln")
        assert isolated_torm.lookup_place(stn) is stn

    def test_non_str_raises_type_error(self, isolated_torm):
        with pytest.raises(TypeError):
            isolated_torm.lookup_place(42)

    def test_bare_system_name_returns_system(self, isolated_torm):
        result = isolated_torm.lookup_place("Sol")
        assert isinstance(result, orm.System)
        assert result.name == "Sol"

    def test_at_annotation_returns_system(self, isolated_torm):
        result = isolated_torm.lookup_place("@Sol")
        assert isinstance(result, orm.System)
        assert result.name == "Sol"

    def test_bare_name_fallback_to_station(self, isolated_torm):
        # "Abraham Lincoln" is not a system; fast path falls through to global station search.
        result = isolated_torm.lookup_place("Abraham Lincoln")
        assert isinstance(result, orm.Station)
        assert result.name == "Abraham Lincoln"

    def test_at_annotation_no_station_fallback(self, isolated_torm):
        # "@name" with no matching system raises LookupError — @ suppresses station fallback.
        with pytest.raises(LookupError):
            isolated_torm.lookup_place("@Abraham Lincoln")

    def test_leading_slash_station(self, isolated_torm):
        result = isolated_torm.lookup_place("/Abraham Lincoln")
        assert isinstance(result, orm.Station)
        assert result.name == "Abraham Lincoln"

    def test_compound_system_station(self, isolated_torm):
        result = isolated_torm.lookup_place("Sol/Abraham Lincoln")
        assert isinstance(result, orm.Station)
        assert result.name == "Abraham Lincoln"
        assert result.system.name == "Sol"

    def test_compound_backslash_separator(self, isolated_torm):
        result = isolated_torm.lookup_place("Sol\\Abraham Lincoln")
        assert isinstance(result, orm.Station)
        assert result.name == "Abraham Lincoln"

    def test_compound_at_annotation(self, isolated_torm):
        result = isolated_torm.lookup_place("@Sol/Abraham Lincoln")
        assert isinstance(result, orm.Station)
        assert result.name == "Abraham Lincoln"
        assert result.system.name == "Sol"

    def test_unknown_system_falls_back_to_global_station(self, isolated_torm):
        # When the system part matches nothing, station search is global.
        result = isolated_torm.lookup_place("xyzzy_no_system/Abraham Lincoln")
        assert isinstance(result, orm.Station)
        assert result.name == "Abraham Lincoln"

    def test_compound_station_not_found(self, isolated_torm):
        with pytest.raises(LookupError):
            isolated_torm.lookup_place("Sol/xyzzy_no_station")

    def test_not_found_raises_lookup_error(self, isolated_torm):
        with pytest.raises(LookupError):
            isolated_torm.lookup_place("xyzzy_no_such_place")

    def test_at_n_in_compound_not_interpreted_as_disambiguation(self, torm_with_dupsys):
        # "Zeta Dup@1" is treated as a literal system string (no match), so station
        # search falls back to global.  "Blanco Manufacturing Forge" exists in two
        # systems → AmbiguityError proves @N was NOT used to scope the system part.
        with pytest.raises(AmbiguityError):
            torm_with_dupsys.lookup_place("Zeta Dup@1/Blanco Manufacturing Forge")

    def test_duplicate_system_stations_found_in_combined_candidates(
        self, torm_with_dupsys_and_station
    ):
        # Both "Zeta Dup" systems match; "Zeta Station" lives in the first one.
        # The combined candidate set allows it to be found uniquely.
        result = torm_with_dupsys_and_station.lookup_place("Zeta Dup/Zeta Station")
        assert isinstance(result, orm.Station)
        assert result.name == "Zeta Station"

    def test_wildcard_guard(self, isolated_torm):
        with pytest.raises(TradeException):
            isolated_torm.lookup_place("%")


@pytest.fixture()
def torm_with_crossname_ambiguity(isolated_torm):
    """System 'Crossmatch' + station 'Crossmatch' in Sol (a different system).

    When lookup_station("Crossmatch") runs the dual scan:
    - stn_results: 1 station (in Sol)
    - sys_results: 1 system (Crossmatch)
    - station.system_id != sys_obj.system_id → AmbiguityError
    """
    from sqlalchemy import text
    session = isolated_torm.session
    max_sys_id = session.execute(text("SELECT MAX(system_id) FROM System")).scalar()
    max_stn_id = session.execute(text("SELECT MAX(station_id) FROM Station")).scalar()
    sol_id = session.execute(
        text("SELECT system_id FROM System WHERE name = 'Sol'")
    ).scalar()
    session.execute(
        text(
            "INSERT INTO System (system_id, name, pos_x, pos_y, pos_z, modified) "
            "VALUES (:id, 'Crossmatch', 500.0, 500.0, 500.0, datetime('now'))"
        ),
        {"id": max_sys_id + 1},
    )
    session.execute(
        text(
            "INSERT INTO Station "
            "(station_id, name, system_id, ls_from_star, blackmarket, max_pad_size, "
            "market, shipyard, outfitting, rearm, refuel, repair, planetary, type_id, modified) "
            "VALUES (:id, 'Crossmatch', :sys_id, 0, '?', '?', '?', '?', '?', '?', '?', '?', '?', 0, datetime('now'))"
        ),
        {"id": max_stn_id + 1, "sys_id": sol_id},
    )
    session.commit()
    session.expire_all()
    yield isolated_torm


class TestAmbiguityAndAtNDisambiguation:
    """Ambiguity propagation and @N disambiguation across all three lookup methods."""

    def test_lookup_place_fast_path_propagates_ambiguity_error(self, torm_with_dupsys):
        # Duplicate system name → lookup_system raises AmbiguityError → propagates.
        with pytest.raises(AmbiguityError):
            torm_with_dupsys.lookup_place("Zeta Dup")

    def test_lookup_place_at_n_disambiguates_to_first_system(self, torm_with_dupsys):
        result = torm_with_dupsys.lookup_place("Zeta Dup@1")
        assert isinstance(result, orm.System)
        assert result.pos_x == pytest.approx(-100.0)

    def test_lookup_place_at_n_disambiguates_to_second_system(self, torm_with_dupsys):
        result = torm_with_dupsys.lookup_place("Zeta Dup@2")
        assert isinstance(result, orm.System)
        assert result.pos_x == pytest.approx(100.0)

    def test_lookup_place_at_annotation_with_at_n(self, torm_with_dupsys):
        # "@Zeta Dup@1": leading @ stripped → bare "Zeta Dup@1" → lookup_system("Zeta Dup@1").
        result = torm_with_dupsys.lookup_place("@Zeta Dup@1")
        assert isinstance(result, orm.System)
        assert result.pos_x == pytest.approx(-100.0)

    def test_lookup_place_at_n_out_of_range_propagates_trade_exception(self, torm_with_dupsys):
        with pytest.raises(TradeException):
            torm_with_dupsys.lookup_place("Zeta Dup@99")

    def test_lookup_station_at_n_not_interpreted_as_disambiguation(self, torm_with_dupsys):
        # "Zeta Dup@1" is passed as a literal station/system name string.
        # No station or system is named "Zeta Dup@1" → LookupError.
        with pytest.raises(LookupError):
            torm_with_dupsys.lookup_station("Zeta Dup@1")

    def test_lookup_station_dual_scan_cross_name_ambiguity(self, torm_with_crossname_ambiguity):
        # Station "Crossmatch" (in Sol) + system "Crossmatch" both match exactly,
        # but they refer to different systems → AmbiguityError.
        with pytest.raises(AmbiguityError):
            torm_with_crossname_ambiguity.lookup_station("Crossmatch")


class TestPartialMatching:
    """Partial (prefix and substring) matching for all three lookup methods."""

    # -- lookup_system partial --

    def test_lookup_system_partial_word_prefix(self, isolated_torm):
        # "Sigma Dra" misses the exact query; prefix "SIGMA" narrows candidates;
        # _list_search finds "Sigma Draconis" via partial match.
        result = isolated_torm.lookup_system("Sigma Dra")
        assert result.name == "Sigma Draconis"

    def test_lookup_system_partial_ambiguous_raises(self, isolated_torm):
        # "Luyten" is a prefix of several Luyten-* systems → AmbiguityError.
        with pytest.raises(AmbiguityError):
            isolated_torm.lookup_system("Luyten")

    def test_lookup_system_not_found_still_raises_lookup_error(self, isolated_torm):
        with pytest.raises(LookupError):
            isolated_torm.lookup_system("xyzzy_no_such_system_f6")

    # -- lookup_station partial --

    def test_lookup_station_partial_ambiguous_raises(self, isolated_torm):
        # "Blanco Manuf" is a prefix of both "Blanco Manufacturing Forge"
        # stations → AmbiguityError.
        with pytest.raises(AmbiguityError):
            isolated_torm.lookup_station("Blanco Manuf")

    def test_lookup_station_partial_scoped_to_system(self, isolated_torm):
        # With a system arg, partial matching pulls all stations in that system.
        result = isolated_torm.lookup_station(
            "Blanco Manuf", system="Lushertha"
        )
        assert result.name == "Blanco Manufacturing Forge"
        assert result.system.name == "Lushertha"

    def test_lookup_station_partial_not_found_raises(self, isolated_torm):
        with pytest.raises(LookupError):
            isolated_torm.lookup_station("xyzzy_no_station_f6")

    # -- lookup_place slow-path partial: station word match --

    def test_lookup_place_compound_partial_station_word_match(self, isolated_torm):
        # "Dunyach" is a word-boundary prefix of "Dunyach Enterprise".
        result = isolated_torm.lookup_place("Ross 490/Dunyach")
        assert isinstance(result, orm.Station)
        assert result.name == "Dunyach Enterprise"
        assert result.system.name == "Ross 490"

    # -- lookup_place slow-path partial: interior substring (any_match) --

    def test_lookup_place_compound_partial_station_any_match(self, isolated_torm):
        # "braham" appears inside "Abraham Lincoln" but not at a word boundary
        # → any_match tier.
        result = isolated_torm.lookup_place("Sol/braham")
        assert isinstance(result, orm.Station)
        assert result.name == "Abraham Lincoln"
        assert result.system.name == "Sol"

    # -- lookup_place slow-path partial: both parts partial --

    def test_lookup_place_compound_partial_both_parts(self, isolated_torm):
        # "ross 49" hits "Ross 490" via any_match; "Dunyach" hits "Dunyach
        # Enterprise" via word_match within the scoped station set.
        result = isolated_torm.lookup_place("ross 49/Dunyach")
        assert isinstance(result, orm.Station)
        assert result.name == "Dunyach Enterprise"
        assert result.system.name == "Ross 490"

    # -- regression: exact paths still work after adding partial matching --

    def test_exact_system_lookup_unchanged(self, isolated_torm):
        result = isolated_torm.lookup_system("Sol")
        assert result.name == "Sol"

    def test_exact_station_fallback_in_lookup_place_unchanged(self, isolated_torm):
        # "Goo Research" is not a system; station exact match still resolves it.
        result = isolated_torm.lookup_place("Goo Research")
        assert isinstance(result, orm.Station)
        assert result.name == "Goo Research"
        assert result.system.name == "LHS 3799"

    # -- @N in partial path: treated as literal, not disambiguated --

    def test_lookup_system_at_n_partial_not_disambiguated(self, torm_with_dupsys):
        # "Zeta@1": exact query for base name "Zeta" misses; partial path uses the
        # full name "Zeta@1" as the search token — no system name contains that
        # literal string, so LookupError is raised.  @N only disambiguates in the
        # exact tier (documented legacy behaviour preserved for parity).
        with pytest.raises(LookupError):
            torm_with_dupsys.lookup_system("Zeta@1")

    # -- interior-suffix partial match: two-step ILIKE required --

    def test_lookup_system_interior_suffix(self, isolated_torm):
        # "Draconis" is a suffix of "Sigma Draconis", not a prefix.
        # Prefix ILIKE 'DRACONIS%' returns nothing; interior ILIKE '%Draconis%'
        # is required to surface the candidate.
        result = isolated_torm.lookup_system("Draconis")
        assert result.name == "Sigma Draconis"

    def test_lookup_place_compound_system_interior(self, isolated_torm):
        # "490" is an interior token of "Ross 490", not a prefix.
        # Prefix ILIKE '490%' returns nothing; interior ILIKE '%490%' finds it.
        result = isolated_torm.lookup_place("490/Dunyach")
        assert isinstance(result, orm.Station)
        assert result.name == "Dunyach Enterprise"
        assert result.system.name == "Ross 490"

    # -- deliberate limitation: punctuation-normalised interior not supported --

    def test_lookup_system_punctuation_normalised_interior_no_match(self, isolated_torm):
        # "CD37" would match "CD-37 15492" after stage-1 normalisation strips the
        # hyphen, but the ORM searches raw names via ILIKE with no normalised column.
        # Deliberate divergence from the legacy resolver — documented in
        # RESOLVER_CONTRACT.md under "DELIBERATE ORM CHANGE".
        with pytest.raises(LookupError):
            isolated_torm.lookup_system("CD37")
