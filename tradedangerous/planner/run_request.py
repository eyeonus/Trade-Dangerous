"""Neutral request DTOs for trade run planning."""

from __future__ import annotations

from dataclasses import dataclass


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
    min_supply: int | None = None
    min_demand: int | None = None
    pad_size_filter: str | None = None
    planetary_filter: str | None = None
    no_planet: bool = False
    fleet_carrier_filter: str | None = None
    settlement_filter: str | None = None
    black_market_filter: str | None = None
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
    towards_text: str | None = None
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
    prune_score: float = 0.0
    prune_hops: int = 3


def run_request_from_cmdenv(cmdenv: object) -> RunRequest:
    """Build a neutral request from the parsed command environment."""

    return RunRequest(
        capacity_units=getattr(cmdenv, "capacity", None),
        starting_credits=getattr(cmdenv, "credits", None),
        insurance_reserve=getattr(cmdenv, "insurance", 0) or 0,
        cargo_limit_per_item=getattr(cmdenv, "limit", None) or 0,
        margin=getattr(cmdenv, "margin", 0.0) or 0.0,
        from_text=getattr(cmdenv, "starting", None),
        to_text=getattr(cmdenv, "ending", None),
        hops=getattr(cmdenv, "hops", 1),
        max_jumps_per_hop=getattr(cmdenv, "maxJumpsPer", None),
        max_ly_per_jump=getattr(cmdenv, "maxLyPer", None),
        age_days=getattr(cmdenv, "maxAge", None),
        min_gain_per_ton=getattr(cmdenv, "minGainPerTon", 1),
        max_gain_per_ton=getattr(cmdenv, "maxGainPerTon", 0),
        min_supply=getattr(cmdenv, "supply", None),
        min_demand=getattr(cmdenv, "demand", None),
        pad_size_filter=getattr(cmdenv, "padSize", None),
        planetary_filter=getattr(cmdenv, "planetary", None),
        no_planet=getattr(cmdenv, "noPlanet", False),
        fleet_carrier_filter=getattr(cmdenv, "fleet", None),
        settlement_filter=getattr(cmdenv, "settlement", None),
        black_market_filter=getattr(cmdenv, "blackMarket", None),
        max_ls=getattr(cmdenv, "maxLs", 0) or 0,
        ls_penalty_percent=getattr(cmdenv, "lsPenalty", 0.0) or 0.0,
        show_jumps=getattr(cmdenv, "showJumps", False),
        summary=getattr(cmdenv, "summary", False),
        progress=getattr(cmdenv, "progress", False),
        detail=getattr(cmdenv, "detail", 0) or 0,
        debug=getattr(cmdenv, "debug", False),
        direct=getattr(cmdenv, "direct", False),
        start_jumps=getattr(cmdenv, "startJumps", 0) or 0,
        end_jumps=getattr(cmdenv, "endJumps", 0) or 0,
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