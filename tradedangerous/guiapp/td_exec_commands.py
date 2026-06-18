"""Command-specific argv builders and validators for the GUI executor."""

from __future__ import annotations

from typing import Any, Callable

# This module is the final field-name-to-argv translation layer after the GUI
# has merged inherited context, main inputs, and advanced dialog values.

def build_run_argv(
    *,
    resolved: dict[str, Any],
    effective_capacity: int | None,
    append_option: Callable[[list[str], str, Any], None],
    append_flag: Callable[[list[str], str, Any], None],
) -> list[str]:
    """Map GUI field names onto the `tradegui.py run` command line."""
    
    argv = ['tradegui.py', 'run']
    
    append_option(argv, '--capacity', effective_capacity)
    append_option(argv, '--credits', resolved.get('credits'))
    append_option(argv, '--ly-per', resolved.get('jump_range_full_ly'))
    append_option(argv, '--empty-ly', resolved.get('jump_range_empty_ly'))
    append_option(argv, '--age', resolved.get('max_data_age_days'))
    
    append_option(argv, '--from', resolved.get('starting'))
    append_option(argv, '--to', resolved.get('ending'))
    append_option(argv, '--towards', resolved.get('goalSystem'))
    
    via_value = resolved.get('via')
    if via_value not in (None, ''):
        for line in str(via_value).splitlines():
            for part in line.split(','):
                cleaned = part.strip()
                if cleaned:
                    argv.extend(['--via', cleaned])
    
    avoid_value = resolved.get('avoid')
    if avoid_value not in (None, ''):
        for line in str(avoid_value).splitlines():
            for part in line.split(','):
                cleaned = part.strip()
                if cleaned:
                    argv.extend(['--avoid', cleaned])
    
    append_flag(argv, '--loop', resolved.get('loop'))
    append_flag(argv, '--direct', resolved.get('direct'))
    append_option(argv, '--hops', resolved.get('hops'))
    append_option(argv, '--jumps-per', resolved.get('maxJumpsPer'))
    append_option(argv, '--start-jumps', resolved.get('startJumps'))
    append_option(argv, '--end-jumps', resolved.get('endJumps'))
    append_flag(argv, '--show-jumps', resolved.get('showJumps'))
    
    append_option(argv, '--limit', resolved.get('limit'))
    append_option(argv, '--pad-size', resolved.get('padSize'))
    append_flag(argv, '--no-planet', resolved.get('noPlanet'))
    append_option(argv, '--planetary', resolved.get('planetary'))
    append_option(argv, '--fleet-carrier', resolved.get('fleet'))
    append_option(argv, '--settlement', resolved.get('settlement'))
    append_flag(argv, '--black-market', resolved.get('blackMarket'))
    
    append_option(argv, '--ls-penalty', resolved.get('lsPenalty'))
    append_option(argv, '--ls-max', resolved.get('maxLs'))
    append_option(argv, '--gain-per-ton', resolved.get('minGainPerTon'))
    append_option(argv, '--max-gain-per-ton', resolved.get('maxGainPerTon'))
    
    append_flag(argv, '--unique', resolved.get('unique'))
    append_option(argv, '--loop-interval', resolved.get('loopInt'))
    append_option(argv, '--margin', resolved.get('margin'))
    append_option(argv, '--insurance', resolved.get('insurance'))
    
    append_option(argv, '--routes', resolved.get('routes'))
    append_option(argv, '--max-routes', resolved.get('maxRoutes'))
    append_flag(argv, '--checklist', resolved.get('checklist'))
    append_flag(argv, '--x52-pro', resolved.get('x52pro'))
    append_option(argv, '--prune-score', resolved.get('pruneScores'))
    append_option(argv, '--prune-hops', resolved.get('pruneHops'))
    
    append_flag(argv, '--progress', resolved.get('progress'))
    append_option(argv, '--supply', resolved.get('supply'))
    append_option(argv, '--demand', resolved.get('demand'))
    append_flag(argv, '--summary', resolved.get('summary'))
    return argv

def build_buy_argv(
    *,
    resolved: dict[str, Any],
    append_option: Callable[[list[str], str, Any], None],
    append_flag: Callable[[list[str], str, Any], None],
    split_search_terms: Callable[[Any], list[str]],
) -> list[str]:
    """Map the buy workspace draft onto the `tradegui.py buy` command line."""
    
    argv = ['tradegui.py', 'buy']
    
    for term in split_search_terms(resolved.get('search')):
        argv.append(term)
    
    append_option(argv, '--supply', resolved.get('supply'))
    append_flag(argv, '--rare', resolved.get('rare'))
    append_flag(argv, '--one-stop', resolved.get('oneStop'))
    append_flag(argv, '--price-sort', resolved.get('sortByPrice'))
    append_flag(argv, '--units-sort', resolved.get('sortByUnits'))
    _append_buysell_search_options(
        argv,
        resolved=resolved,
        ly_option='--ly',
        include_ls_max=True,
        append_option=append_option,
        append_flag=append_flag,
    )
    return argv

