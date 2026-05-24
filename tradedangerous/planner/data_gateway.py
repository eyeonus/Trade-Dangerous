"""Read-only data access for trade run planning."""

from __future__ import annotations

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
    case,
    cast,
    func,
    literal,
    select,
)
from sqlalchemy.orm import Session, aliased

from tradedangerous.db.orm_models import Category, Item, Station, StationItem, System
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
    SourceHasNoSellingData,
    SourceStationIneligible,
    StationHasNoMarket,
)
from .reachability import is_system_pair_reachable
from .run_request import RunRequest
from .run_result import ResolvedStation, ResolvedSystem, TradeCandidate


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

    if request.no_planet and station.planetary != "N":
        raise failure_type(
            f"{option_prefix} station does not meet --no-planet.",
            option_name="--no-planet",
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
    if request.no_planet:
        predicates.append(Station.planetary == "N")
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
    return tuple(predicates)


@contextmanager
def _reachable_station_query(
    session: Session,
    anchor_system: ResolvedSystem,
    request: RunRequest,
) -> Iterator[Select]:
    """Yield a SELECT of station ids reachable from the anchor within --jumps-per.

    For --jumps-per 0 (same-system) no temp table is needed; the helper yields
    today's bounded query. For --jumps-per >= 1 the helper builds a per-call
    temp table ``td_reachable_systems``, seeds it with the anchor, and grows
    it one layer at a time up to --jumps-per before yielding the composed
    SELECT. The table is dropped on exit, even if the caller raises.

    Callers compose the yielded SELECT via ``.in_(...)`` so the reachable set
    stays in SQL — handing a large id list to a later query as a literal
    ``IN (...)`` would flip SQLite off the StationItem primary key onto a
    galaxy-wide index scan, exactly the legacy preload-first failure this
    rewrite exists to avoid.
    """

    if request.max_jumps_per_hop == 0:
        # Same-system supercruise: no jump, no temp table.
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

    connection = session.connection()
    metadata = MetaData()
    # Mirror the System pos column type so the spatial maths inside the layer
    # INSERT runs as floats on either backend without an implicit cast.
    pos_type = System.__table__.c.pos_x.type
    temp = Table(
        "td_reachable_systems",
        metadata,
        Column("system_id", BigInteger, primary_key=True),
        Column("pos_x", pos_type),
        Column("pos_y", pos_type),
        Column("pos_z", pos_type),
        Column("depth", Integer),
        # Depth index lets each layer's JOIN find the previous frontier
        # without scanning the whole accumulated set, which is what makes
        # later layers stay cheap as the table grows.
        Index("ix_td_reachable_systems_depth", "depth"),
        prefixes=["TEMPORARY"],
    )
    # Drop any leftover from a previous interrupted call before recreating.
    temp.drop(connection, checkfirst=True)
    temp.create(connection)
    try:
        _populate_reachable_systems(
            connection,
            temp,
            anchor_system,
            float(request.max_ly_per_jump or 0.0),
            int(request.max_jumps_per_hop),
        )
        yield select(Station.station_id).where(
            and_(
                Station.system_id.in_(select(temp.c.system_id)),
                *_station_attribute_predicates(request),
            )
        )
    finally:
        temp.drop(connection, checkfirst=True)


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
) -> tuple[TradeCandidate, ...]:
    """Fetch profitable commodities for one source/destination station pair.

    Runs the selective join first. Diagnostic probes to classify source-side
    or destination-side missing data are deferred to the zero-result path only.
    """

    source_item = aliased(StationItem)
    destination_item = aliased(StationItem)

    available_credits = int(request.starting_credits or 0) - request.insurance_reserve
    cutoff = _age_cutoff(request.age_days)
    sensitive_category_ids = _bulk_sale_tax_category_ids(session)

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

    candidates = []
    for row in session.execute(stmt):
        source_age = _age_days(row[4])
        destination_age = _age_days(row[7])
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

    if not candidates:
        _classify_zero_result_failure(session, source, destination, request, cutoff)

    return tuple(candidates)


