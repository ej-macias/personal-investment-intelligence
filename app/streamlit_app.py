"""Entry point: `streamlit run app/streamlit_app.py`."""

import sys
from pathlib import Path

# Import invest_intel from this checkout, not from the copy pip installed at build time:
# Streamlit Cloud pulls new commits but only reinstalls when requirements.txt changes.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import streamlit as st  # noqa: E402

from auth import require_login  # noqa: E402

st.set_page_config(page_title="Investment Intelligence", page_icon="📈", layout="centered")

require_login()

navigation = st.navigation(
    [
        st.Page("views/overview.py", title="Portfolio overview", icon="📊", default=True),
        st.Page("views/explorer.py", title="Investment explorer", icon="🔎"),
        st.Page("views/analysis.py", title="Portfolio analysis", icon="📐"),
        st.Page("views/assistant.py", title="AI assistant", icon="💬"),
    ]
)
navigation.run()
