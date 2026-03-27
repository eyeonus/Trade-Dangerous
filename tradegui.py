#!/usr/bin/env python3
# --------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
# Copyright (C) Bernd 'Gazelle' Gollesch 2016, 2017
# Copyright (C) Jonathan 'eyeonus' Jones 2018, 2019
# Copyright (C) Stefan 'Tromador' Morrell 2025,2026
#
# You are free to use, redistribute, or even print and eat a copy of
# this software so long as you include this copyright notice.
# I guarantee there is at least one bug neither of us knew about.
# --------------------------------------------------------------------
# TradeDangerous :: GUI App :: Main Module
#
# This is the main entry point into the native TD GUI.
# tkinter is a requirement to use the GUI.

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import platform
import sys
import traceback

from tradebootstrap import bootstrap_runtime


def _write_crash_log(runtime: dict[str, object]) -> Path:
    logs_dir = runtime.get("logs_dir")
    if logs_dir is None:
        base_dir = Path(os.environ.get("LOCALAPPDATA") or Path.home())
        logs_dir = base_dir / "TradeDangerous" / "logs"
    logs_path = Path(logs_dir)
    logs_path.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = logs_path / f"tradegui-crash-{stamp}.log"
    with log_path.open("w", encoding="utf-8") as fh:
        fh.write(f"timestamp: {datetime.now().isoformat()}\n")
        fh.write(f"python: {sys.version}\n")
        fh.write(f"platform: {platform.platform()}\n")
        fh.write(f"packaged_mode: {runtime.get('packaged_mode')}\n")
        fh.write(f"db_config: {runtime.get('db_config')}\n")
        fh.write(f"data_dir: {runtime.get('data_dir')}\n")
        fh.write(f"tmp_dir: {runtime.get('tmp_dir')}\n")
        fh.write("\n")
        fh.write(traceback.format_exc())
    return log_path


def _show_startup_error(log_path: Path) -> None:
    message = f"Trade Dangerous failed to start.\n\nCrash log: {log_path}"
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "Trade Dangerous startup error", 0x10)
    except Exception:
        print(message, file=sys.stderr)


def main(argv = None):
    runtime = bootstrap_runtime()
    if runtime.get("packaged_mode"):
        try:
            from tradedangerous.guiapp.main import main as gui_main

            return gui_main(argv)
        except Exception:
            log_path = _write_crash_log(runtime)
            _show_startup_error(log_path)
            return 1

    from tradedangerous.guiapp.main import main as gui_main

    return gui_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())