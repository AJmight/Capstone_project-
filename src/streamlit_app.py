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
                            tenant_data_dir, CSV_FILES)
from tool_agent import run_agent
from restock_agent import run_restock

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
CSS = """
<style>
  /* Hide Streamlit's own top bar and footer so the page looks like an app, not a notebook. */
  header[data-testid="stHeader"], footer { visibility: hidden; height: 0; }
  .block-container { padding-top: 1.2rem; padding-bottom: 6rem; max-width: 1280px; }
  /* Stitch screens use a persistent four-item mobile navigation bar. */
  div[data-testid="stRadio"] {
    position: fixed; z-index: 1000; left: 0; right: 0; bottom: 0;
    background: #fcf9f8; border-top: 1px solid #bdc9c6;
    padding: 0.35rem max(0.75rem, env(safe-area-inset-right)) calc(0.35rem + env(safe-area-inset-bottom));
  }
  div[data-testid="stRadio"] > label { display: none; }
  div[data-testid="stRadio"] > div { display: flex; justify-content: space-around; gap: 0.25rem; }
  div[data-testid="stRadio"] label { min-height: 44px; justify-content: center; }

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
    """Draw the welcome screen or the selected business's starter dashboard."""
    if "tenant_id" in st.session_state:
        render_business_home()
        return
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

        # A business name selects an isolated workspace; there is deliberately no login.
        business = st.text_input("Business name", key="business_name_input", max_chars=80,
                                 placeholder="e.g. Aminah's Stationery")
        st.caption("Your workspace and records stay separate from other businesses.")
        if st.button("Open business workspace  →", type="primary", width="stretch"):
            if not business.strip():
                st.warning("Enter your business name to continue.")
            else:
                try:
                    tenant_id = business_tenant_id(business)
                    initialize_business_data(tenant_id)
                    st.session_state["tenant_id"] = tenant_id
                    st.session_state["business_name"] = " ".join(business.split())
                    st.rerun()
                except (ValueError, OSError) as exc:
                    st.error(f"Could not open this business workspace: {exc}")


def render_business_home() -> None:
    """Show a clear business-scoped landing view without an account/login flow."""
    tenant_id = st.session_state["tenant_id"]
    business_name = st.session_state["business_name"]
    page = st.radio("Workspace", ["Dashboard", "Operations", "Restock AI", "Approvals"],
                    horizontal=True, label_visibility="collapsed", key="workspace_page")
    st.markdown(f'<div class="welcome">{html.escape(business_name)}</div>', unsafe_allow_html=True)
    if page == "Restock AI":
        render_restock_page(tenant_id, business_name)
    elif page == "Operations":
        render_operations_page(tenant_id)
    elif page == "Approvals":
        render_approvals_page(tenant_id, business_name)
    else:
        render_dashboard(tenant_id, business_name)
    if st.button("Switch business", type="secondary"):
        st.session_state.pop("tenant_id", None)
        st.session_state.pop("business_name", None)
        st.session_state.pop("workspace_page", None)
        st.rerun()


