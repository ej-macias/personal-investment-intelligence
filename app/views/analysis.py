from datetime import date, timedelta

import pandas as pd
import streamlit as st

import allocation_chart
import chart_colors
import data
import risk_charts

st.title("Portfolio analysis")

PERIODS = {"1M": 30, "6M": 182, "1Y": 365, "3Y": 1095, "All": None}
period = st.segmented_control("Period", list(PERIODS), default="1Y") or "1Y"
start = date.today() - timedelta(days=PERIODS[period]) if PERIODS[period] else None

st.subheader("Return vs. benchmark")
benchmark = data.benchmark(start)
if benchmark.empty:
    st.info("No benchmark yet. Tick is_benchmark on an instrument in Airtable.")
else:
    last = benchmark.iloc[-1]
    left, middle, right = st.columns(3)
    left.metric("Portfolio", f"{last['portfolio_return']:.1%}")
    middle.metric("Benchmark", f"{last['benchmark_return']:.1%}")
    right.metric("Difference", f"{last['excess_return']:+.1%}")
    st.line_chart(
        benchmark,
        x="date_day",
        y=["portfolio_return", "benchmark_return"],
        color=chart_colors.two_lines(),
        x_label="",
        y_label="Return",
    )
    st.caption(f"Benchmark: {last['benchmark_name']}")

DIMENSION_NAMES = {
    "asset_class": "Asset class",
    "region": "Region",
    "instrument_type": "Type",
    "liquidity": "Liquidity",
    "platform": "Platform",
    "instrument": "Holding",
}


def _range(row) -> str:
    low, high = row["min_weight"], row["max_weight"]
    if pd.notna(low) and pd.notna(high):
        return f"{low:.0%}–{high:.0%}"
    if pd.notna(high):
        return f"max {high:.0%}"
    if pd.notna(low):
        return f"min {low:.0%}"
    return "–"


# Only clearly out-of-range limits get a fix and a red row; "Slightly …" needs no action.
OUT_OF_RANGE = {"Above maximum", "Below minimum"}


def _fix(row) -> str:
    amount = row["amount_to_range"]
    if row["status"] not in OUT_OF_RANGE or pd.isna(amount) or amount == 0:
        return ""
    return f"add €{amount:,.0f}" if amount > 0 else f"reduce by €{-amount:,.0f}"


def _highlight(row) -> list[str]:
    red = "background-color: rgba(255, 75, 75, 0.18)"
    return [red if row["Status"] in OUT_OF_RANGE else ""] * len(row)


checks = data.target_checks()
plan = data.plan()
if plan or not checks.empty:
    st.subheader("Your plan vs today")
    if plan.get("goal"):
        horizon = f" · by {plan['horizon_year']}" if plan.get("horizon_year") else ""
        st.caption(f"{plan['goal']}{horizon}")
    if checks.empty:
        st.info("No limits yet. Add rows to the targets table in Airtable.")
    else:
        off = checks[checks["status"].isin(OUT_OF_RANGE)]
        st.metric("Limits out of range", f"{len(off)} of {len(checks)}")
        table = pd.DataFrame(
            {
                "Limit": checks["dimension"].map(DIMENSION_NAMES) + ": " + checks["label"],
                "Today": checks["current_weight"] * 100,
                "Range": checks.apply(_range, axis=1),
                "Target": checks["target_weight"] * 100,
                "Status": checks["status"],
                "To fix": checks.apply(_fix, axis=1),
            }
        )
        st.dataframe(
            table.style.apply(_highlight, axis=1),
            hide_index=True,
            column_config={
                "Limit": st.column_config.TextColumn(width="medium"),
                "Today": st.column_config.NumberColumn(format="%.0f%%"),
                "Target": st.column_config.NumberColumn(format="%.0f%%"),
                "Status": st.column_config.TextColumn(width="medium"),
                "To fix": st.column_config.TextColumn(width="medium"),
            },
        )