def _classify_zero_result_failure(
    session: Session,
    source: ResolvedStation,
    destination: ResolvedStation,
    request: RunRequest,
    cutoff: datetime | None,
) -> None:
    """Raise the most specific failure when a station-pair join returns no candidates."""

    source_filters = [
        StationItem.station_id == source.station_id,
        StationItem.supply_price > 0,
        StationItem.supply_units > 0,
    ]
    if request.min_supply is not None:
        source_filters.append(StationItem.supply_units >= request.min_supply)
    if cutoff is not None:
        source_filters.append(StationItem.modified >= cutoff)

    if not session.execute(
        select(StationItem.item_id).where(and_(*source_filters)).limit(1)
    ).first():
        raise SourceHasNoSellingData(
            f"Source station has no usable selling data: {source.dbname}",
            option_name="--from",
            entity_name=source.dbname,
        )

    destination_filters = [
        StationItem.station_id == destination.station_id,
        StationItem.demand_price > 0,
        StationItem.demand_units >= _MIN_MEANINGFUL_DEMAND,
    ]
    if request.min_demand is not None:
        destination_filters.append(StationItem.demand_units >= request.min_demand)
    if cutoff is not None:
        destination_filters.append(StationItem.modified >= cutoff)

    if not session.execute(
        select(StationItem.item_id).where(and_(*destination_filters)).limit(1)
    ).first():
        raise DestinationHasNoBuyingData(
            f"Destination station has no usable buying data: {destination.dbname}",
            option_name="--to",
            entity_name=destination.dbname,
        )
    # Both sides have qualifying data; zero join result means no profitable intersection.


