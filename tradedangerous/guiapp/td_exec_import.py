from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
import io
from typing import Any, Callable

from rich.console import Console

from tradedangerous import commands, tradedb, tradeexcept
from tradedangerous.commands import exceptions as cmd_exceptions

EDDBLINK_OPTION_ORDER: tuple[str, ...] = (
    'all',
    'skipvend',
    'clean',
    'force',
    'solo',
    'purge',
    'optimize',
    '7days',
    'units',
    'item',
    'rare',
    'ship',
    'upgrade',
    'system',
    'station',
    'shipvend',
    'upvend',
    'listings',
)


@dataclass(slots=True)
class ImportExecutionPayload:
    ok: bool
    error_message: str | None = None
    raw_output: str = ''
    diagnostics_output: str = ''
    structured_result: Any = None


class ImportLogConsole:
    def __init__(self, stream: io.StringIO, monitor: Any) -> None:
        self.stream = stream
        self.monitor = monitor
        self.console = Console(
            file=stream,
            force_terminal=False,
            color_system=None,
            highlight=False,
        )

    def print(self, *args: Any, **kwargs: Any) -> None:
        self.console.print(*args, **kwargs)
        mirror = io.StringIO()
        Console(
            file=mirror,
            force_terminal=False,
            color_system=None,
            highlight=False,
        ).print(*args, **kwargs)
        text = mirror.getvalue().strip()
        if text and self.monitor is not None:
            for line in text.splitlines():
                self.monitor.append_log(line)


def build_import_argv(
    *,
    resolved: dict[str, Any],
    append_option: Callable[[list[str], str, Any], None],
) -> list[str]:
    argv = ['tradegui.py', 'import']
    append_option(argv, '-P', 'eddblink')

    for option in EDDBLINK_OPTION_ORDER:
        if resolved.get(option):
            append_option(argv, '-O', option)

    return argv


def execute_import_command(
    *,
    request: Any,
    argv: list[str],
) -> ImportExecutionPayload:
    diagnostics_stream = io.StringIO()
    monitor = getattr(request, 'import_monitor', None)

    try:
        cmdenv = commands.CommandIndex().parse(list(argv))
        if monitor is None:
            diagnostics_console = Console(
                file=diagnostics_stream,
                force_terminal=False,
                color_system=None,
                highlight=False,
            )
        else:
            diagnostics_console = ImportLogConsole(diagnostics_stream, monitor)
            monitor.set_status('Preparing import...')
            cmdenv.import_monitor = monitor
        cmdenv.console = diagnostics_console
        cmdenv.stderr = diagnostics_console

        with redirect_stdout(diagnostics_stream), redirect_stderr(
            diagnostics_stream
        ):
            preflight = getattr(cmdenv, 'preflight', None)
            if preflight and callable(preflight):
                preflight()

            if monitor is not None:
                monitor.set_status('Import running...')

            tdb = tradedb.TradeDB(cmdenv, load=cmdenv.wantsTradeDB)
            try:
                cmdenv.run(tdb)
            finally:
                tdb.close(final=True)
    except cmd_exceptions.CommandLineError as exc:
        return ImportExecutionPayload(
            ok=False,
            error_message=str(exc),
            diagnostics_output=str(exc),
        )
    except tradeexcept.TradeException as exc:
        return ImportExecutionPayload(
            ok=False,
            error_message=str(exc),
            diagnostics_output=str(exc),
        )
    except Exception as exc:
        return ImportExecutionPayload(
            ok=False,
            error_message=str(exc),
            diagnostics_output=repr(exc),
        )
    finally:
        if monitor is not None:
            monitor.finish()

    return ImportExecutionPayload(
        ok=True,
        diagnostics_output=diagnostics_stream.getvalue().strip(),
    )