"""Execution adapter that translates GUI draft state into TD core calls."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
import io
import math
import multiprocessing
import os
import re
import sys
from multiprocessing.connection import Connection
from typing import Any

from rich.console import Console

from tradedangerous import commands, tradeexcept
from tradedangerous.commands import exceptions as cmd_exceptions

from .td_backend import build_backend
from .td_exec_commands import (
    build_buy_argv,
    build_local_argv,
    build_market_argv,
    build_nav_argv,
    build_olddata_argv,
    build_run_argv,
    build_sell_argv,
    build_trade_argv,
    validate_local_request,
    validate_market_request,
    validate_nav_request,
    validate_olddata_request,
    validate_trade_request,
)
from .td_exec_import import build_import_argv, execute_import_command

# TdExecutor owns three jobs: validate GUI input, translate it into argv via
# `td_exec_commands`, and capture both diagnostics and rendered output for the
# right pane.
@dataclass(slots=True)
class GuiCommandRequest:
    """Self-contained execution payload assembled from GUI state."""
    
    command: str
    main_values: dict[str, Any] = field(default_factory=dict)
    advanced_values: dict[str, Any] = field(default_factory=dict)
    context_overrides: dict[str, Any] = field(default_factory=dict)
    global_values: dict[str, Any] = field(default_factory=dict)
    ship_profile_values: dict[str, Any] = field(default_factory=dict)
    # Optional GUI override for the Elite journal directory. Blank/None keeps
    # the CLI's normal discovery (ELITE_JOURNAL_PATH env var, then OS default).
    journal_dir: str | None = None
    # Set when the GUI has already confirmed an unanchored (whole-galaxy) run.
    # The worker then answers run's interactive 'Continue?' prompt so the search
    # proceeds; without it an unanchored run aborts with guidance.
    confirm_unanchored: bool = False
    import_monitor: Any = None
    
    def effective_context(self) -> dict[str, Any]:
        context: dict[str, Any] = {}
        # Later layers intentionally win: profile values override globals, and
        # explicit per-command overrides take precedence over both.
        context.update(_drop_blank_values(self.global_values))
        context.update(_drop_blank_values(self.ship_profile_values))
        context.update(_drop_blank_values(self.context_overrides))
        return context
    
    def resolved_values(self) -> dict[str, Any]:
        resolved = self.effective_context()
        # Main and advanced command fields are appended on top of inherited
        # context so argv builders can read from a single merged mapping.
        resolved.update(_drop_blank_values(self.main_values))
        resolved.update(_drop_blank_values(self.advanced_values))
        return resolved

@dataclass(slots=True)
class GuiCommandResult:
    """Execution outcome mirrored directly into the session/right-pane UI."""
    
    command: str
    ok: bool
    error_message: str | None = None
    raw_output: str = ''
    diagnostics_output: str = ''
    structured_result: Any = None
    argv_used: list[str] = field(default_factory=list)

# The GUI keeps one managed child process per ordinary command. The shell
# polls this wrapper from asyncio so the app stays responsive, while tool
# switch and native-close flows can still terminate the worker immediately.
class TdCommandProcess:
    """Run one ordinary TD command in a child process so it can be stopped."""
    
    def __init__(self, request: GuiCommandRequest) -> None:
        self.request = request
        self.command = request.command
        # Use explicit spawn semantics so Windows, frozen builds, and native
        # NiceGUI mode all agree on how worker processes are created.
        context = multiprocessing.get_context('spawn')
        self._parent_conn, child_conn = context.Pipe(duplex=False)
        self._child_conn = child_conn
        self._process = context.Process(
            target=_execute_request_worker,
            args=(request, child_conn),
            name=f'td-gui-{request.command}',
        )
        self._result_consumed = False
        self._termination_message: str | None = None
    
    @classmethod
    def launch(cls, request: GuiCommandRequest) -> 'TdCommandProcess':
        runner = cls(request)
        runner.start()
        return runner
    
    def start(self) -> None:
        self._process.start()
        self._child_conn.close()
    
    @property
    def pid(self) -> int | None:
        return self._process.pid
    
    def is_active(self) -> bool:
        if self._result_consumed:
            return False
        return self._process.is_alive() or self._parent_conn.poll()
    
    def poll_result(self) -> GuiCommandResult | None:
        if self._result_consumed:
            return None
        if self._parent_conn.poll():
            try:
                result = self._parent_conn.recv()
            except EOFError:
                result = self._build_process_exit_result()
            self._result_consumed = True
            self._process.join(timeout=0.1)
            return result
        if self._process.is_alive():
            return None
        self._result_consumed = True
        self._process.join(timeout=0.1)
        return self._build_process_exit_result()
    
    def terminate(self, message: str) -> None:
        if self._result_consumed:
            return
        self._termination_message = message
        if self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=0.2)
    
    def close(self) -> None:
        self._parent_conn.close()
        if hasattr(self._process, 'close'):
            try:
                self._process.close()
            except ValueError:
                pass
    
    def _build_process_exit_result(self) -> GuiCommandResult:
        if self._termination_message:
            return GuiCommandResult(
                command=self.command,
                ok=False,
                error_message=self._termination_message,
                diagnostics_output=self._termination_message,
            )
        
        exit_code = self._process.exitcode
        return GuiCommandResult(
            command=self.command,
            ok=False,
            error_message=(
                f'{self.command.title()} stopped before returning a result.'
            ),
            diagnostics_output=(
                'The background command worker exited before returning a GUI '
                f'result payload (exit code {exit_code}).'
            ),
        )

class _AutoConfirmStdin(io.StringIO):
    """A stdin stand-in for a GUI-confirmed unanchored run.

    run gates its whole-galaxy search behind sys.stdin.isatty() and an
    interactive 'Continue?' input(). When the GUI has already confirmed, this
    reports as a TTY (so the guard passes) and answers every prompt with 'y'
    (so input() returns 'y' rather than EOF), letting the search proceed
    without any change to run_cmd.
    """

    def isatty(self) -> bool:
        return True

    def readline(self, *args, **kwargs) -> str:  # noqa: ARG002
        return 'y\n'

def _execute_request_worker(
    request: GuiCommandRequest,
    result_conn: Connection,
) -> None:
    # The worker has no usable interactive terminal, so give it a stdin that
    # makes run's unanchored 'Continue?' prompt resolve without blocking or
    # raising "EOF when reading a line". When the GUI has confirmed the
    # whole-galaxy search, answer 'y' so it proceeds; otherwise a null-device
    # stdin (isatty() False) makes run take its clean abort-with-guidance
    # branch. A leftover console handle (seen on Windows) otherwise reports as a
    # TTY yet EOFs immediately when read, which is the original crash.
    if getattr(request, 'confirm_unanchored', False):
        sys.stdin = _AutoConfirmStdin()
    else:
        try:
            sys.stdin = open(os.devnull, 'r')  # noqa: SIM115 (lives for worker)
        except OSError:
            pass
    try:
        result = TdExecutor().execute(request)
        try:
            # Send the fully prepared GUI result back to the parent. If the
            # payload still contains non-picklable TD objects, fall back to raw
            # text plus diagnostics instead of silently killing the worker.
            result_conn.send(result)
        except Exception as exc:
            transport_note = (
                'Structured GUI result could not be transported from the '
                'background worker; raw text output has been preserved.\n'
                f'{type(exc).__name__}: {exc}'
            )
            diagnostics = '\n\n'.join(
                part
                for part in (result.diagnostics_output, transport_note)
                if part
            )
            result_conn.send(
                GuiCommandResult(
                    command=result.command,
                    ok=result.ok,
                    error_message=result.error_message,
                    raw_output=result.raw_output,
                    diagnostics_output=diagnostics,
                    structured_result=None,
                    argv_used=list(result.argv_used),
                )
            )
    except Exception as exc:
        try:
            result_conn.send(
                GuiCommandResult(
                    command=request.command,
                    ok=False,
                    error_message=str(exc),
                    diagnostics_output=repr(exc),
                )
            )
        except Exception:
            pass
    finally:
        result_conn.close()

class TdExecutor:
    """Thin execution boundary between NiceGUI and TD core.
    
    The first scaffold keeps this intentionally small. It performs cheap,
    GUI-oriented sanity checks and reserves the authoritative command
    execution path for the next tranche.
    """
    
    def validate_request(self, request: GuiCommandRequest) -> list[str]:
        errors: list[str] = []
        context = request.effective_context()
        
        self._validate_optional_int(context, 'credits', minimum=0, errors=errors)
        self._validate_optional_int(context, 'capacity', minimum=0, errors=errors)
        self._validate_optional_int(
            context,
            'reserved_capacity',
            minimum=0,
            errors=errors,
        )
        self._validate_optional_int(
            context,
            'insurance',
            minimum=0,
            errors=errors,
        )
        self._validate_optional_float(
            context,
            'max_data_age_days',
            minimum=0.0,
            errors=errors,
        )
        self._validate_optional_float(
            context,
            'jump_range_full_ly',
            minimum=0.0,
            errors=errors,
        )
        self._validate_optional_float(
            context,
            'jump_range_empty_ly',
            minimum=0.0,
            errors=errors,
        )
        
        capacity = context.get('capacity')
        reserved_capacity = context.get('reserved_capacity')
        if (
            isinstance(capacity, int)
            and isinstance(reserved_capacity, int)
            and reserved_capacity > capacity
        ):
            errors.append('Reserved Capacity cannot exceed Capacity.')
        
        if request.command == 'run':
            resolved = request.resolved_values()
            if self._effective_capacity(context) is None:
                errors.append('Run requires Capacity.')
            if context.get('credits') is None:
                errors.append('Run requires Credits.')
            if (
                not resolved.get('direct')
                and context.get('jump_range_full_ly') is None
            ):
                errors.append('Run requires Jump Range (Full).')
            
            has_to = bool(str(resolved.get('ending') or '').strip())
            has_towards = bool(str(resolved.get('goalSystem') or '').strip())
            if has_to and has_towards:
                errors.append('Run To and Towards are mutually exclusive.')
            # An unanchored run (no From and no To) is a whole-galaxy search.
            # It is allowed, but the GUI confirms it first (see the shell's
            # unanchored-run confirmation) and the worker answers run's prompt;
            # validation does not block it.

        if request.command == 'trade':
            validate_trade_request(
                resolved=self._global_command_resolved_values(request),
                errors=errors,
                validate_optional_int=self._validate_optional_int,
            )
        
        if request.command == 'buy':
            from .td_exec_commands import validate_buy_request
            
            validate_buy_request(
                resolved=self._global_command_resolved_values(request),
                errors=errors,
                validate_optional_int=self._validate_optional_int,
                validate_optional_float=self._validate_optional_float,
                split_search_terms=self._split_search_terms,
            )
        
        if request.command == 'sell':
            from .td_exec_commands import validate_sell_request
            
            validate_sell_request(
                resolved=self._global_command_resolved_values(request),
                errors=errors,
                validate_optional_int=self._validate_optional_int,
                validate_optional_float=self._validate_optional_float,
                split_search_terms=self._split_search_terms,
            )
        
        if request.command == 'local':
            validate_local_request(
                resolved=self._global_command_resolved_values(request),
                errors=errors,
                validate_optional_float=self._validate_optional_float,
            )
        
        if request.command == 'olddata':
            validate_olddata_request(
                resolved=self._global_command_resolved_values(request),
                errors=errors,
                validate_optional_int=self._validate_optional_int,
                validate_optional_float=self._validate_optional_float,
            )
        
        if request.command == 'market':
            validate_market_request(
                resolved=self._global_command_resolved_values(request),
                errors=errors,
            )
        
        if request.command == 'nav':
            validate_nav_request(
                resolved=self._global_command_resolved_values(request),
                errors=errors,
                validate_optional_int=self._validate_optional_int,
                validate_optional_float=self._validate_optional_float,
            )
        
        return errors
    
    def execute(self, request: GuiCommandRequest) -> GuiCommandResult:
        errors = self.validate_request(request)
        if errors:
            return GuiCommandResult(
                command=request.command,
                ok=False,
                error_message=errors[0],
                diagnostics_output='\n'.join(errors),
            )
        
        if request.command == 'run':
            return self._execute_run(request)
        if request.command == 'buy':
            return self._execute_buy(request)
        if request.command == 'sell':
            return self._execute_sell(request)
        if request.command == 'trade':
            return self._execute_trade(request)
        if request.command == 'local':
            return self._execute_local(request)
        if request.command == 'olddata':
            return self._execute_olddata(request)
        if request.command == 'market':
            return self._execute_market(request)
        if request.command == 'nav':
            return self._execute_nav(request)
        if request.command == 'import':
            return self._execute_import(request)
        
        return GuiCommandResult(
            command=request.command,
            ok=False,
            error_message=(
                f"'{request.command}' is not wired into the TD adapter yet."
            ),
            diagnostics_output=(
                'Only the run, buy, sell, trade, local, nav, olddata, '
                'market, and import commands are currently connected '
                'to the in-process TD execution path.'
            ),
        )
    
    def _execute_run(self, request: GuiCommandRequest) -> GuiCommandResult:
        resolved = request.resolved_values()
        context = request.effective_context()
        argv = build_run_argv(
            resolved=resolved,
            effective_capacity=self._effective_capacity(context),
            append_option=self._append_option,
            append_flag=self._append_flag,
        )
        return self._execute_td_command(request, argv)
    
    def _execute_buy(self, request: GuiCommandRequest) -> GuiCommandResult:
        resolved = self._global_command_resolved_values(request)
        argv = build_buy_argv(
            resolved=resolved,
            append_option=self._append_option,
            append_flag=self._append_flag,
            split_search_terms=self._split_search_terms,
        )
        return self._execute_td_command(request, argv)
    
    def _execute_sell(self, request: GuiCommandRequest) -> GuiCommandResult:
        resolved = self._global_command_resolved_values(request)
        argv = build_sell_argv(
            resolved=resolved,
            append_option=self._append_option,
            append_flag=self._append_flag,
            split_search_terms=self._split_search_terms,
        )
        return self._execute_td_command(request, argv)
    
    def _execute_trade(self, request: GuiCommandRequest) -> GuiCommandResult:
        resolved = self._global_command_resolved_values(request)
        argv = build_trade_argv(
            resolved=resolved,
            append_option=self._append_option,
            append_flag=self._append_flag,
        )
        return self._execute_td_command(request, argv)
    
    def _execute_local(self, request: GuiCommandRequest) -> GuiCommandResult:
        resolved = self._global_command_resolved_values(request)
        argv = build_local_argv(
            resolved=resolved,
            append_option=self._append_option,
            append_flag=self._append_flag,
        )
        return self._execute_td_command(request, argv)
    
    def _execute_olddata(self, request: GuiCommandRequest) -> GuiCommandResult:
        resolved = self._global_command_resolved_values(request)
        argv = build_olddata_argv(
            resolved=resolved,
            append_option=self._append_option,
            append_flag=self._append_flag,
        )
        result = self._execute_td_command(request, argv)
        if isinstance(result.structured_result, dict):
            payload = dict(result.structured_result)
            payload['near'] = resolved.get('near')
            result.structured_result = payload
        return result
    
    def _execute_market(self, request: GuiCommandRequest) -> GuiCommandResult:
        resolved = self._global_command_resolved_values(request)
        argv = build_market_argv(
            resolved=resolved,
            append_flag=self._append_flag,
        )
        return self._execute_td_command(request, argv)
    
    def _execute_nav(self, request: GuiCommandRequest) -> GuiCommandResult:
        resolved = self._global_command_resolved_values(request)
        argv = build_nav_argv(
            resolved=resolved,
            append_option=self._append_option,
            append_flag=self._append_flag,
            split_search_terms=self._split_search_terms,
        )
        return self._execute_td_command(request, argv)
    
    def _execute_import(self, request: GuiCommandRequest) -> GuiCommandResult:
        resolved = _drop_blank_values(request.main_values)
        argv = build_import_argv(
            resolved=resolved,
            append_option=self._append_option,
        )
        payload = execute_import_command(
            request=request,
            argv=argv,
        )
        return GuiCommandResult(
            command=request.command,
            ok=payload.ok,
            error_message=payload.error_message,
            raw_output=payload.raw_output,
            diagnostics_output=payload.diagnostics_output,
            structured_result=_snapshot_structured_result(
                request.command,
                payload.structured_result,
            ),
            argv_used=list(argv),
        )
    
    @staticmethod
    def _global_command_resolved_values(
        request: GuiCommandRequest,
    ) -> dict[str, Any]:
        # Non-run commands only inherit the commander-wide globals from the
        # left pane; ship-specific context stays a run-only concern.
        resolved = _drop_blank_values(request.global_values)
        resolved.update(_drop_blank_values(request.main_values))
        resolved.update(_drop_blank_values(request.advanced_values))
        return resolved
    
    @staticmethod
    def _split_search_terms(value: Any) -> list[str]:
        if value in (None, ''):
            return []
        
        # GUI textareas allow either commas or newlines; normalize both so the
        # argv builders can treat multi-value fields consistently.
        terms: list[str] = []
        for line in str(value).splitlines():
            for part in line.split(','):
                cleaned = part.strip()
                if cleaned:
                    terms.append(cleaned)
        return terms
    
    @staticmethod
    def _validate_optional_int(
        payload: dict[str, Any],
        key: str,
        *,
        minimum: int | None,
        errors: list[str],
    ) -> None:
        value = payload.get(key)
        if value is None:
            return
        if not isinstance(value, int):
            errors.append(f'{key} must be an integer.')
            return
        if minimum is not None and value < minimum:
            errors.append(f'{key} must be {minimum} or greater.')
    
    def _execute_td_command(
        self,
        request: GuiCommandRequest,
        argv: list[str],
    ) -> GuiCommandResult:
        diagnostics_stream = io.StringIO()
        render_stream = io.StringIO()
        structured_result = None
        structured_snapshot = None
        
        try:
            cmdenv = commands.CommandIndex().parse(list(argv))
            # Honour an explicit GUI journal directory. journal_path() reads
            # tdenv.journal_path ahead of the ELITE_JOURNAL_PATH env var and the
            # OS default, so this is exactly the override the CLI already expects.
            # Blank/None leaves cmdenv untouched and preserves auto-discovery.
            journal_dir = getattr(request, 'journal_dir', None)
            if journal_dir:
                cmdenv.journal_path = journal_dir
            # Keep diagnostic/preflight output separate from rendered command
            # output so the right pane can show either view cleanly.
            diagnostics_console = Console(
                file=diagnostics_stream,
                force_terminal=False,
                color_system=None,
                highlight=False,
            )
            render_console = Console(
                file=render_stream,
                force_terminal=False,
                color_system=None,
                highlight=False,
            )
            cmdenv.console = diagnostics_console
            cmdenv.stderr = diagnostics_console
            
            with redirect_stdout(diagnostics_stream), redirect_stderr(
                diagnostics_stream
            ):
                preflight = getattr(cmdenv, 'preflight', None)
                if preflight and callable(preflight):
                    preflight()

                # Build the backend exactly as the CLI does: a resolver-tier
                # command gets a TradeORM handle; a no-backend command gets None.
                tdb = build_backend(cmdenv)
                try:
                    self._check_trade_data(cmdenv, tdb)
                    results = cmdenv.run(tdb)
                    if results:
                        # Preserve structured data for the GUI table renderer,
                        # but also capture the normal text render for fallback.
                        structured_result = getattr(results, 'data', None)
                        if structured_result is None:
                            structured_result = {
                                'summary': getattr(results, 'summary', None),
                                'rows': list(getattr(results, 'rows', [])),
                            }
                        cmdenv.console = render_console
                        cmdenv.stderr = render_console
                        with redirect_stdout(render_stream), redirect_stderr(
                            render_stream
                        ):
                            results.render(cmdenv, tdb)
                        # Flatten ORM-backed results into plain data while the
                        # session is still open. After tdb.close() any lazy
                        # relationship access (e.g. System.stations) would raise
                        # DetachedInstanceError.
                        structured_snapshot = _snapshot_structured_result(
                            request.command,
                            structured_result,
                            summary=bool(getattr(cmdenv, 'summary', False)),
                        )
                finally:
                    if tdb is not None:
                        tdb.close(final=True)
        except cmd_exceptions.CommandLineError as exc:
            return self._error_result(request.command, argv, str(exc))
        except tradeexcept.TradeException as exc:
            return self._error_result(request.command, argv, str(exc))
        except Exception as exc:
            return self._error_result(request.command, argv, str(exc), repr(exc))
        
        return GuiCommandResult(
            command=request.command,
            ok=True,
            raw_output=_strip_ansi(render_stream.getvalue().strip()),
            diagnostics_output=_strip_ansi(
                diagnostics_stream.getvalue().strip()
            ),
            structured_result=structured_snapshot,
            argv_used=argv,
        )
    
    @staticmethod
    def _check_trade_data(cmdenv: Any, tdb: Any) -> None:
        if not cmdenv.usesTradeData:
            return
        
        tsc = tdb.tradingStationCount
        if tsc == 0:
            raise cmd_exceptions.NoDataError(
                'There is no trading data for ANY station in the local '
                'database. Please enter or import price data.'
            )
        if tsc == 1:
            raise cmd_exceptions.NoDataError(
                'The local database only contains trading data for one '
                'station. Please enter or import data for additional stations.'
            )
        if tsc < 8:
            cmdenv.NOTE(
                'The local database only contains trading data for {} '
                'stations. Please enter or import data for additional '
                'stations.'.format(tsc)
            )
    
    @staticmethod
    def _validate_optional_float(
        payload: dict[str, Any],
        key: str,
        *,
        minimum: float | None,
        errors: list[str],
    ) -> None:
        value = payload.get(key)
        if value is None:
            return
        if not isinstance(value, (int, float)):
            errors.append(f'{key} must be numeric.')
            return
        if minimum is not None and float(value) < minimum:
            errors.append(f'{key} must be {minimum} or greater.')
    
    @staticmethod
    def _error_result(
        command: str,
        argv: list[str],
        error_message: str,
        diagnostics_output: str | None = None,
    ) -> GuiCommandResult:
        cleaned_error = _strip_ansi(error_message)
        cleaned_diagnostics = _strip_ansi(
            diagnostics_output or error_message
        )
        return GuiCommandResult(
            command=command,
            ok=False,
            error_message=cleaned_error,
            diagnostics_output=cleaned_diagnostics,
            argv_used=argv,
        )
    
    @staticmethod
    def _effective_capacity(context: dict[str, Any]) -> int | None:
        # Match the shell's displayed effective capacity so validation, copied
        # overrides, and execution all agree on the usable cargo space.
        capacity = context.get('capacity')
        reserved_capacity = context.get('reserved_capacity')
        if capacity is None:
            return None
        if reserved_capacity is None:
            return capacity
        if reserved_capacity > capacity:
            return None
        return capacity - reserved_capacity
    
    @staticmethod
    def _append_option(argv: list[str], option: str, value: Any) -> None:
        if value in (None, ''):
            return
        argv.extend([option, str(value)])
    
    @staticmethod
    def _append_flag(argv: list[str], option: str, enabled: Any) -> None:
        if enabled:
            argv.append(option)


# Some TD render paths still emit ANSI-coloured CLI text. Strip it before the
# GUI sees fallback output so transport failures cannot leak escape sequences.
_ANSI_ESCAPE_RE = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')

def _strip_ansi(text: str) -> str:
    if not text:
        return text
    return _ANSI_ESCAPE_RE.sub('', text)

# Child-process results must cross a multiprocessing pipe, so convert any TD
# objects into plain Python data here rather than teaching the renderer or
# shell about pickling quirks.
def _snapshot_structured_result(
    command: str,
    structured_result: Any,
    summary: bool = False,
) -> Any:
    if structured_result is None:
        return None
    if command == 'run':
        return _snapshot_run_routes(structured_result, summary=summary)
    return _snapshot_value(structured_result)

# `run` returns a post-L RunResult: a frozen object graph of routes -> hops ->
# cargo lines and jump paths. It carries no live DB handles, but we still flatten
# it to plain dicts here so the worker payload stays simple and picklable and the
# GUI renderer reads one stable shape. The layout mirrors the CLI rich renderer
# (planner/render_rich.py): a station-centric view where each stop sells what it
# arrived carrying and buys what it leaves with.
def _snapshot_run_routes(result: Any, *, summary: bool = False) -> Any:
    # `summary` records whether the user asked for --summary, so the GUI can
    # pick its compact render mode. The RunResult itself is identical either
    # way; only the chosen presentation differs.
    routes = getattr(result, 'routes', None)
    if routes is None:
        # Guidance-only/empty run (run_cmd sets results.data == ()), or an
        # unexpected shape. Either way there are no routes to render.
        return {'routes': [], 'warnings': [], 'summary': bool(summary)}

    warnings: list[str] = []
    for warning in getattr(result, 'warnings', ()) or ():
        warnings.append(_run_warning_text(warning))

    return {
        'routes': [_snapshot_run_route(route) for route in routes],
        'warnings': warnings,
        'summary': bool(summary),
    }

def _run_warning_text(warning: Any) -> str:
    # Reuse the planner's own warning wording so the GUI matches the CLI.
    try:
        from tradedangerous.planner.render_text import _render_warning
        return _render_warning(warning)
    except Exception:  # noqa: BLE001 - never let a warning break the snapshot
        return str(warning)

def _snapshot_run_route(route: Any) -> dict[str, Any]:
    hops = list(getattr(route, 'hops', ()) or ())
    stations = list(getattr(route, 'stations', ()) or ())
    starting = int(getattr(route, 'starting_credits', 0) or 0)
    total_jumps, total_ly = _run_jump_totals(hops)

    if stations:
        origin, destination = stations[0].dbname, stations[-1].dbname
    elif hops:
        origin = hops[0].source_station.dbname
        destination = hops[-1].destination_station.dbname
    else:
        origin = destination = ''

    capped = any(
        _run_line_capped(line)
        for hop in hops
        for line in hop.cargo.lines
    )

    return {
        'origin': origin,
        'destination': destination,
        'hop_count': len(hops),
        'total_jumps': total_jumps,
        'total_ly': total_ly,
        'total_profit': int(getattr(route, 'total_raw_profit', 0) or 0),
        'starting_credits': starting,
        'ending_credits': int(getattr(route, 'ending_credits', 0) or 0),
        'arrival_hops': getattr(route, 'arrival_hops', None),
        'capped': capped,
        # The summary view is the same station-centric stops as the full table,
        # just rendered leaner (comma loads, no prices/nav/balance), so it needs
        # no separate per-hop data.
        'stops': _run_stops(hops, starting),
    }

def _run_stops(hops: list[Any], starting: int) -> list[dict[str, Any]]:
    # A row per stop: the first hop's source, then every hop's destination. At
    # stop index i you sell what the arriving hop (hops[i-1]) carried and buy
    # what the departing hop (hops[i]) loads; profit and running balance land on
    # the arrival row, matching planner/render_rich.py's _stops_table.
    if not hops:
        return []
    stations = [hops[0].source_station]
    stations.extend(hop.destination_station for hop in hops)

    stops: list[dict[str, Any]] = []
    running = starting
    for index, station in enumerate(stations):
        sell_hop = hops[index - 1] if index > 0 else None
        buy_hop = hops[index] if index < len(hops) else None
        profit = None
        if sell_hop is not None:
            profit = int(getattr(sell_hop, 'raw_profit', 0) or 0)
            running += profit
        stops.append(
            {
                'station': station.dbname,
                'nav': _run_nav_lines(buy_hop),
                'sell': _run_cargo_lines(sell_hop, 'sell'),
                'buy': _run_cargo_lines(buy_hop, 'buy'),
                'profit': profit,
                'balance': running,
            }
        )
    return stops

def _run_cargo_lines(hop: Any, side: str) -> list[dict[str, Any]]:
    if hop is None:
        return []
    lines: list[dict[str, Any]] = []
    for line in hop.cargo.lines:
        price = line.sell_price if side == 'sell' else line.buy_price
        lines.append(
            {
                'qty': int(line.quantity),
                'item': line.item_name,
                'price': int(price),
                'capped': side == 'buy' and _run_line_capped(line),
            }
        )
    return lines

def _run_nav_lines(hop: Any) -> list[str]:
    # The leg leaving this station, one jump per line like render_rich's verbose
    # tier: the system jumped to and that leg's own length. Empty when the hop
    # carries no jump path (--direct, where the commander plots it themselves).
    if hop is None:
        return []
    leg = getattr(hop, 'jump_path', None)
    if leg is None:
        return []
    if getattr(leg, 'is_same_system', False):
        return [f'Supercruise · {leg.distance_ly:.1f} ly']
    systems = list(getattr(leg, 'systems', ()) or ())
    lines: list[str] = []
    for index in range(1, len(systems)):
        previous, system = systems[index - 1], systems[index]
        leg_ly = math.dist(
            (previous.x, previous.y, previous.z),
            (system.x, system.y, system.z),
        )
        lines.append(f'{system.dbname} · {leg_ly:.1f} ly')
    return lines

def _run_line_capped(line: Any) -> bool:
    # Mirrors render_rich._bulk_capped: a Metals/Minerals line loaded right up to
    # the 25%-capped destination demand is one the bulk-sale-tax cap held back.
    return bool(
        getattr(line, 'bulk_sale_tax_sensitive', False)
        and getattr(line, 'quantity', None)
        == getattr(line, 'effective_destination_demand_units', None)
    )

def _run_jump_totals(hops: list[Any]) -> tuple[int, float]:
    # Same-system supercruise and --direct legs are not jumps; they add nothing.
    total_jumps = 0
    total_ly = 0.0
    for hop in hops:
        leg = getattr(hop, 'jump_path', None)
        if leg is not None and not getattr(leg, 'is_same_system', False):
            total_jumps += int(getattr(leg, 'jumps', 0) or 0)
            total_ly += float(getattr(leg, 'distance_ly', 0.0) or 0.0)
    return total_jumps, total_ly

# Generic snapshot path for every non-import command other than `run`. This
# intentionally prefers plain dict/list/scalar structures over cleverness so
# the renderer stays easy to inspect and the worker payload stays safe.
def _snapshot_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    
    if isinstance(value, dict):
        return {
            str(key): _snapshot_value(item)
            for key, item in value.items()
        }
    
    if isinstance(value, (list, tuple)):
        return [_snapshot_value(item) for item in value]
    
    if isinstance(value, set):
        return [
            _snapshot_value(item)
            for item in sorted(value, key=str)
        ]
    
    mapping = getattr(value, '_mapping', None)
    if mapping is not None:
        return {
            str(key): _snapshot_value(item)
            for key, item in mapping.items()
        }
    
    if _is_result_row(value):
        return {
            key: _snapshot_value(item)
            for key, item in vars(value).items()
            if not key.startswith('_')
        }
    
    if _looks_like_station(value):
        return _snapshot_station(value)
    
    if _looks_like_system(value):
        return _snapshot_system(value)
    
    named_value = _named_display_value(value)
    if named_value is not None:
        return {'name': named_value}
    
    if hasattr(value, '__dict__'):
        return {
            key: _snapshot_value(item)
            for key, item in vars(value).items()
            if not key.startswith('_')
        }
    
    return str(value)

def _snapshot_station(station: Any) -> dict[str, Any]:
    return {
        'name': _named_display_value(station),
        'dbname': _display_attr(station, 'dbname'),
        'lsText': _safe_station_ls_text(station),
        'market': _display_attr(station, 'market'),
        'blackMarket': _display_attr(station, 'blackMarket', 'blackmarket'),
        'shipyard': _display_attr(station, 'shipyard'),
        'outfitting': _display_attr(station, 'outfitting'),
        'rearm': _display_attr(station, 'rearm'),
        'refuel': _display_attr(station, 'refuel'),
        'repair': _display_attr(station, 'repair'),
        'maxPadSize': _display_attr(station, 'maxPadSize', 'max_pad_size'),
        'planetary': _display_attr(station, 'planetary'),
        'fleet': _display_attr(station, 'fleet'),
        'settlement': _display_attr(station, 'settlement'),
        'itemCount': _display_attr(station, 'itemCount', 'item_count'),
    }

def _snapshot_system(system: Any) -> dict[str, Any]:
    return {
        'name': _named_display_value(system),
        'dbname': _display_attr(system, 'dbname'),
    }

def _safe_station_ls_text(station: Any) -> str | None:
    dist_from_star = _callable_attr(station, 'distFromStar')
    if dist_from_star not in (None, ''):
        return str(dist_from_star)
    
    ls_from_star = _display_attr(station, 'lsFromStar', 'ls_from_star')
    if ls_from_star in (None, ''):
        return None
    if int(ls_from_star or 0) == 0:
        return '?'
    return str(ls_from_star)

def _is_result_row(value: Any) -> bool:
    return value.__class__.__name__ == 'ResultRow'

def _looks_like_station(value: Any) -> bool:
    return all(
        _has_any_attr(value, *attrs)
        for attrs in (
            ('system',),
            ('dbname', 'name'),
            ('lsFromStar', 'ls_from_star'),
            ('market',),
            ('blackMarket', 'blackmarket'),
        )
    )

def _looks_like_system(value: Any) -> bool:
    return all(
        _has_any_attr(value, *attrs)
        for attrs in (
            ('dbname', 'name'),
            ('posX', 'pos_x'),
            ('posY', 'pos_y'),
            ('posZ', 'pos_z'),
            ('stations',),
        )
    )

def _named_display_value(value: Any) -> str | None:
    if value is None:
        return None
    
    name_attr = getattr(value, 'name', None)
    if callable(name_attr):
        try:
            return str(name_attr(0))
        except TypeError:
            return str(name_attr())
    if name_attr not in (None, ''):
        return str(name_attr)
    
    dbname = _display_attr(value, 'dbname')
    if dbname not in (None, ''):
        return str(dbname)
    
    return None

# Support both legacy TD objects and ORM models, which do not agree on whether
# fields like `name`/`dbname` are plain attributes or helper methods.
# Centralising that wrinkle keeps the snapshot code readable.
def _display_attr(value: Any, *names: str) -> Any:
    for name in names:
        if not hasattr(value, name):
            continue
        attr = getattr(value, name)
        if callable(attr):
            try:
                return attr()
            except TypeError:
                try:
                    return attr(0)
                except TypeError:
                    return attr
        return attr
    return None

def _callable_attr(value: Any, *names: str) -> Any:
    for name in names:
        if not hasattr(value, name):
            continue
        attr = getattr(value, name)
        if not callable(attr):
            continue
        try:
            return attr()
        except TypeError:
            try:
                return attr(False)
            except TypeError:
                try:
                    return attr(0)
                except TypeError:
                    continue
    return None

def _has_any_attr(value: Any, *names: str) -> bool:
    return any(hasattr(value, name) for name in names)

def _drop_blank_values(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop fields that should behave like "unset" when translated to argv."""
    
    return {
        key: value
        for key, value in payload.items()
        if value not in (None, '')
    }
