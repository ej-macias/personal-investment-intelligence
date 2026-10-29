-- The owner's limits, one row per Airtable row. Each row fills exactly one "what" field, which
-- becomes its dimension; "Any" (or the each_instrument checkbox) means every value separately.
-- Airtable Percent fields arrive as fractions (0.6 for 60%). Linked instruments arrive as
-- Airtable record ids and are mapped to ISINs.
with source as {{ airtable_current(source('raw', 'airtable_targets')) }},

fields as (
    select
        record_key as target_id,
        payload -> 'fields' as f
    from source
),

{% set what_fields = [
    ('asset_classes', 'asset_class'),
    ('regions', 'region'),
    ('instrument_types', 'instrument_type'),
    ('liquidity', 'liquidity'),
    ('platforms', 'platform'),
    ('instruments', 'instrument'),
] %}

typed as (
    select
        target_id,
        coalesce((f ->> 'each_instrument')::boolean, false) as each_instrument,
        (
            {% for field, _ in what_fields %}
            (case when jsonb_array_length(coalesce(f -> '{{ field }}', '[]')) > 0 then 1 else 0 end) +
            {% endfor %}
            (case when coalesce((f ->> 'each_instrument')::boolean, false) then 1 else 0 end)
        ) as dimensions_filled,
        case
            when coalesce((f ->> 'each_instrument')::boolean, false) then 'instrument'
            {% for field, dimension in what_fields %}
            when jsonb_array_length(coalesce(f -> '{{ field }}', '[]')) > 0 then '{{ dimension }}'
            {% endfor %}
        end as dimension,
        case
            when coalesce((f ->> 'each_instrument')::boolean, false) then '["Any"]'::jsonb
            {% for field, _ in what_fields %}
            when jsonb_array_length(coalesce(f -> '{{ field }}', '[]')) > 0 then f -> '{{ field }}'
            {% endfor %}
        end as raw_values,
        (f ->> 'min')::numeric as min_weight,
        (f ->> 'target')::numeric as target_weight,
        (f ->> 'max')::numeric as max_weight,
        nullif(trim(f ->> 'note'), '') as note
    from fields
)

select
    t.target_id,
    t.dimension,
    t.dimensions_filled,
    case
        when t.dimension = 'instrument' and not t.each_instrument
            then array(
                select i.isin
                from jsonb_array_elements_text(t.raw_values) as r (record_id)
                inner join {{ ref('stg_airtable__instruments') }} as i
                    on r.record_id = i.airtable_record_id
                order by i.isin
            )
        else array(select e.v from jsonb_array_elements_text(t.raw_values) as e (v))
    end as target_values,
    t.min_weight,
    t.target_weight,
    t.max_weight,
    t.note
from typed as t
