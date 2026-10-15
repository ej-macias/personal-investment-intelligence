{# Use the configured schema as is (silver, gold) instead of prefixing it with the target schema. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name | trim if custom_schema_name is not none else target.schema }}
{%- endmacro %}