def validate_buy_request(
    *,
    resolved: dict[str, Any],
    errors: list[str],
    validate_optional_int: Callable[..., None],
    validate_optional_float: Callable[..., None],
    split_search_terms: Callable[[Any], list[str]],
) -> None:
    search_terms = split_search_terms(resolved.get('search'))
    if not search_terms and not resolved.get('rare'):
        errors.append('Buy requires Search.')
    if resolved.get('oneStop') and resolved.get('rare') and not search_terms:
        errors.append('Buy --one-stop with Rares requires at least one search term.')

    validate_optional_int(resolved, 'supply', minimum=0, errors=errors)
    validate_optional_int(resolved, 'limit', minimum=0, errors=errors)
    validate_optional_int(resolved, 'gt', minimum=0, errors=errors)
    validate_optional_int(resolved, 'lt', minimum=0, errors=errors)
    validate_optional_int(resolved, 'maxLs', minimum=0, errors=errors)
    validate_optional_float(resolved, 'distance', minimum=0.0, errors=errors)
    validate_optional_float(
        resolved,
        'max_data_age_days',
        minimum=0.0,
        errors=errors,
    )
    
    near = str(resolved.get('near') or '').strip()
    if resolved.get('distance') is not None and not near:
        errors.append('Buy distance requires Near.')
    
    gt = resolved.get('gt')
    lt = resolved.get('lt')
    if isinstance(gt, int) and isinstance(lt, int) and lt <= gt:
        errors.append('Buy --gt must be lower than --lt.')

def build_sell_argv(
    *,
    resolved: dict[str, Any],
    append_option: Callable[[list[str], str, Any], None],
    append_flag: Callable[[list[str], str, Any], None],
    split_search_terms: Callable[[Any], list[str]],
) -> list[str]:
    """Map the sell workspace draft onto the `tradegui.py sell` command line."""
    
    argv = ['tradegui.py', 'sell']
    
    search_terms = split_search_terms(resolved.get('search'))
    if search_terms:
        argv.append(search_terms[0])
    
    append_option(argv, '--demand', resolved.get('demand'))
    append_flag(argv, '--price-sort', resolved.get('sortByPrice'))
    _append_buysell_search_options(
        argv,
        resolved=resolved,
        ly_option='--ly-per',
        include_ls_max=False,
        append_option=append_option,
        append_flag=append_flag,
    )
    return argv

def validate_sell_request(
    *,
    resolved: dict[str, Any],
    errors: list[str],
    validate_optional_int: Callable[..., None],
    validate_optional_float: Callable[..., None],
    split_search_terms: Callable[[Any], list[str]],
) -> None:
    search_terms = split_search_terms(resolved.get('search'))
    if not search_terms:
        errors.append('Sell requires Search.')
    elif len(search_terms) > 1:
        errors.append('Sell only accepts one search term.')
    
    validate_optional_int(resolved, 'demand', minimum=0, errors=errors)
    validate_optional_int(resolved, 'limit', minimum=0, errors=errors)
    validate_optional_int(resolved, 'gt', minimum=0, errors=errors)
    validate_optional_int(resolved, 'lt', minimum=0, errors=errors)
    validate_optional_float(resolved, 'distance', minimum=0.0, errors=errors)
    validate_optional_float(
        resolved,
        'max_data_age_days',
        minimum=0.0,
        errors=errors,
    )
    
    near = str(resolved.get('near') or '').strip()
    if resolved.get('distance') is not None and not near:
        errors.append('Sell distance requires Near.')
    
    gt = resolved.get('gt')
    lt = resolved.get('lt')
    if isinstance(gt, int) and isinstance(lt, int) and lt <= gt:
        errors.append('Sell --gt must be lower than --lt.')

