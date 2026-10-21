import streamlit as st

import data

st.title("Investment explorer")

returns = data.returns()
if returns.empty:
    st.info("No holdings yet.")
    st.stop()

st.dataframe(
    returns[
        [
            "instrument_name",
            "asset_class",
            "instrument_type",
            "market_value",
            "total_gain",
            "return_pct",
        ]
    ],
    hide_index=True,
    column_config={
        "instrument_name": "Instrument",
        "asset_class": "Asset class",
        "instrument_type": "Type",
        "market_value": st.column_config.NumberColumn("Value", format="€%.0f"),
        "total_gain": st.column_config.NumberColumn("Gain", format="€%.0f"),
        "return_pct": st.column_config.NumberColumn("Return", format="percent"),
    },
)

names = returns.drop_duplicates("isin").set_index("isin")["instrument_name"].fillna("").to_dict()
isin = st.selectbox("Instrument", list(names), format_func=lambda i: names[i] or i)

history = data.position_history(isin)

st.subheader("Value vs. money invested")
st.line_chart(history, x="date_day", y=["market_value", "net_invested"], x_label="", y_label="EUR")

st.subheader("Price")
st.line_chart(history, x="date_day", y="close_price", x_label="", y_label="EUR")

st.subheader("Transactions")
st.dataframe(
    data.transactions(isin)[
        ["trade_date", "transaction_type", "quantity", "price", "amount", "account_id"]
    ],
    hide_index=True,
)
