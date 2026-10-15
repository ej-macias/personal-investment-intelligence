-- Held instruments missing from the Airtable instruments table have no asset class,
-- region or price symbol. Add them there.
{{ config(severity='warn') }}

select isin, instrument_name
from {{ ref('dim_instrument') }}
where asset_class = 'Unclassified'
