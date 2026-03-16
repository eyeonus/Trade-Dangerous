from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
import io
from typing import Any

from rich.console import Console

from tradedangerous import commands, tradedb, tradeexcept
from tradedangerous.commands import exceptions as cmd_exceptions

from .td_exec_run import build_run_argv
from .td_exec_buysell import build_buy_argv, build_sell_argv

@dataclass(slots=True)
class GuiCommandRequest:
    command: str
    main_values: dict[str, Any] = field(default_factory=dict)
    advanced_values: dict[str, Any] = field(default_factory=dict)
    context_overrides: dict[str, Any] = field(default_factory=dict)
    global_values: dict[str, Any] = field(default_factory=dict)
    ship_profile_values: dict[str, Any] = field(default_factory=dict)
    import_monitor: Any = None

    def effective_context(self) -> dict[str, Any]:
        context: dict[str, Any] = {}
        context.update(_drop_blank_values(self.global_values))
        context.update(_drop_blank_values(self.ship_profile_values))
        context.update(_drop_blank_values(self.context_overrides))
        return context

    def resolved_values(self) -> dict[str, Any]:
        resolved = self.effective_context()
        resolved.update(_drop_blank_values(self.main_values))
        resolved.update(_drop_blank_values(self.advanced_values))
        return resolved


@dataclass(slots=True)
class GuiCommandResult:
    command: str
    ok: bool
    error_message: str | None = None
    raw_output: str = ''
    diagnostics_output: str = ''
    structured_result: Any = None
    argv_used: list[str] = field(default_factory=list)


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
        if request.command == 'import':
            return self._execute_import(request)

        return GuiCommandResult(
            command=request.command,
            ok=False,
            error_message=(
                f"'{request.command}' is not wired into the TD adapter yet."
            ),
            diagnostics_output=(
                'Only the run, buy, sell, and import commands are currently '
                'connected to the in-process TD execution path.'
            ),
        )

    def _execute_run(self, request: GuiCommandRequest) -> GuiCommandResult:
        resolved = request.resolved_values()
        context = request.effective_context()
        argv = build_run_argv(
            resolved=resolved,
            context=context,
            effective_capacity=self._effective_capacity(context),
            append_option=self._append_option,
            append_flag=self._append_flag,
        )
        return self._execute_td_command(request, argv)

    def _execute_buy(self, request: GuiCommandRequest) -> GuiCommandResult:
        resolved = self._buy_sell_resolved_values(request)
        context = request.effective_context()
        argv = build_buy_argv(
            resolved=resolved,
            context=context,
            effective_capacity=self._effective_capacity(context),
            append_option=self._append_option,
            append_flag=self._append_flag,
        )
        return self._execute_td_command(request, argv)

    def _execute_sell(self, request: GuiCommandRequest) -> GuiCommandResult:
        resolved = self._buy_sell_resolved_values(request)
        context = request.effective_context()
        argv = build_sell_argv(
            resolved=resolved,
            context=context,
            effective_capacity=self._effective_capacity(context),
            append_option=self._append_option,
            append_flag=self._append_flag,
        )
        return self._execute_td_command(request, argv)

    def _execute_import(self, request: GuiCommandRequest) -> GuiCommandResult:
        from .td_exec_import import build_import_argv, execute_import_command

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
            structured_result=payload.structured_result,
            argv_used=list(argv),
        )
    
    @staticmethod
    def _buy_sell_resolved_values(
        request: GuiCommandRequest,
    ) -> dict[str, Any]:
        resolved = _drop_blank_values(request.global_values)
        resolved.update(_drop_blank_values(request.main_values))
        resolved.update(_drop_blank_values(request.advanced_values))
        return resolved
    
    @staticmethod
    def _split_search_terms(value: Any) -> list[str]:
        if value in (None, ''):
            return []

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

        try:
            cmdenv = commands.CommandIndex().parse(list(argv))
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

                tdb = tradedb.TradeDB(cmdenv, load=cmdenv.wantsTradeDB)
                try:
                    self._check_trade_data(cmdenv, tdb)
                    results = cmdenv.run(tdb)
                    if results:
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
                finally:
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
            raw_output=render_stream.getvalue().strip(),
            diagnostics_output=diagnostics_stream.getvalue().strip(),
            structured_result=structured_result,
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
        return GuiCommandResult(
            command=command,
            ok=False,
            error_message=error_message,
            diagnostics_output=diagnostics_output or error_message,
            argv_used=argv,
        )

    @staticmethod
    def _effective_capacity(context: dict[str, Any]) -> int | None:
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


def _drop_blank_values(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if value not in (None, '')
    }
