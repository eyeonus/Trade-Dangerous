from types import SimpleNamespace
import gc

import pytest

from tradedangerous.commands import olddata_cmd, run_cmd
from tradedangerous.commands.commandenv import CommandEnv, Needs
from tradedangerous.commands.exceptions import (
    CommandLineError,
    FleetCarrierError,
    SettlementError,
    PadSizeError,
    PlanetaryError,
)
from tradedangerous.db import orm_models as orm
from tradedangerous.tradeorm import TradeORM

from .helpers import isolated_trade_env  # noqa: F401 — used as fixture

_FAKE_CMD = SimpleNamespace(wantsTradeDB=False, usesTradeData=False)
_RESOLVER_CMD = SimpleNamespace(needs=Needs.RESOLVER, usesTradeData=False)

def _make_env(**properties):
    return CommandEnv(properties, ['trade.py', 'test'], _FAKE_CMD)

def _make_cmd_env(cmd_module, **properties):
    return CommandEnv(properties, ['trade.py', 'test'], cmd_module)

def test_run_validateRunArgumentsFast_required_fields():
    with pytest.raises(CommandLineError, match="Missing '--capacity'"):
        run_cmd.validateRunArgumentsFast(SimpleNamespace(capacity=None, credits=1, maxLyPer=5, direct=False))
    
    with pytest.raises(CommandLineError, match="Missing '--credits'"):
        run_cmd.validateRunArgumentsFast(SimpleNamespace(capacity=10, credits=None, maxLyPer=5, direct=False))
    
    with pytest.raises(CommandLineError, match="Missing '--ly-per'"):
        run_cmd.validateRunArgumentsFast(SimpleNamespace(capacity=10, credits=100, maxLyPer=None, direct=False))

def test_run_validateRunArgumentsFast_conflict_rules():
    base = {
        'capacity': 10,
        'credits': 1000,
        'maxLyPer': 8.5,
        'direct': False,
        'goalSystem': None,
        'starting': None,
        'startJumps': 0,
        'endJumps': 0,
        'ending': None,
        'shorten': False,
        'loop': False,
        'unique': False,
        'limit': None,
        'insurance': 0,
        'loopInt': None,
    }
    
    with pytest.raises(CommandLineError, match='--towards requires --from'):
        run_cmd.validateRunArgumentsFast(SimpleNamespace(**(base | {'goalSystem': 'Sol'})))
    
    with pytest.raises(CommandLineError, match='--start-jumps requires --from'):
        run_cmd.validateRunArgumentsFast(SimpleNamespace(**(base | {'startJumps': 1})))
    
    with pytest.raises(CommandLineError, match='--end-jumps requires --to'):
        run_cmd.validateRunArgumentsFast(SimpleNamespace(**(base | {'endJumps': 1})))
    
    with pytest.raises(CommandLineError, match='--shorten only works with --to'):
        run_cmd.validateRunArgumentsFast(SimpleNamespace(**(base | {'shorten': True})))
    
    with pytest.raises(CommandLineError, match='--unique and --loop'):
        run_cmd.validateRunArgumentsFast(SimpleNamespace(**(base | {'loop': True, 'unique': True})))
    
    with pytest.raises(CommandLineError, match='--direct and --loop'):
        run_cmd.validateRunArgumentsFast(SimpleNamespace(**(base | {'loop': True, 'direct': True})))
    
    with pytest.raises(CommandLineError, match="'limit' must be <= capacity"):
        run_cmd.validateRunArgumentsFast(SimpleNamespace(**(base | {'limit': 99})))
    
    with pytest.raises(CommandLineError, match='Insurance leaves no margin for trade'):
        run_cmd.validateRunArgumentsFast(SimpleNamespace(**(base | {'insurance': 1042})))
    
    with pytest.raises(CommandLineError, match='--loop-int must be 2 or higher'):
        run_cmd.validateRunArgumentsFast(SimpleNamespace(**(base | {'loopInt': 1})))

def test_olddata_validateRunArgumentsFast_requires_near_for_route():
    with pytest.raises(CommandLineError, match='--route requires --near'):
        olddata_cmd.validateRunArgumentsFast(SimpleNamespace(route=True, near=None))

def test_commandenv_checkPadSize_normalizes_and_rejects_invalid():
    env = _make_env(padSize='m?slm')
    env.checkPadSize()
    assert env.padSize is None
    
    env = _make_env(padSize='mms')
    env.checkPadSize()
    assert env.padSize == 'MS'
    
    with pytest.raises(PadSizeError):
        _make_env(padSize='mx').checkPadSize()

def test_commandenv_checkPlanetaryFleetSettlement_normalize_or_reject():
    env = _make_env(planetary='yny', fleet='?ny', settlement='n?y')
    env.checkPlanetary()
    env.checkFleet()
    env.checkSettlement()
    assert env.planetary == 'NY'
    assert env.fleet is None
    assert env.settlement is None

    with pytest.raises(PlanetaryError):
        _make_env(planetary='yz').checkPlanetary()
    with pytest.raises(FleetCarrierError):
        _make_env(fleet='za').checkFleet()
    with pytest.raises(SettlementError):
        _make_env(settlement='zn').checkSettlement()


