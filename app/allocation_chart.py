"""The allocation pie on the analysis page."""

from __future__ import annotations

import altair as alt
import pandas as pd

MAX_SLICES = 8
MIN_LABELLED_SHARE = 0.05
OTHER_COLOR = "#898781"
DARK_INK = "#0b0b0b"
LIGHT_INK = "#ffffff"
LIGHT_YELLOW = "#eda100"

PALETTES = {
    "light": [
        "#2a78d6",
        "#eb6834",
        "#1baf7a",
        "#eda100",
        "#e87ba4",
        "#008300",
        "#6250d6",
        "#e34948",
    ],
    "dark": [
        "#3987e5",
        "#d95926",
        "#199e70",
        "#c98500",
        "#d55181",
        "#0ca30c",
        "#9085e9",
        "#e66767",
    ],
}
BACKGROUNDS = {"light": "#ffffff", "dark": "#0e1117"}


def slices(allocation: pd.DataFrame) -> pd.DataFrame:
    """Groups with money, largest first; past MAX_SLICES the smallest fold into 'Other (n)'."""
    rows = (
        allocation.loc[allocation["market_value"] > 0, ["label", "market_value", "weight"]]
        .assign(label=lambda frame: frame["label"].fillna("Not set").astype(str))
        .sort_values("market_value", ascending=False)
        .reset_index(drop=True)
    )
    if len(rows) > MAX_SLICES:
        rest = rows.iloc[MAX_SLICES - 1 :]
        other = pd.DataFrame(
            [
                {
                    "label": f"Other ({len(rest)})",
                    "market_value": rest["market_value"].sum(),
                    "weight": rest["weight"].sum(),
                }
            ]
        )
        rows = pd.concat([rows.iloc[: MAX_SLICES - 1], other], ignore_index=True)
    return rows


def allocation_pie(allocation: pd.DataFrame, theme: str = "light") -> alt.LayerChart:
    """A pie with the share printed on each large slice, and amount and share on hover."""
    mode = theme if theme in PALETTES else "light"
    rows = slices(allocation)
    colors = PALETTES[mode][: len(rows)]
    if (allocation["market_value"] > 0).sum() > MAX_SLICES:
        colors[-1] = OTHER_COLOR
    rows = rows.assign(
        order=range(len(rows)),
        amount=rows["market_value"].map(lambda value: f"€{value:,.0f}"),
        share_label=rows["weight"].map(
            lambda share: f"{share:.0%}" if share >= MIN_LABELLED_SHARE else ""
        ),
        ink=[DARK_INK if color == LIGHT_YELLOW else LIGHT_INK for color in colors],
    )
    base = alt.Chart(rows).encode(
        theta=alt.Theta("market_value:Q", stack=True),
        order=alt.Order("order:Q"),
        tooltip=[
            alt.Tooltip("label:N", title="Group"),
            alt.Tooltip("amount:N", title="Amount"),
            alt.Tooltip("weight:Q", title="Share", format=".1%"),
        ],
    )
    pie = base.mark_arc(outerRadius=130, stroke=BACKGROUNDS[mode], strokeWidth=2).encode(
        color=alt.Color(
            "label:N",
            sort=None,
            scale=alt.Scale(domain=rows["label"].tolist(), range=colors),
            legend=alt.Legend(title=None, orient="right", labelLimit=220),
        )
    )
    labels = base.mark_text(radius=88, fontSize=13, fontWeight="bold").encode(
        text="share_label:N", color=alt.Color("ink:N", scale=None, legend=None)
    )
    return alt.layer(pie, labels).resolve_scale(color="independent").properties(height=320)
