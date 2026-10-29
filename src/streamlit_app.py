"""
SME Procurement Assistant - tenant-scoped Streamlit web prototype.
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

The four Stitch workspaces are Dashboard (AI copilot), Operations, Restock AI and
Approvals. Business records and policy files are always read with the selected tenant.

LOOK AND FEEL
-------------
The local Stitch exports are the UI reference: warm paper canvas, crisp stock-ledger
cards, teal operations, violet AI actions, meaningful icons and restrained motion.

HOW STREAMLIT WORKS (for the viva)
----------------------------------
Streamlit re-runs this whole script from top to bottom every time the user clicks or
types. Anything that must survive a re-run (the user's name, which screen is open) is
kept in st.session_state, a dictionary that lives for one browser session.

Usage (PowerShell, from the repo root, venv active - the data paths are relative):
  py -m streamlit run src\\streamlit_app.py
Then open http://localhost:8501

Owner: Boonabaana Bronia (UI), built with Claude Code; backend by the whole team
Version: 1.1.0 (tenant-aware prototype screens)
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
import html                                    # escape the entered business name in custom HTML
import csv                                     # read and write this business's CSV records
import io                                      # build downloadable CSV content in memory
import os                                      # atomic replace for CSV saves
import re                                      # safe IDs for policy documents
import sys                                     # make "src" importable (see next comment)
import tempfile                                # write CSVs before replacing the saved record
from datetime import date                      # purchase entry date defaults to today
from pathlib import Path                       # locate this file's folder

# `streamlit run` puts this file's folder (src/) on sys.path, but Streamlit's test
# runner (AppTest) does not. Adding it ourselves means `import approvals` works the
# same way in both cases, exactly like src/app.py.
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import streamlit as st                         # the web UI framework
import pandas as pd                             # editable stock ledger table

import approvals                               # human approval gate (no AI): list_drafts()
from tools import procurement                  # deterministic tools (no AI): stock figures
from tenant_context import (business_tenant_id, initialize_business_data,
                            tenant_data_dir, tenant_policy_dir, CSV_FILES)
from tool_agent import run_agent
from restock_agent import run_restock
from rag import index as policy_index
from rag.policy_qa import answer_policy_question
from conversation_context import (COPILOT_RECENT_TURNS, COPILOT_SUMMARY_LIMIT,
                                  build_copilot_context, compact_copilot_turn)

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
# The four Stitch bottom-navigation destinations; the active shop's AI copilot
# is the Dashboard screen, matching the exported screen and the intended flow.
# ---------------------------------------------------------------------------
WORKSPACE_PAGES = ["Dashboard", "Operations", "Restock AI", "Approvals"]
NAV_ICONS = {"Dashboard": "💬", "Operations": "🧰", "Restock AI": "🌱", "Approvals": "🛡️"}

# Inline SVG keeps icons sharp and available even when Google Fonts/CDNs are offline.
ICON_PATHS = {
    "store": '<path d="M3 10h18l-2-6H5l-2 6Z"/><path d="M5 10v10h14V10M9 20v-6h6v6"/><path d="M3 10a3 3 0 0 0 6 0 3 3 0 0 0 6 0 3 3 0 0 0 6 0"/>',
    "sparkles": '<path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z"/><path d="m19 14 .9 2.1L22 17l-2.1.9L19 20l-.9-2.1L16 17l2.1-.9L19 14ZM5 3l.7 1.7L7.5 5.5l-1.8.8L5 8l-.7-1.7-1.8-.8 1.8-.8L5 3Z"/>',
    "inventory": '<path d="M4 7h16M4 12h16M4 17h16"/><path d="M7 4v3m5-3v3m5-3v3M7 12v5m5-5v5m5-5v5"/>',
    "receipt": '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z"/><path d="M9 8h6M9 12h6M9 16h3"/>',
    "restock": '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.6 9a7 7 0 0 1 11.5-2L20 12M4 12l2.9 5a7 7 0 0 0 11.5-2"/>',
    "check": '<path d="M12 3 20 6v5c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6l8-3Z"/><path d="m8.5 12 2.3 2.3 4.8-5"/>',
    "policy": '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 12h7M9 16h7"/>',
}


def _icon_svg(name: str, size: int = 22) -> str:
    """Return a small fixed-path icon (never user-provided markup)."""
    path = ICON_PATHS.get(name, ICON_PATHS["sparkles"])
    return (f'<svg class="ui-icon" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'aria-hidden="true" focusable="false">{path}</svg>')


def _page_header(icon: str, title: str, subtitle: str, eyebrow: str = "YOUR BUSINESS") -> None:
    """Render a recognizable icon-led title instead of an unstyled text heading."""
    st.markdown(
        f'<div class="page-heading"><div class="page-icon {"ai" if icon == "sparkles" else ""}">'
        f'{_icon_svg(icon)}</div><div><div class="eyebrow">{html.escape(eyebrow)}</div>'
        f'<h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div></div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Stitch's exported HTML cannot run as a data-backed app by itself, so its
# ledger palette, card rhythm and page layouts are recreated with Streamlit.
# ---------------------------------------------------------------------------
CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600;700&display=swap');
  :root { color-scheme: light; --canvas:#fcf9f8; --paper:#fff; --soft:#f6f3f2; --ink:#1c1b1b; --muted:#52605d; --line:#d8e0de; --teal:#0f766e; --teal-dark:#005c55; --teal-soft:#e5f4f1; --violet:#712ae2; --violet-soft:#f0e9ff; --amber:#b45309; --amber-soft:#fff4d6; --red:#b42318; --red-soft:#fee9e7; }
  html, body, [data-testid="stAppViewContainer"] { background:var(--canvas); color:var(--ink); font-family:Inter,Arial,sans-serif; }
  header[data-testid="stHeader"], footer { visibility:hidden; height:0; }
  .block-container { max-width:1280px; padding:1.5rem 1.25rem 7rem; }
  h1,h2,h3 { color:var(--ink); letter-spacing:-.025em; }
  p, label, [data-testid="stMarkdownContainer"] { color:var(--muted); }
  .workspace-banner { display:flex; gap:.9rem; align-items:center; background:var(--paper); border:1px solid var(--line); border-left:5px solid var(--teal-dark); padding:.9rem 1.1rem; margin:.2rem 0 1.2rem; animation:rise-in .35s ease-out both; }
  .brand-mark,.page-icon { display:grid; place-items:center; width:46px; height:46px; flex:0 0 46px; color:var(--teal-dark); background:var(--teal-soft); border:1px solid #c4e6df; border-radius:4px; font-size:23px; }
  .workspace-kicker,.eyebrow { color:var(--teal-dark); font-weight:700; font-size:.75rem; letter-spacing:.1em; text-transform:uppercase; }
  .workspace-title { color:var(--ink); font-size:1.3rem; font-weight:700; line-height:1.2; margin-top:.15rem; }
  .workspace-meta { color:#66736f; font:500 .72rem 'JetBrains Mono',monospace; margin-top:.2rem; }
  .page-heading { display:flex; align-items:center; gap:.8rem; margin:.5rem 0 1rem; animation:rise-in .38s ease-out both; }
  .page-heading h1 { font-size:1.75rem; line-height:1.16; margin:.1rem 0; }
  .page-heading p { margin:0; font-size:.95rem; }
  .page-icon.ai { color:var(--violet); background:var(--violet-soft); border-color:#dfd1ff; }
  .page-icon.warning { color:var(--amber); background:var(--amber-soft); border-color:#f5dd9e; }
  .page-icon.success { color:var(--teal-dark); background:var(--teal-soft); }
  .ui-icon { width:24px; height:24px; display:block; fill:none; stroke:currentColor; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round; }
  .welcome-hero { display:flex; align-items:flex-start; gap:1rem; padding:1.4rem; background:#e8f3f1; border:1px solid #cbded9; border-left:5px solid var(--teal-dark); margin:.7rem 0 1rem; animation:rise-in .4s ease-out both; }
  .welcome-hero h1 { margin:.15rem 0 .35rem; font-size:clamp(1.6rem,3vw,2.1rem); }
  .welcome-hero p { max-width:48rem; margin:0; font-size:1rem; line-height:1.55; }
  .feature-strip { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.65rem; margin:.8rem 0 1rem; }
  .feature-tile { display:flex; gap:.65rem; align-items:center; min-height:72px; padding:.75rem; background:var(--paper); border:1px solid var(--line); border-radius:4px; transition:transform .18s ease,border-color .18s ease,background .18s ease; }
  .feature-tile:hover { transform:translateY(-2px); border-color:#9fcac2; background:#fbfffe; }
  .feature-icon { display:grid; place-items:center; width:38px; height:38px; flex:0 0 38px; color:var(--teal-dark); background:var(--teal-soft); border-radius:4px; }
  .feature-title { color:var(--ink); font-weight:650; font-size:.9rem; }
  .feature-copy { color:var(--muted); font-size:.79rem; line-height:1.35; }
  [data-testid="stMetric"] { background:var(--paper); border:1px solid var(--line); border-top:3px solid var(--teal); padding:.85rem 1rem; border-radius:4px; animation:rise-in .36s ease-out both; }
  [data-testid="stMetricLabel"] { color:var(--muted); font-size:.82rem; }
  [data-testid="stMetricValue"] { color:var(--teal-dark); font:700 1.55rem 'JetBrains Mono',monospace; }
  [data-testid="stDataFrame"],[data-testid="stTable"] { background:var(--paper); border:1px solid var(--line); border-radius:4px; }
  .ledger-card { background:var(--paper); border:1px solid var(--line); border-left:3px solid var(--teal); border-radius:4px; padding:.85rem 1rem; margin:.45rem 0; animation:rise-in .3s ease-out both; }
  .assistant-panel { background:var(--paper); border:1px solid #d9cdf5; border-top:3px solid var(--violet); padding:1rem 1.1rem; border-radius:4px; }
  .assistant-brand,.section-heading { display:flex; align-items:center; gap:.75rem; }
  .assistant-brand { align-items:flex-start; }
  .assistant-brand h2,.section-heading h2 { color:var(--ink); font-size:1.1rem; margin:.35rem 0 .2rem; }
  .assistant-brand p,.section-heading p { margin:0; line-height:1.45; font-size:.9rem; }
  .assistant-avatar { display:grid; place-items:center; width:42px; height:42px; flex:0 0 42px; color:var(--violet); background:var(--violet-soft); border:1px solid #dfd1ff; border-radius:4px; }
  .section-heading { margin:.8rem 0 .55rem; }
  .section-heading .feature-icon { width:40px; height:40px; flex-basis:40px; }
  .section-heading h2 { margin:.1rem 0 .15rem; }
  .stock-item-row { display:flex; align-items:center; gap:.8rem; }
  .stock-item-icon { display:grid; place-items:center; width:38px; height:38px; flex:0 0 38px; color:var(--teal-dark); background:var(--teal-soft); border-radius:4px; }
  .stock-item-info { display:flex; flex:1 1 auto; min-width:0; flex-direction:column; }
  .stock-item-info strong { color:var(--ink); font-size:.95rem; }
  .stock-quantity { display:flex; flex-direction:column; min-width:70px; color:var(--red); font:700 1.15rem 'JetBrains Mono',monospace; }
  .stock-quantity span,.stock-threshold { color:var(--muted); font:500 .75rem Inter,Arial,sans-serif; }
  .stock-threshold { min-width:100px; }
  .stock-badge { color:var(--amber); background:var(--amber-soft); border:1px solid #f0db9c; border-radius:4px; padding:.28rem .45rem; font-size:.68rem; letter-spacing:.04em; font-weight:700; }
  .empty-ledger { display:flex; flex-direction:column; align-items:center; text-align:center; gap:.35rem; padding:1.1rem; margin:.45rem 0 1rem; background:var(--paper); border:1px dashed #bdc9c6; border-radius:4px; }
  .empty-ledger strong { color:var(--ink); }
  .empty-ledger span { color:var(--muted); font-size:.87rem; }
  .empty-ledger-icon { display:grid; place-items:center; width:44px; height:44px; margin-bottom:.2rem; color:var(--teal-dark); background:var(--teal-soft); border-radius:4px; }
  .response-card { display:flex; align-items:center; gap:.45rem; color:var(--violet); padding:.6rem .75rem; border:1px solid #dfd1ff; border-left:3px solid var(--violet); background:#faf8ff; }
  .response-label { display:flex; align-items:center; gap:.4rem; font-size:.75rem; letter-spacing:.07em; font-weight:700; }
  .st-key-dashboard_metrics [data-testid="stHorizontalBlock"] { gap:.6rem; }
  .tag-ai { color:var(--violet); background:var(--violet-soft); border:1px solid #dfd1ff; border-radius:4px; padding:.2rem .5rem; font-size:.78rem; font-weight:650; }
  .stButton > button,.stFormSubmitButton > button { min-height:44px; border:1px solid #bdc9c6; border-radius:4px; font-weight:600; transition:transform .15s ease,background .15s ease,border-color .15s ease; }
  .stButton > button:hover,.stFormSubmitButton > button:hover { transform:translateY(-1px); border-color:var(--teal); }
  .stButton > button[kind="primary"],.stFormSubmitButton > button[kind="primary"],button[data-testid="stBaseButton-primary"] { background:var(--teal); border-color:var(--teal); color:white; }
  button[kind="primary"] *,button[data-testid*="primary"] * { color:white !important; }
  .st-key-ai_submit button[kind="primary"],.st-key-ai_submit button[data-testid*="primary"] { background:var(--violet); border-color:var(--violet); }
  input,textarea,[data-baseweb="select"] > div { background:var(--paper) !important; border-color:var(--line) !important; border-radius:4px !important; }
  [data-testid="stTabs"] button { min-height:44px; font-weight:600; }
  [data-testid="stAlert"] { border-radius:4px; border-left:4px solid var(--teal); }
  .st-key-workspace_nav { position:fixed!important; z-index:1000; left:0; right:0; bottom:0; margin:0 auto!important; padding:.45rem max(.75rem,env(safe-area-inset-right)) calc(.4rem + env(safe-area-inset-bottom)); background:rgba(252,249,248,.98); border-top:1px solid var(--line); box-shadow:0 -8px 24px rgba(28,27,27,.06); backdrop-filter:blur(12px); }
  .st-key-workspace_nav [data-testid="stHorizontalBlock"] { display:grid!important; grid-template-columns:repeat(4,minmax(0,1fr)); max-width:900px; margin:0 auto; gap:.55rem; }
  .st-key-workspace_nav [data-testid="stColumn"] { width:auto!important; min-width:0!important; flex:none!important; }
  .st-key-workspace_nav .stButton > button { min-height:52px; border:1px solid transparent; border-radius:14px; color:#52605d; font-size:.88rem; font-weight:650; background:transparent; transition:transform .18s cubic-bezier(.2,.8,.2,1),background .2s ease,color .2s ease,box-shadow .2s ease; }
  .st-key-workspace_nav .stButton > button:hover { transform:translateY(-3px); background:var(--soft); border-color:var(--line); color:var(--ink); }
  .st-key-workspace_nav .stButton > button:active { transform:scale(.94); animation:nav-tap .24s ease-out; }
  .st-key-workspace_nav .stButton > button[kind="primary"] { color:#fff; background:var(--teal); box-shadow:0 5px 14px rgba(15,118,110,.25); }
  .st-key-nav_dashboard button[kind="primary"] { background:#7c3aed!important; border-color:#7c3aed!important; box-shadow:0 5px 16px rgba(124,58,237,.28)!important; }
  .st-key-nav_operations button[kind="primary"] { background:#0f766e!important; border-color:#0f766e!important; }
  .st-key-nav_restock button[kind="primary"] { background:#d97706!important; border-color:#d97706!important; box-shadow:0 5px 16px rgba(217,119,6,.25)!important; }
  .st-key-nav_approvals button[kind="primary"] { background:#2563eb!important; border-color:#2563eb!important; box-shadow:0 5px 16px rgba(37,99,235,.25)!important; }
  .st-key-copilot_transcript [data-testid="stChatMessage"] { gap:.65rem; padding:.35rem 0; animation:rise-in .28s ease-out both; }
  .st-key-copilot_transcript [data-testid="stChatMessageContent"] { max-width: min(820px,92%); padding:.8rem 1rem; border:1px solid #e2d8f7; border-radius:5px 18px 18px 18px; background:#faf8ff; box-shadow:0 3px 10px rgba(54,35,91,.045); }
  .st-key-copilot_transcript [data-testid="stChatMessageContent"] p { color:var(--ink); line-height:1.6; }
  .copilot-greeting { display:flex; align-items:flex-start; gap:.65rem; max-width:min(820px,92%); margin:.55rem 0 1rem; padding:.8rem .95rem; color:var(--ink); line-height:1.55; background:#faf8ff; border:1px solid #e2d8f7; border-radius:5px 18px 18px 18px; box-shadow:0 3px 10px rgba(54,35,91,.045); animation:rise-in .28s ease-out both; }
  .copilot-greeting span { font-size:1.25rem; }
  .st-key-copilot_transcript [data-testid="stChatMessage"]:has([data-testid*="chatAvatarIcon-user"]) [data-testid="stChatMessageContent"] { border-color:#c6e5df; border-radius:18px 5px 18px 18px; background:#edf8f5; }
  .st-key-copilot_transcript [data-testid="stChatMessage"] [data-testid*="chatAvatar"] { font-size:1.25rem; }
  div[data-testid="stChatInput"] { bottom:calc(78px + env(safe-area-inset-bottom))!important; z-index:1000 !important; }
  /* The transcript is a real scroll box: it fills the space above the chat-input
   * dock and scrolls, so a long conversation never pushes the latest answer
   * under the input. The bottom padding keeps the newest message clear of the
   * dock, and the JS below scrolls to the bottom after every turn. */
  .st-key-copilot_transcript { padding-bottom:calc(130px + env(safe-area-inset-bottom))!important; overflow-y:auto; max-height:calc(100vh - 240px); scroll-behavior:smooth; position:relative; }
  .st-key-copilot_transcript [data-testid="stChatMessage"]:last-child { scroll-margin-bottom:160px; }
  .st-key-copilot_transcript [data-testid="stVerticalPortal"] { z-index:50; }
  .st-key-copilot_transcript [data-testid="stDownloadButton"] button { min-height:38px; border-radius:12px; border-color:#c9b7ed; color:#5b21b6; background:#fff; }
  @keyframes nav-tap { 0% { transform:scale(.94); } 70% { transform:scale(1.04); } 100% { transform:scale(1); } }
  @keyframes rise-in { from { opacity:0; transform:translateY(7px); } to { opacity:1; transform:translateY(0); } }
  @keyframes soft-pulse { 50% { opacity:.45; } }
  .live-dot { display:inline-block; width:8px; height:8px; border-radius:50%; background:#16a34a; margin-right:.35rem; animation:soft-pulse 1.8s ease-in-out infinite; }
  @media (min-width:900px) { .block-container { padding:1.5rem 2rem 6rem; } .st-key-workspace_nav { left:max(calc((100vw - 1280px) / 2),0px); right:max(calc((100vw - 1280px) / 2),0px); border:1px solid var(--line); border-bottom:0; border-radius:16px 16px 0 0; } }
  @media (max-width:640px) { .block-container { padding:.8rem .75rem 6rem; } .feature-strip { grid-template-columns:1fr; } .workspace-title { font-size:1.1rem; } .page-heading h1 { font-size:1.45rem; } .st-key-workspace_nav { padding-left:.4rem; padding-right:.4rem; } .st-key-workspace_nav [data-testid="stHorizontalBlock"] { gap:.08rem; } .st-key-workspace_nav .stButton > button { min-height:50px; padding:.2rem .08rem; font-size:.69rem; border-radius:11px; } .st-key-copilot_transcript [data-testid="stChatMessageContent"] { max-width:100%; padding:.68rem .78rem; } .st-key-dashboard_metrics [data-testid="stHorizontalBlock"] { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); } .stock-threshold { display:none; } .stock-item-row { gap:.45rem; } }
  @media (prefers-reduced-motion:reduce) { *,*::before,*::after { animation-duration:.01ms !important; animation-iteration-count:1 !important; scroll-behavior:auto !important; transition-duration:.01ms !important; } }
</style>
"""


