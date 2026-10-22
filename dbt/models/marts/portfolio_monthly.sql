-- The portfolio month by month: value at the month end, money added during the month, the
-- gain the investments made (leaving out money added) and the month's return.
with days as (
    select
        *,
        date_trunc('month', date_day)::date as month
    from {{ ref('portfolio_performance') }}
),

months as (
    select
        month,
        max(date_day) as last_day,
        sum(net_flow) as money_added,
        -- The month's daily returns chained together, as for the time-weighted return.
        exp(sum(ln(greatest(1 + daily_return, 1e-9)))) - 1 as month_return
    from days
    group by month
),

month_ends as (
    select distinct on (month)
        month,
        market_value as month_end_value
    from days
    order by month, date_day desc
)

select
    m.month,
    m.last_day,
    e.month_end_value,
    m.money_added,
    e.month_end_value
    - coalesce(lag(e.month_end_value) over (order by m.month), 0)
    - m.money_added as gain,
    round(m.month_return, 10) as return_pct,
    m.month < date_trunc('month', {{ as_of_date() }})::date as is_complete
from months as m
inner join month_ends as e on m.month = e.month
