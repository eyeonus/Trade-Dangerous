"""CLI entrypoint for the Trade Dangerous NiceGUI shell."""

from __future__ import annotations

import _thread
import argparse
import multiprocessing
import os
import signal
import sys
import time
from threading import Event, Thread
from typing import Any, Callable, Sequence

from nicegui import app, ui

from .profiles import load_gui_store
from .shell import AppShell, COMMAND_OPTIONS

_ORIGINAL_NATIVE_ACTIVATE: Callable[..., None] | None = None
_NATIVE_WINDOW_CLOSE_SHARED_STATE: Any = None


class NativeWindowCloseState:
    """Shared native-window close state for the server and pywebview processes."""

    def __init__(self, *, enabled: bool) -> None:
        self._manager = None
        self.shared = None
        if not enabled:
            return

        self._manager = multiprocessing.Manager()
        self.shared = self._manager.Namespace()
        self.clear()

    def mark_running(self, *, kind: str, command: str, pid: int | None) -> None:
        if self.shared is None:
            return
        self.shared.active_kind = str(kind)
        self.shared.active_command = str(command)
        self.shared.active_worker_pid = int(pid or 0)

    def clear(self) -> None:
        if self.shared is None:
            return
        self.shared.active_kind = ''
        self.shared.active_command = ''
        self.shared.active_worker_pid = 0

    def shutdown(self) -> None:
        if self._manager is not None:
            self._manager.shutdown()
            self._manager = None
            self.shared = None


def _command_label(command: str | None) -> str:
    if not command:
        return 'Command'
    return COMMAND_OPTIONS.get(command, str(command).title())


def _terminate_native_worker(pid: int) -> None:
    if pid <= 0:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return


def _read_native_close_state(shared_state: Any) -> tuple[str, str, int]:
    try:
        kind = str(getattr(shared_state, 'active_kind', '') or '')
        command = str(getattr(shared_state, 'active_command', '') or '')
        pid = int(getattr(shared_state, 'active_worker_pid', 0) or 0)
    except (BrokenPipeError, EOFError, OSError):
        return '', '', 0
    return kind, command, pid


def _clear_native_close_state(shared_state: Any) -> None:
    try:
        shared_state.active_kind = ''
        shared_state.active_command = ''
        shared_state.active_worker_pid = 0
    except (BrokenPipeError, EOFError, OSError):
        return


def _bind_native_close_handler(pywebview_window: Any, shared_state: Any) -> None:
    def on_closing(window: Any) -> bool:
        kind, command, pid = _read_native_close_state(shared_state)
        if not kind or pid <= 0:
            return True

        title = 'Close Trade Dangerous?'
        if kind == 'import':
            message = (
                'Import is still running. Closing now will stop it immediately '
                'and may leave your local Trade Dangerous database inconsistent. '
                'Close anyway?'
            )
        else:
            message = (
                f'{_command_label(command)} is still running. Closing now will '
                'stop it immediately. Close anyway?'
            )

        if not window.create_confirmation_dialog(title, message):
            return False

        _terminate_native_worker(pid)
        _clear_native_close_state(shared_state)
        return True

    pywebview_window.events.closing += on_closing


def _open_window_with_close_handler(
    protocol: str,
    host: str,
    port: int,
    title: str,
    width: int,
    height: int,
    fullscreen: bool,
    frameless: bool,
    method_queue: Any,
    response_queue: Any,
    event_sender: Any,
    shared_state: Any,
) -> None:
    from nicegui import core, helpers
    from nicegui.native import native_mode

    while not helpers.is_port_open(host, port):
        time.sleep(0.1)

    window_kwargs = {
        'url': f'{protocol}://{host}:{port}',
        'title': title,
        'width': width,
        'height': height,
        'fullscreen': fullscreen,
        'frameless': frameless,
        **core.app.native.window_args,
    }
    native_mode.webview.settings.update(**core.app.native.settings)
    window = native_mode.webview.create_window(**window_kwargs)
    assert window is not None

    closed = Event()
    window.events.closed += closed.set
    if shared_state is not None:
        _bind_native_close_handler(window, shared_state)
    native_mode._bind_pywebview_events(window, event_sender)
    native_mode._start_window_method_executor(
        window,
        method_queue,
        response_queue,
        closed,
    )
    native_mode.webview.start(**core.app.native.start_args)


