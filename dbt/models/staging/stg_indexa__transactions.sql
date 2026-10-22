-- TODO(verify): field names against a real Indexa payload. Operation labels: confirmed.
with source as {{ latest_records(source('raw', 'indexa_instrument_transactions')) }}

select
    entity as account_id,
    record_key as transaction_id,
    (payload ->> 'date')::date as trade_date,
    payload -> 'instrument' ->> 'identifier' as isin,
    payload -> 'instrument' ->> 'name' as instrument_name,
    -- Indexa labels operations in Spanish, e.g. "suscripción fondos inversión" for a fund
    -- purchase and "aportacion a plan de pensiones" for a pension contribution. Anything not
    -- recognised passes through unchanged, so the accepted_values test on fct_transactions
    -- stops the build instead of the operation being miscounted.
    case
        when lower(payload ->> 'operation_type') in ('buy', 'sell')
            then lower(payload ->> 'operation_type')
        when lower(payload ->> 'operation_type') like any (array['%suscrip%', '%aportaci%'])
            then 'buy'
        when lower(payload ->> 'operation_type') like any (array['%reembolso%', '%prestaci%'])
            then 'sell'
        else lower(payload ->> 'operation_type')
    end as transaction_type,
    payload ->> 'operation_type' as operation_type,
    abs((payload ->> 'titles')::numeric) as quantity,
    (payload ->> 'price')::numeric as price,
    abs((payload ->> 'amount')::numeric) as amount,
    loaded_at
from source
