"""Fictional portfolio for the public demo: `python -m invest_intel.synthetic.generate`.

Writes made-up holdings and transactions into the same raw tables, in the same payload shapes,
as the real ingestion. Everything downstream (dbt, app, assistant) therefore runs unchanged on
demo data. Refuses to run unless APP_ENV=demo.

Prices are random paths by default, which keeps CI and the tests offline. With --real-prices
the portfolio is valued at real EODHD closes of public ETFs instead. Only EODHD is called,
never Indexa or Airtable, so nothing personal can reach the demo.
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from invest_intel import config, db
from invest_intel.ingestion import bronze, eodhd
from invest_intel.ingestion.bronze import Row
from invest_intel.ingestion.run import _describe

INDEXA_ACCOUNT = "DEMO0001"
BROKER_ACCOUNT = "Demo Broker"
MONTHLY_CONTRIBUTION = 800.0

# isin, name, EODHD symbol, asset class, region, source, target weight,
# then annual drift and volatility for the random price paths
INSTRUMENTS = [
    (
        "IE00B4L5Y983",
        "iShares Core MSCI World UCITS ETF",
        "EUNL.XETRA",
        "Equity",
        "Global",
        "indexa",
        0.45,
        0.08,
        0.15,
    ),
    (
        "IE00BKM4GZ66",
        "iShares Core MSCI EM IMI UCITS ETF",
        "IS3N.XETRA",
        "Equity",
        "Emerging",
        "indexa",
        0.10,
        0.07,
        0.20,
    ),
    (
        "IE00B4WXJJ64",
        "iShares Core Euro Government Bond UCITS ETF",
        "EUNH.XETRA",
        "Fixed income",
        "Europe",
        "indexa",
        0.25,
        0.02,
        0.05,
    ),
    (
        "IE00BF4RFH31",
        "iShares MSCI World Small Cap UCITS ETF",
        "IUSN.XETRA",
        "Equity",
        "Global",
        "indexa",
        0.05,
        0.08,
        0.18,
    ),
    (
        "IE00B3WJKG14",
        "iShares S&P 500 Information Technology Sector UCITS ETF",
        "QDVE.XETRA",
        "Equity",
        "North America",
        "airtable",
        0.07,
        0.11,
        0.25,
    ),
    (
        "DE000A0S9GB0",
        "Xetra-Gold",
        "4GLD.XETRA",
        "Commodities",
        "Global",
        "airtable",
        0.05,
        0.05,
        0.14,
    ),
    (
        "DE0007164600",
        "SAP SE",
        "SAP.XETRA",
        "Equity",
        "Europe",
        "airtable",
        0.03,
        0.09,
        0.35,
    ),
]
BENCHMARK = (
    "IE00B6R52259",
    "iShares MSCI ACWI UCITS ETF",
    "IUSQ.XETRA",
    "Equity",
    "Global",
    0.075,
    0.15,
)
SYMBOLS = [i[2] for i in INSTRUMENTS] + [BENCHMARK[2]]


def _business_days(start: date, end: date) -> list[date]:
    days = []
    day = start
    while day <= end:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def _price_path(
    rng: random.Random, days: list[date], drift: float, volatility: float
) -> dict[date, float]:
    price = 100.0
    path = {}
    for day in days:
        price *= 1 + rng.gauss(drift / 252, volatility / 252**0.5)
        path[day] = round(price, 4)
    return path


def _price_on(path: dict[date, float], day: date) -> float:
    """Last close on or before the day, so exchange holidays reuse the previous quote."""
    return path[max(d for d in path if d <= day)]


def _eodhd_rows(symbol: str, path: dict[date, float]) -> list[Row]:
    return [
        (
            symbol,
            day.isoformat(),
            {
                "date": day.isoformat(),
                "open": p,
                "high": p,
                "low": p,
                "close": p,
                "adjusted_close": p,
                "volume": 0,
            },
        )
        for day, p in path.items()
    ]


def generate(
    today: date,
    seed: int = 42,
    years: int = 3,
    prices: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, list[Row]]:
    """Build every raw table. `prices` holds EODHD payloads by symbol; None means random paths."""
    rng = random.Random(seed)
    tables: dict[str, list[Row]] = {name: [] for name in bronze.RAW_TABLES}

    catalogue = [(i[0], i[1], i[2], i[3], i[4], False, i[7], i[8]) for i in INSTRUMENTS]
    catalogue.append((*BENCHMARK[:5], True, BENCHMARK[5], BENCHMARK[6]))

    paths: dict[str, dict[date, float]] = {}
    if prices is None:
        days = _business_days(today - timedelta(days=365 * years), today)
        for isin, _, symbol, _, _, _, drift, vol in catalogue:
            paths[isin] = _price_path(rng, days, drift, vol)
            tables["eodhd_prices"].extend(_eodhd_rows(symbol, paths[isin]))
    else:
        for isin, _, symbol, *_ in catalogue:
            quotes = [p for p in prices.get(symbol, []) if p.get("close") is not None]
            if not quotes:
                raise ValueError(f"No EODHD prices for {symbol}")
            paths[isin] = {date.fromisoformat(p["date"]): float(p["close"]) for p in quotes}
            tables["eodhd_prices"].extend((symbol, p["date"], p) for p in quotes)
        # Start once every instrument has a quote, so each trade has a price.
        days = _business_days(max(min(path) for path in paths.values()), today)

    for n, (isin, name, symbol, asset_class, region, is_benchmark, _, _) in enumerate(catalogue):
        fields: dict[str, Any] = {
            "isin": isin,
            "name": name,
            "eodhd_symbol": symbol,
            "asset_class": asset_class,
            "region": region,
            "currency": "EUR",
        }
        if is_benchmark:  # Airtable omits unchecked checkboxes
            fields["is_benchmark"] = True
        tables["airtable_instruments"].append(
            ("instruments", f"recINS{n:04d}", {"id": f"recINS{n:04d}", "fields": fields})
        )

    holdings = {i[0]: 0.0 for i in INSTRUMENTS}
    contribution_days = [d for n, d in enumerate(days) if n == 0 or days[n - 1].month != d.month]
    sell_day = contribution_days[len(contribution_days) // 2]
    sequence = 0

    def trade(day: date, instrument: tuple, kind: str, quantity: float) -> None:
        nonlocal sequence
        sequence += 1
        isin, name, source = instrument[0], instrument[1], instrument[5]
        price = _price_on(paths[isin], day)
        holdings[isin] += quantity if kind == "buy" else -quantity
        if source == "indexa":
            reference = f"T{sequence:06d}"
            payload = {
                "reference": reference,
                "date": day.isoformat(),
                "instrument": {"identifier": isin, "name": name},
                "operation_type": kind,
                "titles": quantity,
                "price": price,
                "amount": round(quantity * price, 2),
            }
            tables["indexa_instrument_transactions"].append((INDEXA_ACCOUNT, reference, payload))
        else:
            record_id = f"recTRX{sequence:04d}"
            fields = {
                "date": day.isoformat(),
                "isin": isin,
                "type": kind,
                "quantity": quantity,
                "price": price,
                "fees": 1.5,
                "account": BROKER_ACCOUNT,
            }
            tables["airtable_transactions"].append(
                ("transactions", record_id, {"id": record_id, "fields": fields})
            )

    for day in contribution_days:
        for instrument in INSTRUMENTS:
            amount = MONTHLY_CONTRIBUTION * instrument[6] * rng.uniform(0.9, 1.1)
            price = _price_on(paths[instrument[0]], day)
            trade(day, instrument, "buy", round(amount / price, 4))
        if day == sell_day:
            stock = INSTRUMENTS[-1]
            trade(day, stock, "sell", round(holdings[stock[0]] / 2, 4))

    last_day = days[-1]
    positions = []
    for i in INSTRUMENTS:
        if i[5] != "indexa":
            continue
        price = _price_on(paths[i[0]], last_day)
        positions.append(
            {
                "instrument": {"identifier": i[0], "name": i[1]},
                "titles": round(holdings[i[0]], 4),
                "price": price,
                "amount": round(holdings[i[0]] * price, 2),
            }
        )
    snapshot = {
        "portfolio": {
            "date": last_day.isoformat(),
            "total_amount": round(sum(p["amount"] for p in positions), 2),
        },
        "instrument_accounts": [{"positions": positions}],
    }
    tables["indexa_portfolio"].append((INDEXA_ACCOUNT, last_day.isoformat(), snapshot))
    return tables


def fetch_prices(today: date) -> dict[str, list[dict[str, Any]]]:
    """One EODHD call per demo symbol, covering EODHD_HISTORY_DAYS."""
    start = today - timedelta(days=int(config.env("EODHD_HISTORY_DAYS", "365")))
    prices: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for symbol, _, payload in eodhd.fetch_history([(s, start) for s in SYMBOLS], today):
        prices[symbol].append(payload)
    return prices


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--real-prices", action="store_true", help="value the portfolio at real EODHD closes"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    log = logging.getLogger("synthetic")
    if not config.is_demo():
        log.error(
            "Refusing to run: this replaces the raw tables. Set APP_ENV=demo on a demo database."
        )
        return 2

    today = date.today()
    # Fetch before touching the database: if EODHD fails, last run's demo data stays in place.
    try:
        prices = fetch_prices(today) if args.real_prices else None
    except Exception as exc:  # noqa: BLE001 - the token is in the URL, so log the type only
        log.error("EODHD prices unavailable: %s", _describe(exc))
        return 1
    try:
        tables = generate(today, prices=prices)
    except ValueError as exc:  # a symbol without quotes; symbols are public
        log.error("%s", exc)
        return 1

    with db.connect() as conn:
        bronze.ensure_tables(conn)
        bronze.truncate_all(conn)
        for table, rows in tables.items():
            bronze.load(conn, table, rows, run_id="synthetic")
            log.info("%s: %d rows", table, len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
