-- Current holdings per instrument with their share of the portfolio.
-- Aggregate by asset_class or region for the allocation views.
with holdings as (
    select
        isin,
        max(instrument_name) as instrument_name,
        max(asset_class) as asset_class,
        max(region) as region,
        sum(market_value) as market_value
    from {{ ref('investment_returns') }}
    where quantity > 0
    group by isin
)

select
    isin,
    coalesce(instrument_name, isin) as instrument_name,
    coalesce(asset_class, 'Unclassified') as asset_class,
    coalesce(region, 'Unclassified') as region,
    market_value,
    market_value / nullif(sum(market_value) over (), 0) as weight
from holdings
