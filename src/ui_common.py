"""
Shared helpers for the Streamlit screens (src/streamlit_app.py and src/pages/*.py).
===================================================================================

WHY THIS FILE EXISTS
--------------------
Every screen needs the same four things: the page set-up, the navy/orange styling of
Screen 1, a row of links to the other screens, and the "who is using this?" check.
Putting them here means the five screens stay short and look identical. There is NO
business logic here; the screens call the same tested functions as src/app.py.

Streamlit runs each file in src/pages/ as its own page (multipage app). session_state
is shared between pages within one browser session, so the name typed on Home
(st.session_state["user"]) is available on every screen.
"""

import sys
from pathlib import Path

# Make "src" importable when a page runs (same trick as streamlit_app.py / app.py).
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import streamlit as st

# (page file relative to the entry script, label) - one per app.py menu option.
NAV = [
    ("streamlit_app.py", "🏠 Home"),
    ("pages/1_Ask_the_assistant.py", "💬 Ask"),
    ("pages/2_Weekly_restock.py", "🔄 Restock"),
    ("pages/3_Policy_questions.py", "📘 Policy"),
    ("pages/4_Review_and_approve.py", "✅ Review & approve"),
    ("pages/5_Stock_overview.py", "📦 Stock"),
]

# Page-level styling: same colours as Screen 1 (navy #1B2A5B, orange #F5A100).
CSS = """
<style>
  header[data-testid="stHeader"], footer { visibility: hidden; height: 0; }
  .block-container { padding-top: 1.2rem; padding-bottom: 1rem; max-width: 1100px; }
  [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none; }
  .page-banner { background: #1B2A5B; color: #FFFFFF; border-radius: 16px;
                 padding: 22px 30px; margin: 10px 0 18px 0; }
  .page-banner .kicker { color: #F5A100; font-weight: 700; letter-spacing: 0.25em; font-size: 0.8rem; }
  .page-banner .ptitle { font-size: 2rem; font-weight: 800; margin: 4px 0; }
  .page-banner .psub   { color: #D6DCF0; font-size: 1rem; }
  .stButton > button[kind="primary"] { height: 3rem; border-radius: 12px; }
</style>
"""


def setup_page(title: str, icon: str, subtitle: str, need_user: bool = True) -> str | None:
    """
    Page set-up used at the top of every screen: config, CSS, nav row, banner.
    Returns the user's name, or stops the page with a pointer to Home if no name yet
    (the name is recorded on drafts and decisions, so those screens need one).
    """
    st.set_page_config(page_title=f"{title} - SME Procurement Assistant", page_icon=icon, layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    cols = st.columns(len(NAV))
    for col, (path, label) in zip(cols, NAV):
        col.page_link(path, label=label)
    # Only our own constant text goes into this HTML (never user input).
    st.markdown(
        f'<div class="page-banner"><div class="kicker">SME PROCUREMENT ASSISTANT</div>'
        f'<div class="ptitle">{icon} {title}</div><div class="psub">{subtitle}</div></div>',
        unsafe_allow_html=True,
    )
    user = st.session_state.get("user")
    if need_user and not user:
        st.warning("Please enter your name on the Home screen first. It is recorded on every decision.")
        st.page_link("streamlit_app.py", label="Go to Home", icon="🏠")
        st.stop()
    return user
