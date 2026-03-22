"""Translate the trade workspace draft into TD CLI arguments."""

from __future__ import annotations

from typing import Any, Callable


def build_trade_argv(
    *,
    resolved: dict[str, Any],
    append_option: Callable[[list[str], str, Any], None],
    append_flag: Callable[[list[str], str, Any], None],
) -> list[str]:
    """Map the trade workspace draft onto the `tradegui.py trade` command line."""

    origin = str(resolved.get('origin') or '').strip()
    dest = str(resolved.get('dest') or '').strip()

    argv = ['tradegui.py', 'trade', origin, dest]

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
    """Apply command-local validation for the `trade` workspace payload."""

    if not str(resolved.get('origin') or '').strip():
        errors.append('Trade requires Origin.')
    if not str(resolved.get('dest') or '').strip():
        errors.append('Trade requires Destination.')

    validate_optional_int(
        resolved,
        'minGainPerTon',
        minimum=0,
        errors=errors,
    )
    validate_optional_int(
        resolved,
        'limit',
        minimum=0,
        errors=errors,
    )
    validate_optional_int(
        resolved,
        'supply',
        minimum=0,
        errors=errors,
    )
    validate_optional_int(
        resolved,
        'demand',
        minimum=0,
        errors=errors,
    )

    cargo_mode = resolved.get('cargoMode')
    if cargo_mode not in (None, '', 'fill', 'load', 'full'):
        errors.append('Trade cargo mode is invalid.')
