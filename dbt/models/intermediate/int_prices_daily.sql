-- One price per instrument per calendar day.
-- EODHD is the primary source; the price Indexa reports in each portfolio snapshot fills
-- gaps for free. Days without a quote (weekends, holidays, NAV lag) carry the last price.
with eodhd as (
    select
        i.isin,
        p.price_date,
        p.close_price,
        1 as source_priority
    from {{ ref('stg_eodhd__prices') }} as p
    inner join {{ ref('stg_airtable__instruments') }} as i on p.symbol = i.eodhd_symbol
),

indexa as (
    select
        isin,
        snapshot_date as price_date,
        price as close_price,
        2 as source_priority
    from {{ ref('stg_indexa__positions') }}
    where price is not null
),

observed as (
    select distinct on (isin, price_date)
        isin,
        price_date,
        close_price
    from (
        select * from eodhd
        union all
        select * from indexa
    ) as unioned
    order by isin, price_date, source_priority
),

bounds as (
    select
        isin,
        min(price_date) as first_date
    from observed
    group by isin
),

spine as (
    select
        b.isin,
        g.d::date as date_day
    from bounds as b
    cross join lateral generate_series(
        b.first_date::timestamp, {{ as_of_date() }}::timestamp, interval '1 day'
    ) as g (d)
),

joined as (
    select
        s.isin,
        s.date_day,
        o.close_price as observed_price,
        count(o.close_price) over (partition by s.isin order by s.date_day) as fill_group
    from spine as s
    left join observed as o on s.isin = o.isin and s.date_day = o.price_date
)

select
    isin,
    date_day,
    max(observed_price) over (partition by isin, fill_group) as close_price,
    observed_price is null as is_forward_filled
from joined
