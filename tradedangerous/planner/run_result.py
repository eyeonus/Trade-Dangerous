"""Result DTOs for trade run planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ResolvedSystem:
    system_id: int
    name: str
    dbname: str
    x: float
    y: float
    z: float


@dataclass(frozen=True, slots=True)
class ResolvedStation:
    station_id: int
    name: str
    dbname: str
    system_id: int
    system_name: str
    x: float
    y: float
    z: float
    ls_from_star: int
    market: str
    black_market: str
    max_pad_size: str
    planetary: str
    fleet_carrier: str | None
    settlement: str | None
    type_id: int
    modified: datetime | None
    data_age_days: float | None


@dataclass(frozen=True, slots=True)
class MarketQuote:
    station_id: int
    item_id: int
    item_name: str
    buy_price: int
    sell_price: int
    supply_units: int
    demand_units: int
    supply_level: int
    demand_level: int
    modified: datetime | None
    age_days: float | None


@dataclass(frozen=True, slots=True)
class TradeCandidate:
    item_id: int
    item_name: str
    source_station_id: int
    destination_station_id: int
    buy_price: int
    sell_price: int
    profit_per_unit: int
    source_supply_units: int
    destination_demand_units: int
    source_age_days: float | None
    destination_age_days: float | None


@dataclass(frozen=True, slots=True)
class CargoLine:
    item_id: int
    item_name: str
    quantity: int
    buy_price: int
    sell_price: int
    profit_per_unit: int
    total_cost: int
    total_profit: int
    source_supply_units: int
    destination_demand_units: int


@dataclass(frozen=True, slots=True)
class CargoPlan:
    lines: tuple[CargoLine, ...]
    units_loaded: int
    total_cost: int
    total_profit: int
    unused_capacity: int
    unspent_capital: int


@dataclass(frozen=True, slots=True)
class JumpPath:
    source_system_id: int
    destination_system_id: int
    systems: tuple[ResolvedSystem, ...]
    distance_ly: float
    jumps: int
    is_same_system: bool
    is_reachable: bool


@dataclass(frozen=True, slots=True)
class PlannedHop:
    source_station: ResolvedStation
    destination_station: ResolvedStation
    cargo: CargoPlan
    raw_profit: int
    practical_score: float
    jump_path: JumpPath


@dataclass(frozen=True, slots=True)
class PlannedRoute:
    stations: tuple[ResolvedStation, ...]
    hops: tuple[PlannedHop, ...]
    total_raw_profit: int
    total_practical_score: float
    starting_credits: int
    ending_credits: int


@dataclass(frozen=True, slots=True)
class PlannerDiagnostics:
    validation_ms: float = 0.0
    resolution_ms: float = 0.0
    station_query_ms: float = 0.0
    market_query_ms: float = 0.0
    reachability_ms: float = 0.0
    cargo_optimisation_ms: float = 0.0
    render_ms: float = 0.0
    total_planner_ms: float = 0.0
    candidate_trade_count: int = 0


@dataclass(frozen=True, slots=True)
class RunResult:
    routes: tuple[PlannedRoute, ...]
    diagnostics: PlannerDiagnostics = field(default_factory=PlannerDiagnostics)
    warnings: tuple[str, ...] = ()