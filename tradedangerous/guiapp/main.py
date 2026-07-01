"""CLI entrypoint for the Trade Dangerous NiceGUI shell."""

from __future__ import annotations

import _thread
import argparse
import multiprocessing
import os
from pathlib import Path
import socket
import signal
import sys
import time
from threading import Event, Thread
from typing import Any, Callable, Sequence

from nicegui import app, ui

from .profiles import (
    LAUNCHER_PORT_MAX,
    LAUNCHER_PORT_MIN,
    load_gui_store,
)
from .shell import AppShell, COMMAND_OPTIONS
from . import native_bridge

# Let the user select (and so manually copy) text in the native window. pywebview
# disables document text selection by default; NiceGUI forwards native window
# arguments through app.native.window_args. This is set at module import — not
# inside main() — so it also takes effect in the spawned native-window process,
# which re-imports this module and reads core.app.native.window_args when it
# creates the window (spawn does not inherit the parent's runtime state).
app.native.window_args['text_select'] = True

_ORIGINAL_NATIVE_ACTIVATE: Callable[..., None] | None = None
_NATIVE_WINDOW_CLOSE_SHARED_STATE: Any = None

def _shutdown_debug_note(stage: str, *, server: Any = None) -> None:
    return
# This was checking an intermittent fault that stopped happening the moment
# we started looking for it. Leaving the code here in case, but for now, just 
# dropping the function to a no-op.
#
#    parts = [f'[td-gui shutdown {time.strftime("%H:%M:%S")}]', stage]
#    if server is not None:
#        state = getattr(server, 'server_state', None)
#        if state is not None:
#            parts.append(f'connections={len(state.connections)}')
#            parts.append(f'tasks={len(state.tasks)}')
#        parts.append(f'should_exit={getattr(server, "should_exit", None)}')
#    print(' '.join(parts), file=sys.stderr, flush=True)


# NiceGUI native mode launches the pywebview window in a separate process.
# This manager-backed state is the narrow bridge that lets the server process
# publish "what is running now" so the native window can warn on close.
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
            try:
                # Native-mode shutdown can inject KeyboardInterrupt into the
                # main thread while the multiprocessing manager is finalizing.
                # Treat that as exit noise so packaged GUI shutdown stays clean.
                self._manager.shutdown()
            except KeyboardInterrupt:
                pass
            finally:
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


# Close confirmation has to live on the native pywebview window because this
# is the only veto-capable close hook NiceGUI/native mode exposes to us.
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


# This runs inside the native pywebview child process, not the main NiceGUI
# server process. The close handler must be bound here because `closing` is not
# exposed on NiceGUI's public native API.
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
    native_favicon: str | Path | None,
    shared_state: Any,
    checklist_queue: Any = None,
) -> None:
    from nicegui import core, helpers
    from nicegui.native import native_mode, window_icon
    
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
    
    if sys.platform == 'win32' and native_favicon is not None:
        def on_shown() -> None:
            window_icon.apply_icon(
                window.native.Handle.ToInt32(),
                title,
                str(native_favicon),
            )
            window.events.shown -= on_shown
        
        window.events.shown += on_shown
    
    native_mode._start_window_method_executor(
        window,
        method_queue,
        response_queue,
        closed,
    )

    # Detached helper windows (the Run checklist). The server process puts
    # {'url', 'title'} requests on checklist_queue; each becomes its own
    # pywebview window created here in the GUI process. They carry no close
    # veto -- closing one leaves the main window running. When the main window
    # closes we destroy any survivors so webview.start() can return and the
    # process exits cleanly.
    checklist_windows: list[Any] = []

    def _apply_checklist_window_icon(win: Any, win_title: str) -> None:
        # Give detached checklist windows the same Windows icon as the main
        # window. Best-effort: an icon failure must never break the window.
        try:
            window_icon.apply_icon(
                win.native.Handle.ToInt32(),
                win_title,
                str(native_favicon),
            )
        except Exception:
            pass

    def _serve_checklist_requests() -> None:
        while not closed.is_set():
            try:
                request = checklist_queue.get(timeout=0.2)
            except Exception:
                continue
            if not request:
                continue
            try:
                window_title = request.get('title', 'Run Checklist')
                extra = native_mode.webview.create_window(
                    window_title,
                    request.get('url'),
                    width=520,
                    height=720,
                )
                checklist_windows.append(extra)
                if sys.platform == 'win32' and native_favicon is not None:
                    extra.events.shown += (
                        lambda win=extra, title=window_title:
                        _apply_checklist_window_icon(win, title)
                    )
            except Exception:
                pass

    def _destroy_checklist_windows() -> None:
        for extra in list(checklist_windows):
            try:
                extra.destroy()
            except Exception:
                pass
        checklist_windows.clear()

    if checklist_queue is not None:
        window.events.closed += _destroy_checklist_windows
        Thread(target=_serve_checklist_requests, daemon=True).start()

    native_mode.webview.start(**core.app.native.start_args)

