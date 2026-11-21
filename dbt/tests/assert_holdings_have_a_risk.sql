-- Every holding should have a risk from 1 to 7 in Airtable. One without a valid rating is left
-- out of the portfolio's average risk.
{{ config(severity='warn') }}

select isin, instrument_name, market_value
from {{ ref('asset_allocation') }}
where risk_level is null
