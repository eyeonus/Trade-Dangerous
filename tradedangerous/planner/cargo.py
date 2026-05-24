"""Bounded multi-commodity cargo optimiser."""

from __future__ import annotations

from dataclasses import dataclass

from .failures import NoProfitableTrades
from .run_result import CargoLine, CargoPlan, TradeCandidate


@dataclass(frozen=True, slots=True)
class _BoundedCandidate:
    trade: TradeCandidate
    max_quantity: int


def optimise_cargo(
    candidates: tuple[TradeCandidate, ...],
    *,
    capacity_units: int,
    available_credits: int,
    cargo_limit_per_item: int = 0,
) -> CargoPlan:
    """Return an optimal cargo plan for one hop.

    The objective is maximum total profit under shared cargo capacity and
    credit constraints, with source supply and destination demand as hard caps.
    """

    bounded = _build_bounded_candidates(
        candidates,
        capacity_units=capacity_units,
        available_credits=available_credits,
        cargo_limit_per_item=cargo_limit_per_item,
    )
    if not bounded:
        raise NoProfitableTrades("No viable cargo plan was available.")

    bounded.sort(
        key=lambda c: (
            c.trade.profit_per_unit,
            -c.trade.buy_price,
            c.trade.item_name,
        ),
        reverse=True,
    )

    best_quantities = [0] * len(bounded)
    current_quantities = [0] * len(bounded)
    best_profit = 0
    best_cost = 0

    def fractional_upper_bound(
        index: int,
        remaining_capacity: int,
        remaining_credits: int,
        current_profit: int,
    ) -> float:
        bound = float(current_profit)
        for idx in range(index, len(bounded)):
            candidate = bounded[idx]
            trade = candidate.trade
            if remaining_capacity <= 0:
                break
            if remaining_credits < trade.buy_price:
                continue

            quantity = min(
                candidate.max_quantity,
                remaining_capacity,
                remaining_credits // trade.buy_price,
            )
            if quantity <= 0:
                continue

            bound += quantity * trade.profit_per_unit
            remaining_capacity -= quantity
            remaining_credits -= quantity * trade.buy_price

        return bound

    def search(
        index: int,
        remaining_capacity: int,
        remaining_credits: int,
        current_profit: int,
        current_cost: int,
    ) -> None:
        nonlocal best_cost, best_profit, best_quantities

        if index >= len(bounded):
            if current_profit > best_profit:
                best_profit = current_profit
                best_cost = current_cost
                best_quantities = current_quantities.copy()
            return

        if (
            fractional_upper_bound(
                index,
                remaining_capacity,
                remaining_credits,
                current_profit,
            )
            <= best_profit
        ):
            return

        candidate = bounded[index]
        trade = candidate.trade
        max_quantity = min(
            candidate.max_quantity,
            remaining_capacity,
            remaining_credits // trade.buy_price,
        )

        for quantity in range(max_quantity, -1, -1):
            current_quantities[index] = quantity
            search(
                index + 1,
                remaining_capacity - quantity,
                remaining_credits - quantity * trade.buy_price,
                current_profit + quantity * trade.profit_per_unit,
                current_cost + quantity * trade.buy_price,
            )
        current_quantities[index] = 0

    search(
        index=0,
        remaining_capacity=capacity_units,
        remaining_credits=available_credits,
        current_profit=0,
        current_cost=0,
    )

    if best_profit <= 0:
        raise NoProfitableTrades("No viable cargo plan was available.")

    lines = []
    for candidate, quantity in zip(bounded, best_quantities):
        if quantity <= 0:
            continue

        trade = candidate.trade
        lines.append(
            CargoLine(
                item_id=trade.item_id,
                item_name=trade.item_name,
                quantity=quantity,
                buy_price=trade.buy_price,
                sell_price=trade.sell_price,
                profit_per_unit=trade.profit_per_unit,
                total_cost=quantity * trade.buy_price,
                total_profit=quantity * trade.profit_per_unit,
                source_supply_units=trade.source_supply_units,
                destination_demand_units=trade.destination_demand_units,
                bulk_sale_tax_sensitive=trade.bulk_sale_tax_sensitive,
                effective_destination_demand_units=trade.effective_destination_demand_units,
            )
        )

    lines.sort(key=lambda line: (-line.total_profit, line.item_name))
    units_loaded = sum(line.quantity for line in lines)

    return CargoPlan(
        lines=tuple(lines),
        units_loaded=units_loaded,
        total_cost=best_cost,
        total_profit=best_profit,
        unused_capacity=capacity_units - units_loaded,
        unspent_capital=available_credits - best_cost,
    )


def _build_bounded_candidates(
    candidates: tuple[TradeCandidate, ...],
    *,
    capacity_units: int,
    available_credits: int,
    cargo_limit_per_item: int,
) -> list[_BoundedCandidate]:
    bounded = []

    for trade in candidates:
        if trade.profit_per_unit <= 0 or trade.buy_price <= 0:
            continue

        max_quantity = min(
            trade.source_supply_units,
            trade.effective_destination_demand_units,
            capacity_units,
            available_credits // trade.buy_price,
        )
        if cargo_limit_per_item > 0:
            max_quantity = min(max_quantity, cargo_limit_per_item)

        if max_quantity > 0:
            bounded.append(_BoundedCandidate(trade=trade, max_quantity=max_quantity))

    return bounded