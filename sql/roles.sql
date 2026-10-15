-- Run once per database as the owner, after the first `dbt build`.
-- The Streamlit app and the AI assistant connect as app_reader: they can read the gold
-- schema and nothing else, so neither raw payloads nor write access are ever exposed.

create role app_reader login password 'CHANGE_ME';

grant usage on schema gold to app_reader;
grant select on all tables in schema gold to app_reader;
alter default privileges in schema gold grant select on tables to app_reader;