def render_dashboard(tenant_id: str, business_name: str) -> None:
    """Show quick stock and draft counts for the active business only."""
    safe_business_name = html.escape(business_name)
    st.markdown(f'<div class="title">{safe_business_name}</div>'
                '<div class="intro">Your stock, purchase history and drafts are saved for this business.</div>',
                unsafe_allow_html=True)
    status = shop_status(tenant_id)
    if "error" in status:
        st.warning(f"Business records could not be read: {status['error']}")
    else:
        a, b = st.columns(2)
        a.metric("Items running low", f"{status['low']} / {status['total']}")
        b.metric("Drafts awaiting your review", status["waiting"] if status["waiting"] is not None else "—")
    st.subheader("Today's Restock Assessment")
    low = procurement.get_low_stock(tenant_id=tenant_id)
    if "error" in low:
        st.warning(low["error"])
    elif low["items"]:
        names = ", ".join(f"{item['item_name']} ({item['current_stock']} left)" for item in low["items"][:3])
        st.info(f"{names} need attention. Review stock or ask the assistant for a plan.")
    else:
        st.success("No items are currently below their reorder point.")
    st.caption("Quick questions")
    quick_columns = st.columns(3)
    quick_question = None
    if quick_columns[0].button("What's low?", use_container_width=True):
        quick_question = "Which items are low on stock?"
    if quick_columns[1].button("Plan UGX 300k", use_container_width=True):
        quick_question = "Plan a restock within UGX 300,000."
    if quick_columns[2].button("Compare pens", use_container_width=True):
        quick_question = "Compare supplier prices for Bic Pens (Blue)."
    if quick_question:
        _run_business_question(quick_question, tenant_id, business_name)
    with st.form("dashboard_ask"):
        question = st.text_input("Ask your shop", placeholder="Ask about stock, purchases or policy")
        submitted = st.form_submit_button("Ask AI", type="primary")
    if submitted and question.strip():
        _run_business_question(question.strip(), tenant_id, business_name)
    st.caption("Every stock, purchase and draft action is saved in this business workspace.")


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
    """Group counter, stock and receiving actions under the mockup's Operations destination."""
    st.subheader("Operations")
    stock_tab, sale_tab, purchase_tab = st.tabs(["Stock", "Sales", "Purchases"])
    with stock_tab:
        render_stock_page(tenant_id)
    with sale_tab:
        render_sale_page(tenant_id)
    with purchase_tab:
        render_purchase_page(tenant_id)


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
    """Run the existing restock planner while passing the selected shop scope."""
    st.subheader("Restock plan")
    with st.form("restock_business"):
        budget = st.number_input("Budget (UGX)", min_value=1, step=10000, value=300000)
        submitted = st.form_submit_button("Build restock plan", type="primary")
    if submitted:
        try:
            with st.status("Reviewing this business's stock…", expanded=True) as status:
                result = run_restock(int(budget), user_name=business_name,
                                     shop_id=tenant_id, tenant_id=tenant_id)
                status.update(label="Restock review complete", state="complete", expanded=False)
            st.write(result.get("final_text", result.get("outcome", "No summary returned.")))
            created = result.get("state", {}).get("drafts_created", [])
            if created:
                st.success(f"Draft {created[0]} is ready for human review.")
        except Exception as exc:
            st.error(f"Restock planning failed: {type(exc).__name__}: {exc}")


def render_stock_page(tenant_id: str) -> None:
    """Edit only the current business's stock CSV."""
    st.subheader("Stock overview")
    headers, rows = _read_tenant_rows(tenant_id, "current_stock.csv")
    numeric_fields = {"current_stock", "reorder_point", "unit_cost_ugx"}
    typed_rows = [{**row, **{key: int(row[key]) for key in numeric_fields if row.get(key, "") != ""}}
                  for row in rows]
    frame = pd.DataFrame(typed_rows, columns=headers)
    number_columns = {key: st.column_config.NumberColumn(key.replace("_", " ").title(),
                                                         min_value=0, step=1)
                      for key in numeric_fields}
    edited = st.data_editor(frame, num_rows="dynamic", width="stretch",
                            column_config=number_columns, key="stock_editor")
    if st.button("Save stock changes", type="primary"):
        try:
            records = edited.to_dict("records")
            item_ids = [str(row.get("item_id", "")).strip() for row in records]
            if any(not item_id for item_id in item_ids) or len(item_ids) != len(set(item_ids)):
                st.error("Each stock item needs a unique item ID.")
                return
            required = set(headers)
            if any(any(pd.isna(row.get(key)) or str(row.get(key)).strip() == ""
                           for key in required) for row in records):
                st.error("Complete every field for each stock item before saving.")
                return
            _write_tenant_rows(tenant_id, "current_stock.csv", headers, records)
            st.success("Stock saved in this business workspace.")
            st.rerun()
        except Exception as exc:
            st.error(f"Stock could not be saved: {type(exc).__name__}: {exc}")


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


def render_approvals_page(tenant_id: str, business_name: str) -> None:
    """Keep decisions human-only and display drafts from the selected business."""
    st.subheader("Human approvals")
    st.warning("The assistant cannot approve or reject a draft.")
    drafts = approvals.list_drafts(tenant_id=tenant_id, user_id="default-user")
    waiting = [draft for draft in drafts if draft["status"] == procurement.DRAFT_STATUS]
    if not waiting:
        st.info("No drafts are waiting for review.")
        return
    selected = st.selectbox("Draft", waiting, format_func=lambda d: d["draft_id"])
    draft = approvals.load_draft(selected["draft_id"], tenant_id, "default-user")
    for line in draft["lines"]:
        st.write(f"{line['item_name']} · {line['recommended_qty']} units · UGX {line['total_cost_ugx']:,}")
    st.metric("Draft total", f"UGX {draft['estimated_budget_ugx']:,}")
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
