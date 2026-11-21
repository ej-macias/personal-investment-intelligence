"""The risk charts on the analysis page, all on the same 1 to 7 scale."""

from __future__ import annotations

import altair as alt
import pandas as pd

BLUE = "#2a78d6"
GRAY = "#8a8984"
SCALE = alt.Scale(domain=[1, 7], nice=False)
AXIS = alt.Axis(values=list(range(1, 8)), format="d", grid=False, title=None)


def _has_range(risk: dict) -> bool:
    return risk.get("risk_min") is not None and risk.get("risk_max") is not None


def _band(risk: dict, horizontal: bool) -> alt.Chart:
    band = pd.DataFrame([{"low": risk["risk_min"], "high": risk["risk_max"]}])
    start, end = ("x", "x2") if horizontal else ("y", "y2")
    encoding = {
        start: alt.X("low:Q", scale=SCALE) if horizontal else alt.Y("low:Q", scale=SCALE),
        end: "high:Q",
        "tooltip": [alt.Tooltip("low:Q", title="Lowest"), alt.Tooltip("high:Q", title="Highest")],
    }
    return alt.Chart(band).mark_rect(color=GRAY, opacity=0.22).encode(**encoding)


def gauge(risk: dict) -> alt.LayerChart:
    """Today's average on the scale, with the accepted range shaded and the target marked."""
    today = pd.DataFrame([{"average": risk["avg_risk"], "label": f"{risk['avg_risk']:.2f}"}])
    track = (
        alt.Chart(pd.DataFrame([{"low": 1, "high": 7}]))
        .mark_rule(color=GRAY, strokeWidth=2)
        .encode(x=alt.X("low:Q", scale=SCALE, axis=AXIS), x2="high:Q")
    )
    layers: list[alt.Chart] = [track]
    if _has_range(risk):
        layers.insert(0, _band(risk, horizontal=True))
    if risk.get("risk_target") is not None:
        target = pd.DataFrame([{"target": risk["risk_target"]}])
        layers.append(
            alt.Chart(target)
            .mark_tick(color=GRAY, thickness=2, size=28)
            .encode(x=alt.X("target:Q", scale=SCALE), tooltip=alt.Tooltip("target:Q", title="Goal"))
        )
    point = alt.Chart(today).encode(x=alt.X("average:Q", scale=SCALE))
    layers.append(
        point.mark_point(filled=True, size=170, color=BLUE, opacity=1, stroke="white").encode(
            tooltip=alt.Tooltip("average:Q", title="Average risk", format=".2f")
        )
    )
    layers.append(point.mark_text(dy=-20, fontWeight="bold").encode(text="label:N"))
    return alt.layer(*layers).properties(height=90)


def by_level(allocation: pd.DataFrame) -> alt.Chart:
    """Share of the money at each risk level, keeping empty levels so the shape is honest."""
    levels = [str(level) for level in range(1, 8)]
    if "Unrated" in set(allocation["label"]):
        levels.append("Unrated")
    shares = (
        allocation.set_index("label")[["market_value", "weight"]]
        .reindex(levels, fill_value=0)
        .reset_index()
    )
    return (
        alt.Chart(shares)
        .mark_bar(color=BLUE, cornerRadiusEnd=4, size=26)
        .encode(
            x=alt.X("label:N", sort=levels, title="Risk level", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("weight:Q", title="Share of portfolio", axis=alt.Axis(format=".0%")),
            tooltip=[
                alt.Tooltip("label:N", title="Risk level"),
                alt.Tooltip("weight:Q", title="Share", format=".1%"),
                alt.Tooltip("market_value:Q", title="EUR", format=",.0f"),
            ],
        )
        .properties(height=220)
    )


def over_time(history: pd.DataFrame, risk: dict) -> alt.LayerChart:
    """Month-end average risk, with the accepted range behind it."""
    line = (
        alt.Chart(history.assign(date_day=pd.to_datetime(history["date_day"])))
        .mark_line(color=BLUE, strokeWidth=2)
        .encode(
            x=alt.X("date_day:T", title=None, axis=alt.Axis(grid=False)),
            y=alt.Y("avg_risk:Q", scale=SCALE, axis=AXIS),
            tooltip=[
                alt.Tooltip("date_day:T", title="Month end", format="%b %Y"),
                alt.Tooltip("avg_risk:Q", title="Average risk", format=".2f"),
            ],
        )
    )
    layers: list[alt.Chart] = [line]
    if _has_range(risk):
        layers.insert(0, _band(risk, horizontal=False))
    return alt.layer(*layers).properties(height=220)
