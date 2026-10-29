"""Airtable: instruments, manually tracked transactions, and the owner's plan and targets.

Expected fields (see docs/architecture.md, Airtable base):
  instruments:  isin, name, eodhd_symbol, asset_class, region, instrument_type, liquidity,
                currency, is_benchmark, ter
  transactions: date, isin, type (buy/sell), quantity, price, fees, account
  plan:         goal, horizon_year, rules                                       (optional table)
  targets:      one of asset_classes, regions, instrument_types, liquidity, platforms,
                instruments, each_instrument; min, target, max, note           (optional table)

Every table also yields an IDS_KEY row listing the record ids it has now, so records deleted
in Airtable can be left out downstream even though raw tables are append-only.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from invest_intel import config
from invest_intel.ingestion.bronze import Row
from invest_intel.ingestion.errors import SourceHTTPError

BASE_URL = "https://api.airtable.com/v0"
# record_key of the row holding the table's current record ids; Airtable ids start with "rec".
IDS_KEY = "__ids__"
# Tables the pipeline works without: a missing one (HTTP 404) is skipped, not an error.
OPTIONAL = {"airtable_plan", "airtable_targets"}

log = logging.getLogger(__name__)


def _records(client: httpx.Client, base_id: str, table: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset: str | None = None
    while True:
        response = client.get(f"/{base_id}/{table}", params={"offset": offset} if offset else None)
        if response.is_error:
            raise SourceHTTPError(response.status_code, f"table {table!r}")
        body = response.json()
        records.extend(body["records"])
        offset = body.get("offset")
        if not offset:
            return records


def _rows(table: str, records: list[dict[str, Any]]) -> list[Row]:
    rows: list[Row] = [(table, r["id"], r) for r in records]
    rows.append((table, IDS_KEY, {"ids": sorted(r["id"] for r in records)}))
    return rows


def fetch() -> dict[str, list[Row]]:
    base_id = config.require("AIRTABLE_BASE_ID")
    sources = {
        "airtable_instruments": config.env("AIRTABLE_INSTRUMENTS_TABLE", "instruments"),
        "airtable_transactions": config.env("AIRTABLE_TRANSACTIONS_TABLE", "transactions"),
        "airtable_plan": config.env("AIRTABLE_PLAN_TABLE", "plan"),
        "airtable_targets": config.env("AIRTABLE_TARGETS_TABLE", "targets"),
    }
    headers = {"Authorization": f"Bearer {config.require('AIRTABLE_TOKEN')}"}
    tables: dict[str, list[Row]] = {}
    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=30) as client:
        for raw_table, table in sources.items():
            try:
                records = _records(client, base_id, table)
            except SourceHTTPError as exc:
                if raw_table in OPTIONAL and exc.status == 404:
                    log.info("%s: table %r not found, skipped", raw_table, table)
                    continue
                raise
            tables[raw_table] = _rows(table, records)
    return tables
