"""Read-only data access for trade run planning."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, Index, Integer, MetaData, Select, Table, and_, func, select
from sqlalchemy.orm import Session, aliased

from tradedangerous.db.orm_models import Item, Station, StationItem, System
from tradedangerous.db.station_types import (
    DISPLAY_NAMES,
    FLEET_CARRIER_TYPE_IDS,
    SETTLEMENT_TYPE_IDS,
    UNKNOWN,
    fleet_carrier_state,
    settlement_state,
)
from tradedangerous.db.utils import prefer_in_memory_temp_storage

from .failures import (
    DestinationHasNoBuyingData,
    DestinationStationIneligible,
    MarketTimestampInvalid,
    SourceHasNoSellingData,
    SourceStationIneligible,
    StationHasNoMarket,
)
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


def _system_reach_predicates(anchor_system: ResolvedSystem, max_ly: float):
    """Return SQL predicates selecting systems within max_ly of an anchor system.

    A bounding box on the indexed System.pos_x/pos_y/pos_z columns is the
    coarse filter; an exact squared-distance test refines it without a square
    root. Both run SQL-side, so spatial narrowing happens before any join to
    station or market data.
    """

    ax, ay, az = anchor_system.x, anchor_system.y, anchor_system.z
    reach_sq = max_ly * max_ly
    dx = System.pos_x - ax
    dy = System.pos_y - ay
    dz = System.pos_z - az
    return (
        System.pos_x.between(ax - max_ly, ax + max_ly),
        System.pos_y.between(ay - max_ly, ay + max_ly),
        System.pos_z.between(az - max_ly, az + max_ly),
        dx * dx + dy * dy + dz * dz <= reach_sq,
    )


def _reachable_station_id_query(
    anchor_system: ResolvedSystem,
    request: RunRequest,
) -> Select:
    """Return a SELECT of station ids reachable from the anchor in one jump.

    This is a subquery, not a materialised id list. Callers compose it into a
    larger statement with ``.in_(...)`` so the reachable set never leaves SQL.
    Handing a large id list back to a later query as a literal ``IN (...)``
    flips SQLite off the StationItem primary key and onto a galaxy-wide index
    scan; keeping the set as a subquery holds the plan on the primary key.

    Spatial narrowing still runs first: the System bounding box is itself a
    nested subquery, so the in-range systems are resolved before the Station
    attribute filters and well before the caller touches the market table.
    """

    if request.max_jumps_per_hop == 0:
        # --jumps-per 0: same-system supercruise only, no hyperspace jump.
        system_filter = System.system_id == anchor_system.system_id
    else:
        # --jumps-per 1: every system within a single loaded jump.
        system_filter = and_(
            *_system_reach_predicates(
                anchor_system,
                float(request.max_ly_per_jump or 0.0),
            )
        )
    in_range_systems = select(System.system_id).where(system_filter)

    filters = [
        Station.system_id.in_(in_range_systems),
        *_station_attribute_predicates(request),
    ]
    return select(Station.station_id).where(and_(*filters))


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
                destination_demand_units=int(row[6]),
                source_age_days=source_age,
                destination_age_days=destination_age,
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

    The reachable stations stay a subquery (see _reachable_station_id_query),
    never a materialised id list: handed to a query as a large literal
    IN (...) they would flip SQLite onto a galaxy-wide index scan, so as a
    subquery the query holds the StationItem primary key. The fixed endpoint
    is one named place and small, so its id list is passed directly. Supply
    rows and demand rows are fetched as two separate single-table queries and
    matched on item_id in Python; a single self-join would instead let SQLite
    scan the market table galaxy-wide by item_id, so the two sides stay apart.

    Failure classification is left to the caller: this returns an empty tuple
    when no candidate survives, rather than probing for a specific reason.
    """

    reachable_query = _reachable_station_id_query(anchor_system, request)

    # open_role names the endpoint the planner selects; the spatially-reached
    # set fills that side's query and the fixed endpoint fills the other. The
    # reachable set stays a subquery so SQLite keeps the StationItem primary
    # key; a large literal id list would flip it onto a galaxy-wide index
    # scan. The fixed endpoint is one named place, small, so a literal id
    # list is safe there.
    if open_role == "source":
        supply_station_filter = StationItem.station_id.in_(reachable_query)
        demand_station_filter = StationItem.station_id.in_(fixed_station_ids)
    else:
        supply_station_filter = StationItem.station_id.in_(fixed_station_ids)
        demand_station_filter = StationItem.station_id.in_(reachable_query)

    available_credits = int(request.starting_credits or 0) - request.insurance_reserve
    cutoff = _age_cutoff(request.age_days)

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
    item_names = {
        int(item_id): str(name)
        for item_id, name in session.execute(
            select(Item.item_id, Item.name).where(
                Item.item_id.in_(tuple(supply_item_ids))
            )
        ).all()
    }

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
        for demand in demand_matches:
            destination_station_id = int(demand[1])
            if destination_station_id == source_station_id:
                # Same-station self-pair, never a valid hop. The fixed and
                # reachable station sets legitimately overlap on a same-system
                # search, so the source != destination invariant is enforced
                # here, per pair.
                continue
            sell_price = int(demand[2])
            profit_per_unit = sell_price - buy_price
            if profit_per_unit < min_gain:
                continue
            if max_gain > 0 and profit_per_unit > max_gain:
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
                    destination_demand_units=int(demand[3]),
                    source_age_days=source_age,
                    destination_age_days=_age_days(demand[4]),
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

    reachable_query = _reachable_station_id_query(anchor_system, request)
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


