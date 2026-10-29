-- Every value named in the Airtable targets table should match the data, spelled exactly as in
-- Assets (asset_class, region, instrument_type, liquidity) or as a platform name. A misspelt
-- value matches nothing, so its limit would check an empty share.
{{ config(severity='warn') }}

with named as (
    select t.target_id, t.dimension, v.value
    from {{ ref('stg_airtable__targets') }} as t
    cross join lateral unnest(t.target_values) as v (value)
    where t.dimensions_filled = 1 and v.value <> 'Any' and t.dimension <> 'instrument'
),

known as (
    select 'asset_class' as dimension, asset_class as value from {{ ref('dim_instrument') }}
    union select 'region', region from {{ ref('dim_instrument') }}
    union select 'instrument_type', instrument_type from {{ ref('dim_instrument') }}
    union select 'liquidity', liquidity from {{ ref('dim_instrument') }}
    union select 'platform', platform from {{ ref('investment_returns') }}
)

select n.*
from named as n
left join known as k on n.dimension = k.dimension and n.value = k.value
where k.value is null
