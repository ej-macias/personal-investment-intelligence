-- One row of simple facts about the portfolio's ups and downs: best and worst month, how
-- often a month ended with a gain, and the biggest drop from a previous high.
-- Months: complete months only. Drops: measured on the time-weighted return, so adding or
-- withdrawing money does not look like a rise or a fall.
with complete_months as (
    select *
    from {{ ref('portfolio_monthly') }}
    where is_complete
),

best as (
    select month, return_pct
    from complete_months
    order by return_pct desc, month
    limit 1
),

worst as (
    select month, return_pct
    from complete_months
    order by return_pct asc, month
    limit 1
),

month_counts as (
    select
        count(*)::integer as months_counted,
        (count(*) filter (where gain > 0))::integer as months_with_gain
    from complete_months
),

levels as (
    select
        date_day,
        1 + cumulative_twr as level,
        max(1 + cumulative_twr) over (order by date_day) as high
    from {{ ref('portfolio_performance') }}
),

drops as (
    select
        date_day,
        level / high - 1 as drop_pct
    from levels
),

deepest as (
    select date_day, drop_pct
    from drops
    order by drop_pct asc, date_day
    limit 1
),

drop_start as (
    -- The last high before the deepest point.
    select max(d.date_day) as date_day
    from drops as d
    cross join deepest
    where d.date_day <= deepest.date_day and d.drop_pct = 0
),

latest as (
    select drop_pct
    from drops
    order by date_day desc
    limit 1
)

select
    best.month as best_month,
    best.return_pct as best_month_return,
    worst.month as worst_month,
    worst.return_pct as worst_month_return,
    c.months_counted,
    c.months_with_gain,
    round(c.months_with_gain::numeric / nullif(c.months_counted, 0), 4) as share_of_months_with_gain,
    round(deepest.drop_pct, 10) as biggest_drop_pct,
    drop_start.date_day as biggest_drop_from,
    deepest.date_day as biggest_drop_to,
    round(latest.drop_pct, 10) as below_high_pct
from month_counts as c
cross join deepest
cross join drop_start
cross join latest
left join best on true
left join worst on true
