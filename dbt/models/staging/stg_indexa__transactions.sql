-- TODO(verify): field names and operation_type codes against a real Indexa payload.
with source as {{ latest_records(source('raw', 'indexa_instrument_transactions')) }}

select
    entity as account_id,
    record_key as transaction_id,
    (payload ->> 'date')::date as trade_date,
    payload -> 'instrument' ->> 'identifier' as isin,
    payload -> 'instrument' ->> 'name' as instrument_name,
    lower(payload ->> 'operation_type') as transaction_type,
    abs((payload ->> 'titles')::numeric) as quantity,
    (payload ->> 'price')::numeric as price,
    abs((payload ->> 'amount')::numeric) as amount,
    loaded_at
from source
