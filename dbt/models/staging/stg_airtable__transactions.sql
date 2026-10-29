with source as {{ airtable_current(source('raw', 'airtable_transactions')) }}

select
    coalesce(payload -> 'fields' ->> 'account', 'Manual') as account_id,
    record_key as transaction_id,
    (payload -> 'fields' ->> 'date')::date as trade_date,
    payload -> 'fields' ->> 'isin' as isin,
    lower(payload -> 'fields' ->> 'type') as transaction_type,
    (payload -> 'fields' ->> 'quantity')::numeric as quantity,
    (payload -> 'fields' ->> 'price')::numeric as price,
    coalesce((payload -> 'fields' ->> 'fees')::numeric, 0) as fees,
    loaded_at
from source
