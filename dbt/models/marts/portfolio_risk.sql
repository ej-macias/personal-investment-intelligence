-- Today's average risk against the owner's range and goal, in one row. Still has a row without
-- a plan, with the limits empty.
-- An average just outside its range (by up to 0.1 points) is "slightly" off: worth knowing, not
-- worth acting on.
with latest as (
    select *
    from {{ ref('portfolio_risk_daily') }}
    order by date_day desc
    limit 1
),

with_plan as (
    select
        l.*,
        p.risk_min,
        p.risk_max,
        -- With a range and no target, aim for the middle of the range.
        coalesce(p.risk_target, (p.risk_min + p.risk_max) / 2) as risk_target
    from latest as l
    left join {{ ref('investment_plan') }} as p on true
)

select
    date_day,
    market_value,
    rated_value,
    rated_share,
    avg_risk,
    risk_min,
    risk_target,
    risk_max,
    case
        when avg_risk is null or (risk_min is null and risk_max is null) then null
        when avg_risk < risk_min - 0.1 then 'Below minimum'
        when avg_risk < risk_min then 'Slightly below minimum'
        when avg_risk > risk_max + 0.1 then 'Above maximum'
        when avg_risk > risk_max then 'Slightly above maximum'
        else 'Within range'
    end as status,
    case
        when avg_risk < risk_min then risk_min - avg_risk
        when avg_risk > risk_max then risk_max - avg_risk
        when avg_risk is not null then 0
    end as points_to_range,
    risk_target - avg_risk as points_to_target
from with_plan
