from __future__ import annotations

import argparse
from typing import Sequence

from nicegui import ui

from .profiles import load_gui_store
from .shell import AppShell


def build_arg_parser() -> argparse.ArgumentParser:
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

    @ui.page('/')
    def index() -> None:
        store = load_gui_store()
        shell = AppShell(store)
        shell.build()

    ui.run(
        host=args.host,
        native=args.native,
        port=args.port,
        reload=False,
        title='Trade Dangerous',
        window_size=(1500, 950),
    )
    return 0