def fetch_unanchored_trade_candidates(
    session: Session,
    request: RunRequest,
) -> tuple[TradeCandidate, ...]:
    """Fetch the bounded best-trade candidate set for an unanchored search.

    Neither endpoint is named, so the search is galaxy-wide and cannot
    materialise every profitable trade. The query is exhaustive in
    consideration but bounded in materialisation:

      1. A reachable-system map is built once as a run-scoped temporary table:
         every ordered system pair within --ly-per (--jumps-per 1), or skipped
         entirely when --jumps-per 0 collapses reachability to same-system.
      2. Each commodity is reduced, supply and demand separately, to its best
         price per system, carrying the station that achieves it.
      3. The two reductions are matched through the reachability map, ranked
         by gross profit-per-unit, and the top slice is kept.

    Commodities are walked in descending order of their galaxy-wide
    profit-per-unit bound. A pair's total profit cannot exceed
    capacity x best-profit-per-unit, so once a concrete trade of total profit
    T has been seen, any commodity whose capacity x bound is at or below T can
    win nothing and the walk stops — a single pass, since the order is
    descending. The reductions and the map keep the candidate set in SQL; only
    the bounded top slice per surviving commodity crosses into Python.
    """

    available_credits = int(request.starting_credits or 0) - request.insurance_reserve
    cutoff = _age_cutoff(request.age_days)
    capacity = int(request.capacity_units or 0)
    per_item_limit = request.cargo_limit_per_item
    same_system = request.max_jumps_per_hop == 0

    metadata = MetaData()
    modified_type = StationItem.__table__.c.modified.type
    supply_temp = Table(
        "td_unanchored_supply",
        metadata,
        Column("system_id", Integer),
        Column("station_id", Integer),
        Column("supply_price", Integer),
        Column("supply_units", Integer),
        Column("modified", modified_type),
        prefixes=["TEMPORARY"],
    )
    demand_temp = Table(
        "td_unanchored_demand",
        metadata,
        Column("system_id", Integer),
        Column("station_id", Integer),
        Column("demand_price", Integer),
        Column("demand_units", Integer),
        Column("modified", modified_type),
        Index("ix_td_unanchored_demand_sys", "system_id"),
        prefixes=["TEMPORARY"],
    )
    reach_temp = None
    if not same_system:
        reach_temp = Table(
            "td_unanchored_reach",
            metadata,
            Column("s", Integer),
            Column("d", Integer),
            prefixes=["TEMPORARY"],
        )

    connection = session.connection()
    # Keep the reachable-system map and the per-commodity scratch tables in
    # memory where the backend allows it — on SQLite that is the difference
    # between a memory-fast search and a disk-bound one.
    prefer_in_memory_temp_storage(session)
    _create_unanchored_temps(connection, supply_temp, demand_temp, reach_temp)
    try:
        if reach_temp is not None:
            _populate_reach_map(
                connection,
                reach_temp,
                float(request.max_ly_per_jump or 0.0),
            )

        item_bounds, item_names = _unanchored_item_bounds(session)

        candidates: list[TradeCandidate] = []
        best_total_profit = 0
        for item_id, profit_bound in item_bounds:
            # Descending bound order: once capacity x bound cannot beat the
            # best concrete trade seen, no later commodity can either.
            if capacity * profit_bound <= best_total_profit:
                break
            _reduce_supply_by_system(
                session, supply_temp, item_id, request, available_credits, cutoff
            )
            _reduce_demand_by_system(
                session, demand_temp, item_id, request, cutoff
            )
            for row in _match_reachable_trades(
                session, supply_temp, demand_temp, reach_temp, request
            ):
                candidate = _unanchored_candidate_from_row(
                    row, item_id, item_names.get(item_id, "")
                )
                candidates.append(candidate)
                best_total_profit = max(
                    best_total_profit,
                    _concrete_total_profit(
                        candidate, capacity, available_credits, per_item_limit
                    ),
                )
        return tuple(candidates)
    finally:
        _drop_unanchored_temps(connection, supply_temp, demand_temp, reach_temp)


