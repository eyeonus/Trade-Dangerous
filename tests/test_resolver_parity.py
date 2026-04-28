"""
Resolver parity tests — Checkpoint F2.

Documents and locks the lookup semantics of the legacy TradeDB resolver so that
the ORM-first replacement (F3+) can be verified for parity.

Every test here corresponds to a row in the parity matrix in docs/RESOLVER_CONTRACT.md.
Tests are grouped by the function under test.  Fixture data comes from the sol-25ly
v13 fixture pack; synthetic duplicate-name systems are injected where the real bubble
data does not provide the required shape.
"""
from __future__ import annotations

import pytest

from tradedangerous.tradedb import TradeDB, System as TDBSystem
from tradedangerous.tradeexcept import AmbiguityError, SystemNotStationError, TradeException

from .helpers import isolated_tdb


@pytest.fixture()
def tdb_with_dupsys(isolated_tdb):
    """TradeDB with two synthetic 'Zeta Dup' systems for @N disambiguation testing.

    Injects directly into the in-memory caches to avoid the SA/BigInteger PK issue
    with addLocalSystem on SQLite.  The @N tests only exercise lookupSystem, which
    operates entirely on systemByName/systemByID.

    sys1 has posX=-100 → @1 (sorted first by X).
    sys2 has posX=+100 → @2 (sorted second by X).
    """
    max_id = max(isolated_tdb.systemByID.keys())
    sys1 = TDBSystem(max_id + 1, "ZETA DUP", -100.0, 0.0, 0.0)
    sys2 = TDBSystem(max_id + 2, "ZETA DUP", 100.0, 0.0, 0.0)

    isolated_tdb.systemByID[sys1.ID] = sys1
    isolated_tdb.systemByID[sys2.ID] = sys2
    isolated_tdb.systemByName["ZETA DUP"] = sorted(
        [sys1, sys2], key=lambda s: (s.posX, s.posY, s.posZ, s.ID)
    )

    return isolated_tdb, sys1, sys2


# ---------------------------------------------------------------------------
# Normalization pipeline
# ---------------------------------------------------------------------------

class TestNormalization:
    """Unit tests for the two-stage normalization pipeline (no DB fixture needed)."""

    def test_stage1_uppercases_letters(self):
        assert "hello world".translate(TradeDB.normalizeTrans) == "HELLO WORLD"

    def test_stage1_strips_punctuation_set(self):
        # Characters deleted by stage 1: [ ] ( ) * + - . , { } :
        result = "A[B](C)*+-.D,{E}:F".translate(TradeDB.normalizeTrans)
        assert result == "ABCDEF"

    def test_stage1_preserves_spaces_and_apostrophes(self):
        # Spaces and apostrophes survive stage 1 — stage 2 removes them.
        result = "Foo Bar O'Brien".translate(TradeDB.normalizeTrans)
        assert result == "FOO BAR O'BRIEN"

    def test_stage2_strips_spaces_and_apostrophes(self):
        result = "FOO BAR O'BRIEN".translate(TradeDB.trimTrans)
        assert result == "FOOBAROBRIEN"

    def test_combined_pipeline_apostrophe_item(self):
        s = "Baltah'sine Vacuum Krill"
        stage1 = s.translate(TradeDB.normalizeTrans)
        assert stage1 == "BALTAH'SINE VACUUM KRILL"
        stage2 = stage1.translate(TradeDB.trimTrans)
        assert stage2 == "BALTAHSINEVACUUMKRILL"

    def test_stage1_strips_hyphen_in_sector_name(self):
        result = "Jastreb Sector CL-Y d145".translate(TradeDB.normalizeTrans)
        assert result == "JASTREB SECTOR CLY D145"


# ---------------------------------------------------------------------------
# lookupSystem
# ---------------------------------------------------------------------------

