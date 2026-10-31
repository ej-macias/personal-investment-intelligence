from datetime import date

import pytest

from invest_intel.analytics import queries
from invest_intel.analytics.returns import annual_return


def test_one_deposit_growing_ten_percent_in_a_year():
    flows = [(date(2025, 1, 1), -1000.0), (date(2026, 1, 1), 1100.0)]
    assert annual_return(flows) == pytest.approx(0.10, abs=1e-9)


def test_a_loss():
    flows = [(date(2025, 1, 1), -1000.0), (date(2026, 1, 1), 900.0)]
    assert annual_return(flows) == pytest.approx(-0.10, abs=1e-9)


def test_matches_spreadsheet_xirr():
    # The example from the spreadsheet XIRR documentation; its result is 37.34%.
    flows = [
        (date(2008, 1, 1), -10000.0),
        (date(2008, 3, 1), 2750.0),
        (date(2008, 10, 30), 4250.0),
        (date(2009, 2, 15), 3250.0),
        (date(2009, 4, 1), 2750.0),
    ]
    assert annual_return(flows) == pytest.approx(0.373363, abs=1e-6)


def test_money_added_late_weighs_less():
    # Same final gain, but most of the money arrived halfway: a higher rate on less time.
    early = [(date(2025, 1, 1), -2000.0), (date(2026, 1, 1), 2100.0)]
    late = [(date(2025, 1, 1), -100.0), (date(2025, 7, 2), -1900.0), (date(2026, 1, 1), 2100.0)]
    assert annual_return(late) > annual_return(early)


def test_needs_money_in_and_a_value():
    with pytest.raises(ValueError):
        annual_return([(date(2025, 1, 1), -1000.0)])
    with pytest.raises(ValueError):
        annual_return([(date(2025, 1, 1), 1000.0)])


def test_not_shown_for_a_short_history(monkeypatch):
    rows = [
        {"date_day": date(2026, 9, 1), "net_flow": 1000.0, "market_value": 1000.0},
        {"date_day": date(2026, 10, 1), "net_flow": 0.0, "market_value": 1050.0},
    ]
    monkeypatch.setattr(queries.db, "query", lambda sql, params=None: rows)
    result = queries.annual_return()
    assert result["days"] == 30 and result["annual_return"] is None


def test_built_from_flows_and_todays_value(monkeypatch):
    rows = [
        {"date_day": date(2025, 1, 1), "net_flow": 1000.0, "market_value": 1000.0},
        {"date_day": date(2026, 1, 1), "net_flow": 0.0, "market_value": 1100.0},
    ]
    monkeypatch.setattr(queries.db, "query", lambda sql, params=None: rows)
    assert queries.annual_return()["annual_return"] == pytest.approx(0.10, abs=1e-9)


def test_per_year():
    from invest_intel.analytics.returns import per_year

    assert per_year(0.21, 730) == pytest.approx(0.10, abs=1e-3)
    assert per_year(0.10, 365) == pytest.approx(0.10)


def test_summary_gives_the_time_weighted_return_per_year(monkeypatch):
    row = {
        "date_day": date(2026, 1, 1),
        "first_day": date(2024, 1, 2),
        "market_value": 1.0,
        "net_invested": 1.0,
        "total_gain": 0.0,
        "cumulative_twr": 0.21,
    }
    monkeypatch.setattr(queries.db, "query", lambda sql, params=None: [dict(row)])
    summary = queries.portfolio_summary()
    assert summary["twr_per_year"] == pytest.approx(0.10, abs=1e-3)

    row["first_day"] = date(2025, 12, 1)  # a month: too short for a yearly figure
    assert queries.portfolio_summary()["twr_per_year"] is None
