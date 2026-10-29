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
    result = json.loads(tools.run_tool("get_investment_plan", {})[0])
    assert result["plan"] is None and result["total_yearly_fees"] is None
    assert "No plan" in result["note"]


def test_plan_tool_adds_up_fees(monkeypatch):
    monkeypatch.setattr(queries, "investment_plan", lambda: {"goal": "Retirement"})
    monkeypatch.setattr(queries, "target_checks", lambda: [{"label": "Equity"}])
    monkeypatch.setattr(
        queries,
        "investment_returns",
        lambda: [{"yearly_fee": 12.5, "account_id": "ES1"}, {"yearly_fee": 7.25}, {}],
    )
    result, is_error = tools.run_tool("get_investment_plan", {})
    assert not is_error and "ES1" not in result
    assert json.loads(result)["total_yearly_fees"] == 19.75
