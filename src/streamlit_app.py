"""
SME Procurement Assistant - web UI (Streamlit), Screen 1: Home / Welcome.
========================================================================

WHY THIS FILE EXISTS
--------------------
src/app.py is the console version of the system. For the presentation the system has
to be usable in a browser (hosted on Render or Streamlit Community Cloud), so this file
is the web version of the same menu. Like app.py it adds NO business logic: every
figure on the screen comes from a function that already exists and is tested.

  Screen element                  Existing function it calls
  ------------------------------  ------------------------------------------------------
  "N of M items are low"          tools.procurement.get_low_stock() / get_inventory()
  "N drafts awaiting approval"    approvals.list_drafts()   (SQLite store, since F-26)
  "Your name" + Get Started       replaces app.py's ask("Your name") at start-up

The five feature cards are the five menu options of app.py (MENU). Each will become its
own screen, one at a time (Ask, Restock, Policy, Review & approve, Stock). This first
screen makes NO model call, so it needs no GEMINI_API_KEY and spends no quota.

LOOK AND FEEL
-------------
Layout and colours follow docs/ui-mockup.png (a style reference): a navy hero panel on
the left, a white panel with feature cards and a full-width "Get Started" button on the
right. The mockup's language picker is left out on purpose: we have no translations, and
a control that does nothing would mislead the user.

HOW STREAMLIT WORKS (for the viva)
----------------------------------
Streamlit re-runs this whole script from top to bottom every time the user clicks or
types. Anything that must survive a re-run (the user's name, which screen is open) is
kept in st.session_state, a dictionary that lives for one browser session.

Usage (PowerShell, from the repo root, venv active - the data paths are relative):
  py -m streamlit run src\\streamlit_app.py
Then open http://localhost:8501

Owner: Boonabaana Bronia (UI), built with Claude Code; backend by the whole team
Version: 0.1.0 (Screen 1: Home / Welcome)
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
import sys                                     # make "src" importable (see next comment)
from pathlib import Path                       # locate this file's folder

# `streamlit run` puts this file's folder (src/) on sys.path, but Streamlit's test
# runner (AppTest) does not. Adding it ourselves means `import approvals` works the
# same way in both cases, exactly like src/app.py.
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import streamlit as st                         # the web UI framework

import approvals                               # human approval gate (no AI): list_drafts()
from tools import procurement                  # deterministic tools (no AI): stock figures

# ---------------------------------------------------------------------------
# Page set-up: must be the first Streamlit call in the script
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SME Procurement Assistant",
    page_icon="📦",
    layout="wide",                             # use the full browser width, like the mockup
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# The five things the system can do = the five menu options of src/app.py.
# (icon, title, one-line description). Kept as data so Screen 1 and the tests
# use the same list, and later screens can reuse it for navigation.
# ---------------------------------------------------------------------------
FEATURES = [
    ("💬", "Ask the assistant",
     "Ask about stock, suppliers or history. The AI picks a tool; Python does the maths."),
    ("🔄", "Weekly restock",
     "Give a budget. A bounded agent plans what fits and drafts one requisition."),
    ("📘", "Policy questions",
     "Answers from the shop's own policy documents, with sources cited."),
    ("✅", "Review & approve drafts",
     "You edit, approve or reject every draft. The AI can never approve."),
    ("📦", "Stock overview",
     "See every item, its stock level and what is running low. No AI, instant."),
]

# ---------------------------------------------------------------------------
# Styling. Streamlit has no built-in "hero panel" or "feature card", so we draw
# them with HTML + CSS (st.markdown(..., unsafe_allow_html=True)). Only text we
# wrote ourselves (never the user's input) is put in this HTML, so a name like
# "<script>" cannot inject markup; the user's name is only shown via st.success.
# Colours: navy #1B2A5B and orange #F5A100, as in the mockup.
# ---------------------------------------------------------------------------
# Page files for the five features, in the same order as FEATURES.
PAGES = ["pages/1_Ask_the_assistant.py", "pages/2_Weekly_restock.py", "pages/3_Policy_questions.py",
         "pages/4_Review_and_approve.py", "pages/5_Stock_overview.py"]

CSS = """
<style>
  [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none; }
  /* Hide Streamlit's own top bar and footer so the page looks like an app, not a notebook. */
  header[data-testid="stHeader"], footer { visibility: hidden; height: 0; }
  .block-container { padding-top: 1.2rem; padding-bottom: 1rem; max-width: 1400px; }

  /* ---- Left: the navy hero panel ---- */
  .hero {
    position: relative; overflow: hidden;
    background: #1B2A5B; color: #FFFFFF;
    border-radius: 18px; padding: 44px 48px; min-height: 86vh;
  }
  .brand { display: flex; align-items: center; gap: 14px; }
  .brand-badge {
    width: 56px; height: 56px; border-radius: 14px; background: #F5A100;
    display: flex; align-items: center; justify-content: center; font-size: 28px;
  }
  .brand-name { font-size: 1.35rem; font-weight: 700; line-height: 1.1; }
  .brand-tag  { font-size: 0.95rem; color: #D6DCF0; }
  .kicker {
    margin-top: 22vh; color: #F5A100; font-weight: 700;
    letter-spacing: 0.32em; font-size: 0.85rem;
  }
  .headline { font-size: 3.4rem; font-weight: 800; line-height: 1.12; margin: 18px 0 22px 0; }
  .subline  { font-size: 1.15rem; color: #D6DCF0; max-width: 34rem; position: relative; z-index: 1; }
  /* Decorative shapes from the mockup: a ring with a dot, and a circle in the corner. */
  .ring {
    position: absolute; top: 120px; right: -90px; width: 300px; height: 300px;
    border-radius: 50%; border: 56px solid rgba(255, 255, 255, 0.10);
  }
  .dot {
    position: absolute; top: 190px; right: 150px; width: 22px; height: 22px;
    border-radius: 50%; background: #F5A100; box-shadow: 0 0 0 12px rgba(245, 161, 0, 0.18);
  }
  .corner {
    position: absolute; bottom: -140px; left: -120px; width: 340px; height: 340px;
    border-radius: 50%; background: #22357A;
  }

  /* ---- Right: welcome text, feature cards, status strip ---- */
  .welcome { color: #E07B00; font-weight: 700; margin-top: 8px; }
  .title   { color: #1B2A5B; font-size: 2.6rem; font-weight: 800; line-height: 1.15; margin: 6px 0 10px 0; }
  .intro   { color: #5B6478; font-size: 1.05rem; margin-bottom: 18px; }
  .card {
    display: flex; gap: 16px; align-items: center;
    background: #F7F9FC; border: 1px solid #E6EAF2; border-radius: 14px;
    padding: 14px 18px; margin-bottom: 10px;
  }
  .card-icon {
    min-width: 46px; height: 46px; border-radius: 12px; background: #EAF0FF;
    display: flex; align-items: center; justify-content: center; font-size: 22px;
  }
  .card-title { color: #1B2A5B; font-weight: 700; font-size: 1.05rem; }
  .card-text  { color: #5B6478; font-size: 0.93rem; }
  .status {
    background: #FFF6E5; border: 1px solid #F5D9A0; color: #6B4A00;
    border-radius: 12px; padding: 10px 16px; margin: 6px 0 14px 0; font-size: 0.95rem;
  }
  .status b { color: #1B2A5B; }

  /* Make the primary button (Get Started) large and navy, like the mockup. */
  .stButton > button[kind="primary"] { height: 3.4rem; border-radius: 12px; }
  /* Streamlit puts the button label inside a <p>, so the font is set on that element. */
  .stButton > button[kind="primary"] p { font-size: 1.15rem; font-weight: 700; }
</style>
"""


# ---------------------------------------------------------------------------
# Data for the status strip - read-only calls to existing, tested functions
# ---------------------------------------------------------------------------
def shop_status() -> dict:
    """
    Figures for the status strip: how many items are low, out of how many, and how
    many drafts are waiting for a human. Nothing is computed here except a count of
    drafts by status; the stock figures come straight from the tools.

    If the data cannot be read (e.g. a missing CSV), the home page must still open,
    so problems are returned as an "error" text instead of crashing the screen.
    """
    low = procurement.get_low_stock()                # {"count", "items"} or {"error"}
    inventory = procurement.get_inventory()          # {"count", "items", ...} or {"error"}
    if "error" in low or "error" in inventory:
        return {"error": low.get("error") or inventory.get("error")}
    try:
        # Same store that draft_requisition writes to and approvals.py reads (F-26).
        waiting = sum(1 for d in approvals.list_drafts() if d["status"] == procurement.DRAFT_STATUS)
    except Exception as exc:                         # the database is optional for the home page
        return {"low": low["count"], "total": inventory["count"], "waiting": None,
                "error": f"drafts unavailable ({type(exc).__name__})"}
    return {"low": low["count"], "total": inventory["count"], "waiting": waiting}


# ---------------------------------------------------------------------------
# Screen 1: Home / Welcome
# ---------------------------------------------------------------------------
def render_home() -> None:
    """Draw the two-column welcome screen and handle the Get Started button."""
    left, right = st.columns([1.05, 1], gap="large")

    # ---- Left column: the navy hero panel (pure presentation, no data) ----
    with left:
        st.markdown(
            """
            <div class="hero">
              <div class="ring"></div><div class="dot"></div><div class="corner"></div>
              <div class="brand">
                <div class="brand-badge">📦</div>
                <div>
                  <div class="brand-name">SME Procurement Assistant</div>
                  <div class="brand-tag">AI supports, never decides.</div>
                </div>
              </div>
              <div class="kicker">SMART STOCK. HUMAN DECISIONS.</div>
              <div class="headline">Keep your shop stocked, not stressed.</div>
              <div class="subline">Spot low stock, compare suppliers, plan a restock within
                your budget and approve every order yourself, all in one place.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ---- Right column: welcome text, the five feature cards, live status, name + button ----
    with right:
        st.markdown(
            '<div class="welcome">Welcome</div>'
            '<div class="title">Restocking, made simpler.</div>'
            '<div class="intro">Your stock book, suppliers and shop policies in one assistant. '
            'It prepares the paperwork; you make the decisions.</div>',
            unsafe_allow_html=True,
        )

        # One card per feature (= one per app.py menu option).
        cards = "".join(
            f'<div class="card"><div class="card-icon">{icon}</div>'
            f'<div><div class="card-title">{title}</div><div class="card-text">{text}</div></div></div>'
            for icon, title, text in FEATURES
        )
        st.markdown(cards, unsafe_allow_html=True)

        # Live, deterministic status (no AI): the same numbers the terminal tools give.
        status = shop_status()
        if "low" in status:
            waiting = ("drafts unavailable" if status["waiting"] is None
                       else f'<b>{status["waiting"]}</b> draft(s) awaiting your approval')
            st.markdown(
                f'<div class="status">📊 <b>{status["low"]}</b> of <b>{status["total"]}</b> items are '
                f'low on stock &nbsp;·&nbsp; {waiting}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.warning(f"Shop data could not be read: {status['error']}")

        # Who is using the system. Replaces app.py's ask("Your name"). There are no
        # roles or passwords (decision-001); the name is recorded on drafts and on
        # every approval decision as created_by / decided_by.
        name = st.text_input("Your name", key="name_input", max_chars=60,
                             placeholder="e.g. Shop Owner")
        if st.button("Get Started  →", type="primary", width="stretch"):
            if not name.strip():
                st.warning("Please type your name first. It is recorded on every decision you make.")
            else:
                st.session_state["user"] = name.strip()   # kept across re-runs for later screens

        if "user" in st.session_state:
            st.success(f"Logged in as {st.session_state['user']}. Choose a screen:")
            # Links to the five screens in src/pages/ (one per app.py menu option).
            for page, (icon, title, _) in zip(PAGES, FEATURES):
                st.page_link(page, label=title, icon=icon)


# ---------------------------------------------------------------------------
# Script body: Streamlit runs this top to bottom on every interaction
# ---------------------------------------------------------------------------
st.markdown(CSS, unsafe_allow_html=True)
render_home()
