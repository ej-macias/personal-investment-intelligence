-- The Airtable plan table should have one row; with several, the most recently changed is used.
{{ config(severity='warn') }}

select count(*) as plan_rows
from {{ ref('stg_airtable__plan') }}
having count(*) > 1
