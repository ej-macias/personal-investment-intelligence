-- Current holdings per instrument and platform with their share of the portfolio.
-- Aggregate by asset_class, region, instrument_type, liquidity or platform for the
-- allocation views.
with holdings as (
    select
        isin,
        platform,
        max(instrument_name) as instrument_name,
        max(asset_class) as asset_class,
        max(region) as region,
        max(instrument_type) as instrument_type,
        max(liquidity) as liquidity,
        sum(market_value) as market_value
    from {{ ref('investment_returns') }}
    where quantity > 0
    group by isin, platform
)

select
    md5(isin || '|' || platform) as allocation_key,
    isin,
    platform,
    coalesce(instrument_name, isin) as instrument_name,
    coalesce(asset_class, 'Unclassified') as asset_class,
    coalesce(region, 'Unclassified') as region,
    coalesce(instrument_type, 'Unclassified') as instrument_type,
    coalesce(liquidity, 'Unclassified') as liquidity,
    market_value,
    market_value / nullif(sum(market_value) over (), 0) as weight
from holdings
