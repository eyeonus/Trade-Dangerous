from __future__ import annotations

import gc

import pytest

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


class TestTradeORMLookup:
    def test_lookup_station_exact_partial_and_system_only_cases(self, isolated_torm):
        exact_station = isolated_torm.lookup_station("Abraham Lincoln")
        partial_station = isolated_torm.lookup_station("Abraham Lin")
        
        assert exact_station is not None
        assert partial_station is not None
        
        assert exact_station.name == "Abraham Lincoln"
        assert exact_station.system.name == "Sol"
        
        assert partial_station.station_id == exact_station.station_id
        
        with pytest.raises(
            SystemNotStationError,
            match=r'"Sol" is a system name',
        ):
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


class TestLookupSystemF3:
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

    def test_lookup_system_partial_raises_lookup_error(self, isolated_torm):
        # No partial matching in F3 — "So" is not Sol.
        with pytest.raises(LookupError):
            isolated_torm.lookup_system("So")

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