def _append_buysell_search_options(
    argv: list[str],
    *,
    resolved: dict[str, Any],
    ly_option: str,
    include_ls_max: bool,
    append_option: Callable[[list[str], str, Any], None],
    append_flag: Callable[[list[str], str, Any], None],
) -> None:
    append_option(argv, '--near', resolved.get('near'))
    append_option(argv, ly_option, resolved.get('distance'))
    append_option(argv, '--limit', resolved.get('limit'))
    append_option(argv, '--age', resolved.get('max_data_age_days'))
    append_option(argv, '--pad-size', resolved.get('padSize'))
    append_flag(argv, '--no-planet', resolved.get('noPlanet'))
    append_option(argv, '--planetary', resolved.get('planetary'))
    append_option(argv, '--fleet-carrier', resolved.get('fleet'))
    append_option(argv, '--settlement', resolved.get('settlement'))
    append_flag(argv, '--black-market', resolved.get('blackMarket'))
    append_option(argv, '--gt', resolved.get('gt'))
    append_option(argv, '--lt', resolved.get('lt'))
    if include_ls_max:
        append_option(argv, '--ls-max', resolved.get('maxLs'))

def build_trade_argv(
    *,
    resolved: dict[str, Any],
    append_option: Callable[[list[str], str, Any], None],
    append_flag: Callable[[list[str], str, Any], None],
) -> list[str]:
    origin = str(resolved.get('origin') or '').strip()
    dest = str(resolved.get('dest') or '').strip()
    
    argv = ['tradegui.py', 'trade', origin, dest]
    
    # The trade renderer expects the detailed row payload rather than the
    # compact CLI summary, so the GUI forces detail mode here.
    append_flag(argv, '--detail', True)
    append_option(argv, '--gain-per-ton', resolved.get('minGainPerTon'))
    append_option(argv, '--limit', resolved.get('limit'))
    append_option(argv, '--supply', resolved.get('supply'))
    append_option(argv, '--demand', resolved.get('demand'))
    append_flag(argv, '--reverse', resolved.get('reverse'))
    
    cargo_mode = str(resolved.get('cargoMode') or '').strip()
    if cargo_mode == 'fill':
        append_flag(argv, '--fill', True)
    elif cargo_mode == 'load':
        append_flag(argv, '--load', True)
    elif cargo_mode == 'full':
        append_flag(argv, '--full-load', True)
    
    return argv

def validate_trade_request(
    *,
    resolved: dict[str, Any],
    errors: list[str],
    validate_optional_int: Callable[..., None],
) -> None:
    if not str(resolved.get('origin') or '').strip():
        errors.append('Trade requires Origin.')
    if not str(resolved.get('dest') or '').strip():
        errors.append('Trade requires Destination.')
    
    validate_optional_int(resolved, 'minGainPerTon', minimum=0, errors=errors)
    validate_optional_int(resolved, 'limit', minimum=0, errors=errors)
    validate_optional_int(resolved, 'supply', minimum=0, errors=errors)
    validate_optional_int(resolved, 'demand', minimum=0, errors=errors)
    
    cargo_mode = resolved.get('cargoMode')
    if cargo_mode not in (None, '', 'fill', 'load', 'full'):
        errors.append('Trade cargo mode is invalid.')

def build_market_argv(
    *,
    resolved: dict[str, Any],
    append_flag: Callable[[list[str], str, Any], None],
) -> list[str]:
    origin = str(resolved.get('origin') or '').strip()
    argv = ['tradegui.py', 'market', origin]
    
    mode = str(resolved.get('mode') or '').strip()
    append_flag(argv, '--buying', mode == 'buying')
    append_flag(argv, '--selling', mode == 'selling')
    # Market tables rely on the full detail payload, including averages and age.
    argv.extend(['--detail', '--detail'])
    
    return argv

def validate_market_request(
    *,
    resolved: dict[str, Any],
    errors: list[str],
) -> None:
    if not str(resolved.get('origin') or '').strip():
        errors.append('Market requires Station.')
    
    mode = resolved.get('mode')
    if mode not in (None, '', 'buying', 'selling'):
        errors.append('Market side selection is invalid.')

def build_local_argv(
    *,
    resolved: dict[str, Any],
    append_option: Callable[[list[str], str, Any], None],
    append_flag: Callable[[list[str], str, Any], None],
) -> list[str]:
    near = str(resolved.get('near') or '').strip()
    argv = ['tradegui.py', 'local', near]
    
    append_option(argv, '--ly', resolved.get('ly'))
    append_option(argv, '--age', resolved.get('max_data_age_days'))
    append_option(argv, '--pad-size', resolved.get('padSize'))
    append_flag(argv, '--no-planet', resolved.get('noPlanet'))
    append_option(argv, '--planetary', resolved.get('planetary'))
    append_option(argv, '--fleet-carrier', resolved.get('fleet'))
    append_option(argv, '--settlement', resolved.get('settlement'))
    
    append_flag(argv, '--trading', resolved.get('trading'))
    append_flag(argv, '--black-market', resolved.get('blackMarket'))
    append_flag(argv, '--shipyard', resolved.get('shipyard'))
    append_flag(argv, '--outfitting', resolved.get('outfitting'))
    append_flag(argv, '--rearm', resolved.get('rearm'))
    append_flag(argv, '--refuel', resolved.get('refuel'))
    append_flag(argv, '--repair', resolved.get('repair'))
    
    # Local expansions show per-system station details, so request the richer
    # payload shape even though the plain CLI can work with less detail.
    argv.extend(['--detail', '--detail'])
    return argv

