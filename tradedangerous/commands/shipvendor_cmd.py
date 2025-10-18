# tradedangerous/commands/shipvendor_cmd.py — DEPRECATED (no-op)
# This command no longer maintains ship lists directly.
# Guidance:
#   • Import authoritative data via:   trade import -P spansh  |  trade import -P eddblink
#   • Search for ships via:            trade buy --near "<place>" --ly N "<ship>"

from __future__ import annotations
from .parsing import ParseArgument  # to swallow arbitrary positional args

# ---- Command metadata ----
help = "DEPRECATED: no longer used. See deprecation banner when run."
name = "shipvendor"
epilog = None
acceptUnknown = True

# No DB access needed.
wantsTradeDB = False
usesTradeData = False

# Accept ANY number of positional args and ignore them (prevents parser errors).
arguments = (
    ParseArgument(
        'args',
        help="(deprecated) ignored",
        nargs='*',
        type=str,
    ),
)
# No switches; unknown switches will still be rejected by the global parser.
switches = tuple()


def _banner() -> str:
    return (
        "\n"
        "=== DEPRECATION NOTICE: shipvendor ==================================\n"
        "This command is no longer used and does not modify the database.\n"
        "• Import authoritative data with:  trade import -P eddblink | -P spansh\n"
        "• Search for ships using:         trade buy --near \"<place>\" --ly N \"<ship>\"\n"
        "======================================================================\n"
    )


def run(results, cmdenv, tdb=None):
    """
    No-op implementation: print banner and exit immediately.
    All arguments/switches are ignored by design.
    """
    banner = _banner()
    try:
        cmdenv.NOTE("{}", banner)
    except Exception:
        print(banner)
    return None


def render(results, cmdenv, tdb=None):
    # No output beyond the banner emitted in run().
    return
