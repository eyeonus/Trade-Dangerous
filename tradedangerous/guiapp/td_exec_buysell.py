from __future__ import annotations

from typing import Any, Callable


def build_buy_argv(
    *,
    resolved: dict[str, Any],
    context: dict[str, Any],
    effective_capacity: int | None,
    append_option: Callable[[list[str], str, Any], None],
    append_flag: Callable[[list[str], str, Any], None],
) -> list[str]:
    argv = ['tradegui.py', 'buy']

    for term in _split_search_terms(resolved.get('search')):
        argv.append(term)

    append_option(argv, '--supply', resolved.get('supply'))
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


def build_sell_argv(
    *,
    resolved: dict[str, Any],
    context: dict[str, Any],
    effective_capacity: int | None,
    append_option: Callable[[list[str], str, Any], None],
    append_flag: Callable[[list[str], str, Any], None],
) -> list[str]:
    argv = ['tradegui.py', 'sell']

    search_terms = _split_search_terms(resolved.get('search'))
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
    append_option(argv, '--odyssey', resolved.get('odyssey'))
    append_flag(argv, '--black-market', resolved.get('blackMarket'))
    append_option(argv, '--gt', resolved.get('gt'))
    append_option(argv, '--lt', resolved.get('lt'))
    if include_ls_max:
        append_option(argv, '--ls-max', resolved.get('maxLs'))


def _split_search_terms(value: Any) -> list[str]:
    if value in (None, ''):
        return []

    terms: list[str] = []
    for line in str(value).splitlines():
        for part in line.split(','):
            cleaned = part.strip()
            if cleaned:
                terms.append(cleaned)
    return terms
