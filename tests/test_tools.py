import json
from datetime import date

from invest_intel.analytics import queries
from invest_intel.assistant import tools


def test_every_tool_has_a_handler():
    assert {t["name"] for t in tools.TOOLS} == set(tools.HANDLERS)


def test_unknown_tool_is_reported_not_raised():
    assert tools.run_tool("drop_everything", {}) == ("Unknown tool: drop_everything", True)


def test_invalid_arguments_are_reported_to_the_model():
    result, is_error = tools.run_tool("get_portfolio_performance", {"start_date": "last year"})
    assert is_error and result.startswith("Invalid arguments")
    assert tools.run_tool("get_asset_allocation", {"dimension": "isin; drop table x"})[1]


def test_arguments_are_parsed_and_results_serialised(monkeypatch):
    seen = {}

    def fake(start_date=None, end_date=None, frequency="daily"):
        seen.update(start_date=start_date, frequency=frequency)
        return [{"date_day": date(2026, 1, 31), "market_value": 1.0}]

    monkeypatch.setattr(queries, "portfolio_performance", fake)
    result, is_error = tools.run_tool("get_portfolio_performance", {"start_date": "2026-01-01"})
    assert not is_error
    assert seen == {"start_date": date(2026, 1, 1), "frequency": "monthly"}
    assert json.loads(result) == [{"date_day": "2026-01-31", "market_value": 1.0}]


def test_account_ids_never_reach_the_model(monkeypatch):
    row = {"isin": "IE00B4L5Y983", "account_id": "ES0000000001", "amount": 100.0}
    monkeypatch.setattr(queries, "transactions", lambda isin=None, limit=50: [row])
    monkeypatch.setattr(queries, "investment_returns", lambda: [row])
    for name in ("get_transactions", "get_investment_returns"):
        result, is_error = tools.run_tool(name, {})
        assert not is_error
        assert "ES0000000001" not in result and "account_id" not in result
        assert json.loads(result) == [{"isin": "IE00B4L5Y983", "amount": 100.0}]


def test_plan_tool_without_a_plan(monkeypatch):
    monkeypatch.setattr(queries, "investment_plan", lambda: {})
    monkeypatch.setattr(queries, "target_checks", lambda: [])
    monkeypatch.setattr(queries, "investment_returns", lambda: [{"yearly_fee": None}])
    monkeypatch.setattr(queries, "portfolio_risk", lambda: {})
    result = json.loads(tools.run_tool("get_investment_plan", {})[0])
    assert result["plan"] is None and result["total_yearly_fees"] is None
    assert result["risk"] is None
    assert "No plan" in result["note"]


def test_plan_tool_adds_up_fees(monkeypatch):
    monkeypatch.setattr(queries, "investment_plan", lambda: {"goal": "Retirement"})
    monkeypatch.setattr(queries, "target_checks", lambda: [{"label": "Equity"}])
    monkeypatch.setattr(
        queries,
        "investment_returns",
        lambda: [{"yearly_fee": 12.5, "account_id": "ES1"}, {"yearly_fee": 7.25}, {}],
    )
    monkeypatch.setattr(queries, "portfolio_risk", lambda: {})
    result, is_error = tools.run_tool("get_investment_plan", {})
    assert not is_error and "ES1" not in result
    assert json.loads(result)["total_yearly_fees"] == 19.75


def test_plan_tool_reports_risk_and_unrated_holdings(monkeypatch):
    monkeypatch.setattr(queries, "investment_plan", lambda: {"goal": "Retirement"})
    monkeypatch.setattr(queries, "target_checks", lambda: [])
    monkeypatch.setattr(
        queries,
        "investment_returns",
        lambda: [
            {"isin": "A", "instrument_name": "World", "quantity": 1, "risk_level": 6},
            {"isin": "B", "instrument_name": "New fund", "quantity": 1, "risk_level": None},
            {"isin": "C", "instrument_name": "Sold", "quantity": 0, "risk_level": None},
        ],
    )
    monkeypatch.setattr(
        queries,
        "portfolio_risk",
        lambda: {
            "rated_value": 10000.0,
            "rated_share": 0.8,
            "avg_risk": 5.5,
            "risk_min": 3.0,
            "risk_target": 4.0,
            "risk_max": 5.0,
            "status": "Above maximum",
            "points_to_range": -0.5,
        },
    )
    risk = json.loads(tools.run_tool("get_investment_plan", {})[0])["risk"]
    assert risk["average"] == 5.5 and risk["status"] == "Above maximum"
    assert risk["unrated_holdings"] == ["New fund"]
    # 10,000 at 5.5 plus 2,500 at risk 3 averages 5.
    assert risk["euros_to_fix"]["to_range"]["new_money_by_risk_level"]["3"] == 2500
    assert risk["euros_to_fix"]["to_range"]["switch_by_risk_gap"]["2"] == 2500
