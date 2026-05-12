"""Validation for the currently enabled trade run command shape."""

from __future__ import annotations

from .failures import (
    ContradictoryOptions,
    InvalidNumericOption,
    MissingRequiredInput,
    UnsupportedFirstSliceShape,
)
from .run_request import RunRequest


def validate_first_slice_request(request: RunRequest) -> None:
    """Reject requests outside the enabled one-hop station-pair shape."""

    _require_present(request.from_text, "--from")
    _require_present(request.to_text, "--to")
    _require_present(request.capacity_units, "--capacity")
    _require_present(request.starting_credits, "--credits")
    _require_present(request.max_ly_per_jump, "--ly-per")

    if request.hops != 1:
        raise UnsupportedFirstSliceShape(
            "Only --hops 1 is currently supported.",
            option_name="--hops",
        )

    unsupported = (
        ("--direct", request.direct),
        ("--towards", request.towards_text is not None),
        ("--loop", request.loop),
        ("--via", bool(request.via)),
        ("--avoid", bool(request.avoid)),
        ("--unique", request.unique),
        ("--loop-interval", request.loop_interval is not None),
        ("--shorten", request.shorten),
        ("--checklist", request.checklist),
        ("--x52-pro", request.x52_pro),
    )
    for option_name, active in unsupported:
        if active:
            raise UnsupportedFirstSliceShape(
                f"{option_name} is not supported for this planner slice.",
                option_name=option_name,
            )

    unsupported_non_zero = (
        ("--start-jumps", request.start_jumps),
        ("--end-jumps", request.end_jumps),
        ("--max-routes", request.max_routes),
        ("--prune-score", request.prune_score),
    )
    for option_name, value in unsupported_non_zero:
        if value:
            raise UnsupportedFirstSliceShape(
                f"{option_name} is not supported for this planner slice.",
                option_name=option_name,
            )

    if request.routes != 1:
        raise UnsupportedFirstSliceShape(
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

    if request.max_ly_per_jump is None or request.max_ly_per_jump <= 0:
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

    if request.no_planet and request.planetary_filter:
        raise ContradictoryOptions(
            "--no-planet cannot be combined with --planetary.",
            option_name="--no-planet",
        )


def _require_present(value: object, option_name: str) -> None:
    if value is None or value == "":
        raise MissingRequiredInput(
            f"Missing required option {option_name}.",
            option_name=option_name,
        )