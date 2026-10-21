"""Read-only queries over the gold schema.

This is the single access path to the data for both the Streamlit pages and the AI
assistant's tools: every question the app can answer is a function here, with fixed SQL
and bound parameters.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from invest_intel import db

Rows = list[dict[str, Any]]

ALLOCATION_DIMENSIONS = {
    "asset_class": "asset_class",
    "region": "region",
    "instrument_type": "instrument_type",
    "liquidity": "liquidity",
    "instrument": "instrument_name",
}
FREQUENCIES = ("daily", "monthly")


def portfolio_summary() -> dict[str, Any]:
    rows = db.query(
        """
        select date_day, market_value::float8, net_invested::float8, total_gain::float8,
               cumulative_twr::float8
        from gold.portfolio_performance
        order by date_day desc
        limit 1
        """
    )
    return rows[0] if rows else {}


def portfolio_performance(
    start_date: date | None = None, end_date: date | None = None, frequency: str = "daily"
) -> Rows:
    """Value, net invested, gain and time-weighted return per day or per month end."""
    if frequency not in FREQUENCIES:
        raise ValueError(f"frequency must be one of {FREQUENCIES}")
    return db.query(
        """
        select distinct on (period) date_day, market_value::float8, net_invested::float8,
               total_gain::float8, daily_return::float8, cumulative_twr::float8
        from (
            select *,
                   case when %(frequency)s = 'monthly'
                        then date_trunc('month', date_day)::date else date_day end as period
            from gold.portfolio_performance
            where (%(start)s::date is null or date_day >= %(start)s::date)
              and (%(end)s::date is null or date_day <= %(end)s::date)
        ) p
        order by period, date_day desc
        """,
        {"start": start_date, "end": end_date, "frequency": frequency},
    )


def asset_allocation(dimension: str = "asset_class") -> Rows:
    """Current market value and weight grouped by one of ALLOCATION_DIMENSIONS."""
    if dimension not in ALLOCATION_DIMENSIONS:
        raise ValueError(f"dimension must be one of {sorted(ALLOCATION_DIMENSIONS)}")
    column = ALLOCATION_DIMENSIONS[dimension]
    return db.query(
        f"""
        select {column} as label, sum(market_value)::float8 as market_value,
               sum(weight)::float8 as weight
        from gold.asset_allocation
        group by 1
        order by 2 desc
        """  # noqa: S608 - column comes from the whitelist above
    )


def investment_returns() -> Rows:
    """Per-instrument quantity, cost, value and gain as of the latest day."""
    return db.query(
        """
        select isin, instrument_name, asset_class, instrument_type, account_id, quantity::float8,
               net_invested::float8, market_value::float8, total_gain::float8,
               return_pct::float8
        from gold.investment_returns
        order by market_value desc
        """
    )


def compare_with_benchmark(start_date: date | None = None, frequency: str = "daily") -> Rows:
    """Portfolio vs benchmark cumulative return, both rebased to zero at the start date."""
    if frequency not in FREQUENCIES:
        raise ValueError(f"frequency must be one of {FREQUENCIES}")
    return db.query(
        """
        with rebased as (
            select date_day, benchmark_name,
                   (1 + portfolio_return) / (1 + first_value(portfolio_return) over w) - 1
                       as portfolio_return,
                   (1 + benchmark_return) / (1 + first_value(benchmark_return) over w) - 1
                       as benchmark_return
            from gold.benchmark_comparison
            where %(start)s::date is null or date_day >= %(start)s::date
            window w as (partition by benchmark_isin order by date_day)
        )
        select distinct on (benchmark_name, period) date_day, benchmark_name,
               portfolio_return::float8, benchmark_return::float8,
               (portfolio_return - benchmark_return)::float8 as excess_return
        from (
            select *,
                   case when %(frequency)s = 'monthly'
                        then date_trunc('month', date_day)::date else date_day end as period
            from rebased
        ) r
        order by benchmark_name, period, date_day desc
        """,
        {"start": start_date, "frequency": frequency},
    )


def transactions(isin: str | None = None, limit: int = 50) -> Rows:
    return db.query(
        """
        select t.trade_date, t.source, t.account_id, t.isin, i.instrument_name,
               t.transaction_type, t.quantity::float8, t.price::float8, t.amount::float8
        from gold.fct_transactions t
        left join gold.dim_instrument i using (isin)
        where %(isin)s::text is null or t.isin = %(isin)s::text
        order by t.trade_date desc
        limit %(limit)s
        """,
        {"isin": isin, "limit": max(1, min(int(limit), 500))},
    )


def position_history(isin: str) -> Rows:
    return db.query(
        """
        select date_day, sum(quantity)::float8 as quantity,
               sum(market_value)::float8 as market_value,
               sum(net_invested)::float8 as net_invested,
               max(close_price)::float8 as close_price
        from gold.fct_positions_daily
        where isin = %(isin)s
        group by 1
        order by 1
        """,
        {"isin": isin},
    )
