"""Resolver contract guardrail — TradeORM.

Protects the place / system / station / item resolution contract documented in
``docs/RESOLVER_CONTRACT.md`` §0 (the v13 ORM resolver). These are scenario tests
on the shared ``TradeORM`` lookups that every command and the planner depend on,
so a failure here names the contract that broke.

This is **not** legacy ``TradeDB`` parity — that comparison was retired with the
in-memory engine. The exhaustive edge-case suite lives in
``test_tradeorm_lookup_db.py``; this module is the focused, readable contract
guard.
"""
from __future__ import annotations

import gc

import pytest

from sqlalchemy import text

from tradedangerous.db import orm_models as orm
from tradedangerous.tradeexcept import (
    AmbiguityError, SystemNotStationError, TradeException,
)
from tradedangerous.tradeorm import TradeORM

from .helpers import isolated_trade_env


@pytest.fixture()
def isolated_torm(isolated_trade_env):
    """A TradeORM bound to the isolated fixture database."""
    instance = TradeORM()
    yield instance
    instance.session.close()
    instance.engine.dispose()
    del instance
    gc.collect()


@pytest.fixture()
def torm_dup_systems(isolated_torm):
    """Inject two same-named 'Zeta Dup' systems for duplicate / @N coverage.

    Ordered by (pos_x, pos_y, pos_z, system_id), so @1 is the pos_x=-100 system
    and @2 is the pos_x=+100 one.
    """
    session = isolated_torm.session
    max_id = session.execute(text("SELECT MAX(system_id) FROM System")).scalar()
    for offset, pos_x in ((1, -100.0), (2, 100.0)):
        session.execute(
            text(
                "INSERT INTO System (system_id, name, pos_x, pos_y, pos_z, modified) "
                "VALUES (:id, 'Zeta Dup', :x, 0.0, 0.0, datetime('now'))"
            ),
            {"id": max_id + offset, "x": pos_x},
        )
    session.commit()
    session.expire_all()
    yield isolated_torm


class TestLookupPlaceSyntax:
    """The accepted-syntax table: the form picks the namespace."""

    def test_bare_name_returns_system(self, isolated_torm):
        result = isolated_torm.lookup_place("Sol")
        assert isinstance(result, orm.System)
        assert result.name == "Sol"

    def test_bare_station_partial_falls_back_to_station(self, isolated_torm):
        # "hamlinc" names no system, so it falls back to a station search.
        result = isolated_torm.lookup_place("hamlinc")
        assert isinstance(result, orm.Station)
        assert result.name == "Abraham Lincoln"
        assert result.system.name == "Sol"

    def test_leading_slash_forces_station(self, isolated_torm):
        result = isolated_torm.lookup_place("/hamlinc")
        assert isinstance(result, orm.Station)
        assert result.name == "Abraham Lincoln"

    def test_compound_scopes_station_to_system(self, isolated_torm):
        result = isolated_torm.lookup_place("Sol/hamlinc")
        assert isinstance(result, orm.Station)
        assert result.name == "Abraham Lincoln"
        assert result.system.name == "Sol"

    def test_backslash_is_treated_as_forward_slash(self, isolated_torm):
        fwd = isolated_torm.lookup_place("Sol/hamlinc")
        bck = isolated_torm.lookup_place("Sol\\hamlinc")
        assert isinstance(bck, orm.Station)
        assert bck.station_id == fwd.station_id

    def test_trailing_slash_forces_system(self, isolated_torm):
        result = isolated_torm.lookup_place("Sol/")
        assert isinstance(result, orm.System)
        assert result.name == "Sol"

    def test_at_annotation_forces_system(self, isolated_torm):
        result = isolated_torm.lookup_place("@Sol")
        assert isinstance(result, orm.System)
        assert result.name == "Sol"

    def test_at_annotation_compound_scopes_station(self, isolated_torm):
        result = isolated_torm.lookup_place("@Sol/hamlinc")
        assert isinstance(result, orm.Station)
        assert result.name == "Abraham Lincoln"
        assert result.system.name == "Sol"


class TestLookupPlaceResolution:
    """Precedence, fallback, and ambiguity for lookup_place."""

    def test_system_match_wins_over_station_fallback(self, isolated_torm):
        # "Test" is a system (with one station); the bare name resolves to the
        # SYSTEM because a system match wins before the station fallback runs.
        result = isolated_torm.lookup_place("Test")
        assert isinstance(result, orm.System)
        assert result.name == "Test"

    def test_unknown_bare_name_raises_lookup_error(self, isolated_torm):
        with pytest.raises(LookupError):
            isolated_torm.lookup_place("xyzzy_no_such_place")

    def test_ambiguous_station_fallback_raises(self, isolated_torm):
        # No system is named "Blanco Manufacturing Forge"; the bare fallback
        # finds that station in two systems -> ambiguity.
        with pytest.raises(AmbiguityError):
            isolated_torm.lookup_place("Blanco Manufacturing Forge")

    def test_compound_unknown_station_in_system_raises(self, isolated_torm):
        with pytest.raises(LookupError):
            isolated_torm.lookup_place("Sol/xyzzy_no_station")