def fetch_open_ended_trade_candidates(
    session: Session,
    fixed_station_ids: tuple[int, ...],
    anchor_system: ResolvedSystem,
    request: RunRequest,
    *,
    open_role: str,
) -> tuple[TradeCandidate, ...]:
    """Fetch profitable trades between a fixed endpoint and reachable stations.

    open_role is the trade role of the endpoint the planner selects — "source"
    when --from is omitted, "destination" when --to is omitted. The fixed
    endpoint takes the other role. The spatially-reached station set and the
    fixed station set are assigned to the supply and demand queries from
    open_role: an open source feeds the supply query from reachable stations
    and the demand query from the fixed destination; an open destination feeds
    the supply query from the fixed origin and the demand query from reachable
    stations.

    The reachable stations stay a subquery (see _reachable_station_query),
    never a materialised id list: handed to a query as a large literal
    IN (...) they would flip SQLite onto a galaxy-wide index scan, so as a
    subquery the query holds the StationItem primary key. The fixed endpoint
    is one named place and small, so its id list is passed directly. Supply
    rows and demand rows are fetched as two separate single-table queries and
    matched on item_id in Python; a single self-join would instead let SQLite
    scan the market table galaxy-wide by item_id, so the two sides stay apart.

    The temp table backing the reachable-systems set is created by the
    context manager on entry and dropped on exit, so the whole supply +
    demand fetch must run inside the ``with`` block.

    Failure classification is left to the caller: this returns an empty tuple
    when no candidate survives, rather than probing for a specific reason.
    """

    with _reachable_station_query(session, anchor_system, request) as reachable_query:
        # open_role names the endpoint the planner selects; the spatially-
        # reached set fills that side's query and the fixed endpoint fills the
        # other. The reachable set stays a subquery so SQLite keeps the
        # StationItem primary key; a large literal id list would flip it onto
        # a galaxy-wide index scan. The fixed endpoint is one named place,
        # small, so a literal id list is safe there.
        if open_role == "source":
            supply_station_filter = StationItem.station_id.in_(reachable_query)
            demand_station_filter = StationItem.station_id.in_(fixed_station_ids)
        else:
            supply_station_filter = StationItem.station_id.in_(fixed_station_ids)
            demand_station_filter = StationItem.station_id.in_(reachable_query)

        available_credits = int(request.starting_credits or 0) - request.insurance_reserve
        cutoff = _age_cutoff(request.age_days)
        sensitive_category_ids = _bulk_sale_tax_category_ids(session)

        supply_filters = [
            supply_station_filter,
            StationItem.supply_price > 0,
            StationItem.supply_units > 0,
            StationItem.supply_price <= available_credits,
        ]
        if request.min_supply is not None:
            supply_filters.append(StationItem.supply_units >= request.min_supply)
        if cutoff is not None:
            supply_filters.append(StationItem.modified >= cutoff)

        supply_rows = session.execute(
            select(
                StationItem.item_id,
                StationItem.station_id,
                StationItem.supply_price,
                StationItem.supply_units,
                StationItem.modified,
            ).where(and_(*supply_filters))
        ).all()
        if not supply_rows:
            return ()

        demand_filters = [
            demand_station_filter,
            StationItem.demand_price > 0,
            StationItem.demand_units >= _MIN_MEANINGFUL_DEMAND,
        ]
        if request.min_demand is not None:
            demand_filters.append(StationItem.demand_units >= request.min_demand)
        if cutoff is not None:
            demand_filters.append(StationItem.modified >= cutoff)

        demand_rows = session.execute(
            select(
                StationItem.item_id,
                StationItem.station_id,
                StationItem.demand_price,
                StationItem.demand_units,
                StationItem.modified,
            ).where(and_(*demand_filters))
        ).all()
        if not demand_rows:
            return ()

        demand_by_item: dict[int, list] = {}
        for row in demand_rows:
            demand_by_item.setdefault(int(row[0]), []).append(row)

        supply_item_ids = {int(row[0]) for row in supply_rows}
        # Fetch name and category_id together so the per-candidate
        # sensitivity check costs one dict lookup, not another query.
        item_names: dict[int, str] = {}
        item_categories: dict[int, int] = {}
        for item_id, name, category_id in session.execute(
            select(Item.item_id, Item.name, Item.category_id).where(
                Item.item_id.in_(tuple(supply_item_ids))
            )
        ).all():
            item_names[int(item_id)] = str(name)
            item_categories[int(item_id)] = int(category_id)

        min_gain = request.min_gain_per_ton
        max_gain = request.max_gain_per_ton

        candidates = []
        for supply in supply_rows:
            item_id = int(supply[0])
            demand_matches = demand_by_item.get(item_id)
            if not demand_matches:
                continue
            source_station_id = int(supply[1])
            buy_price = int(supply[2])
            source_supply_units = int(supply[3])
            source_age = _age_days(supply[4])
            item_name = item_names.get(item_id, "")
            sensitive = item_categories.get(item_id) in sensitive_category_ids
            for demand in demand_matches:
                destination_station_id = int(demand[1])
                if destination_station_id == source_station_id:
                    # Same-station self-pair, never a valid hop. The fixed and
                    # reachable station sets legitimately overlap on a same-
                    # system search, so the source != destination invariant
                    # is enforced here, per pair.
                    continue
                sell_price = int(demand[2])
                profit_per_unit = sell_price - buy_price
                if profit_per_unit < min_gain:
                    continue
                if max_gain > 0 and profit_per_unit > max_gain:
                    continue
                demand_units = int(demand[3])
                # floor(demand * 0.25); Python integer division on
                # non-negative ints rounds toward zero, matching floor.
                effective_demand = demand_units // 4 if sensitive else demand_units
                if effective_demand <= 0:
                    # Bulk-sale cap reduces this Metals/Minerals row to
                    # zero safe cargo at the advertised price. Another
                    # demand row for the same item at a different station
                    # may still produce a usable cap, so we drop this
                    # pair only, not the whole item.
                    continue
                candidates.append(
                    TradeCandidate(
                        item_id=item_id,
                        item_name=item_name,
                        source_station_id=source_station_id,
                        destination_station_id=destination_station_id,
                        buy_price=buy_price,
                        sell_price=sell_price,
                        profit_per_unit=profit_per_unit,
                        source_supply_units=source_supply_units,
                        destination_demand_units=demand_units,
                        source_age_days=source_age,
                        destination_age_days=_age_days(demand[4]),
                        bulk_sale_tax_sensitive=sensitive,
                        effective_destination_demand_units=effective_demand,
                    )
                )

        candidates.sort(key=lambda c: (-c.profit_per_unit, c.item_name))
        return tuple(candidates)


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
) -> dict[int, ResolvedStation]:
    """Fetch ResolvedStation DTOs for a set of station ids, keyed by id.

    Used to materialise the destination stations that actually appear in
    open-ended trade candidates, so reachable stations with no profitable
    trade are never loaded into planner space.
    """

    if not station_ids:
        return {}

    stmt = (
        select(Station, System)
        .join(System, System.system_id == Station.system_id)
        .where(Station.station_id.in_(station_ids))
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
    return stations


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

    The reach map that prior slices used (all ordered pairs in --ly-per
    range) is gone: at multi-jump in dense space it grows to hundreds of
    millions of rows. The direct-distance prefilter plus on-demand reach
    via Piece A's bubble cache replaces it without ever materialising a
    multi-jump pair set.
    """

    available_credits = int(request.starting_credits or 0) - request.insurance_reserve
    cutoff = _age_cutoff(request.age_days)
    sensitive_item_ids = _bulk_sale_tax_sensitive_item_ids(session)
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

    connection = session.connection()
    # Tune the connection for bulk work: temp tables in memory and a larger
    # page cache on SQLite, session-scoped commit and lock tuning on MariaDB.
    begin_bulk_mode(session)
    _create_unanchored_temps(connection, supply_temp, demand_temp)

    pairs_examined = 0
    pairs_accepted = 0
    cap_hits = 0
    try:
        item_bounds, item_names = _unanchored_item_bounds(session)

        candidates: list[TradeCandidate] = []
        best_total_profit = 0
        for item_id, profit_bound in item_bounds:
            # Descending bound order: once capacity x bound cannot beat the
            # best concrete trade seen, no later commodity can either.
            if capacity * profit_bound <= best_total_profit:
                break
            is_sensitive = item_id in sensitive_item_ids
            _reduce_supply_by_system(
                session, supply_temp, item_id, request, available_credits, cutoff
            )
            _reduce_demand_by_system(
                session, demand_temp, item_id, request, cutoff, is_sensitive
            )

            if same_system:
                rows = _match_same_system_trades(
                    session, supply_temp, demand_temp, request
                )
                accepted_for_item = len(rows)
            else:
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
            _drop_unanchored_temps(connection, supply_temp, demand_temp)
        except Exception:
            pass


def _create_unanchored_temps(connection, supply_temp, demand_temp) -> None:
    """Create the run-scoped temporary tables, replacing any stale leftovers."""

    demand_temp.drop(connection, checkfirst=True)
    supply_temp.drop(connection, checkfirst=True)
    supply_temp.create(connection)
    demand_temp.create(connection)


def _drop_unanchored_temps(connection, supply_temp, demand_temp) -> None:
    """Drop the run-scoped temporary tables once the search has finished."""

    demand_temp.drop(connection, checkfirst=True)
    supply_temp.drop(connection, checkfirst=True)


def _unanchored_item_bounds(
    session: Session,
) -> tuple[list[tuple[int, int]], dict[int, str]]:
    """Return per-commodity profit-per-unit bounds, highest first, with names.

    The bound is the galaxy-wide dearest demand price minus the cheapest
    supply price for the commodity, ignoring reachability and the station and
    affordability filters. That makes it a true upper bound on any reachable
    trade's profit-per-unit, which is what the walk's cutoff requires; the
    per-commodity reductions apply the precise filters. The loose form keeps
    this a pair of covering-index aggregates over the partial supply/demand
    indexes.
    """

    min_supply = {
        int(item_id): int(price)
        for item_id, price in session.execute(
            select(StationItem.item_id, func.min(StationItem.supply_price))
            .where(StationItem.supply_price > 0)
            .group_by(StationItem.item_id)
        )
    }
    max_demand = {
        int(item_id): int(price)
        for item_id, price in session.execute(
            select(StationItem.item_id, func.max(StationItem.demand_price))
            .where(StationItem.demand_price > 0)
            .group_by(StationItem.item_id)
        )
    }
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
    """

    session.execute(supply_temp.delete())

    filters = [
        StationItem.item_id == item_id,
        StationItem.supply_price > 0,
        StationItem.supply_units > 0,
        StationItem.supply_price <= available_credits,
        *_station_attribute_predicates(request),
    ]
    if request.min_supply is not None:
        filters.append(StationItem.supply_units >= request.min_supply)
    if cutoff is not None:
        filters.append(StationItem.modified >= cutoff)

    ranked = (
        select(
            Station.system_id.label("system_id"),
            StationItem.station_id.label("station_id"),
            StationItem.supply_price.label("supply_price"),
            StationItem.supply_units.label("supply_units"),
            StationItem.modified.label("modified"),
            func.row_number()
            .over(
                partition_by=Station.system_id,
                order_by=(
                    StationItem.supply_price.asc(),
                    StationItem.station_id.asc(),
                ),
            )
            .label("rank_in_system"),
        )
        .select_from(StationItem)
        .join(Station, Station.station_id == StationItem.station_id)
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
        *_station_attribute_predicates(request),
    ]
    if request.min_demand is not None:
        filters.append(StationItem.demand_units >= request.min_demand)
    if cutoff is not None:
        filters.append(StationItem.modified >= cutoff)

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
            Station.system_id.label("system_id"),
            StationItem.station_id.label("station_id"),
            StationItem.demand_price.label("demand_price"),
            StationItem.demand_units.label("demand_units"),
            effective_demand_expr,
            StationItem.modified.label("modified"),
            func.row_number()
            .over(
                partition_by=Station.system_id,
                order_by=(
                    StationItem.demand_price.desc(),
                    StationItem.station_id.asc(),
                ),
            )
            .label("rank_in_system"),
        )
        .select_from(StationItem)
        .join(Station, Station.station_id == StationItem.station_id)
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


