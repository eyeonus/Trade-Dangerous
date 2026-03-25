"""Translate the buy/sell workspace drafts into TD CLI arguments."""

from __future__ import annotations

from typing import Any, Callable


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
    append_option: Callable[[list[str], str, Any], None],
    append_flag: Callable[[list[str], str, Any], None],
    split_search_terms: Callable[[Any], list[str]],
) -> list[str]:
    """Map the sell workspace draft onto the `tradegui.py sell` command line."""

    argv = ['tradegui.py', 'sell']

    search_terms = split_search_terms(resolved.get('search'))
    if search_terms:
        # The underlying sell command accepts a single item search term.
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
    """Append the shared location/filter options used by buy and sell."""

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

