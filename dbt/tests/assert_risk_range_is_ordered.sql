-- risk_min <= risk_target <= risk_max in the Airtable plan, all on the 1 to 7 scale.
{{ config(severity='warn') }}

select plan_id, risk_min, risk_target, risk_max
from {{ ref('stg_airtable__plan') }}
where risk_min > coalesce(risk_target, risk_max)
   or risk_target > risk_max
   or least(risk_min, risk_target, risk_max) < 1
   or greatest(risk_min, risk_target, risk_max) > 7
