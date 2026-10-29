-- The owner's plan: what the money is for, when it is needed, and their own rules.
with source as {{ airtable_current(source('raw', 'airtable_plan')) }}

select
    record_key as plan_id,
    nullif(trim(payload -> 'fields' ->> 'goal'), '') as goal,
    (payload -> 'fields' ->> 'horizon_year')::numeric::integer as horizon_year,
    nullif(trim(payload -> 'fields' ->> 'rules'), '') as rules,
    loaded_at
from source
