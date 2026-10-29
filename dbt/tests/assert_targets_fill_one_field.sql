-- Each row in the Airtable targets table should fill exactly one of asset_classes, regions,
-- instrument_types, liquidity, platforms, instruments or each_instrument. Rows that don't are
-- ignored by target_checks.
{{ config(severity='warn') }}

select target_id, dimensions_filled
from {{ ref('stg_airtable__targets') }}
where dimensions_filled <> 1
