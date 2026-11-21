import pytest

from invest_intel.analytics.risk import fix_amounts, new_money_to_reach, switch_amount


def _average_after_adding(value, average, amount, risk):
    return (value * average + amount * risk) / (value + amount)


@pytest.mark.parametrize(
    ("average", "goal", "risk"), [(5.5, 5, 2), (5.5, 4, 1), (2.5, 3, 6), (2.5, 4, 7)]
)
def test_new_money_reaches_the_goal(average, goal, risk):
    amount = new_money_to_reach(10000, average, goal, risk)
    assert _average_after_adding(10000, average, amount, risk) == pytest.approx(goal)


@pytest.mark.parametrize(("average", "goal", "risk"), [(5.5, 5, 5), (5.5, 5, 6), (2.5, 3, 2)])
def test_new_money_that_cannot_reach_the_goal(average, goal, risk):
    assert new_money_to_reach(10000, average, goal, risk) is None


def test_switch_moves_the_average_by_the_gap():
    amount = switch_amount(10000, 5.5, 5, 3)
    assert 5.5 - amount * 3 / 10000 == pytest.approx(5)


def test_fix_amounts_within_range_only_aims_for_the_target():
    row = {"rated_value": 10000.0, "avg_risk": 4.5, "risk_target": 4.0, "points_to_range": 0.0}
    amounts = fix_amounts(row)
    assert set(amounts) == {"to_target"}
    assert amounts["to_target"]["new_money_by_risk_level"]["3"] == 5000


def test_fix_amounts_without_a_goal_is_empty():
    row = {"rated_value": 10000.0, "avg_risk": 4.5, "risk_target": None, "points_to_range": None}
    assert fix_amounts(row) == {}
