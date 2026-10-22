from datetime import date, timedelta

import pandas as pd
import streamlit as st

import data

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
        x_label="",
        y_label="Return",
    )
    st.caption(f"Benchmark: {last['benchmark_name']}")

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
st.bar_chart(
    allocation, x="label", y="weight", horizontal=True, x_label="Share of portfolio", y_label=""
)

st.subheader("Gain by instrument")
st.bar_chart(
    data.returns(), x="instrument_name", y="total_gain", horizontal=True, x_label="EUR", y_label=""
)
