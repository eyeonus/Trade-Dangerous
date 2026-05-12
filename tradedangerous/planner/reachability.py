"""Reachability checks for trade run planning."""

from __future__ import annotations

import math

from .failures import NoReachableRoute, ReachabilityImplementationMissing
from .run_result import JumpPath, ResolvedSystem


def plan_jump_path(
    source: ResolvedSystem,
    destination: ResolvedSystem,
    *,
    max_jumps_per_hop: int,
    max_ly_per_jump: float,
) -> JumpPath:
    """Return a jump path that satisfies the request constraints.

    The current implementation proves same-system supercruise and direct
    one-jump travel. Multi-jump graph search needs a neighbour/range surface
    and must not be approximated from straight-line distance alone.
    """

    if source.system_id == destination.system_id:
        return JumpPath(
            source_system_id=source.system_id,
            destination_system_id=destination.system_id,
            systems=(source,),
            distance_ly=0.0,
            jumps=0,
            is_same_system=True,
            is_reachable=True,
        )

    if max_jumps_per_hop <= 0:
        raise NoReachableRoute(
            "Destination system is not reachable with --jumps-per 0.",
            option_name="--jumps-per",
            details={
                "source_system": source.name,
                "destination_system": destination.name,
            },
        )

    distance_ly = system_distance_ly(source, destination)

    if max_jumps_per_hop == 1:
        if distance_ly > max_ly_per_jump:
            raise NoReachableRoute(
                "Destination system is outside the requested jump range.",
                option_name="--ly-per",
                details={
                    "source_system": source.name,
                    "destination_system": destination.name,
                    "distance_ly": distance_ly,
                    "max_ly_per_jump": max_ly_per_jump,
                },
            )

        return JumpPath(
            source_system_id=source.system_id,
            destination_system_id=destination.system_id,
            systems=(source, destination),
            distance_ly=distance_ly,
            jumps=1,
            is_same_system=False,
            is_reachable=True,
        )

    raise ReachabilityImplementationMissing(
        "Multi-jump reachability is not implemented for this planner slice.",
        option_name="--jumps-per",
        details={
            "source_system": source.name,
            "destination_system": destination.name,
            "max_jumps_per_hop": max_jumps_per_hop,
        },
    )


def system_distance_ly(source: ResolvedSystem, destination: ResolvedSystem) -> float:
    """Return Euclidean system distance in light years."""

    return math.sqrt(
        (source.x - destination.x) ** 2
        + (source.y - destination.y) ** 2
        + (source.z - destination.z) ** 2
    )