# ---------------------------------------------------------------------------
# Data for the status strip - read-only calls to existing, tested functions
# ---------------------------------------------------------------------------
def shop_status(tenant_id: str = "default-shop") -> dict:
    """
    Figures for the status strip: how many items are low, out of how many, and how
    many drafts are waiting for a human. Nothing is computed here except a count of
    drafts by status; the stock figures come straight from the tools.

    If the data cannot be read (e.g. a missing CSV), the home page must still open,
    so problems are returned as an "error" text instead of crashing the screen.
    """
    low = procurement.get_low_stock(tenant_id=tenant_id)  # {"count", "items"} or {"error"}
    inventory = procurement.get_inventory(tenant_id=tenant_id)  # {"count", "items", ...}
    if "error" in low or "error" in inventory:
        return {"error": low.get("error") or inventory.get("error")}
    try:
        # Same store that draft_requisition writes to and approvals.py reads (F-26).
        waiting = sum(1 for d in approvals.list_drafts(
            tenant_id=tenant_id, user_id="default-user")
            if d["status"] == procurement.DRAFT_STATUS)
    except Exception as exc:                         # the database is optional for the home page
        return {"low": low["count"], "total": inventory["count"], "waiting": None,
                "error": f"drafts unavailable ({type(exc).__name__})"}
    return {"low": low["count"], "total": inventory["count"], "waiting": waiting}


