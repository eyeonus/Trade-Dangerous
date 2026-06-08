"""Endpoint name resolution for trade run planning.

Endpoint names (--from / --to / --towards) resolve through the shared
``TradeORM`` place lookup, which owns the exact -> prefix -> substring matching
and the ``@N`` duplicate-system disambiguation. This module is the thin
planner-side adapter: it calls that lookup once, converts the ORM row to the
planner's neutral DTOs, and reports whether the match was approximate (so
dispatch can echo the expansion). No ORM object travels past this module into
the planner.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tradedangerous.db.orm_models import Station, System

from .data_gateway import _resolved_station_from_model
from .failures import UnknownPlace
from .run_result import ResolvedStation, ResolvedSystem

if TYPE_CHECKING:
    from tradedangerous.tradeorm import TradeORM


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
    system: ResolvedSystem | None = None
    station: ResolvedStation | None = None
    # True when the lookup matched something other than the verbatim name
    # (a partial / fuzzy hit). Dispatch echoes these so the commander sees what
    # their input expanded to; an exact or @N-indexed name is not approximate.
    approximate: bool = False

    @property
    def is_station(self) -> bool:
        return self.station is not None

    @property
    def is_system(self) -> bool:
        return self.station is None and self.system is not None


def parse_endpoint_reference(text: str, *, option_name: str) -> EndpointReference:
    """Split an endpoint into its (system, station) parts.

    Accepted forms: System, System/Station, @System, @System/Station,
    System\\Station, /Station, Station. This drives the approximate-match
    check; the actual lookup is delegated to ``TradeORM.lookup_place``, which
    does its own parsing.
    """

    cleaned = (text or "").strip()
    if not cleaned:
        raise UnknownPlace(
            f"{option_name} endpoint name is empty.",
            option_name=option_name,
            entity_name=text,
        )

    if cleaned.startswith("@"):
        cleaned = cleaned[1:].strip()

    delimiter = "/" if "/" in cleaned else "\\" if "\\" in cleaned else None
    if delimiter is None:
        return EndpointReference(system_name=None, station_name=cleaned)

    system_name, station_name = (
        part.strip() for part in cleaned.split(delimiter, 1)
    )
    return EndpointReference(
        system_name=system_name or None,
        station_name=station_name or None,
    )


def _system_to_resolved(system: System) -> ResolvedSystem:
    """Convert an ORM System to a planner ResolvedSystem DTO."""

    return ResolvedSystem(
        system_id=int(system.system_id),
        name=str(system.name),
        dbname=str(system.name),
        x=float(system.pos_x),
        y=float(system.pos_y),
        z=float(system.pos_z),
    )


def system_for_endpoint(endpoint: ResolvedEndpoint) -> ResolvedSystem | None:
    """Collapse an endpoint to its system.

    A station endpoint positions on its parent system; a system endpoint is its
    own system. Returns None for an unpopulated endpoint so the caller can raise
    rather than assume a side is filled.
    """

    if endpoint.station is not None:
        station = endpoint.station
        return ResolvedSystem(
            system_id=station.system_id,
            name=station.system_name,
            dbname=station.system_name,
            x=station.x,
            y=station.y,
            z=station.z,
        )
    return endpoint.system


def resolve_endpoint(
    orm_db: "TradeORM",
    text: str,
    *,
    option_name: str,
) -> ResolvedEndpoint:
    """Resolve a run endpoint to a fixed station or a system.

    Delegates to ``TradeORM.lookup_place`` for exact -> prefix -> substring
    matching and ``@N`` duplicate-system disambiguation. The returned ORM row is
    converted to neutral DTOs here, so no ORM object travels further into the
    planner. An unknown name becomes a planner ``UnknownPlace``; an ambiguous
    name or a bad ``@N`` index propagates as the lookup's own exception, which
    already carries the user-facing candidate / ``@N`` message.
    """

    try:
        place = orm_db.lookup_place(text)
    except LookupError as exc:
        raise UnknownPlace(
            f"Unrecognized {option_name} place: {text}",
            option_name=option_name,
            entity_name=text,
        ) from exc

    approximate = _was_approximate(text, place, option_name=option_name)

    if isinstance(place, Station):
        resolved_system = _system_to_resolved(place.system)
        station = _resolved_station_from_model(place, resolved_system)
        return ResolvedEndpoint(
            original_text=text,
            option_name=option_name,
            station=station,
            approximate=approximate,
        )

    return ResolvedEndpoint(
        original_text=text,
        option_name=option_name,
        system=_system_to_resolved(place),
        approximate=approximate,
    )


def _was_approximate(
    text: str,
    place: System | Station,
    *,
    option_name: str,
) -> bool:
    """Report whether the input matched anything other than the exact name.

    A pure case difference, or an ``@N`` selection of an otherwise exact name,
    does not count as approximate — only a genuine partial / fuzzy expansion
    does, which is what the dispatch echo exists to surface.
    """

    reference = parse_endpoint_reference(text, option_name=option_name)
    system_in = _strip_index(reference.system_name)
    station_in = _strip_index(reference.station_name)

    if isinstance(place, Station):
        if system_in and not _names_equal(system_in, place.system.name):
            return True
        if station_in and not _names_equal(station_in, place.name):
            return True
        return False

    # System: the supplied token is the system half when the input was scoped,
    # otherwise the bare name (which the parser places in station_name).
    supplied = system_in or station_in
    return bool(supplied and not _names_equal(supplied, place.name))


def _names_equal(supplied: str, resolved: str) -> bool:
    """Case-insensitive name comparison for the approximate-match check."""

    return supplied.casefold() == str(resolved).casefold()


def _strip_index(name: str | None) -> str | None:
    """Strip a trailing ``@N`` duplicate-system index from a supplied name."""

    if name is None:
        return None
    at = name.rfind("@")
    if at > 0 and name[at + 1:].isdigit():
        return name[:at]
    return name
