"""
Offline integration checks for tenant-scoped Streamlit workflows.
=================================================================

WHAT IS TESTED
--------------
Streamlit ships a headless test runner, streamlit.testing.v1.AppTest. It runs the app
script in-process (no browser, no server, no GEMINI_API_KEY) and lets the test read the
elements on the page and click buttons, the same way a person would.

  UI-01..15  business selection, route/session safety, stock CRUD, sales, purchases,
             quotes, policy editing/Q&A, bounded chat context, restock-to-approval,
             human quantity edits, approval state and tenant isolation.

SANDBOX
-------
The app reads drafts through approvals.list_drafts(). The test points
procurement.STORAGE_PATH at a temporary database, so it never touches the real
data/state.sqlite3. AppTest runs in this same Python process, so the patched module
is the one the app imports.

Usage (PowerShell, repo root):  py tests\\test_ui_home.py

Owner: Boonabaana Bronia (UI), built with Claude Code
"""

# ---------------------------------------------------------------------------
# Imports and paths
# ---------------------------------------------------------------------------
import csv                                     # independent recount of the low-stock items
import os
import sys
import tempfile
import traceback
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from streamlit.testing.v1 import AppTest       # Streamlit's headless app runner

from tools import procurement                  # to sandbox STORAGE_PATH
import approvals
import memory as memory_module
import state as state_module
import tool_agent
import tenant_context                          # to sandbox business folders
from conversation_context import (COPILOT_RECENT_TURNS, COPILOT_SUMMARY_LIMIT,
                                  build_copilot_context, compact_copilot_turn)
from rag import index as policy_index
from rag import policy_qa
from tools.knowledge import search_policy

APP = ROOT / "src" / "streamlit_app.py"
EXPECTED_ROUTES = ["Dashboard", "Operations", "Restock AI", "Approvals"]


