from __future__ import annotations
import dataclasses
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
    NoTowardsProgress,
    PlannerFailure,
    StationHasNoUsablePriceData,
    UnknownPlace,
)
from tradedangerous.planner import resolver
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
# Perform query and populate result set


def _is_unanchored_request(request) -> bool:
    """Return whether neither endpoint was named — the unanchored search."""

    return not request.from_text and not request.to_text


def _endpoint_display(endpoint, fallback_text):
    """Friendly name for a resolved endpoint in failure messages.

    Prefers the resolved canonical name — System/Station for a station, System
    for a system — so the error reads in full even when the commander typed a
    partial. Falls back to the raw input text if resolution is somehow absent.
    """

    if endpoint is None:
        return fallback_text
    if endpoint.station is not None:
        return endpoint.station.dbname
    if endpoint.system is not None:
        return endpoint.system.name
    return fallback_text


def _planner_result_message(exc, request) -> str:
    """Build the user-facing message for a planner failure that has no result.

    The new planner knows enough about the search shape to say what actually
    happened, so the legacy 'possible causes' footer (which advises checking
    for missing systems or stale prices) is misleading here. The wording
    follows the failure spec: it names the resolved endpoints in full (a
    partial name reads back as the real station/system), talks about 'jump
    settings' rather than internal terms, and only recommends --jumps-per
    where increasing it is genuinely the likely fix.

    StationHasNoUsablePriceData (and its subclasses) carry their own
    specific message from the planner — they describe a different kind of
    failure (a named station has no usable data) — and are surfaced as-is.
    """

    if isinstance(exc, StationHasNoUsablePriceData):
        return exc.message

    if isinstance(exc, NoTowardsProgress):
        # --towards: the search found no profitable trade that moved the route
        # closer to the target. The failure already names the target; add the
        # levers that let a progressing trade through. Checked before the
        # NoReachableRoute branch below because that one only fires with --to,
        # which --towards forbids.
        return (
            f"{exc.message}\n"
            f"\n"
            f"Try increasing --hops or --jumps-per, widening --ly-per, or "
            f"relaxing filters so a trade toward the target can be found."
        )

    from_named = bool(request.from_text)
    to_named = bool(request.to_text)
    from_label = _endpoint_display(request.from_endpoint, request.from_text)
    to_label = _endpoint_display(request.to_endpoint, request.to_text)

    if (
        isinstance(exc, NoReachableRoute)
        and from_named
        and to_named
    ):
        # Fixed endpoints, but the jump settings cannot connect them.
        return (
            f"No route was found from {from_label} to "
            f"{to_label} with the current jump settings.\n"
            f"\n"
            f"Try increasing --jumps-per or choosing a closer start or "
            f"destination."
        )

    if from_named and to_named:
        # Fixed endpoints are connectable, but no profitable trade exists.
        return (
            f"No profitable trade was found from {from_label} to "
            f"{to_label} with the current jump settings.\n"
            f"\n"
            f"Try relaxing filters or choosing a different start or "
            f"destination."
        )

    if from_named:
        return (
            f"No profitable trade was found from {from_label} with "
            f"the current jump settings.\n"
            f"\n"
            f"Try increasing --jumps-per, choosing a different starting "
            f"point, or relaxing filters."
        )

    if to_named:
        return (
            f"No profitable trade was found to {to_label} with the "
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


def _resolve_named_endpoint(tdb, text, option_name):
    """Resolve one endpoint name if supplied, echoing an approximate match.

    Returns the ResolvedEndpoint, or None when no name was given for this
    option. An unknown name is reported as a clean CommandLineError; an
    ambiguous name or a bad @N index propagates as the lookup's own message
    (the @N candidate list), which the CLI prints verbatim.
    """

    if not text:
        return None
    try:
        endpoint = resolver.resolve_endpoint(tdb, text, option_name=option_name)
    except UnknownPlace as exc:
        raise CommandLineError(exc.message) from exc
    if endpoint.approximate:
        canonical = (
            endpoint.station.dbname if endpoint.station is not None
            else endpoint.system.name
        )
        print(f"{option_name} {text} resolved as {canonical}", flush=True)
    return endpoint


def _resolve_request_endpoints(request, tdb):
    """Resolve --from / --to / --towards once and carry the results on the request.

    Resolution happens here at dispatch so the planner shapes work from
    canonical resolved endpoints and never see the TradeORM handle. --towards
    collapses to its system, matching the progress metric's system-to-system
    distance.
    """

    updates = {}

    from_endpoint = _resolve_named_endpoint(tdb, request.from_text, "--from")
    if from_endpoint is not None:
        updates["from_endpoint"] = from_endpoint

    to_endpoint = _resolve_named_endpoint(tdb, request.to_text, "--to")
    if to_endpoint is not None:
        updates["to_endpoint"] = to_endpoint

    if request.towards_text:
        towards_endpoint = _resolve_named_endpoint(
            tdb, request.towards_text, "--towards",
        )
        target = resolver.system_for_endpoint(towards_endpoint)
        if target is None:
            raise CommandLineError(
                "--towards could not resolve to a system: "
                f"{request.towards_text}"
            )
        updates["towards_target"] = target

    if request.avoid:
        # Resolve every --avoid token once here, into the three id sets the
        # planner consumes. An unresolvable token is a clean CommandLineError;
        # an ambiguous name or bad @N propagates as the lookup's own message
        # (its candidate / @N list), which the CLI prints verbatim.
        try:
            resolved_avoid = resolver.resolve_avoid_tokens(tdb, request.avoid)
        except UnknownPlace as exc:
            raise CommandLineError(exc.message) from exc
        updates["avoid_system_ids"] = resolved_avoid.system_ids
        updates["avoid_station_ids"] = resolved_avoid.station_ids
        updates["avoid_item_ids"] = resolved_avoid.item_ids
        for token, canonical in resolved_avoid.echoes:
            print(f"--avoid {token} resolved as {canonical}", flush=True)

    if not updates:
        return request
    return dataclasses.replace(request, **updates)


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

        # Resolve the named endpoints once here, at dispatch, via the shared
        # TradeORM lookup. The planner then consumes the resolved DTOs and never
        # touches the database handle for name resolution.
        request = _resolve_request_endpoints(request, tdb)

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
