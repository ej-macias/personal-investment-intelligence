"""Colors shared by the two-line charts."""

import streamlit as st

# Blue for the portfolio's own line, orange for what it is compared with.
TWO_LINES = {"light": ["#2a78d6", "#eb6834"], "dark": ["#3987e5", "#d95926"]}


def theme() -> str:
    """The app's current theme, falling back to light while it is not known yet."""
    current = st.context.theme.type
    return current if current in TWO_LINES else "light"


def two_lines() -> list[str]:
    return TWO_LINES[theme()]
