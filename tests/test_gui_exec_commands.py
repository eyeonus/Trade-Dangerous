from tradedangerous.guiapp.td_exec import TdExecutor
from tradedangerous.guiapp.td_exec_commands import (
    build_buy_argv,
    build_local_argv,
    build_market_argv,
    build_nav_argv,
    build_olddata_argv,
    build_rares_argv,
    build_run_argv,
    build_sell_argv,
    build_trade_argv,
    validate_local_request,
    validate_market_request,
    validate_nav_request,
    validate_olddata_request,
    validate_rares_request,
    validate_trade_request,
)


_APPEND_OPTION = TdExecutor._append_option
_APPEND_FLAG = TdExecutor._append_flag
_SPLIT = TdExecutor._split_search_terms
_VALIDATE_INT = TdExecutor._validate_optional_int
_VALIDATE_FLOAT = TdExecutor._validate_optional_float


def test_build_run_argv_maps_expected_fields():
    argv = build_run_argv(
        resolved={
            'credits': 9000,
            'jump_range_full_ly': 24.5,
            'jump_range_empty_ly': 28.0,
            'max_data_age_days': 3,
            'starting': 'Sol/Abraham Lincoln',
            'ending': 'LHS 380/Fisher Point',
            'via': 'A, B',
            'avoid': 'C',
            'loop': True,
            'hops': 4,
            'maxJumpsPer': 3,
            'startJumps': 1,
            'showJumps': True,
            'padSize': 'L',
            'fleet': 'Y',
            'odyssey': 'N',
            'routes': 2,
            'summary': True,
        },
        effective_capacity=36,
        append_option=_APPEND_OPTION,
        append_flag=_APPEND_FLAG,
    )

    assert argv[:2] == ['tradegui.py', 'run']
    assert '--capacity' in argv and '36' in argv
    assert '--credits' in argv and '9000' in argv
    assert '--ly-per' in argv and '24.5' in argv
    assert '--empty-ly' in argv and '28.0' in argv
    assert '--from' in argv and 'Sol/Abraham Lincoln' in argv
    assert '--to' in argv and 'LHS 380/Fisher Point' in argv
    assert '--loop' in argv
    assert '--show-jumps' in argv
    assert '--summary' in argv


def test_build_trade_argv_and_validate_trade_request():
    resolved = {
        'origin': 'Sol/Abraham Lincoln',
        'dest': 'Sol/Burnell Station',
        'minGainPerTon': 10,
        'cargoMode': 'fill',
    }
    errors = []

    argv = build_trade_argv(
        resolved=resolved,
        append_option=_APPEND_OPTION,
        append_flag=_APPEND_FLAG,
    )
    validate_trade_request(
        resolved=resolved,
        errors=errors,
        validate_optional_int=_VALIDATE_INT,
    )

    assert argv == [
        'tradegui.py', 'trade', 'Sol/Abraham Lincoln', 'Sol/Burnell Station',
        '--detail', '--gain-per-ton', '10', '--fill',
    ]
    assert errors == []


def test_build_local_argv_and_validate_local_request():
    resolved = {
        'near': 'Sol',
        'ly': 12.5,
        'max_data_age_days': 2,
        'padSize': 'M',
        'trading': True,
        'repair': True,
    }
    errors = []

    argv = build_local_argv(
        resolved=resolved,
        append_option=_APPEND_OPTION,
        append_flag=_APPEND_FLAG,
    )
    validate_local_request(
        resolved=resolved,
        errors=errors,
        validate_optional_float=_VALIDATE_FLOAT,
    )

    assert argv[:4] == ['tradegui.py', 'local', 'Sol', '--ly']
    assert '--trading' in argv
    assert '--repair' in argv
    assert argv[-2:] == ['--detail', '--detail']
    assert errors == []


