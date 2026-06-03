from __future__ import annotations
import sys

from .commandenv import Needs
from .exceptions import CommandLineError, PlannerResultError
from .parsing import (
    BlackMarketSwitch, FleetCarrierArgument, MutuallyExclusiveGroup,
    NoPlanetSwitch, SettlementArgument, ParseArgument,
    PlanetaryArgument,
)

from tradedangerous.planner.failures import (
    AmbiguousPlace,
    InvalidRunRequest,
    NoProfitableTrades,
    NoReachableRoute,
    PlannerFailure,
    StationHasNoUsablePriceData,
    UnknownPlace,
)
from tradedangerous.planner.render_text import render_run_result
from tradedangerous.planner.run_route import plan_route
from tradedangerous.planner.run_request import run_request_from_cmdenv
from tradedangerous.planner.run_result import RunResult
from tradedangerous.planner.validation import validate_run_request

######################################################################
# Parser config

help = 'Calculate best trade run.'
name = 'run'
epilog = None
usesTradeData = True
skipResolverPrechecks = True

# trade run is planner-only: it always needs the resolver database handle,
# never the legacy full-galaxy preload.
needs = Needs.RESOLVER

arguments = [
    ParseArgument('--capacity',
            help = 'Maximum capacity of cargo hold.',
            metavar = 'N',
            type = int,
        ),
    ParseArgument('--credits',
            help = 'Starting credits.',
            metavar = 'CR',
            type = "credits",
        ),
]


def _run_pad_size_threshold(value):
    """Parse trade run's --pad-size as a single ship-fit threshold.

    Unlike the shared multi-size pad filter, run takes one threshold letter —
    S, M or L — the smallest pad the ship can use; a station qualifies when its
    largest pad is at least that size. '?', empty input, or a combination like
    'SML' is rejected here at parse time so the planner only ever sees a valid
    threshold. (S and M still admit stations whose pad size is unrecorded; L
    does not — that inclusion is the filter's job, not the parser's.)
    """
    text = str(value).strip().upper()
    if text not in ("S", "M", "L"):
        raise CommandLineError(
            f"Invalid --pad-size '{value}': trade run takes a single "
            "pad-size threshold, one of 'S' (small), 'M' (medium) or 'L' "
            "(large). A station qualifies when its largest pad is at least "
            "that size."
        )
    return text


