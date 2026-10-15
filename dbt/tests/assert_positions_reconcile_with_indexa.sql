-- Positions rebuilt from transactions should match what Indexa reports in its snapshots.
{{ config(severity='warn') }}

select
    s.account_id,
    s.isin,
    s.snapshot_date,
    s.quantity as reported_quantity,
    p.quantity as derived_quantity
from {{ ref('stg_indexa__positions') }} as s
left join {{ ref('fct_positions_daily') }} as p
    on s.account_id = p.account_id and s.isin = p.isin and s.snapshot_date = p.date_day
where abs(s.quantity - coalesce(p.quantity, 0)) > 0.001
