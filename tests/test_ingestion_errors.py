import httpx
import pytest

from invest_intel import config
from invest_intel.ingestion import airtable, indexa
from invest_intel.ingestion.errors import SourceHTTPError
from invest_intel.ingestion.run import _describe

TOKEN = "secret-token-123"
ACCOUNT = "ES0000000001"


def _client(status: int, base_url: str) -> httpx.Client:
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json={}))
    return httpx.Client(
        base_url=base_url, headers={"Authorization": f"Bearer {TOKEN}"}, transport=transport
    )


def test_airtable_error_names_the_table_only():
    with _client(404, airtable.BASE_URL) as client, pytest.raises(SourceHTTPError) as caught:
        airtable._records(client, "appXXXXXXXXXXXXXX", "instruments")
    message = _describe(caught.value)
    assert message == "HTTP 404 (table 'instruments')"
    assert TOKEN not in message


def test_indexa_error_names_the_endpoint_template_not_the_account():
    with _client(401, indexa.BASE_URL) as client, pytest.raises(SourceHTTPError) as caught:
        indexa._get(client, "/accounts/{account}/portfolio", account=ACCOUNT)
    message = _describe(caught.value)
    assert message == "HTTP 401 (/accounts/{account}/portfolio)"
    assert ACCOUNT not in message and TOKEN not in message


def test_require_strips_pasted_whitespace(monkeypatch):
    monkeypatch.setenv("SOME_TOKEN", f"{TOKEN}\n")
    assert config.require("SOME_TOKEN") == TOKEN