switches = [
    ParseArgument('--from', '-f',
        help = 'Starting system/station.',
        dest = 'starting',
        metavar = 'STATION',
    ),
    MutuallyExclusiveGroup(
        ParseArgument('--to', '-t',
            help = 'Final system/station.',
            dest = 'ending',
            metavar = 'PLACE',
            default = None,
        ),
        ParseArgument('--towards', '-T',
            help = (
                'Choose a route that continually reduces the '
                'distance towards this system.'
            ),
            dest = 'goalSystem',
            metavar = 'SYSTEM',
            default = None,
        ),
        ParseArgument('--loop',
            help = 'Return to the starting station.',
            action = 'store_true',
            default = False,
        ),
    ),
    ParseArgument('--via',
        help = 'Require specified systems/stations to be en-route.',
        action = 'append',
        metavar = 'PLACE[,PLACE,...]',
    ),
    ParseArgument('--avoid',
        help = 'Exclude an item, system or station from trading. '
                'Partial matches allowed, '
                'e.g. "dom.App" or "domap" matches "Dom. Appliances".',
        action = 'append',
    ),
    MutuallyExclusiveGroup(
        ParseArgument('--direct',
            help = "Assume destinations are reachable without worrying "
                "about jumps.",
            action = 'store_true',
        ),
        ParseArgument('--hops',
            help = 'Number of hops (station-to-station) to run.',
            default = 2,
            type = int,
            metavar = 'N',
        ),
    ),
    ParseArgument('--jumps-per',
        # Default deliberately None: the new planner keys the default off
        # --ly-per (see run_request._resolve_jumps_per_hop); the legacy --old
        # path restores its historical default of 1 at the top of its branch.
        # Leaving the parser default as None is what lets either path tell
        # "user omitted the flag" from "user explicitly passed --jumps-per 1".
        help = 'Maximum number of jumps (system-to-system) per hop.',
        default = None,
        dest = 'maxJumpsPer',
        metavar = 'N',
        type = int,
    ),
    ParseArgument('--ly-per',
        help = 'Maximum light years per jump.',
        dest = 'maxLyPer',
        metavar = 'N.NN',
        type = float,
    ),
    ParseArgument('--empty-ly',
        help = 'Maximum light years ship can jump when empty.',
        dest = 'emptyLyPer',
        metavar = 'N.NN',
        type = float,
        default = None,
    ),
    ParseArgument('--start-jumps', '-s',
        help = 'Consider stations within this many jumps of the origin '
             '(requires --from).',
        dest = 'startJumps',
        default = 0,
        type = int,
    ),
    ParseArgument('--end-jumps', '-e',
        help = 'Consider stations within this many jumps of the destination '
             '(requires --to).',
        dest = 'endJumps',
        default = 0,
        type = int,
    ),
    ParseArgument('--show-jumps', '-J',
        help = 'Show detail of jumps between hops.',
        dest = 'showJumps',
        action = 'store_true',
    ),
    ParseArgument('--limit',
        help = 'Maximum units of any one cargo item to buy (0: unlimited).',
        metavar = 'N',
        type = int,
    ),
    ParseArgument('--age', '--max-days-old', '-MD',
        help = 'Maximum age (in days) of trade data to use.',
        metavar = 'DAYS',
        type = float,
        dest = 'maxAge',
    ),
    ParseArgument('--pad-size', '-p',
        help = (
            'Restrict to stations whose largest landing pad is at least '
            'this size: S, M or L. Omit for no pad restriction.'
        ),
        metavar = 'S|M|L',
        dest = 'padSize',
        type = _run_pad_size_threshold,
    ),
    MutuallyExclusiveGroup(
        NoPlanetSwitch(),
        PlanetaryArgument(),
    ),
    FleetCarrierArgument(),
    SettlementArgument(),
    BlackMarketSwitch(),
    ParseArgument('--ls-penalty', '--lsp',
        help = "Penalty per 1kls stations are from their stars.",
        default = 12.5,
        type = float,
        dest = 'lsPenalty'
    ),
    ParseArgument('--ls-max',
        help = 'Only consider stations upto this many ls from their star.',
        metavar = 'LS',
        dest = 'maxLs',
        type = int,
        default = 0,
    ),
    ParseArgument('--gain-per-ton', '--gpt',
        help = 'Specify the minimum gain per ton of cargo',
        dest = 'minGainPerTon',
        type = "credits",
        default = 1
    ),
    ParseArgument('--max-gain-per-ton', '--mgpt',
        help = 'Specify the maximum gain per ton of cargo',
        dest = 'maxGainPerTon',
        type = "credits",
        default = 0
    ),
    ParseArgument('--max-price', '--mp',
        # Parser default is None so the new planner can distinguish
        # "omitted" (apply the configured default) from "explicit 0"
        # (disable the cap). The legacy --old branch maps None to 0
        # to keep its historical no-cap behaviour.
        help = (
            'Maximum commodity market price to use (cr/t). '
            'Default: 1,500,000. Use 0 to disable.'
        ),
        dest = 'maxPrice',
        type = "credits",
        default = None,
    ),
    ParseArgument('--unique',
        help = 'Only visit each station once.',
        action = 'store_true',
        default = False,
    ),
    ParseArgument('--loop-interval', '-li',
        help = (
            'Require this many hops between visits to the same station. '
            'A value of 1 would be the default behavior, so a value of '
            '2 is the minimum allowed.'
        ),
        type = int,
        default = None,
        dest = 'loopInt',
    ),
    ParseArgument('--margin',
        help = 'Reduce gains made on each hop to provide a margin of error '
                'for market fluctuations (e.g: 0.25 reduces gains by 1/4). '
                '0<: N<: 0.25.',
        default = 0.00,
        metavar = 'N.NN',
        type = float,
    ),
    ParseArgument('--insurance',
        help = 'Reserve at least this many credits to cover insurance.',
        default = 0,
        metavar = 'CR',
        type = "credits",
    ),
    ParseArgument('--routes',
        help = 'Maximum number of routes to show. DEFAULT: 1',
        default = 1,
        metavar = 'N',
        type = int,
    ),
    ParseArgument('--max-routes',
        help = 'At the end of each hop, limit the number of routes '
                'that continue to the next round to the top N '
                'highest scoring',
        default = 0,
        metavar = 'N',
        type = int,
        dest = 'maxRoutes',
    ),
    ParseArgument('--checklist',
        help = 'Provide a checklist flow for the route.',
        action = 'store_true',
        default = False,
    ),
    ParseArgument('--x52-pro',
        help = 'Enable experimental X52 Pro MFD output (requires --checklist).',
        action = 'store_true',
        default = False,
        dest = 'x52pro',
    ),
    ParseArgument('--prune-score',
        help = "From the 3rd hop on, only consider routes which have at least this percentage of the current best route's score.",
        dest = 'pruneScores',
        type = float,
        default = 0,
    ),
    ParseArgument('--prune-hops',
        help = 'Changes which hop --prune-score takes effect from.',
        default = 3,
        type = int,
        dest = 'pruneHops',
    ),
    ParseArgument('--progress', '-P',
        help = 'Show hop progress',
        default = False,
        action = 'store_true',
    ),
    ParseArgument('--supply',
        help = 'Only considers items which have at least this many units.',
        default = None,
        type = int,
    ),
    ParseArgument('--demand',
        help = 'Only considers items which have at least this much demand.',
        default = None,
        type = int
    ),
    ParseArgument('--summary',
        help = 'Summary layout of route instructions.',
        action = 'store_true',
    ),
    ParseArgument('--shorten',
        help = '(Requires --to) Find the shortest route with the best gpt.',
        action = 'store_true',
    ),
]