class TestLookupSystem:

    def test_exact_match_preserves_dbname(self, isolated_tdb):
        assert isolated_tdb.lookupSystem("Sol").dbname == "Sol"

    def test_exact_match_case_insensitive(self, isolated_tdb):
        # systemByName key is uppercased — "sol".upper() hits the same bucket as "Sol".
        assert isolated_tdb.lookupSystem("sol").dbname == "Sol"

    def test_exact_match_mixed_case(self, isolated_tdb):
        assert isolated_tdb.lookupSystem("lHs 3799").dbname == "LHS 3799"

    def test_partial_match_via_list_search_fallback(self, isolated_tdb):
        # "Sigma Dra" misses the exact dict key → listSearch → unique match.
        assert isolated_tdb.lookupSystem("Sigma Dra").dbname == "Sigma Draconis"

    def test_partial_match_ambiguous_raises(self, isolated_tdb):
        # "Luyten" matches six Luyten-* systems in the fixture.
        with pytest.raises(AmbiguityError):
            isolated_tdb.lookupSystem("Luyten")

    def test_not_found_raises_lookup_error(self, isolated_tdb):
        with pytest.raises(LookupError):
            isolated_tdb.lookupSystem("xyzzy_not_a_system")

    def test_pass_through_system_object(self, isolated_tdb):
        sol = isolated_tdb.lookupSystem("Sol")
        assert isolated_tdb.lookupSystem(sol) is sol

    def test_pass_through_station_returns_its_system(self, isolated_tdb):
        station = isolated_tdb.lookupPlace("Sol/Abraham Lincoln")
        result = isolated_tdb.lookupSystem(station)
        assert result.dbname == "Sol"

    def test_leading_at_is_not_stripped_in_lookup_system(self, isolated_tdb):
        # "@Sol" is a lookupPlace annotation concept, not a lookupSystem concept.
        # lookupSystem looks for a system literally named "@SOL" — not found.
        with pytest.raises(LookupError):
            isolated_tdb.lookupSystem("@Sol")


# ---------------------------------------------------------------------------
# lookupSystem — @N disambiguation
# ---------------------------------------------------------------------------

class TestLookupSystemAtN:

    def test_at1_returns_first_by_coordinate_order(self, tdb_with_dupsys):
        tdb, sys1, sys2 = tdb_with_dupsys
        assert tdb.lookupSystem("Zeta Dup@1") is sys1

    def test_at2_returns_second_by_coordinate_order(self, tdb_with_dupsys):
        tdb, sys1, sys2 = tdb_with_dupsys
        assert tdb.lookupSystem("Zeta Dup@2") is sys2

    def test_no_index_with_duplicate_name_raises_ambiguity(self, tdb_with_dupsys):
        tdb, sys1, sys2 = tdb_with_dupsys
        with pytest.raises(AmbiguityError):
            tdb.lookupSystem("Zeta Dup")

    def test_index_out_of_range_raises_trade_exception(self, tdb_with_dupsys):
        tdb, sys1, sys2 = tdb_with_dupsys
        with pytest.raises(TradeException):
            tdb.lookupSystem("Zeta Dup@99")

    def test_ordering_is_by_position_ascending_x(self, tdb_with_dupsys):
        tdb, sys1, sys2 = tdb_with_dupsys
        r1 = tdb.lookupSystem("Zeta Dup@1")
        r2 = tdb.lookupSystem("Zeta Dup@2")
        assert r1.posX < r2.posX


# ---------------------------------------------------------------------------
# lookupPlace — fast path
# ---------------------------------------------------------------------------

class TestLookupPlaceFastPath:

    def test_bare_system_name_returns_system(self, isolated_tdb):
        result = isolated_tdb.lookupPlace("Sol")
        assert result is isolated_tdb.lookupSystem("Sol")

    def test_at_annotation_returns_same_system_object(self, isolated_tdb):
        # "@Sol" strips the leading @ then calls lookupSystem("Sol").
        assert isolated_tdb.lookupPlace("@Sol") is isolated_tdb.lookupPlace("Sol")

    def test_system_wins_over_station_for_bare_name(self, isolated_tdb):
        # "LHS 3799" is a system whose only station is "Goo Research".
        # lookupPlace returns the System, not the station.
        result = isolated_tdb.lookupPlace("LHS 3799")
        assert result is isolated_tdb.lookupSystem("LHS 3799")

    def test_fast_path_ambiguity_propagates_immediately(self, isolated_tdb):
        # lookupSystem raises AmbiguityError; lookupPlace does not catch it.
        with pytest.raises(AmbiguityError):
            isolated_tdb.lookupPlace("Luyten")

    def test_bare_name_misses_system_resolves_to_station(self, isolated_tdb):
        # "Goo Research" is not a system name → fast path LookupError → slow path → station.
        result = isolated_tdb.lookupPlace("Goo Research")
        assert result.dbname == "Goo Research"
        assert result.system.dbname == "LHS 3799"

    def test_unknown_bare_name_raises_lookup_error(self, isolated_tdb):
        with pytest.raises(LookupError):
            isolated_tdb.lookupPlace("xyzzy_no_such_place")


# ---------------------------------------------------------------------------
# lookupPlace — slow path / compound forms
# ---------------------------------------------------------------------------

