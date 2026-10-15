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
right.metric("Time-weighted return", f"{summary['cumulative_twr']:.1%}")
st.caption(f"As of {summary['date_day']}")

st.subheader("Value vs. money invested")
performance = data.performance()
st.line_chart(
    performance, x="date_day", y=["market_value", "net_invested"], x_label="", y_label="EUR"
)

st.subheader("Asset allocation")
allocation = data.allocation("asset_class")
st.bar_chart(allocation, x="label", y="market_value", horizontal=True, x_label="EUR", y_label="")
