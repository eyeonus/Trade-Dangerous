"""Neutral request DTOs for trade run planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .run_result import ResolvedSystem


# Default cap on absolute commodity prices for trade run. Preserves observed
# legitimate non-carrier high-margin trades while removing obvious multi-
# million carrier-fiction rows. --max-price 0 disables the filter entirely.
DEFAULT_MAX_PRICE = 1_500_000


@dataclass(frozen=True, slots=True)
class RunRequest:
    """Parsed trade run inputs, independent of command-layer objects."""

    capacity_units: int | None = None
    starting_credits: int | None = None
    insurance_reserve: int = 0
    cargo_limit_per_item: int = 0
    margin: float = 0.0
    from_text: str | None = None
    to_text: str | None = None
    hops: int = 1
    max_jumps_per_hop: int | None = None
    max_ly_per_jump: float | None = None
    age_days: float | None = None
    min_gain_per_ton: int = 1
    max_gain_per_ton: int = 0
    max_price: int = DEFAULT_MAX_PRICE
    min_supply: int | None = None
    min_demand: int | None = None
    pad_size: str | None = None
    planetary_filter: tuple[str, ...] = ()
    no_planet: bool = False
    fleet_carrier_filter: tuple[str, ...] = ()
    settlement_filter: tuple[str, ...] = ()
    black_market_filter: tuple[str, ...] = ()
    max_ls: int = 0
    ls_penalty_percent: float = 0.0
    show_jumps: bool = False
    summary: bool = False
    progress: bool = False
    detail: int = 0
    debug: bool = False
    direct: bool = False
    start_jumps: int = 0
    end_jumps: int = 0
    empty_ly_per: float | None = None
    towards_text: str | None = None
    # Resolved --towards target system (id + coordinates). Filled once at
    # dispatch from towards_text; stays None for every shape that does not use
    # --towards. Carried as canonical state so the open-destination fetch can
    # apply the per-hop progress constraint in one shared place.
    towards_target: ResolvedSystem | None = None
    loop: bool = False
    via: tuple[str, ...] = ()
    avoid: tuple[str, ...] = ()
    unique: bool = False
    loop_interval: int | None = None
    shorten: bool = False
    routes: int = 1
    checklist: bool = False
    x52_pro: bool = False
    max_routes: int = 0
    prune_score: float = 0.0
    prune_hops: int = 3


def run_request_from_cmdenv(cmdenv: object) -> RunRequest:
    """Build a neutral request from the parsed command environment."""

    # --direct is a single direct hop by definition; the parser makes it
    # mutually exclusive with --hops, so resolve the canonical hop count to 1
    # here rather than letting the --hops default flow through to dispatch.
    direct = getattr(cmdenv, "direct", False)

    return RunRequest(
        capacity_units=getattr(cmdenv, "capacity", None),
        starting_credits=getattr(cmdenv, "credits", None),
        insurance_reserve=getattr(cmdenv, "insurance", 0) or 0,
        cargo_limit_per_item=getattr(cmdenv, "limit", None) or 0,
        margin=getattr(cmdenv, "margin", 0.0) or 0.0,
        from_text=getattr(cmdenv, "starting", None),
        to_text=getattr(cmdenv, "ending", None),
        hops=1 if direct else getattr(cmdenv, "hops", 1),
        max_jumps_per_hop=_resolve_jumps_per_hop(
            getattr(cmdenv, "maxJumpsPer", None),
            getattr(cmdenv, "maxLyPer", None),
        ),
        max_ly_per_jump=getattr(cmdenv, "maxLyPer", None),
        age_days=getattr(cmdenv, "maxAge", None),
        min_gain_per_ton=getattr(cmdenv, "minGainPerTon", 1),
        max_gain_per_ton=getattr(cmdenv, "maxGainPerTon", 0),
        max_price=_resolve_max_price(getattr(cmdenv, "maxPrice", None)),
        min_supply=getattr(cmdenv, "supply", None),
        min_demand=getattr(cmdenv, "demand", None),
        pad_size=_normalise_pad_size(getattr(cmdenv, "padSize", None)),
        planetary_filter=_normalise_state_filter(
            getattr(cmdenv, "planetary", None),
        ),
        no_planet=getattr(cmdenv, "noPlanet", False),
        fleet_carrier_filter=_normalise_state_filter(
            getattr(cmdenv, "fleet", None),
        ),
        settlement_filter=_normalise_state_filter(
            getattr(cmdenv, "settlement", None),
        ),
        black_market_filter=_normalise_state_filter(
            getattr(cmdenv, "blackMarket", None),
        ),
        max_ls=getattr(cmdenv, "maxLs", 0) or 0,
        ls_penalty_percent=getattr(cmdenv, "lsPenalty", 0.0) or 0.0,
        show_jumps=getattr(cmdenv, "showJumps", False),
        summary=getattr(cmdenv, "summary", False),
        progress=getattr(cmdenv, "progress", False),
        detail=getattr(cmdenv, "detail", 0) or 0,
        debug=getattr(cmdenv, "debug", False),
        direct=direct,
        start_jumps=getattr(cmdenv, "startJumps", 0) or 0,
        end_jumps=getattr(cmdenv, "endJumps", 0) or 0,
        empty_ly_per=getattr(cmdenv, "emptyLyPer", None),
        towards_text=getattr(cmdenv, "goalSystem", None),
        loop=getattr(cmdenv, "loop", False),
        via=tuple(getattr(cmdenv, "via", None) or ()),
        avoid=tuple(getattr(cmdenv, "avoid", None) or ()),
        unique=getattr(cmdenv, "unique", False),
        loop_interval=getattr(cmdenv, "loopInt", None),
        shorten=getattr(cmdenv, "shorten", False),
        routes=getattr(cmdenv, "routes", 1),
        checklist=getattr(cmdenv, "checklist", False),
        x52_pro=getattr(cmdenv, "x52pro", False),
        max_routes=getattr(cmdenv, "maxRoutes", 0) or 0,
        prune_score=getattr(cmdenv, "pruneScores", 0.0) or 0.0,
        prune_hops=getattr(cmdenv, "pruneHops", 3),
    )


# --jumps-per default rule. With --ly-per <= 12.5 LY (typical of an unmodified
# small/medium ship), one jump per hop tends to leave too few reachable
# destinations to be useful, so two jumps is a better starting point. Longer
# jump ranges already reach plenty of systems with a single jump, so the old
# default of 1 stays appropriate there.
_SHORT_RANGE_LY = 12.5
_DEFAULT_JUMPS_PER_HOP_SHORT_RANGE = 2
_DEFAULT_JUMPS_PER_HOP_LONG_RANGE = 1


def _resolve_jumps_per_hop(
    raw_value: int | None,
    max_ly_per_jump: float | None,
) -> int | None:
    """Apply the keyed default only when --jumps-per was omitted.

    Explicit values from the command line — including 0 and 1 — pass through
    untouched. With --jumps-per omitted, a short jump range defaults to two
    jumps per hop; anything longer defaults to one. If --ly-per is also
    missing the long-range default is returned, but validation will reject
    the missing --ly-per first, so that fallback is never actually used.
    """

    if raw_value is not None:
        return raw_value
    if (
        max_ly_per_jump is not None
        and max_ly_per_jump <= _SHORT_RANGE_LY
    ):
        return _DEFAULT_JUMPS_PER_HOP_SHORT_RANGE
    return _DEFAULT_JUMPS_PER_HOP_LONG_RANGE


def _resolve_max_price(raw_value: int | None) -> int:
    """Apply the default only when --max-price was omitted.

    An explicit --max-price 0 is the user's "disable absolute price
    filtering" signal and must pass through untouched. The default is
    applied only when the flag was omitted altogether (raw_value is None).
    """

    if raw_value is None:
        return DEFAULT_MAX_PRICE
    return raw_value


def _normalise_state_filter(value: object) -> tuple[str, ...]:
    """Normalise Y/N/? filters into accepted-state tuples.

    The command parser may provide string-like values, but planner code should
    only care about membership in the accepted set. YN? accepts every possible
    state and is therefore equivalent to no filter.
    """

    states = _normalise_character_filter(value, allowed=("Y", "N", "?"))
    if set(states) == {"Y", "N", "?"}:
        return ()
    return states


def _normalise_pad_size(value: object) -> str | None:
    """Normalise the raw --pad-size input without discarding bad values.

    --pad-size is a single ship-fit threshold (S, M, or L). Normalisation only
    strips surrounding whitespace and uppercases, so validation can reject any
    value that is not one of the three valid sizes. An absent or empty value
    means no pad-size threshold was requested.
    """

    if value is None:
        return None

    text = str(value).strip().upper()
    return text or None


def _normalise_character_filter(
    value: object,
    *,
    allowed: tuple[str, ...],
) -> tuple[str, ...]:
    """Return a de-duplicated tuple of allowed uppercase filter characters."""

    if value is None:
        return ()

    if isinstance(value, str):
        raw_values = tuple(value.upper())
    else:
        raw_values = tuple(str(v).upper() for v in value)

    accepted = []
    for item in raw_values:
        if item in allowed and item not in accepted:
            accepted.append(item)

    return tuple(accepted)