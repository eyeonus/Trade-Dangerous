"""Server-process bridge for asking the native shim to open helper windows.

The Open Checklist button runs in the NiceGUI server process; the pywebview
window lives in a separate process. main.py wires a request channel here during
native activation (set_checklist_window_channel); the button calls
request_checklist_window(), which puts a request on the channel for the window
process to pick up and turn into a real pywebview window.

This module deliberately holds no pywebview/NiceGUI imports so both shell.py and
main.py can use it without an import cycle. When the channel is unset (browser
mode, or native setup failed) request_checklist_window() returns False and the
caller falls back to the in-window dialog.
"""

from __future__ import annotations

from typing import Any

_checklist_queue: Any = None
_url_base: str = ''

def set_checklist_window_channel(queue: Any, url_base: str) -> None:
    """Register the request queue and URL base (called during native startup)."""
    global _checklist_queue, _url_base
    _checklist_queue = queue
    _url_base = url_base.rstrip('/')

def request_checklist_window(path: str, title: str = 'Run Checklist') -> bool:
    """Ask the native shim to open a window at ``path``.

    Returns True if the request was queued (native mode with a live channel),
    False otherwise so the caller can fall back to the dialog.
    """
    if _checklist_queue is None:
        return False
    try:
        url = f'{_url_base}/{path.lstrip("/")}'
        _checklist_queue.put({'url': url, 'title': title})
        return True
    except Exception:  # noqa: BLE001 - any channel failure must fall back
        return False
