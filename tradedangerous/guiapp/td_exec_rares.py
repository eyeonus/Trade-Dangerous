"""Translate the rares workspace draft into TD CLI arguments."""

from __future__ import annotations

from typing import Any, Callable


def build_rares_argv(
    *,
    resolved: dict[str, Any],
    append_option: Callable[[list[str], str, Any], None],
    append_flag: Callable[[list[str], str, Any], None],
    split_search_terms: Callable[[Any], list[str]],
) -> list[str]:
    """Map the rares workspace draft onto the `tradegui.py rares` command line."""

    near = str(resolved.get('near') or '').strip()
    argv = ['tradegui.py', 'rares', near]

    append_option(argv, '--ly', resolved.get('ly'))
    append_option(argv, '--limit', resolved.get('limit'))
    append_option(argv, '--pad-size', resolved.get('padSize'))
    append_flag(argv, '--no-planet', resolved.get('noPlanet'))
    append_option(argv, '--planetary', resolved.get('planetary'))
    append_option(argv, '--fleet-carrier', resolved.get('fleet'))
    append_option(argv, '--odyssey', resolved.get('odyssey'))
    append_flag(argv, '--price-sort', resolved.get('sortByPrice'))
    append_flag(argv, '--reverse', resolved.get('reverse'))

    legal_mode = str(resolved.get('legalMode') or '').strip()
    append_flag(argv, '--legal', legal_mode == 'legal')
    append_flag(argv, '--illegal', legal_mode == 'illegal')

    away = resolved.get('away')
    away_from = split_search_terms(resolved.get('awayFrom'))
    append_option(argv, '--away', away)
    for system_name in away_from:
        argv.extend(['--from', system_name])

    argv.extend(['--detail', '--detail'])
    return argv


def validate_rares_request(
    *,
    resolved: dict[str, Any],
    errors: list[str],
    validate_optional_int: Callable[..., None],
    validate_optional_float: Callable[..., None],
    split_search_terms: Callable[[Any], list[str]],
) -> None:
    """Apply command-local validation for the `rares` workspace payload."""

    if not str(resolved.get('near') or '').strip():
        errors.append('Rares requires Near.')

    validate_optional_float(
        resolved,
        'ly',
        minimum=0.0,
        errors=errors,
    )
    validate_optional_int(
        resolved,
        'limit',
        minimum=0,
        errors=errors,
    )
    validate_optional_float(
        resolved,
        'away',
        minimum=0.0,
        errors=errors,
    )

    legal_mode = resolved.get('legalMode')
    if legal_mode not in (None, '', 'legal', 'illegal'):
        errors.append('Rares legality selection is invalid.')

    has_away = resolved.get('away') is not None
    has_away_from = bool(split_search_terms(resolved.get('awayFrom')))
    if has_away != has_away_from:
        errors.append(
            'Rares away filtering requires both Away distance and Away from.'
        )
