import pandas as pd
import pytest

from allocation_chart import MAX_SLICES, OTHER_COLOR, allocation_pie, slices


def _allocation(count: int) -> pd.DataFrame:
    values = [float(count - index) * 100 for index in range(count)]
    total = sum(values)
    return pd.DataFrame(
        {
            "label": [f"Group {index}" for index in range(count)],
            "market_value": values,
            "weight": [value / total for value in values],
        }
    )


def _color_range(chart) -> list[str]:
    return chart.to_dict()["layer"][0]["encoding"]["color"]["scale"]["range"]


def test_keeps_every_group_up_to_the_limit():
    rows = slices(_allocation(MAX_SLICES))
    assert rows["label"].tolist() == [f"Group {index}" for index in range(MAX_SLICES)]


def test_folds_the_smallest_groups_and_preserves_totals():
    allocation = _allocation(12)
    rows = slices(allocation)
    assert len(rows) == MAX_SLICES
    assert rows["label"].iloc[-1] == "Other (5)"
    assert rows["market_value"].iloc[-1] == allocation["market_value"].iloc[7:].sum()
    assert rows["market_value"].sum() == pytest.approx(allocation["market_value"].sum())
    assert rows["weight"].sum() == pytest.approx(1)


def test_drops_groups_without_money():
    allocation = _allocation(3)
    allocation.loc[2, "market_value"] = 0
    assert len(slices(allocation)) == 2


def test_only_a_folded_slice_is_gray():
    assert OTHER_COLOR not in _color_range(allocation_pie(_allocation(MAX_SLICES)))
    assert _color_range(allocation_pie(_allocation(12)))[-1] == OTHER_COLOR
