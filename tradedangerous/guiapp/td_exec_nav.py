"""Translate the nav workspace draft into TD CLI arguments."""

from __future__ import annotations

from typing import Any, Callable


def build_nav_argv(
    *,
    resolved: dict[str, Any],
    append_option: Callable[[list[str], str, Any], None],
    append_flag: Callable[[list[str], str, Any], None],
    split_search_terms: Callable[[Any], list[str]],
) -> list[str]:
    """Map the nav workspace draft onto the `tradegui.py nav` command line."""

    starting = str(resolved.get('starting') or '').strip()
    ending = str(resolved.get('ending') or '').strip()
    argv = ['tradegui.py', 'nav', starting, ending]

    append_option(argv, '--ly-per', resolved.get('lyPer'))
    append_option(argv, '--refuel-jumps', resolved.get('refuelJumps'))
    append_option(argv, '--pad-size', resolved.get('padSize'))
    append_flag(argv, '--no-planet', resolved.get('noPlanet'))
    append_option(argv, '--planetary', resolved.get('planetary'))
    append_option(argv, '--fleet-carrier', resolved.get('fleet'))
    append_option(argv, '--odyssey', resolved.get('odyssey'))

    for place in split_search_terms(resolved.get('via')):
        argv.extend(['--via', place])

    for place in split_search_terms(resolved.get('avoid')):
        argv.extend(['--avoid', place])

    argv.append('--stations')
    argv.extend(['--detail', '--detail'])
    return argv


def validate_nav_request(
    *,
    resolved: dict[str, Any],
    errors: list[str],
    validate_optional_int: Callable[..., None],
    validate_optional_float: Callable[..., None],
) -> None:
    """Apply command-local validation for the `nav` workspace payload."""

    if not str(resolved.get('starting') or '').strip():
        errors.append('Nav requires Start.')

    if not str(resolved.get('ending') or '').strip():
        errors.append('Nav requires End.')

    validate_optional_float(
        resolved,
        'lyPer',
        minimum=0.0,
        errors=errors,
    )
    validate_optional_int(
        resolved,
        'refuelJumps',
        minimum=0,
        errors=errors,
    )
