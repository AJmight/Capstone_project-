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
# The five things the system can do = the five menu options of src/app.py.
# (icon, title, one-line description). Kept as data so Screen 1 and the tests
# use the same list, and later screens can reuse it for navigation.
# ---------------------------------------------------------------------------
FEATURES = [
    ("📊", "Dashboard", "See this business's stock alerts and recent activity."),
    ("📦", "Operations", "Add items, record sales and log supplier purchases."),
    ("✨", "Restock AI", "Build a budget-aware reorder draft from this shop's stock."),
    ("💬", "AI Copilot", "Ask about this shop's records and its editable policies."),
    ("✓", "Approvals", "Review, edit and record human decisions on reorder drafts."),
]

# ---------------------------------------------------------------------------
# Styling. Streamlit has no built-in "hero panel" or "feature card", so we draw
# them with HTML + CSS (st.markdown(..., unsafe_allow_html=True)). Only text we
# wrote ourselves (never the user's input) is put in this HTML, so a name like
# "<script>" cannot inject markup; the user's name is only shown via st.success.
# Colours: navy #1B2A5B and orange #F5A100, as in the mockup.
# ---------------------------------------------------------------------------
CSS = """
<style>
  /* Hide Streamlit's own top bar and footer so the page looks like an app, not a notebook. */
  header[data-testid="stHeader"], footer { visibility: hidden; height: 0; }
  .block-container { padding-top: 1.2rem; padding-bottom: 6rem; max-width: 1280px; }
  /* Stitch screens use a persistent four-item mobile navigation bar. */
  .st-key-workspace_nav div[data-testid="stRadio"] {
    position: fixed; z-index: 1000; left: 0; right: 0; bottom: 0;
    background: #fcf9f8; border-top: 1px solid #bdc9c6;
    padding: 0.35rem max(0.75rem, env(safe-area-inset-right)) calc(0.35rem + env(safe-area-inset-bottom));
  }
  .st-key-workspace_nav div[data-testid="stRadio"] > label { display: none; }
  .st-key-workspace_nav div[data-testid="stRadio"] > div { display: flex; justify-content: space-around; gap: 0.25rem; }
  .st-key-workspace_nav div[data-testid="stRadio"] label { min-height: 44px; justify-content: center; }

  /* ---- Left: the navy hero panel ---- */
  .hero {
    position: relative; overflow: hidden;
    background: #005c55; color: #FFFFFF;
    border-radius: 4px; padding: 44px 48px; min-height: 86vh;
  }
  .brand { display: flex; align-items: center; gap: 14px; }
  .brand-badge {
    width: 56px; height: 56px; border-radius: 4px; background: #7C3AED;
    display: flex; align-items: center; justify-content: center; font-size: 28px;
  }
  .brand-name { font-size: 1.35rem; font-weight: 700; line-height: 1.1; }
  .brand-tag  { font-size: 0.95rem; color: #D6DCF0; }
  .kicker {
    margin-top: 22vh; color: #a3faef; font-weight: 700;
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
    border-radius: 50%; background: #7C3AED; box-shadow: 0 0 0 12px rgba(124, 58, 237, 0.18);
  }
  .corner {
    position: absolute; bottom: -140px; left: -120px; width: 340px; height: 340px;
    border-radius: 50%; background: #0f766e;
  }

  /* ---- Right: welcome text, feature cards, status strip ---- */
  .welcome { color: #005c55; font-weight: 700; margin-top: 8px; }
  .title   { color: #1c1b1b; font-size: 2.6rem; font-weight: 800; line-height: 1.15; margin: 6px 0 10px 0; }
  .intro   { color: #5B6478; font-size: 1.05rem; margin-bottom: 18px; }
  .card {
    display: flex; gap: 16px; align-items: center;
    background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 4px;
    padding: 14px 18px; margin-bottom: 10px;
  }
  .card-icon {
    min-width: 46px; height: 46px; border-radius: 4px; background: #EDE9FE;
    display: flex; align-items: center; justify-content: center; font-size: 22px;
  }
  .card-title { color: #1c1b1b; font-weight: 700; font-size: 1.05rem; }
  .card-text  { color: #5B6478; font-size: 0.93rem; }
  .status {
    background: #E6F4F2; border: 1px solid #bdc9c6; color: #00504a;
    border-radius: 4px; padding: 10px 16px; margin: 6px 0 14px 0; font-size: 0.95rem;
  }
  .status b { color: #005c55; }

  /* Make the primary button (Get Started) large and navy, like the mockup. */
  .stButton > button[kind="primary"] { height: 3.4rem; border-radius: 4px; background: #005c55; }
  /* Streamlit puts the button label inside a <p>, so the font is set on that element. */
  .stButton > button[kind="primary"] p { font-size: 1.15rem; font-weight: 700; }
  /* Stitch ledger system: warm canvas, teal actions, crisp borders, no card shadows. */
  :root { color-scheme: light; }
  [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background: #fcf9f8; }
  .block-container { max-width: 1280px; padding: 1rem 1rem 7rem; }
  h1, h2, h3 { color: #1c1b1b; letter-spacing: -0.02em; }
  p, label, [data-testid="stMarkdownContainer"] { color: #3e4947; }
  [data-testid="stMetric"] { background: #fff; border: 1px solid #e5e7eb; padding: 1rem; border-radius: 4px; }
  [data-testid="stMetricLabel"] { color: #3e4947; }
  [data-testid="stMetricValue"] { color: #005c55; font-family: 'JetBrains Mono', monospace; }
  [data-testid="stDataFrame"], [data-testid="stTable"] { border: 1px solid #e5e7eb; border-radius: 4px; }
  .stButton > button, .stFormSubmitButton > button { min-height: 44px; border-radius: 4px; border-color: #bdc9c6; }
  .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"],
  button[data-testid="stBaseButton-primary"] { background: #0f766e !important; border-color: #0f766e !important; color: #fff !important; }
  button[kind="primary"] *, button[data-testid*="primary"] * { color: #fff !important; }
  .workspace-banner { background: #fff; border: 1px solid #bdc9c6; border-left: 5px solid #005c55; padding: 1rem 1.25rem; margin: .25rem 0 1.25rem; }
  .workspace-kicker { color: #005c55; font-weight: 700; font-size: .8rem; letter-spacing: .08em; text-transform: uppercase; }
  .workspace-title { color: #1c1b1b; font-size: 1.55rem; font-weight: 700; margin-top: .2rem; }
  .workspace-meta { color: #6b7280; font-family: 'JetBrains Mono', monospace; font-size: .78rem; }
  .ledger-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 4px; padding: 1rem; margin: .5rem 0; }
  .tag-ai { color: #712ae2; background: #eaddff; border-radius: 4px; padding: .15rem .45rem; font-size: .8rem; }
  .st-key-workspace_nav div[data-testid="stRadio"] { background: #fcf9f8; border-top: 1px solid #bdc9c6; }
  .st-key-workspace_nav div[data-testid="stRadio"] label { min-height: 44px; justify-content: center; }
  @media (min-width: 900px) {
    .block-container { padding: 1.5rem 2rem 6rem; }
    .st-key-workspace_nav div[data-testid="stRadio"] { left: max(calc((100vw - 1280px) / 2), 0px); right: max(calc((100vw - 1280px) / 2), 0px); }
  }
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
    st.markdown('<div class="workspace-banner"><div class="workspace-kicker">SME PROCUREMENT ASSISTANT</div>'
                '<div class="workspace-title">Your shop, your stock book.</div>'
                '<div>Enter a business name to open its separate inventory, purchase and reorder records.</div></div>',
                unsafe_allow_html=True)
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
    """Show persistent workspace navigation and route every feature to this tenant."""
    tenant_id = st.session_state["tenant_id"]
    business_name = st.session_state["business_name"]
    with st.container(key="workspace_nav"):
        page = st.radio("Workspace", ["Dashboard", "Operations", "Restock AI", "AI Copilot", "Approvals"],
                        horizontal=True, label_visibility="collapsed", key="workspace_page")
    safe_name = html.escape(business_name)
    st.markdown(f'<div class="workspace-banner"><div class="workspace-kicker">ACTIVE BUSINESS WORKSPACE</div>'
                f'<div class="workspace-title">{safe_name}</div>'
                f'<div class="workspace-meta">TENANT · {html.escape(tenant_id)}</div></div>',
                unsafe_allow_html=True)
    if page == "Restock AI":
        render_restock_page(tenant_id, business_name)
    elif page == "Operations":
        render_operations_page(tenant_id)
    elif page == "AI Copilot":
        render_copilot_page(tenant_id, business_name)
    elif page == "Approvals":
        render_approvals_page(tenant_id, business_name)
    else:
        render_dashboard(tenant_id, business_name)
    if st.button("Switch business workspace", type="secondary", key="switch_business"):
        st.session_state.pop("tenant_id", None)
        st.session_state.pop("business_name", None)
        st.session_state.pop("workspace_page", None)
        st.rerun()


def render_dashboard(tenant_id: str, business_name: str) -> None:
    """Show the active shop's ledger summary and clear paths into each workflow."""
    safe_business_name = html.escape(business_name)
    st.markdown(f'<div class="workspace-title">Morning, {safe_business_name}</div>'
                '<div class="intro">Your business ledger is ready. Add your own stock and supplier quotes to get started.</div>',
                unsafe_allow_html=True)
    status = shop_status(tenant_id)
    if "error" in status:
        st.warning(f"Business records could not be read: {status['error']}")
    else:
        sales = _read_tenant_rows(tenant_id, "sales.csv")[1]
        today_sales = [row for row in sales if row.get("date") == date.today().isoformat()]
        drafts = approvals.list_drafts(tenant_id=tenant_id, user_id="default-user")
        metrics = st.columns(4)
        metrics[0].metric("Products", status["total"])
        metrics[1].metric("Below reorder point", status["low"])
        metrics[2].metric("Sales today", len(today_sales))
        metrics[3].metric("Drafts to review", status["waiting"] if status["waiting"] is not None else "—")
    st.subheader("Today's Restock Assessment")
    low = procurement.get_low_stock(tenant_id=tenant_id)
    if "error" in low:
        st.warning(low["error"])
    elif low["items"]:
        low_frame = pd.DataFrame([{"Item": item["item_name"], "SKU": item["item_id"],
                                   "In stock": item["current_stock"],
                                   "Reorder point": item["reorder_point"]} for item in low["items"]])
        st.dataframe(low_frame, width="stretch", hide_index=True)
    else:
        st.info("No products yet. Add this shop's items in Operations → Stock to start recording sales and reorders.")
    st.subheader("Quick actions")
    actions = st.columns(3)
    if actions[0].button("＋ Add or edit stock", width="stretch", key="dash_stock"):
        st.session_state["workspace_page"] = "Operations"
        st.rerun()
    if actions[1].button("✨ Plan a restock", width="stretch", key="dash_restock"):
        st.session_state["workspace_page"] = "Restock AI"
        st.rerun()
    if actions[2].button("📘 Ask this shop's policy", width="stretch", key="dash_policy"):
        st.session_state["workspace_page"] = "AI Copilot"
        st.session_state["copilot_tab"] = "Policy Q&A"
        st.rerun()
    st.caption("Every view, stock change, sale, supplier receipt and reorder draft uses the tenant ID shown above.")


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
    st.subheader("Operations Stock")
    st.caption("Changes made here are saved only inside the active business ledger.")
    inventory = procurement.get_inventory(tenant_id=tenant_id)
    low = procurement.get_low_stock(tenant_id=tenant_id)
    sales_rows = _read_tenant_rows(tenant_id, "sales.csv")[1]
    summaries = st.columns(3)
    summaries[0].metric("SKUs tracked", inventory.get("count", 0))
    summaries[1].metric("Below threshold", low.get("count", 0))
    summaries[2].metric("Sales recorded", len(sales_rows))
    stock_tab, sale_tab, purchase_tab, quote_tab, activity_tab = st.tabs(
        ["Stock", "Sales", "Purchases", "Supplier quotes", "Activity"])
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
    st.subheader("Ask the assistant")
    st.caption("The assistant can read this business's stock, quotes and purchase history. It cannot approve or place orders.")
    with st.form("ask_business"):
        question = st.text_area("What would you like to know?", placeholder="Which items are low on stock?")
        submitted = st.form_submit_button("Ask assistant", type="primary")
    if submitted:
        if not question.strip():
            st.warning("Enter a question first.")
        else:
            try:
                with st.status("Checking this business's records…", expanded=True) as status:
                    result = run_agent(question.strip(), user_name=business_name,
                                       tenant_id=tenant_id)
                    status.update(label="Response ready", state="complete", expanded=False)
                st.write(result.get("final_text", "The assistant returned no response."))
                st.caption(f"Run {result.get('run_id', 'n/a')} · {result.get('latency_s', 0)} seconds")
            except Exception as exc:
                st.error(f"The assistant could not complete this request: {type(exc).__name__}: {exc}")


