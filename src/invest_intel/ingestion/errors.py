"""Errors that are safe to print in public GitHub Actions logs."""

from __future__ import annotations


class SourceHTTPError(Exception):
    """An HTTP error described by status code and what was asked for, never by URL.

    `what` must not contain tokens or account numbers: a table name or an endpoint template.
    """

    def __init__(self, status: int, what: str) -> None:
        super().__init__(f"HTTP {status} ({what})")
        self.status = status
