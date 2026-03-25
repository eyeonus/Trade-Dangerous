"""Translate the olddata workspace draft into TD CLI arguments."""

from __future__ import annotations

from typing import Any, Callable


def build_olddata_argv(
    *,
    resolved: dict[str, Any],
    append_option: Callable[[list[str], str, Any], None],
    append_flag: Callable[[list[str], str, Any], None],
) -> list[str]:
    """Map the olddata workspace draft onto the `tradegui.py olddata` command line."""

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
    append_option(argv, '--odyssey', resolved.get('odyssey'))

    return argv


def validate_olddata_request(
    *,
    resolved: dict[str, Any],
    errors: list[str],
    validate_optional_int: Callable[..., None],
    validate_optional_float: Callable[..., None],
) -> None:
    """Apply command-local validation for the `olddata` workspace payload."""

    validate_optional_float(
        resolved,
        'ly',
        minimum=0.0,
        errors=errors,
    )
    validate_optional_float(
        resolved,
        'minAge',
        minimum=0.0,
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
        'lsMax',
        minimum=0,
        errors=errors,
    )

    near = str(resolved.get('near') or '').strip()
    if resolved.get('ly') is not None and not near:
        errors.append('Old Data distance requires Near.')
    if resolved.get('route') and not near:
        errors.append('Old Data route sorting requires Near.')
