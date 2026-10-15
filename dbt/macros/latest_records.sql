{# Raw tables are append-only: keep the most recently loaded version of each record. #}
{% macro latest_records(relation) %}
(
    select distinct on (entity, record_key)
        entity,
        record_key,
        payload,
        loaded_at
    from {{ relation }}
    order by entity, record_key, loaded_at desc, id desc
)
{% endmacro %}
