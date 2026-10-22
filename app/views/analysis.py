from datetime import date, timedelta

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
