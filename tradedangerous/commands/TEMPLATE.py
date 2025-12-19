from __future__ import annotations
import typing

from .commandenv import ResultRow
from .parsing import ParseArgument  # import specific helpers as needed

from tradedangerous.formatting import RowFormat

if typing.TYPE_CHECKING:
    from tradedangerous import TradeDB, TradeORM, CommandEnv, CommandResults


######################################################################
# Parser config

help = 'Describe your command briefly here for the top-level --help.'
name = 'TEMPLATE'       # name of your .py file excluding the _cmd
epilog = None           # text to print at the bottom of --help

# Whether this command needs a TradeDB instance
wantsTradeDB = True
usesTradeData = False

# Parser wiring (keep tuples for consistency with loader)
arguments = (
    ParseArgument("name", help="Example positional(s).", type=str, nargs="*"),
)
switches = (
    ParseArgument("--flag", help="Example flag.", action="store_true", default=False),
)


# Runtime API


def run(
        results: CommandResults,
        cmdenv: CommandEnv,
        tdb: TradeDB | TradeORM | None,     # choose one
    ) -> CommandResults | bool | None:      # choose one
    """
    Implement code that validates arguments, collects and prepares
    any data you will need to generate your results for the user.
    
    If your command has finished and has no output to generate,
    return None, otherwise return "results" to be forwarded to
    the 'render' function.
    
    DO NOT print() during 'run', this allows run() functions to
    be re-used between modules and allows them to be used beyond
    the trade.py command line - e.g. someone writing a TD GUI
    will call run() and then render the results themselves.
    """
    
    ### TODO: Implement
    row = ResultRow(example="ok")
    results.rows.append(row)
    return results


def render(results: CommandResults, cmdenv: CommandEnv, tdb: TradeDB | TradeORM | None):
    """
    If run() returns a truthy value, the trade.py code will then
    call the corresponding render() function.
    
    This is where you should generate any output from your command.
    """
    fmt = RowFormat()
    fmt.addColumn("Example", "<", 10, key=lambda r: getattr(r, "example", ""))
    if not cmdenv.quiet:
        hdr, ul = fmt.heading()
        print(hdr, ul, sep="\n")
    for row in results.rows:
        print(fmt.format(row))
