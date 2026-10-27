"""Login gate. The demo is open; every other environment needs an allowlisted login (Auth0)."""

import streamlit as st

from invest_intel import config


def _allowed_emails() -> set[str]:
    return {
        e.strip().lower() for e in (config.env("ALLOWED_EMAILS", "") or "").split(",") if e.strip()
    }


def _login_configured() -> bool:
    """True when the app's secrets have an [auth] section for st.login()."""
    try:
        return "auth" in st.secrets
    except Exception:  # noqa: BLE001 - no secrets file at all
        return False


def require_login() -> None:
    """Stop the script unless the viewer may see the data. Fails closed."""
    if config.is_demo():
        st.sidebar.info("Demo: a fictional portfolio valued at real market prices.")
        return

    if not _login_configured():
        st.title("Investment Intelligence")
        st.error("Login is not set up for this app: its secrets have no [auth] section.")
        st.stop()

    if not st.user.is_logged_in:
        st.title("Investment Intelligence")
        st.button("Log in", on_click=st.login, type="primary")
        st.stop()

    email = (st.user.get("email") or "").lower()
    if not st.user.get("email_verified") or email not in _allowed_emails():
        st.error("This account is not allowed to view this app.")
        st.button("Log out", on_click=st.logout)
        st.stop()

    st.sidebar.button("Log out", on_click=st.logout)
