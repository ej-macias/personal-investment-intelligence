"""Synthetic portfolio for the public demo: `python -m invest_intel.synthetic.generate`.

Writes fictional instruments, prices and transactions into the same raw tables, in the same
payload shapes, as the real ingestion. Everything downstream (dbt, app, assistant) therefore
runs unchanged on demo data. Refuses to run unless APP_ENV=demo.
"""

from __future__ import annotations

import logging
import random
import sys
from datetime import date, timedelta
from typing import Any

from invest_intel import config, db
from invest_intel.ingestion import bronze
from invest_intel.ingestion.bronze import Row

INDEXA_ACCOUNT = "DEMO0001"
BROKER_ACCOUNT = "Demo Broker"
MONTHLY_CONTRIBUTION = 800.0

# isin, name, symbol, asset class, region, source, target weight, annual drift, annual volatility
INSTRUMENTS = [
    (
        "XX0000000001",
        "Global Equity Index Fund",
        "GLEQ.DEMO",
        "Equity",
        "Global",
        "indexa",
        0.45,
        0.08,
        0.15,
    ),
    (
        "XX0000000002",
        "Emerging Markets Index Fund",
        "EMEQ.DEMO",
        "Equity",
        "Emerging",
        "indexa",
        0.10,
        0.07,
        0.20,
    ),
    (
        "XX0000000003",
        "Euro Government Bond Index Fund",
        "EUGB.DEMO",
        "Fixed income",
        "Europe",
        "indexa",
        0.25,
        0.02,
        0.05,
    ),
    (
        "XX0000000004",
        "Global Small Cap Index Fund",
        "GLSC.DEMO",
        "Equity",
        "Global",
        "indexa",
        0.05,
        0.08,
        0.18,
    ),
    (
        "XX0000000005",
        "Technology Sector ETF",
        "TECH.DEMO",
        "Equity",
        "North America",
        "airtable",
        0.07,
        0.11,
        0.25,
    ),
    (
        "XX0000000006",
        "Physical Gold ETC",
        "GOLD.DEMO",
        "Commodities",
        "Global",
        "airtable",
        0.05,
        0.05,
        0.14,
    ),
    (
        "XX0000000007",
        "Acme Robotics plc",
        "ACME.DEMO",
        "Equity",
        "Europe",
        "airtable",
        0.03,
        0.09,
        0.35,
    ),
]
BENCHMARK = (
    "XX0000000099",
    "Global Equity Benchmark Index",
    "BENCH.DEMO",
    "Equity",
    "Global",
    0.075,
    0.15,
)


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


def generate(today: date, seed: int = 42, years: int = 3) -> dict[str, list[Row]]:
    rng = random.Random(seed)
    days = _business_days(today - timedelta(days=365 * years), today)
    tables: dict[str, list[Row]] = {name: [] for name in bronze.RAW_TABLES}

    paths: dict[str, dict[date, float]] = {}
    catalogue = [(i[0], i[1], i[2], i[3], i[4], False, i[7], i[8]) for i in INSTRUMENTS]
    catalogue.append((*BENCHMARK[:5], True, BENCHMARK[5], BENCHMARK[6]))
    for n, (isin, name, symbol, asset_class, region, is_benchmark, drift, vol) in enumerate(
        catalogue
    ):
        paths[isin] = _price_path(rng, days, drift, vol)
        tables["eodhd_prices"].extend(_eodhd_rows(symbol, paths[isin]))
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
        price = paths[isin][day]
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
            trade(day, instrument, "buy", round(amount / paths[instrument[0]][day], 4))
        if day == sell_day:
            acme = INSTRUMENTS[-1]
            trade(day, acme, "sell", round(holdings[acme[0]] / 2, 4))

    last_day = days[-1]
    positions = [
        {
            "instrument": {"identifier": i[0], "name": i[1]},
            "titles": round(holdings[i[0]], 4),
            "price": paths[i[0]][last_day],
            "amount": round(holdings[i[0]] * paths[i[0]][last_day], 2),
        }
        for i in INSTRUMENTS
        if i[5] == "indexa"
    ]
    snapshot = {
        "portfolio": {
            "date": last_day.isoformat(),
            "total_amount": round(sum(p["amount"] for p in positions), 2),
        },
        "instrument_accounts": [{"positions": positions}],
    }
    tables["indexa_portfolio"].append((INDEXA_ACCOUNT, last_day.isoformat(), snapshot))
    return tables


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    log = logging.getLogger("synthetic")
    if not config.is_demo():
        log.error(
            "Refusing to run: this replaces the raw tables. Set APP_ENV=demo on a demo database."
        )
        return 2
    tables = generate(date.today())
    with db.connect() as conn:
        bronze.ensure_tables(conn)
        bronze.truncate_all(conn)
        for table, rows in tables.items():
            bronze.load(conn, table, rows, run_id="synthetic")
            log.info("%s: %d rows", table, len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