class TestLookupPlaceSlowPath:

    def test_explicit_station_leading_slash(self, isolated_tdb):
        result = isolated_tdb.lookupPlace("/Abraham Lincoln")
        assert result.dbname == "Abraham Lincoln"
        assert result.system.dbname == "Sol"

    def test_compound_exact_system_and_station(self, isolated_tdb):
        result = isolated_tdb.lookupPlace("Ross 490/Dunyach Enterprise")
        assert result.dbname == "Dunyach Enterprise"
        assert result.system.dbname == "Ross 490"

    def test_compound_partial_station_word_match(self, isolated_tdb):
        # "Dunyach" is a word-start prefix of "Dunyach Enterprise" → word_match tier.
        result = isolated_tdb.lookupPlace("Ross 490/Dunyach")
        assert result.dbname == "Dunyach Enterprise"
        assert result.system.dbname == "Ross 490"

    def test_compound_partial_station_any_match(self, isolated_tdb):
        # "braham" is found inside "Abraham Lincoln" but not at a word boundary → any_match.
        result = isolated_tdb.lookupPlace("Sol/braham")
        assert result.dbname == "Abraham Lincoln"
        assert result.system.dbname == "Sol"

    def test_compound_partial_both_parts(self, isolated_tdb):
        # "ross 49" hits Ross 490 via any_match; "Dunyach" hits Dunyach Enterprise via word_match.
        result = isolated_tdb.lookupPlace("ross 49/Dunyach")
        assert result.dbname == "Dunyach Enterprise"
        assert result.system.dbname == "Ross 490"

    def test_at_system_slash_station_form(self, isolated_tdb):
        result = isolated_tdb.lookupPlace("@Sol/Abraham Lincoln")
        assert result.dbname == "Abraham Lincoln"
        assert result.system.dbname == "Sol"

    def test_backslash_separator_identical_to_forward_slash(self, isolated_tdb):
        fwd = isolated_tdb.lookupPlace("Sol/Abraham Lincoln")
        bkd = isolated_tdb.lookupPlace("Sol\\Abraham Lincoln")
        assert fwd.dbname == bkd.dbname
        assert fwd.system.dbname == bkd.system.dbname

    def test_compound_nonexistent_station_raises_lookup_error(self, isolated_tdb):
        # Station not found within Sol → LookupError.
        with pytest.raises(LookupError):
            isolated_tdb.lookupPlace("Sol/xyzzy_no_station")

    def test_compound_unknown_system_falls_back_to_global_station_search(self, isolated_tdb):
        # When the system part matches nothing, station lookup is global.
        # "Abraham Lincoln" is unique across all stations → returned without error.
        result = isolated_tdb.lookupPlace("xyzzy_no_system/Abraham Lincoln")
        assert result.dbname == "Abraham Lincoln"
        assert result.system.dbname == "Sol"

    def test_bare_duplicate_station_name_raises_ambiguity(self, isolated_tdb):
        # "Blanco Manufacturing Forge" exists in Lushertha and Jastreb Sector CL-Y d145.
        # Fast path: lookupSystem raises LookupError. Slow path: station _lookup finds two
        # exact matches → AmbiguityError.
        with pytest.raises(AmbiguityError):
            isolated_tdb.lookupPlace("Blanco Manufacturing Forge")


# ---------------------------------------------------------------------------
# lookupStation
# ---------------------------------------------------------------------------