def render_restock_page(tenant_id: str, business_name: str) -> None:
    """Build and save a tenant-scoped reorder draft for human review."""
    st.subheader("Restock Planner")
    st.caption("Uses only this business's stock, purchase history and saved supplier quotes.")
    with st.form("restock_business"):
        budget = st.number_input("Procurement cash budget (UGX)", min_value=1,
                                 step=10000, value=300000)
        choice = st.radio("Planning method", ["AI restock planner", "Create a deterministic draft"],
                          horizontal=True, key="restock_method")
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
    st.subheader("Stock editor")
    headers, rows = _read_tenant_rows(tenant_id, "current_stock.csv")
    st.caption(f"{len(rows)} products in this business. Add new items here; edit or remove rows in the ledger, then save.")
    with st.expander("＋ Add stock item", expanded=not rows):
        with st.form("add_stock_item"):
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
            with st.form(f"edit_stock_item_{index}"):
                name = st.text_input("Product name", row["item_name"], key=f"stock_name_{index}")
                category = st.text_input("Category", row["category"], key=f"stock_category_{index}")
                values = st.columns(3)
                stock = values[0].number_input("Current stock", min_value=0, value=current,
                                               step=1, key=f"stock_current_{index}")
                threshold = values[1].number_input("Reorder point", min_value=0, value=reorder,
                                                   step=1, key=f"stock_reorder_{index}")
                cost = values[2].number_input("Unit cost (UGX)", min_value=0,
                                              value=int(row.get("unit_cost_ugx") or 0), step=100,
                                              key=f"stock_cost_{index}")
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
    st.subheader("Record a purchase")
    stock_headers, stock_rows = _read_tenant_rows(tenant_id, "current_stock.csv")
    if not stock_rows:
        st.info("Add stock items in Stock before recording a purchase.")
        return
    item_by_id = {row["item_id"]: row for row in stock_rows}
    with st.form("purchase_entry"):
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
    st.subheader("Record a sale")
    stock_headers, stock_rows = _read_tenant_rows(tenant_id, "current_stock.csv")
    available = {row["item_id"]: row for row in stock_rows}
    if not available:
        st.info("Add stock items before recording a sale.")
        return
    with st.form("sale_entry"):
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
    st.subheader("Supplier price book")
    _, stock_rows = _read_tenant_rows(tenant_id, "current_stock.csv")
    if not stock_rows:
        st.info("Add products in Stock before saving supplier quotes.")
        return
    names = {row["item_id"]: row["item_name"] for row in stock_rows}
    with st.form("supplier_quote_entry"):
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
    st.subheader("Business activity ledger")
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
    """Answer shop-specific questions and let the shop edit its own policy copies."""
    st.subheader("AI Copilot")
    st.caption("Answers use this business's saved stock, purchases, quotes and policy documents.")
    tabs = st.tabs(["Ask the assistant", "Policy Q&A", "View & edit policies"])
    with tabs[0]:
        render_ask_page(tenant_id, business_name)
    with tabs[1]:
        st.markdown("#### Ask this shop's policy")
        with st.form("tenant_policy_question"):
            question = st.text_input("Policy question", placeholder="What approvals are needed for a large order?")
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
        selected = st.selectbox("Policy document", [path.name for path in documents], key="policy_document")
        selected_path = policy_dir / selected
        policy_text = selected_path.read_text(encoding="utf-8")
        with st.form("edit_tenant_policy"):
            edited = st.text_area("Policy text (Markdown)", value=policy_text,
                                  height=360, key=f"policy_text_{selected}")
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
        with st.form("new_tenant_policy"):
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
    st.subheader("Human Approvals")
    st.caption("Reorder drafts stay attached to this tenant. The assistant cannot approve or place orders.")
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
        with st.form("edit_reorder_quantity"):
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
    with st.form("approval_decision"):
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