def _activate_native_mode_with_close_handler(
    protocol: str,
    host: str,
    port: int,
    title: str,
    width: int,
    height: int,
    fullscreen: bool,
    frameless: bool,
    shutdown_event: Any = None,
) -> None:
    global _ORIGINAL_NATIVE_ACTIVATE

    if _NATIVE_WINDOW_CLOSE_SHARED_STATE is None:
        assert _ORIGINAL_NATIVE_ACTIVATE is not None
        _ORIGINAL_NATIVE_ACTIVATE(
            protocol,
            host,
            port,
            title,
            width,
            height,
            fullscreen,
            frameless,
            shutdown_event,
        )
        return

    from nicegui import core, optional_features
    from nicegui.logging import log
    from nicegui.native import native, native_mode
    from nicegui.server import Server

    def check_shutdown() -> None:
        while process.is_alive():
            time.sleep(0.1)
        if shutdown_event is not None:
            shutdown_event.set()
        Server.instance.should_exit = True
        while not core.app.is_stopped:
            time.sleep(0.1)
        _thread.interrupt_main()
        native_mode.event_manager.stop()
        native.remove_queues()

    if not optional_features.has('webview'):
        log.error(
            'Native mode is not supported in this configuration.\n'
            'Please run "pip install pywebview" to use it.'
        )
        sys.exit(1)

    multiprocessing.freeze_support()
    native.create_queues()
    native_mode.event_manager.start()
    args = (
        protocol,
        host,
        port,
        title,
        width,
        height,
        fullscreen,
        frameless,
        native.method_queue,
        native.response_queue,
        native.event_sender,
        _NATIVE_WINDOW_CLOSE_SHARED_STATE,
    )
    process = multiprocessing.Process(
        target=_open_window_with_close_handler,
        args=args,
        daemon=True,
    )
    process.start()

    Thread(target=check_shutdown, daemon=True).start()


def _install_native_activate_shim(shared_state: Any) -> None:
    import nicegui.ui_run as ui_run_module
    from nicegui.native import native_mode

    global _ORIGINAL_NATIVE_ACTIVATE, _NATIVE_WINDOW_CLOSE_SHARED_STATE

    if _ORIGINAL_NATIVE_ACTIVATE is None:
        _ORIGINAL_NATIVE_ACTIVATE = native_mode.activate

    _NATIVE_WINDOW_CLOSE_SHARED_STATE = shared_state
    native_mode.activate = _activate_native_mode_with_close_handler
    ui_run_module.native_module.activate = _activate_native_mode_with_close_handler


def _restore_native_activate_shim() -> None:
    import nicegui.ui_run as ui_run_module
    from nicegui.native import native_mode

    global _NATIVE_WINDOW_CLOSE_SHARED_STATE

    if _ORIGINAL_NATIVE_ACTIVATE is not None:
        native_mode.activate = _ORIGINAL_NATIVE_ACTIVATE
        ui_run_module.native_module.activate = _ORIGINAL_NATIVE_ACTIVATE
    _NATIVE_WINDOW_CLOSE_SHARED_STATE = None


def build_arg_parser() -> argparse.ArgumentParser:
    """Expose the small launcher surface for native versus browser shells."""

    parser = argparse.ArgumentParser(prog='tradegui.py')
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        '--native',
        dest='native',
        action='store_true',
        help='Run NiceGUI in native window mode.',
    )
    mode_group.add_argument(
        '--browser',
        dest='native',
        action='store_false',
        help='Run NiceGUI in browser/server mode.',
    )
    parser.set_defaults(native=True)
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='Host/interface to bind when starting the local NiceGUI server.',
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8080,
        help='Port for the local NiceGUI server.',
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    window_close_state = NativeWindowCloseState(enabled=args.native)

    if args.native and window_close_state.shared is not None:
        _install_native_activate_shim(window_close_state.shared)
    else:
        _restore_native_activate_shim()

    @ui.page('/')
    def index() -> None:
        # Build a fresh shell per client page so browser sessions do not share
        # mutable SessionState, while still reading the same persisted GUI store.
        store = load_gui_store()
        shell = AppShell(store, window_close_state=window_close_state)
        shell.build()

    try:
        ui.run(
            host=args.host,
            native=args.native,
            port=args.port,
            reload=False,
            title='Trade Dangerous',
            window_size=(1550, 1000),
        )
    finally:
        _restore_native_activate_shim()
        window_close_state.shutdown()
    return 0