def expected_low_and_total() -> tuple[int, int]:
    """Recount from the CSV itself: low means current_stock <= reorder_point (handoff §6)."""
    with open(ROOT / "data" / "current_stock.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    low = sum(1 for r in rows if int(r["current_stock"]) <= int(r["reorder_point"]))
    return low, len(rows)


def fresh_app() -> AppTest:
    """Run the home screen once and return the test handle."""
    at = AppTest.from_file(str(APP), default_timeout=30)
    at.run()
    return at


def open_business(at: AppTest, name: str) -> str:
    """Enter a named shop through the same welcome form used in the browser."""
    at.text_input(key="business_name_input").input(name)
    next(button for button in at.form_submit_button if button.label == "Open business workspace").click().run()
    return tenant_context.business_tenant_id(name)


def write_rows(path: Path, headers: list[str], rows: list[dict]) -> None:
    """Create a tenant-local fixture using the production CSV schema."""
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def seed_one_low_item(tenant_id: str) -> None:
    """Create a low stock item with valid purchase history and a usable quote."""
    folder = tenant_context.tenant_data_dir(tenant_id)
    write_rows(folder / "current_stock.csv",
               ["item_id", "item_name", "category", "current_stock", "reorder_point", "unit_cost_ugx"],
               [{"item_id": "ITM001", "item_name": "Blue exercise books", "category": "Stationery",
                 "current_stock": 1, "reorder_point": 5, "unit_cost_ugx": 900}])
    write_rows(folder / "past_purchases.csv",
               ["date", "item_id", "quantity_purchased", "historical_unit_price_ugx", "supplier_name", "payment_status"],
               [{"date": "2026-08-01", "item_id": "ITM001", "quantity_purchased": 10,
                 "historical_unit_price_ugx": 900, "supplier_name": "Stationery Supply Co", "payment_status": "Paid Cash / MoMo"}])
    write_rows(folder / "supplier_quotes.csv",
               ["supplier_name", "item_id", "offered_unit_price_ugx", "min_order_qty", "lead_time_days"],
               [{"supplier_name": "Stationery Supply Co", "item_id": "ITM001",
                 "offered_unit_price_ugx": 900, "min_order_qty": 1, "lead_time_days": 2}])


def page_text(at: AppTest) -> str:
    """All the HTML/markdown on the page as one string, for simple 'is it shown' checks."""
    return " ".join(m.value for m in at.markdown)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_ui01_page_renders():
    at = fresh_app()
    assert not at.exception, at.exception


def test_ui02_business_entry_matches_workspace_flow():
    at = fresh_app()
    assert any(item.label == "Business name" for item in at.text_input)
    assert any(button.label == "Open business workspace" for button in at.form_submit_button)


def test_ui03_welcome_does_not_show_shared_shop_records():
    at = fresh_app()
    assert any(item.label == "Business name" for item in at.text_input)
    assert "items are low" not in page_text(at)


def test_ui04_empty_name_is_refused():
    at = fresh_app()
    at.text_input(key="business_name_input").input("   ")
    at.form_submit_button[0].click().run()
    assert any("enter your business name" in w.value.lower() for w in at.warning)
    assert "tenant_id" not in at.session_state


def test_ui05_business_name_opens_an_empty_workspace():
    at = fresh_app()
    at.text_input(key="business_name_input").input("Aminah Stationery")
    at.form_submit_button[0].click().run()
    tenant_id = tenant_context.business_tenant_id("Aminah Stationery")
    assert at.session_state["business_name"] == "Aminah Stationery"
    assert at.session_state["tenant_id"] == tenant_id
    stock_file = tenant_context.tenant_data_dir(tenant_id) / "current_stock.csv"
    with stock_file.open(encoding="utf-8", newline="") as source:
        assert len(list(csv.DictReader(source))) == 0
    assert list(tenant_context.tenant_policy_dir(tenant_id).glob("*.md"))


def test_ui06_workspace_routes_render():
    at = fresh_app()
    at.text_input(key="business_name_input").input("UI Route Shop")
    at.form_submit_button[0].click().run()
    for page in EXPECTED_ROUTES:
        at.radio(key="workspace_page").set_value(page).run()
        assert not at.exception, f"{page}: {at.exception}"
    at.radio(key="workspace_page").set_value("Dashboard").run()
    assert "AI Copilot" in page_text(at), "Dashboard should open the shop's AI Copilot view"
    next(button for button in at.button if "Which items are low on stock?" in button.label).click().run()
    assert not at.exception, at.exception
    tenant_id = tenant_context.business_tenant_id("UI Route Shop")
    assert at.session_state[f"assistant_question_{tenant_id}"] == "Which items are low on stock?"
    next(button for button in at.button if button.label == "↔ Switch shop").click().run()
    assert not at.exception, at.exception
    assert "tenant_id" not in at.session_state


def test_ui08_stock_item_can_be_added_from_the_ui():
    at = fresh_app()
    at.text_input(key="business_name_input").input("UI Stock Entry Shop")
    at.form_submit_button[0].click().run()
    at.radio(key="workspace_page").set_value("Operations").run()
    next(item for item in at.text_input if item.label == "Product name").input("Blue exercise book")
    next(item for item in at.text_input if item.label == "Category").input("Stationery")
    next(item for item in at.number_input if item.label == "Current stock").set_value(5)
    next(item for item in at.number_input if item.label == "Reorder point").set_value(8)
    next(item for item in at.number_input if item.label == "Unit cost (UGX)").set_value(1200)
    next(button for button in at.form_submit_button if button.label == "Add item to this business").click().run()
    assert not at.exception, at.exception
    tenant_id = tenant_context.business_tenant_id("UI Stock Entry Shop")
    stock_file = tenant_context.tenant_data_dir(tenant_id) / "current_stock.csv"
    with stock_file.open(encoding="utf-8", newline="") as source:
        saved = list(csv.DictReader(source))
    assert saved == [{"item_id": "ITM001", "item_name": "Blue exercise book", "category": "Stationery",
                      "current_stock": "5", "reorder_point": "8", "unit_cost_ugx": "1200"}]
    # The visible stock cards must also support editing and removal from this ledger.
    tenant_id = tenant_context.business_tenant_id("UI Stock Entry Shop")
    next(item for item in at.text_input if item.key == f"stock_name_{tenant_id}_0").input("Blue exercise books")
    next(item for item in at.number_input if item.key == f"stock_current_{tenant_id}_0").set_value(7)
    next(button for button in at.form_submit_button if button.label == "Save item").click().run()
    with stock_file.open(encoding="utf-8", newline="") as source:
        saved = list(csv.DictReader(source))
    assert saved[0]["item_name"] == "Blue exercise books" and saved[0]["current_stock"] == "7"
    next(button for button in at.form_submit_button if button.label == "Delete item").click().run()
    with stock_file.open(encoding="utf-8", newline="") as source:
        assert list(csv.DictReader(source)) == []


def test_ui07_business_stock_is_isolated():
    shop_a = tenant_context.business_tenant_id("Business Alpha")
    shop_b = tenant_context.business_tenant_id("Business Beta")
    tenant_context.initialize_business_data(shop_a)
    tenant_context.initialize_business_data(shop_b)
    stock_file = tenant_context.tenant_data_dir(shop_a) / "current_stock.csv"
    with stock_file.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=["item_id", "item_name", "category",
                                   "current_stock", "reorder_point", "unit_cost_ugx"])
        writer.writeheader()
        writer.writerow({"item_id": "A-001", "item_name": "Alpha stock", "category": "Test",
                         "current_stock": 3, "reorder_point": 5, "unit_cost_ugx": 10})
    assert procurement.get_inventory(tenant_id=shop_a)["count"] == 1
    assert procurement.get_inventory(tenant_id=shop_b)["count"] == 0


