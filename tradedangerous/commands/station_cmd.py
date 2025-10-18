# tradedangerous/commands/station_cmd.py — DEPRECATED (no-op)
# This command no longer edits station records directly.
#
# How to maintain station data going forward:
#   • Import authoritative data via:   trade import -P spansh  |  trade import -P eddblink
#   • Solo/offline players (manual capture via EDMC plugin):
#       TradeDangerous DB-Update for EDMC → https://github.com/bgol/UpdateTD
#
# To inspect a station’s data, use read-only commands like:
#   trade station <name>         ← (legacy pattern; now deprecated)
#   trade local --near "<system>"   (discoverability)
#   trade market --origin "<station>" (market view)

from __future__ import annotations
from .parsing import ParseArgument

# ---- Command metadata ----
help = "DEPRECATED: no longer used. See deprecation banner when run."
name = "station"
epilog = None
acceptUnknown = True

# No DB access is needed for this no-op command.
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
        "=== DEPRECATION NOTICE: station ====================================\n"
        "This command no longer edits station records and does not modify the DB.\n"
        "• Import station data via:    trade import -P eddblink | -P spansh\n"
        "• Solo/offline capture via EDMC plugin:\n"
        "    TradeDangerous DB-Update → https://github.com/bgol/UpdateTD\n"
        "=====================================================================\n"
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
