"""Neutral GUI backend factory.

Both the ordinary-command executor (`td_exec`) and the import executor
(`td_exec_import`) need to build the engine backend the same way the CLI does.
Keeping that single rule here — rather than in either executor module — stops
the two flows drifting apart, and avoids a circular import (`td_exec` already
imports `td_exec_import`).

The rule mirrors `cli.py`: a command declaring ``Needs.RESOLVER`` gets a
``TradeORM`` handle; a command needing no backend (``Needs.NOTHING``) gets
``None``. ``allowMissingDB`` is honoured so build/bootstrap and import commands
can construct the handle without an existing database file.
"""

from __future__ import annotations

from typing import Any

from tradedangerous.tradeorm import TradeORM


def build_backend(cmdenv: Any) -> TradeORM | None:
    """Construct the backend for a parsed command, matching the CLI contract.

    Returns a ``TradeORM`` for resolver-tier commands and ``None`` for
    no-backend commands. The caller owns closing whatever it gets back.
    """
    if not getattr(cmdenv, 'needs_resolver', False):
        return None
    allow_missing = getattr(cmdenv._cmd, 'allowMissingDB', False)  # noqa: SLF001  (command module lives on cmdenv._cmd; same access as cli.py)
    return TradeORM(tdenv=cmdenv, require_db=not allow_missing)
