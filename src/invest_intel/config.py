"""Environment-driven settings. Database credentials use the standard PG* variables."""

from __future__ import annotations

import os

DEMO = "demo"


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value else default


def require(name: str) -> str:
    value = env(name)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def app_env() -> str:
    return (env("APP_ENV", "dev") or "dev").lower()


def is_demo() -> bool:
    return app_env() == DEMO
