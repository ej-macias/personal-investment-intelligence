import streamlit as st

import data

st.title("Portfolio overview")

summary = data.summary()
if not summary:
    st.info("No data yet. Run the ingestion and `dbt build` first.")
    st.stop()

left, right = st.columns(2)
left.metric("Market value", f"€{summary['market_value']:,.0f}")
right.metric("Total gain", f"€{summary['total_gain']:,.0f}")
left.metric("Net invested", f"€{summary['net_invested']:,.0f}")
MWR_HELP = (
    "How much your own money has grown per year. It takes into account when and how much you "
    "put in: money added just before prices rise helps, money added just before a fall hurts. "
    "It's the 'personal return' banks and brokers show."
)
TWR_HELP = (
    "How well your investments themselves have done per year, ignoring when and how much money "
    "you added, as if you had invested once at the start. It's the fair way to compare with "
    "the benchmark or with a fund."
)
NOT_YET = "Available after 3 months of history."

mwr = data.annual_return().get("annual_return")
twr = summary.get("twr_per_year")
mwr_column, twr_column = st.columns(2)
mwr_column.metric(
    "Money-weighted return (MWR), per year",
    f"{mwr:.1%}" if mwr is not None else "–",
    help=MWR_HELP if mwr is not None else f"{MWR_HELP} {NOT_YET}",
)
twr_column.metric(
    "Time-weighted return (TWR), per year",
    f"{twr:.1%}" if twr is not None else "–",
    help=f"{TWR_HELP} Since the start: {summary['cumulative_twr']:.1%}."
    if twr is not None
    else f"{TWR_HELP} {NOT_YET}",
)
st.caption(f"As of {summary['date_day']}")
if summary.get("twr_per_year") is not None and summary["history_days"] < 365:
    st.caption(
        f"The yearly figures are based on {summary['history_days']} days of history; "
        "a short history can make them swing."
    )

st.subheader("Value vs. money invested")
performance = data.performance()
st.line_chart(
    performance, x="date_day", y=["market_value", "net_invested"], x_label="", y_label="EUR"
)

st.subheader("Asset allocation")
allocation = data.allocation("asset_class")
st.bar_chart(allocation, x="label", y="market_value", horizontal=True, x_label="EUR", y_label="")