######################################################################
# Helpers

# Do some basic syntax validation before we waste time loading data.
def validateRunArgumentsFast(cmdenv):
    """
    Fast-fail argument checks that should run BEFORE any database
    access or route planning.
    """
    if cmdenv.capacity is None:
        raise CommandLineError("Missing '--capacity'")
    
    if cmdenv.credits is None:
        raise CommandLineError("Missing '--credits'")
    
    if cmdenv.maxLyPer is None and not cmdenv.direct:
        raise CommandLineError("Missing '--ly-per'")
    
    if getattr(cmdenv, 'x52pro', False) and not getattr(cmdenv, 'checklist', False):
        raise CommandLineError("--x52-pro requires --checklist")
    
    # --towards requires --from
    if cmdenv.goalSystem and not getattr(cmdenv, "starting", None):
        raise CommandLineError("--towards requires --from")
    
    # --start-jumps requires --from
    if cmdenv.startJumps and not getattr(cmdenv, "starting", None):
        raise CommandLineError("--start-jumps requires --from")
    
    # --end-jumps requires --to
    if cmdenv.endJumps and not getattr(cmdenv, "ending", None):
        raise CommandLineError("--end-jumps requires --to")
    
    # --shorten only valid with --to
    if cmdenv.shorten and not getattr(cmdenv, "ending", None):
        raise CommandLineError("--shorten only works with --to.")
    
    if cmdenv.loop and cmdenv.unique:
        raise CommandLineError("Cannot use --unique and --loop together")
    
    if cmdenv.loop and cmdenv.direct:
        raise CommandLineError("Cannot use --direct and --loop together")
    
    if (
        cmdenv.limit is not None
        and cmdenv.capacity is not None
        and cmdenv.limit > cmdenv.capacity
    ):
        raise CommandLineError("'limit' must be <= capacity")
    
    if cmdenv.insurance:
        arbitraryInsuranceBuffer = 42
        if cmdenv.insurance >= (cmdenv.credits + arbitraryInsuranceBuffer):
            raise CommandLineError("Insurance leaves no margin for trade")
    
    if cmdenv.loopInt is not None and cmdenv.loopInt < 2:
        raise CommandLineError(
            "--loop-int must be 2 or higher to have any effect. "
        )
    
    unsupported = (
        ("--direct", getattr(cmdenv, "direct", False)),
        ("--towards", getattr(cmdenv, "goalSystem", None) is not None),
        ("--loop", getattr(cmdenv, "loop", False)),
        ("--via", bool(getattr(cmdenv, "via", None))),
        ("--avoid", bool(getattr(cmdenv, "avoid", None))),
        ("--unique", getattr(cmdenv, "unique", False)),
        ("--loop-interval", getattr(cmdenv, "loopInt", None) is not None),
        ("--shorten", getattr(cmdenv, "shorten", False)),
        ("--checklist", getattr(cmdenv, "checklist", False)),
        ("--x52-pro", getattr(cmdenv, "x52pro", False)),
    )
    for option_name, active in unsupported:
        if active:
            raise CommandLineError(
                f"{option_name} is not supported for this planner slice."
            )
    
    unsupported_non_zero = (
        ("--start-jumps", getattr(cmdenv, "startJumps", 0)),
        ("--end-jumps", getattr(cmdenv, "endJumps", 0)),
        ("--max-routes", getattr(cmdenv, "maxRoutes", 0)),
        ("--prune-score", getattr(cmdenv, "pruneScores", 0)),
    )
    for option_name, value in unsupported_non_zero:
        if value:
            raise CommandLineError(
                f"{option_name} is not supported for this planner slice."
            )

    # --prune-hops defaults to 3 at the parser; reject only non-default
    # values since the pruning controls remain deferred.
    if getattr(cmdenv, "pruneHops", 3) != 3:
        raise CommandLineError(
            "--prune-hops is not supported for this planner slice."
        )

    if getattr(cmdenv, "routes", 1) != 1:
        raise CommandLineError(
            "Only --routes 1 is currently supported."
        )

    margin = getattr(cmdenv, "margin", 0.0) or 0.0
    if margin < 0 or margin > 1:
        raise CommandLineError("--margin must be between 0 and 1.")