class TestLookupStation:

    def test_exact_station_name(self, isolated_tdb):
        result = isolated_tdb.lookupStation("Abraham Lincoln")
        assert result.dbname == "Abraham Lincoln"
        assert result.system.dbname == "Sol"

    def test_pass_through_station_object(self, isolated_tdb):
        station = isolated_tdb.lookupStation("Abraham Lincoln")
        assert isolated_tdb.lookupStation(station) is station

    def test_system_with_one_station_returns_station(self, isolated_tdb):
        lhs3799 = isolated_tdb.lookupSystem("LHS 3799")
        result = isolated_tdb.lookupStation(lhs3799)
        assert result.dbname == "Goo Research"
        assert result.system is lhs3799

    def test_system_with_multiple_stations_raises(self, isolated_tdb):
        sol = isolated_tdb.lookupSystem("Sol")
        with pytest.raises(SystemNotStationError):
            isolated_tdb.lookupStation(sol)

    def test_with_system_arg_scopes_to_that_system(self, isolated_tdb):
        result = isolated_tdb.lookupStation("Dunyach Enterprise", system="Ross 490")
        assert result.dbname == "Dunyach Enterprise"
        assert result.system.dbname == "Ross 490"

    def test_exact_duplicate_station_name_returns_first_match(self, isolated_tdb):
        # listSearch exact-match short-circuits: the first "Blanco Manufacturing Forge"
        # hit returns immediately without checking for other candidates.
        result = isolated_tdb.lookupStation("Blanco Manufacturing Forge")
        assert result.dbname == "Blanco Manufacturing Forge"

    def test_partial_duplicate_station_name_raises_ambiguity(self, isolated_tdb):
        # A partial that isn't an exact normalized match hits partialMatch for both
        # "Blanco Manufacturing Forge" stations → AmbiguityError.
        with pytest.raises(AmbiguityError):
            isolated_tdb.lookupStation("Blanco Manuf")

    def test_duplicate_disambiguated_by_system_arg(self, isolated_tdb):
        lushertha = isolated_tdb.lookupStation(
            "Blanco Manufacturing Forge", system="Lushertha"
        )
        jastreb = isolated_tdb.lookupStation(
            "Blanco Manufacturing Forge", system="Jastreb Sector CL-Y d145"
        )
        assert lushertha.dbname == "Blanco Manufacturing Forge"
        assert lushertha.system.dbname == "Lushertha"
        assert jastreb.dbname == "Blanco Manufacturing Forge"
        assert jastreb.system.dbname == "Jastreb Sector CL-Y d145"
        assert lushertha.ID != jastreb.ID

    def test_not_found_raises_lookup_error(self, isolated_tdb):
        with pytest.raises(LookupError):
            isolated_tdb.lookupStation("xyzzy_no_such_station")


# ---------------------------------------------------------------------------
# lookupItem
# ---------------------------------------------------------------------------

class TestLookupItem:

    def test_exact_item_name(self, isolated_tdb):
        result = isolated_tdb.lookupItem("Gold")
        assert result.dbname == "Gold"

    def test_exact_match_case_insensitive(self, isolated_tdb):
        # Both "gold" and "Gold" normalize to "GOLD" — same exact-match bucket.
        result = isolated_tdb.lookupItem("gold")
        assert result.dbname == "Gold"

    def test_partial_match_word_start(self, isolated_tdb):
        # "Bertrand" is a word-start prefix of "Bertrandite" only → unique word_match.
        result = isolated_tdb.lookupItem("Bertrand")
        assert result.dbname == "Bertrandite"

    def test_apostrophe_item_partial_match(self, isolated_tdb):
        # "Baltah" hits word boundary before the apostrophe in "Baltah'sine Vacuum Krill".
        result = isolated_tdb.lookupItem("Baltah")
        assert result.dbname == "Baltah'sine Vacuum Krill"

    def test_not_found_raises_lookup_error(self, isolated_tdb):
        with pytest.raises(LookupError):
            isolated_tdb.lookupItem("xyzzy_no_such_item")


# ---------------------------------------------------------------------------
# @N boundary — lock down that @N is NOT silently extended
# ---------------------------------------------------------------------------

class TestAtNBoundary:
    """These tests document intentional limitations of @N disambiguation.

    Do not 'fix' these without an explicit decision and a test update — doing so
    would silently change the resolver contract.
    """

    def test_at_n_works_in_fast_path_not_slow_path_compound(self, tdb_with_dupsys):
        tdb, sys1, sys2 = tdb_with_dupsys
        # Fast path (bare name): "Zeta Dup@1" IS resolved via @N.
        assert tdb.lookupSystem("Zeta Dup@1") is sys1
        # Slow path (compound form, slash present): "Zeta Dup@1" is a literal system name.
        # "ZETA DUP@1" does not exist in systemByName → no system match → LookupError.
        with pytest.raises(LookupError):
            tdb.lookupPlace("Zeta Dup@1/zzz_no_station")

    def test_at_n_not_applied_in_lookup_station(self, tdb_with_dupsys):
        # lookupStation passes the name directly to listSearch; @N is not stripped.
        tdb, sys1, sys2 = tdb_with_dupsys
        with pytest.raises(LookupError):
            tdb.lookupStation("Zeta Dup@1")

    def test_at_n_silently_stops_working_when_exact_key_misses(self, tdb_with_dupsys):
        # DOCUMENTED LEGACY BUG: if the exact-dict key for base_name misses,
        # lookupSystem falls to listSearch with the *full* name including @N.
        # listSearch treats "@1" as part of the search string — no disambiguation.
        # "Zeta@1": base_name="Zeta", exact key "ZETA" → KeyError → listSearch("Zeta@1")
        # → "ZETA@1" not found as a substring in any system name → LookupError.
        tdb, sys1, sys2 = tdb_with_dupsys
        with pytest.raises(LookupError):
            tdb.lookupSystem("Zeta@1")
