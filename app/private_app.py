"""Entry point for the private deployment: `streamlit run app/private_app.py`.

Streamlit Community Cloud allows one app per repository, branch and main file, so the private
app needs a file of its own. It runs the same app as streamlit_app.py; the secrets decide
which database it reads and that it requires a login.
"""

import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).with_name("streamlit_app.py")), run_name="__main__")
