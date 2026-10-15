"""PostgreSQL connections. Credentials come from the PG* environment variables."""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row


def connect() -> psycopg.Connection:
    """Read-write connection for ingestion jobs."""
    return psycopg.connect("")


def query(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run a read-only query and return rows as dicts. Used by the app and the assistant."""
    with psycopg.connect("", row_factory=dict_row) as conn:
        conn.read_only = True
        return conn.execute(sql, params or {}).fetchall()
