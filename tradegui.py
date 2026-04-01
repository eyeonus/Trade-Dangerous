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


# Keep one process-local handle to the packaged GUI runtime log so fallback
# stdout/stderr writes all land in the same file for the lifetime of the app.
_RUNTIME_LOG_STREAM = None


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


def _ensure_packaged_runtime_log_stream(runtime: dict[str, object]) -> None:
    global _RUNTIME_LOG_STREAM

    # Only packaged GUI mode should ever call this helper. It provides a
    # stable logfile for any fallback stdout/stderr writes when the frozen
    # executable runs with no attached console window.
    if _RUNTIME_LOG_STREAM is None or _RUNTIME_LOG_STREAM.closed:
        logs_dir = runtime.get("logs_dir")
        if logs_dir is None:
            base_dir = Path(os.environ.get("LOCALAPPDATA") or Path.home())
            logs_dir = base_dir / "TradeDangerous" / "logs"
        logs_path = Path(logs_dir)
        logs_path.mkdir(parents=True, exist_ok=True)
        log_path = logs_path / "tradegui.log"
        _RUNTIME_LOG_STREAM = log_path.open("a", encoding="utf-8", buffering=1)
        _RUNTIME_LOG_STREAM.write(
            f"\n[{datetime.now().isoformat()}] Trade Dangerous GUI startup\n"
        )
        _RUNTIME_LOG_STREAM.flush()

    # PyInstaller windowed mode may leave stdout/stderr as None. Point either
    # missing stream at the packaged runtime log so stray prints and rich
    # console writes do not crash the GUI startup path.
    if sys.stdout is None or getattr(sys.stdout, "closed", False):
        sys.stdout = _RUNTIME_LOG_STREAM
    if sys.stderr is None or getattr(sys.stderr, "closed", False):
        sys.stderr = _RUNTIME_LOG_STREAM


# This should only ever be called by packaged GUI, so safe to use direct windows call
# but we fall back to plain text anyway.
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
        # Packaged GUI launches without a terminal, so install the logfile-backed
        # fallback streams before importing and starting the NiceGUI app.
        _ensure_packaged_runtime_log_stream(runtime)
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
    import multiprocessing
    
    # We need this to make the application freeze nicely.
    multiprocessing.freeze_support()
    raise SystemExit(main())