with source as {{ latest_records(source('raw', 'eodhd_prices')) }}

select
    entity as symbol,
    record_key::date as price_date,
    -- Unadjusted close: market value is quantity held times the quoted price.
    (payload ->> 'close')::numeric as close_price,
    (payload ->> 'adjusted_close')::numeric as adjusted_close_price
from source
