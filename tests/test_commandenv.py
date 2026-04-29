from types import SimpleNamespace

import pytest

from tradedangerous.commands import olddata_cmd, run_cmd
from tradedangerous.commands.commandenv import CommandEnv, Needs
from tradedangerous.commands.exceptions import (
    CommandLineError,
    FleetCarrierError,
    OdysseyError,
    PadSizeError,
    PlanetaryError,
)

_FAKE_CMD = SimpleNamespace(wantsTradeDB=False, usesTradeData=False)

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

def test_commandenv_checkPlanetaryFleetOdyssey_normalize_or_reject():
    env = _make_env(planetary='yny', fleet='?ny', odyssey='n?y')
    env.checkPlanetary()
    env.checkFleet()
    env.checkOdyssey()
    assert env.planetary == 'NY'
    assert env.fleet is None
    assert env.odyssey is None
    
    with pytest.raises(PlanetaryError):
        _make_env(planetary='yz').checkPlanetary()
    with pytest.raises(FleetCarrierError):
        _make_env(fleet='za').checkFleet()
    with pytest.raises(OdysseyError):
        _make_env(odyssey='zn').checkOdyssey()


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
    from tradedangerous.commands import update_cmd
    env = _make_cmd_env(update_cmd)
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

