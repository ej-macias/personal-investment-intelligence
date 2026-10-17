from collections import defaultdict
from datetime import date, timedelta

import pytest

from invest_intel.ingestion import bronze
from invest_intel.synthetic.generate import INSTRUMENTS, SYMBOLS, generate

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


def _quotes(start: date, closes: list[float], skip: set[int] = frozenset()) -> list[dict]:
    """EODHD-shaped payloads on consecutive weekdays, leaving out the indexes in `skip`."""
    quotes, day = [], start
    for n, close in enumerate(closes):
        while day.weekday() >= 5:
            day += timedelta(days=1)
        if n not in skip:
            quotes.append({"date": day.isoformat(), "close": close, "adjusted_close": close})
        day += timedelta(days=1)
    return quotes


def _real_prices() -> dict[str, list[dict]]:
    # Weekdays 5 Jan to 6 Feb 2026; the first symbol misses 2 Feb, as on an exchange holiday.
    closes = [10.0 + n for n in range(25)]
    prices = {symbol: _quotes(date(2026, 1, 5), closes) for symbol in SYMBOLS}
    prices[SYMBOLS[0]] = _quotes(date(2026, 1, 5), closes, skip={20})
    return prices


def test_real_prices_pass_through_and_price_the_trades():
    prices = _real_prices()
    tables = generate(date(2026, 2, 6), prices=prices)
    assert {(s, k) for s, k, _ in tables["eodhd_prices"]} == {
        (s, p["date"]) for s, quotes in prices.items() for p in quotes
    }
    closes = {(s, p["date"]): p["close"] for s, quotes in prices.items() for p in quotes}
    symbol = {i[0]: i[2] for i in INSTRUMENTS}
    for _, _, tx in tables["indexa_instrument_transactions"]:
        key = (symbol[tx["instrument"]["identifier"]], tx["date"])
        if key in closes:
            assert tx["price"] == closes[key]


def test_real_prices_reuse_the_previous_close_on_a_holiday():
    tables = generate(date(2026, 2, 6), prices=_real_prices())
    first = INSTRUMENTS[0][0]
    (feb,) = [
        tx
        for _, _, tx in tables["indexa_instrument_transactions"]
        if tx["instrument"]["identifier"] == first and tx["date"] == "2026-02-02"
    ]
    assert feb["price"] == 29.0  # Friday 30 January's close


def test_real_prices_require_every_symbol():
    prices = _real_prices()
    del prices[SYMBOLS[-1]]
    with pytest.raises(ValueError, match=SYMBOLS[-1]):
        generate(date(2026, 2, 6), prices=prices)
