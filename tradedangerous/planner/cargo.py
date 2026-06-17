"""Bounded multi-commodity cargo optimiser."""

from __future__ import annotations

import time
from dataclasses import dataclass

from .failures import NoProfitableTrades
from .run_result import CargoLine, CargoPlan, TradeCandidate


# Debug instrumentation: how often the exact greedy fast path is taken versus
# the branch-and-bound fallback, how many solves the caller pre-empted as
# unwinnable, and the wall time spent fitting cargo. A plain dict so it can be
# mutated without a module-level rebinding. Reset per run by the planner and
# surfaced in the diagnostics line, so the cargo cost split is visible without
# a profiler.
_cargo_path_counts = {"fast": 0, "recursive": 0, "pruned": 0, "ms": 0.0}


def reset_cargo_counters() -> None:
    """Zero the cargo path counters at the start of a planner run."""
    _cargo_path_counts["fast"] = 0
    _cargo_path_counts["recursive"] = 0
    _cargo_path_counts["pruned"] = 0
    _cargo_path_counts["ms"] = 0.0


def cargo_counters() -> tuple[int, int]:
    """Return (fast_path_hits, recursive_hits) since the last reset."""
    return _cargo_path_counts["fast"], _cargo_path_counts["recursive"]


def cargo_pruned() -> int:
    """Return the count of solves skipped as unwinnable since the last reset."""
    return _cargo_path_counts["pruned"]


def cargo_time_ms() -> float:
    """Return total wall time (ms) spent in optimise_cargo since the last reset.

    Accumulated across every caller, so any route shape gets a per-run cargo
    cost without each engine timing its own optimise_cargo calls.
    """
    return _cargo_path_counts["ms"]


# Branch-and-bound stops on two conditions, whichever fires first.
#
# Primary stop — no improvement for a while: the search records the node at
# which it last bettered its incumbent, and gives up once it has gone
# _SEARCH_NO_IMPROVEMENT_LIMIT nodes with no further improvement. A seeded,
# tightly-bounded search reaches the optimum early, then only *proves* that
# nothing better exists — wasted work for us. So we stop, confident in the
# incumbent, rather than pay to prove it optimal. On large holds (the
# branching factor is the hold size) that proof otherwise grinds for tens of
# thousands of nodes per solve, and there is one solve per candidate pair.
#
# Outer fuse — _SEARCH_NODE_LIMIT: a hard ceiling so a pathological mix can
# never hang the planner. Sized well above where real answers settle, not a
# tuning value; the no-improvement stop is what ends a normal search.
#
# Either stop returns the best feasible plan found so far (always at least
# the greedy seed), so the result stays valid — at worst slightly under-
# optimal on a pathological instance. Both are levers, tunable on evidence
# like the beam width.
_SEARCH_NO_IMPROVEMENT_LIMIT = 500
_SEARCH_NODE_LIMIT = 2_000


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
    prune_below_raw: float | None = None,
    ignore_credits: bool = False,
) -> CargoPlan | None:
    """Time-wrapped entry point for the cargo optimiser.

    Delegates to _optimise_cargo and accumulates the wall time into the module
    counter, so the per-run cargo cost is visible in diagnostics for any route
    shape without each engine timing its own calls. ``prune_below_raw`` is
    passed through: when the pair cannot beat the caller's kept threshold the
    delegate returns None, and that None is returned here unchanged.
    ``ignore_credits`` drops the credit constraint entirely for the
    no-affordability optimistic pass — see _optimise_cargo.
    """

    started = time.perf_counter()
    try:
        return _optimise_cargo(
            candidates,
            capacity_units=capacity_units,
            available_credits=available_credits,
            cargo_limit_per_item=cargo_limit_per_item,
            prune_below_raw=prune_below_raw,
            ignore_credits=ignore_credits,
        )
    finally:
        _cargo_path_counts["ms"] += (time.perf_counter() - started) * 1000.0