# ---------------------------------------------------------------------------
# Screen 1: Home / Welcome
# ---------------------------------------------------------------------------
def render_home() -> None:
    """Open a business's private workspace without presenting a login screen."""
    if "tenant_id" in st.session_state:
        render_business_home()
        return
    st.markdown(
        f'<div class="welcome-hero"><div class="page-icon success">{_icon_svg("store", 27)}</div>'
        '<div><div class="workspace-kicker">SME PROCUREMENT WORKSPACE</div>'
        '<h1>Your shop, your stock book.</h1>'
        '<p>Track stock, sales, supplier purchases and reorder decisions in a clear digital ledger. '
        'Each business opens its own private workspace.</p></div></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="feature-strip">'
        f'<div class="feature-tile"><div class="feature-icon">{_icon_svg("inventory", 20)}</div><div><div class="feature-title">Stock & counter sales</div><div class="feature-copy">Add products and record daily movements.</div></div></div>'
        f'<div class="feature-tile"><div class="feature-icon">{_icon_svg("restock", 20)}</div><div><div class="feature-title">Plan a restock</div><div class="feature-copy">Use your own records and budget.</div></div></div>'
        f'<div class="feature-tile"><div class="feature-icon">{_icon_svg("check", 20)}</div><div><div class="feature-title">You stay in control</div><div class="feature-copy">A person reviews every reorder draft.</div></div></div>'
        '</div>', unsafe_allow_html=True)
    with st.form("open_business_workspace"):
        business = st.text_input("Business name", key="business_name_input", max_chars=80,
                                 placeholder="e.g. Aminah's Stationery")
        st.caption("No account or login. Each name opens the same business workspace and tenant ID.")
        submitted = st.form_submit_button("Open business workspace", type="primary", width="stretch")
    if submitted:
        if not business.strip():
            st.warning("Enter your business name to continue.")
        else:
            try:
                tenant_id = business_tenant_id(business)
                initialize_business_data(tenant_id)
                st.session_state["tenant_id"] = tenant_id
                st.session_state["business_name"] = " ".join(business.split())
                st.session_state["workspace_page"] = "Dashboard"
                st.rerun()
            except (ValueError, OSError) as exc:
                st.error(f"Could not open this business workspace: {exc}")


def render_business_home() -> None:
    """Show the four Stitch workspaces and route every action through one tenant."""
    tenant_id = st.session_state["tenant_id"]
    business_name = st.session_state["business_name"]
    # Callbacks and page actions queue navigation here. Apply it before rendering
    # the bottom bar so saved drafts open Approvals on the next run.
    next_page = st.session_state.pop("_next_workspace_page", None)
    if next_page in WORKSPACE_PAGES:
        st.session_state["workspace_page"] = next_page
    with st.container(key="workspace_nav"):
        nav_cols = st.columns(4)
        page = st.session_state.get("workspace_page", "Dashboard")
        for index, destination in enumerate(WORKSPACE_PAGES):
            slug = destination.lower().replace(" ", "_")
            with nav_cols[index]:
                with st.container(key=f"nav_{slug}"):
                    st.button(f"{NAV_ICONS[destination]}  {destination}",
                              key=f"workspace_nav_{slug}", width="stretch",
                              type="primary" if page == destination else "secondary",
                              on_click=_set_workspace_page, args=(destination,))
    safe_name = html.escape(business_name)
    header, switch = st.columns([6, 1])
    with header:
        st.markdown(f'<div class="workspace-banner"><div class="brand-mark">{_icon_svg("store")}</div>'
                    f'<div><div class="workspace-kicker"><span class="live-dot"></span>ACTIVE BUSINESS WORKSPACE</div>'
                    f'<div class="workspace-title">{safe_name}</div>'
                    f'<div class="workspace-meta">TENANT · {html.escape(tenant_id)}</div></div></div>',
                    unsafe_allow_html=True)
    with switch:
        st.button("↔ Switch shop", key="switch_business", help="Open another business ledger",
                  on_click=_switch_business)
    if page == "Restock AI":
        render_restock_page(tenant_id, business_name)
    elif page == "Operations":
        render_operations_page(tenant_id)
    elif page == "Approvals":
        render_approvals_page(tenant_id, business_name)
    else:
        render_dashboard(tenant_id, business_name)


