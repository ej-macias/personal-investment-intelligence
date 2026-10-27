-- Run once in the private database as the owner role (the one the pipeline uses), after
-- sql/roles.sql. Stores the AI assistant's conversations so they survive between sessions.
-- app_reader can read and write this one table; it still only reads gold.
-- The demo never uses it.

create schema if not exists app;

create table if not exists app.assistant_conversations (
    id bigint generated always as identity primary key,
    owner_email text not null,
    title text not null,
    messages jsonb not null,  -- [[role, text], ...] as shown on screen
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists assistant_conversations_owner
    on app.assistant_conversations (owner_email, updated_at desc);

grant usage on schema app to app_reader;
grant select, insert, update, delete on app.assistant_conversations to app_reader;
