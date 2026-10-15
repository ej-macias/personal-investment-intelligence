"""Indexa Capital: accounts, portfolio snapshot (positions) and transactions.

TODO(verify): endpoint paths and payload field names follow the public API docs
(https://indexacapital.com/en/api-rest-v1) but have not been run against a live account.
Check one real payload per endpoint, then adjust dbt/models/staging/stg_indexa__*.sql.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

import httpx

from invest_intel import config
from invest_intel.ingestion.bronze import Row, payload_hash

BASE_URL = "https://api.indexacapital.com"


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers={"X-AUTH-TOKEN": config.require("INDEXA_API_TOKEN")},
        timeout=30,
    )


def _get(client: httpx.Client, path: str) -> Any:
    response = client.get(path)
    response.raise_for_status()
    return response.json()


def _transaction_rows(account: str, transactions: list[dict[str, Any]]) -> Iterator[Row]:
    for tx in transactions:
        yield account, str(tx.get("reference") or payload_hash(tx)), tx


def fetch(today: date | None = None) -> dict[str, list[Row]]:
    """Return rows per raw table for every account the token can see."""
    snapshot_date = (today or date.today()).isoformat()
    tables: dict[str, list[Row]] = {
        "indexa_portfolio": [],
        "indexa_instrument_transactions": [],
        "indexa_cash_transactions": [],
    }
    with _client() as client:
        accounts = [a["account_number"] for a in _get(client, "/users/me")["accounts"]]
        for account in accounts:
            portfolio = _get(client, f"/accounts/{account}/portfolio")
            tables["indexa_portfolio"].append((account, snapshot_date, portfolio))
            tables["indexa_instrument_transactions"].extend(
                _transaction_rows(
                    account, _get(client, f"/accounts/{account}/instrument-transactions")
                )
            )
            tables["indexa_cash_transactions"].extend(
                _transaction_rows(account, _get(client, f"/accounts/{account}/cash-transactions"))
            )
    return tables