def _switch_business() -> None:
    """Clear this browser's selected shop before Streamlit creates its nav widget."""
    for key in ("tenant_id", "business_name", "business_name_input", "workspace_page",
                "_next_workspace_page"):
        st.session_state.pop(key, None)


def _set_workspace_page(destination: str) -> None:
    """Switch workspace from an animated button in the fixed bottom navigation."""
    if destination in WORKSPACE_PAGES:
        st.session_state["workspace_page"] = destination


def render_dashboard(tenant_id: str, business_name: str) -> None:
    """Make the Copilot the dashboard, with the shop's real work one tap away."""
    _page_header("sparkles", "AI Copilot", f"Good day, {business_name}. Ask about this shop's stock, suppliers, purchases or policies.", "DASHBOARD · BUSINESS ASSISTANT")
    status = shop_status(tenant_id)
    if "error" in status:
        st.warning(f"Business records could not be read: {status['error']}")
    else:
        sales = _read_tenant_rows(tenant_id, "sales.csv")[1]
        today_sales = [row for row in sales if row.get("date") == date.today().isoformat()]
        with st.container(key="dashboard_metrics"):
            metrics = st.columns(4)
            metrics[0].metric("📦 Products", status["total"])
            metrics[1].metric("⚠️ Need restock", status["low"])
            metrics[2].metric("🧾 Sales today", len(today_sales))
            metrics[3].metric("✅ Drafts awaiting you", status["waiting"] if status["waiting"] is not None else "—")
    st.markdown('<div class="section-heading"><div class="feature-icon">'
                f'{_icon_svg("restock", 20)}</div><div><h2>Today\'s restock assessment</h2>'
                '<p>Items at or below this shop\'s reorder point.</p></div></div>', unsafe_allow_html=True)
    low = procurement.get_low_stock(tenant_id=tenant_id)
    if "error" in low:
        st.warning(low["error"])
    elif low["items"]:
        for item in low["items"][:4]:
            st.markdown(
                '<div class="ledger-card stock-item-row">'
                f'<div class="stock-item-icon">{_icon_svg("inventory", 19)}</div>'
                f'<div class="stock-item-info"><strong>{html.escape(str(item["item_name"]))}</strong>'
                f'<span class="workspace-meta">{html.escape(str(item["item_id"]))}</span></div>'
                f'<div class="stock-quantity"><strong>{item["current_stock"]}</strong><span>in stock</span></div>'
                f'<div class="stock-threshold">Reorder at <b>{item["reorder_point"]}</b></div>'
                '<span class="stock-badge">LOW STOCK</span></div>', unsafe_allow_html=True)
        if len(low["items"]) > 4:
            st.caption(f"And {len(low['items']) - 4} more low-stock items · see the full ledger in Operations.")
    else:
        st.markdown('<div class="empty-ledger"><div class="empty-ledger-icon">'
                    f'{_icon_svg("inventory", 26)}</div><strong>This stock ledger is ready for your items.</strong>'
                    '<span>Add products in Operations and the assistant will use this shop\'s records.</span></div>',
                    unsafe_allow_html=True)
    # The restock is planned through the chat (ask the copilot to "plan a restock
    # under UGX X") so every draft is a conversation the shop owner can see and
    # question - there is no separate control here.
    render_copilot_page(tenant_id, business_name)


def _run_business_question(question: str, tenant_id: str, business_name: str) -> None:
    """Run one question with the workspace scope passed as trusted context."""
    try:
        with st.status("Checking this business's records…", expanded=True) as status:
            if _is_restock_question(question):
                # The model stays in the middle: run_restock senses low stock in
                # code, then hands the model a [RESTOCK TASK] message with the
                # Section 7 contract (plan -> decide -> draft -> summary). The
                # The agent is the only restock planner; if the model is
                # unavailable, run_restock hands off without saving a draft.
                budget = _extract_restock_budget(question) or 300000
                result = run_restock(int(budget), user_name=business_name,
                                     shop_id=tenant_id, tenant_id=tenant_id)
                status.update(label="Restock review complete", state="complete", expanded=False)
            else:
                result = run_agent(question, user_name=business_name, tenant_id=tenant_id)
                status.update(label="Response ready", state="complete", expanded=False)
        st.write(result.get("final_text", "The assistant returned no response."))
    except Exception as exc:
        st.error(f"The assistant could not complete this request: {type(exc).__name__}: {exc}")


def render_operations_page(tenant_id: str) -> None:
    """Record stock, counter sales, supplier quotes and received purchases."""
    _page_header("inventory", "Operations", "Keep this shop's inventory, counter sales and supplier activity together.", "BUSINESS LEDGER")
    inventory = procurement.get_inventory(tenant_id=tenant_id)
    low = procurement.get_low_stock(tenant_id=tenant_id)
    sales_rows = _read_tenant_rows(tenant_id, "sales.csv")[1]
    summaries = st.columns(3)
    summaries[0].metric("SKUs tracked", inventory.get("count", 0))
    summaries[1].metric("Below threshold", low.get("count", 0))
    summaries[2].metric("Sales recorded", len(sales_rows))
    stock_tab, sale_tab, purchase_tab, quote_tab, activity_tab = st.tabs(
        ["📦 Stock", "🧾 Sales", "📥 Purchases", "🏷️ Supplier quotes", "↻ Activity"])
    with stock_tab:
        render_stock_page(tenant_id)
    with sale_tab:
        render_sale_page(tenant_id)
    with purchase_tab:
        render_purchase_page(tenant_id)
    with quote_tab:
        render_quote_page(tenant_id)
    with activity_tab:
        render_activity_page(tenant_id)


def _tenant_csv(tenant_id: str, filename: str) -> Path:
    """Resolve one allow-listed CSV filename inside the validated tenant folder."""
    if filename not in CSV_FILES:
        raise ValueError("Unsupported business record file.")
    return tenant_data_dir(tenant_id) / filename


def _read_tenant_rows(tenant_id: str, filename: str) -> tuple[list[str], list[dict]]:
    """Read a scoped CSV and preserve its schema for a safe write-back."""
    path = _tenant_csv(tenant_id, filename)
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        return list(reader.fieldnames or []), list(reader)


def _write_tenant_rows(tenant_id: str, filename: str, headers: list[str], rows: list[dict]) -> None:
    """Replace a tenant CSV atomically so interrupted edits do not corrupt records."""
    path = _tenant_csv(tenant_id, filename)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _next_item_id(rows: list[dict]) -> str:
    """Generate the next simple ITM code without reusing an existing SKU."""
    used = {str(row.get("item_id", "")).strip().upper() for row in rows}
    number = 1
    while f"ITM{number:03d}" in used:
        number += 1
    return f"ITM{number:03d}"


