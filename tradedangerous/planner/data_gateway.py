"""Read-only data access for trade run planning."""

from __future__ import annotations

import time

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    BigInteger,
    Column,
    Index,
    Integer,
    MetaData,
    Select,
    Table,
    and_,
    bindparam,
    case,
    cast,
    func,
    literal,
    or_,
    select,
    text,
)
from sqlalchemy.orm import Session, aliased

from tradedangerous.db.orm_models import Category, Item, Station, StationItem, System
from tradedangerous.db.utils import analyze_temp_table, force_order_join
from tradedangerous.db.station_types import (
    DISPLAY_NAMES,
    FLEET_CARRIER_TYPE_IDS,
    SETTLEMENT_TYPE_IDS,
    UNKNOWN,
    fleet_carrier_state,
    settlement_state,
)
from tradedangerous.db.utils import begin_bulk_mode

from .failures import (
    DestinationHasNoBuyingData,
    DestinationStationIneligible,
    MarketTimestampInvalid,
    PlannerDataError,
    SourceHasNoSellingData,
    SourceStationIneligible,
    StationHasNoMarket,
)
from .reachability import is_system_pair_reachable
from .run_request import RunRequest
from .run_result import ExpansionStats, ResolvedStation, ResolvedSystem, TradeCandidate


def validate_station_filters(
    station: ResolvedStation,
    request: RunRequest,
    *,
    role: str,
) -> None:
    """Validate station-level filters for a selected route endpoint."""

    failure_type = (
        SourceStationIneligible if role == "source" else DestinationStationIneligible
    )
    option_prefix = "--from" if role == "source" else "--to"

    # Unknown market state is allowed to proceed when usable price rows exist.
    # A positive market record is stronger evidence than an unset service flag.
    if station.market == "N":
        raise StationHasNoMarket(
            f"{option_prefix} station has no market: {station.dbname}",
            option_name=option_prefix,
            entity_name=station.dbname,
        )

    # An unknown pad qualifies whenever the requested threshold admits a medium
    # pad, and is rejected only under --pad-size L; _pad_size_matches applies
    # that rule. The message names the unknown pad as the cause when relevant.
    if not _pad_size_matches(station.max_pad_size, request.pad_size):
        if station.max_pad_size not in _KNOWN_PAD_SIZES:
            message = (
                f"{option_prefix} station has an unknown landing pad size: "
                f"{station.dbname}"
            )
        else:
            message = f"{option_prefix} station does not meet --pad-size."
        raise failure_type(
            message,
            option_name="--pad-size",
            entity_name=station.dbname,
        )

    if request.planetary_filter and station.planetary not in request.planetary_filter:
        raise failure_type(
            f"{option_prefix} station does not meet --planetary.",
            option_name="--planetary",
            entity_name=station.dbname,
        )

    if request.black_market_filter and not _state_filter_matches(
        station.black_market,
        request.black_market_filter,
    ):
        raise failure_type(
            f"{option_prefix} station does not meet --black-market.",
            option_name="--black-market",
            entity_name=station.dbname,
        )

    if request.max_ls and (
        station.ls_from_star <= 0 or station.ls_from_star > request.max_ls
    ):
        raise failure_type(
            f"{option_prefix} station does not meet --ls-max.",
            option_name="--ls-max",
            entity_name=station.dbname,
        )

    if request.fleet_carrier_filter and not _state_filter_matches(
        station.fleet_carrier,
        request.fleet_carrier_filter,
    ):
        raise failure_type(
            f"{option_prefix} station does not meet --fleet-carrier.",
            option_name="--fleet-carrier",
            entity_name=station.dbname,
        )
    
    if request.settlement_filter and not _state_filter_matches(
        station.settlement,
        request.settlement_filter,
    ):
        raise failure_type(
            f"{option_prefix} station does not meet --settlement.",
            option_name="--settlement",
            entity_name=station.dbname,
        )


def fetch_eligible_stations_in_system(
    session: Session,
    system: ResolvedSystem,
    request: RunRequest,
    *,
    role: str,
) -> tuple[ResolvedStation, ...]:
    """Fetch stations in one resolved system that pass station-level filters.

    This is endpoint expansion only: it deliberately stays bounded to the
    selected system and does not inspect market quotes. Source/destination
    quote eligibility is still evaluated later for each station pair.
    SQL predicates are authoritative for all station-level filters.
    """

    stmt = (
        select(Station)
        .where(
            and_(
                Station.system_id == system.system_id,
                *_station_attribute_predicates(request),
            )
        )
        .order_by(Station.station_id)
    )
    return tuple(
        _resolved_station_from_model(station, system)
        for station in session.scalars(stmt)
    )


def fetch_eligible_stations_in_reachable_systems(
    session: Session,
    systems: tuple[ResolvedSystem, ...],
    request: RunRequest,
    *,
    role: str,
) -> tuple[ResolvedStation, ...]:
    """Fetch eligible stations across a precomputed reachable-system set.

    The empty-jump positioning fan-out (--start-jumps / --end-jumps) hands in
    the systems within N empty jumps of an anchor, already computed in memory
    from the cKDTree bubble. The set is bulk-inserted into a temp table and the
    membership test stays a SQL subquery, never a large IN (...) literal that
    would flip SQLite off the station index. Station-attribute filters apply
    exactly as for single-system expansion; market quotes are still checked
    later per station pair.

    The precomputed systems already carry coordinates, so each station's
    ResolvedSystem comes from the in-memory set rather than a second System
    join.
    """

    if not systems:
        return ()

    systems_by_id = {int(system.system_id): system for system in systems}
    connection = session.connection()
    metadata = MetaData()
    # Mirror the System pos column type so the bulk insert needs no implicit
    # cast on either backend. depth is unused here (no layered BFS) but the
    # shared bulk-insert helper writes it, so the column must exist.
    pos_type = System.__table__.c.pos_x.type
    temp = Table(
        "td_positioning_systems",
        metadata,
        Column("system_id", BigInteger, primary_key=True),
        Column("pos_x", pos_type),
        Column("pos_y", pos_type),
        Column("pos_z", pos_type),
        Column("depth", Integer),
        prefixes=["TEMPORARY"],
    )
    # Drop any leftover from a previous interrupted call before recreating.
    temp.drop(connection, checkfirst=True)
    temp.create(connection)
    try:
        _bulk_insert_reachable_systems(connection, temp, systems)
        # Role-qualify in SQL before materialising DTOs: a source positioning
        # station must have at least one usable supply row, a destination one
        # at least one usable demand row, under the run-constant predicates
        # (price/units, --age, --max-price, avoided commodities). Without this
        # a station that clears the attribute filters but has no usable rows for
        # its role is still built into a DTO and admitted to the pair matrix,
        # only to be found useless. The predicates are the canonical constant-row
        # filters shared with the pair query and the qualification temps, so
        # eligibility cannot drift; the per-hop credit cap and the pair-gain stay
        # later (neither is run-constant), so this removes only stations that can
        # never produce a candidate — exact, not a new eligibility definition.
        cutoff = _age_cutoff(request.age_days)
        if role == "source":
            row_filters = _supply_constant_row_filters(request, cutoff)
        else:
            row_filters = _demand_constant_row_filters(request, cutoff)
        has_usable_row = (
            select(StationItem.station_id)
            .where(StationItem.station_id == Station.station_id, *row_filters)
            .exists()
        )
        stmt = (
            select(Station)
            .where(
                and_(
                    Station.system_id.in_(select(temp.c.system_id)),
                    *_station_attribute_predicates(request),
                    has_usable_row,
                )
            )
            .order_by(Station.station_id)
        )
        stations = []
        for station in session.scalars(stmt):
            resolved_system = systems_by_id.get(int(station.system_id))
            if resolved_system is None:
                # Station whose system left the precomputed set — defensive
                # skip rather than a KeyError, mirroring fetch_stations_by_id.
                continue
            stations.append(
                _resolved_station_from_model(station, resolved_system)
            )
        return tuple(stations)
    finally:
        temp.drop(connection, checkfirst=True)


def _station_attribute_predicates(request: RunRequest):
    """Return SQL predicates for station-attribute filters.

    These filters apply regardless of how the candidate station set was
    reached: bounded system expansion and the open-ended spatial search both
    use them. The System.system_id pin (expansion) or the spatial predicates
    (open search) are composed in separately by the caller.
    """

    predicates = [
        Station.market != "N",
        # --pad-size raises the threshold to medium-or-larger, or large-only,
        # when supplied. Unknown-pad stations qualify unless the threshold is
        # large-only (see _qualifying_pad_sizes).
        Station.max_pad_size.in_(_qualifying_pad_sizes(request.pad_size)),
    ]
    if request.planetary_filter:
        predicates.append(Station.planetary.in_(request.planetary_filter))
    if request.black_market_filter:
        predicates.append(Station.blackmarket.in_(request.black_market_filter))
    if request.max_ls:
        predicates.append(Station.ls_from_star > 0)
        predicates.append(Station.ls_from_star <= request.max_ls)
    if request.fleet_carrier_filter:
        predicates.append(
            Station.type_id.in_(
                _type_id_filter_values(
                    request.fleet_carrier_filter,
                    FLEET_CARRIER_TYPE_IDS,
                )
            )
        )
    if request.settlement_filter:
        predicates.append(
            Station.type_id.in_(
                _type_id_filter_values(
                    request.settlement_filter,
                    SETTLEMENT_TYPE_IDS,
                )
            )
        )
    # --avoid station/system exclusion. An avoided station is never an eligible
    # route station; an avoided system bars every station within it. The id sets
    # are small (a handful of user-typed tokens), so a literal NOT IN is correct
    # and cheap here. This is the single seam every attribute-filtered candidate
    # fetch flows through, so both shapes inherit the exclusion in one place.
    if request.avoid_station_ids:
        predicates.append(Station.station_id.notin_(request.avoid_station_ids))
    if request.avoid_system_ids:
        predicates.append(Station.system_id.notin_(request.avoid_system_ids))
    return tuple(predicates)


def _reachable_memo_key(
    anchor_system: ResolvedSystem,
    request: RunRequest,
) -> tuple[int, int, float]:
    """Key a memoised reachable-set temp table by what defines its contents."""

    return (
        int(anchor_system.system_id),
        int(request.max_jumps_per_hop),
        float(request.max_ly_per_jump or 0.0),
    )


def reachable_memo_contains(
    memo: dict,
    anchor_system: ResolvedSystem,
    request: RunRequest,
) -> bool:
    """Whether the memo already holds this anchor's reachable temp table.

    Callers that precompute the reachable set in memory (the cKDTree BFS)
    check this first: on a hit the temp table is reused as-is and a
    precomputed set would be discarded unread, so the BFS can be skipped.
    """

    return _reachable_memo_key(anchor_system, request) in memo


