"""Validation for the currently enabled trade run command shape."""

from __future__ import annotations

from .failures import (
    ContradictoryOptions,
    InvalidNumericOption,
    InvalidRunRequest,
    MissingRequiredInput,
    UnsupportedRunShape,
)
from .run_request import RunRequest


# Upper bound on --hops. The spec mandates "an excessive hop count beyond the
# supported search policy" must reject; 25 covers any realistic trader plan
# while keeping the worst-case frontier expansion bounded.
_MULTIHOP_MAX_HOPS = 25


def validate_run_request(request: RunRequest) -> None:
    """Reject requests outside the currently enabled planner shape."""

    _require_present(request.capacity_units, "--capacity")
    _require_present(request.starting_credits, "--credits")
    if not request.direct:
        # --direct discards the jump model entirely, so --ly-per is moot under
        # it and not required. Every other shape needs it.
        _require_present(request.max_ly_per_jump, "--ly-per")

    if request.hops < 1:
        raise InvalidNumericOption(
            "--hops must be at least 1.",
            option_name="--hops",
        )

    if request.hops > _MULTIHOP_MAX_HOPS:
        raise InvalidNumericOption(
            "--hops exceeds the supported maximum.",
            option_name="--hops",
        )

    # --direct is a single direct hop between two named endpoints: the best
    # trade from --from to --to, with the jump route left to the commander. It
    # needs both ends anchored, and it throws away the reachability model, so the
    # options that shape multi-hop routing or empty-jump positioning have nothing
    # to act on and are rejected outright rather than silently ignored. We do not
    # guess which of two contradictory flags the commander meant. Options that
    # --direct merely makes moot (--ly-per, --jumps-per) are tolerated, so a
    # standard paste-in block is not punished for an irrelevant flag.
    if request.direct:
        if request.loop:
            # Not covered by the parser's exclusion groups (--loop sits with
            # --to/--towards, --direct with --hops), so the contradiction is
            # rejected here with a message that names the real conflict.
            raise ContradictoryOptions(
                "--direct cannot be combined with --loop.",
                option_name="--direct",
            )
        if not request.from_text or not request.to_text:
            raise MissingRequiredInput(
                "--direct needs both --from and --to.",
                option_name="--direct",
            )
        if request.towards_text:
            raise ContradictoryOptions(
                "--direct cannot be combined with --towards.",
                option_name="--direct",
            )
        if request.start_jumps or request.end_jumps:
            raise ContradictoryOptions(
                "--direct cannot be combined with --start-jumps or "
                "--end-jumps.",
                option_name="--direct",
            )
        if request.via:
            # A chosen scope restriction for this slice, not a logical
            # impossibility: a direct hop's own origin or destination could in
            # principle satisfy a via. It is deferred because --direct throws
            # away the reachability model the via search is built on — so it
            # reads as an unsupported shape, not a contradiction.
            raise UnsupportedRunShape(
                "--direct cannot be combined with --via.",
                option_name="--direct",
            )

    # Steering and positioning options each need a companion endpoint to act
    # on. --towards steers an open route toward a target, so it needs a fixed
    # start (--from). --start-jumps / --end-jumps expand the eligible endpoints
    # outward from an anchor system, so each needs the anchor it expands from.
    # (--towards combined with --to is rejected at the parser, so it is not
    # repeated here.)
    if request.towards_text and not request.from_text:
        raise MissingRequiredInput(
            "--towards requires --from.",
            option_name="--towards",
        )

    # --loop closes the route back on its own starting station. (--loop with
    # --to or --towards is rejected at the parser's mutually-exclusive group.)
    if request.loop:
        # --loop requires a named --from. The galaxy-wide loop (--from
        # omitted) was investigated and is not supported: seeding the search
        # faithfully within the fixed beam width was not achievable at
        # acceptable cost. See docs/Planner/unanchored_loop_investigation.md.
        if not request.from_text:
            raise UnsupportedRunShape(
                "--loop requires --from; name a starting station or system.",
                option_name="--loop",
            )
        # A 1-hop loop would buy and sell at the same counter. --hops
        # defaults to 2, so this only fires on an explicit --hops 1.
        if request.hops < 2:
            raise InvalidNumericOption(
                "--loop needs --hops of at least 2.",
                option_name="--loop",
            )
        # --start-jumps would reposition the commander to a better trade
        # origin near the anchor before looping. But the loop's terminal set
        # is the anchor's own stations, so a repositioned origin outside the
        # anchor system can never close its loop and is silently dropped --
        # the positioning expansion is cancelled, not honoured. Gate the pair
        # until a positioning-aware loop terminal (close on the repositioned
        # origin, show the empty leg) is built. (--end-jumps needs --to, which
        # --loop forbids, so only --start-jumps is reachable here.)
        if request.start_jumps:
            raise UnsupportedRunShape(
                "--loop with --start-jumps is not supported yet; the "
                "repositioned origin cannot close its loop.",
                option_name="--loop",
            )

    # --unique and --loop-interval are one no-revisit constraint at two
    # strengths, so their validation lives together:
    #  - --loop returns the route to its own start, which is a revisit, so it
    #    cannot be combined with --unique (a spec early failure).
    #  - --unique forbids every revisit, so a supplied --loop-interval would be
    #    inert under it; reject rather than silently drop the user's interval.
    #  - --loop-interval 1 is the default "every hop" behaviour, so 2 is the
    #    minimum the spec allows.
    # --loop *with* --loop-interval is deliberately allowed: a minimum gap
    # before the route returns to its start. Whether the hop count can satisfy
    # the gap surfaces later as a no-route failure, not here.
    if request.loop and request.unique:
        raise ContradictoryOptions(
            "--loop cannot be combined with --unique: a loop returns to its "
            "starting station, which --unique forbids.",
            option_name="--unique",
        )

    if request.unique and request.loop_interval is not None:
        raise ContradictoryOptions(
            "--unique already forbids all station revisits; do not combine "
            "it with --loop-interval.",
            option_name="--unique",
        )

    if request.loop_interval is not None and request.loop_interval < 2:
        raise InvalidNumericOption(
            "--loop-interval must be at least 2; 1 is the default behaviour.",
            option_name="--loop-interval",
        )

    if request.start_jumps and not request.from_text:
        raise MissingRequiredInput(
            "--start-jumps requires --from.",
            option_name="--start-jumps",
        )

    if request.end_jumps and not request.to_text:
        raise MissingRequiredInput(
            "--end-jumps requires --to.",
            option_name="--end-jumps",
        )

    # --via routes through one or more named waypoints. It needs at least one
    # anchored endpoint to hang the search on: --from, --to, or both (--loop
    # supplies its own --from). The no-anchor case is rejected — with both ends
    # free it is unbounded the way the unanchored loop was, and redundant
    # besides: the cheapest way to "include" a place is to start or finish
    # there, so it asks for nothing a plain --from / --to would not.
    if request.via and not request.from_text and not request.to_text:
        raise MissingRequiredInput(
            "--via requires --from or --to; a via cannot anchor a route "
            "by itself.",
            option_name="--via",
        )

    # --via and --towards are two steering constraints at once: --towards drives
    # every hop strictly closer to a target, --via forces the route through named
    # waypoints (which a via may sit sideways or temporarily outward of). Serving
    # both needs a deliberate joint search policy, so the combination is deferred
    # this slice rather than guessed at. (--towards needs --from and excludes
    # --to, both handled above / at the parser.)
    if request.via and request.towards_text:
        raise UnsupportedRunShape(
            "--via cannot be combined with --towards: steering toward a target "
            "and routing through waypoints together need a joint search policy "
            "that is not yet built.",
            option_name="--via",
        )

    unsupported = (
        ("--checklist", request.checklist),
        ("--x52-pro", request.x52_pro),
    )
    for option_name, active in unsupported:
        if active:
            raise UnsupportedRunShape(
                f"{option_name} is not supported for this planner slice.",
                option_name=option_name,
            )

    unsupported_non_zero = (
        ("--max-routes", request.max_routes),
        ("--prune-score", request.prune_score),
    )
    for option_name, value in unsupported_non_zero:
        if value:
            raise UnsupportedRunShape(
                f"{option_name} is not supported for this planner slice.",
                option_name=option_name,
            )

    # --prune-hops defaults to 3 at the parser; reject only non-default values
    # since the pruning controls remain deferred to a later slice.
    if request.prune_hops != 3:
        raise UnsupportedRunShape(
            "--prune-hops is not supported for this planner slice.",
            option_name="--prune-hops",
        )

    if request.routes != 1:
        raise UnsupportedRunShape(
            "Only --routes 1 is currently supported.",
            option_name="--routes",
        )

    if request.capacity_units is None or request.capacity_units <= 0:
        raise InvalidNumericOption(
            "--capacity must be greater than zero.",
            option_name="--capacity",
        )

    if request.starting_credits is None or request.starting_credits < 0:
        raise InvalidNumericOption(
            "--credits must not be negative.",
            option_name="--credits",
        )

    if request.insurance_reserve < 0:
        raise InvalidNumericOption(
            "--insurance must not be negative.",
            option_name="--insurance",
        )

    if request.starting_credits is not None and (
        request.insurance_reserve >= request.starting_credits
    ):
        raise InvalidNumericOption(
            "--insurance must leave credits available for trading.",
            option_name="--insurance",
        )

    # --margin is a fraction of accumulated profit the planner will not trust as
    # buying power for later hops. Negative margins would invent capital; values
    # above 1 would shrink the budget below the base trade budget.
    if request.margin < 0 or request.margin > 1:
        raise InvalidNumericOption(
            "--margin must be between 0 and 1.",
            option_name="--margin",
        )

    if request.cargo_limit_per_item < 0:
        raise InvalidNumericOption(
            "--limit must not be negative.",
            option_name="--limit",
        )

    if request.cargo_limit_per_item > request.capacity_units:
        raise InvalidNumericOption(
            "--limit must be less than or equal to --capacity.",
            option_name="--limit",
        )

    if request.max_jumps_per_hop is None or request.max_jumps_per_hop < 0:
        raise InvalidNumericOption(
            "--jumps-per must not be negative.",
            option_name="--jumps-per",
        )

    if not request.direct and (
        request.max_ly_per_jump is None or request.max_ly_per_jump <= 0
    ):
        raise InvalidNumericOption(
            "--ly-per must be greater than zero.",
            option_name="--ly-per",
        )

    if request.min_supply is not None and request.min_supply < 0:
        raise InvalidNumericOption(
            "--supply must not be negative.",
            option_name="--supply",
        )

    if request.min_demand is not None and request.min_demand < 0:
        raise InvalidNumericOption(
            "--demand must not be negative.",
            option_name="--demand",
        )

    if request.min_gain_per_ton < 0:
        raise InvalidNumericOption(
            "--gain-per-ton must not be negative.",
            option_name="--gain-per-ton",
        )

    if request.max_gain_per_ton < 0:
        raise InvalidNumericOption(
            "--max-gain-per-ton must not be negative.",
            option_name="--max-gain-per-ton",
        )

    if (
        request.max_gain_per_ton > 0
        and request.max_gain_per_ton < request.min_gain_per_ton
    ):
        raise InvalidNumericOption(
            "--max-gain-per-ton must be greater than or equal to --gain-per-ton.",
            option_name="--max-gain-per-ton",
        )

    # --max-price is the absolute commodity-price cap. Zero is allowed and
    # means "disable the cap"; negative values are rejected.
    if request.max_price < 0:
        raise InvalidNumericOption(
            "--max-price must not be negative.",
            option_name="--max-price",
        )

    if request.no_planet and request.planetary_filter:
        raise ContradictoryOptions(
            "--no-planet cannot be combined with --planetary.",
            option_name="--no-planet",
        )

    # --pad-size is a single ship-fit threshold: the pad size the ship needs.
    # ?, multi-letter values, and anything that is not S, M, or L are rejected.
    if request.pad_size is not None and request.pad_size not in ("S", "M", "L"):
        raise InvalidRunRequest(
            "--pad-size must be one of S, M, or L.",
            option_name="--pad-size",
        )


def _require_present(value: object, option_name: str) -> None:
    if value is None or value == "":
        raise MissingRequiredInput(
            f"Missing required option {option_name}.",
            option_name=option_name,
        )