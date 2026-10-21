with source as {{ latest_records(source('raw', 'airtable_instruments')) }}

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
    -- Airtable leaves unchecked checkboxes out of the payload
    coalesce((payload -> 'fields' ->> 'is_benchmark')::boolean, false) as is_benchmark
from source
where payload -> 'fields' ->> 'isin' is not null
