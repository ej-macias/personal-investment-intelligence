"""How much money it takes to move the portfolio's average risk, weighted by value."""

from __future__ import annotations

from typing import Any

RISK_LEVELS = range(1, 8)


def new_money_to_reach(rated_value: float, avg_risk: float, goal: float, risk: int) -> float | None:
    """Euros to add at a given risk so the average reaches `goal`. None when money at that risk
    cannot get there: it would have to be on the other side of the goal from today's average."""
    if risk == goal:
        return None
    amount = rated_value * (goal - avg_risk) / (risk - goal)
    return amount if amount >= 0 else None


def switch_amount(rated_value: float, avg_risk: float, goal: float, risk_gap: int) -> float:
    """Euros to move between two holdings whose risks differ by `risk_gap` to reach `goal`. The
    total stays the same, so the average moves by amount x gap / value."""
    return rated_value * abs(goal - avg_risk) / risk_gap


def _amounts(rated_value: float, avg_risk: float, goal: float) -> dict[str, Any]:
    new_money = {
        str(level): round(amount, 2)
        for level in RISK_LEVELS
        if (amount := new_money_to_reach(rated_value, avg_risk, goal, level)) is not None
    }
    switch = {
        str(gap): round(switch_amount(rated_value, avg_risk, goal, gap), 2)
        for gap in range(1, len(RISK_LEVELS))
    }
    return {"new_money_by_risk_level": new_money, "switch_by_risk_gap": switch}


def fix_amounts(row: dict[str, Any]) -> dict[str, Any]:
    """Euros to get back in range (when outside it) and to reach the goal, from a portfolio_risk
    row."""
    value, average = row["rated_value"], row["avg_risk"]
    amounts: dict[str, Any] = {}
    if row.get("points_to_range"):
        amounts["to_range"] = _amounts(value, average, average + row["points_to_range"])
    if row.get("risk_target") is not None and row["risk_target"] != average:
        amounts["to_target"] = _amounts(value, average, row["risk_target"])
    return amounts