def test_build_nav_argv_and_validate_nav_request():
    resolved = {
        'starting': 'Sol',
        'ending': 'Shinrarta Dezhra',
        'lyPer': 25.0,
        'refuelJumps': 4,
        'via': 'A, B\nC',
        'avoid': 'D\nE',
    }
    errors = []

    argv = build_nav_argv(
        resolved=resolved,
        append_option=_APPEND_OPTION,
        append_flag=_APPEND_FLAG,
        split_search_terms=_SPLIT,
    )
    validate_nav_request(
        resolved=resolved,
        errors=errors,
        validate_optional_int=_VALIDATE_INT,
        validate_optional_float=_VALIDATE_FLOAT,
    )

    assert argv[:3] == ['tradegui.py', 'nav', 'Sol']
    assert argv.count('--via') == 3
    assert argv.count('--avoid') == 2
    assert '--stations' in argv
    assert argv[-2:] == ['--detail', '--detail']
    assert errors == []


def test_build_olddata_argv_and_validate_olddata_request():
    resolved = {
        'near': 'Sol',
        'ly': 10.0,
        'route': True,
        'minAge': 5.0,
        'limit': 20,
        'lsMax': 1000,
    }
    errors = []

    argv = build_olddata_argv(
        resolved=resolved,
        append_option=_APPEND_OPTION,
        append_flag=_APPEND_FLAG,
    )
    validate_olddata_request(
        resolved=resolved,
        errors=errors,
        validate_optional_int=_VALIDATE_INT,
        validate_optional_float=_VALIDATE_FLOAT,
    )

    assert argv == [
        'tradegui.py', 'olddata',
        '--near', 'Sol',
        '--ly', '10.0',
        '--route',
        '--min-age', '5.0',
        '--limit', '20',
        '--ls-max', '1000',
    ]
    assert errors == []


def test_build_rares_argv_and_validate_rares_request():
    resolved = {
        'near': 'Leesti',
        'ly': 25.0,
        'limit': 5,
        'legalMode': 'legal',
        'away': 100.0,
        'awayFrom': 'Sol, Lave',
    }
    errors = []

    argv = build_rares_argv(
        resolved=resolved,
        append_option=_APPEND_OPTION,
        append_flag=_APPEND_FLAG,
        split_search_terms=_SPLIT,
    )
    validate_rares_request(
        resolved=resolved,
        errors=errors,
        validate_optional_int=_VALIDATE_INT,
        validate_optional_float=_VALIDATE_FLOAT,
        split_search_terms=_SPLIT,
    )

    assert argv[:3] == ['tradegui.py', 'rares', 'Leesti']
    assert '--legal' in argv
    assert '--away' in argv and '100.0' in argv
    assert argv.count('--from') == 2
    assert argv[-2:] == ['--detail', '--detail']
    assert errors == []


def test_build_buy_sell_market_argv_and_validators():
    buy_argv = build_buy_argv(
        resolved={
            'search': 'hydrogen fuel, water',
            'supply': 100,
            'oneStop': True,
            'sortByPrice': True,
            'near': 'Sol',
            'distance': 12.5,
        },
        append_option=_APPEND_OPTION,
        append_flag=_APPEND_FLAG,
        split_search_terms=_SPLIT,
    )
    sell_argv = build_sell_argv(
        resolved={
            'search': 'hydrogen fuel\nwater',
            'demand': 50,
            'sortByPrice': True,
            'near': 'Sol',
            'distance': 8.0,
        },
        append_option=_APPEND_OPTION,
        append_flag=_APPEND_FLAG,
        split_search_terms=_SPLIT,
    )
    market_errors = []
    market_argv = build_market_argv(
        resolved={'origin': 'Sol/Abraham Lincoln', 'mode': 'buying'},
        append_flag=_APPEND_FLAG,
    )
    validate_market_request(
        resolved={'origin': 'Sol/Abraham Lincoln', 'mode': 'buying'},
        errors=market_errors,
    )

    assert buy_argv[:4] == ['tradegui.py', 'buy', 'hydrogen fuel', 'water']
    assert '--one-stop' in buy_argv
    assert '--price-sort' in buy_argv
    assert sell_argv[:3] == ['tradegui.py', 'sell', 'hydrogen fuel']
    assert '--demand' in sell_argv and '50' in sell_argv
    assert market_argv == ['tradegui.py', 'market', 'Sol/Abraham Lincoln', '--buying', '--detail', '--detail']
    assert market_errors == []
