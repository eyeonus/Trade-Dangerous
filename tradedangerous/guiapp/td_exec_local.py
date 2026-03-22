"""Translate the local workspace draft into TD CLI arguments."""

from __future__ import annotations

from typing import Any, Callable


def build_local_argv(
    *,
    resolved: dict[str, Any],
    append_option: Callable[[list[str], str, Any], None],
    append_flag: Callable[[list[str], str, Any], None],
) -> list[str]:
    """Map the local workspace draft onto the `tradegui.py local` command line."""

    near = str(resolved.get('near') or '').strip()
    argv = ['tradegui.py', 'local', near]

    append_option(argv, '--ly', resolved.get('ly'))
    append_option(argv, '--age', resolved.get('max_data_age_days'))
    append_option(argv, '--pad-size', resolved.get('padSize'))
    append_flag(argv, '--no-planet', resolved.get('noPlanet'))
    append_option(argv, '--planetary', resolved.get('planetary'))
    append_option(argv, '--fleet-carrier', resolved.get('fleet'))
    append_option(argv, '--odyssey', resolved.get('odyssey'))

    append_flag(argv, '--trading', resolved.get('trading'))
    append_flag(argv, '--black-market', resolved.get('blackMarket'))
    append_flag(argv, '--shipyard', resolved.get('shipyard'))
    append_flag(argv, '--outfitting', resolved.get('outfitting'))
    append_flag(argv, '--rearm', resolved.get('rearm'))
    append_flag(argv, '--refuel', resolved.get('refuel'))
    append_flag(argv, '--repair', resolved.get('repair'))

    argv.extend(['--detail', '--detail'])
    return argv


def validate_local_request(
    *,
    resolved: dict[str, Any],
    errors: list[str],
    validate_optional_float: Callable[..., None],
) -> None:
    """Apply command-local validation for the `local` workspace payload."""

    if not str(resolved.get('near') or '').strip():
        errors.append('Local requires Near.')

    validate_optional_float(
        resolved,
        'ly',
        minimum=0.0,
        errors=errors,
    )