def test_ui10_business_data_can_use_a_separate_storage_root():
    saved_root, saved_tenants = tenant_context.DATA_ROOT, tenant_context.TENANTS_ROOT
    try:
        with tempfile.TemporaryDirectory() as folder:
            tenant_context.DATA_ROOT = Path(folder)
            tenant_context.TENANTS_ROOT = Path(folder) / "tenants"
            tenant_id = tenant_context.business_tenant_id("External Mount Shop")
            path = tenant_context.initialize_business_data(tenant_id)
            with (path / "current_stock.csv").open(encoding="utf-8", newline="") as source:
                assert list(csv.DictReader(source)) == []
    finally:
        tenant_context.DATA_ROOT, tenant_context.TENANTS_ROOT = saved_root, saved_tenants


def test_ui11_operations_record_sales_purchases_and_quotes():
    at = fresh_app()
    tenant_id = open_business(at, "UI Operations Flow")
    at.radio(key="workspace_page").set_value("Operations").run()
    at.text_input(key=f"new_stock_name_{tenant_id}").input("Blue exercise book")
    at.text_input(key=f"new_stock_category_{tenant_id}").input("Stationery")
    at.number_input(key=f"new_stock_current_{tenant_id}").set_value(10)
    at.number_input(key=f"new_stock_reorder_{tenant_id}").set_value(3)
    at.number_input(key=f"new_stock_cost_{tenant_id}").set_value(900)
    next(b for b in at.form_submit_button if b.label == "Add item to this business").click().run()
    assert not at.exception, at.exception

    at.text_input(key=f"quote_supplier_{tenant_id}").input("Stationery Supply Co")
    at.number_input(key=f"quote_price_{tenant_id}").set_value(900)
    next(b for b in at.form_submit_button if b.label == "Save supplier quote").click().run()
    assert not at.exception, at.exception
    quote_file = tenant_context.tenant_data_dir(tenant_id) / "supplier_quotes.csv"
    with quote_file.open(encoding="utf-8", newline="") as source:
        assert next(csv.DictReader(source))["supplier_name"] == "Stationery Supply Co"

    at.number_input(key=f"purchase_qty_{tenant_id}").set_value(2)
    at.number_input(key=f"purchase_price_{tenant_id}").set_value(850)
    at.text_input(key=f"purchase_supplier_{tenant_id}").input("Stationery Supply Co")
    next(b for b in at.form_submit_button if b.label == "Save purchase").click().run()
    assert not at.exception, at.exception
    at.number_input(key=f"sale_qty_{tenant_id}").set_value(3)
    at.number_input(key=f"sale_price_{tenant_id}").set_value(1500)
    next(b for b in at.form_submit_button if b.label == "Save sale & update stock").click().run()
    assert not at.exception, at.exception
    stock = tenant_context.tenant_data_dir(tenant_id) / "current_stock.csv"
    sales = tenant_context.tenant_data_dir(tenant_id) / "sales.csv"
    purchases = tenant_context.tenant_data_dir(tenant_id) / "past_purchases.csv"
    with stock.open(encoding="utf-8", newline="") as source:
        assert next(csv.DictReader(source))["current_stock"] == "9"
    with sales.open(encoding="utf-8", newline="") as source:
        assert len(list(csv.DictReader(source))) == 1
    with purchases.open(encoding="utf-8", newline="") as source:
        assert len(list(csv.DictReader(source))) == 1

    at.number_input(key=f"sale_qty_{tenant_id}").set_value(10)
    next(b for b in at.form_submit_button if b.label == "Save sale & update stock").click().run()
    assert any("Only 9 units" in error.value for error in at.error)
    with stock.open(encoding="utf-8", newline="") as source:
        assert next(csv.DictReader(source))["current_stock"] == "9"
    assert not at.exception, at.exception


