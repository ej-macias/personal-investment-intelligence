"""EODHD: end-of-day prices for the symbols listed in the Airtable instruments table.

The free tier allows 20 calls a day and one call returns one symbol's history, so each run
asks only for the symbols that are behind, stalest first, and only for the missing dates.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx
import psycopg

from invest_intel import config
from invest_intel.ingestion.bronze import Row

BASE_URL = "https://eodhd.com/api"

_SYMBOLS_SQL = """
select distinct symbol
from (
    select distinct on (record_key) payload -> 'fields' ->> 'eodhd_symbol' as symbol
    from raw.airtable_instruments
    order by record_key, loaded_at desc, id desc
) latest
where symbol is not null and symbol <> ''
"""

_LAST_DATES_SQL = "select entity, max(record_key) from raw.eodhd_prices group by entity"


def previous_weekday(day: date) -> date:
    day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def plan_requests(
    symbols: list[str],
    last_dates: dict[str, date],
    today: date,
    budget: int,
    history_days: int,
) -> list[tuple[str, date]]:
    """Pick (symbol, from_date) requests that fit the daily call budget, stalest first."""
    latest_close = previous_weekday(today)
    never_loaded = sorted(s for s in symbols if s not in last_dates)
    behind = sorted(
        (s for s in symbols if s in last_dates and last_dates[s] < latest_close),
        key=lambda s: (last_dates[s], s),
    )
    plan = [(s, today - timedelta(days=history_days)) for s in never_loaded]
    plan += [(s, last_dates[s] + timedelta(days=1)) for s in behind]
    return plan[: max(budget, 0)]


def _fetch_symbol(client: httpx.Client, symbol: str, start: date, today: date) -> list[Row]:
    response = client.get(
        f"/eod/{symbol}", params={"from": start.isoformat(), "to": today.isoformat()}
    )
    response.raise_for_status()
    prices: list[dict[str, Any]] = response.json()
    return [(symbol, p["date"], p) for p in prices]


def fetch(conn: psycopg.Connection, today: date | None = None) -> dict[str, list[Row]]:
    today = today or date.today()
    symbols = [row[0] for row in conn.execute(_SYMBOLS_SQL).fetchall()]
    last_dates = {
        entity: date.fromisoformat(last)
        for entity, last in conn.execute(_LAST_DATES_SQL).fetchall()
    }
    plan = plan_requests(
        symbols,
        last_dates,
        today,
        budget=int(config.env("EODHD_DAILY_CALL_BUDGET", "18")),
        history_days=int(config.env("EODHD_HISTORY_DAYS", "365")),
    )
    return {"eodhd_prices": fetch_history(plan, today)}


def fetch_history(requests: list[tuple[str, date]], today: date) -> list[Row]:
    """Fetch each (symbol, from_date) up to today: one API call per symbol."""
    rows: list[Row] = []
    # The token travels as a query parameter, so never log request URLs or raw httpx errors.
    params = {"api_token": config.require("EODHD_API_TOKEN"), "fmt": "json"}
    with httpx.Client(base_url=BASE_URL, params=params, timeout=30) as client:
        for symbol, start in requests:
            rows.extend(_fetch_symbol(client, symbol, start, today))
    return rows
