-- Portfolio time-weighted return next to each benchmark's price return, both rebased to
-- zero on the first day they have in common.
with benchmark_prices as (
    select
        p.isin as benchmark_isin,
        i.instrument_name as benchmark_name,
        p.date_day,
        p.close_price
    from {{ ref('int_prices_daily') }} as p
    inner join {{ ref('dim_instrument') }} as i on p.isin = i.isin
    where i.is_benchmark
),

joined as (
    select
        b.benchmark_isin,
        b.benchmark_name,
        b.date_day,
        b.close_price,
        perf.cumulative_twr,
        first_value(b.close_price) over since_start as base_price,
        first_value(perf.cumulative_twr) over since_start as base_twr
    from benchmark_prices as b
    inner join {{ ref('portfolio_performance') }} as perf on b.date_day = perf.date_day
    window since_start as (partition by b.benchmark_isin order by b.date_day)
)

select
    benchmark_isin,
    benchmark_name,
    date_day,
    (1 + cumulative_twr) / (1 + base_twr) - 1 as portfolio_return,
    close_price / base_price - 1 as benchmark_return,
    (1 + cumulative_twr) / (1 + base_twr) - close_price / base_price as excess_return
from joined
