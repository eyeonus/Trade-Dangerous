"""Reachability checks for trade run planning."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

import numpy as np
from scipy.spatial import cKDTree
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from tradedangerous.db.orm_models import System

from .failures import NoReachableRoute
from .run_result import JumpPath, ResolvedSystem


@dataclass(slots=True)
class _LocalBubble:
    """A pre-fetched neighbourhood of systems with its full adjacency table.

    The bubble is the set of systems within (max_jumps_per_hop * max_ly_per_jump)
    of an anchor system — wide enough that any path of up to max_jumps_per_hop
    hops from the anchor stays inside it (triangle inequality). Adjacency is
    built once at load time with cKDTree.query_ball_tree(self, max_ly); BFS
    then walks pure-Python lists with no further scipy calls.

    path_cache stores BFS results keyed by destination bubble-index. A station
    pair matrix evaluating many (source_station, destination_station) pairs
    asks the same (source_system, destination_system) reachability question
    over and over — the cache turns every repeat into a dict lookup. Cached
    None means "computed unreachable"; absent means "not yet computed."
    """

    systems: tuple[ResolvedSystem, ...]
    adjacency: tuple[tuple[int, ...], ...]
    id_to_index: dict[int, int]
    path_cache: dict[int, tuple[ResolvedSystem, ...] | None] = field(
        default_factory=dict,
    )


def plan_jump_path(
    source: ResolvedSystem,
    destination: ResolvedSystem,
    *,
    max_jumps_per_hop: int,
    max_ly_per_jump: float,
    session: Session,
    bubble_cache: dict[int, _LocalBubble],
) -> JumpPath:
    """Return a jump path from source to destination within the request limits.

    Order of work:
      1. Same-system supercruise — no jump needed.
      2. --jumps-per 0 rejection — caller asked for no jumps at all.
      3. Direct-line single hop — destination is within one --ly-per of source.
         Applies for any --jumps-per >= 1 since one is always within the cap.
      4. Triangle-inequality early-out — even an N-jump straight line of N jumps
         at max --ly-per each cannot reach destinations more than N*max_ly away.
      5. Bubble + adjacency BFS, depth capped at --jumps-per. The bubble is
         loaded once per anchor and cached on bubble_cache for reuse.
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

    # Squared distances throughout: cheap, monotonic with the real distance,
    # and the bubble fetch uses the same shape — no need to take a square root
    # until a result actually needs reporting.
    dx = destination.x - source.x
    dy = destination.y - source.y
    dz = destination.z - source.z
    distance_sq = dx * dx + dy * dy + dz * dz
    max_ly_sq = max_ly_per_jump * max_ly_per_jump

    if distance_sq <= max_ly_sq:
        distance_ly = math.sqrt(distance_sq)
        return JumpPath(
            source_system_id=source.system_id,
            destination_system_id=destination.system_id,
            systems=(source, destination),
            distance_ly=distance_ly,
            jumps=1,
            is_same_system=False,
            is_reachable=True,
        )

    # The widest path of N jumps at max --ly-per each spans N*max_ly LY. If the
    # destination is further than that, no path of the requested depth exists,
    # and the bubble fetch can be skipped.
    bubble_radius = max_jumps_per_hop * max_ly_per_jump
    if distance_sq > bubble_radius * bubble_radius:
        raise NoReachableRoute(
            _unreachable_message(max_jumps_per_hop, max_ly_per_jump),
            option_name="--jumps-per",
            details={
                "source_system": source.name,
                "destination_system": destination.name,
                "max_jumps_per_hop": max_jumps_per_hop,
                "max_ly_per_jump": max_ly_per_jump,
            },
        )

    bubble = bubble_cache.get(source.system_id)
    if bubble is None:
        bubble = _load_local_bubble(
            session, source, bubble_radius, max_ly_per_jump
        )
        bubble_cache[source.system_id] = bubble

    destination_idx = bubble.id_to_index.get(destination.system_id)
    if destination_idx is None:
        # Anchor is at the bubble centre and the triangle-inequality check
        # guarantees the destination is inside it — reaching this branch
        # means a data gap in the System table around this anchor.
        path: tuple[ResolvedSystem, ...] | None = None
    elif destination_idx in bubble.path_cache:
        path = bubble.path_cache[destination_idx]
    else:
        path = _bfs_jump_path(
            source=source,
            destination=destination,
            bubble=bubble,
            destination_idx=destination_idx,
            max_jumps=max_jumps_per_hop,
        )
        bubble.path_cache[destination_idx] = path

    if path is None:
        raise NoReachableRoute(
            _unreachable_message(max_jumps_per_hop, max_ly_per_jump),
            option_name="--jumps-per",
            details={
                "source_system": source.name,
                "destination_system": destination.name,
                "max_jumps_per_hop": max_jumps_per_hop,
                "max_ly_per_jump": max_ly_per_jump,
            },
        )

    # distance_ly is straight-line source-to-destination for now; the polyline
    # vs straight-line decision is task #4 and revisits this in one place.
    distance_ly = math.sqrt(distance_sq)
    return JumpPath(
        source_system_id=source.system_id,
        destination_system_id=destination.system_id,
        systems=path,
        distance_ly=distance_ly,
        jumps=len(path) - 1,
        is_same_system=False,
        is_reachable=True,
    )


