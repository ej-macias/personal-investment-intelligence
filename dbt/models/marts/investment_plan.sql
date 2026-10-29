-- The owner's plan in one row: goal, horizon and rules from Airtable, plus how much money has
-- actually been added per month over the last 12 complete months (contributions are irregular,
-- so this replaces a planned monthly amount). Empty when no plan has been written.
with plan as (
    select *
    from {{ ref('stg_airtable__plan') }}
    order by loaded_at desc, plan_id
    limit 1
),

recent_months as (
    select money_added
    from {{ ref('portfolio_monthly') }}
    where is_complete
    order by month desc
    limit 12
)

select
    p.goal,
    p.horizon_year,
    p.rules,
    (select round(avg(money_added), 2) from recent_months) as avg_money_added_12m
from plan as p
