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
NAV_ICONS = {"Dashboard": "▦", "Operations": "▤", "Restock AI": "✧", "Approvals": "✓"}

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
  .st-key-workspace_nav [data-testid="stRadio"] { position:fixed; z-index:1000; left:0; right:0; bottom:0; margin:0; padding:.35rem max(.75rem,env(safe-area-inset-right)) calc(.35rem + env(safe-area-inset-bottom)); background:rgba(252,249,248,.98); border-top:1px solid var(--line); }
  .st-key-workspace_nav [data-testid="stRadio"] > label { display:none; }
  .st-key-workspace_nav [role="radiogroup"] { display:flex; justify-content:center; gap:.45rem; }
  .st-key-workspace_nav [role="radiogroup"] label > div:first-child { display:none; }
  .st-key-workspace_nav [role="radiogroup"] label { min-height:46px; justify-content:center; padding:.3rem .8rem; border:1px solid transparent; border-radius:4px; color:#52605d; transition:background .16s ease,color .16s ease,border-color .16s ease; }
  .st-key-workspace_nav [role="radiogroup"] label:hover { background:var(--soft); }
  .st-key-workspace_nav [role="radiogroup"] label:has(input:checked) { color:var(--teal-dark); font-weight:700; background:var(--teal-soft); border-color:#b9ddd6; }
  .st-key-workspace_nav [role="radiogroup"] label:has(input:checked) p { color:var(--teal-dark); }
  @keyframes rise-in { from { opacity:0; transform:translateY(7px); } to { opacity:1; transform:translateY(0); } }
  @keyframes soft-pulse { 50% { opacity:.45; } }
  .live-dot { display:inline-block; width:8px; height:8px; border-radius:50%; background:#16a34a; margin-right:.35rem; animation:soft-pulse 1.8s ease-in-out infinite; }
  @media (min-width:900px) { .block-container { padding:1.5rem 2rem 6rem; } .st-key-workspace_nav [data-testid="stRadio"] { left:max(calc((100vw - 1280px) / 2),0px); right:max(calc((100vw - 1280px) / 2),0px); } }
  @media (max-width:640px) { .block-container { padding:.8rem .75rem 6rem; } .feature-strip { grid-template-columns:1fr; } .workspace-title { font-size:1.1rem; } .page-heading h1 { font-size:1.45rem; } .st-key-workspace_nav [role="radiogroup"] { gap:.08rem; } .st-key-workspace_nav [role="radiogroup"] label { min-height:50px; padding:.2rem .22rem; font-size:.75rem; } .stock-threshold { display:none; } .stock-item-row { gap:.45rem; } .st-key-dashboard_metrics [data-testid="stHorizontalBlock"] { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); } }
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
    with st.container(key="workspace_nav"):
        page = st.radio("Workspace", WORKSPACE_PAGES, format_func=lambda item: f"{NAV_ICONS[item]}  {item}",
                        horizontal=True, label_visibility="collapsed", key="workspace_page")
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
    for key in ("tenant_id", "business_name", "workspace_page"):
        st.session_state.pop(key, None)


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
    render_copilot_page(tenant_id, business_name)


def _run_business_question(question: str, tenant_id: str, business_name: str) -> None:
    """Run one question with the workspace scope passed as trusted context."""
    try:
        with st.status("Checking this business's records…", expanded=True) as status:
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
    """Run the existing bounded procurement agent in the active tenant context."""
    st.markdown('<div class="assistant-panel"><div class="assistant-brand">'
                f'<div class="assistant-avatar">{_icon_svg("sparkles", 21)}</div>'
                '<div><span class="tag-ai">AI COPILOT</span><h2>How can I help your shop?</h2>'
                '<p>Answers use this business\'s saved stock, supplier quotes and purchase history. '
                'A person still approves every reorder.</p></div></div></div>', unsafe_allow_html=True)
    question_key = f"assistant_question_{tenant_id}"
    prompts = [
        ("⚠️  Which items are low on stock?", "Which items are low on stock?"),
        ("✧  Plan restock under UGX 300,000", "Plan a restock under UGX 300,000"),
        ("⇄  Compare supplier pen prices", "Compare supplier prices for pens"),
        ("▤  What did we buy last month?", "What did we buy last month?"),
    ]
    prompt_cols = st.columns(2)
    for index, (label, prompt) in enumerate(prompts):
        prompt_cols[index % 2].button(label, key=f"assistant_prompt_{tenant_id}_{index}", width="stretch",
                                      on_click=_select_assistant_prompt, args=(prompt, question_key))
    with st.form(f"ask_business_{tenant_id}"):
        question = st.text_area("Ask about your business", key=question_key,
                                placeholder="Ask about stock, suppliers, purchases or policies…", height=100)
        with st.container(key="ai_submit"):
            submitted = st.form_submit_button("✧  Ask Copilot", type="primary", width="stretch")
    if submitted:
        if not question.strip():
            st.warning("Enter a question first.")
        else:
            try:
                with st.status("Checking this business's records…", expanded=True) as status:
                    result = run_agent(question.strip(), user_name=business_name,
                                       tenant_id=tenant_id)
                    status.update(label="Response ready", state="complete", expanded=False)
                st.markdown('<div class="response-card"><div class="response-label">'
                            f'{_icon_svg("sparkles", 16)} COPILOT RESPONSE</div></div>', unsafe_allow_html=True)
                st.markdown(result.get("final_text", "The assistant returned no response."))
                st.caption(f"Run {result.get('run_id', 'n/a')} · {result.get('latency_s', 0)} seconds · tenant-scoped")
            except Exception as exc:
                st.error(f"The assistant could not complete this request: {type(exc).__name__}: {exc}")


def _select_assistant_prompt(prompt: str, input_key: str) -> None:
    """Put a suggestion into the chat input before that widget is instantiated."""
    st.session_state[input_key] = prompt


def render_restock_page(tenant_id: str, business_name: str) -> None:
    """Build and save a tenant-scoped reorder draft for human review."""
    _page_header("restock", "Restock AI", "Build a budget-aware draft from this shop's own stock, prices and purchase history.", "AI-ASSISTED · HUMAN-APPROVED")
    with st.form(f"restock_business_{tenant_id}"):
        budget = st.number_input("Procurement cash budget (UGX)", min_value=1,
                                 step=10000, value=300000)
        choice = st.radio("Planning method", ["AI restock planner", "Create a deterministic draft"],
                          horizontal=True, key=f"restock_method_{tenant_id}")
        submitted = st.form_submit_button("Run restock planner", type="primary", width="stretch")
    if not submitted:
        return
    inventory = procurement.get_inventory(tenant_id=tenant_id)
    if "error" in inventory or not inventory.get("items"):
        st.info("Add this shop's stock items in Operations → Stock before planning a reorder.")
        return
    try:
        if choice == "AI restock planner":
            with st.status("Reviewing this business's stock…", expanded=True) as status:
                result = run_restock(int(budget), user_name=business_name,
                                     shop_id=tenant_id, tenant_id=tenant_id)
                status.update(label="Restock review complete", state="complete", expanded=False)
        else:
            result = _create_deterministic_draft(int(budget), tenant_id, business_name)
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
        created = state.get("drafts_created", [])
        if created:
            st.success(f"Draft {created[0]} is saved to this business's approvals queue.")
            st.info("This is a draft only. Review it under Approvals before making any purchase.")
    except Exception as exc:
        st.error(f"Restock planning failed: {type(exc).__name__}: {exc}")


def _create_deterministic_draft(budget: int, tenant_id: str, business_name: str) -> dict:
    """Save an offline-ready quote-based draft when no model call is available."""
    from tools import registry

    context = {"created_by": business_name, "tenant_id": tenant_id, "user_id": "default-user"}
    low, status = registry.execute_tool("get_low_stock", {}, context=context)
    if status != "ok":
        raise ValueError(low.get("error", "Could not read this shop's low stock."))
    if not low["items"]:
        return {"outcome": "NOTHING_TO_DO", "final_text": "No items are below their reorder point."}
    plan, status = registry.execute_tool("plan_within_budget", {
        "items": [row["item_id"] for row in low["items"]], "budget_ugx": budget}, context=context)
    if status != "ok":
        raise ValueError(plan.get("error", "Could not build a restock plan."))
    if not plan["included"]:
        return {"outcome": "NEEDS_HUMAN", "state": {"plan": plan},
                "final_text": "No priced reorder fits this budget. Add supplier quotes or purchase history first."}
    draft, status = registry.execute_tool("draft_requisition", {
        "items": [row["item_id"] for row in plan["included"]]}, context=context)
    if status != "ok":
        raise ValueError(draft.get("error", "Could not save the reorder draft."))
    if int(draft["estimated_budget_ugx"]) > budget:
        raise ValueError("The calculated draft exceeded the budget; it was not submitted for approval.")
    return {"outcome": "DRAFT_READY", "final_text": "A quote-based draft is ready for human review.",
            "state": {"plan": plan, "drafts_created": [draft["draft_id"]]}}


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
            item_name = st.text_input("Product name", placeholder="e.g. Exercise books")
            category = st.text_input("Category", placeholder="e.g. Stationery")
            values = st.columns(3)
            current = values[0].number_input("Current stock", min_value=0, step=1)
            reorder = values[1].number_input("Reorder point", min_value=0, step=1)
            unit_cost = values[2].number_input("Unit cost (UGX)", min_value=0, step=100)
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
        item_id = st.selectbox("Item", list(item_by_id), format_func=lambda key: item_by_id[key]["item_name"])
        qty = st.number_input("Quantity received", min_value=1, step=1)
        price = st.number_input("Unit price (UGX)", min_value=0, step=100)
        supplier = st.text_input("Supplier")
        payment = st.selectbox("Payment status", ["Paid Cash / MoMo", "On Supplier Credit", "Partial Paid"])
        purchased_on = st.date_input("Purchase date", value=date.today())
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
                               format_func=lambda key: available[key]["item_name"])
        qty = st.number_input("Quantity sold", min_value=1, step=1)
        price = st.number_input("Unit sale price (UGX)", min_value=0, step=100)
        payment = st.selectbox("Payment method", ["Cash", "MTN MoMo", "Airtel Money"])
        sold_on = st.date_input("Sale date", value=date.today())
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
        item_id = st.selectbox("Product", list(names), format_func=lambda key: names[key])
        supplier = st.text_input("Supplier name")
        fields = st.columns(3)
        price = fields[0].number_input("Unit price (UGX)", min_value=1, step=100)
        minimum = fields[1].number_input("Minimum order quantity", min_value=1, step=1)
        lead = fields[2].number_input("Lead time (days)", min_value=0, step=1)
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
            title = st.text_input("Policy title", placeholder="e.g. Credit sales policy")
            body = st.text_area("Policy details", height=160)
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
    """Let a human review, edit and decide this shop's recorded reorder drafts."""
    _page_header("check", "Approvals", "Review the AI's draft, adjust quantities and record a human decision.", "OWNER / MANAGER REVIEW")
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
    for line in draft["lines"]:
        st.write(f"{line['item_name']} · {line['recommended_qty']} units · UGX {line['total_cost_ugx']:,}")
    st.metric("Draft total", f"UGX {draft['estimated_budget_ugx']:,}")
    with st.expander("Adjust a suggested quantity"):
        with st.form(f"edit_reorder_quantity_{tenant_id}"):
            line_id = st.selectbox("Item", [line["item_id"] for line in draft["lines"]],
                                   format_func=lambda key: next(line["item_name"] for line in draft["lines"] if line["item_id"] == key))
            new_qty = st.number_input("New quantity", min_value=0, step=1)
            edit_reason = st.text_input("Reason for changing the AI suggestion")
            edit_submitted = st.form_submit_button("Save quantity change")
        if edit_submitted:
            try:
                approvals.edit_quantity(draft["draft_id"], line_id, int(new_qty), business_name,
                                        edit_reason, tenant_id=tenant_id, user_id="default-user")
                st.success("Edited quantity saved and audited for this business.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    with st.form(f"approval_decision_{tenant_id}"):
        decision = st.selectbox("Decision", ["APPROVED", "REJECTED"])
        reason = st.text_input("Reason (required for rejection or an override)")
        confirmation = st.text_input(f"Type {decision} to confirm")
        submitted = st.form_submit_button("Record human decision", type="primary")
    if submitted:
        if confirmation != decision:
            st.error(f"Type {decision} exactly to confirm this decision.")
            return
        try:
            approvals.decide(draft["draft_id"], decision, business_name, reason,
                             tenant_id=tenant_id, user_id="default-user")
            st.success(f"{decision.title()} decision recorded.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


# ---------------------------------------------------------------------------
# Script body: Streamlit runs this top to bottom on every interaction
# ---------------------------------------------------------------------------
st.markdown(CSS, unsafe_allow_html=True)
render_home()
