from datetime import date, timedelta

from invest_intel.ingestion.eodhd import plan_requests, previous_weekday

MONDAY = date(2026, 1, 12)
FRIDAY = date(2026, 1, 9)


def test_previous_weekday_skips_the_weekend():
    assert previous_weekday(MONDAY) == FRIDAY


def test_up_to_date_symbols_cost_no_calls():
    assert plan_requests(["A"], {"A": FRIDAY}, MONDAY, budget=18, history_days=365) == []


def test_new_symbols_backfill_and_stale_symbols_resume():
    plan = plan_requests(["A", "B"], {"B": date(2026, 1, 5)}, MONDAY, budget=18, history_days=365)
    assert plan == [("A", MONDAY - timedelta(days=365)), ("B", date(2026, 1, 6))]


def test_budget_caps_calls_and_keeps_the_stalest():
    last = {"A": date(2026, 1, 8), "B": date(2026, 1, 2), "C": date(2026, 1, 6)}
    plan = plan_requests(list(last), last, MONDAY, budget=2, history_days=365)
    assert [symbol for symbol, _ in plan] == ["B", "C"]