st.subheader("Risk")
risk = data.risk()
if risk.get("avg_risk") is None:
    st.info("No risk ratings yet. Fill the risk field (1 to 7) of your assets in Airtable.")
else:
    left, right = st.columns(2)
    left.metric("Average risk", f"{risk['avg_risk']:.2f} / 7")
    if risk.get("status"):
        right.metric("Status", risk["status"])
    st.altair_chart(risk_charts.gauge(risk))
    if risk.get("risk_min") is not None and risk.get("risk_max") is not None:
        st.caption(
            f"Shaded: your range, {risk['risk_min']:g} to {risk['risk_max']:g}. "
            f"Gray mark: your goal, {risk['risk_target']:g}. Each holding counts by its money."
        )
    else:
        st.caption("Each holding counts by its money. Add risk_min and risk_max to your plan.")
    if risk["rated_share"] < 1:
        st.warning(f"{1 - risk['rated_share']:.0%} of the value has no rating and is left out.")

    st.markdown("**Money by risk level**")
    st.altair_chart(risk_charts.by_level(data.allocation("risk_level")))

    history = data.risk_history()
    if len(history) > 1:
        st.markdown("**Average risk over time**")
        st.altair_chart(risk_charts.over_time(history, risk))
        st.caption("Past months use today's risk ratings.")

    st.markdown("**What drives the risk**")
    holdings = data.risk_by_holding()
    st.dataframe(
        pd.DataFrame(
            {
                "Holding": holdings["instrument_name"],
                "Risk": holdings["risk_level"],
                "Share": holdings["weight"] * 100,
                "Adds": holdings["risk_points"],
            }
        ),
        hide_index=True,
        column_config={
            "Holding": st.column_config.TextColumn(width=170),
            "Risk": st.column_config.NumberColumn(format="%d", width=48),
            "Share": st.column_config.NumberColumn(format="%.0f%%", width=62),
            "Adds": st.column_config.NumberColumn(format="%.2f", width=58),
        },
    )
    st.caption("Adds: the points each holding adds to the average risk. They sum to the average.")

st.subheader("Month by month")
monthly = data.monthly()
if monthly.empty:
    st.info("No monthly data yet.")
else:
    st.bar_chart(monthly, x="month", y="gain", x_label="", y_label="Gain (EUR)")
    st.caption("What the investments gained or lost each month, leaving out money added.")
    facts = data.highlights()
    if facts.get("months_counted"):
        rows = [
            ("Best month", f"{facts['best_month']:%b %Y}", f"{facts['best_month_return']:+.1%}"),
            (
                "Worst month",
                f"{facts['worst_month']:%b %Y}",
                f"{facts['worst_month_return']:+.1%}",
            ),
            (
                "Months with a gain",
                f"{facts['months_with_gain']} of {facts['months_counted']}",
                f"{facts['share_of_months_with_gain']:.0%}",
            ),
            (
                "Biggest drop from a high",
                f"{facts['biggest_drop_from']:%d %b %Y} to {facts['biggest_drop_to']:%d %b %Y}",
                f"{facts['biggest_drop_pct']:.1%}",
            ),
            ("Below its high today", "", f"{facts['below_high_pct']:.1%}"),
        ]
        st.dataframe(pd.DataFrame(rows, columns=["", "When", "Return"]), hide_index=True)
        st.caption(
            f"Based on {facts['months_counted']} complete months; "
            "a short history can make these figures swing."
        )

st.subheader("Allocation")
dimension = (
    st.segmented_control(
        "Group by",
        ["asset_class", "region", "instrument_type", "liquidity", "platform", "instrument"],
        default="region",
    )
    or "region"
)
allocation = data.allocation(dimension)
if allocation.empty:
    st.info("No allocation data yet.")
else:
    st.altair_chart(allocation_chart.allocation_pie(allocation, chart_colors.theme()))

st.subheader("Gain by instrument")
st.bar_chart(
    data.returns(), x="instrument_name", y="total_gain", horizontal=True, x_label="EUR", y_label=""
)
