-- The owner's limits checked against today's portfolio. One row per limit; a limit on "Any"
-- value (or each_instrument) becomes one row per held value, except values that have a
-- single-value limit of their own, which overrides it.
-- Weights are shares of the whole portfolio: 0.6 means 60%.
with holdings as (
    select * from {{ ref('asset_allocation') }}
),

total as (
    select nullif(sum(market_value), 0) as portfolio_value from holdings
),

-- Today's value per dimension and value, e.g. ('region', 'Europe', 2500.00).
value_by_dimension as (
    {% set dimensions = ['asset_class', 'region', 'instrument_type', 'liquidity', 'platform'] %}
    {% for dimension in dimensions %}
    select '{{ dimension }}' as dimension, {{ dimension }} as value, sum(market_value) as current_value
    from holdings
    group by {{ dimension }}
    union all
    {% endfor %}
    select 'instrument' as dimension, isin as value, sum(market_value) as current_value
    from holdings
    group by isin
),

names as (
    select isin, instrument_name from {{ ref('dim_instrument') }}
),

limits as (
    select *
    from {{ ref('stg_airtable__targets') }}
    where dimensions_filled = 1 and cardinality(target_values) > 0
),

-- Values with a limit of their own are left out of that dimension's "Any" limits.
own_limit as (
    select dimension, target_values[1] as value
    from limits
    where cardinality(target_values) = 1 and target_values[1] <> 'Any'
),

group_checks as (
    select
        l.target_id,
        l.dimension,
        null::text as applies_to,
        case
            when l.dimension = 'instrument'
                then (
                    select string_agg(coalesce(n.instrument_name, v.value), ', ' order by v.ord)
                    from unnest(l.target_values) with ordinality as v (value, ord)
                    left join names as n on v.value = n.isin
                )
            else array_to_string(l.target_values, ', ')
        end as label,
        coalesce((
            select sum(d.current_value)
            from value_by_dimension as d
            where d.dimension = l.dimension and d.value = any(l.target_values)
        ), 0) as current_value,
        l.min_weight,
        l.target_weight,
        l.max_weight,
        l.note
    from limits as l
    where not ('Any' = any(l.target_values))
),

each_value_checks as (
    select
        l.target_id,
        l.dimension,
        d.value as applies_to,
        case when l.dimension = 'instrument' then coalesce(n.instrument_name, d.value) else d.value end
            as label,
        d.current_value,
        l.min_weight,
        l.target_weight,
        l.max_weight,
        l.note
    from limits as l
    inner join value_by_dimension as d on l.dimension = d.dimension
    left join names as n on l.dimension = 'instrument' and d.value = n.isin
    where 'Any' = any(l.target_values)
      and not exists (
          select 1 from own_limit as o where o.dimension = d.dimension and o.value = d.value
      )
),

checks as (
    select * from group_checks
    union all
    select * from each_value_checks
),

weighted as (
    select
        c.*,
        c.current_value / t.portfolio_value as current_weight,
        -- With a range and no target, aim for the middle of the range.
        coalesce(
            c.target_weight,
            case
                when c.min_weight is not null and c.max_weight is not null
                    then (c.min_weight + c.max_weight) / 2
            end
        ) as aim_weight,
        t.portfolio_value
    from checks as c
    cross join total as t
)

select
    md5(target_id || '|' || coalesce(applies_to, '')) as check_key,
    target_id,
    dimension,
    applies_to is not null as applies_to_each,
    label,
    round(current_value, 2) as current_value,
    current_weight,
    min_weight,
    aim_weight as target_weight,
    max_weight,
    case
        when min_weight is not null and current_weight < min_weight then 'Below minimum'
        when max_weight is not null and current_weight > max_weight then 'Above maximum'
        else 'Within range'
    end as status,
    round(
        case
            when min_weight is not null and current_weight < min_weight
                then (min_weight - current_weight) * portfolio_value
            when max_weight is not null and current_weight > max_weight
                then (max_weight - current_weight) * portfolio_value
            else 0
        end,
        2
    ) as amount_to_range,
    round((aim_weight - current_weight) * portfolio_value, 2) as amount_to_target,
    note
from weighted
