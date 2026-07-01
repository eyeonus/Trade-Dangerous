from types import SimpleNamespace
import gc

import pytest

from tradedangerous.commands import olddata_cmd
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

_FAKE_CMD = SimpleNamespace(needs=Needs.NOTHING, usesTradeData=False)
_RESOLVER_CMD = SimpleNamespace(needs=Needs.RESOLVER, usesTradeData=False)

def _make_env(**properties):
    return CommandEnv(properties, ['trade.py', 'test'], _FAKE_CMD)

def _make_cmd_env(cmd_module, **properties):
    return CommandEnv(properties, ['trade.py', 'test'], cmd_module)

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