def render_ask_page(tenant_id: str, business_name: str) -> None:
    """Run a tenant-scoped chat with compact, bounded context between questions."""
    st.markdown('<div class="assistant-panel"><div class="assistant-brand">'
                f'<div class="assistant-avatar">{_icon_svg("sparkles", 21)}</div>'
                '<div><span class="tag-ai">AI COPILOT</span><h2>How can I help your shop?</h2>'
                '<p>Answers use this business\'s saved stock, supplier quotes and purchase history. '
                'A person still approves every reorder.</p></div></div></div>', unsafe_allow_html=True)
    question_key = f"assistant_question_{tenant_id}"
    history_key = f"copilot_history_{tenant_id}"
    summary_key = f"copilot_summary_{tenant_id}"
    history = st.session_state.get(history_key, [])
    summary = st.session_state.get(summary_key, "")
    if summary:
        with st.expander("Earlier conversation · compacted context"):
            st.caption(summary)
    with st.container(key="copilot_transcript"):
        if not history:
            st.markdown('<div class="copilot-greeting"><span>🤖</span><div>Hi! Ask me what\'s running low, '
                        'compare supplier prices, or find a shop policy. When I use your records, '
                        'I can give you a CSV to download.</div></div>', unsafe_allow_html=True)
        for index, turn in enumerate(history):
            with st.chat_message("user", avatar="🙋"):
                st.write(turn["question"])
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(turn["answer"])
                if turn.get("result_rows"):
                    _render_csv_download(turn["result_rows"], tenant_id, index)
                if turn.get("tool_calls"):
                    _render_tool_evidence(turn["tool_calls"], index)
                if turn.get("latency_s") is not None:
                    st.caption(f"{turn.get('latency_s')} s · checked against this shop's records")
    if history or summary:
        st.button("Clear conversation", key=f"clear_conversation_{tenant_id}",
                  on_click=_clear_copilot_context, args=(tenant_id,))
    prompts = [
        ("⚠️  Which items are low on stock?", "Which items are low on stock?"),
        ("✧  Plan restock under UGX 300,000", "Plan a restock under UGX 300,000"),
        ("⇄  Compare supplier pen prices", "Compare supplier prices for pens"),
        ("▤  What did we buy last month?", "What did we buy last month?"),
    ]
    prompt_cols = st.columns(2)
    for index, (label, prompt) in enumerate(prompts):
        prompt_cols[index % 2].button(label, key=f"assistant_prompt_{tenant_id}_{index}", width="stretch",
                                      on_click=_queue_assistant_prompt, args=(prompt, tenant_id))
    queued_key = f"assistant_queued_question_{tenant_id}"
    queued_question = st.session_state.pop(queued_key, None)
    question = st.chat_input("Message your shop assistant…", key=question_key)
    question = queued_question or question
    if queued_question:
        st.caption(f"You asked: {queued_question}")
    if question:
        if not question.strip():
            st.warning("Enter a question first.")
        else:
            try:
                with st.status("Checking this business's records…", expanded=True) as status:
                    if _is_restock_question(question.strip()):
                        budget = _extract_restock_budget(question.strip()) or 300000
                        result = run_restock(int(budget), user_name=business_name,
                                             shop_id=tenant_id, tenant_id=tenant_id)
                        status.update(label="Restock review complete", state="complete", expanded=False)
                    else:
                        contextual_question = _copilot_context(summary, history, question.strip())
                        result = run_agent(contextual_question, user_name=business_name,
                                           tenant_id=tenant_id)
                        status.update(label="Response ready", state="complete", expanded=False)
                answer = result.get("final_text", "The assistant returned no response.")
                result_rows = _result_rows_for_export(result)
                _save_copilot_turn(tenant_id, question.strip(), answer,
                                   result.get("latency_s"), result_rows,
                                   result.get("tool_calls", []))
                with st.chat_message("user", avatar="🙋"):
                    st.write(question.strip())
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(answer)
                    if result_rows:
                        _render_csv_download(result_rows, tenant_id, len(history))
                    if result.get("tool_calls"):
                        _render_tool_evidence(result["tool_calls"], len(history))
                    loop = result.get("loop") or {}
                    run_id = result.get("run_id", loop.get("run_id", "n/a"))
                    latency = result.get("latency_s", loop.get("latency_s", 0))
                    st.caption(f"Run {run_id} · {latency} seconds")
                agent_state = result.get("state", {})
                created_ids = agent_state.get("drafts_created", result.get("drafts_created", []))
                if created_ids:
                    st.session_state[f"restock_handoff_{tenant_id}"] = {
                        "draft_id": created_ids[0],
                        "timeline": agent_state.get("timeline", []),
                        "plan": agent_state.get("plan"),
                        "ai_summary": answer,
                        "sources": ["current_stock.csv", "past_purchases.csv", "supplier_quotes.csv"],
                    }
                    st.session_state["_next_workspace_page"] = "Approvals"
                    st.rerun()
            except Exception as exc:
                st.error(f"The assistant could not complete this request: {type(exc).__name__}: {exc}")
    # Auto-scroll the transcript to the bottom after every turn so the newest
    # message is always visible above the chat input dock (see CSS in the head).
    st.markdown(
        '<script>(function(){'
        'var t=document.querySelector(".st-key-copilot_transcript");'
        'if(!t)return;'
        'function scroll(){t.scrollTop=t.scrollHeight;}'
        'scroll();'
        'var mo=new MutationObserver(function(){'
        'window.requestAnimationFrame(scroll);'
        '});'
        'mo.observe(t,{childList:true,subtree:true,characterData:true});'
        'window.__copilot_observer=mo;'
        '})();</script>', unsafe_allow_html=True)


def _queue_assistant_prompt(prompt: str, tenant_id: str) -> None:
    """Turn a suggested prompt into a normal chat message on the next run."""
    st.session_state[f"assistant_queued_question_{tenant_id}"] = prompt


# ---------------------------------------------------------------------------
# Restock routing for the chat copilot
# ---------------------------------------------------------------------------
# The chat is normally answered by run_agent (the tool agent). That loop calls
# the model, so when the free-tier quota is exhausted (HTTP 429) every
# restock question in chat fails. run_restock has a deterministic fallback
# (restock_agent._deterministic_fallback) that builds the plan and draft from
# the same Python tools with no model call, so restock questions are routed
# there when the wording is clearly a restock request.
_RESTOCK_PATTERNS = (
    "restock", "reorder", "re-order", "re order", "plan a restock",
    "plan restock", "buy", "order", "procure", "procurement", "stock up",
    "what should we buy", "what should we order", "weekly restock",
)


def _is_restock_question(question: str) -> bool:
    """Return True when the wording is clearly a restock request."""
    lower = question.lower()
    return any(pattern in lower for pattern in _RESTOCK_PATTERNS)


def _extract_restock_budget(question: str) -> int | None:
    """Pull a UGX budget out of a restock question, or None when none is given."""
    match = re.search(r"(\d{1,3}(?:[,\s]\d{3})*|\d{4,})\s*(?:ugx|shillings|shs)?",
                      question, re.IGNORECASE)
    if not match:
        return None
    digits = match.group(1).replace(",", "").replace(" ", "")
    try:
        return int(digits)
    except ValueError:
        return None


def _result_rows_for_export(result: dict) -> list[dict]:
    """Extract record-shaped tool results for a one-click CSV export."""
    rows = []
    for call in result.get("tool_calls", []):
        if call.get("status") != "ok":
            continue
        payload = call.get("result", {})
        if not isinstance(payload, dict):
            continue
        for key, value in payload.items():
            if isinstance(value, list) and value and all(isinstance(row, dict) for row in value):
                rows.extend({"Source": call.get("name", "result"), "Result group": key, **row}
                            for row in value)
    return rows


def _render_csv_download(rows: list[dict], tenant_id: str, turn_index: int,
                         key_prefix: str = "copilot_csv") -> None:
    """Render a compact download action for tenant-scoped record-shaped results."""
    if not rows:
        return
    csv_buffer = io.StringIO(newline="")
    fieldnames = list(dict.fromkeys(key for row in rows for key in row))
    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    st.download_button("⬇️  Download results as CSV", csv_buffer.getvalue(),
                       file_name=f"shop-results-{tenant_id[:8]}-{key_prefix}-{turn_index + 1}.csv",
                       mime="text/csv", key=f"{key_prefix}_{tenant_id}_{turn_index}",
                       width="content")


def _render_tool_evidence(tool_calls: list[dict], turn_index: int) -> None:
    """Show auditable tool results and source records without exposing model internals."""
    if not tool_calls:
        return
    with st.expander(f"Evidence checked · {len(tool_calls)} record lookup(s)"):
        for index, call in enumerate(tool_calls):
            tool_name = str(call.get("name", "record lookup"))
            status = str(call.get("status", "unknown"))
            with st.container(border=True):
                st.markdown(f"**{html.escape(tool_name.replace('_', ' ').title())}** · "
                            f"`{html.escape(status)}`")
                arguments = call.get("args")
                if arguments:
                    st.caption(f"Lookup: {arguments}")
                result = call.get("result")
                if result is not None:
                    st.json(result, expanded=index == 0 and turn_index < 2)


def _copilot_context(summary: str, history: list[dict], question: str) -> str:
    """Build a small, tenant-local prompt with only compact history and recent turns."""
    return build_copilot_context(summary, history, question)