class TestLookupPlaceDuplicateSystems:
    """@N disambiguation and duplicate-system ambiguity (synthetic fixture)."""

    def test_bare_duplicate_system_name_raises_ambiguity(self, torm_dup_systems):
        with pytest.raises(AmbiguityError):
            torm_dup_systems.lookup_place("Zeta Dup")

    def test_at_n_selects_first_duplicate(self, torm_dup_systems):
        result = torm_dup_systems.lookup_place("Zeta Dup@1")
        assert isinstance(result, orm.System)
        assert result.pos_x == pytest.approx(-100.0)

    def test_at_n_selects_second_duplicate(self, torm_dup_systems):
        result = torm_dup_systems.lookup_place("Zeta Dup@2")
        assert isinstance(result, orm.System)
        assert result.pos_x == pytest.approx(100.0)

    def test_invalid_at_n_reports_error(self, torm_dup_systems):
        with pytest.raises(TradeException):
            torm_dup_systems.lookup_place("Zeta Dup@99")


class TestLookupStation:
    """lookup_station is station-only: it returns a Station or raises."""

    def test_exact_station_name(self, isolated_torm):
        result = isolated_torm.lookup_station("Abraham Lincoln")
        assert isinstance(result, orm.Station)
        assert result.name == "Abraham Lincoln"

    def test_bare_partial_resolves_station(self, isolated_torm):
        result = isolated_torm.lookup_station("hamlinc")
        assert isinstance(result, orm.Station)
        assert result.name == "Abraham Lincoln"

    def test_station_object_passthrough(self, isolated_torm):
        station = isolated_torm.lookup_station("Abraham Lincoln")
        assert isolated_torm.lookup_station(station) is station

    def test_system_with_one_station_returns_that_station(self, isolated_torm):
        test_sys = isolated_torm.lookup_system("Test")
        result = isolated_torm.lookup_station(test_sys)
        assert isinstance(result, orm.Station)
        assert result.name == "Metallic Base 2"

    def test_system_with_many_stations_raises(self, isolated_torm):
        sol = isolated_torm.lookup_system("Sol")
        with pytest.raises(SystemNotStationError):
            isolated_torm.lookup_station(sol)

    def test_scoped_by_system_argument(self, isolated_torm):
        result = isolated_torm.lookup_station("Grandin Gateway", system="Altair")
        assert isinstance(result, orm.Station)
        assert result.name == "Grandin Gateway"
        assert result.system.name == "Altair"

    def test_duplicate_station_partial_raises_ambiguity(self, isolated_torm):
        # "Blanco Manuf" partially matches the duplicate station in two systems;
        # ambiguity is still real for a station-only lookup.
        with pytest.raises(AmbiguityError):
            isolated_torm.lookup_station("Blanco Manuf")

    def test_not_found_raises_lookup_error(self, isolated_torm):
        with pytest.raises(LookupError):
            isolated_torm.lookup_station("xyzzy_no_such_station")


class TestLookupSystem:
    """lookup_system is system-only: it returns a System or raises."""

    def test_exact_match(self, isolated_torm):
        assert isolated_torm.lookup_system("Sol").name == "Sol"

    def test_case_insensitive(self, isolated_torm):
        assert isolated_torm.lookup_system("sIrIuS").name == "Sirius"

    def test_fuzzy_normalised_match(self, isolated_torm):
        # Prefix / normalised match through the lookup_name column.
        assert isolated_torm.lookup_system("Sigma Dra").name == "Sigma Draconis"

    def test_ambiguous_partial_raises(self, isolated_torm):
        # Many "Luyten ..." systems share the prefix -> ambiguity.
        with pytest.raises(AmbiguityError):
            isolated_torm.lookup_system("Luyten")

    def test_unknown_raises_lookup_error(self, isolated_torm):
        with pytest.raises(LookupError):
            isolated_torm.lookup_system("xyzzy_not_a_system")

    def test_system_object_passthrough(self, isolated_torm):
        sol = isolated_torm.lookup_system("Sol")
        assert isolated_torm.lookup_system(sol) is sol

    def test_station_object_unwraps_to_parent_system(self, isolated_torm):
        station = isolated_torm.lookup_station("Abraham Lincoln")
        assert isolated_torm.lookup_system(station).name == "Sol"

    def test_at_n_selects_duplicate(self, torm_dup_systems):
        result = torm_dup_systems.lookup_system("Zeta Dup@1")
        assert result.pos_x == pytest.approx(-100.0)

    def test_invalid_at_n_raises(self, torm_dup_systems):
        with pytest.raises(TradeException):
            torm_dup_systems.lookup_system("Zeta Dup@99")


class TestLookupItem:
    """Item resolution: exact, fuzzy/normalised, ambiguous, unknown."""

    def test_exact_item(self, isolated_torm):
        assert isolated_torm.lookup_item("Gold").name == "Gold"

    def test_case_insensitive(self, isolated_torm):
        assert isolated_torm.lookup_item("gold").name == "Gold"

    def test_fuzzy_word_start(self, isolated_torm):
        assert isolated_torm.lookup_item("Bertrand").name == "Bertrandite"

    def test_normalised_apostrophe(self, isolated_torm):
        # "Baltah" -> "Baltah'sine Vacuum Krill": the apostrophe is normalised out.
        assert isolated_torm.lookup_item("Baltah").name == "Baltah'sine Vacuum Krill"

    def test_ambiguous_item_raises(self, isolated_torm):
        # "hydrog" matches Hydrogen Fuel and Hydrogen Peroxide.
        with pytest.raises(AmbiguityError):
            isolated_torm.lookup_item("hydrog")

    def test_unknown_item_raises(self, isolated_torm):
        with pytest.raises(LookupError):
            isolated_torm.lookup_item("xyzzy_no_such_item")
