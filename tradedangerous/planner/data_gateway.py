"""Read-only data access for trade run planning."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, aliased

from tradedangerous.db.orm_models import Item, Station, StationItem
from tradedangerous.db.station_types import (
    DISPLAY_NAMES,
    FLEET_CARRIER_TYPE_IDS,
    SETTLEMENT_TYPE_IDS,
    UNKNOWN,
    fleet_carrier_state,
    settlement_state,
)

from .failures import (
    DestinationHasNoBuyingData,
    DestinationStationIneligible,
    MarketTimestampInvalid,
    SourceHasNoSellingData,
    SourceStationIneligible,
    StationHasNoMarket,
)
from .run_request import RunRequest
from .run_result import ResolvedStation, TradeCandidate


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

    if request.pad_size_filter and not _pad_size_matches(
        station.max_pad_size,
        request.pad_size_filter,
    ):
        raise failure_type(
            f"{option_prefix} station does not meet --pad-size.",
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
    system,
    request: RunRequest,
    *,
    role: str,
) -> tuple[ResolvedStation, ...]:
    """Fetch stations in one resolved system that pass station-level filters.

    This is endpoint expansion only: it deliberately stays bounded to the
    selected system and does not inspect market quotes. Source/destination
    quote eligibility is still evaluated later for each station pair.
    """

    stmt = (
        select(Station)
        .where(and_(*_station_filter_predicates(system, request)))
        .order_by(Station.station_id)
    )

    stations = []
    for station in session.scalars(stmt):
        resolved = _resolved_station_from_model(station, system)
        try:
            validate_station_filters(resolved, request, role=role)
        except (SourceStationIneligible, DestinationStationIneligible, StationHasNoMarket):
            # Defensive fallback only. Normal expansion filtering should happen
            # in SQL so rejected station rows are not materialised in Python.
            continue
        stations.append(resolved)

    return tuple(stations)


def _station_filter_predicates(system, request: RunRequest):
    """Return SQL predicates for station-level endpoint expansion filters."""

    predicates = [
        Station.system_id == system.system_id,
        Station.market != "N",
    ]
    if request.pad_size_filter:
        predicates.append(Station.max_pad_size.in_(request.pad_size_filter))
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
    """Fetch profitable commodities for one source/destination station pair."""

    source_item = aliased(StationItem)
    destination_item = aliased(StationItem)

    available_credits = int(request.starting_credits or 0) - request.insurance_reserve
    cutoff = _age_cutoff(request.age_days)
    
    source_filters = [
        StationItem.station_id == source.station_id,
        StationItem.supply_price > 0,
        StationItem.supply_units > 0,
    ]
    if request.min_supply is not None:
        source_filters.append(StationItem.supply_units >= request.min_supply)
    if cutoff is not None:
        source_filters.append(StationItem.modified >= cutoff)
    
    source_exists = session.execute(
        select(StationItem.item_id).where(and_(*source_filters)).limit(1)
    ).first()
    if source_exists is None:
        raise SourceHasNoSellingData(
            f"Source station has no usable selling data: {source.dbname}",
            option_name="--from",
            entity_name=source.dbname,
        )
    
    destination_filters = [
        StationItem.station_id == destination.station_id,
        StationItem.demand_price > 0,
        StationItem.demand_units > 0,
    ]
    if request.min_demand is not None:
        destination_filters.append(StationItem.demand_units >= request.min_demand)
    if cutoff is not None:
        destination_filters.append(StationItem.modified >= cutoff)
    
    destination_exists = session.execute(
        select(StationItem.item_id).where(and_(*destination_filters)).limit(1)
    ).first()
    if destination_exists is None:
        raise DestinationHasNoBuyingData(
            f"Destination station has no usable buying data: {destination.dbname}",
            option_name="--to",
            entity_name=destination.dbname,
        )
    
    filters = [
        source_item.station_id == source.station_id,
        destination_item.station_id == destination.station_id,
        destination_item.item_id == source_item.item_id,
        source_item.supply_price > 0,
        source_item.supply_units > 0,
        destination_item.demand_price > 0,
        destination_item.demand_units > 0,
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

    return tuple(candidates)


def _resolved_station_from_model(station: Station, system) -> ResolvedStation:
    """Build the planner station DTO from ORM rows already bounded by system."""

    return ResolvedStation(
        station_id=int(station.station_id),
        name=str(station.name),
        dbname=f"{system.name}/{station.name}",
        system_id=int(system.system_id),
        system_name=str(system.name),
        x=float(system.pos_x),
        y=float(system.pos_y),
        z=float(system.pos_z),
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


def _pad_size_matches(
    station_pad_size: str | None,
    requested_pad_sizes: tuple[str, ...],
) -> bool:
    """Return whether a station pad size is in the requested accepted set.

    Pad-size filters are exact station-state filters, not ship-compatibility
    ranks. Unknown pad size is represented as '?'.
    """

    return (station_pad_size or "?").upper() in requested_pad_sizes


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