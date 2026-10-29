-- min <= target <= max in every Airtable targets row, and per dimension the minimums of the
-- named groups add up to no more than 100%.
{{ config(severity='warn') }}

select target_id, 'min, target and max are out of order' as problem
from {{ ref('stg_airtable__targets') }}
where min_weight > coalesce(target_weight, max_weight)
   or target_weight > max_weight

union all

select dimension, 'minimums add up to more than 100%'
from {{ ref('stg_airtable__targets') }}
where dimensions_filled = 1 and not ('Any' = any(target_values))
group by dimension
having sum(coalesce(min_weight, 0)) > 1
