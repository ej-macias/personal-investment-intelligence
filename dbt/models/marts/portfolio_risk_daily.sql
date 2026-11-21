-- The portfolio's average risk per day, weighted by money: a holding twice as large counts twice.
-- Holdings without a rating are left out of the average; rated_share says how much that covers.
-- Past days use today's ratings, since Airtable keeps no history of them.
with positions as (
    select
        p.date_day,
        p.market_value,
        i.risk_level
    from {{ ref('fct_positions_daily') }} as p
    left join {{ ref('dim_instrument') }} as i on p.isin = i.isin
    where p.quantity > 0
),

daily as (
    select
        date_day,
        sum(market_value) as market_value,
        coalesce(sum(market_value) filter (where risk_level is not null), 0) as rated_value,
        sum(market_value * risk_level) as risk_points
    from positions
    group by date_day
)

select
    date_day,
    market_value,
    rated_value,
    rated_value / nullif(market_value, 0) as rated_share,
    risk_points / nullif(rated_value, 0) as avg_risk
from daily