def test_ui12_restocks_create_a_session_and_open_approvals_automatically():
    at = fresh_app()
    tenant_id = open_business(at, "UI Restock Session Flow")
    seed_one_low_item(tenant_id)
    at.radio(key="workspace_page").set_value("Restock AI").run()
    assert at.radio(key=f"restock_method_{tenant_id}").value == "Quick deterministic plan"
    at.number_input(key=f"restock_budget_{tenant_id}").set_value(100000)
    next(b for b in at.form_submit_button if b.label == "Build restock draft").click().run()
    assert not at.exception, at.exception
    assert at.radio(key="workspace_page").value == "Approvals", (
        f"a saved draft should open the review queue; got {at.radio(key='workspace_page').value}; "
        f"errors={[e.value for e in at.error]}; text={page_text(at)}")
    assert any("is ready here for your review" in success.value for success in at.success)
    assert any("Read 1 low-stock items" in item.value for item in at.markdown)
    assert any("current_stock.csv" in item.value for item in at.markdown)
    pending = approvals.list_drafts(tenant_id=tenant_id, user_id="default-user")
    assert len(pending) == 1 and pending[0]["status"] == procurement.DRAFT_STATUS
    draft_id = pending[0]["draft_id"]
    manager = state_module.StateManager()
    try:
        session = manager.find_session_by_draft_id(draft_id)
        assert session is not None and session.approval_status == "AWAITING_APPROVAL"
    finally:
        manager.close()

    # A second run in the same browser must get a fresh workflow session and
    # leave the first pending draft untouched.
    at.radio(key="workspace_page").set_value("Restock AI").run()
    next(b for b in at.form_submit_button if b.label == "Build restock draft").click().run()
    assert not at.exception, at.exception
    pending = approvals.list_drafts(tenant_id=tenant_id, user_id="default-user")
    assert len(pending) == 2 and len({d["draft_id"] for d in pending}) == 2


def test_ui13_approval_edit_and_decision_are_session_safe():
    at = fresh_app()
    tenant_id = open_business(at, "UI Approval Flow")
    seed_one_low_item(tenant_id)
    at.radio(key="workspace_page").set_value("Restock AI").run()
    at.number_input(key=f"restock_budget_{tenant_id}").set_value(100000)
    next(b for b in at.form_submit_button if b.label == "Build restock draft").click().run()
    draft_summary = approvals.list_drafts(tenant_id=tenant_id, user_id="default-user")[0]
    draft = approvals.load_draft(draft_summary["draft_id"], tenant_id, "default-user")

    at.number_input(key=f"approval_qty_{tenant_id}").set_value(draft["lines"][0]["recommended_qty"] + 1)
    at.text_input(key=f"approval_edit_reason_{tenant_id}").input("Increase for expected school demand")
    next(b for b in at.form_submit_button if b.label == "Save quantity change").click().run()
    assert not at.exception, at.exception
    edited = approvals.load_draft(draft["draft_id"], tenant_id, "default-user")
    assert edited["lines"][0]["ai_suggested_qty"] < edited["lines"][0]["recommended_qty"]
    assert edited["lines"][0]["edits"][-1]["reason"] == "Increase for expected school demand"

    at.selectbox(key=f"approval_decision_{tenant_id}").set_value("APPROVED")
    at.text_input(key=f"approval_confirmation_{tenant_id}").input("APPROVED")
    next(b for b in at.form_submit_button if b.label == "Record human decision").click().run()
    assert not at.exception, at.exception
    decided = approvals.load_draft(draft["draft_id"], tenant_id, "default-user")
    assert decided["status"] == "APPROVED"
    assert decided["decision"]["decided_by"] == "UI Approval Flow"
    assert at.radio(key="workspace_page").value == "Approvals"

    # A second draft can be rejected only after a human enters both the reason
    # and the exact confirmation; the workflow then records REJECTED.
    at.radio(key="workspace_page").set_value("Restock AI").run()
    next(b for b in at.form_submit_button if b.label == "Build restock draft").click().run()
    second = next(d for d in approvals.list_drafts(tenant_id=tenant_id, user_id="default-user")
                  if d["status"] == procurement.DRAFT_STATUS)
    at.selectbox(key=f"approval_decision_{tenant_id}").set_value("REJECTED")
    at.text_input(key=f"approval_confirmation_{tenant_id}").input("REJECTED")
    next(b for b in at.form_submit_button if b.label == "Record human decision").click().run()
    assert any("reason is required" in error.value.lower() for error in at.error)
    assert approvals.load_draft(second["draft_id"], tenant_id, "default-user")["status"] == procurement.DRAFT_STATUS
    at.text_input(key=f"approval_reason_{tenant_id}").input("Supplier delivery is too late")
    next(b for b in at.form_submit_button if b.label == "Record human decision").click().run()
    assert not at.exception, at.exception
    rejected = approvals.load_draft(second["draft_id"], tenant_id, "default-user")
    assert rejected["status"] == "REJECTED"
    assert rejected["decision"]["reason"] == "Supplier delivery is too late"


