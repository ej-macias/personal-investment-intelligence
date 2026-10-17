"""Login gate. The demo is open; every other environment needs an allowlisted Google login."""

import streamlit as st

from invest_intel import config


def _allowed_emails() -> set[str]:
    return {
        e.strip().lower() for e in (config.env("ALLOWED_EMAILS", "") or "").split(",") if e.strip()
    }


def require_login() -> None:
    """Stop the script unless the viewer may see the data. Fails closed."""
    if config.is_demo():
        st.sidebar.info("Demo: a fictional portfolio valued at real market prices.")
        return

    if not st.user.is_logged_in:
        st.title("Investment Intelligence")
        st.button("Log in with Google", on_click=st.login, type="primary")
        st.stop()

    email = (st.user.get("email") or "").lower()
    if not st.user.get("email_verified") or email not in _allowed_emails():
        st.error("This account is not allowed to view this app.")
        st.button("Log out", on_click=st.logout)
        st.stop()

    st.sidebar.button("Log out", on_click=st.logout)
