-- One row per account, snapshot date and instrument, unnested from the portfolio payload.
-- Structure checked against a live Indexa portfolio response.
with snapshots as {{ latest_records(source('raw', 'indexa_portfolio')) }},

positions as (
    select
        s.entity as account_id,
        s.record_key::date as snapshot_date,
        pos.value as pos
    from snapshots as s
    cross join lateral jsonb_array_elements(s.payload -> 'instrument_accounts') as acc (value)
    cross join lateral jsonb_array_elements(acc.value -> 'positions') as pos (value)
)

select
    account_id,
    snapshot_date,
    pos -> 'instrument' ->> 'identifier' as isin,
    pos -> 'instrument' ->> 'name' as instrument_name,
    (pos ->> 'titles')::numeric as quantity,
    (pos ->> 'price')::numeric as price,
    (pos ->> 'amount')::numeric as market_value
from positions
