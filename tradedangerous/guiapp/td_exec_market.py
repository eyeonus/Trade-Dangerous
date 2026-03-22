"""Translate the market workspace draft into TD CLI arguments."""

from __future__ import annotations

from typing import Any, Callable


def build_market_argv(
    *,
    resolved: dict[str, Any],
    append_flag: Callable[[list[str], str, Any], None],
) -> list[str]:
    """Map the market workspace draft onto the `tradegui.py market` command line."""

    origin = str(resolved.get('origin') or '').strip()
    argv = ['tradegui.py', 'market', origin]

    mode = str(resolved.get('mode') or '').strip()
    append_flag(argv, '--buying', mode == 'buying')
    append_flag(argv, '--selling', mode == 'selling')
    argv.extend(['--detail', '--detail'])

    return argv


def validate_market_request(
    *,
    resolved: dict[str, Any],
    errors: list[str],
) -> None:
    """Apply command-local validation for the `market` workspace payload."""

    if not str(resolved.get('origin') or '').strip():
        errors.append('Market requires Station.')

    mode = resolved.get('mode')
    if mode not in (None, '', 'buying', 'selling'):
        errors.append('Market side selection is invalid.')

    detail = resolved.get('detail')
    if detail not in (None, '', '1', '2'):
        errors.append('Market detail selection is invalid.')