def _save_copilot_turn(tenant_id: str, question: str, answer: str,
                       latency_s: float | None = None,
                       result_rows: list[dict] | None = None,
                       tool_calls: list[dict] | None = None) -> None:
    """Keep four recent turns and compact older exchanges without another model call."""
    history_key = f"copilot_history_{tenant_id}"
    summary_key = f"copilot_summary_{tenant_id}"
    history = list(st.session_state.get(history_key, []))
    summary = st.session_state.get(summary_key, "")
    summary, history = compact_copilot_turn(summary, history, question, answer, latency_s)
    if history:
        if result_rows:
            history[-1]["result_rows"] = result_rows
        if tool_calls:
            history[-1]["tool_calls"] = tool_calls
    st.session_state[history_key] = history
    st.session_state[summary_key] = summary.strip()


def _clear_copilot_context(tenant_id: str) -> None:
    """Clear only the active business's conversational context before rerender."""
    st.session_state.pop(f"copilot_history_{tenant_id}", None)
    st.session_state.pop(f"copilot_summary_{tenant_id}", None)
    st.session_state.pop(f"assistant_question_{tenant_id}", None)
    st.session_state.pop(f"assistant_queued_question_{tenant_id}", None)


def render_restock_page(tenant_id: str, business_name: str) -> None:
    """Ask the AI agent to prepare a tenant-scoped draft for human review."""
    _page_header("restock", "Restock AI", "The AI weighs this shop's stock, purchase history, budget and supplier choices.", "AI-PLANNED · HUMAN-APPROVED")
    with st.form(f"restock_business_{tenant_id}"):
        budget = st.number_input("Procurement cash budget (UGX)", min_value=1,
                                 step=10000, value=300000, key=f"restock_budget_{tenant_id}")
        st.caption("The AI chooses priorities and supplier trade-offs from your records. Python checks every figure and the budget; you approve or reject the saved draft.")
        submitted = st.form_submit_button("Ask AI to plan restock", type="primary", width="stretch")
    if not submitted:
        return
    inventory = procurement.get_inventory(tenant_id=tenant_id)
    if "error" in inventory or not inventory.get("items"):
        st.info("Add this shop's stock items in Operations → Stock before planning a reorder.")
        return
    try:
        with st.status("AI is reviewing stock, purchase history and supplier quotes…", expanded=True) as status:
            result = run_restock(int(budget), user_name=business_name,
                                 shop_id=tenant_id, tenant_id=tenant_id)
            status.update(label="AI restock review complete", state="complete", expanded=False)
        state = result.get("state", {})
        plan = state.get("plan")
        if plan and plan.get("included"):
            st.markdown("### Recommended reorder")
            st.dataframe(pd.DataFrame([{
                "Item": line["item_name"], "Quantity": line["recommended_qty"],
                "Supplier": line.get("selected_supplier", "—"),
                "Estimated cost (UGX)": line.get("cost_ugx", line.get("total_cost_ugx", 0)),
            } for line in plan["included"]]), width="stretch", hide_index=True)
            st.metric("Planned spend", f"UGX {plan.get('planned_total_ugx', 0):,}")
        if plan and plan.get("deferred"):
            st.warning(f"{len(plan['deferred'])} item(s) do not fit this budget and were deferred.")
        if plan and plan.get("needs_human"):
            st.info(f"{len(plan['needs_human'])} item(s) need a quote or purchase history before they can be priced.")
        st.write(result.get("final_text", result.get("outcome", "No summary returned.")))
        if result.get("outcome") == "HANDOFF_MODEL_UNAVAILABLE":
            st.warning("No draft was saved because the AI could not complete its review. Your records are unchanged; retry when the AI service is available.")
        created = state.get("drafts_created", [])
        if created:
            st.success(f"Draft {created[0]} is saved to this business's approvals queue.")
            st.info("This is a draft only. Review it under Approvals before making any purchase.")
            st.session_state[f"restock_handoff_{tenant_id}"] = {
                "draft_id": created[0], "timeline": state.get("timeline", []),
                "plan": plan, "ai_summary": result.get("final_text", ""),
                "sources": ["current_stock.csv", "past_purchases.csv", "supplier_quotes.csv"],
            }
            st.session_state["_next_workspace_page"] = "Approvals"
            st.rerun()
    except Exception as exc:
        st.error(f"Restock planning failed: {type(exc).__name__}: {exc}")


def render_stock_page(tenant_id: str) -> None:
    """Add, update or remove items in this business's own inventory ledger."""
    st.markdown('<div class="section-heading"><div class="feature-icon">'
                f'{_icon_svg("inventory", 20)}</div><div><h2>Stock editor</h2>'
                '<p>Change quantities, reorder points or cost; every edit stays in this shop.</p></div></div>',
                unsafe_allow_html=True)
    headers, rows = _read_tenant_rows(tenant_id, "current_stock.csv")
    st.caption(f"{len(rows)} products in this business. Add new items here; edit or remove rows in the ledger, then save.")
    with st.expander("＋ Add stock item", expanded=not rows):
        with st.form(f"add_stock_item_{tenant_id}"):
            item_name = st.text_input("Product name", placeholder="e.g. Exercise books", key=f"new_stock_name_{tenant_id}")
            category = st.text_input("Category", placeholder="e.g. Stationery", key=f"new_stock_category_{tenant_id}")
            values = st.columns(3)
            current = values[0].number_input("Current stock", min_value=0, step=1, key=f"new_stock_current_{tenant_id}")
            reorder = values[1].number_input("Reorder point", min_value=0, step=1, key=f"new_stock_reorder_{tenant_id}")
            unit_cost = values[2].number_input("Unit cost (UGX)", min_value=0, step=100, key=f"new_stock_cost_{tenant_id}")
            st.caption(f"Next item ID: {_next_item_id(rows)}")
            add_item = st.form_submit_button("Add item to this business", type="primary")
        if add_item:
            if not item_name.strip() or not category.strip():
                st.error("Enter both a product name and category.")
            else:
                rows.append({"item_id": _next_item_id(rows), "item_name": item_name.strip(),
                             "category": category.strip(), "current_stock": int(current),
                             "reorder_point": int(reorder), "unit_cost_ugx": int(unit_cost)})
                _write_tenant_rows(tenant_id, "current_stock.csv", headers, rows)
                st.success("Item added to this business's stock ledger.")
                st.rerun()
    if not rows:
        st.info("This is a new, empty business ledger. Add the products this shop carries; sample stock was not copied in.")
        return
    # One tactile product card per SKU mirrors the Stitch stock editor and keeps
    # edit/delete actions obvious on phone-size screens.
    for index, row in enumerate(rows):
        current = int(row.get("current_stock") or 0)
        reorder = int(row.get("reorder_point") or 0)
        with st.container(border=True):
            title_cols = st.columns([3, 1])
            title_cols[0].markdown(f"**{row['item_name']}**  ·  `{row['item_id']}`  ·  {row['category']}")
            if current <= reorder:
                title_cols[1].warning("Below threshold")
            else:
                title_cols[1].success("In stock")
            with st.form(f"edit_stock_item_{tenant_id}_{index}"):
                name = st.text_input("Product name", row["item_name"], key=f"stock_name_{tenant_id}_{index}")
                category = st.text_input("Category", row["category"], key=f"stock_category_{tenant_id}_{index}")
                values = st.columns(3)
                stock = values[0].number_input("Current stock", min_value=0, value=current,
                                               step=1, key=f"stock_current_{tenant_id}_{index}")
                threshold = values[1].number_input("Reorder point", min_value=0, value=reorder,
                                                   step=1, key=f"stock_reorder_{tenant_id}_{index}")
                cost = values[2].number_input("Unit cost (UGX)", min_value=0,
                                              value=int(row.get("unit_cost_ugx") or 0), step=100,
                                              key=f"stock_cost_{tenant_id}_{index}")
                actions = st.columns([1, 1, 3])
                save_item = actions[0].form_submit_button("Save item", type="primary")
                delete_item = actions[1].form_submit_button("Delete item")
            if delete_item:
                remaining = [item for position, item in enumerate(rows) if position != index]
                _write_tenant_rows(tenant_id, "current_stock.csv", headers, remaining)
                st.success(f"{row['item_name']} removed from this business's stock ledger.")
                st.rerun()
            if save_item:
                if not name.strip() or not category.strip():
                    st.error("Product name and category are required.")
                else:
                    rows[index] = {**row, "item_name": name.strip(), "category": category.strip(),
                                   "current_stock": int(stock), "reorder_point": int(threshold),
                                   "unit_cost_ugx": int(cost)}
                    _write_tenant_rows(tenant_id, "current_stock.csv", headers, rows)
                    st.success("Stock item updated in this business ledger.")
                    st.rerun()