def _optimise_cargo(
    candidates: tuple[TradeCandidate, ...],
    *,
    capacity_units: int,
    available_credits: int,
    cargo_limit_per_item: int = 0,
    prune_below_raw: float | None = None,
    ignore_credits: bool = False,
) -> CargoPlan | None:
    """Return an optimal cargo plan for one hop, or None when pre-empted.

    The objective is maximum total profit under shared cargo capacity and
    credit constraints, with source supply and destination demand as hard caps.

    When ``prune_below_raw`` is supplied, the optimiser first checks the
    admissible root bound (the most profit this pair could possibly yield). If
    even that cannot reach ``prune_below_raw``, the pair cannot beat what the
    caller is already keeping, so the full solve is skipped and None is
    returned. None is distinct from the NoProfitableTrades raise, which means no
    viable plan exists at all.

    ``ignore_credits`` drops the credit constraint: quantities are bounded by
    capacity, supply and demand only, and the greedy capacity fill runs. The via
    search uses it so the optimistic pass cannot fall into branch-and-bound even
    under --max-price 0, where no fixed budget could prove credits non-binding.
    """

    bounded = _build_bounded_candidates(
        candidates,
        capacity_units=capacity_units,
        available_credits=available_credits,
        cargo_limit_per_item=cargo_limit_per_item,
        ignore_credits=ignore_credits,
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

    # Positions into `bounded` ordered by profit per credit (profit_per_unit /
    # buy_price) descending. The credit-relaxation half of the pruning bound
    # walks items in this order; precomputed once so each bound call stays O(n).
    credit_order = sorted(
        range(len(bounded)),
        key=lambda i: bounded[i].trade.profit_per_unit / bounded[i].trade.buy_price,
        reverse=True,
    )

    best_quantities = [0] * len(bounded)
    current_quantities = [0] * len(bounded)
    best_profit = 0
    best_cost = 0
    visited = 0
    last_improve_at = 0

    def optimistic_upper_bound(
        index: int,
        remaining_capacity: int,
        remaining_credits: int,
        current_profit: int,
    ) -> float:
        # Admissible upper bound for pruning. Each of the two shared constraints
        # — cargo capacity and the running credit budget — is relaxed away in
        # turn, the remaining single-constraint knapsack solved optimally, and
        # the *smaller* of the two results used. Dropping a constraint can only
        # raise the optimum, so each half is a true over-estimate of the real
        # subtree optimum; the min of two over-estimates is the tighter one and
        # still an over-estimate, so "bound <= best" pruning stays safe.
        #
        # Both halves are needed. The capacity half alone is far too loose when
        # credits bind — it ignores the budget, barely prunes, and the search
        # explodes; the credit half alone is loose when capacity binds.
        # Whichever constraint actually bites supplies the tight bound.
        #
        # A single greedy that *spends* the budget would be unsafe: that is a
        # feasible-solution value (a lower bound), which can fall below the
        # subtree optimum and prune the best plan. The real credit constraint
        # is still enforced in search(), which only generates affordable combos.

        # Capacity relaxation: greedy by profit-per-unit (bounded is already in
        # that order), integer fill — exact for unit cargo weights.
        capacity = remaining_capacity
        cap_bound = 0.0
        for idx in range(index, len(bounded)):
            if capacity <= 0:
                break
            candidate = bounded[idx]
            quantity = min(candidate.max_quantity, capacity)
            cap_bound += quantity * candidate.trade.profit_per_unit
            capacity -= quantity

        if ignore_credits:
            # No-affordability pass: credit must not bind anywhere, the prune
            # bound included. Capacity-only is still an admissible over-estimate
            # (dropping the credit constraint can only raise the optimum), so the
            # prune stays sound without a finite credit ceiling that --max-price
            # 0 could trip into pruning a valid expensive candidate.
            return current_profit + cap_bound

        # Credit relaxation: fractional knapsack on the budget, greedy by
        # profit-per-credit. Allowing the last item to be taken fractionally is
        # what makes this an over-estimate rather than a feasible value.
        budget = float(remaining_credits)
        credit_bound = 0.0
        for pos in credit_order:
            if pos < index:
                # Already decided by an outer search level.
                continue
            if budget <= 0:
                break
            candidate = bounded[pos]
            buy_price = candidate.trade.buy_price
            quantity = min(candidate.max_quantity, budget / buy_price)
            credit_bound += quantity * candidate.trade.profit_per_unit
            budget -= quantity * buy_price

        return current_profit + min(cap_bound, credit_bound)

    def search(
        index: int,
        remaining_capacity: int,
        remaining_credits: int,
        current_profit: int,
        current_cost: int,
    ) -> None:
        nonlocal best_cost, best_profit, best_quantities
        nonlocal visited, last_improve_at

        visited += 1
        # Confident stop: give up once we've gone this many nodes without
        # bettering the incumbent, rather than keep proving it optimal.
        if visited - last_improve_at > _SEARCH_NO_IMPROVEMENT_LIMIT:
            return
        # Outer fuse so a pathological mix can never hang the planner.
        if visited > _SEARCH_NODE_LIMIT:
            return

        if index >= len(bounded):
            if current_profit > best_profit:
                best_profit = current_profit
                best_cost = current_cost
                best_quantities = current_quantities.copy()
                last_improve_at = visited
            return

        if (
            optimistic_upper_bound(
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

    def greedy_feasible(order):
        # A feasible plan respecting BOTH capacity and credits, taking items in
        # the given order. Used to seed the search incumbent so the admissible
        # bound prunes hard from the root.
        quantities = [0] * len(bounded)
        capacity = capacity_units
        budget = available_credits
        profit = 0
        cost = 0
        for idx in order:
            if capacity <= 0:
                break
            candidate = bounded[idx]
            buy_price = candidate.trade.buy_price
            quantity = min(candidate.max_quantity, capacity, budget // buy_price)
            if quantity <= 0:
                continue
            quantities[idx] = quantity
            capacity -= quantity
            budget -= quantity * buy_price
            profit += quantity * candidate.trade.profit_per_unit
            cost += quantity * buy_price
        return quantities, profit, cost

    if prune_below_raw is not None:
        # Caller-supplied skip: if the most profit this pair could ever yield —
        # the admissible root bound — cannot reach the score the caller is
        # already keeping, the full solve is wasted. Strict <, so a pair that
        # merely ties the threshold is still solved and left to the caller's
        # tie-break. Counted apart from the "no viable plan" raise below.
        root_bound = optimistic_upper_bound(
            0, capacity_units, available_credits, 0
        )
        if root_bound < prune_below_raw:
            _cargo_path_counts["pruned"] += 1
            return None

    if ignore_credits or _credit_cannot_bind(
        bounded, capacity_units, available_credits
    ):
        # Exact greedy fast path. With unit cargo weights and a budget that
        # cannot bind, taking the highest profit-per-unit candidates first up to
        # capacity is optimal — the same answer branch-and-bound reaches, but
        # without the recursion. bounded is already sorted by profit-per-unit,
        # so one pass fills the hold. This is the common case for the
        # open-origin backward search, which fits cargo against a deliberately
        # non-binding optimistic budget.
        _cargo_path_counts["fast"] += 1
        remaining_capacity = capacity_units
        for index, candidate in enumerate(bounded):
            if remaining_capacity <= 0:
                break
            quantity = min(candidate.max_quantity, remaining_capacity)
            if quantity <= 0:
                continue
            best_quantities[index] = quantity
            best_profit += quantity * candidate.trade.profit_per_unit
            best_cost += quantity * candidate.trade.buy_price
            remaining_capacity -= quantity
    else:
        _cargo_path_counts["recursive"] += 1
        # Seed the incumbent with the better of two cheap feasible greedies —
        # one ranked by profit-per-unit, one by profit-per-credit — so the
        # admissible bound has a strong lower bound to prune against from the
        # first node. Starting from a zero incumbent is what let the search
        # explode when credits bind.
        seed_quantities, seed_profit, seed_cost = max(
            (greedy_feasible(range(len(bounded))), greedy_feasible(credit_order)),
            key=lambda seed: seed[1],
        )
        best_quantities = seed_quantities
        best_profit = seed_profit
        best_cost = seed_cost
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
    ignore_credits: bool = False,
) -> list[_BoundedCandidate]:
    bounded = []

    for trade in candidates:
        if trade.profit_per_unit <= 0 or trade.buy_price <= 0:
            continue

        caps = [
            trade.source_supply_units,
            trade.effective_destination_demand_units,
            capacity_units,
        ]
        if not ignore_credits:
            # The credit cap: no more than the budget can buy. Dropped in the
            # no-affordability pass so the fill is capacity-bound only and
            # credits provably cannot bind, whatever the prices.
            caps.append(available_credits // trade.buy_price)
        max_quantity = min(caps)
        if cargo_limit_per_item > 0:
            max_quantity = min(max_quantity, cargo_limit_per_item)

        if max_quantity > 0:
            bounded.append(_BoundedCandidate(trade=trade, max_quantity=max_quantity))

    return bounded


def _credit_cannot_bind(
    bounded: list[_BoundedCandidate],
    capacity_units: int,
    available_credits: int,
) -> bool:
    """Return True when the credit budget cannot constrain the cargo plan.

    If filling the entire hold with the most expensive available candidate
    still costs no more than the budget, no quantity choice can be limited by
    credits — so the greedy fill by profit-per-unit is the exact optimum and
    the branch-and-bound search is unnecessary. ``bounded`` is non-empty here:
    optimise_cargo returns early when it is empty.
    """

    max_buy_price = max(candidate.trade.buy_price for candidate in bounded)
    return available_credits >= capacity_units * max_buy_price