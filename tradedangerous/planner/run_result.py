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
    # Elite penalises selling more than 25% of a station's demand in one go
    # on Metals and Minerals. bulk_sale_tax_sensitive is True for items in
    # either category; effective_destination_demand_units is the capped
    # value cargo fitting and unanchored ranking treat as the destination-
    # side quantity limit — floor(destination_demand_units * 0.25) when
    # sensitive, equal to destination_demand_units otherwise. The
    # advertised sell price is left untouched because no quantity above the
    # safe threshold is ever planned.
    bulk_sale_tax_sensitive: bool
    effective_destination_demand_units: int


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
    # Carried through from TradeCandidate so the renderer can flag hops
    # where the bulk-sale cap actively shaped the cargo plan. A sensitive
    # line with quantity == effective_destination_demand_units is one the
    # cap bound; sensitive lines with quantity below that were bound by
    # supply, capacity remainder, or credits first.
    bulk_sale_tax_sensitive: bool
    effective_destination_demand_units: int


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
    """One source-to-destination jump path produced by the reachability walk.

    distance_ly is the polyline length — the sum of straight-line leg lengths
    along ``systems``, i.e. the distance actually flown. For multi-jump paths
    through systems that bend off the direct line, this exceeds the straight-
    line endpoint distance and is the more meaningful figure to display.
    """

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


@dataclass(slots=True)
class ExpansionStats:
    """Aggregate counters across all per-frontier-node expansion calls.

    Mutated in place during a multi-hop run, then snapshotted onto
    ``PlannerDiagnostics`` for inspection. Mutable because the same
    instance threads through every expansion helper call so the data
    gateway can contribute memo hit/miss counts without a side channel.
    """

    expansion_calls: int = 0
    memo_hits: int = 0
    memo_misses: int = 0
    candidate_rows: int = 0
    grouped_pairs: int = 0
    cargo_calls: int = 0
    children_returned: int = 0
    elapsed_ms: float = 0.0


@dataclass(slots=True)
class FinalHopStats:
    """Per-run accounting for the final hop of a fixed-terminal multi-hop.

    Open-terminal multi-hop final hops use the same expansion helper as
    intermediate hops, so they accumulate into ExpansionStats and leave
    this DTO at its defaults.
    """

    frontier_nodes_attempted: int = 0
    nodes_with_reachable_destination: int = 0
    market_candidates_found: int = 0
    viable_cargo_plans: int = 0
    elapsed_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class LayerStats:
    """One intermediate-layer snapshot, recorded after the trim."""

    layer_index: int
    frontier_size_in: int
    expansion_calls: int
    children_generated: int
    children_kept: int
    elapsed_ms: float


@dataclass(frozen=True, slots=True)
class PlannerDiagnostics:
    validation_ms: float = 0.0
    resolution_ms: float = 0.0
    station_filter_ms: float = 0.0
    market_query_ms: float = 0.0
    reachability_ms: float = 0.0
    cargo_optimisation_ms: float = 0.0
    render_ms: float = 0.0
    total_planner_ms: float = 0.0
    candidate_trade_count: int = 0
    # Unanchored on-demand-reach instrumentation (zero outside the unanchored
    # path). Examined counts pairs surviving the SQL direct-distance prefilter;
    # accepted counts those whose actual reachability check passed. Bubble
    # systems is the size of the per-request bubble cache at end-of-run; cap
    # hits is the number of commodities that hit the per-commodity cap.
    unanchored_pairs_examined: int = 0
    unanchored_pairs_accepted: int = 0
    unanchored_bubble_systems: int = 0
    unanchored_per_commodity_cap_hits: int = 0
    # Multi-hop instrumentation. hops_planned is 1 for any single-hop run and N
    # for an N-hop plan. multihop_frontier_widths records the surviving
    # frontier size at the end of each expansion layer, useful for spotting a
    # frontier that collapses well before the target hop count.
    # multihop_expansions_examined is the total number of per-node expansions
    # evaluated during the run.
    hops_planned: int = 1
    multihop_frontier_widths: tuple[int, ...] = ()
    multihop_expansions_examined: int = 0
    # Richer multi-hop instrumentation. multihop_layers is one entry per
    # intermediate layer; multihop_expansion_stats aggregates per-call
    # counters across the whole run; multihop_final_hop_stats is filled
    # only when the final hop runs the fixed-terminal --to evaluation.
    multihop_layers: tuple[LayerStats, ...] = ()
    multihop_expansion_stats: ExpansionStats | None = None
    multihop_final_hop_stats: FinalHopStats | None = None


@dataclass(frozen=True, slots=True)
class PartialRouteWarning:
    """Structured warning for a rendered partial multi-hop route.
    
    The planner emits facts only; the text renderer owns user-facing wording.
    phase is currently "expansion" or "final". reason is currently one of
    "no_viable_continuation", "no_reachable_route", or "no_viable_trade".
    """
    
    completed_hops: int
    requested_hops: int
    phase: str
    reason: str


@dataclass(frozen=True, slots=True)
class RunResult:
    routes: tuple[PlannedRoute, ...]
    diagnostics: PlannerDiagnostics = field(default_factory=PlannerDiagnostics)
    warnings: tuple[PartialRouteWarning, ...] = ()