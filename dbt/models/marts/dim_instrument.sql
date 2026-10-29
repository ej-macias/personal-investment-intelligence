-- Every instrument held or used as a benchmark. Instruments seen in Indexa that have not
-- been described in Airtable yet still appear, flagged as Unclassified.
with described as (
    select
        isin,
        instrument_name,
        eodhd_symbol,
        asset_class,
        region,
        instrument_type,
        liquidity,
        currency,
        is_benchmark,
        ter as yearly_fee_pct
    from {{ ref('stg_airtable__instruments') }}
),

undescribed as (
    select
        isin,
        max(instrument_name) as instrument_name
    from {{ ref('stg_indexa__transactions') }}
    where isin not in (select isin from described)
    group by isin
)

select * from described

union all

select
    isin,
    instrument_name,
    null::text as eodhd_symbol,
    'Unclassified'::text as asset_class,
    'Unclassified'::text as region,
    'Unclassified'::text as instrument_type,
    'Unclassified'::text as liquidity,
    'EUR'::text as currency,
    false as is_benchmark,
    null::numeric as yearly_fee_pct
from undescribed
