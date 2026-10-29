import pytest

from invest_intel.ingestion import airtable
from invest_intel.ingestion.errors import SourceHTTPError


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("AIRTABLE_BASE_ID", "appTEST")
    monkeypatch.setenv("AIRTABLE_TOKEN", "token")
    monkeypatch.setenv("AIRTABLE_PLAN_TABLE", "Plan")


def _fake_records(missing: set[str]):
    def records(client, base_id, table):
        if table in missing:
            raise SourceHTTPError(404, f"table {table!r}")
        return [{"id": f"rec{table}{n}", "fields": {}} for n in (2, 1)]

    return records


def test_each_table_lists_its_current_record_ids(env, monkeypatch):
    monkeypatch.setattr(airtable, "_records", _fake_records(set()))
    tables = airtable.fetch()
    rows = tables["airtable_transactions"]
    assert rows[-1] == (
        "transactions",
        airtable.IDS_KEY,
        {"ids": ["rectransactions1", "rectransactions2"]},
    )
    assert [key for _, key, _ in rows[:-1]] == ["rectransactions2", "rectransactions1"]


def test_missing_optional_tables_are_skipped(env, monkeypatch):
    monkeypatch.setattr(airtable, "_records", _fake_records({"Plan", "targets"}))
    tables = airtable.fetch()
    assert set(tables) == {"airtable_instruments", "airtable_transactions"}


def test_missing_required_table_still_fails(env, monkeypatch):
    monkeypatch.setattr(airtable, "_records", _fake_records({"transactions"}))
    with pytest.raises(SourceHTTPError):
        airtable.fetch()
