"""Entry point: `streamlit run app/streamlit_app.py`."""

import streamlit as st

from auth import require_login

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
