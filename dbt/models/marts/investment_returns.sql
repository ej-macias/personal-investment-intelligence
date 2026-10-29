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
        min(trade_date) as first_trade_date,
        max(source) as source
    from {{ ref('fct_transactions') }}
    group by account_id, isin
)

select
    l.account_id,
    -- The platform holding it: every Indexa account is one platform; manually tracked
    -- accounts are named in Airtable (e.g. a broker).
    case when b.source = 'indexa' then 'Indexa Capital' else l.account_id end as platform,
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
    -- What the fund charges per year at today's value; empty when its fee is not recorded.
    round(l.market_value * i.yearly_fee_pct, 2) as yearly_fee,
    l.is_price_estimated
from latest as l
inner join bought as b on l.account_id = b.account_id and l.isin = b.isin
left join {{ ref('dim_instrument') }} as i on l.isin = i.isin
