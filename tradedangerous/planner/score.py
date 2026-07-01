"""Scoring helpers for trade run planning."""

from __future__ import annotations

import math


def raw_profit_score(profit: int) -> float:
    """Return the unadjusted score for a profitable hop or route."""

    return float(profit)


def ls_penalty_multiplier(distance_ls: int | None, penalty_percent: float) -> float:
    """Return the protected arrival-distance score multiplier.

    The curve mildly favours nearby stations, then increasingly penalises
    stations that require long supercruise travel from the arrival star.
    """

    if penalty_percent <= 0:
        return 1.0

    distance_ls = max(int(distance_ls or 0), 0)
    x = math.floor((distance_ls / 1000.0) * 10.0) / 10.0
    weight = max(0.0, min(float(penalty_percent) / 100.0, 1.0))

    def sigmoid(value: float) -> float:
        return value / (1.0 + abs(value))

    boost = (1.0 - sigmoid(25.0 * (x - 1.0))) / 4.0
    drop = (-1.0 - sigmoid(50.0 * (x - 4.0))) / 4.0

    try:
        middle = (-1.0 + 1.0 / (x + 1.0) ** ((x + 1.0) / 4.0)) / 2.0
    except OverflowError:
        # Extremely distant stations should not win due to numeric overflow.
        middle = -0.5

    curve = boost + drop + middle
    return 1.0 + curve * weight


def score_with_destination_penalty(
    profit: int,
    *,
    destination_distance_ls: int | None,
    penalty_percent: float,
) -> float:
    """Score a hop using raw profit and destination arrival distance."""

    return raw_profit_score(profit) * ls_penalty_multiplier(
        destination_distance_ls,
        penalty_percent,
    )