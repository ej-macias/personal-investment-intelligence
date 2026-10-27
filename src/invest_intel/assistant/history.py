"""Saved assistant conversations, private app only.

Stored in app.assistant_conversations (sql/assistant_history.sql) as the question and answer
text shown on screen. Every statement is limited to the logged-in owner's email. Reopening a
conversation reads it from the database; the Anthropic API is called only when a new question
is sent, with the earlier text rebuilt by api_messages().
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from psycopg.types.json import Jsonb

from invest_intel import config, db

Chat = list[tuple[str, str]]

TITLE_LENGTH = 80
LIST_LIMIT = 50
RETENTION_MONTHS = 12


def enabled() -> bool:
    """The demo is anonymous and read-only, so it never stores history."""
    return not config.is_demo()


def _title(chat: Chat) -> str:
    question = next((text for role, text in chat if role == "user"), "Conversation")
    question = " ".join(question.split())
    return question if len(question) <= TITLE_LENGTH else question[: TITLE_LENGTH - 1] + "…"


def list_conversations(email: str) -> list[dict[str, Any]]:
    return db.execute(
        """
        select id, title, updated_at
        from app.assistant_conversations
        where owner_email = %(email)s
        order by updated_at desc
        limit %(limit)s
        """,
        {"email": email, "limit": LIST_LIMIT},
    )


def load(conversation_id: int, email: str) -> Chat:
    rows = db.execute(
        """
        select messages
        from app.assistant_conversations
        where id = %(id)s and owner_email = %(email)s
        """,
        {"id": conversation_id, "email": email},
    )
    return [(role, text) for role, text in rows[0]["messages"]] if rows else []


def save(conversation_id: int | None, email: str, chat: Chat) -> int:
    """Insert a new conversation or update an existing one; returns its id."""
    params = {
        "id": conversation_id,
        "email": email,
        "title": _title(chat),
        "messages": Jsonb([list(pair) for pair in chat]),
    }
    if conversation_id is not None:
        rows = db.execute(
            """
            update app.assistant_conversations
            set messages = %(messages)s, updated_at = now()
            where id = %(id)s and owner_email = %(email)s
            returning id
            """,
            params,
        )
        if rows:
            return rows[0]["id"]
    rows = db.execute(
        """
        insert into app.assistant_conversations (owner_email, title, messages)
        values (%(email)s, %(title)s, %(messages)s)
        returning id
        """,
        params,
    )
    return rows[0]["id"]


def delete(conversation_id: int, email: str) -> None:
    db.execute(
        """
        delete from app.assistant_conversations
        where id = %(id)s and owner_email = %(email)s
        """,
        {"id": conversation_id, "email": email},
    )


def purge(email: str, months: int = RETENTION_MONTHS) -> None:
    """Delete conversations not touched for `months` months."""
    db.execute(
        """
        delete from app.assistant_conversations
        where owner_email = %(email)s
          and updated_at < now() - make_interval(months => %(months)s)
        """,
        {"email": email, "months": months},
    )


def api_messages(chat: Chat) -> list[dict[str, Any]]:
    """Claude API messages from saved text: user and assistant turns alternating, starting
    with the user. Consecutive turns from the same side are merged."""
    messages: list[dict[str, Any]] = []
    for role, text in chat:
        if role not in ("user", "assistant") or (not messages and role != "user"):
            continue
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += "\n\n" + text
        else:
            messages.append({"role": role, "content": text})
    if messages and messages[-1]["role"] == "user":
        messages.pop()  # an unanswered question; the new one is appended by the caller
    return messages


def label(row: dict[str, Any]) -> str:
    when = row["updated_at"]
    when = when.strftime("%d %b %Y") if isinstance(when, datetime) else str(when)
    return f"{when} · {row['title']}"