def render_purchase_page(tenant_id: str) -> None:
    """Record a purchase in this business's history and increase its stock."""
    st.markdown('<div class="section-heading"><div class="feature-icon">'
                f'{_icon_svg("receipt", 20)}</div><div><h2>Record a purchase</h2>'
                '<p>Log goods received and update this shop\'s stock at the same time.</p></div></div>',
                unsafe_allow_html=True)
    stock_headers, stock_rows = _read_tenant_rows(tenant_id, "current_stock.csv")
    if not stock_rows:
        st.info("Add stock items in Stock before recording a purchase.")
        return
    item_by_id = {row["item_id"]: row for row in stock_rows}
    with st.form(f"purchase_entry_{tenant_id}"):
        item_id = st.selectbox("Item", list(item_by_id), format_func=lambda key: item_by_id[key]["item_name"], key=f"purchase_item_{tenant_id}")
        qty = st.number_input("Quantity received", min_value=1, step=1, key=f"purchase_qty_{tenant_id}")
        price = st.number_input("Unit price (UGX)", min_value=0, step=100, key=f"purchase_price_{tenant_id}")
        supplier = st.text_input("Supplier", key=f"purchase_supplier_{tenant_id}")
        payment = st.selectbox("Payment status", ["Paid Cash / MoMo", "On Supplier Credit", "Partial Paid"], key=f"purchase_payment_{tenant_id}")
        purchased_on = st.date_input("Purchase date", value=date.today(), key=f"purchase_date_{tenant_id}")
        submitted = st.form_submit_button("Save purchase", type="primary")
    if submitted:
        try:
            history_headers, history_rows = _read_tenant_rows(tenant_id, "past_purchases.csv")
            history_rows.append({"date": purchased_on.isoformat(), "item_id": item_id,
                                 "quantity_purchased": int(qty),
                                 "historical_unit_price_ugx": int(price),
                                 "supplier_name": supplier.strip(), "payment_status": payment})
            item_by_id[item_id]["current_stock"] = str(int(item_by_id[item_id]["current_stock"]) + int(qty))
            _write_tenant_rows(tenant_id, "past_purchases.csv", history_headers, history_rows)
            _write_tenant_rows(tenant_id, "current_stock.csv", stock_headers, stock_rows)
            st.success("Purchase and updated stock saved for this business.")
        except Exception as exc:
            st.error(f"Purchase could not be saved: {type(exc).__name__}: {exc}")


def render_sale_page(tenant_id: str) -> None:
    """Record a counter sale in this business and reduce its stock count."""
    st.markdown('<div class="section-heading"><div class="feature-icon">'
                f'{_icon_svg("receipt", 20)}</div><div><h2>Record a sale</h2>'
                '<p>Record what left the shelf; the stock balance is updated automatically.</p></div></div>',
                unsafe_allow_html=True)
    stock_headers, stock_rows = _read_tenant_rows(tenant_id, "current_stock.csv")
    available = {row["item_id"]: row for row in stock_rows}
    if not available:
        st.info("Add stock items before recording a sale.")
        return
    with st.form(f"sale_entry_{tenant_id}"):
        item_id = st.selectbox("Item sold", list(available),
                               format_func=lambda key: available[key]["item_name"], key=f"sale_item_{tenant_id}")
        qty = st.number_input("Quantity sold", min_value=1, step=1, key=f"sale_qty_{tenant_id}")
        price = st.number_input("Unit sale price (UGX)", min_value=0, step=100, key=f"sale_price_{tenant_id}")
        payment = st.selectbox("Payment method", ["Cash", "MTN MoMo", "Airtel Money"], key=f"sale_payment_{tenant_id}")
        sold_on = st.date_input("Sale date", value=date.today(), key=f"sale_date_{tenant_id}")
        submitted = st.form_submit_button("Save sale & update stock", type="primary")
    if submitted:
        try:
            current = int(available[item_id]["current_stock"])
            if int(qty) > current:
                st.error(f"Only {current} units are in stock.")
                return
            sales_headers, sales_rows = _read_tenant_rows(tenant_id, "sales.csv")
            sales_rows.append({"date": sold_on.isoformat(), "item_id": item_id,
                               "quantity_sold": int(qty), "unit_price_ugx": int(price),
                               "payment_method": payment})
            available[item_id]["current_stock"] = str(current - int(qty))
            _write_tenant_rows(tenant_id, "sales.csv", sales_headers, sales_rows)
            _write_tenant_rows(tenant_id, "current_stock.csv", stock_headers, stock_rows)
            st.success("Sale saved in this business workspace and stock updated.")
        except Exception as exc:
            st.error(f"Sale could not be saved: {type(exc).__name__}: {exc}")


def render_quote_page(tenant_id: str) -> None:
    """Record supplier quotes so restock calculations use this shop's price book."""
    _page_header("policy", "Supplier quotes", "Keep this shop's prices and lead times ready for the next reorder.", "SUPPLIER LEDGER")
    _, stock_rows = _read_tenant_rows(tenant_id, "current_stock.csv")
    if not stock_rows:
        st.info("Add products in Stock before saving supplier quotes.")
        return
    names = {row["item_id"]: row["item_name"] for row in stock_rows}
    with st.form(f"supplier_quote_entry_{tenant_id}"):
        item_id = st.selectbox("Product", list(names), format_func=lambda key: names[key], key=f"quote_item_{tenant_id}")
        supplier = st.text_input("Supplier name", key=f"quote_supplier_{tenant_id}")
        fields = st.columns(3)
        price = fields[0].number_input("Unit price (UGX)", min_value=1, step=100, key=f"quote_price_{tenant_id}")
        minimum = fields[1].number_input("Minimum order quantity", min_value=1, step=1, key=f"quote_minimum_{tenant_id}")
        lead = fields[2].number_input("Lead time (days)", min_value=0, step=1, key=f"quote_lead_{tenant_id}")
        submitted = st.form_submit_button("Save supplier quote", type="primary")
    if submitted:
        if not supplier.strip():
            st.error("Enter the supplier's name.")
            return
        headers, quotes = _read_tenant_rows(tenant_id, "supplier_quotes.csv")
        quotes.append({"supplier_name": supplier.strip(), "item_id": item_id,
                       "offered_unit_price_ugx": int(price), "min_order_qty": int(minimum),
                       "lead_time_days": int(lead)})
        _write_tenant_rows(tenant_id, "supplier_quotes.csv", headers, quotes)
        st.success("Quote saved to this business's price book.")
        st.rerun()


def render_activity_page(tenant_id: str) -> None:
    """Show this business's purchases, sales and reorder decisions together."""
    _page_header("receipt", "Business activity", "A running record of stock movements and reorder decisions.", "AUDIT HISTORY")
    purchases = _read_tenant_rows(tenant_id, "past_purchases.csv")[1]
    sales = _read_tenant_rows(tenant_id, "sales.csv")[1]
    drafts = approvals.list_drafts(tenant_id=tenant_id, user_id="default-user")
    st.markdown("#### Reorder drafts and decisions")
    if drafts:
        st.dataframe(pd.DataFrame([{"Draft ID": d["draft_id"], "Status": d["status"],
                                   "Created": d["created_at"], "Lines": d["lines"],
                                   "Estimated (UGX)": d["estimated_budget_ugx"]}
                                  for d in drafts]), width="stretch", hide_index=True)
    else:
        st.info("No reorder drafts have been recorded for this business.")
    left, right = st.columns(2)
    with left:
        st.markdown("#### Purchases received")
        st.dataframe(pd.DataFrame(purchases), width="stretch", hide_index=True)
    with right:
        st.markdown("#### Counter sales")
        st.dataframe(pd.DataFrame(sales), width="stretch", hide_index=True)