def test_commandenv_needs_explicit_resolver():
    """Commands declaring Needs.RESOLVER receive TradeORM; no legacy DB loaded."""
    from tradedangerous.commands import trade_cmd, export_cmd
    for cmd in (trade_cmd, export_cmd):
        env = _make_cmd_env(cmd)
        assert env.commandNeeds == Needs.RESOLVER
        assert not env.needs_legacy_db
        assert not env.needs_full_load


def test_commandenv_needs_explicit_nothing():
    """Commands declaring Needs.NOTHING require no backend at all."""
    from tradedangerous.commands import update_cmd, station_cmd, shipvendor_cmd
    for cmd in (update_cmd, station_cmd, shipvendor_cmd):
        env = _make_cmd_env(cmd)
        assert env.commandNeeds == Needs.NOTHING
        assert not env.needs_legacy_db
        assert not env.needs_full_load


def test_commandenv_needs_legacy_wantsTradeDB_false_gives_handle():
    """wantsTradeDB=False without an explicit needs= maps to LEGACY_HANDLE, not RESOLVER."""
    from tradedangerous.commands import buildcache_cmd, import_cmd
    for cmd in (buildcache_cmd, import_cmd):
        env = _make_cmd_env(cmd)
        assert env.commandNeeds == Needs.LEGACY_HANDLE
        assert env.needs_legacy_db
        assert not env.needs_full_load


def test_commandenv_needs_legacy_wantsTradeDB_true_gives_full_legacy():
    """wantsTradeDB=True (or absent) maps to FULL_LEGACY with full preload."""
    env = _make_cmd_env(run_cmd)
    assert env.commandNeeds == Needs.FULL_LEGACY
    assert env.needs_legacy_db
    assert env.needs_full_load


def test_commandenv_run_preload_fires_before_checkFromToNear(monkeypatch):
    """CommandEnv.run() must call preload(tdb) before checkFromToNear()."""
    call_order = []

    fake_cmd = SimpleNamespace(
        needs=Needs.LEGACY_HANDLE,
        preload=lambda tdb: call_order.append('preload'),
        run=lambda results, cmdenv, tdb: None,
    )

    cmdenv = CommandEnv({}, ['trade.py', 'test'], fake_cmd)
    monkeypatch.setattr(cmdenv, 'checkFromToNear', lambda: call_order.append('checkFromToNear'))
    monkeypatch.setattr(cmdenv, 'checkAvoids', lambda: None)
    monkeypatch.setattr(cmdenv, 'checkVias', lambda: None)

    cmdenv.run(SimpleNamespace())

    assert call_order.index('preload') < call_order.index('checkFromToNear')


def test_olddata_preload_exact_loader_contract():
    """olddata_cmd.preload() calls reloadCache/_loadSystems/_loadStationShell only."""
    from unittest.mock import MagicMock
    from tradedangerous.commands import olddata_cmd

    tdb = MagicMock()
    olddata_cmd.preload(tdb)

    assert tdb.reloadCache.call_count == 1
    assert tdb._loadSystems.call_count == 1
    assert tdb._loadStationShell.call_count == 1
    tdb._loadStationSummaries.assert_not_called()
    tdb._loadCategories.assert_not_called()
    tdb._loadItems.assert_not_called()


@pytest.fixture()
def isolated_torm(isolated_trade_env):
    instance = TradeORM()
    yield instance
    instance.session.close()
    instance.engine.dispose()
    del instance
    gc.collect()


def _make_orm_env(torm, **props):
    env = CommandEnv(props, ['trade.py', 'test'], _RESOLVER_CMD)
    env.tdb = torm
    return env


def test_checkFromToNearORM_near_system_sets_nearSystem(isolated_torm):
    env = _make_orm_env(isolated_torm, near='Sol', starting=None, ending=None)
    env.checkFromToNearORM()
    assert isinstance(env.nearSystem, orm.System)
    assert env.nearSystem.name == 'Sol'


def test_checkFromToNearORM_near_station_unwraps_to_system(isolated_torm):
    env = _make_orm_env(isolated_torm, near='Abraham Lincoln', starting=None, ending=None)
    env.checkFromToNearORM()
    assert isinstance(env.nearSystem, orm.System)
    assert env.nearSystem.name == 'Sol'


def test_checkFromToNearORM_starting_sets_origPlace(isolated_torm):
    env = _make_orm_env(isolated_torm, starting='Sol', ending=None, near=None)
    env.checkFromToNearORM()
    assert isinstance(env.origPlace, orm.System)
    assert env.origPlace.name == 'Sol'


def test_checkFromToNearORM_ending_sets_destPlace(isolated_torm):
    env = _make_orm_env(isolated_torm, starting=None, ending='Abraham Lincoln', near=None)
    env.checkFromToNearORM()
    assert isinstance(env.destPlace, orm.Station)
    assert env.destPlace.system.name == 'Sol'


