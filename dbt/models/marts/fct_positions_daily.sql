-- Quantity held, money invested and market value per account and instrument for every
-- calendar day since the first trade. Positions are rebuilt from transactions.
-- Where no price exists yet (before the price history starts) the position is valued at
-- cost and flagged with is_price_estimated.
with daily_trades as (
    select
        account_id,
        isin,
        trade_date,
        sum(signed_quantity) as quantity_change,
        sum(signed_amount) as net_flow
    from {{ ref('fct_transactions') }}
    group by account_id, isin, trade_date
),

bounds as (
    select
        account_id,
        isin,
        min(trade_date) as first_date
    from daily_trades
    group by account_id, isin
),

spine as (
    select
        b.account_id,
        b.isin,
        g.d::date as date_day
    from bounds as b
    cross join lateral generate_series(
        b.first_date::timestamp, current_date::timestamp, interval '1 day'
    ) as g (d)
),

cumulative as (
    select
        s.account_id,
        s.isin,
        s.date_day,
        coalesce(t.net_flow, 0) as net_flow,
        sum(coalesce(t.quantity_change, 0)) over position_to_date as quantity,
        sum(coalesce(t.net_flow, 0)) over position_to_date as net_invested
    from spine as s
    left join daily_trades as t
        on s.account_id = t.account_id and s.isin = t.isin and s.date_day = t.trade_date
    window position_to_date as (partition by s.account_id, s.isin order by s.date_day)
)

select
    md5(c.account_id || '|' || c.isin || '|' || c.date_day) as position_key,
    c.account_id,
    c.isin,
    c.date_day,
    c.quantity,
    c.net_flow,
    c.net_invested,
    p.close_price,
    p.close_price is null as is_price_estimated,
    coalesce(
        round(c.quantity * coalesce(p.close_price, c.net_invested / nullif(c.quantity, 0)), 2), 0
    ) as market_value
from cumulative as c
left join {{ ref('int_prices_daily') }} as p on c.isin = p.isin and c.date_day = p.date_day