@contextmanager
def _reachable_station_query(
    session: Session,
    anchor_system: ResolvedSystem,
    request: RunRequest,
    *,
    reachable_memo: dict | None = None,
    destination_envelope_xyz: tuple[float, float, float] | None = None,
    destination_envelope_ly: float | None = None,
    expansion_stats: ExpansionStats | None = None,
    precomputed_systems: tuple[ResolvedSystem, ...] | None = None,
) -> Iterator[Select]:
    """Yield a SELECT of station ids reachable from the anchor within --jumps-per.

    For --jumps-per 0 (same-system) no temp table is needed; the helper yields
    today's bounded query. For --jumps-per >= 1 the helper builds a per-call
    temp table seeded with the anchor and grown one layer at a time up to
    --jumps-per before yielding the composed SELECT. Without ``reachable_memo``
    the table is dropped on exit, even if the caller raises.

    When ``reachable_memo`` is supplied, the helper caches the temp table in
    the memo keyed on ``(source_system_id, max_jumps_per_hop, max_ly_per_jump)``
    so repeated callers for the same key reuse a single built table. Memoised
    tables are uniquely named and outlive the ``with`` block; the caller is
    responsible for releasing them at end-of-request via
    ``release_reachable_memo`` so they do not linger.

    When ``destination_envelope_xyz`` and ``destination_envelope_ly`` are both
    supplied, the yielded SELECT additionally restricts the reachable set to
    systems within a bounding box plus squared-distance check against those
    coordinates. The temp table already carries pos_x/y/z columns from the
    BFS build, so the filter runs against the temp directly with no extra
    System join. Multi-hop fixed-terminal expansion uses this to drop
    destinations that cannot plausibly close on --to in the remaining hops,
    before they ever leave SQL into Python.

    When ``request.towards_target`` is set (the --towards open-destination
    shapes only), the reachable set is instead restricted to systems strictly
    closer to that target than the anchor, applying the spec's per-hop progress
    rule in SQL. It is mutually exclusive with the destination envelope:
    --towards forbids --to, and the envelope is a fixed-terminal device.

    Callers compose the yielded SELECT via ``.in_(...)`` so the reachable set
    stays in SQL — handing a large id list to a later query as a literal
    ``IN (...)`` would flip SQLite off the StationItem primary key onto a
    galaxy-wide index scan, exactly the legacy preload-first failure this
    rewrite exists to avoid.
    """

    if request.max_jumps_per_hop == 0:
        # Same-system supercruise: no jump, no temp table. With an envelope
        # supplied the only reachable system is the anchor itself, so the
        # envelope collapses to a single distance check on the anchor.
        if destination_envelope_xyz is not None and destination_envelope_ly is not None:
            dx = anchor_system.x - destination_envelope_xyz[0]
            dy = anchor_system.y - destination_envelope_xyz[1]
            dz = anchor_system.z - destination_envelope_xyz[2]
            envelope_sq = destination_envelope_ly * destination_envelope_ly
            if (dx * dx + dy * dy + dz * dz) > envelope_sq:
                # Anchor outside envelope — no reachable stations qualify.
                yield select(Station.station_id).where(literal(False))
                return
        # --towards: a same-system hop keeps the route at the anchor system, so
        # it makes no forward progress toward the target. It qualifies only when
        # the anchor already is the target (the spec's "unless the hop reaches
        # the target system" clause); otherwise nothing here can progress.
        if (
            request.towards_target is not None
            and anchor_system.system_id != request.towards_target.system_id
        ):
            yield select(Station.station_id).where(literal(False))
            return
        in_range_systems = select(System.system_id).where(
            System.system_id == anchor_system.system_id
        )
        yield select(Station.station_id).where(
            and_(
                Station.system_id.in_(in_range_systems),
                *_station_attribute_predicates(request),
            )
        )
        return

    memo_key: tuple[int, int, float] | None = None
    temp: Table | None = None
    if reachable_memo is not None:
        memo_key = _reachable_memo_key(anchor_system, request)
        temp = reachable_memo.get(memo_key)
        if expansion_stats is not None:
            if temp is not None:
                expansion_stats.memo_hits += 1
            else:
                expansion_stats.memo_misses += 1

    connection = session.connection()
    built_locally = temp is None
    if temp is None:
        metadata = MetaData()
        # Mirror the System pos column type so the spatial maths inside the layer
        # INSERT runs as floats on either backend without an implicit cast.
        pos_type = System.__table__.c.pos_x.type
        if memo_key is None:
            table_name = "td_reachable_systems"
        else:
            # Per-key temp table so concurrent memoised entries can coexist
            # within one session. ly_per is encoded as integer hundredths to
            # keep the name stable across equivalent float representations.
            table_name = (
                f"td_reachable_systems_{memo_key[0]}_"
                f"{memo_key[1]}_{int(memo_key[2] * 100)}"
            )
        temp = Table(
            table_name,
            metadata,
            Column("system_id", BigInteger, primary_key=True),
            Column("pos_x", pos_type),
            Column("pos_y", pos_type),
            Column("pos_z", pos_type),
            Column("depth", Integer),
            # Depth index lets each layer's JOIN find the previous frontier
            # without scanning the whole accumulated set, which is what makes
            # later layers stay cheap as the table grows.
            Index(f"ix_{table_name}_depth", "depth"),
            prefixes=["TEMPORARY"],
        )
        # Drop any leftover from a previous interrupted call before recreating.
        temp.drop(connection, checkfirst=True)
        temp.create(connection)
        try:
            if precomputed_systems is not None:
                # Reachable set computed in memory from the cKDTree bubble
                # (reachability.reachable_systems_from); bulk-insert it instead
                # of running the layered SQL spatial BFS. Identical set, far
                # cheaper per anchor.
                _bulk_insert_reachable_systems(connection, temp, precomputed_systems)
            else:
                _populate_reachable_systems(
                    connection,
                    temp,
                    anchor_system,
                    float(request.max_ly_per_jump or 0.0),
                    int(request.max_jumps_per_hop),
                )
        except Exception:
            temp.drop(connection, checkfirst=True)
            raise
        if memo_key is not None:
            reachable_memo[memo_key] = temp

    try:
        # System-id source: either the unfiltered temp, or an envelope-
        # narrowed subselect against the temp's pos columns. Bounding box
        # first lets the database short-circuit before the squared-distance
        # refinement; the temp set is bounded by the BFS, so the test runs
        # on at most a few thousand rows.
        if (
            destination_envelope_xyz is not None
            and destination_envelope_ly is not None
        ):
            to_x, to_y, to_z = destination_envelope_xyz
            env = destination_envelope_ly
            envelope_sq = env * env
            dx = temp.c.pos_x - to_x
            dy = temp.c.pos_y - to_y
            dz = temp.c.pos_z - to_z
            system_id_source = select(temp.c.system_id).where(
                and_(
                    temp.c.pos_x.between(to_x - env, to_x + env),
                    temp.c.pos_y.between(to_y - env, to_y + env),
                    temp.c.pos_z.between(to_z - env, to_z + env),
                    dx * dx + dy * dy + dz * dz <= envelope_sq,
                )
            )
        elif request.towards_target is not None:
            # --towards: restrict the reachable destination set to systems that
            # sit strictly closer to the target than the anchor — the anchor is
            # this hop's previous trade position, so this is the per-hop
            # forward-progress rule. The sphere is centred on the target with
            # radius = the anchor's own distance to the target; strict "<"
            # rejects a hop that lands no closer. The OR arm admits the target
            # system itself (the "unless the hop reaches the target system"
            # clause), which also covers the radius-0 case where the anchor
            # already is the target. Bounding box first, then squared distance,
            # mirroring the envelope path and running against the temp's own
            # pos columns with no extra System join.
            target = request.towards_target
            adx = anchor_system.x - target.x
            ady = anchor_system.y - target.y
            adz = anchor_system.z - target.z
            anchor_dist_sq = adx * adx + ady * ady + adz * adz
            radius = anchor_dist_sq ** 0.5
            dx = temp.c.pos_x - target.x
            dy = temp.c.pos_y - target.y
            dz = temp.c.pos_z - target.z
            system_id_source = select(temp.c.system_id).where(
                or_(
                    and_(
                        temp.c.pos_x.between(target.x - radius, target.x + radius),
                        temp.c.pos_y.between(target.y - radius, target.y + radius),
                        temp.c.pos_z.between(target.z - radius, target.z + radius),
                        dx * dx + dy * dy + dz * dz < anchor_dist_sq,
                    ),
                    temp.c.system_id == target.system_id,
                )
            )
        else:
            system_id_source = select(temp.c.system_id)
        yield select(Station.station_id).where(
            and_(
                Station.system_id.in_(system_id_source),
                *_station_attribute_predicates(request),
            )
        )
    finally:
        # Memoised tables outlive this context; release_reachable_memo drops
        # them at end of request. Non-memoised tables drop here as before.
        if memo_key is None and built_locally:
            temp.drop(connection, checkfirst=True)


def release_reachable_memo(session: Session, memo: dict) -> None:
    """Drop every temp table held in a reachable-set memo and clear it.

    Multi-hop planning keeps reachable-system temp tables alive across calls
    via the memo so the per-key build is paid once per
    ``(source_system, jumps_per, ly_per)`` tuple. At request teardown the
    memo must be released so the tables do not linger across requests.
    """

    if not memo:
        return
    connection = session.connection()
    for temp_table in memo.values():
        try:
            temp_table.drop(connection, checkfirst=True)
        except Exception:
            # Mirrors the unanchored teardown: the request is already being
            # torn down, so a drop failure here cannot help recovery.
            pass
    memo.clear()


def _bulk_insert_reachable_systems(
    connection,
    temp: Table,
    systems: tuple[ResolvedSystem, ...],
) -> None:
    """Bulk-insert a precomputed reachable system set into the temp table.

    The set is computed in memory from the cKDTree bubble (see
    reachability.reachable_systems_from) instead of the layered SQL spatial
    BFS, which is far cheaper per anchor. pos columns are carried so the
    destination-envelope filter still runs against the temp directly; depth is
    unused once the table is built, so a constant 0 is fine. The bubble's
    reachable set is already de-duplicated, so the primary key never collides.
    """

    if not systems:
        return
    connection.execute(
        temp.insert(),
        [
            {
                "system_id": int(s.system_id),
                "pos_x": s.x,
                "pos_y": s.y,
                "pos_z": s.z,
                "depth": 0,
            }
            for s in systems
        ],
    )


def _populate_reachable_systems(
    connection,
    temp: Table,
    anchor: ResolvedSystem,
    max_ly: float,
    max_jumps: int,
) -> None:
    """Seed the anchor at depth 0 and grow the reachable set one layer at a time.

    Each layer K adds systems within max_ly of any depth-(K-1) system that
    aren't already in the table. Bounding box first on the indexed System
    pos columns, squared-distance refines. The NOT EXISTS dedup keeps the
    table free of duplicates as overlapping neighbourhoods would otherwise
    produce them.
    """

    connection.execute(
        temp.insert().values(
            system_id=anchor.system_id,
            pos_x=anchor.x,
            pos_y=anchor.y,
            pos_z=anchor.z,
            depth=0,
        )
    )
    if max_jumps <= 0:
        return

    ly_sq = max_ly * max_ly
    for prev_depth in range(max_jumps):
        next_depth = prev_depth + 1
        r = temp.alias()
        dx = System.pos_x - r.c.pos_x
        dy = System.pos_y - r.c.pos_y
        dz = System.pos_z - r.c.pos_z
        layer_select = (
            select(
                System.system_id,
                System.pos_x,
                System.pos_y,
                System.pos_z,
                literal(next_depth).label("depth"),
            )
            .distinct()
            .select_from(
                System.__table__.join(
                    r,
                    and_(
                        r.c.depth == prev_depth,
                        System.pos_x.between(
                            r.c.pos_x - max_ly, r.c.pos_x + max_ly
                        ),
                        System.pos_y.between(
                            r.c.pos_y - max_ly, r.c.pos_y + max_ly
                        ),
                        System.pos_z.between(
                            r.c.pos_z - max_ly, r.c.pos_z + max_ly
                        ),
                        dx * dx + dy * dy + dz * dz <= ly_sq,
                    ),
                )
            )
            .where(
                ~(
                    select(temp.c.system_id)
                    .where(temp.c.system_id == System.system_id)
                    .exists()
                )
            )
        )
        connection.execute(
            temp.insert().from_select(
                ["system_id", "pos_x", "pos_y", "pos_z", "depth"],
                layer_select,
            )
        )


def _type_id_filter_values(
    requested_states: tuple[str, ...],
    yes_type_ids: frozenset[int],
) -> tuple[int, ...]:
    """Translate Y/N/? accepted states to concrete Station.type_id values."""

    states = set(requested_states)
    known_type_ids = set(DISPLAY_NAMES) - {UNKNOWN}
    accepted = set()
    if "?" in states:
        accepted.add(UNKNOWN)
    if "Y" in states:
        accepted.update(yes_type_ids)
    if "N" in states:
        accepted.update(known_type_ids - set(yes_type_ids))
    return tuple(sorted(accepted))


def fetch_station_pair_candidates(
    session: Session,
    source: ResolvedStation,
    destination: ResolvedStation,
    request: RunRequest,
    *,
    available_credits: int,
    classify_zero_result: bool = True,
) -> tuple[TradeCandidate, ...]:
    """Fetch profitable commodities for one source/destination station pair.

    Runs the selective join first. Diagnostic probes to classify source-side
    or destination-side missing data are optional on the zero-result path.
    Matrix callers disable them inside hot loops and aggregate failures after
    the whole endpoint set has been searched. ``available_credits`` is the
    credit budget for the hop's buy step; single-hop callers pass
    ``starting_credits - insurance_reserve``, multi-hop callers pass the
    per-frontier-node budget after the margin haircut.
    """

    source_item = aliased(StationItem)
    destination_item = aliased(StationItem)

    cutoff = _age_cutoff(request.age_days)
    sensitive_category_ids = _effective_sensitive_category_ids(session, request)

    filters = [
        source_item.station_id == source.station_id,
        destination_item.station_id == destination.station_id,
        destination_item.item_id == source_item.item_id,
        source_item.supply_price > 0,
        source_item.supply_units > 0,
        destination_item.demand_price > 0,
        destination_item.demand_units >= _MIN_MEANINGFUL_DEMAND,
        destination_item.demand_price - source_item.supply_price
        >= request.min_gain_per_ton,
        source_item.supply_price <= available_credits,
    ]

    if request.max_gain_per_ton > 0:
        filters.append(
            destination_item.demand_price - source_item.supply_price
            <= request.max_gain_per_ton
        )
    if request.min_supply is not None:
        filters.append(source_item.supply_units >= request.min_supply)
    if request.min_demand is not None:
        filters.append(destination_item.demand_units >= request.min_demand)
    if cutoff is not None:
        filters.append(source_item.modified >= cutoff)
        filters.append(destination_item.modified >= cutoff)
    if request.max_price > 0:
        # Absolute commodity-price cap. Applied row-local on both sides so
        # outlier supply or demand prices cannot leak into candidate rows.
        filters.append(source_item.supply_price <= request.max_price)
        filters.append(destination_item.demand_price <= request.max_price)
    if request.avoid_item_ids:
        # Avoided commodities are never bought. Excluding the buy side removes
        # the whole buy->sell pair (the pair is matched on item_id), so the
        # commodity never enters cargo and is never sold.
        filters.append(source_item.item_id.notin_(request.avoid_item_ids))

    stmt = (
        select(
            source_item.item_id,
            Item.name,
            source_item.supply_price,
            source_item.supply_units,
            source_item.modified,
            destination_item.demand_price,
            destination_item.demand_units,
            destination_item.modified,
            Item.category_id,
        )
        .join(destination_item, destination_item.item_id == source_item.item_id)
        .join(Item, Item.item_id == source_item.item_id)
        .where(and_(*filters))
        .order_by(
            (destination_item.demand_price - source_item.supply_price).desc(),
            Item.name.asc(),
        )
    )

    now_utc = datetime.now(timezone.utc)
    candidates = []
    for row in session.execute(stmt):
        source_age = _age_days(row[4], now_utc=now_utc)
        destination_age = _age_days(row[7], now_utc=now_utc)
        profit_per_unit = int(row[5]) - int(row[2])
        demand_units = int(row[6])
        sensitive = int(row[8]) in sensitive_category_ids
        # floor(demand * 0.25); Python integer division on non-negative
        # ints rounds toward zero, which matches floor for the values
        # here.
        effective_demand = demand_units // 4 if sensitive else demand_units
        if effective_demand <= 0:
            # The bulk-sale cap reduces this Metals/Minerals row to zero
            # safe cargo at the advertised sell price. Buying data is
            # fine, so the empty-result path treats this as "no profitable
            # trade" rather than promoting it to a destination-side data
            # failure.
            continue
        candidates.append(
            TradeCandidate(
                item_id=int(row[0]),
                item_name=str(row[1]),
                source_station_id=source.station_id,
                destination_station_id=destination.station_id,
                buy_price=int(row[2]),
                sell_price=int(row[5]),
                profit_per_unit=profit_per_unit,
                source_supply_units=int(row[3]),
                destination_demand_units=demand_units,
                source_age_days=source_age,
                destination_age_days=destination_age,
                bulk_sale_tax_sensitive=sensitive,
                effective_destination_demand_units=effective_demand,
            )
        )

    if not candidates and classify_zero_result:
        _classify_zero_result_failure(session, source, destination, request, cutoff)

    return tuple(candidates)