######################################################################
# Perform query and populate result set


def _is_unanchored_request(request) -> bool:
    """Return whether neither endpoint was named — the unanchored search."""

    return not request.from_text and not request.to_text


def _planner_result_message(exc, request) -> str:
    """Build the user-facing message for a planner failure that has no result.

    The new planner knows enough about the search shape to say what actually
    happened, so the legacy 'possible causes' footer (which advises checking
    for missing systems or stale prices) is misleading here. The wording
    follows the failure spec: it names the endpoints the user typed where
    they typed them, talks about 'jump settings' rather than internal terms,
    and only recommends --jumps-per where increasing it is genuinely the
    likely fix.

    StationHasNoUsablePriceData (and its subclasses) carry their own
    specific message from the planner — they describe a different kind of
    failure (a named station has no usable data) — and are surfaced as-is.
    """

    if isinstance(exc, StationHasNoUsablePriceData):
        return exc.message

    from_named = bool(request.from_text)
    to_named = bool(request.to_text)

    if (
        isinstance(exc, NoReachableRoute)
        and from_named
        and to_named
    ):
        # Fixed endpoints, but the jump settings cannot connect them.
        return (
            f"No route was found from {request.from_text} to "
            f"{request.to_text} with the current jump settings.\n"
            f"\n"
            f"Try increasing --jumps-per or choosing a closer start or "
            f"destination."
        )

    if from_named and to_named:
        # Fixed endpoints are connectable, but no profitable trade exists.
        return (
            f"No profitable trade was found from {request.from_text} to "
            f"{request.to_text} with the current jump settings.\n"
            f"\n"
            f"Try relaxing filters or choosing a different start or "
            f"destination."
        )

    if from_named:
        return (
            f"No profitable trade was found from {request.from_text} with "
            f"the current jump settings.\n"
            f"\n"
            f"Try increasing --jumps-per, choosing a different starting "
            f"point, or relaxing filters."
        )

    if to_named:
        return (
            f"No profitable trade was found to {request.to_text} with the "
            f"current jump settings.\n"
            f"\n"
            f"Try increasing --jumps-per, choosing a different destination, "
            f"or relaxing filters."
        )

    # Unanchored: neither endpoint named.
    return (
        "No profitable trade was found with the current jump settings.\n"
        "\n"
        "Try increasing --jumps-per or relaxing filters."
    )


