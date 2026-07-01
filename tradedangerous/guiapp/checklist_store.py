"""Transient, in-memory store for detached-checklist payloads.

A detached checklist window is a separate NiceGUI client, so it cannot read the
shell's session state directly. The shell stashes the plain Run-snapshot routes
here under a short-lived token and opens the window at /run-checklist/<token>;
the page reads them back. Nothing here is persisted to tradegui_state.json.

The store is bounded (most-recent-N) so repeated opens cannot grow it without
limit; an evicted or unknown token simply reads back as None, which the page
turns into a friendly "no longer available" message.
"""

from __future__ import annotations

import uuid
from collections import OrderedDict
from typing import Any

# Keep only the most recent N payloads. A handful is plenty -- a checklist
# window is opened, read once on load, and then lives off its own client state.
_MAX_PAYLOADS = 16

_payloads: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()

def store_checklist(routes: list[dict[str, Any]]) -> str:
    """Stash route payloads and return a token for the checklist URL."""
    token = uuid.uuid4().hex
    _payloads[token] = routes
    _payloads.move_to_end(token)
    while len(_payloads) > _MAX_PAYLOADS:
        _payloads.popitem(last=False)
    return token

def get_checklist(token: str) -> list[dict[str, Any]] | None:
    """Return the stored route payloads for a token, or None if unknown."""
    return _payloads.get(token)
