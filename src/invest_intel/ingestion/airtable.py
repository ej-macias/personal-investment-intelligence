"""Airtable: manually tracked instruments (metadata + EODHD symbol mapping) and transactions.

Expected fields (see docs/architecture.md):
  instruments:  isin, name, eodhd_symbol, asset_class, region, currency, is_benchmark
  transactions: date, isin, type (buy/sell), quantity, price, fees, account
"""

from __future__ import annotations

from typing import Any

import httpx

from invest_intel import config
from invest_intel.ingestion.bronze import Row

BASE_URL = "https://api.airtable.com/v0"


def _records(client: httpx.Client, base_id: str, table: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset: str | None = None
    while True:
        response = client.get(f"/{base_id}/{table}", params={"offset": offset} if offset else None)
        response.raise_for_status()
        body = response.json()
        records.extend(body["records"])
        offset = body.get("offset")
        if not offset:
            return records


def fetch() -> dict[str, list[Row]]:
    base_id = config.require("AIRTABLE_BASE_ID")
    sources = {
        "airtable_instruments": config.env("AIRTABLE_INSTRUMENTS_TABLE", "instruments"),
        "airtable_transactions": config.env("AIRTABLE_TRANSACTIONS_TABLE", "transactions"),
    }
    headers = {"Authorization": f"Bearer {config.require('AIRTABLE_TOKEN')}"}
    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=30) as client:
        return {
            raw_table: [(table, r["id"], r) for r in _records(client, base_id, table)]
            for raw_table, table in sources.items()
        }