def _abort_unanchored_run(results, message):
    """Print a message and return an empty result set: a clean no-op exit.

    A declined confirmation prompt and a non-interactive invocation both end
    the command here, before the planner is ever called — a plain message and
    no traceback, with nothing for the renderer to show.
    """

    print(message, flush=True)
    results.summary.exception = ""
    results.data = ()
    return results


def run(results, cmdenv, tdb):
    request = run_request_from_cmdenv(cmdenv)
    session = getattr(tdb, "session", None)
    if session is None:
        raise CommandLineError("Resolver database session is not available.")

    try:
        # Validate before the unanchored confirmation prompt. A request
        # that cannot run must fail immediately with its error, not after
        # a confirmation the planner would only then refuse — far likelier
        # the user simply mistyped the command. plan_route re-validates
        # as its own input contract; the repeat is cheap.
        validate_run_request(request)

        # Both endpoints omitted: the galaxy-wide search. It is markedly
        # slower than a search that names either endpoint, so it runs
        # only behind an interactive confirmation; with no TTY it cannot
        # prompt and aborts cleanly with guidance. The planner stays
        # non-interactive.
        if _is_unanchored_request(request):
            if not sys.stdin.isatty():
                return _abort_unanchored_run(
                    results,
                    "Without --from or --to, Trade Dangerous searches the "
                    "whole galaxy\n"
                    "for the best trades, which could take several "
                    "minutes.\n"
                    "It needs you to confirm first, but there's no "
                    "interactive terminal here.\n"
                    "Re-run in a terminal, or name a starting system with "
                    "--from and/or a\n"
                    "destination with --to.",
                )
            print(
                "Without --from or --to, Trade Dangerous will search the "
                "whole galaxy\n"
                "for the best trades. This can be much slower than "
                "naming either endpoint,\n"
                "and could take several minutes.\n"
                "\n"
                "To speed up the search:\n"
                "  - Name a starting system with --from, a destination "
                "with --to, or both.\n"
                "  - Use filters such as --age <days>, --pad-size, "
                "--planetary, --fc N.",
                flush=True,
            )
            if input("Continue? [y/N] ").strip().lower() not in ("y", "yes"):
                return _abort_unanchored_run(results, "Search cancelled.")

        results.data = plan_route(session, request)
        results.summary.exception = ""
    except (
        NoProfitableTrades,
        NoReachableRoute,
        StationHasNoUsablePriceData,
    ) as exc:
        # The new planner has the context to say what actually
        # happened; do not wrap in NoDataError's generic 'possible
        # causes' footer, which is wrong for these failures.
        raise PlannerResultError(
            _planner_result_message(exc, request)
        ) from exc
    except (AmbiguousPlace, InvalidRunRequest, UnknownPlace) as exc:
        raise CommandLineError(exc.message) from exc
    except PlannerFailure as exc:
        raise CommandLineError(exc.message) from exc

    return results


######################################################################
# Transform result set into output


def render(results, cmdenv, tdb):
    # The planner always returns a RunResult, and the new renderer owns the
    # whole route presentation. A cancelled or non-interactive unanchored
    # run leaves results.data empty — its guidance was already printed — so
    # there is nothing further to show.
    if isinstance(results.data, RunResult):
        cmdenv.console.print(render_run_result(results.data), highlight=False)
