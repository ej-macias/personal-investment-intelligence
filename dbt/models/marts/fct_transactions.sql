-- All buys and sells across Indexa and manually tracked accounts, in one shape.
-- signed_quantity and signed_amount are positive for money going into an instrument.
with indexa as (
    select
        'indexa'::text as source,
        account_id,
        transaction_id,
        trade_date,
        isin,
        transaction_type,
        quantity,
        price,
        amount
    from {{ ref('stg_indexa__transactions') }}
),

manual as (
    select
        'airtable'::text as source,
        account_id,
        transaction_id,
        trade_date,
        isin,
        transaction_type,
        quantity,
        price,
        round(quantity * price + case when transaction_type = 'sell' then -fees else fees end, 2)
            as amount
    from {{ ref('stg_airtable__transactions') }}
),

unioned as (
    select * from indexa
    union all
    select * from manual
)

select
    md5(source || '|' || account_id || '|' || transaction_id) as transaction_key,
    source,
    account_id,
    transaction_id,
    trade_date,
    isin,
    transaction_type,
    quantity,
    price,
    amount,
    case transaction_type when 'buy' then quantity when 'sell' then -quantity else 0 end
        as signed_quantity,
    case transaction_type when 'buy' then amount when 'sell' then -amount else 0 end
        as signed_amount
from unioned
