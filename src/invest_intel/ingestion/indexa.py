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
from invest_intel.ingestion.errors import SourceHTTPError

BASE_URL = "https://api.indexacapital.com"


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers={"X-AUTH-TOKEN": config.require("INDEXA_API_TOKEN")},
        timeout=30,
    )


def _get(client: httpx.Client, template: str, **params: str) -> Any:
    """GET template.format(**params); errors name the template, never the account number."""
    response = client.get(template.format(**params))
    if response.is_error:
        raise SourceHTTPError(response.status_code, template)
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
            portfolio = _get(client, "/accounts/{account}/portfolio", account=account)
            tables["indexa_portfolio"].append((account, snapshot_date, portfolio))
            tables["indexa_instrument_transactions"].extend(
                _transaction_rows(
                    account,
                    _get(client, "/accounts/{account}/instrument-transactions", account=account),
                )
            )
            tables["indexa_cash_transactions"].extend(
                _transaction_rows(
                    account, _get(client, "/accounts/{account}/cash-transactions", account=account)
                )
            )
    return tables
