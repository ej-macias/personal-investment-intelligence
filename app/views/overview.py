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
TWR_HELP = (
    "How the investments themselves did, leaving out when and how much money you added. "
    "Each day's change in value, without that day's contributions, chained together."
)
if summary.get("twr_per_year") is not None:
    right.metric(
        "Time-weighted return, per year",
        f"{summary['twr_per_year']:.1%}",
        help=f"{TWR_HELP} Shown per year; since the start it is {summary['cumulative_twr']:.1%}.",
    )
else:
    right.metric("Time-weighted return, so far", f"{summary['cumulative_twr']:.1%}", help=TWR_HELP)
personal = data.annual_return()
if personal.get("annual_return") is not None:
    left.metric(
        "Your annual return",
        f"{personal['annual_return']:.1%}",
        help="The yearly rate your own money has earned, taking into account when you added "
        "it. The time-weighted return leaves that timing out, to show how the investments did.",
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
