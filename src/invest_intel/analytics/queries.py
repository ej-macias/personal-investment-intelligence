"""Read-only queries over the gold schema.

This is the single access path to the data for both the Streamlit pages and the AI
assistant's tools: every question the app can answer is a function here, with fixed SQL
and bound parameters.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from invest_intel import db
from invest_intel.analytics.returns import annual_return as _annual_return
from invest_intel.analytics.returns import per_year

Rows = list[dict[str, Any]]

ALLOCATION_DIMENSIONS = {
    "asset_class": "asset_class",
    "region": "region",
    "instrument_type": "instrument_type",
    "liquidity": "liquidity",
    "platform": "platform",
    "instrument": "instrument_name",
}
FREQUENCIES = ("daily", "monthly")
# Below this much history a yearly rate swings too much to be meaningful.
MIN_DAYS_FOR_ANNUAL_RETURN = 90


def portfolio_summary() -> dict[str, Any]:
    """Latest value, money invested and gain, and the time-weighted return both since the start
    and per year (None while the history is shorter than MIN_DAYS_FOR_ANNUAL_RETURN)."""
    rows = db.query(
        """
        select date_day, market_value::float8, net_invested::float8, total_gain::float8,
               cumulative_twr::float8,
               (select min(date_day) from gold.portfolio_performance) as first_day
        from gold.portfolio_performance
        order by date_day desc
        limit 1
        """
    )
    if not rows:
        return {}
    summary = rows[0]
    days = (summary["date_day"] - summary["first_day"]).days
    summary["history_days"] = days
    summary["twr_per_year"] = (
        per_year(summary["cumulative_twr"], days) if days >= MIN_DAYS_FOR_ANNUAL_RETURN else None
    )
    return summary


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
        select isin, instrument_name, asset_class, instrument_type, platform, account_id,
               quantity::float8, net_invested::float8, market_value::float8, total_gain::float8,
               return_pct::float8, yearly_fee::float8
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


def annual_return() -> dict[str, Any]:
    """Your annual return (money-weighted), from every day money was added or taken out plus
    today's value. `annual_return` is None while the history is shorter than
    MIN_DAYS_FOR_ANNUAL_RETURN."""
    rows = db.query(
        """
        select date_day, net_flow::float8, market_value::float8
        from gold.portfolio_performance
        where net_flow <> 0
           or date_day = (select max(date_day) from gold.portfolio_performance)
        order by date_day
        """
    )
    if not rows:
        return {}
    first, last = rows[0]["date_day"], rows[-1]["date_day"]
    days = (last - first).days
    result: dict[str, Any] = {"since": first, "as_of": last, "days": days, "annual_return": None}
    if days >= MIN_DAYS_FOR_ANNUAL_RETURN:
        # From your side: money put in is negative, money taken out and today's value positive.
        flows = [(r["date_day"], -r["net_flow"]) for r in rows if r["net_flow"]]
        flows.append((last, rows[-1]["market_value"]))
        try:
            result["annual_return"] = _annual_return(flows)
        except ValueError:
            pass
    return result


def monthly_summary() -> Rows:
    """Month by month: value at the month end, money added, gain and return."""
    return db.query(
        """
        select month, month_end_value::float8, money_added::float8, gain::float8,
               return_pct::float8, is_complete
        from gold.portfolio_monthly
        order by month
        """
    )


def highlights() -> dict[str, Any]:
    """Best and worst month, share of months with a gain, biggest drop from a high."""
    rows = db.query(
        """
        select best_month, best_month_return::float8, worst_month, worst_month_return::float8,
               months_counted, months_with_gain, share_of_months_with_gain::float8,
               biggest_drop_pct::float8, biggest_drop_from, biggest_drop_to,
               below_high_pct::float8
        from gold.portfolio_highlights
        """
    )
    return rows[0] if rows else {}


def investment_plan() -> dict[str, Any]:
    """The owner's goal, horizon and rules, and the average money added per month."""
    rows = db.query(
        """
        select goal, horizon_year, rules, avg_money_added_12m::float8
        from gold.investment_plan
        """
    )
    return rows[0] if rows else {}


def target_checks() -> Rows:
    """The owner's limits against today's portfolio: status and euros to fix."""
    return db.query(
        """
        select dimension, label, applies_to_each, current_value::float8,
               current_weight::float8, min_weight::float8, target_weight::float8,
               max_weight::float8, status, amount_to_range::float8, amount_to_target::float8,
               note
        from gold.target_checks
        order by dimension, applies_to_each, label
        """
    )