def _usable_selling_filters(
    station_clause,
    request: RunRequest,
    cutoff: datetime | None,
) -> list:
    """Filters defining "usable selling data" for the failure probes.

    Shared by the single-pair classifier and the station-set probes so the
    two can never drift apart on what counts as a sellable row.
    """

    filters = [
        station_clause,
        StationItem.supply_price > 0,
        StationItem.supply_units > 0,
    ]
    if request.min_supply is not None:
        filters.append(StationItem.supply_units >= request.min_supply)
    if cutoff is not None:
        filters.append(StationItem.modified >= cutoff)
    if request.max_price > 0:
        # Apply the cap to the failure probe too: a station whose only rows
        # are above the cap genuinely has no usable selling data under the
        # current settings, and the probe must report it consistently.
        filters.append(StationItem.supply_price <= request.max_price)
    if request.avoid_item_ids:
        # Same consistency: a source whose only sellable rows are avoided
        # commodities has no usable selling data under the current settings.
        filters.append(StationItem.item_id.notin_(request.avoid_item_ids))
    return filters


def _usable_buying_filters(
    station_clause,
    request: RunRequest,
    cutoff: datetime | None,
) -> list:
    """Filters defining "usable buying data" — mirror of the selling probe.

    No avoid-commodity arm: --avoid bars the buy side of a trade, so a
    destination's demand rows stay usable whatever the avoid list says.
    """

    filters = [
        station_clause,
        StationItem.demand_price > 0,
        StationItem.demand_units >= _MIN_MEANINGFUL_DEMAND,
    ]
    if request.min_demand is not None:
        filters.append(StationItem.demand_units >= request.min_demand)
    if cutoff is not None:
        filters.append(StationItem.modified >= cutoff)
    if request.max_price > 0:
        # Mirror the supply-side probe: a destination whose only buy rows
        # are above the cap has no usable buying data under the user's
        # settings.
        filters.append(StationItem.demand_price <= request.max_price)
    return filters


def station_set_has_selling_data(
    session: Session,
    station_ids: tuple[int, ...],
    request: RunRequest,
) -> bool:
    """Whether any station in the set has usable selling data.

    One LIMIT-1 probe over the whole set. Matrix planners call this on
    their no-route failure path instead of classifying every zero-result
    pair inside the hot loop; the id set is an endpoint expansion — tens
    of stations at most — so a literal IN is safe.
    """

    if not station_ids:
        return False
    filters = _usable_selling_filters(
        StationItem.station_id.in_(station_ids),
        request,
        _age_cutoff(request.age_days),
    )
    return session.execute(
        select(StationItem.item_id).where(and_(*filters)).limit(1)
    ).first() is not None


def station_set_has_buying_data(
    session: Session,
    station_ids: tuple[int, ...],
    request: RunRequest,
) -> bool:
    """Whether any station in the set has usable buying data.

    Mirror of station_set_has_selling_data for the destination side.
    """

    if not station_ids:
        return False
    filters = _usable_buying_filters(
        StationItem.station_id.in_(station_ids),
        request,
        _age_cutoff(request.age_days),
    )
    return session.execute(
        select(StationItem.item_id).where(and_(*filters)).limit(1)
    ).first() is not None


def _classify_zero_result_failure(
    session: Session,
    source: ResolvedStation,
    destination: ResolvedStation,
    request: RunRequest,
    cutoff: datetime | None,
) -> None:
    """Raise the most specific failure when a station-pair join returns no candidates."""

    source_filters = _usable_selling_filters(
        StationItem.station_id == source.station_id, request, cutoff
    )
    if not session.execute(
        select(StationItem.item_id).where(and_(*source_filters)).limit(1)
    ).first():
        raise SourceHasNoSellingData(
            f"Source station has no usable selling data: {source.dbname}",
            option_name="--from",
            entity_name=source.dbname,
        )

    destination_filters = _usable_buying_filters(
        StationItem.station_id == destination.station_id, request, cutoff
    )
    if not session.execute(
        select(StationItem.item_id).where(and_(*destination_filters)).limit(1)
    ).first():
        raise DestinationHasNoBuyingData(
            f"Destination station has no usable buying data: {destination.dbname}",
            option_name="--to",
            entity_name=destination.dbname,
        )
    # Both sides have qualifying data; zero join result means no profitable intersection.


def _supply_constant_row_filters(request: RunRequest, cutoff):
    """Run-constant supply-side row predicates (rows a station can sell).

    Shared verbatim between the direct per-anchor query and the
    qualification-temp build so the two can never drift apart. Excludes
    the per-hop credit cap, which is anchor-specific.
    """

    filters = [
        StationItem.supply_price > 0,
        StationItem.supply_units > 0,
    ]
    if request.min_supply is not None:
        filters.append(StationItem.supply_units >= request.min_supply)
    if cutoff is not None:
        filters.append(StationItem.modified >= cutoff)
    if request.max_price > 0:
        filters.append(StationItem.supply_price <= request.max_price)
    if request.avoid_item_ids:
        # Avoided commodities are never bought (the buy side of the trade).
        filters.append(StationItem.item_id.notin_(request.avoid_item_ids))
    return filters


def _demand_constant_row_filters(request: RunRequest, cutoff):
    """Run-constant demand-side row predicates (rows a station will buy)."""

    filters = [
        StationItem.demand_price > 0,
        StationItem.demand_units >= _MIN_MEANINGFUL_DEMAND,
    ]
    if request.min_demand is not None:
        filters.append(StationItem.demand_units >= request.min_demand)
    if cutoff is not None:
        filters.append(StationItem.modified >= cutoff)
    if request.max_price > 0:
        filters.append(StationItem.demand_price <= request.max_price)
    return filters


class QualificationCache:
    """Run-scoped, lazily populated market-qualification temps.

    The run-constant row predicates (price/units thresholds, --age,
    --max-price, avoided commodities) give the same answer for a station
    no matter which anchor asks, yet frontier bubbles overlap so heavily
    that the open-ended fetch re-derives those answers many times per
    row. This cache answers them once: the first anchor to reach a
    station qualifies its rows into a run-scoped temp table, and every
    later anchor's pairing query reads the temp instead of re-walking
    StationItem.

    Population is lazy and stays in SQL end to end: a seen-stations temp
    records which stations are already in, each fetch inserts only the
    unseen slice of its bubble (one INSERT...SELECT per side), and no id
    list ever round-trips through Python. With --age set the fresh-
    station set is derived once from the modified-led covering index and
    stale stations are never walked at all; the row-level age predicate
    is still applied during population, so mixed-timestamp stations
    behave exactly as they would under the direct query.

    The age cutoff is frozen at first use so the temps and every
    anchor's query agree on one "now" for the whole run, instead of the
    cutoff drifting with the wall clock across a long search.

    One instance per planning run, created next to the reachable-set
    memo and released the same way (``release``); the temps are
    connection-scoped, so dropping them on the way out mirrors
    release_reachable_memo.
    """

    _SIDES = {
        "supply": ("supply_price", "supply_units"),
        "demand": ("demand_price", "demand_units"),
    }

    def __init__(self) -> None:
        self._metadata = MetaData()
        self._qual: dict[str, Table] = {}
        self._seen: dict[str, Table] = {}
        self._batch: Table | None = None
        self._fresh: Table | None = None
        self._rows_total = {"supply": 0, "demand": 0}
        self._rows_at_analyze = {"supply": -1, "demand": -1}
        self._cutoff_frozen = False
        self._cutoff = None
        # Bubbles fully processed for a side, keyed on (side, reachable
        # memo key). Most expansion calls revisit a bubble an earlier
        # anchor already exhausted; the marker lets them skip the
        # which-stations-are-new check entirely.
        self._processed: set = set()

    def frozen_cutoff(self, request: RunRequest):
        """The run's single --age cutoff, fixed at first use."""

        if not self._cutoff_frozen:
            self._cutoff = _age_cutoff(request.age_days)
            self._cutoff_frozen = True
        return self._cutoff

    def _side_tables(self, connection, side: str) -> tuple[Table, Table]:
        qual = self._qual.get(side)
        if qual is not None:
            return qual, self._seen[side]
        price_column, units_column = self._SIDES[side]
        # Mirrors the StationItem primary key so an IN-driven station
        # lookup runs the same PK search shape as the direct query.
        qual = Table(
            f"td_run_{side}_qual",
            self._metadata,
            Column("station_id", BigInteger, primary_key=True),
            Column("item_id", BigInteger, primary_key=True),
            Column(price_column, Integer),
            Column(units_column, Integer),
            Column("modified", StationItem.__table__.c.modified.type),
            prefixes=["TEMPORARY"],
            sqlite_with_rowid=False,
        )
        seen = Table(
            f"td_run_{side}_qual_seen",
            self._metadata,
            Column("station_id", BigInteger, primary_key=True),
            prefixes=["TEMPORARY"],
        )
        # Drop any leftover from a previous interrupted run, then create.
        qual.drop(connection, checkfirst=True)
        seen.drop(connection, checkfirst=True)
        qual.create(connection)
        seen.create(connection)
        self._qual[side] = qual
        self._seen[side] = seen
        return qual, seen

    def _batch_table(self, connection) -> Table:
        if self._batch is None:
            batch = Table(
                "td_run_qual_batch",
                self._metadata,
                Column("station_id", BigInteger, primary_key=True),
                prefixes=["TEMPORARY"],
            )
            batch.drop(connection, checkfirst=True)
            batch.create(connection)
            self._batch = batch
        return self._batch

    def _fresh_station_select(self, session: Session, cutoff):
        """Station-level --age cut: ids with any row inside the window.

        Built once per run with a single range scan over the
        modified-led covering index; stations outside it are never
        walked during qualification.
        """

        if self._fresh is None:
            fresh = Table(
                "td_run_fresh_stations",
                self._metadata,
                Column("station_id", BigInteger, primary_key=True),
                prefixes=["TEMPORARY"],
            )
            connection = session.connection()
            fresh.drop(connection, checkfirst=True)
            fresh.create(connection)
            session.execute(
                fresh.insert().from_select(
                    ["station_id"],
                    select(StationItem.station_id)
                    .where(StationItem.modified >= cutoff)
                    .distinct(),
                )
            )
            self._fresh = fresh
        return select(self._fresh.c.station_id)

    def ensure_populated(
        self,
        session: Session,
        *,
        side: str,
        station_list: Select,
        request: RunRequest,
        cutoff,
        expansion_stats: ExpansionStats | None = None,
        skip_key: tuple | None = None,
    ) -> Table:
        """Qualify any of ``station_list``'s stations not yet in the temp.

        Returns the side's qual table, ready for the pairing query.
        Stations are marked seen whether or not any of their rows
        qualified — including stations excluded by the --age station cut
        — so no station is ever examined twice.

        ``skip_key``, when supplied, identifies a station list that is a
        pure function of the key (the caller guarantees no per-call
        narrowing): once that list has been processed, later calls with
        the same key return immediately without re-checking for new
        stations.
        """

        if skip_key is not None and skip_key in self._processed:
            return self._qual[side]

        started = time.perf_counter()
        connection = session.connection()
        qual, seen = self._side_tables(connection, side)
        batch = self._batch_table(connection)

        session.execute(batch.delete())
        bubble = station_list.subquery()
        unseen = select(bubble.c.station_id).where(
            ~select(literal(1))
            .where(seen.c.station_id == bubble.c.station_id)
            .exists()
        )
        batched = session.execute(
            batch.insert().from_select(["station_id"], unseen)
        )
        new_stations = int(batched.rowcount or 0)
        rows_added = 0
        if new_stations:
            price_column, units_column = self._SIDES[side]
            row_filters = [
                StationItem.station_id.in_(select(batch.c.station_id)),
            ]
            if cutoff is not None:
                row_filters.append(
                    StationItem.station_id.in_(
                        self._fresh_station_select(session, cutoff)
                    )
                )
            if side == "supply":
                row_filters += _supply_constant_row_filters(request, cutoff)
            else:
                row_filters += _demand_constant_row_filters(request, cutoff)
            inserted = session.execute(
                qual.insert().from_select(
                    ["station_id", "item_id", price_column, units_column,
                     "modified"],
                    select(
                        StationItem.station_id,
                        StationItem.item_id,
                        getattr(StationItem, price_column),
                        getattr(StationItem, units_column),
                        StationItem.modified,
                    ).where(and_(*row_filters)),
                )
            )
            rows_added = int(inserted.rowcount or 0)
            session.execute(
                seen.insert().from_select(
                    ["station_id"], select(batch.c.station_id)
                )
            )
            self._rows_total[side] += rows_added
            # A stats-less temp can invert SQLite's join order (the
            # analyze_temp_table lesson). Re-analyze only when the table
            # has doubled since the last pass so the cost stays bounded
            # across hundreds of small population bursts.
            if (
                self._rows_at_analyze[side] < 0
                or self._rows_total[side] >= 2 * self._rows_at_analyze[side]
            ):
                analyze_temp_table(session, qual)
                self._rows_at_analyze[side] = max(self._rows_total[side], 1)
        if skip_key is not None:
            self._processed.add(skip_key)
        if expansion_stats is not None:
            expansion_stats.qual_stations += new_stations
            expansion_stats.qual_rows += rows_added
            expansion_stats.qual_ms += (time.perf_counter() - started) * 1000.0
        return qual

    def release(self, session: Session) -> None:
        """Drop every temp this cache created; safe on a partial run."""

        connection = session.connection()
        for table in (
            self._fresh,
            self._batch,
            *self._qual.values(),
            *self._seen.values(),
        ):
            if table is not None:
                table.drop(connection, checkfirst=True)
        self._qual.clear()
        self._seen.clear()
        self._batch = None
        self._fresh = None