def _create_unanchored_temps(connection, supply_temp, demand_temp, reach_temp) -> None:
    """Create the run-scoped temporary tables, replacing any stale leftovers."""

    for table in (reach_temp, demand_temp, supply_temp):
        if table is not None:
            table.drop(connection, checkfirst=True)
    supply_temp.create(connection)
    demand_temp.create(connection)
    if reach_temp is not None:
        reach_temp.create(connection)


def _drop_unanchored_temps(connection, supply_temp, demand_temp, reach_temp) -> None:
    """Drop the run-scoped temporary tables once the search has finished."""

    for table in (reach_temp, demand_temp, supply_temp):
        if table is not None:
            table.drop(connection, checkfirst=True)


def _populate_reach_map(connection, reach_temp: Table, max_ly: float) -> None:
    """Fill the reachable-system map with every ordered system pair in range.

    A bounding box on the indexed System.pos_x/pos_y/pos_z columns is the
    coarse filter; an exact squared-distance test refines it without a square
    root. The map is built once and reused for every commodity — the property
    that keeps the per-commodity cost flat.
    """

    source_system = aliased(System)
    destination_system = aliased(System)
    dx = destination_system.pos_x - source_system.pos_x
    dy = destination_system.pos_y - source_system.pos_y
    dz = destination_system.pos_z - source_system.pos_z
    pair_select = (
        select(source_system.system_id, destination_system.system_id)
        .select_from(source_system)
        .join(
            destination_system,
            and_(
                destination_system.pos_x.between(
                    source_system.pos_x - max_ly, source_system.pos_x + max_ly
                ),
                destination_system.pos_y.between(
                    source_system.pos_y - max_ly, source_system.pos_y + max_ly
                ),
                destination_system.pos_z.between(
                    source_system.pos_z - max_ly, source_system.pos_z + max_ly
                ),
                dx * dx + dy * dy + dz * dz <= max_ly * max_ly,
            ),
        )
    )
    connection.execute(reach_temp.insert().from_select(["s", "d"], pair_select))
    # Index after the bulk load: the match query searches the map by source
    # system, and an unindexed multi-million-row scan per commodity is the
    # cost this shape exists to avoid.
    Index("ix_td_unanchored_reach_s", reach_temp.c.s).create(connection)


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
) -> None:
    """Reduce one commodity's demand to the dearest eligible station per system.

    The mirror of the supply reduction: ROW_NUMBER ranks each system's
    eligible buyers, dearest first with station id as the tie-break, and the
    outer query keeps rank one. Standard SQL, identical on every backend.
    """

    session.execute(demand_temp.delete())

    filters = [
        StationItem.item_id == item_id,
        StationItem.demand_price > 0,
        StationItem.demand_units >= _MIN_MEANINGFUL_DEMAND,
        *_station_attribute_predicates(request),
    ]
    if request.min_demand is not None:
        filters.append(StationItem.demand_units >= request.min_demand)
    if cutoff is not None:
        filters.append(StationItem.modified >= cutoff)

    ranked = (
        select(
            Station.system_id.label("system_id"),
            StationItem.station_id.label("station_id"),
            StationItem.demand_price.label("demand_price"),
            StationItem.demand_units.label("demand_units"),
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
        ranked.c.modified,
    ).where(ranked.c.rank_in_system == 1)
    session.execute(
        demand_temp.insert().from_select(
            ["system_id", "station_id", "demand_price", "demand_units", "modified"],
            dearest_per_system,
        )
    )


def _match_reachable_trades(
    session: Session,
    supply_temp: Table,
    demand_temp: Table,
    reach_temp: Table | None,
    request: RunRequest,
) -> list:
    """Match reduced supply to reduced demand through the reachability map.

    With a reachability map (--jumps-per 1) the per-system supply and demand
    rows are joined through it; with --jumps-per 0 the join is a same-system
    equality. Either way the result is ranked by gross profit-per-unit and the
    top slice kept.
    """

    profit = demand_temp.c.demand_price - supply_temp.c.supply_price
    filters = [profit >= request.min_gain_per_ton]
    if request.max_gain_per_ton > 0:
        filters.append(profit <= request.max_gain_per_ton)

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
    if reach_temp is None:
        joined = supply_temp.join(
            demand_temp,
            demand_temp.c.system_id == supply_temp.c.system_id,
        )
    else:
        joined = supply_temp.join(
            reach_temp,
            reach_temp.c.s == supply_temp.c.system_id,
        ).join(
            demand_temp,
            demand_temp.c.system_id == reach_temp.c.d,
        )

    stmt = (
        select(*columns)
        .select_from(joined)
        .where(and_(*filters))
        .order_by(profit.desc())
        .limit(_UNANCHORED_MATCH_LIMIT)
    )
    return session.execute(stmt).all()


def _unanchored_candidate_from_row(row, item_id: int, item_name: str) -> TradeCandidate:
    """Build a TradeCandidate from one matched supply/demand row."""

    buy_price = int(row[1])
    sell_price = int(row[5])
    return TradeCandidate(
        item_id=item_id,
        item_name=item_name,
        source_station_id=int(row[0]),
        destination_station_id=int(row[4]),
        buy_price=buy_price,
        sell_price=sell_price,
        profit_per_unit=sell_price - buy_price,
        source_supply_units=int(row[2]),
        destination_demand_units=int(row[6]),
        source_age_days=_age_days(row[3]),
        destination_age_days=_age_days(row[7]),
    )


def _concrete_total_profit(
    candidate: TradeCandidate,
    capacity: int,
    available_credits: int,
    per_item_limit: int,
) -> int:
    """Return a realisable total profit for trading one candidate alone.

    This is a deliberate lower bound on the best achievable trade: a single
    commodity, capped by capacity, supply, demand, affordability, and --limit.
    The walk's cutoff needs a lower bound — understating it only widens the
    search, never discards the winner.
    """

    if candidate.buy_price <= 0:
        return 0
    units = min(
        capacity,
        candidate.source_supply_units,
        candidate.destination_demand_units,
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