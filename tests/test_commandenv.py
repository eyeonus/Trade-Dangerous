from types import SimpleNamespace

import pytest

from tradedangerous.commands import olddata_cmd, run_cmd
from tradedangerous.commands.commandenv import CommandEnv
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


def test_commandenv_colorize_known_and_unknown_colors():
    env = _make_env()

    colored = env.colorize('red', 'alert')
    raw = env.colorize('unknown-color', 'alert')

    assert colored.startswith('[')
    assert colored.endswith('alert[0m')
    assert raw == 'alert'