def _load_local_bubble(
    session: Session,
    anchor: ResolvedSystem,
    radius_ly: float,
    max_ly_per_jump: float,
) -> _LocalBubble:
    """Fetch every system within radius_ly of the anchor and precompute adjacency.

    Bounding-box predicates run first on the indexed pos_x/pos_y/pos_z columns;
    a squared-distance refinement trims the box to a sphere without ever taking
    a square root. cKDTree.query_ball_tree(self, max_ly_per_jump) computes the
    full per-system neighbour list in one C-side call; from that point on BFS
    walks pure-Python tuples with no further scipy work. One-time scipy cost
    per anchor; per-BFS cost stays in Python list traversal.
    """

    ax, ay, az = anchor.x, anchor.y, anchor.z
    radius_sq = radius_ly * radius_ly
    dx = System.pos_x - ax
    dy = System.pos_y - ay
    dz = System.pos_z - az
    stmt = select(System).where(
        and_(
            System.pos_x.between(ax - radius_ly, ax + radius_ly),
            System.pos_y.between(ay - radius_ly, ay + radius_ly),
            System.pos_z.between(az - radius_ly, az + radius_ly),
            dx * dx + dy * dy + dz * dz <= radius_sq,
        )
    )

    systems: list[ResolvedSystem] = []
    id_to_index: dict[int, int] = {}
    coords_list: list[tuple[float, float, float]] = []
    for index, row in enumerate(session.scalars(stmt)):
        system_id = int(row.system_id)
        x = float(row.pos_x)
        y = float(row.pos_y)
        z = float(row.pos_z)
        name = str(row.name)
        systems.append(
            ResolvedSystem(
                system_id=system_id,
                name=name,
                dbname=name,
                x=x,
                y=y,
                z=z,
            )
        )
        id_to_index[system_id] = index
        coords_list.append((x, y, z))

    coords = np.asarray(coords_list, dtype=np.float64)
    tree = cKDTree(coords)
    # query_ball_tree returns a Python list of N lists. Each inner list is the
    # indices of bubble systems within max_ly of the row's system, self
    # included — the self entry is harmless because BFS filters already-seen
    # indices via the parent map.
    raw_adjacency = tree.query_ball_tree(tree, r=max_ly_per_jump)
    adjacency = tuple(tuple(neighbours) for neighbours in raw_adjacency)

    return _LocalBubble(
        systems=tuple(systems),
        adjacency=adjacency,
        id_to_index=id_to_index,
    )


def _bfs_jump_path(
    *,
    source: ResolvedSystem,
    destination: ResolvedSystem,
    bubble: _LocalBubble,
    destination_idx: int,
    max_jumps: int,
) -> tuple[ResolvedSystem, ...] | None:
    """Walk the bubble breadth-first up to max_jumps layers.

    Returns the ordered system sequence from source to destination, or None if
    no path of length <= max_jumps exists inside the bubble. The bubble is
    sized so that any path of the requested depth stays within it, so failure
    here means no such path exists in the galaxy under these constraints.
    """

    source_idx = bubble.id_to_index.get(source.system_id)
    if source_idx is None:
        return None

    parent: dict[int, int] = {source_idx: source_idx}
    frontier = [source_idx]
    adjacency = bubble.adjacency
    for _depth in range(max_jumps):
        if not frontier:
            return None
        next_frontier: list[int] = []
        for idx in frontier:
            for n in adjacency[idx]:
                if n in parent:
                    continue
                parent[n] = idx
                if n == destination_idx:
                    return _reconstruct_path(
                        parent, destination_idx, bubble.systems
                    )
                next_frontier.append(n)
        frontier = next_frontier
    return None


def _reconstruct_path(
    parent: dict[int, int],
    destination_idx: int,
    systems: tuple[ResolvedSystem, ...],
) -> tuple[ResolvedSystem, ...]:
    """Walk the parent map from destination back to source, returning forward order."""

    path_indices: deque[int] = deque()
    current = destination_idx
    while True:
        path_indices.appendleft(current)
        upstream = parent[current]
        if upstream == current:
            break
        current = upstream
    return tuple(systems[i] for i in path_indices)


def _unreachable_message(max_jumps_per_hop: int, max_ly_per_jump: float) -> str:
    """Return the standard 'no path found' message for failed BFS / triangle reject."""

    return (
        f"No jump path within --jumps-per {max_jumps_per_hop} "
        f"at --ly-per {max_ly_per_jump:g} LY; "
        f"increase --jumps-per or --ly-per."
    )


def system_distance_ly(source: ResolvedSystem, destination: ResolvedSystem) -> float:
    """Return Euclidean system distance in light years."""

    return math.sqrt(
        (source.x - destination.x) ** 2
        + (source.y - destination.y) ** 2
        + (source.z - destination.z) ** 2
    )