def _demand_viability_filters(item, request: RunRequest, cutoff) -> list:
    """The bare 'this station has usable demand' row conditions.

    Factored out so onward-viability and loop-root qualification share one
    definition of meaningful demand and cannot drift: price positive, a
    meaningful quantity, plus --demand / --age / --max-price. ``item`` is the
    StationItem entity or alias the caller reads columns from.

    These are the bare conditions only. They deliberately omit the avoided-
    commodity exclusion and the bulk-sale-tax effective-demand floor: onward
    viability does not need them, but loop-root qualification does and adds
    them on top (see fetch_loop_closable_station_ids).
    """

    filters = [
        item.demand_price > 0,
        item.demand_units >= _MIN_MEANINGFUL_DEMAND,
    ]
    if request.min_demand is not None:
        filters.append(item.demand_units >= request.min_demand)
    if cutoff is not None:
        filters.append(item.modified >= cutoff)
    if request.max_price > 0:
        filters.append(item.demand_price <= request.max_price)
    return filters


def _onward_viability_filter(request: RunRequest, cutoff, open_role: str, station_id_column):
    """Correlated EXISTS: the station stays viable for the *next* hop.

    Intermediate frontier nodes must not be one-sided dead ends: an open
    destination (forward) must be able to sell onward, an open source
    (backward) must be able to buy onward. The conditions mirror the
    run-constant row filters for the opposite side verbatim, so this test
    and the qualification temps can never disagree about what "viable"
    means. A correlated EXISTS keeps the database on the StationItem
    primary key. The correlation column is a parameter because the open
    side may read either StationItem directly or the qualification temp.
    """

    onward = aliased(StationItem)
    onward_filters = [onward.station_id == station_id_column]
    if open_role == "source":
        onward_filters += _demand_viability_filters(onward, request, cutoff)
    else:
        onward_filters += [
            onward.supply_price > 0,
            onward.supply_units > 0,
        ]
        if request.min_supply is not None:
            onward_filters.append(onward.supply_units >= request.min_supply)
        if cutoff is not None:
            onward_filters.append(onward.modified >= cutoff)
        if request.max_price > 0:
            onward_filters.append(onward.supply_price <= request.max_price)
        if request.avoid_item_ids:
            # The onward leg here is the next hop's buy, so an avoided
            # commodity must not count toward onward viability either.
            onward_filters.append(
                onward.item_id.notin_(request.avoid_item_ids)
            )
    return select(literal(1)).where(and_(*onward_filters)).exists()


def fetch_loop_closable_station_ids(
    session: Session,
    station_ids: tuple[int, ...],
    request: RunRequest,
) -> frozenset[int]:
    """Return which of the given stations can receive a usable return trade.

    A loop's terminal is its own origin, so a candidate root can only close the
    loop if it is a genuine *destination*: it must demand at least one commodity
    well enough to actually sell into. This qualifies roots before they seed the
    bounded frontier, so a supply-only or otherwise-unclosable root never spends
    a beam slot only to fail at the final hop.

    "Usable demand" mirrors the destination side of fetch_station_pair_candidates
    exactly:
      - the shared meaningful-demand conditions (price, threshold, --demand,
        --age, --max-price), via _demand_viability_filters;
      - avoided commodities excluded -- a root whose only demand is for an
        avoided item cannot be sold to;
      - the bulk-sale-tax effective-demand floor -- a sensitive (Metals/
        Minerals) commodity flooring to floor(demand * 0.25) == 0 sells no safe
        quantity, so it does not count (raw demand must be >= 4).

    It deliberately does NOT check gain-per-ton, credits, or source supply:
    those depend on the eventual source of the return hop, which is unknown at
    root-qualification time.

    The id set is one system's stations (or a single fixed station) -- already
    narrow -- so a parameterised IN (...) is correct and cheap here; this is not
    a galaxy-scale id round-trip.
    """

    if not station_ids:
        return frozenset()

    cutoff = _age_cutoff(request.age_days)
    sensitive_category_ids = _effective_sensitive_category_ids(session, request)

    filters = [
        StationItem.station_id.in_(station_ids),
        *_demand_viability_filters(StationItem, request, cutoff),
    ]
    if request.avoid_item_ids:
        filters.append(StationItem.item_id.notin_(request.avoid_item_ids))

    stmt = select(StationItem.station_id)
    if sensitive_category_ids:
        # Bulk-sale-tax effective-demand floor. A sensitive commodity with raw
        # demand 2 or 3 floors to floor(demand * 0.25) == 0 -- no safe quantity
        # at the advertised price -- so require raw demand >= 4 for sensitive
        # items; non-sensitive items keep the meaningful-demand threshold above.
        # The Item join is only needed to read category_id for this test.
        stmt = stmt.join(Item, Item.item_id == StationItem.item_id)
        filters.append(
            or_(
                Item.category_id.notin_(sensitive_category_ids),
                StationItem.demand_units >= 4,
            )
        )
    stmt = stmt.where(and_(*filters)).distinct()
    return frozenset(int(station_id) for station_id in session.scalars(stmt))


def _build_open_fixed_bounds(
    session: Session,
    open_role: str,
    supply_filters: list,
    demand_filters: list,
):
    """Aggregate the fixed side's per-item price extremes into a temp table.

    The fixed side is one named place — a handful of stations at most — so
    its per-item price extremes are cheap to aggregate, straight into a temp
    table in SQL (no Python round-trip). They become the open side's
    narrowing: an open-side row only survives when the fixed side trades
    that item at all, at a price that could clear --gain-per-ton against
    the fixed side's best price.

    Returns (table, populated). populated False means the fixed endpoint
    has no usable rows under the current filters — nothing can pair, so the
    open-side query never needs to run. The caller owns the drop.
    """

    bounds_temp = Table(
        "td_open_fixed_bounds",
        MetaData(),
        Column("item_id", BigInteger, primary_key=True),
        Column("min_price", Integer),
        Column("max_price", Integer),
        prefixes=["TEMPORARY"],
    )
    connection = session.connection()
    bounds_temp.drop(connection, checkfirst=True)
    bounds_temp.create(connection)
    if open_role == "destination":
        fixed_price = StationItem.supply_price
        fixed_filters = supply_filters
    else:
        fixed_price = StationItem.demand_price
        fixed_filters = demand_filters
    session.execute(
        bounds_temp.insert().from_select(
            ["item_id", "min_price", "max_price"],
            select(
                StationItem.item_id,
                func.min(fixed_price),
                func.max(fixed_price),
            )
            .where(and_(*fixed_filters))
            .group_by(StationItem.item_id),
        )
    )
    return bounds_temp, _temp_has_rows(session, bounds_temp)


# Rows per cursor fetch when streaming the bound-ordered open-side query.
_STREAM_PARTITION_ROWS = 2000


def _station_group_candidates(
    open_rows: list,
    fixed_rows_by_item: dict[int, list],
    *,
    open_role: str,
    min_gain: int,
    max_gain: int,
    item_names: dict[int, str],
    item_categories: dict[int, int],
    sensitive_category_ids: frozenset[int],
    now_utc: datetime,
) -> tuple[TradeCandidate, ...]:
    """Build one open station's TradeCandidates against the fixed side.

    The exact pair tests — self-pair skip, the per-pair gain window, the
    Metals/Minerals bulk-sale cap — applied to the rows of a single open
    station against the fixed side's rows, matched by item. Sorted by
    (-profit_per_unit, item_name), the canonical candidate order.
    """

    candidates = []
    for open_row in open_rows:
        item_id = int(open_row[0])
        fixed_matches = fixed_rows_by_item.get(item_id)
        if not fixed_matches:
            continue
        for fixed_row in fixed_matches:
            if open_role == "destination":
                supply, demand = fixed_row, open_row
            else:
                supply, demand = open_row, fixed_row
            source_station_id = int(supply[1])
            destination_station_id = int(demand[1])
            if destination_station_id == source_station_id:
                # Same-station self-pair, never a valid hop. The fixed and
                # reachable station sets legitimately overlap on a same-
                # system search, so the invariant is enforced per pair.
                continue
            buy_price = int(supply[2])
            sell_price = int(demand[2])
            profit_per_unit = sell_price - buy_price
            if profit_per_unit < min_gain:
                continue
            if max_gain > 0 and profit_per_unit > max_gain:
                continue
            sensitive = item_categories.get(item_id) in sensitive_category_ids
            demand_units = int(demand[3])
            # floor(demand * 0.25); Python integer division on non-negative
            # ints rounds toward zero, matching floor.
            effective_demand = demand_units // 4 if sensitive else demand_units
            if effective_demand <= 0:
                # Bulk-sale cap reduces this Metals/Minerals row to zero safe
                # cargo at the advertised price; drop the pair, not the item.
                continue
            candidates.append(
                TradeCandidate(
                    item_id=item_id,
                    item_name=item_names.get(item_id, ""),
                    source_station_id=source_station_id,
                    destination_station_id=destination_station_id,
                    buy_price=buy_price,
                    sell_price=sell_price,
                    profit_per_unit=profit_per_unit,
                    source_supply_units=int(supply[3]),
                    destination_demand_units=demand_units,
                    source_age_days=_age_days(supply[4], now_utc=now_utc),
                    destination_age_days=_age_days(demand[4], now_utc=now_utc),
                    bulk_sale_tax_sensitive=sensitive,
                    effective_destination_demand_units=effective_demand,
                )
            )
    candidates.sort(key=lambda c: (-c.profit_per_unit, c.item_name))
    return tuple(candidates)


# A via reserved fetch can hand back a large station-id set under --end-jumps:
# the whole expanded terminal region. A literal IN of that many ids risks
# SQLite's bound-parameter ceiling and can knock the query off its index, so
# above this count the set is materialised into a temp table and applied as a
# subquery instead. Small reservations (an exact terminal, a loop root, one
# --to system's eligible set) stay a cheap literal IN.
_RESERVE_IN_LITERAL_MAX = 500


def _build_station_id_temp(
    connection, station_ids, name: str = "td_reserved_stations"
):
    """Materialise a station-id set into a temp table for subquery restriction.

    Returns a freshly created TEMPORARY table holding the supplied ids in one
    indexed station_id column. The caller restricts a query with
    ``column.in_(select(temp.c.station_id))`` instead of a large literal IN, and
    drops the table when the fetch is done. station_id is BigInteger in the ORM,
    so the temp mirrors that to avoid an implicit cast. ``name`` distinguishes
    concurrent restriction temps (fixed side, open side) so they cannot collide.
    """

    metadata = MetaData()
    temp = Table(
        name,
        metadata,
        Column("station_id", BigInteger, primary_key=True),
        prefixes=["TEMPORARY"],
    )
    temp.drop(connection, checkfirst=True)
    temp.create(connection)
    connection.execute(
        temp.insert(),
        [{"station_id": int(sid)} for sid in station_ids],
    )
    return temp


def build_open_restriction(connection, station_ids):
    """Build a reusable open-side station restriction for the streaming fetch.

    Returns ``(temp_or_none, kwargs)`` to splat into
    iter_open_ended_station_groups. A large set is materialised once into a temp
    table and passed as a subquery — reused across many streams, e.g. the
    one-hop matrix's destination set applied against each source-system stream
    rather than rebuilt each time. A small set stays a cheap literal IN. The
    caller drops the returned temp (if any) once every stream is done.
    """

    if len(station_ids) > _RESERVE_IN_LITERAL_MAX:
        temp = _build_station_id_temp(
            connection, station_ids, name="td_onehop_destinations"
        )
        return temp, {
            "restrict_open_station_subquery": select(temp.c.station_id),
        }
    return None, {"restrict_open_station_ids": frozenset(station_ids)}