def render_copilot_page(tenant_id: str, business_name: str) -> None:
    """Keep business questions and the shop's editable policies inside Dashboard."""
    tabs = st.tabs(["💬 Ask Copilot", "📘 Policy Q&A", "📄 View & edit policies"])
    with tabs[0]:
        render_ask_page(tenant_id, business_name)
    with tabs[1]:
        st.markdown('<div class="section-heading"><div class="feature-icon">'
                    f'{_icon_svg("policy", 20)}</div><div><h2>Ask this shop\'s policy</h2>'
                    '<p>Get an answer grounded in this business\'s saved policy documents.</p></div></div>',
                    unsafe_allow_html=True)
        with st.form(f"tenant_policy_question_{tenant_id}"):
            question = st.text_input("Policy question", key=f"policy_question_{tenant_id}",
                                     placeholder="What approvals are needed for a large order?")
            submitted = st.form_submit_button("Ask policy", type="primary")
        if submitted:
            if not question.strip():
                st.warning("Type a question about a policy first.")
            else:
                try:
                    answer = answer_policy_question(question.strip(), tenant_id=tenant_id)
                    st.markdown(answer["answer"])
                    if answer["sources"]:
                        with st.expander("Sources used"):
                            for source in answer["sources"]:
                                st.write(f"[{source['label']}] {source['title']} · {source['section']}")
                    st.caption("Grounded in policy sources for this business only.")
                except Exception as exc:
                    st.error(f"Policy answer unavailable: {type(exc).__name__}: {exc}")
    with tabs[2]:
        render_policy_editor(tenant_id)


def render_policy_editor(tenant_id: str) -> None:
    """Show and save tenant-owned policy documents without changing shared originals."""
    policy_dir = tenant_policy_dir(tenant_id)
    documents = sorted(policy_dir.glob("*.md"))
    st.markdown("#### Policies for this business")
    st.caption("Each business gets its own starter policy copies; edits do not affect other shops.")
    if documents:
        selected = st.selectbox("Policy document", [path.name for path in documents],
                                key=f"policy_document_{tenant_id}")
        selected_path = policy_dir / selected
        policy_text = selected_path.read_text(encoding="utf-8")
        with st.form(f"edit_tenant_policy_{tenant_id}"):
            edited = st.text_area("Policy text (Markdown)", value=policy_text,
                                  height=360, key=f"policy_text_{tenant_id}_{selected}")
            saved = st.form_submit_button("Save this business's policy", type="primary")
        if saved:
            if not edited.strip():
                st.error("A policy document cannot be empty.")
            else:
                selected_path.write_text(edited, encoding="utf-8")
                policy_index.get_index.cache_clear()
                st.success("Policy updated for this business. The next question will use this version.")
                st.rerun()
    with st.expander("Add a business-specific policy"):
        with st.form(f"new_tenant_policy_{tenant_id}"):
            title = st.text_input("Policy title", placeholder="e.g. Credit sales policy", key=f"new_policy_title_{tenant_id}")
            body = st.text_area("Policy details", height=160, key=f"new_policy_body_{tenant_id}")
            add_policy = st.form_submit_button("Add policy")
        if add_policy:
            if not title.strip() or not body.strip():
                st.error("Enter both a title and policy details.")
            else:
                slug = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")[:40] or "custom"
                target = policy_dir / f"SHOP-{slug}.md"
                if target.exists():
                    st.error("A policy with that title already exists. Edit it above.")
                else:
                    target.write_text(f"# {title.strip()}\n\n{body.strip()}\n", encoding="utf-8")
                    policy_index.get_index.cache_clear()
                    st.success("Business-specific policy added.")
                    st.rerun()


def render_approvals_page(tenant_id: str, business_name: str) -> None:
    """Let a human review and decide this shop's recorded reorder drafts.

    One draft at a time: a card per line with the AI's reasoning, then two big
    buttons (Approve / Deny) plus a comments box. No quantity editor here - the
    shop owner can still change a quantity in Operations if they want to.
    """
    _page_header("check", "Approvals", "Review the AI's draft and record your decision.", "OWNER / MANAGER REVIEW")
    handoff = st.session_state.pop(f"restock_handoff_{tenant_id}", None)
    if handoff:
        st.success(f"Restock draft {handoff['draft_id']} is ready here for your review.")
        with st.expander("Restock process & sources", expanded=True):
            if handoff.get("ai_summary"):
                st.markdown("**AI decision brief**")
                st.markdown(handoff["ai_summary"])
            for step in handoff.get("timeline", []):
                st.markdown(f"**{step.get('phase', 'STEP')}** · {step.get('detail', '')} · Source: {step.get('source', 'agent trace')}")
            st.markdown("**Records checked:** " + ", ".join(handoff.get("sources", [])))
    drafts = approvals.list_drafts(tenant_id=tenant_id, user_id="default-user")
    waiting = [draft for draft in drafts if draft["status"] == procurement.DRAFT_STATUS]
    if not waiting:
        st.info("No reorder drafts are waiting for review.")
        if drafts:
            st.markdown("#### Recorded reorder history")
            st.dataframe(pd.DataFrame([{"Draft ID": d["draft_id"], "Status": d["status"],
                                        "Created": d["created_at"], "Estimated (UGX)": d["estimated_budget_ugx"]}
                                       for d in drafts]), width="stretch", hide_index=True)
        return
    selected = st.selectbox("Draft", waiting, format_func=lambda d: d["draft_id"])
    draft = approvals.load_draft(selected["draft_id"], tenant_id, "default-user")
    st.markdown(f"#### Reorder {draft['draft_id']}")
    st.caption(f"Created by {draft['created_by']} · {draft['created_at']} · total UGX {draft['estimated_budget_ugx']:,}")
    st.info("This draft is saved for review only. No supplier has been contacted and no order has been placed.")
    if draft.get("ai_selection_rationale"):
        st.markdown("### AI decision brief")
        st.markdown(draft["ai_selection_rationale"])
    st.markdown("### Why the AI suggested each line")
    st.caption("The AI chooses priorities and supplier trade-offs. Every figure is independently calculated and budget-checked in Python.")
    for line in draft["lines"]:
        with st.container(border=True):
            head = st.columns([3, 1, 2])
            head[0].markdown(f"**{line['item_name']}**  ·  `{line['item_id']}`")
            head[1].metric("Qty", line["recommended_qty"])
            head[2].metric("Line total", f"UGX {line['total_cost_ugx']:,}")
            st.markdown(f"**Stock now:** {line['current_stock']} · **Reorder point:** {line['reorder_point']} · "
                        f"**Supplier:** {line.get('selected_supplier', '—')} · "
                        f"**Unit price:** UGX {line['unit_price_ugx']:,} · "
                        f"**Delivers in:** {line.get('lead_time_days', 0)} day(s)")
            st.markdown(f"*How much to order:* {line.get('quantity_basis', '—')}")
            if line.get("supplier_reason"):
                st.markdown(f"**Verified quote comparison:** {line['supplier_reason']}")
            if line.get("ai_supplier_rationale"):
                st.markdown(f"**AI's reason for this choice:** {line['ai_supplier_rationale']}")
            alternatives = [option for option in line.get("supplier_options", [])
                            if option["supplier_name"] != line.get("selected_supplier")]
            if alternatives:
                with st.expander(f"Other quotes for {line['item_name']}"):
                    for option in alternatives:
                        st.write(f"{option['supplier_name']}: UGX {option['unit_price_ugx']:,} each · "
                                 f"MOQ {option['min_order_qty']} · {option['lead_time_days']} day(s) to deliver")
            if line.get("requires_override"):
                st.warning(f"⚠️  This line is above the 200% safety cap ({line.get('safety_cap')}); an override reason is required to approve.")
    st.metric("Draft total", f"UGX {draft['estimated_budget_ugx']:,}")
    st.markdown("---")
    with st.form(f"approval_decision_{tenant_id}"):
        reason = st.text_area("Comment (required to reject, or to note an override)",
                              key=f"approval_reason_{tenant_id}", height=80,
                              placeholder="Add a note, or explain why this draft should be rejected.")
        col_a, col_b = st.columns(2)
        with col_a:
            approve_clicked = st.form_submit_button("Approve draft", type="primary", width="stretch")
        with col_b:
            reject_clicked = st.form_submit_button("Reject draft", width="stretch")
    if approve_clicked or reject_clicked:
        chosen = "APPROVED" if approve_clicked else "REJECTED"
        if chosen == "REJECTED" and not reason.strip():
            st.error("A reason is required to deny a draft.")
            return
        if chosen == "APPROVED" and draft.get("requires_override_any") and not reason.strip():
            st.error("This draft has a line above the 200% cap; an override reason is required to approve it.")
            return
        try:
            approvals.decide(draft["draft_id"], chosen, business_name, reason,
                             tenant_id=tenant_id, user_id="default-user")
            st.success(f"{chosen.title()} decision recorded.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


# ---------------------------------------------------------------------------
# Script body: Streamlit runs this top to bottom on every interaction
# ---------------------------------------------------------------------------
st.markdown(CSS, unsafe_allow_html=True)
render_home()
