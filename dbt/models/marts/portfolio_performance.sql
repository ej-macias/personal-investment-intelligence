-- Whole-portfolio value and return per day.
-- daily_return is time-weighted: money added or withdrawn that day is removed before
-- comparing with the previous day's value, so contributions do not count as performance.
with daily as (
    select
        date_day,
        sum(market_value) as market_value,
        sum(net_invested) as net_invested,
        sum(net_flow) as net_flow
    from {{ ref('fct_positions_daily') }}
    group by date_day
),

returns as (
    select
        *,
        -- Rounded so the stored value has a fixed number of decimals.
        round(
            case
                when lag(market_value) over (order by date_day) > 0
                    then (market_value - net_flow) / lag(market_value) over (order by date_day) - 1
                else 0
            end,
            10
        ) as daily_return
    from daily
)

select
    date_day,
    market_value,
    net_invested,
    net_flow,
    market_value - net_invested as total_gain,
    daily_return,
    exp(sum(ln(greatest(1 + daily_return, 1e-9))) over (order by date_day)) - 1 as cumulative_twr
from returns
