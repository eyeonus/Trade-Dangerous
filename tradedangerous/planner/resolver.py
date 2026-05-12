"""Station name resolution for trade run planning."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from tradedangerous.db.orm_models import Station, System
from tradedangerous.db.station_types import fleet_carrier_state, settlement_state

from .failures import (
    AmbiguousStation,
    AmbiguousSystem,
    UnknownStation,
    UnknownSystem,
    UnsupportedFirstSliceShape,
)
from .run_result import ResolvedStation


@dataclass(frozen=True, slots=True)
class StationReference:
    """Parsed station reference from command text."""

    system_name: str | None
    station_name: str


def parse_station_reference(text: str, *, option_name: str) -> StationReference:
    """Parse supported station reference forms.

    Accepted station forms include:
    - System/Station
    - @System/Station
    - System\\Station
    - /Station
    - Station

    System-only references are deliberately rejected here because planning a
    system-wide station set belongs to a broader route-shape implementation.
    """

    cleaned = (text or "").strip()
    if not cleaned:
        raise UnknownStation(
            f"{option_name} station name is empty.",
            option_name=option_name,
        )

    if cleaned.startswith("@"):
        cleaned = cleaned[1:].strip()

    delimiter = "/" if "/" in cleaned else "\\" if "\\" in cleaned else None
    if delimiter is None:
        return StationReference(system_name=None, station_name=cleaned)

    system_name, station_name = (part.strip() for part in cleaned.split(delimiter, 1))
    if not station_name:
        raise UnsupportedFirstSliceShape(
            f"{option_name} must identify a station, not only a system.",
            option_name=option_name,
            entity_name=text,
        )

    return StationReference(
        system_name=system_name or None,
        station_name=station_name,
    )


def resolve_station(
    session: Session,
    text: str,
    *,
    option_name: str,
) -> ResolvedStation:
    """Resolve a station reference to a single station.

    Scoped references resolve the system first and then search stations within
    that system only. They never fall back to global station matching.
    """

    reference = parse_station_reference(text, option_name=option_name)

    if reference.system_name:
        system = _resolve_exact_system(
            session,
            reference.system_name,
            option_name=option_name,
        )
        station = _resolve_exact_station_in_system(
            session,
            reference.station_name,
            system_id=system.system_id,
            option_name=option_name,
            original_text=text,
        )
    else:
        station = _resolve_exact_station_global(
            session,
            reference.station_name,
            option_name=option_name,
            original_text=text,
        )

    return _resolved_station_from_model(station)


def _resolve_exact_system(
    session: Session,
    name: str,
    *,
    option_name: str,
) -> System:
    stmt = (
        select(System)
        .where(func.upper(System.name) == name.upper())
        .order_by(System.system_id)
    )
    matches = list(session.scalars(stmt))

    if not matches:
        raise UnknownSystem(
            f"Unknown system in {option_name}: {name}",
            option_name=option_name,
            entity_name=name,
        )

    if len(matches) > 1:
        raise AmbiguousSystem(
            f"Ambiguous system in {option_name}: {name}",
            option_name=option_name,
            entity_name=name,
            details={"matches": [system.name for system in matches]},
        )

    return matches[0]


def _resolve_exact_station_in_system(
    session: Session,
    name: str,
    *,
    system_id: int,
    option_name: str,
    original_text: str,
) -> Station:
    stmt = (
        select(Station)
        .options(joinedload(Station.system))
        .where(Station.system_id == system_id)
        .where(func.upper(Station.name) == name.upper())
        .order_by(Station.station_id)
    )
    matches = list(session.scalars(stmt))

    if not matches:
        raise UnknownStation(
            f"Unknown station in {option_name}: {original_text}",
            option_name=option_name,
            entity_name=original_text,
        )

    if len(matches) > 1:
        raise AmbiguousStation(
            f"Ambiguous station in {option_name}: {original_text}",
            option_name=option_name,
            entity_name=original_text,
            details={"matches": [station.dbname() for station in matches]},
        )

    return matches[0]


def _resolve_exact_station_global(
    session: Session,
    name: str,
    *,
    option_name: str,
    original_text: str,
) -> Station:
    stmt = (
        select(Station)
        .options(joinedload(Station.system))
        .where(func.upper(Station.name) == name.upper())
        .order_by(Station.system_id, Station.station_id)
    )
    matches = list(session.scalars(stmt))

    if not matches:
        raise UnknownStation(
            f"Unknown station in {option_name}: {original_text}",
            option_name=option_name,
            entity_name=original_text,
        )

    if len(matches) > 1:
        raise AmbiguousStation(
            f"Ambiguous station in {option_name}: {original_text}",
            option_name=option_name,
            entity_name=original_text,
            details={"matches": [station.dbname() for station in matches]},
        )

    return matches[0]


def _resolved_station_from_model(station: Station) -> ResolvedStation:
    system = station.system

    return ResolvedStation(
        station_id=int(station.station_id),
        name=str(station.name),
        dbname=station.dbname(),
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