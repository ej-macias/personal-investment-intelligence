"""Bronze layer: append-only raw tables holding source payloads as JSONB.

Every raw table has the same shape, so adding a source means adding a name to RAW_TABLES.
A payload is stored again only when it changed, which keeps daily full refreshes of small
endpoints idempotent and the database inside the Neon free tier.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

RAW_SCHEMA = "raw"
RAW_TABLES = (
    "indexa_portfolio",
    "indexa_instrument_transactions",
    "indexa_cash_transactions",
    "airtable_instruments",
    "airtable_transactions",
    "airtable_plan",
    "airtable_targets",
    "eodhd_prices",
)

# (entity, record_key, payload): entity is the account, table or symbol the record belongs to.
Row = tuple[str, str, dict[str, Any]]

_DDL = """
create table if not exists {table} (
    id           bigint generated always as identity primary key,
    run_id       text        not null,
    loaded_at    timestamptz not null default now(),
    entity       text        not null,
    record_key   text        not null,
    payload      jsonb       not null,
    payload_hash text        not null,
    unique (entity, record_key, payload_hash)
)
"""

_INSERT = """
insert into {table} (run_id, entity, record_key, payload, payload_hash)
values (%s, %s, %s, %s, %s)
on conflict do nothing
"""


def payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _table(name: str) -> sql.Identifier:
    if name not in RAW_TABLES:
        raise ValueError(f"Unknown raw table: {name}")
    return sql.Identifier(RAW_SCHEMA, name)


def ensure_tables(conn: psycopg.Connection) -> None:
    conn.execute(sql.SQL("create schema if not exists {}").format(sql.Identifier(RAW_SCHEMA)))
    for name in RAW_TABLES:
        conn.execute(sql.SQL(_DDL).format(table=_table(name)))
    conn.commit()


def load(conn: psycopg.Connection, table: str, rows: Iterable[Row], run_id: str) -> int:
    """Append rows to a raw table and return how many were new or changed."""
    params = [
        (run_id, entity, key, Jsonb(payload), payload_hash(payload))
        for entity, key, payload in rows
    ]
    if not params:
        return 0
    with conn.cursor() as cur:
        cur.executemany(sql.SQL(_INSERT).format(table=_table(table)), params)
        inserted = cur.rowcount
    conn.commit()
    return inserted


def truncate_all(conn: psycopg.Connection) -> None:
    for name in RAW_TABLES:
        conn.execute(sql.SQL("truncate table {}").format(_table(name)))
    conn.commit()
