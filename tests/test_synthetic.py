from collections import defaultdict
from datetime import date

from invest_intel.ingestion import bronze
from invest_intel.synthetic.generate import INSTRUMENTS, generate

TODAY = date(2026, 1, 15)


def test_generates_every_raw_table_deterministically():
    first = generate(TODAY)
    assert first == generate(TODAY)
    assert set(first) == set(bronze.RAW_TABLES)
    for table in set(bronze.RAW_TABLES) - {"indexa_cash_transactions"}:
        assert first[table], table


def test_target_weights_sum_to_one():
    assert abs(sum(i[6] for i in INSTRUMENTS) - 1) < 1e-9


def test_never_sells_more_than_held():
    tables = generate(TODAY)
    held = defaultdict(float)
    for _, _, payload in tables["airtable_transactions"]:
        fields = payload["fields"]
        held[fields["isin"]] += (
            fields["quantity"] if fields["type"] == "buy" else -fields["quantity"]
        )
        assert held[fields["isin"]] >= 0


def test_snapshot_matches_indexa_transactions():
    tables = generate(TODAY)
    bought = defaultdict(float)
    for _, _, tx in tables["indexa_instrument_transactions"]:
        bought[tx["instrument"]["identifier"]] += tx["titles"]
    ((_, _, snapshot),) = tables["indexa_portfolio"]
    for position in snapshot["instrument_accounts"][0]["positions"]:
        assert abs(position["titles"] - bought[position["instrument"]["identifier"]]) < 1e-3
