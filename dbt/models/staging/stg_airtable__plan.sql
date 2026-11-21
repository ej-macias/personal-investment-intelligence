-- The owner's plan: what the money is for, when it is needed, and their own rules.
with source as {{ airtable_current(source('raw', 'airtable_plan')) }}

select
    record_key as plan_id,
    nullif(trim(payload -> 'fields' ->> 'goal'), '') as goal,
    (payload -> 'fields' ->> 'horizon_year')::numeric::integer as horizon_year,
    nullif(trim(payload -> 'fields' ->> 'rules'), '') as rules,
    -- The accepted range and goal for the portfolio's average risk, on the 1 to 7 scale.
    (payload -> 'fields' ->> 'risk_min')::numeric as risk_min,
    (payload -> 'fields' ->> 'risk_target')::numeric as risk_target,
    (payload -> 'fields' ->> 'risk_max')::numeric as risk_max,
    loaded_at
from source
