from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tradedangerous.guiapp.td_exec import (
    GuiCommandRequest,
    TdExecutor,
    _snapshot_structured_result,
)


def test_td_exec_request_context_precedence():
    request = GuiCommandRequest(
        command='run',
        global_values={'credits': 1000, 'capacity': 10},
        ship_profile_values={'capacity': 20, 'jump_range_full_ly': 15},
        context_overrides={'capacity': 30, 'starting': 'Sol'},
        main_values={'starting': 'Achenar', 'hops': 4},
        advanced_values={'hops': 6, 'routes': 2},
    )

    assert request.effective_context() == {
        'credits': 1000,
        'capacity': 30,
        'jump_range_full_ly': 15,
        'starting': 'Sol',
    }
    assert request.resolved_values() == {
        'credits': 1000,
        'capacity': 30,
        'jump_range_full_ly': 15,
        'starting': 'Achenar',
        'hops': 6,
        'routes': 2,
    }


def test_td_executor_validate_request_core_rules_per_command():
    executor = TdExecutor()

    run_errors = executor.validate_request(GuiCommandRequest(command='run'))
    trade_errors = executor.validate_request(GuiCommandRequest(command='trade'))
    local_errors = executor.validate_request(GuiCommandRequest(command='local'))
    market_errors = executor.validate_request(GuiCommandRequest(command='market'))
    nav_errors = executor.validate_request(GuiCommandRequest(command='nav'))
    olddata_errors = executor.validate_request(
        GuiCommandRequest(command='olddata', main_values={'route': True})
    )

    assert 'Run requires Capacity.' in run_errors
    assert 'Run requires Credits.' in run_errors
    assert 'Run requires Jump Range (Full).' in run_errors
    # The GUI's Trade workspace drives the `direct` command (trade is its CLI
    # alias), so its validation speaks in Direct terms.
    assert trade_errors == [
        'Direct requires an origin system or station.',
        'Direct requires a destination system or station.',
    ]
    assert local_errors == ['Local requires Near.']
    assert market_errors == ['Market requires Station.']
    assert nav_errors == ['Nav requires Start.', 'Nav requires End.']
    assert olddata_errors == ['Old Data route sorting requires Near.']


def test_td_exec_snapshot_helpers_flatten_run_result_to_plain_data():
    # The post-L RunResult is a routes -> hops -> cargo-lines graph. The snapshot
    # flattens it to plain dicts (carrying no live DB handles) so the worker
    # payload stays simple and the GUI renderer reads one stable shape.
    sol = SimpleNamespace(dbname='Sol', x=0.0, y=0.0, z=0.0)
    lhs = SimpleNamespace(dbname='LHS 380', x=3.0, y=4.0, z=0.0)
    origin = SimpleNamespace(dbname='Sol/Abraham Lincoln')
    destination = SimpleNamespace(dbname='LHS 380/Fisher Point')

    line = SimpleNamespace(
        quantity=10,
        item_name='Hydrogen Fuel',
        buy_price=50,
        sell_price=75,
        bulk_sale_tax_sensitive=False,
        effective_destination_demand_units=None,
    )
    leg = SimpleNamespace(
        is_same_system=False, systems=[sol, lhs], jumps=1, distance_ly=5.0,
    )
    hop = SimpleNamespace(
        source_station=origin,
        destination_station=destination,
        raw_profit=250,
        cargo=SimpleNamespace(lines=[line]),
        jump_path=leg,
    )
    route = SimpleNamespace(
        hops=[hop],
        stations=[origin, destination],
        starting_credits=1000,
        total_raw_profit=250,
        ending_credits=1250,
        arrival_hops=None,
    )
    result = SimpleNamespace(routes=[route], warnings=())

    snapshot = _snapshot_structured_result('run', result)

    assert snapshot['summary'] is False
    assert snapshot['warnings'] == []
    assert len(snapshot['routes']) == 1

    r = snapshot['routes'][0]
    assert r['origin'] == 'Sol/Abraham Lincoln'
    assert r['destination'] == 'LHS 380/Fisher Point'
    assert r['hop_count'] == 1
    assert r['total_jumps'] == 1
    assert r['total_profit'] == 250
    assert r['starting_credits'] == 1000
    assert r['ending_credits'] == 1250

    stops = r['stops']
    assert [s['station'] for s in stops] == [
        'Sol/Abraham Lincoln', 'LHS 380/Fisher Point',
    ]
    # The departing hop's cargo is the 'buy' side of the source stop, and its
    # jump path is the nav for that leg.
    assert stops[0]['buy'] == [
        {'qty': 10, 'item': 'Hydrogen Fuel', 'price': 50, 'capped': False},
    ]
    assert stops[0]['nav'] == ['LHS 380 · 5.0 ly']
    # The arrival stop sells what it carried; profit and balance land there.
    assert stops[1]['sell'] == [
        {'qty': 10, 'item': 'Hydrogen Fuel', 'price': 75, 'capped': False},
    ]
    assert stops[1]['profit'] == 250
    assert stops[1]['balance'] == 1250


def _make_fake_cmdenv(*, needs_resolver):
    """Minimal fake CommandEnv for the GUI backend-selection path."""
    env = MagicMock()
    env.needs_resolver = needs_resolver
    env.usesTradeData = False
    env.run.return_value = None
    env.preflight = None
    return env


def test_execute_td_command_constructs_orm_for_resolver_commands():
    """A resolver-tier command builds a TradeORM (via build_backend) and closes it."""
    fake_cmdenv = _make_fake_cmdenv(needs_resolver=True)
    request = GuiCommandRequest(command='trade')
    mock_torm = MagicMock()

    with (
        patch(
            'tradedangerous.guiapp.td_exec.commands.CommandIndex.parse',
            return_value=fake_cmdenv,
        ),
        patch(
            'tradedangerous.guiapp.td_backend.TradeORM',
            return_value=mock_torm,
        ) as torm_cls,
    ):
        TdExecutor()._execute_td_command(
            request, ['trade.py', 'trade', 'Sol', 'Sol']
        )

    torm_cls.assert_called_once()
    mock_torm.close.assert_called_once_with(final=True)


def test_execute_td_command_constructs_no_backend_for_nothing_commands():
    """A no-backend command builds neither backend; run() receives None."""
    fake_cmdenv = _make_fake_cmdenv(needs_resolver=False)
    request = GuiCommandRequest(command='update')

    with (
        patch(
            'tradedangerous.guiapp.td_exec.commands.CommandIndex.parse',
            return_value=fake_cmdenv,
        ),
        patch('tradedangerous.guiapp.td_backend.TradeORM') as torm_cls,
    ):
        TdExecutor()._execute_td_command(request, ['trade.py', 'update'])

    torm_cls.assert_not_called()
    fake_cmdenv.run.assert_called_once_with(None)
