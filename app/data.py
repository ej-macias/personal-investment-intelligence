"""Cached DataFrame loaders for the pages. All data comes from invest_intel.analytics.queries."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from invest_intel.analytics import queries

TTL = 600


@st.cache_data(ttl=TTL)
def summary() -> dict:
    return queries.portfolio_summary()


@st.cache_data(ttl=TTL)
def performance(start_date: date | None = None) -> pd.DataFrame:
    return pd.DataFrame(queries.portfolio_performance(start_date=start_date))


@st.cache_data(ttl=TTL)
def allocation(dimension: str) -> pd.DataFrame:
    return pd.DataFrame(queries.asset_allocation(dimension))


@st.cache_data(ttl=TTL)
def returns() -> pd.DataFrame:
    return pd.DataFrame(queries.investment_returns())


@st.cache_data(ttl=TTL)
def benchmark(start_date: date | None = None) -> pd.DataFrame:
    return pd.DataFrame(queries.compare_with_benchmark(start_date=start_date))


@st.cache_data(ttl=TTL)
def transactions(isin: str) -> pd.DataFrame:
    return pd.DataFrame(queries.transactions(isin=isin, limit=200))


@st.cache_data(ttl=TTL)
def position_history(isin: str) -> pd.DataFrame:
    return pd.DataFrame(queries.position_history(isin))


@st.cache_data(ttl=TTL)
def annual_return() -> dict:
    return queries.annual_return()


@st.cache_data(ttl=TTL)
def monthly() -> pd.DataFrame:
    return pd.DataFrame(queries.monthly_summary())


@st.cache_data(ttl=TTL)
def highlights() -> dict:
    return queries.highlights()