def iter_open_ended_station_groups(
    session: Session,
    fixed_station_ids: tuple[int, ...],
    anchor_system: ResolvedSystem,
    request: RunRequest,
    *,
    open_role: str,
    available_credits: int,
    unbounded_credits: bool = False,
    terminal_hop: bool = True,
    reachable_memo: dict | None = None,
    destination_envelope_xyz: tuple[float, float, float] | None = None,
    destination_envelope_ly: float | None = None,
    restrict_open_station_ids: frozenset[int] | None = None,
    restrict_open_station_subquery=None,
    expansion_stats: ExpansionStats | None = None,
    precomputed_reachable_systems: tuple[ResolvedSystem, ...] | None = None,
    qualification: QualificationCache | None = None,
) -> Iterator[tuple[int, int, tuple[TradeCandidate, ...]]]:
    """Stream per-station candidate groups, best open station first.

    The open-ended candidate fetch: every profitable trade between a fixed
    endpoint and the stations reachable from the anchor, streamed grouped
    by open station, stations ordered by descending ceiling — the station's
    best optimistic profit per unit, computed in SQL against the fixed
    side's per-item price extremes (the bounds temp, joined 1:1 on its item
    primary key). The consumer may stop iterating — close the generator —
    once the next ceiling cannot beat what it already holds; rows past that
    point are never read off the cursor, never converted, never paired.

    Yields (station_id, ceiling_ppu, candidates):

    - ceiling_ppu is an upper bound on the per-unit profit of any pair this
      station could form (multiply by capacity for a raw-profit ceiling).
      Ceilings are non-increasing across the stream.
    - candidates is the station's TradeCandidate tuple, sorted
      (-profit_per_unit, item_name); it may span several pairs when the
      fixed endpoint has several stations. Stations whose rows produce no
      candidates are skipped, which only tightens the ceiling sequence.

    Exact: an exhausted stream yields every candidate the filters admit —
    the bounds join and ceiling are necessary-condition narrowing and
    ordering only — and a stopped stream omits only stations whose ceiling
    the consumer proved unbeatable. No ordering, scoring, or selection
    decisions are made here.

    Onward viability (non-terminal hops) is answered per station from the
    opposite side's qualification temp when a cache is supplied — the
    temp's row predicates are the onward conditions, shared verbatim, so a
    station has rows there exactly when the per-row EXISTS would pass.
    The temp is populated for this bubble on first need and amortises
    across every anchor that shares it. Without a cache the per-row
    correlated EXISTS applies, unchanged.

    Everything else is the established fetch contract: spatial narrowing
    via the reachable temp, the credit cap on the buy side, the
    qualification temps for the run-constant predicates, the
    destination-envelope restriction, and empty-result classification left
    to the caller. ``unbounded_credits`` drops the buy-side credit cap for the
    no-affordability optimistic pass (the via search), so an expensive row is
    not hidden before its price is seen. ``restrict_open_station_ids`` narrows
    the open side to a given station set for the via search's targeted reserved
    fetch (reachable intersected with the required stations).
    """

    fetch_started = time.perf_counter()

    def _charge_fetch():
        # Attribute generator-side work to the fetch phase; consumer time
        # between yields is excluded by resetting the mark on resume.
        nonlocal fetch_started
        if expansion_stats is not None:
            expansion_stats.fetch_ms += (
                time.perf_counter() - fetch_started
            ) * 1000.0
        fetch_started = time.perf_counter()

    with _reachable_station_query(
        session,
        anchor_system,
        request,
        reachable_memo=reachable_memo,
        destination_envelope_xyz=destination_envelope_xyz,
        destination_envelope_ly=destination_envelope_ly,
        expansion_stats=expansion_stats,
        precomputed_systems=precomputed_reachable_systems,
    ) as reachable_query:
        connection = session.connection()
        # The fixed side restricts by a literal IN, or a temp-backed subquery
        # when the set is large enough to risk SQLite's parameter ceiling or to
        # knock the query off the station index — e.g. the one-hop matrix groups
        # its fixed source side by system, and a single system can hold many
        # stations. Dropped in the finally below.
        fixed_temp = None
        if len(fixed_station_ids) > _RESERVE_IN_LITERAL_MAX:
            fixed_temp = _build_station_id_temp(
                connection, fixed_station_ids, name="td_fixed_stations"
            )
            fixed_clause = StationItem.station_id.in_(
                select(fixed_temp.c.station_id)
            )
        else:
            fixed_clause = StationItem.station_id.in_(fixed_station_ids)
        if open_role == "source":
            supply_station_filter = StationItem.station_id.in_(reachable_query)
            demand_station_filter = fixed_clause
        else:
            supply_station_filter = fixed_clause
            demand_station_filter = StationItem.station_id.in_(reachable_query)

        if qualification is not None:
            cutoff = qualification.frozen_cutoff(request)
        else:
            cutoff = _age_cutoff(request.age_days)
        sensitive_category_ids = _effective_sensitive_category_ids(session, request)

        supply_filters = [supply_station_filter]
        if not unbounded_credits:
            # The buy side is capped by what the commander can afford. The
            # no-affordability optimistic pass drops the cap so an expensive row
            # (e.g. under --max-price 0) is still returned; real credits re-enter
            # at the forward correction.
            supply_filters.append(StationItem.supply_price <= available_credits)
        supply_filters.extend(_supply_constant_row_filters(request, cutoff))
        demand_filters = [
            demand_station_filter,
            *_demand_constant_row_filters(request, cutoff),
        ]

        min_gain = request.min_gain_per_ton
        max_gain = request.max_gain_per_ton
        bounds_temp, bounds_populated = _build_open_fixed_bounds(
            session, open_role, supply_filters, demand_filters
        )
        # A large open-side restriction set is materialised once into a temp
        # table (see _build_station_id_temp) and dropped in the finally below.
        reserve_temp = None
        try:
            if not bounds_populated:
                # Fixed endpoint has no usable rows — nothing can pair.
                _charge_fetch()
                return

            # The fixed side is one named place, small: read it in full and
            # index by item for the per-station pairing.
            if open_role == "destination":
                fixed_query = select(
                    StationItem.item_id,
                    StationItem.station_id,
                    StationItem.supply_price,
                    StationItem.supply_units,
                    StationItem.modified,
                ).where(and_(*supply_filters))
            else:
                fixed_query = select(
                    StationItem.item_id,
                    StationItem.station_id,
                    StationItem.demand_price,
                    StationItem.demand_units,
                    StationItem.modified,
                ).where(and_(*demand_filters))
            fixed_rows = session.execute(fixed_query).all()
            if not fixed_rows:
                _charge_fetch()
                return

            fixed_rows_by_item: dict[int, list] = {}
            for row in fixed_rows:
                fixed_rows_by_item.setdefault(int(row[0]), []).append(row)

            # Every candidate's item exists on both sides of the pair, so
            # the fixed side's (small) item set covers the name/category
            # lookups for all candidates built below.
            item_names: dict[int, str] = {}
            item_categories: dict[int, int] = {}
            for item_id, name, category_id in session.execute(
                select(Item.item_id, Item.name, Item.category_id).where(
                    Item.item_id.in_(tuple(fixed_rows_by_item))
                )
            ).all():
                item_names[int(item_id)] = str(name)
                item_categories[int(item_id)] = int(category_id)

            # Open side: the qualification temp when a cache is supplied
            # (run-constant predicates applied at population), raw
            # StationItem otherwise.
            if qualification is not None:
                open_side = "supply" if open_role == "source" else "demand"
                skip_key = None
                if (
                    destination_envelope_xyz is None
                    and destination_envelope_ly is None
                    and request.towards_target is None
                ):
                    skip_key = (
                        open_side,
                        _reachable_memo_key(anchor_system, request),
                    )
                open_qual = qualification.ensure_populated(
                    session,
                    side=open_side,
                    station_list=reachable_query,
                    request=request,
                    cutoff=cutoff,
                    expansion_stats=expansion_stats,
                    skip_key=skip_key,
                )
                open_entity = open_qual
                station_column = open_qual.c.station_id
                item_column = open_qual.c.item_id
                modified_column = open_qual.c.modified
                if open_role == "source":
                    price_column = open_qual.c.supply_price
                    units_column = open_qual.c.supply_units
                else:
                    price_column = open_qual.c.demand_price
                    units_column = open_qual.c.demand_units
                open_filters = [station_column.in_(reachable_query)]
                if open_role == "source" and not unbounded_credits:
                    open_filters.append(price_column <= available_credits)
            else:
                open_entity = StationItem
                station_column = StationItem.station_id
                item_column = StationItem.item_id
                modified_column = StationItem.modified
                if open_role == "source":
                    price_column = StationItem.supply_price
                    units_column = StationItem.supply_units
                    open_filters = list(supply_filters)
                else:
                    price_column = StationItem.demand_price
                    units_column = StationItem.demand_units
                    open_filters = list(demand_filters)

            if restrict_open_station_subquery is not None:
                # The caller built and owns a restriction temp once and passes
                # its subquery — the one-hop matrix's destination set, reused
                # across every source-system stream rather than rebuilt each
                # time. Applied directly as a subquery membership test.
                open_filters.append(
                    station_column.in_(restrict_open_station_subquery)
                )
            elif restrict_open_station_ids is not None:
                # Targeted reserved fetch: the via owner restricts the open side
                # to the specific stations it must retain (an owed station via,
                # the exact terminal, the loop root, or a --to / expanded
                # terminal set). reachable ∩ required, so an out-of-range
                # required station simply yields no candidate. Same
                # qualification, cutoff and affordability rules as the ordinary
                # stream. A large set (the --end-jumps expanded terminal region)
                # goes through a temp-backed subquery rather than a literal IN,
                # which would risk SQLite's parameter ceiling and the index.
                if len(restrict_open_station_ids) > _RESERVE_IN_LITERAL_MAX:
                    reserve_temp = _build_station_id_temp(
                        connection, restrict_open_station_ids
                    )
                    open_filters.append(
                        station_column.in_(select(reserve_temp.c.station_id))
                    )
                else:
                    open_filters.append(
                        station_column.in_(restrict_open_station_ids)
                    )

            if not terminal_hop:
                if qualification is not None:
                    # Onward viability is a per-station fact; the opposite
                    # side's qualification temp holds a station's rows
                    # exactly when the per-row EXISTS would pass, so a
                    # semi-join against it answers once per station what
                    # the EXISTS re-derived per row.
                    other_side = (
                        "demand" if open_role == "source" else "supply"
                    )
                    other_skip = None
                    if (
                        destination_envelope_xyz is None
                        and destination_envelope_ly is None
                        and request.towards_target is None
                    ):
                        other_skip = (
                            other_side,
                            _reachable_memo_key(anchor_system, request),
                        )
                    other_qual = qualification.ensure_populated(
                        session,
                        side=other_side,
                        station_list=reachable_query,
                        request=request,
                        cutoff=cutoff,
                        expansion_stats=expansion_stats,
                        skip_key=other_skip,
                    )
                    open_filters.append(
                        station_column.in_(select(other_qual.c.station_id))
                    )
                else:
                    open_filters.append(
                        _onward_viability_filter(
                            request, cutoff, open_role, station_column
                        )
                    )

            # Per-row optimistic profit against the fixed side's best price,
            # with the interval-overlap necessary conditions inlined on the
            # 1:1 bounds join (the EXISTS shape, expressed as a join so the
            # bound is available to order by). The exact per-pair gain test
            # still runs in the pairing step.
            if open_role == "destination":
                bounds_conditions = [
                    price_column >= bounds_temp.c.min_price + min_gain,
                ]
                if max_gain > 0:
                    bounds_conditions.append(
                        price_column <= bounds_temp.c.max_price + max_gain
                    )
                opt_ppu = price_column - bounds_temp.c.min_price
            else:
                bounds_conditions = [
                    price_column <= bounds_temp.c.max_price - min_gain,
                ]
                if max_gain > 0:
                    bounds_conditions.append(
                        price_column >= bounds_temp.c.min_price - max_gain
                    )
                opt_ppu = bounds_temp.c.max_price - price_column

            ceiling = func.max(opt_ppu).over(partition_by=station_column)
            open_query = (
                select(
                    item_column,
                    station_column,
                    price_column,
                    units_column,
                    modified_column,
                    ceiling.label("ceiling_ppu"),
                )
                .select_from(open_entity)
                .join(bounds_temp, bounds_temp.c.item_id == item_column)
                .where(and_(*open_filters, *bounds_conditions))
                .order_by(ceiling.desc(), station_column)
            )

            now_utc = datetime.now(timezone.utc)
            result = session.execute(
                open_query.execution_options(
                    yield_per=_STREAM_PARTITION_ROWS
                )
            )
            try:
                pending_station: int | None = None
                pending_ceiling = 0
                pending_rows: list = []
                for partition in result.partitions():
                    if expansion_stats is not None:
                        expansion_stats.stream_rows_read += len(partition)
                    for row in partition:
                        station_id = int(row[1])
                        if (
                            pending_station is not None
                            and station_id != pending_station
                        ):
                            group = _station_group_candidates(
                                pending_rows,
                                fixed_rows_by_item,
                                open_role=open_role,
                                min_gain=min_gain,
                                max_gain=max_gain,
                                item_names=item_names,
                                item_categories=item_categories,
                                sensitive_category_ids=sensitive_category_ids,
                                now_utc=now_utc,
                            )
                            pending_rows = []
                            if group:
                                _charge_fetch()
                                yield pending_station, pending_ceiling, group
                                fetch_started = time.perf_counter()
                        pending_station = station_id
                        pending_ceiling = int(row[5])
                        pending_rows.append(row)
                if pending_rows and pending_station is not None:
                    group = _station_group_candidates(
                        pending_rows,
                        fixed_rows_by_item,
                        open_role=open_role,
                        min_gain=min_gain,
                        max_gain=max_gain,
                        item_names=item_names,
                        item_categories=item_categories,
                        sensitive_category_ids=sensitive_category_ids,
                        now_utc=now_utc,
                    )
                    if group:
                        _charge_fetch()
                        yield pending_station, pending_ceiling, group
                        fetch_started = time.perf_counter()
            finally:
                result.close()
            _charge_fetch()
        finally:
            bounds_temp.drop(connection, checkfirst=True)
            if reserve_temp is not None:
                reserve_temp.drop(connection, checkfirst=True)
            if fixed_temp is not None:
                fixed_temp.drop(connection, checkfirst=True)


def any_reachable_station_pair(
    session: Session,
    anchor_system: ResolvedSystem,
    request: RunRequest,
    fixed_station_ids: tuple[int, ...],
) -> bool:
    """Return whether a reachable station can form a non-self pair.

    This separates two empty open-ended searches: reachable stations exist but
    yield no profitable trade, versus no valid station pair being reachable at
    all. The question is pair existence, not station existence — does some
    reachable station differ in id from some fixed station.

    With two or more fixed stations any reachable station satisfies it: even
    if the reachable station is itself one of the fixed stations, it pairs
    with a different fixed station. With exactly one fixed station, a reachable
    station qualifies only if it is not that station, so the sole fixed id is
    excluded from the probe.
    """

    with _reachable_station_query(session, anchor_system, request) as reachable_query:
        if len(fixed_station_ids) == 1:
            reachable_query = reachable_query.where(
                Station.station_id != fixed_station_ids[0]
            )
        return session.execute(reachable_query.limit(1)).first() is not None


