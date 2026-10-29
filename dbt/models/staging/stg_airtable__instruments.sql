with source as {{ airtable_current(source('raw', 'airtable_instruments')) }}

select
    record_key as airtable_record_id,
    payload -> 'fields' ->> 'isin' as isin,
    payload -> 'fields' ->> 'name' as instrument_name,
    nullif(payload -> 'fields' ->> 'eodhd_symbol', '') as eodhd_symbol,
    coalesce(payload -> 'fields' ->> 'asset_class', 'Unclassified') as asset_class,
    coalesce(payload -> 'fields' ->> 'region', 'Unclassified') as region,
    coalesce(payload -> 'fields' ->> 'instrument_type', 'Unclassified') as instrument_type,
    coalesce(payload -> 'fields' ->> 'liquidity', 'Unclassified') as liquidity,
    coalesce(payload -> 'fields' ->> 'currency', 'EUR') as currency,
    -- Yearly fee as a fraction: Airtable Percent fields arrive as 0.002 for 0.20%
    (payload -> 'fields' ->> 'ter')::numeric as ter,
    -- Airtable leaves unchecked checkboxes out of the payload
    coalesce((payload -> 'fields' ->> 'is_benchmark')::boolean, false) as is_benchmark
from source
where payload -> 'fields' ->> 'isin' is not null