# This is a local shim around NiceGUI's native activation path. It exists only
# to thread our shared close-state into the spawned pywebview process without
# forking NiceGUI or redesigning the app around window-close behaviour.
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
    native_favicon: str | Path | None = None,
) -> None:
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
            native_favicon,
        )
        return
    
    from nicegui import core, optional_features
    from nicegui.logging import log
    from nicegui.native import native, native_mode
    from nicegui.server import Server
    
    def check_shutdown() -> None:
        while process.is_alive():
            time.sleep(0.1)
        
        server = getattr(Server, 'instance', None)
        _shutdown_debug_note('native window process exited', server=server)
        if shutdown_event is not None:
            shutdown_event.set()
            _shutdown_debug_note('reload shutdown event set', server=server)
        if server is not None:
            _shutdown_debug_note('setting server should_exit', server=server)
            server.should_exit = True
            _shutdown_debug_note('server should_exit set', server=server)
        
        next_log_at = time.monotonic() + 1.0
        while not core.app.is_stopped:
            if time.monotonic() >= next_log_at:
                _shutdown_debug_note('waiting for app stop', server=server)
                next_log_at = time.monotonic() + 1.0
            time.sleep(0.1)
        
        _shutdown_debug_note('app reported stopped', server=server)
        _thread.interrupt_main()
        native_mode.event_manager.stop()
        native.remove_queues()
        _shutdown_debug_note('native queues removed', server=server)
    
    if not optional_features.has('webview'):
        log.error(
            'Native mode is not supported in this configuration.\n'
            'Please run "pip install pywebview" to use it.'
        )
        sys.exit(1)
    
    multiprocessing.freeze_support()
    native.create_queues()
    native_mode.event_manager.start()
    # Channel for detached helper windows (the Run checklist). The server
    # process puts requests here; the spawned window process serves them.
    checklist_queue = multiprocessing.Queue()
    # Requests are fire-and-forget, so never let the queue's background feeder
    # thread block interpreter shutdown -- an unmanaged mp.Queue can otherwise
    # hang the process (and so the terminal) on exit, notably on Windows.
    checklist_queue.cancel_join_thread()
    native_bridge.set_checklist_window_channel(
        checklist_queue,
        f'{protocol}://{host}:{port}',
    )
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
        native_favicon,
        _NATIVE_WINDOW_CLOSE_SHARED_STATE,
        checklist_queue,
    )
    process = multiprocessing.Process(
        target=_open_window_with_close_handler,
        args=args,
        daemon=True,
    )
    process.start()
    
    Thread(target=check_shutdown, daemon=True).start()


# Swap in the close-aware native activation shim for the duration of this app
# launch only. Restoring the original entry point keeps the coupling explicit
# and easy to audit if NiceGUI changes upstream.
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


DEFAULT_LAUNCHER_PORT = 8542