def fetch_stations_by_id(
    session: Session,
    station_ids: tuple[int, ...],
    *,
    cache: dict[int, ResolvedStation] | None = None,
) -> dict[int, ResolvedStation]:
    """Fetch ResolvedStation DTOs for a set of station ids, keyed by id.

    Used to materialise the destination stations that actually appear in
    open-ended trade candidates, so reachable stations with no profitable
    trade are never loaded into planner space.

    ``cache`` is a run-scoped DTO store: frontier expansion rediscovers the
    same stations across layers and neighbouring nodes, and the DTOs are
    immutable for the run, so with a cache supplied only ids not yet seen
    touch the database. The returned dict still covers exactly the requested
    ids that exist.
    """

    if not station_ids:
        return {}

    if cache is None:
        missing = station_ids
    else:
        missing = tuple(
            station_id for station_id in station_ids if station_id not in cache
        )
        if not missing:
            return {
                station_id: cache[station_id]
                for station_id in station_ids
                if station_id in cache
            }

    stmt = (
        select(Station, System)
        .join(System, System.system_id == Station.system_id)
        .where(Station.station_id.in_(missing))
    )
    stations: dict[int, ResolvedStation] = {}
    for station, system in session.execute(stmt):
        resolved_system = ResolvedSystem(
            system_id=int(system.system_id),
            name=str(system.name),
            dbname=str(system.name),
            x=float(system.pos_x),
            y=float(system.pos_y),
            z=float(system.pos_z),
        )
        stations[int(station.station_id)] = _resolved_station_from_model(
            station,
            resolved_system,
        )
    if cache is None:
        return stations
    cache.update(stations)
    return {
        station_id: cache[station_id]
        for station_id in station_ids
        if station_id in cache
    }


# Per commodity the unanchored search keeps at most this many of the
# highest-profit reachable system pairs. The match query ranks by gross
# profit-per-unit and takes this top slice; together with the per-commodity
# cutoff it holds the materialised candidate set far below a galaxy-wide scan.
_UNANCHORED_MATCH_LIMIT = 50


@dataclass(frozen=True, slots=True)
class UnanchoredCounters:
    """Instrumentation counters from one unanchored search run.

    Examined counts pairs that survived the SQL direct-distance prefilter;
    accepted counts those whose reachability check then passed. Bubble
    systems is the per-request bubble cache size at end-of-run; cap hits is
    the number of commodities that hit the per-commodity cap before the
    stream exhausted. These ride alongside wall-clock measurement so a
    regression is diagnosable without re-instrumenting.
    """

    pairs_examined: int = 0
    pairs_accepted: int = 0
    bubble_systems: int = 0
    per_commodity_cap_hits: int = 0


def fetch_unanchored_trade_candidates(
    session: Session,
    request: RunRequest,
    bubble_cache: dict[int, object],
) -> tuple[tuple[TradeCandidate, ...], UnanchoredCounters]:
    """Fetch the bounded best-trade candidate set for an unanchored search.

    Neither endpoint is named, so the search is galaxy-wide and cannot
    materialise every profitable trade. The query is exhaustive in
    consideration but bounded in materialisation:

      1. Each commodity is reduced, supply and demand separately, to its best
         price per system, carrying the station that achieves it.
      2. For --jumps-per 0 the two reductions are matched by same-system
         equality and the top slice is kept.
      3. For --jumps-per >= 1 the SQL pair query prefilters by direct
         distance (bbox + sphere at --jumps-per * --ly-per) and streams
         the candidate cursor; each row's actual reachability is then
         checked via the shared bubble cache, accepting up to the per-
         commodity cap.

    Commodities are walked in descending order of their galaxy-wide
    profit-per-unit bound. A pair's total profit cannot exceed
    capacity x best-profit-per-unit, so once a concrete trade of total profit
    T has been seen, any commodity whose capacity x bound is at or below T
    can win nothing and the walk stops — a single pass, since the order is
    descending. The reductions keep the candidate set in SQL; only the
    bounded slice per surviving commodity crosses into Python.

    The earlier reach map (all ordered pairs in --ly-per range) is gone: at
    multi-jump in dense space it grows to hundreds of millions of rows. The
    direct-distance prefilter plus on-demand reach via the reachability
    bubble cache replaces it without ever materialising a multi-jump pair set.
    """

    available_credits = int(request.starting_credits or 0) - request.insurance_reserve
    cutoff = _age_cutoff(request.age_days)
    sensitive_item_ids = _effective_sensitive_item_ids(session, request)
    capacity = int(request.capacity_units or 0)
    per_item_limit = request.cargo_limit_per_item
    same_system = request.max_jumps_per_hop == 0
    max_ly = float(request.max_ly_per_jump or 0.0)
    max_jumps = int(request.max_jumps_per_hop or 0)
    l_max = max_jumps * max_ly
    l_max_sq = l_max * l_max

    metadata = MetaData()
    modified_type = StationItem.__table__.c.modified.type
    # System and station identifiers are BigInteger in the ORM; the temp tables
    # mirror that. SQLite shrugs at the narrower type but MariaDB's INT is
    # 32-bit signed, and live Elite IDs already exceed that range.
    supply_temp = Table(
        "td_unanchored_supply",
        metadata,
        Column("system_id", BigInteger),
        Column("station_id", BigInteger),
        Column("supply_price", Integer),
        Column("supply_units", Integer),
        Column("modified", modified_type),
        prefixes=["TEMPORARY"],
    )
    demand_temp = Table(
        "td_unanchored_demand",
        metadata,
        Column("system_id", BigInteger),
        Column("station_id", BigInteger),
        Column("demand_price", Integer),
        Column("demand_units", Integer),
        # Raw demand_units stays unchanged for display and post-walk
        # processing; effective_demand_units carries the bulk-sale-tax
        # cap (floor(demand * 0.25) for Metals/Minerals, raw otherwise)
        # so the realisable-profit ranking can read it directly without
        # an inline CASE per row.
        Column("effective_demand_units", Integer),
        Column("modified", modified_type),
        Index("ix_td_unanchored_demand_sys", "system_id"),
        prefixes=["TEMPORARY"],
    )
    # Stations that pass the request's attribute filters (pad size, planetary,
    # fleet carrier, ...), reduced once for the whole walk. The bounds
    # aggregates and both per-item reductions drive from this instead of
    # re-deriving the filter set from Station for every commodity; it also
    # carries the system_id the reductions partition by. The primary key
    # doubles as the probe index for the per-row station_id lookups.
    qualifying = Table(
        "td_unanchored_qual",
        metadata,
        Column("station_id", BigInteger, primary_key=True),
        Column("system_id", BigInteger),
        prefixes=["TEMPORARY"],
    )

    connection = session.connection()
    # Tune the connection for bulk work: temp tables in memory and a larger
    # page cache on SQLite, session-scoped commit and lock tuning on MariaDB.
    begin_bulk_mode(session)
    _create_unanchored_temps(connection, supply_temp, demand_temp, qualifying)

    pairs_examined = 0
    pairs_accepted = 0
    cap_hits = 0
    try:
        # The station-attribute filters stay defined once, in
        # _station_attribute_predicates; this reduces Station to the
        # qualifying (station_id, system_id) pairs every later stage drives
        # from. ANALYZE hands the optimiser the temp's real cardinality so
        # the per-item reductions get sane join plans.
        session.execute(
            qualifying.insert().from_select(
                ["station_id", "system_id"],
                select(Station.station_id, Station.system_id).where(
                    and_(*_station_attribute_predicates(request))
                ),
            )
        )
        analyze_temp_table(session, qualifying)

        item_bounds, item_names = _unanchored_item_bounds(
            session, qualifying, request, available_credits, cutoff
        )
        if request.avoid_item_ids:
            # Avoided commodities are never bought, so drop them from the
            # candidate item set before any per-item supply/demand work. The
            # match helpers read the supply temp, so they inherit the exclusion.
            item_bounds = [
                bound for bound in item_bounds
                if bound[0] not in request.avoid_item_ids
            ]

        candidates: list[TradeCandidate] = []
        best_total_profit = 0
        for item_id, profit_bound in item_bounds:
            # Descending bound order: once capacity x bound cannot beat the
            # best concrete trade seen, no later commodity can either.
            if capacity * profit_bound <= best_total_profit:
                break
            is_sensitive = item_id in sensitive_item_ids
            _reduce_supply_by_system(
                session,
                qualifying,
                supply_temp,
                item_id,
                request,
                available_credits,
                cutoff,
            )
            _reduce_demand_by_system(
                session, qualifying, demand_temp, item_id, request, cutoff,
                is_sensitive,
            )

            if same_system:
                rows = _match_same_system_trades(
                    session, supply_temp, demand_temp, request
                )
                accepted_for_item = len(rows)
            else:
                # The multi-jump match runs into two SQLite cost-model
                # failures without temp-table stats: an empty side
                # stalls the System x System cross-join plan for ~5
                # minutes per walk before returning zero rows, and
                # even non-empty temps get the wrong join order
                # because the planner has no cardinality to weigh
                # against System's ~80K rows. Skip the match when
                # either side is empty, then ANALYZE the populated
                # temps so the planner anchors on them.
                if not (
                    _temp_has_rows(session, supply_temp)
                    and _temp_has_rows(session, demand_temp)
                ):
                    rows = []
                    examined = 0
                    accepted_for_item = 0
                    hit_cap = False
                else:
                    analyze_temp_table(session, supply_temp)
                    analyze_temp_table(session, demand_temp)
                    rows, examined, accepted_for_item, hit_cap = (
                        _match_via_on_demand_reach(
                            session,
                            supply_temp,
                            demand_temp,
                            request,
                            bubble_cache,
                            l_max,
                            l_max_sq,
                        )
                    )
                pairs_examined += examined
                if hit_cap:
                    cap_hits += 1
            pairs_accepted += accepted_for_item

            for row in rows:
                candidate = _unanchored_candidate_from_row(
                    row, item_id, item_names.get(item_id, ""), is_sensitive
                )
                candidates.append(candidate)
                best_total_profit = max(
                    best_total_profit,
                    _concrete_total_profit(
                        candidate, capacity, available_credits, per_item_limit
                    ),
                )
        return (
            tuple(candidates),
            UnanchoredCounters(
                pairs_examined=pairs_examined,
                pairs_accepted=pairs_accepted,
                bubble_systems=len(bubble_cache),
                per_commodity_cap_hits=cap_hits,
            ),
        )
    finally:
        # A ^C deep inside SQLite can leave the session's transaction in a
        # broken state, so the cleanup DROPs below would then raise their own
        # exception and mask the original KeyboardInterrupt. Swallow any
        # cleanup failure: the temp tables are session-scoped and the run is
        # being torn down anyway.
        try:
            _drop_unanchored_temps(
                connection, supply_temp, demand_temp, qualifying
            )
        except Exception:
            pass


def _create_unanchored_temps(
    connection, supply_temp, demand_temp, qualifying
) -> None:
    """Create the run-scoped temporary tables, replacing any stale leftovers."""

    qualifying.drop(connection, checkfirst=True)
    demand_temp.drop(connection, checkfirst=True)
    supply_temp.drop(connection, checkfirst=True)
    supply_temp.create(connection)
    demand_temp.create(connection)
    qualifying.create(connection)


def _drop_unanchored_temps(
    connection, supply_temp, demand_temp, qualifying
) -> None:
    """Drop the run-scoped temporary tables once the search has finished."""

    qualifying.drop(connection, checkfirst=True)
    demand_temp.drop(connection, checkfirst=True)
    supply_temp.drop(connection, checkfirst=True)


def _temp_has_rows(session: Session, temp_table: Table) -> bool:
    """O(1) emptiness check on a run-scoped temp table.

    SQLite's planner falls back to a default-cardinality heuristic for
    tables it has no stats on, and the resulting plan for the
    unanchored multi-jump match can stall for minutes per empty walk
    on the live data before returning zero rows. Caller uses this to
    skip the match step when either side is empty.
    """

    return session.execute(
        text(f"SELECT 1 FROM {temp_table.name} LIMIT 1")
    ).first() is not None


def _bounds_aggregate(
    session: Session,
    qualifying_name: str,
    join_kw: str,
    *,
    aggregate: str,
    price_column: str,
    units_column: str,
    units_floor: int,
    price_ceiling: int | None,
    min_units: int | None,
    cutoff: datetime | None,
    max_price: int,
) -> dict[int, int]:
    """Aggregate one per-item price bound over the qualifying stations.

    Drives from the qualifying-station temp (``join_kw`` pins that order on
    either backend) and probes StationItem by primary key, so it reads only the
    qualifying stations' market rows rather than scanning the whole market
    table. ``aggregate`` is MIN for the cheapest supply, MAX for the dearest
    demand. Returns ``{item_id: bounding price}``.

    The per-row predicates mirror what the per-commodity reductions apply, so
    the bound stays admissible (see _unanchored_item_bounds). They are
    StationItem columns only -- the station-attribute filters are already baked
    into the qualifying temp.
    """

    clauses = [
        "si.station_id = q.station_id",
        f"si.{price_column} > 0",
        f"si.{units_column} >= :units_floor",
    ]
    params: dict[str, object] = {"units_floor": units_floor}
    if price_ceiling is not None:
        clauses.append(f"si.{price_column} <= :ceiling")
        params["ceiling"] = price_ceiling
    if min_units is not None:
        clauses.append(f"si.{units_column} >= :min_units")
        params["min_units"] = min_units
    if max_price and max_price > 0:
        clauses.append(f"si.{price_column} <= :max_price")
        params["max_price"] = max_price
    typed_binds = []
    if cutoff is not None:
        clauses.append("si.modified >= :cutoff")
        params["cutoff"] = cutoff
        # Bind through the column's own type so the datetime renders the way the
        # ORM stores it, whatever the backend.
        typed_binds.append(
            bindparam("cutoff", type_=StationItem.__table__.c.modified.type)
        )

    statement = text(
        f"SELECT si.item_id AS item_id, "
        f"{aggregate}(si.{price_column}) AS bound "
        f"FROM {qualifying_name} q {join_kw} {StationItem.__table__.name} si "
        f"WHERE {' AND '.join(clauses)} "
        f"GROUP BY si.item_id"
    )
    if typed_binds:
        statement = statement.bindparams(*typed_binds)
    return {
        int(item_id): int(bound)
        for item_id, bound in session.execute(statement, params)
    }