def test_checkFromToNearORM_does_not_resolve_origin_or_dest(isolated_torm):
    """origin and dest are command-owned; invalid values must not raise or resolve."""
    env = _make_orm_env(isolated_torm, origin='~', dest='~/Some Station', near=None, starting=None, ending=None)
    env.checkFromToNearORM()
    assert not isinstance(getattr(env, 'startStation', None), orm.Station)
    assert not isinstance(getattr(env, 'stopStation', None), orm.Station)


def test_checkFromToNearORM_not_found_raises_CommandLineError(isolated_torm):
    env = _make_orm_env(isolated_torm, near='xyzzy_no_such_place', starting=None, ending=None)
    with pytest.raises(CommandLineError, match='xyzzy_no_such_place'):
        env.checkFromToNearORM()


def test_checkFromToNearORM_no_args_sets_all_none(isolated_torm):
    env = _make_orm_env(isolated_torm, near=None, starting=None, ending=None)
    env.checkFromToNearORM()
    assert env.nearSystem is None
    assert env.origPlace is None
    assert env.destPlace is None


# --- checkAvoidsORM ---

def test_checkAvoidsORM_no_avoid_sets_empty_lists(isolated_torm):
    env = _make_orm_env(isolated_torm)
    env.checkAvoidsORM()
    assert env.avoidItems == []
    assert env.avoidPlaces == []


def test_checkAvoidsORM_system_name_adds_system_to_avoidPlaces(isolated_torm):
    env = _make_orm_env(isolated_torm, avoid=['Sol'])
    env.checkAvoidsORM()
    assert len(env.avoidPlaces) == 1
    assert isinstance(env.avoidPlaces[0], orm.System)
    assert env.avoidPlaces[0].name == 'Sol'
    assert env.avoidItems == []


def test_checkAvoidsORM_station_name_adds_station_to_avoidPlaces(isolated_torm):
    env = _make_orm_env(isolated_torm, avoid=['Abraham Lincoln'])
    env.checkAvoidsORM()
    assert len(env.avoidPlaces) == 1
    assert isinstance(env.avoidPlaces[0], orm.Station)
    assert env.avoidItems == []


def test_checkAvoidsORM_item_name_adds_item_to_avoidItems(isolated_torm):
    env = _make_orm_env(isolated_torm, avoid=['Gold'])
    env.checkAvoidsORM()
    assert len(env.avoidItems) == 1
    assert isinstance(env.avoidItems[0], orm.Item)
    assert env.avoidItems[0].name == 'Gold'
    assert env.avoidPlaces == []


def test_checkAvoidsORM_multiple_args_resolves_all(isolated_torm):
    env = _make_orm_env(isolated_torm, avoid=['Sol', 'Gold'])
    env.checkAvoidsORM()
    assert len(env.avoidPlaces) == 1
    assert len(env.avoidItems) == 1


def test_checkAvoidsORM_comma_separated_resolves_all(isolated_torm):
    env = _make_orm_env(isolated_torm, avoid=['Sol,Abraham Lincoln'])
    env.checkAvoidsORM()
    assert len(env.avoidPlaces) == 2


def test_checkAvoidsORM_unknown_raises_CommandLineError(isolated_torm):
    env = _make_orm_env(isolated_torm, avoid=['xyzzy_no_such_place'])
    with pytest.raises(CommandLineError, match='xyzzy_no_such_place'):
        env.checkAvoidsORM()


def test_checkAvoidsORM_normalised_item_exact_suppresses_place_lookup(isolated_torm):
    # "HESuits" normalises identically to "H.E. Suits"; the normalised-exact
    # short-circuit must fire and leave avoidPlaces empty.
    env = _make_orm_env(isolated_torm, avoid=['HESuits'])
    env.checkAvoidsORM()
    assert len(env.avoidItems) == 1
    assert env.avoidItems[0].name == 'H.E. Suits'
    assert env.avoidPlaces == []


# --- checkViasORM ---

def test_checkViasORM_no_via_sets_empty_list(isolated_torm):
    env = _make_orm_env(isolated_torm)
    env.checkViasORM()
    assert env.viaPlaces == []


def test_checkViasORM_system_name_adds_to_viaPlaces(isolated_torm):
    env = _make_orm_env(isolated_torm, via=['Sol'])
    env.checkViasORM()
    assert len(env.viaPlaces) == 1
    assert isinstance(env.viaPlaces[0], orm.System)
    assert env.viaPlaces[0].name == 'Sol'


def test_checkViasORM_comma_separated_resolves_multiple(isolated_torm):
    env = _make_orm_env(isolated_torm, via=['Sol,Abraham Lincoln'])
    env.checkViasORM()
    assert len(env.viaPlaces) == 2


def test_checkViasORM_unknown_raises_CommandLineError(isolated_torm):
    env = _make_orm_env(isolated_torm, via=['xyzzy_no_such_place'])
    with pytest.raises(CommandLineError, match='xyzzy_no_such_place'):
        env.checkViasORM()

