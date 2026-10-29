{# Airtable records that still exist: the latest version of each, limited to the ids listed in
   the table's latest "__ids__" row (see invest_intel.ingestion.airtable). A row deleted in
   Airtable drops out on the next run. Before the first run that wrote an id list, every record
   is kept. #}
{% macro airtable_current(relation) %}
(
    with versions as {{ latest_records(relation) }},

    -- The most recent list only, so records under an old table name drop out after a rename.
    id_lists as (
        select payload -> 'ids' as ids
        from versions
        where record_key = '__ids__'
        order by loaded_at desc
        limit 1
    )

    select v.*
    from versions as v
    where v.record_key <> '__ids__'
      and (
          not exists (select 1 from id_lists)
          or exists (select 1 from id_lists as l where l.ids ? v.record_key)
      )
)
{% endmacro %}
