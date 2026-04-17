"""Import-specific TD execution helpers and progress-aware console mirroring."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
import io
from typing import Any, Callable

from rich.console import Console

from tradedangerous import commands, tradedb, tradeexcept
from tradedangerous.commands import exceptions as cmd_exceptions

EDDBLINK_OPTION_ORDER: tuple[str, ...] = (
    # Keep the option order stable so diagnostics and reproduced commands are
    # easy to compare with the old CLI usage.
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
EDDBLINK_GUI_SHIPVEND_KEY = 'shipvend_mode'
EDDBLINK_GUI_SHIPVEND_BASE_OPTIONS: tuple[str, ...] = (
    'rare',
    'upgrade',
    'shipvend',
    'listings',
)
EDDBLINK_GUI_SHIPVEND_PASS_THROUGH: tuple[str, ...] = (
    'force',
    'purge',
    'optimize',
    '7days',
    'units',
)

@dataclass(slots=True)
class ImportExecutionPayload:
    ok: bool
    error_message: str | None = None
    raw_output: str = ''
    diagnostics_output: str = ''
    structured_result: Any = None

class ImportLogConsole:
    """Mirror Rich output into the import monitor one rendered line at a time."""
    
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
        # Render through a plain in-memory console so the monitor receives the
        # final text exactly as the user would see it, minus color codes.
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
    """Map the import workspace draft onto the eddblink import command line."""
    
    argv = ['tradegui.py', 'import']
    append_option(argv, '-P', 'eddblink')
    
    if resolved.get(EDDBLINK_GUI_SHIPVEND_KEY):
        # GUI-only mode: keep the normal fast-path defaults out of the emitted
        # argv and request the explicit non-clean ship-vendor formula instead.
        # Clean and Solo are intentionally not emitted in this mode.
        for option in EDDBLINK_GUI_SHIPVEND_PASS_THROUGH:
            if resolved.get(option):
                append_option(argv, '-O', option)
        
        for option in EDDBLINK_GUI_SHIPVEND_BASE_OPTIONS:
            append_option(argv, '-O', option)
        
        return argv
    
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
            # ImportCommand uses this hook to publish progress callbacks from
            # deep inside the TD import pipeline.
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