def _unanchored_item_bounds(
    session: Session,
    qualifying: Table,
    request: RunRequest,
    available_credits: int,
    cutoff: datetime | None,
) -> tuple[list[tuple[int, int]], dict[int, str]]:
    """Return per-commodity profit-per-unit bounds, highest first, with names.

    The bound is the dearest demand price minus the cheapest supply price for
    the commodity. It still ignores reachability — the pairing between a supply
    system and a demand system — so it stays a true upper bound on any
    reachable trade's profit-per-unit, which is what the walk's cutoff requires.

    It applies the same per-row filters the per-commodity reductions apply:
    stock present and affordable on the supply side, a meaningful buyer on the
    demand side, the station-attribute filters (pad size, planetary, fleet
    carrier, ...), the age cutoff, and --max-price. Every one only ever removes
    rows, which can only push a bound down, so the result stays an upper bound
    on achievable profit-per-unit. Matching the reductions matters: a bound
    blind to these filters stays sky-high on stations the real walk has
    excluded — a fleet carrier's wild price, say — so the early-cutoff never
    fires and the walk grinds through commodities that cannot win.

    The station-attribute filters live on Station, not on the market rows, so
    they are applied once: the caller reduces Station into the run-scoped
    ``qualifying`` temp (already populated here), and the two price aggregates
    read only those stations' market rows. The aggregate is forced to drive
    from that small temp (force_order_join); left to itself the optimiser
    scans all ~11M market rows and seeks the station per row, instead of
    scanning the ~14% of stations that qualify and seeking their market rows
    — measured ~60x slower.

    The demand floor here is the uniform _MIN_MEANINGFUL_DEMAND; the reductions
    raise it to 4 for bulk-sale-tax-sensitive items, but using the looser floor
    keeps this one grouped query and a looser floor is still admissible.
    """

    join_kw = force_order_join(session)
    min_supply = _bounds_aggregate(
        session,
        qualifying.name,
        join_kw,
        aggregate="MIN",
        price_column="supply_price",
        units_column="supply_units",
        units_floor=1,
        price_ceiling=available_credits,
        min_units=request.min_supply,
        cutoff=cutoff,
        max_price=request.max_price,
    )
    max_demand = _bounds_aggregate(
        session,
        qualifying.name,
        join_kw,
        aggregate="MAX",
        price_column="demand_price",
        units_column="demand_units",
        units_floor=_MIN_MEANINGFUL_DEMAND,
        price_ceiling=None,
        min_units=request.min_demand,
        cutoff=cutoff,
        max_price=request.max_price,
    )
    bounds: list[tuple[int, int]] = []
    for item_id, supply_price in min_supply.items():
        demand_price = max_demand.get(item_id)
        if demand_price is None:
            continue
        profit_bound = demand_price - supply_price
        if profit_bound > 0:
            bounds.append((item_id, profit_bound))
    bounds.sort(key=lambda entry: entry[1], reverse=True)

    item_names = {
        int(item_id): str(name)
        for item_id, name in session.execute(select(Item.item_id, Item.name))
    }
    return bounds, item_names


def _reduce_supply_by_system(
    session: Session,
    qualifying: Table,
    supply_temp: Table,
    item_id: int,
    request: RunRequest,
    available_credits: int,
    cutoff: datetime | None,
) -> None:
    """Reduce one commodity's supply to the cheapest eligible station per system.

    Each system keeps one representative supplier: the cheapest, with station
    id as a deterministic tie-break. ROW_NUMBER ranks the eligible stations
    within each system and the outer query keeps rank one. This is standard
    SQL — it relies on no single backend's handling of non-grouped columns —
    so the reduction behaves identically whichever database is in use.

    Station eligibility comes from the run-scoped ``qualifying`` temp — the
    station-attribute filters were applied once when it was populated, so
    the per-item join is a primary-key probe rather than a Station join
    with the whole predicate set re-evaluated per commodity. The temp also
    carries the system_id the ranking partitions by.
    """

    session.execute(supply_temp.delete())

    filters = [
        StationItem.item_id == item_id,
        StationItem.supply_price > 0,
        StationItem.supply_units > 0,
        StationItem.supply_price <= available_credits,
    ]
    if request.min_supply is not None:
        filters.append(StationItem.supply_units >= request.min_supply)
    if cutoff is not None:
        filters.append(StationItem.modified >= cutoff)
    if request.max_price > 0:
        filters.append(StationItem.supply_price <= request.max_price)

    ranked = (
        select(
            qualifying.c.system_id.label("system_id"),
            StationItem.station_id.label("station_id"),
            StationItem.supply_price.label("supply_price"),
            StationItem.supply_units.label("supply_units"),
            StationItem.modified.label("modified"),
            func.row_number()
            .over(
                partition_by=qualifying.c.system_id,
                order_by=(
                    StationItem.supply_price.asc(),
                    StationItem.station_id.asc(),
                ),
            )
            .label("rank_in_system"),
        )
        .select_from(StationItem)
        .join(qualifying, qualifying.c.station_id == StationItem.station_id)
        .where(and_(*filters))
        .subquery()
    )
    cheapest_per_system = select(
        ranked.c.system_id,
        ranked.c.station_id,
        ranked.c.supply_price,
        ranked.c.supply_units,
        ranked.c.modified,
    ).where(ranked.c.rank_in_system == 1)
    session.execute(
        supply_temp.insert().from_select(
            ["system_id", "station_id", "supply_price", "supply_units", "modified"],
            cheapest_per_system,
        )
    )


def _reduce_demand_by_system(
    session: Session,
    qualifying: Table,
    demand_temp: Table,
    item_id: int,
    request: RunRequest,
    cutoff: datetime | None,
    is_sensitive: bool,
) -> None:
    """Reduce one commodity's demand to the dearest eligible station per system.

    The mirror of the supply reduction: ROW_NUMBER ranks each system's
    eligible buyers, dearest first with station id as the tie-break, and the
    outer query keeps rank one. Standard SQL, identical on every backend.
    Station eligibility comes from the run-scoped ``qualifying`` temp, same
    as the supply reduction.

    is_sensitive is known at call time — True for Metals/Minerals items —
    and drives the bulk-sale-tax cap: effective_demand_units is set to
    floor(demand_units * 0.25) when sensitive, otherwise to demand_units.
    The SQL ranking in _realisable_profit_expression reads that column
    directly so the cap reshapes which pair wins.
    """

    session.execute(demand_temp.delete())

    # Sensitive items with raw demand 2 or 3 floor to effective 0 and
    # cannot produce a usable trade, so filter them out at SQL rather than
    # materialise dead rows. Non-sensitive items keep the existing
    # _MIN_MEANINGFUL_DEMAND >= 2 floor for dormant-buy-side noise.
    min_demand_floor = 4 if is_sensitive else _MIN_MEANINGFUL_DEMAND
    filters = [
        StationItem.item_id == item_id,
        StationItem.demand_price > 0,
        StationItem.demand_units >= min_demand_floor,
    ]
    if request.min_demand is not None:
        filters.append(StationItem.demand_units >= request.min_demand)
    if cutoff is not None:
        filters.append(StationItem.modified >= cutoff)
    if request.max_price > 0:
        filters.append(StationItem.demand_price <= request.max_price)

    # cast(demand * 0.25 AS INTEGER) is the dialect-portable floor: both
    # SQLite and MariaDB return float for the multiplication and truncate
    # toward zero on the integer cast, which equals floor for the non-
    # negative demand values here. is_sensitive is known in Python so the
    # conditional collapses to one column expression rather than a SQL
    # CASE per row.
    if is_sensitive:
        effective_demand_expr = cast(
            StationItem.demand_units * 0.25, Integer
        ).label("effective_demand_units")
    else:
        effective_demand_expr = StationItem.demand_units.label(
            "effective_demand_units"
        )

    ranked = (
        select(
            qualifying.c.system_id.label("system_id"),
            StationItem.station_id.label("station_id"),
            StationItem.demand_price.label("demand_price"),
            StationItem.demand_units.label("demand_units"),
            effective_demand_expr,
            StationItem.modified.label("modified"),
            func.row_number()
            .over(
                partition_by=qualifying.c.system_id,
                order_by=(
                    StationItem.demand_price.desc(),
                    StationItem.station_id.asc(),
                ),
            )
            .label("rank_in_system"),
        )
        .select_from(StationItem)
        .join(qualifying, qualifying.c.station_id == StationItem.station_id)
        .where(and_(*filters))
        .subquery()
    )
    dearest_per_system = select(
        ranked.c.system_id,
        ranked.c.station_id,
        ranked.c.demand_price,
        ranked.c.demand_units,
        ranked.c.effective_demand_units,
        ranked.c.modified,
    ).where(ranked.c.rank_in_system == 1)
    session.execute(
        demand_temp.insert().from_select(
            [
                "system_id",
                "station_id",
                "demand_price",
                "demand_units",
                "effective_demand_units",
                "modified",
            ],
            dearest_per_system,
        )
    )


def _realisable_profit_expression(supply_temp: Table, demand_temp: Table, request: RunRequest):
    """Build the realisable-profit ranking expression used by both match shapes.

    Rank by realisable total, not unit profit. A pair with a high unit margin
    but only one ton of supply or demand can be worth less than a full-hold
    pair at a smaller margin, and the bounded slice would otherwise clip the
    latter. The realisable tonnage is the smaller of supply, demand, and the
    per-request ceiling (capacity, narrowed by --limit when set); cap each
    row's supply_units and demand_units to that ceiling, then take the
    smaller of the capped pair.

    Credits-affordability would be the third row-wise cap (credits divided
    by supply_price), but at ordinary Cmdr balances it is rarely the binding
    constraint, and folding the integer division into the rank expression
    materially complicates the SQL. Left out deliberately; the walk's cutoff
    arithmetic (capacity * bound) still overestimates the realised total, so
    omitting credits cannot terminate the walk early.
    """

    capacity = int(request.capacity_units or 0)
    per_item_limit = request.cargo_limit_per_item
    ceiling = capacity
    if per_item_limit and per_item_limit > 0:
        ceiling = min(ceiling, per_item_limit)
    capped_supply = case(
        (supply_temp.c.supply_units > ceiling, ceiling),
        else_=supply_temp.c.supply_units,
    )
    # effective_demand_units already carries the bulk-sale-tax cap when
    # the commodity is sensitive (see _reduce_demand_by_system); cap it
    # against the ceiling to get realisable demand.
    capped_demand = case(
        (demand_temp.c.effective_demand_units > ceiling, ceiling),
        else_=demand_temp.c.effective_demand_units,
    )
    realisable_units = case(
        (capped_supply < capped_demand, capped_supply),
        else_=capped_demand,
    )
    profit = demand_temp.c.demand_price - supply_temp.c.supply_price
    return realisable_units * profit


def _match_same_system_trades(
    session: Session,
    supply_temp: Table,
    demand_temp: Table,
    request: RunRequest,
) -> list:
    """Match supply to demand within the same system, --jumps-per 0 only.

    No reach check needed because both sides are required to share a system.
    Result ranked by realisable total profit; top slice kept.
    """

    profit = demand_temp.c.demand_price - supply_temp.c.supply_price
    # A self-pair (same station as source and destination) is never a valid
    # trade hop.
    filters = [
        profit >= request.min_gain_per_ton,
        supply_temp.c.station_id != demand_temp.c.station_id,
    ]
    if request.max_gain_per_ton > 0:
        filters.append(profit <= request.max_gain_per_ton)

    realisable_profit = _realisable_profit_expression(
        supply_temp, demand_temp, request
    )
    columns = (
        supply_temp.c.station_id,
        supply_temp.c.supply_price,
        supply_temp.c.supply_units,
        supply_temp.c.modified,
        demand_temp.c.station_id,
        demand_temp.c.demand_price,
        demand_temp.c.demand_units,
        demand_temp.c.modified,
    )
    stmt = (
        select(*columns)
        .select_from(
            supply_temp.join(
                demand_temp,
                demand_temp.c.system_id == supply_temp.c.system_id,
            )
        )
        .where(and_(*filters))
        .order_by(realisable_profit.desc())
        .limit(_UNANCHORED_MATCH_LIMIT)
    )
    return session.execute(stmt).all()


# Streaming batch size for the on-demand reach matcher. Not a hard cap on
# examined rows — the cursor keeps streaming until the per-commodity accept
# cap is hit or the result set is exhausted. Just controls how many rows
# fetchmany pulls per round-trip.
_ON_DEMAND_REACH_BATCH = 5000