def test_ui14_policy_edit_and_copilot_context_are_bounded_and_tenant_local():
    at = fresh_app()
    tenant_id = open_business(at, "UI Policy Chat Shop")
    at.text_input(key=f"new_policy_title_{tenant_id}").input("School credit window")
    at.text_area(key=f"new_policy_body_{tenant_id}").input("Credit invoices are due in 14 days.")
    next(b for b in at.form_submit_button if b.label == "Add policy").click().run()
    custom = tenant_context.tenant_policy_dir(tenant_id) / "SHOP-school-credit-window.md"
    assert custom.is_file() and "14 days" in custom.read_text(encoding="utf-8")
    at.selectbox(key=f"policy_document_{tenant_id}").set_value(custom.name).run()
    at.text_area(key=f"policy_text_{tenant_id}_{custom.name}").input("# School credit window\n\nInvoices are due in 21 days.")
    next(b for b in at.form_submit_button if b.label == "Save this business's policy").click().run()
    assert "21 days" in custom.read_text(encoding="utf-8"), custom.read_text(encoding="utf-8")

    with patch.object(policy_qa, "answer_policy_question", return_value={
            "answer": "The edited credit policy allows 21 days.", "sources": [{"label": "SHOP-1", "title": custom.name, "section": "School credit window"}]}):
        at.text_input(key=f"policy_question_{tenant_id}").input("How long is the school credit window?")
        next(b for b in at.form_submit_button if b.label == "Ask policy").click().run()
    assert "allows 21 days" in page_text(at)
    assert not at.exception, at.exception

    # Pure context builder assertions prove compaction bounds without burning model calls.
    history = [{"question": f"question {i}", "answer": f"answer {i}", "latency_s": 1.0}
               for i in range(10)]
    context = build_copilot_context("remember blue exercise books", history, "How many should I reorder?")
    assert "question 9" in context and "question 0" not in context
    assert "remember blue exercise books" in context and "How many should I reorder?" in context
    summary = ""
    compacted_history = []
    for i in range(10):
        summary, compacted_history = compact_copilot_turn(
            summary, compacted_history, f"question {i}", f"answer {i}", 1.0)
    assert len(compacted_history) == COPILOT_RECENT_TURNS
    assert len(summary) <= COPILOT_SUMMARY_LIMIT
    compacted_context = build_copilot_context(summary, compacted_history, "current")
    assert "question 0" in summary and "question 9" in compacted_context
    assert len(compacted_context) < COPILOT_SUMMARY_LIMIT + 4 * (240 + 420) + 500


