"""Station name resolution for trade run planning."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from tradedangerous.db.orm_models import Station, System
from tradedangerous.db.station_types import fleet_carrier_state, settlement_state

from .failures import (
    AmbiguousPlace,
    AmbiguousStation,
    AmbiguousSystem,
    UnknownPlace,
    UnknownStation,
    UnknownSystem,
    UnsupportedRunShape,
)
from .run_result import ResolvedStation


@dataclass(frozen=True, slots=True)
class StationReference:
    """Parsed station reference from command text."""

    system_name: str | None
    station_name: str


@dataclass(frozen=True, slots=True)
class EndpointReference:
    """Parsed endpoint reference from command text."""

    system_name: str | None
    station_name: str | None


@dataclass(frozen=True, slots=True)
class ResolvedEndpoint:
    """Resolved run endpoint before station expansion."""

    original_text: str
    option_name: str
    system: System | None = None
    station: ResolvedStation | None = None

    @property
    def is_station(self) -> bool:
        return self.station is not None

    @property
    def is_system(self) -> bool:
        return self.station is None and self.system is not None


def parse_station_reference(text: str, *, option_name: str) -> StationReference:
    """Parse supported station reference forms."""

    reference = parse_endpoint_reference(text, option_name=option_name)
    if not reference.station_name:
        raise UnsupportedRunShape(
            f"{option_name} must identify a station, not only a system.",
            option_name=option_name,
            entity_name=text,
        )

    return StationReference(
        system_name=reference.system_name,
        station_name=reference.station_name,
    )


def parse_endpoint_reference(text: str, *, option_name: str) -> EndpointReference:
    """Parse supported station or system endpoint reference forms.

    Accepted endpoint forms include:
    - System
    - System/Station
    - @System
    - @System/Station
    - System\\Station
    - /Station
    - Station
    """

    cleaned = (text or "").strip()
    if not cleaned:
        raise UnknownStation(
            f"{option_name} endpoint name is empty.",
            option_name=option_name,
        )

    if cleaned.startswith("@"):
        cleaned = cleaned[1:].strip()

    delimiter = "/" if "/" in cleaned else "\\" if "\\" in cleaned else None
    if delimiter is None:
        return EndpointReference(system_name=None, station_name=cleaned)

    system_name, station_name = (part.strip() for part in cleaned.split(delimiter, 1))
    return EndpointReference(
        system_name=system_name or None,
        station_name=station_name or None,
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
    station = _resolve_station_reference(
        session,
        reference,
        option_name=option_name,
        original_text=text,
    )
    return _resolved_station_from_model(station)


def resolve_endpoint(
    session: Session,
    text: str,
    *,
    option_name: str,
) -> ResolvedEndpoint:
    """Resolve a run endpoint as either a fixed station or a system."""

    reference = parse_endpoint_reference(text, option_name=option_name)

    if reference.system_name:
        system = _resolve_exact_system(
            session,
            reference.system_name,
            option_name=option_name,
        )
        if reference.station_name:
            station = _resolve_exact_station_in_system(
                session,
                reference.station_name,
                system_id=system.system_id,
                option_name=option_name,
                original_text=text,
            )
            return ResolvedEndpoint(
                original_text=text,
                option_name=option_name,
                station=_resolved_station_from_model(station),
            )

        return ResolvedEndpoint(
            original_text=text,
            option_name=option_name,
            system=system,
        )

    return _resolve_unscoped_endpoint(
        session,
        str(reference.station_name),
        option_name=option_name,
        original_text=text,
    )


def _resolve_unscoped_endpoint(
    session: Session,
    name: str,
    *,
    option_name: str,
    original_text: str,
) -> ResolvedEndpoint:
    """Resolve an unscoped endpoint by exact system/station candidates.

    Future fuzzy matching should extend this helper after exact candidates
    fail, not replace the exact-first behaviour.
    """

    systems = _find_exact_systems(session, name)
    stations = _find_exact_stations_global(session, name)
    if systems and stations:
        raise AmbiguousPlace(
            f"Ambiguous endpoint in {option_name}: {original_text}",
            option_name=option_name,
            entity_name=original_text,
            details={
                "systems": [system.name for system in systems],
                "stations": [station.dbname() for station in stations],
            },
        )
    if systems:
        if len(systems) > 1:
            raise AmbiguousSystem(
                f"Ambiguous system in {option_name}: {original_text}",
                option_name=option_name,
                entity_name=original_text,
                details={"matches": [system.name for system in systems]},
            )
        return ResolvedEndpoint(
            original_text=original_text,
            option_name=option_name,
            system=systems[0],
        )
    if stations:
        if len(stations) > 1:
            raise AmbiguousStation(
                f"Ambiguous station in {option_name}: {original_text}",
                option_name=option_name,
                entity_name=original_text,
                details={"matches": [station.dbname() for station in stations]},
            )
        return ResolvedEndpoint(
            original_text=original_text,
            option_name=option_name,
            station=_resolved_station_from_model(stations[0]),
        )
    raise UnknownPlace(
        f"Unknown system or station in {option_name}: {original_text}",
        option_name=option_name,
        entity_name=original_text,
    )


def _find_exact_systems(session: Session, name: str) -> list[System]:
    stmt = (
        select(System)
        .where(func.upper(System.name) == name.upper())
        .order_by(System.system_id)
    )
    return list(session.scalars(stmt))


def _find_exact_stations_global(session: Session, name: str) -> list[Station]:
    stmt = (
        select(Station)
        .options(joinedload(Station.system))
        .where(func.upper(Station.name) == name.upper())
        .order_by(Station.system_id, Station.station_id)
    )
    return list(session.scalars(stmt))


def _resolve_station_reference(
    session: Session,
    reference: StationReference,
    *,
    option_name: str,
    original_text: str,
) -> Station:
    if reference.system_name:
        system = _resolve_exact_system(
            session,
            reference.system_name,
            option_name=option_name,
        )
        return _resolve_exact_station_in_system(
            session,
            reference.station_name,
            system_id=system.system_id,
            option_name=option_name,
            original_text=original_text,
        )

    return _resolve_exact_station_global(
        session,
        reference.station_name,
        option_name=option_name,
        original_text=original_text,
    )


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