def _parse_port_arg(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('Port must be a whole number.') from exc
    if port < LAUNCHER_PORT_MIN or port > LAUNCHER_PORT_MAX:
        raise argparse.ArgumentTypeError(
            f'Port must be between {LAUNCHER_PORT_MIN} and {LAUNCHER_PORT_MAX}.'
        )
    return port


def _port_bind_error(host: str, port: int) -> str | None:
    bind_host = host or '127.0.0.1'
    flags = socket.AI_PASSIVE if bind_host in {'0.0.0.0', '::'} else 0
    try:
        addrinfo = socket.getaddrinfo(
            bind_host,
            port,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
            flags=flags,
        )
    except socket.gaierror as exc:
        raise RuntimeError(
            f'Host/interface {bind_host!r} could not be resolved: {exc}'
        ) from exc

    last_error: OSError | None = None
    seen: set[tuple[int, Any]] = set()
    for family, socktype, proto, _, sockaddr in addrinfo:
        key = (family, sockaddr)
        if key in seen:
            continue
        seen.add(key)
        try:
            with socket.socket(family, socktype, proto) as sock:
                sock.bind(sockaddr)
        except OSError as exc:
            last_error = exc
            continue
        return None

    if last_error is None:
        return f'No bindable addresses were returned for host {bind_host!r}.'
    return str(last_error)


def _find_random_port(host: str) -> int:
    bind_host = host or '127.0.0.1'
    flags = socket.AI_PASSIVE if bind_host in {'0.0.0.0', '::'} else 0
    try:
        addrinfo = socket.getaddrinfo(
            bind_host,
            0,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
            flags=flags,
        )
    except socket.gaierror as exc:
        raise RuntimeError(
            f'Host/interface {bind_host!r} could not be resolved: {exc}'
        ) from exc

    last_error: OSError | None = None
    seen: set[tuple[int, Any]] = set()
    for family, socktype, proto, _, sockaddr in addrinfo:
        key = (family, sockaddr)
        if key in seen:
            continue
        seen.add(key)
        try:
            with socket.socket(family, socktype, proto) as sock:
                sock.bind(sockaddr)
                return int(sock.getsockname()[1])
        except OSError as exc:
            last_error = exc
            continue

    if last_error is None:
        raise RuntimeError(
            f'No bindable addresses were returned for host {bind_host!r}.'
        )
    raise RuntimeError(
        f'Trade Dangerous could not allocate a random GUI server port on '
        f'{bind_host!r}: {last_error}'
    )


def _resolve_server_port(
    *,
    host: str,
    cli_port: int | None,
    store: Any,
) -> int:
    if cli_port is not None:
        error = _port_bind_error(host, cli_port)
        if error is not None:
            raise RuntimeError(
                f'Trade Dangerous could not start on CLI port {cli_port}: '
                f'{error}'
            )
        return cli_port

    saved_port = getattr(store, 'launcher_port', None)
    if saved_port is not None:
        error = _port_bind_error(host, saved_port)
        if error is not None:
            raise RuntimeError(
                f'Trade Dangerous could not start on saved port '
                f'{saved_port}: {error}. Change it in Settings or override '
                f'it with --port.'
            )
        return saved_port

    if _port_bind_error(host, DEFAULT_LAUNCHER_PORT) is None:
        return DEFAULT_LAUNCHER_PORT
    return _find_random_port(host)


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
        type=_parse_port_arg,
        default=None,
        help=(
            'Port for the local NiceGUI server. Must be between 8000 and 8999; '
            'overrides the saved setting for this launch only. When omitted, '
            'Trade Dangerous tries 8542 first and then falls back to a random '
            'local port.'
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    startup_store = load_gui_store()
    resolved_port = _resolve_server_port(
        host=args.host,
        cli_port=args.port,
        store=startup_store,
    )
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

    favicon_path = Path(__file__).resolve().parents[2] / 'tradedangerouscrest.ico'
    favicon = str(favicon_path) if favicon_path.exists() else None
    
    try:
        ui.run(
            host=args.host,
            native=args.native,
            port=resolved_port,
            reload=False,
            title='Trade Dangerous',
            favicon=favicon,
            window_size=(1550, 1000),
        )
    finally:
        _restore_native_activate_shim()
        window_close_state.shutdown()
    return 0
