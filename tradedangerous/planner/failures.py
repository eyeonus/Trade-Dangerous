"""Typed failures for the trade run planner rewrite."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class PlannerFailure(Exception):
    """Base class for planner failures intended for command-layer mapping."""

    def __init__(
        self,
        message: str,
        *,
        option_name: str | None = None,
        entity_name: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.option_name = option_name
        self.entity_name = entity_name
        self.details = dict(details or {})

    def as_dict(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "option_name": self.option_name,
            "entity_name": self.entity_name,
            "details": self.details,
        }


class InvalidRunRequest(PlannerFailure):
    """The parsed request is internally invalid."""


class UnsupportedRunShape(InvalidRunRequest):
    """The request is outside the currently enabled trade run planner shape."""


class MissingRequiredInput(InvalidRunRequest):
    """A required user input is missing."""


class ContradictoryOptions(InvalidRunRequest):
    """The request contains mutually contradictory options."""


class InvalidNumericOption(InvalidRunRequest):
    """A numeric option is outside the accepted range."""


class UnknownPlace(PlannerFailure):
    """A named place could not be resolved."""


class AmbiguousPlace(PlannerFailure):
    """A named place resolved to more than one possible match."""


class UnknownSystem(UnknownPlace):
    """A named system could not be resolved."""


class AmbiguousSystem(AmbiguousPlace):
    """A named system resolved to more than one possible match."""


class UnknownStation(UnknownPlace):
    """A named station could not be resolved."""


class AmbiguousStation(AmbiguousPlace):
    """A named station resolved to more than one possible match."""


class StationHasNoMarket(PlannerFailure):
    """A selected station exists but is not marked as having a market."""


class StationHasNoUsablePriceData(PlannerFailure):
    """A selected station has no usable market data for this request."""


class SourceHasNoSellingData(StationHasNoUsablePriceData):
    """The source station has no usable source-side selling data."""


class DestinationHasNoBuyingData(StationHasNoUsablePriceData):
    """The destination station has no usable destination-side buying data."""


class SourceStationIneligible(PlannerFailure):
    """The source station fails one or more requested station filters."""


class DestinationStationIneligible(PlannerFailure):
    """The destination station fails one or more requested station filters."""


class MarketTimestampInvalid(PlannerFailure):
    """A market timestamp could not be parsed safely."""


class NoReachableRoute(PlannerFailure):
    """No route satisfies the requested reachability constraints."""


class ReachabilityImplementationMissing(NoReachableRoute):
    """The requested reachability mode has no permitted implementation yet."""


class NoProfitableTrades(PlannerFailure):
    """No profitable trades satisfy the request constraints."""


class PlannerCancelled(PlannerFailure):
    """The planner was cancelled before completion."""


class PlannerInternalError(PlannerFailure):
    """Unexpected planner failure that should not leak a raw traceback."""