def validate_local_request(
    *,
    resolved: dict[str, Any],
    errors: list[str],
    validate_optional_float: Callable[..., None],
) -> None:
    if not str(resolved.get('near') or '').strip():
        errors.append('Local requires Near.')
    
    validate_optional_float(resolved, 'ly', minimum=0.0, errors=errors)

def build_nav_argv(
    *,
    resolved: dict[str, Any],
    append_option: Callable[[list[str], str, Any], None],
    append_flag: Callable[[list[str], str, Any], None],
    split_search_terms: Callable[[Any], list[str]],
) -> list[str]:
    starting = str(resolved.get('starting') or '').strip()
    ending = str(resolved.get('ending') or '').strip()
    argv = ['tradegui.py', 'nav', starting, ending]
    
    append_option(argv, '--ly-per', resolved.get('lyPer'))
    append_option(argv, '--refuel-jumps', resolved.get('refuelJumps'))
    append_option(argv, '--pad-size', resolved.get('padSize'))
    append_flag(argv, '--no-planet', resolved.get('noPlanet'))
    append_option(argv, '--planetary', resolved.get('planetary'))
    append_option(argv, '--fleet-carrier', resolved.get('fleet'))
    append_option(argv, '--settlement', resolved.get('settlement'))
    
    # TD accepts repeated `--via`/`--avoid` flags, so split the GUI text areas
    # into discrete argv entries instead of forwarding a raw comma block.
    for place in split_search_terms(resolved.get('via')):
        argv.extend(['--via', place])
    
    for place in split_search_terms(resolved.get('avoid')):
        argv.extend(['--avoid', place])
    
    argv.append('--stations')
    # Nav results render as hops with expandable station matches, which only
    # exist when the command asks TD for station detail explicitly.
    argv.extend(['--detail', '--detail'])
    return argv

def validate_nav_request(
    *,
    resolved: dict[str, Any],
    errors: list[str],
    validate_optional_int: Callable[..., None],
    validate_optional_float: Callable[..., None],
) -> None:
    if not str(resolved.get('starting') or '').strip():
        errors.append('Nav requires Start.')
    
    if not str(resolved.get('ending') or '').strip():
        errors.append('Nav requires End.')
    
    validate_optional_float(resolved, 'lyPer', minimum=0.0, errors=errors)
    validate_optional_int(resolved, 'refuelJumps', minimum=0, errors=errors)

def build_olddata_argv(
    *,
    resolved: dict[str, Any],
    append_option: Callable[[list[str], str, Any], None],
    append_flag: Callable[[list[str], str, Any], None],
) -> list[str]:
    argv = ['tradegui.py', 'olddata']
    
    append_option(argv, '--near', resolved.get('near'))
    append_option(argv, '--ly', resolved.get('ly'))
    append_flag(argv, '--route', resolved.get('route'))
    append_option(argv, '--min-age', resolved.get('minAge'))
    append_option(argv, '--limit', resolved.get('limit'))
    append_option(argv, '--ls-max', resolved.get('lsMax'))
    append_option(argv, '--pad-size', resolved.get('padSize'))
    append_option(argv, '--planetary', resolved.get('planetary'))
    append_option(argv, '--fleet-carrier', resolved.get('fleet'))
    append_option(argv, '--settlement', resolved.get('settlement'))
    
    return argv

def validate_olddata_request(
    *,
    resolved: dict[str, Any],
    errors: list[str],
    validate_optional_int: Callable[..., None],
    validate_optional_float: Callable[..., None],
) -> None:
    validate_optional_float(resolved, 'ly', minimum=0.0, errors=errors)
    validate_optional_float(resolved, 'minAge', minimum=0.0, errors=errors)
    validate_optional_int(resolved, 'limit', minimum=0, errors=errors)
    validate_optional_int(resolved, 'lsMax', minimum=0, errors=errors)
    
    near = str(resolved.get('near') or '').strip()
    if resolved.get('ly') is not None and not near:
        errors.append('Old Data distance requires Near.')
    if resolved.get('route') and not near:
        errors.append('Old Data route sorting requires Near.')