def _bulk_sale_tax_category_ids(session: Session) -> frozenset[int]:
    """Resolve the bulk-sale-tax category names to local category_ids.

    Run once per candidate-fetch path. Returns an empty set if neither
    category exists in the local database — behaviour reverts to "no
    commodity is bulk-tax-sensitive", a safe degradation rather than a
    crash. Category.name is CIString, so the IN match is case-insensitive
    on both backends.
    """

    rows = session.execute(
        select(Category.category_id).where(
            Category.name.in_(_BULK_SALE_TAX_CATEGORY_NAMES)
        )
    ).all()
    return frozenset(int(row[0]) for row in rows)


def _bulk_sale_tax_sensitive_item_ids(session: Session) -> frozenset[int]:
    """Resolve bulk-sale-tax sensitive item_ids in one query.

    The unanchored walk iterates every profitable item and benefits from
    a flat membership set rather than re-resolving the category for each
    item. Returns an empty set when no sensitive categories are present
    locally — safe degradation, same as _bulk_sale_tax_category_ids.
    """

    sensitive_category_ids = _bulk_sale_tax_category_ids(session)
    if not sensitive_category_ids:
        return frozenset()
    rows = session.execute(
        select(Item.item_id).where(
            Item.category_id.in_(tuple(sensitive_category_ids))
        )
    ).all()
    return frozenset(int(row[0]) for row in rows)


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


def _age_days(value: object) -> float | None:
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

    return (
        datetime.now(timezone.utc) - modified.astimezone(timezone.utc)
    ).total_seconds() / 86400.0