def test_ui15_copilot_context_survives_turns_and_clears_on_shop_switch():
    at = fresh_app()
    tenant_a = open_business(at, "UI Chat Shop A")
    calls = []

    def fake_agent(message, **kwargs):
        calls.append((message, kwargs["tenant_id"]))
        return {"final_text": "Two items are low; source: current_stock.csv.",
                "latency_s": 0.03, "run_id": "mock-run"}

    with patch.object(tool_agent, "run_agent", side_effect=fake_agent):
        at.text_area(key=f"assistant_question_{tenant_a}").input("What is low in stock?")
        next(b for b in at.form_submit_button if "Ask Copilot" in b.label).click().run()
        assert not at.exception, at.exception
        at.text_area(key=f"assistant_question_{tenant_a}").input("What source did you use?")
        next(b for b in at.form_submit_button if "Ask Copilot" in b.label).click().run()
        assert not at.exception, at.exception
        assert len(calls) == 2
        assert "What is low in stock?" in calls[1][0]
        assert "Two items are low" in calls[1][0]
        assert calls[1][1] == tenant_a
        assert len(at.session_state[f"copilot_history_{tenant_a}"]) == 2
        next(b for b in at.button if b.label == "Clear conversation").click().run()
        assert not at.exception, at.exception
        assert f"copilot_history_{tenant_a}" not in at.session_state

        at.radio(key="workspace_page").set_value("Operations").run()
        at.text_input(key=f"new_stock_name_{tenant_a}").input("Unsaved item from shop A")
        next(b for b in at.button if b.label == "↔ Switch shop").click().run()
        tenant_b = open_business(at, "UI Chat Shop B")
        at.radio(key="workspace_page").set_value("Operations").run()
        assert at.text_input(key=f"new_stock_name_{tenant_b}").value == ""
        at.radio(key="workspace_page").set_value("Dashboard").run()
        at.text_area(key=f"assistant_question_{tenant_b}").input("What is low in stock?")
        next(b for b in at.form_submit_button if "Ask Copilot" in b.label).click().run()
        assert not at.exception, at.exception
        assert "What source did you use?" not in calls[-1][0]
        assert calls[-1][1] == tenant_b


def test_ui09_policy_documents_are_editable_and_isolated():
    shop_a = tenant_context.business_tenant_id("Policy Shop A")
    shop_b = tenant_context.business_tenant_id("Policy Shop B")
    tenant_context.initialize_business_data(shop_a)
    tenant_context.initialize_business_data(shop_b)
    saved_root = policy_index.TENANTS_ROOT
    try:
        policy_index.TENANTS_ROOT = tenant_context.TENANTS_ROOT
        custom = tenant_context.tenant_policy_dir(shop_a) / "SHOP-credit-window.md"
        custom.write_text("# Credit Window\n\n## Custom Rule\nInvoices for saffron notebooks are due within eleven market days.",
                          encoding="utf-8")
        policy_index.get_index.cache_clear()
        result_a = search_policy("saffron notebooks eleven market days", tenant_id=shop_a)
        result_b = search_policy("saffron notebooks eleven market days", tenant_id=shop_b)
        assert result_a["results"] and "eleven market days" in result_a["results"][0]["text"]
        assert all("SHOP-credit-window" not in row["source_id"] for row in result_b["results"])
    finally:
        policy_index.TENANTS_ROOT = saved_root
        policy_index.get_index.cache_clear()


# ---------------------------------------------------------------------------
# Plain runner (pytest is not installed in this project)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    tests = [(n, f) for n, f in list(globals().items()) if n.startswith("test_") and callable(f)]
    test_filter = os.getenv("UI_TEST_FILTER", "")
    if test_filter:
        tests = [(n, f) for n, f in tests if test_filter in n]
    saved = procurement.STORAGE_PATH
    saved_state_manager = state_module.StateManager
    saved_memory_manager = memory_module.MemoryManager
    saved_tenants_root = tenant_context.TENANTS_ROOT
    passed = 0
    with tempfile.TemporaryDirectory() as folder:
        procurement.STORAGE_PATH = Path(folder) / "state.sqlite3"   # never the real database
        tenant_context.TENANTS_ROOT = Path(folder) / "tenants"
        state_db = Path(folder) / "procurement.db"
        memory_db = Path(folder) / "memory.db"
        try:
            state_module.StateManager = lambda: saved_state_manager(db_path=state_db)
            memory_module.MemoryManager = lambda: saved_memory_manager(db_path=memory_db)
            for name, fn in tests:
                try:
                    fn()
                    passed += 1
                    print(f"PASS  {name}")
                except Exception as error:
                    print(f"FAIL  {name}: {type(error).__name__}: {error}")
                    traceback.print_exc()
        finally:
            state_module.StateManager = saved_state_manager
            memory_module.MemoryManager = saved_memory_manager
            procurement.STORAGE_PATH = saved
            tenant_context.TENANTS_ROOT = saved_tenants_root
    print(f"UI checks: {passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
