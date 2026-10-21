-- Where each holding stands today: cost, value and gain per account and instrument.
-- Closed positions stay in, with their realised gain.
with latest as (
    select *
    from {{ ref('fct_positions_daily') }}
    where date_day = (select max(date_day) from {{ ref('fct_positions_daily') }})
),

bought as (
    select
        account_id,
        isin,
        sum(amount) filter (where transaction_type = 'buy') as total_bought,
        min(trade_date) as first_trade_date
    from {{ ref('fct_transactions') }}
    group by account_id, isin
)

select
    l.account_id,
    l.isin,
    i.instrument_name,
    i.asset_class,
    i.region,
    i.instrument_type,
    i.liquidity,
    b.first_trade_date,
    l.quantity,
    l.net_invested,
    l.market_value,
    l.market_value - l.net_invested as total_gain,
    (l.market_value - l.net_invested) / nullif(b.total_bought, 0) as return_pct,
    l.is_price_estimated
from latest as l
inner join bought as b on l.account_id = b.account_id and l.isin = b.isin
left join {{ ref('dim_instrument') }} as i on l.isin = i.isin