def _match_via_on_demand_reach(
    session: Session,
    supply_temp: Table,
    demand_temp: Table,
    request: RunRequest,
    bubble_cache: dict[int, object],
    l_max: float,
    l_max_sq: float,
) -> tuple[list, int, int, bool]:
    """Stream pairs through a direct-distance prefilter; reach-check per row.

    The SQL pair query cross-joins supply x demand temp tables, joins each
    side to System for coords, and applies a direct-distance prefilter
    (bbox + sphere at l_max = --jumps-per * --ly-per). Result is ordered
    by realisable profit DESC, no LIMIT — Python streams it and asks the
    bubble cache whether each row is *actually* reachable in --jumps-per
    hops. The prefilter is necessary-not-sufficient at multi-jump: a pair
    within straight-line l_max may still need more than --jumps-per actual
    hops. The bubble cache + BFS gives the truth; the prefilter just cuts
    the cross-join from "every pair" to "every pair plausibly in range".

    Returns: (accepted_rows, pairs_examined, pairs_accepted, hit_cap).
    pairs_examined counts rows fetched from the cursor; pairs_accepted
    counts those whose reachability check passed; hit_cap is True if the
    per-commodity cap stopped the stream before exhaustion.
    """

    profit = demand_temp.c.demand_price - supply_temp.c.supply_price
    supply_sys = aliased(System)
    demand_sys = aliased(System)
    dx = demand_sys.pos_x - supply_sys.pos_x
    dy = demand_sys.pos_y - supply_sys.pos_y
    dz = demand_sys.pos_z - supply_sys.pos_z

    filters = [
        profit >= request.min_gain_per_ton,
        supply_temp.c.station_id != demand_temp.c.station_id,
        demand_sys.pos_x.between(
            supply_sys.pos_x - l_max, supply_sys.pos_x + l_max
        ),
        demand_sys.pos_y.between(
            supply_sys.pos_y - l_max, supply_sys.pos_y + l_max
        ),
        demand_sys.pos_z.between(
            supply_sys.pos_z - l_max, supply_sys.pos_z + l_max
        ),
        dx * dx + dy * dy + dz * dz <= l_max_sq,
    ]
    if request.max_gain_per_ton > 0:
        filters.append(profit <= request.max_gain_per_ton)

    realisable_profit = _realisable_profit_expression(
        supply_temp, demand_temp, request
    )

    # Join order: supply -> supply_sys (anchor coords) -> demand (cross)
    # -> demand_sys (dest coords). The bbox + sq-dist filters narrow the
    # cross-join heavily before the result-row build.
    stmt = (
        select(
            supply_temp.c.system_id.label("source_system_id"),
            supply_temp.c.station_id.label("supply_station_id"),
            supply_temp.c.supply_price.label("supply_price"),
            supply_temp.c.supply_units.label("supply_units"),
            supply_temp.c.modified.label("supply_modified"),
            demand_temp.c.system_id.label("dest_system_id"),
            demand_temp.c.station_id.label("demand_station_id"),
            demand_temp.c.demand_price.label("demand_price"),
            demand_temp.c.demand_units.label("demand_units"),
            demand_temp.c.modified.label("demand_modified"),
        )
        .select_from(
            supply_temp.join(
                supply_sys,
                supply_sys.system_id == supply_temp.c.system_id,
            ).join(
                demand_temp,
                supply_temp.c.station_id != demand_temp.c.station_id,
            ).join(
                demand_sys,
                demand_sys.system_id == demand_temp.c.system_id,
            )
        )
        .where(and_(*filters))
        .order_by(realisable_profit.desc())
    )

    max_jumps = int(request.max_jumps_per_hop or 0)
    max_ly = float(request.max_ly_per_jump or 0.0)
    accepted_rows: list = []
    examined = 0
    hit_cap = False

    result = session.execute(stmt)
    try:
        done = False
        while not done:
            batch = result.fetchmany(_ON_DEMAND_REACH_BATCH)
            if not batch:
                break
            for row in batch:
                examined += 1
                if not is_system_pair_reachable(
                    session,
                    int(row.source_system_id),
                    int(row.dest_system_id),
                    max_jumps_per_hop=max_jumps,
                    max_ly_per_jump=max_ly,
                    bubble_cache=bubble_cache,
                    avoid_system_ids=request.avoid_system_ids,
                ):
                    continue
                # _unanchored_candidate_from_row expects positional row[0..7]:
                # (supply_station_id, supply_price, supply_units, supply_modified,
                #  demand_station_id, demand_price, demand_units, demand_modified).
                accepted_rows.append(
                    (
                        row.supply_station_id,
                        row.supply_price,
                        row.supply_units,
                        row.supply_modified,
                        row.demand_station_id,
                        row.demand_price,
                        row.demand_units,
                        row.demand_modified,
                    )
                )
                if len(accepted_rows) >= _UNANCHORED_MATCH_LIMIT:
                    hit_cap = True
                    done = True
                    break
    finally:
        result.close()

    return accepted_rows, examined, len(accepted_rows), hit_cap


def _unanchored_candidate_from_row(
    row, item_id: int, item_name: str, is_sensitive: bool,
) -> TradeCandidate:
    """Build a TradeCandidate from one matched supply/demand row."""

    buy_price = int(row[1])
    sell_price = int(row[5])
    demand_units = int(row[6])
    # floor(demand * 0.25); Python integer division on non-negative ints
    # rounds toward zero, matching floor.
    effective_demand = demand_units // 4 if is_sensitive else demand_units
    return TradeCandidate(
        item_id=item_id,
        item_name=item_name,
        source_station_id=int(row[0]),
        destination_station_id=int(row[4]),
        buy_price=buy_price,
        sell_price=sell_price,
        profit_per_unit=sell_price - buy_price,
        source_supply_units=int(row[2]),
        destination_demand_units=demand_units,
        source_age_days=_age_days(row[3]),
        destination_age_days=_age_days(row[7]),
        bulk_sale_tax_sensitive=is_sensitive,
        effective_destination_demand_units=effective_demand,
    )


def _concrete_total_profit(
    candidate: TradeCandidate,
    capacity: int,
    available_credits: int,
    per_item_limit: int,
) -> int:
    """Return a realisable total profit for trading one candidate alone.

    This is a deliberate lower bound on the best achievable trade: a single
    commodity, capped by capacity, supply, effective demand (already
    bulk-sale-cap aware), affordability, and --limit. The walk's cutoff
    needs a lower bound — understating it only widens the search, never
    discards the winner.
    """

    if candidate.buy_price <= 0:
        return 0
    units = min(
        capacity,
        candidate.source_supply_units,
        candidate.effective_destination_demand_units,
        available_credits // candidate.buy_price,
    )
    if per_item_limit > 0:
        units = min(units, per_item_limit)
    if units <= 0:
        return 0
    return units * candidate.profit_per_unit


def _resolved_station_from_model(station: Station, system: ResolvedSystem) -> ResolvedStation:
    """Build the planner station DTO from an ORM station row and a resolved system DTO."""

    return ResolvedStation(
        station_id=int(station.station_id),
        name=str(station.name),
        dbname=f"{system.name}/{station.name}",
        system_id=system.system_id,
        system_name=system.name,
        x=system.x,
        y=system.y,
        z=system.z,
        ls_from_star=int(station.ls_from_star or 0),
        market=str(station.market),
        black_market=str(station.blackmarket),
        max_pad_size=str(station.max_pad_size),
        planetary=str(station.planetary),
        fleet_carrier=fleet_carrier_state(int(station.type_id or 0)),
        settlement=settlement_state(int(station.type_id or 0)),
        type_id=int(station.type_id or 0),
        modified=station.modified,
        data_age_days=None,
    )


# A station that stocks a commodity still shows a nominal demand for it.
# demand_units of 0 or 1 is the dormant buy side of stocked goods, copied
# verbatim from the source market data; it is not a real buyer. Capping cargo
# at such a row produces one-tonne noise routes. Genuine destination markets
# carry a demand of 2 or more, so that is the floor for a row to count.
_MIN_MEANINGFUL_DEMAND = 2


# Elite charges a per-unit penalty when more than 25% of a station's
# advertised demand is sold in one go on Metals and Minerals. The post-25%
# discount curve is not precisely documented and varies by station and
# state, so the planner does not try to model discounted prices; instead
# it caps the planned destination quantity at floor(demand * 0.25) for
# affected commodities, keeping the advertised sell price in force on the
# planned quantity. The classification is canonical (EDCD/FDevIDs
# category names), so the resolver matches on Category.name rather than
# hardcoded ids — ids are deployment-local, names are the contract.
_BULK_SALE_TAX_CATEGORY_NAMES = ("Metals", "Minerals")
_BULK_SALE_TAX_CATEGORY_IDS_CACHE_KEY = "planner.bulk_sale_tax_category_ids"
_BULK_SALE_TAX_ITEM_IDS_CACHE_KEY = "planner.bulk_sale_tax_item_ids"


def _bulk_sale_tax_category_ids(session: Session) -> frozenset[int]:
    """Resolve the bulk-sale-tax category names to local category_ids.

    Cached per SQLAlchemy session. Metals and Minerals are required category
    rows in a valid imported database; if either is missing, the planner cannot
    safely apply the bulk-sale demand cap and must fail loudly. Category.name is
    CIString, so the IN match is case-insensitive on both backends.
    """

    cached = session.info.get(_BULK_SALE_TAX_CATEGORY_IDS_CACHE_KEY)
    if cached is not None:
        return cached

    rows = session.execute(
        select(Category.category_id).where(
            Category.name.in_(_BULK_SALE_TAX_CATEGORY_NAMES)
        )
    ).all()
    resolved = frozenset(int(row[0]) for row in rows)
    if len(resolved) != len(_BULK_SALE_TAX_CATEGORY_NAMES):
        raise PlannerDataError(
            "Bulk-sale-tax commodity categories are missing from the database.",
            details={
                "required_category_names": _BULK_SALE_TAX_CATEGORY_NAMES,
                "resolved_count": len(resolved),
            },
        )

    session.info[_BULK_SALE_TAX_CATEGORY_IDS_CACHE_KEY] = resolved
    return resolved


def _bulk_sale_tax_sensitive_item_ids(session: Session) -> frozenset[int]:
    """Resolve bulk-sale-tax sensitive item_ids in one query.

    Cached per SQLAlchemy session. The unanchored walk iterates every
    profitable item and benefits from a flat membership set rather than
    re-resolving the category for each item.
    """

    cached = session.info.get(_BULK_SALE_TAX_ITEM_IDS_CACHE_KEY)
    if cached is not None:
        return cached

    sensitive_category_ids = _bulk_sale_tax_category_ids(session)
    rows = session.execute(
        select(Item.item_id).where(
            Item.category_id.in_(tuple(sensitive_category_ids))
        )
    ).all()
    resolved = frozenset(int(row[0]) for row in rows)

    session.info[_BULK_SALE_TAX_ITEM_IDS_CACHE_KEY] = resolved
    return resolved


def _effective_sensitive_category_ids(
    session: Session, request: RunRequest
) -> frozenset[int]:
    """Sensitive (Metals/Minerals) category_ids, or empty under --no-bulk-cap.

    --no-bulk-cap turns off the safe bulk-sale-tax demand cap by declaring
    nothing sensitive, so the cap evaporates at every site that tests this set.
    The empty path bypasses the session cache, so it never overwrites the real
    resolved set for a later capped run on the same session.
    """

    if request.no_bulk_cap:
        return frozenset()
    return _bulk_sale_tax_category_ids(session)


def _effective_sensitive_item_ids(
    session: Session, request: RunRequest
) -> frozenset[int]:
    """Sensitive (Metals/Minerals) item_ids, or empty under --no-bulk-cap.

    Mirrors _effective_sensitive_category_ids for the unanchored walk's
    item-id membership set.
    """

    if request.no_bulk_cap:
        return frozenset()
    return _bulk_sale_tax_sensitive_item_ids(session)


_KNOWN_PAD_SIZES = ("S", "M", "L")

_PAD_SIZE_QUALIFYING = {
    "S": ("S", "M", "L", "?"),
    "M": ("M", "L", "?"),
    "L": ("L",),
}


def _qualifying_pad_sizes(pad_size: str | None) -> tuple[str, ...]:
    """Return the station max-pad-size values satisfying a --pad-size threshold.

    --pad-size names the pad size the ship needs; a station qualifies when its
    largest pad is at least that size. With no --pad-size the threshold is the
    weakest (small), which every known pad size meets. An unknown pad ("?")
    qualifies whenever the threshold admits a medium pad (under small, medium,
    or no --pad-size) and is excluded only under large, where landing cannot be
    risked on an unrecorded pad.
    """

    return _PAD_SIZE_QUALIFYING[pad_size or "S"]


def _pad_size_matches(station_pad_size: str, pad_size: str | None) -> bool:
    """Return whether a station's largest pad meets a --pad-size threshold."""

    return station_pad_size in _qualifying_pad_sizes(pad_size)


def _state_filter_matches(
    station_state: str | None,
    requested_states: tuple[str, ...],
) -> bool:
    """Return whether a station Y/N/? state passes a requested state set."""

    return (station_state or "?").upper() in requested_states


def _age_cutoff(age_days: float | None) -> datetime | None:
    if age_days is None:
        return None
    return datetime.now(timezone.utc) - timedelta(days=float(age_days))


def _age_days(
    value: object,
    *,
    now_utc: datetime | None = None,
) -> float | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        modified = value
    elif isinstance(value, str):
        try:
            modified = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise MarketTimestampInvalid(
                "Market timestamp could not be parsed.",
                details={"timestamp": value},
            ) from exc
    else:
        raise MarketTimestampInvalid(
            "Market timestamp has an unsupported type.",
            details={"timestamp_type": type(value).__name__},
        )

    if modified.tzinfo is None:
        modified = modified.replace(tzinfo=timezone.utc)

    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    return (
        now_utc - modified.astimezone(timezone.utc)
    ).total_seconds() / 86400.0