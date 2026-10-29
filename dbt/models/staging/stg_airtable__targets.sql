-- The owner's limits, one row per Airtable row. Each row fills exactly one "what" field, which
-- becomes its dimension; "Any" (or the each_instrument checkbox) means every value separately.
-- each_instrument may be narrowed by one select field, e.g. instrument_types = Share for
-- "no single company above 10%": that field becomes the row's scope, not its dimension.
-- Airtable Percent fields arrive as fractions (0.6 for 60%). Linked instruments arrive as
-- Airtable record ids and are mapped to ISINs.
with source as {{ airtable_current(source('raw', 'airtable_targets')) }},

fields as (
    select
        record_key as target_id,
        payload -> 'fields' as f
    from source
),

{% set select_fields = [
    ('asset_classes', 'asset_class'),
    ('regions', 'region'),
    ('instrument_types', 'instrument_type'),
    ('liquidity', 'liquidity'),
    ('platforms', 'platform'),
] %}
{% set what_fields = select_fields + [('instruments', 'instrument')] %}

counted as (
    select
        target_id,
        f,
        coalesce((f ->> 'each_instrument')::boolean, false) as each_instrument,
        (
            {% for field, _ in select_fields %}
            (case when jsonb_array_length(coalesce(f -> '{{ field }}', '[]')) > 0 then 1 else 0 end)
            {{- " +" if not loop.last }}
            {% endfor %}
        ) as selects_filled,
        jsonb_array_length(coalesce(f -> 'instruments', '[]')) > 0 as instruments_filled
    from fields
),

typed as (
    select
        target_id,
        each_instrument,
        -- each_instrument counts as the one "what" field and may take one select as its scope.
        case
            when each_instrument
                then 1 + (case when instruments_filled then 1 else 0 end) + greatest(selects_filled - 1, 0)
            else selects_filled + (case when instruments_filled then 1 else 0 end)
        end as dimensions_filled,
        case
            when each_instrument and selects_filled = 1 then
                case
                    {% for field, dimension in select_fields %}
                    when jsonb_array_length(coalesce(f -> '{{ field }}', '[]')) > 0 then '{{ dimension }}'
                    {% endfor %}
                end
        end as scope_dimension,
        case
            when each_instrument and selects_filled = 1 then
                case
                    {% for field, _ in select_fields %}
                    when jsonb_array_length(coalesce(f -> '{{ field }}', '[]')) > 0 then f -> '{{ field }}'
                    {% endfor %}
                end
        end as scope_raw,
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
    from counted
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
    t.scope_dimension,
    case
        when t.scope_raw is not null
            then array(select e.v from jsonb_array_elements_text(t.scope_raw) as e (v))
    end as scope_values,
    t.min_weight,
    t.target_weight,
    t.max_weight,
    t.note
from typed as t
