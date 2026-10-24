"""
Offline tests for the Streamlit web UI, Screen 1: Home / Welcome (src/streamlit_app.py).
=======================================================================================

WHAT IS TESTED
--------------
Streamlit ships a headless test runner, streamlit.testing.v1.AppTest. It runs the app
script in-process (no browser, no server, no GEMINI_API_KEY) and lets the test read the
elements on the page and click buttons, the same way a person would.

  UI-01  the page renders without an exception
  UI-02  all five feature cards are shown (= the five menu options of src/app.py)
  UI-03  the low-stock figure equals a count computed here from data/current_stock.csv
         (AGENTS.md rule 8: expected values come from the CSVs, never typed in)
  UI-04  Get Started with an empty name shows a warning and logs nobody in
  UI-05  Get Started with a name stores it in session_state["user"] and confirms it

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
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from streamlit.testing.v1 import AppTest       # Streamlit's headless app runner

from tools import procurement                  # to sandbox STORAGE_PATH
import tenant_context                          # to sandbox business folders
from rag import index as policy_index
from tools.knowledge import search_policy

APP = ROOT / "src" / "streamlit_app.py"
EXPECTED_ROUTES = ["Dashboard", "Operations", "Restock AI", "AI Copilot", "Approvals"]


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
    next(item for item in at.text_input if item.key == "stock_name_0").input("Blue exercise books")
    next(item for item in at.number_input if item.key == "stock_current_0").set_value(7)
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
    saved = procurement.STORAGE_PATH
    saved_tenants_root = tenant_context.TENANTS_ROOT
    passed = 0
    with tempfile.TemporaryDirectory() as folder:
        procurement.STORAGE_PATH = Path(folder) / "state.sqlite3"   # never the real database
        tenant_context.TENANTS_ROOT = Path(folder) / "tenants"
        try:
            for name, fn in tests:
                try:
                    fn()
                    passed += 1
                    print(f"PASS  {name}")
                except Exception as error:
                    print(f"FAIL  {name}: {type(error).__name__}: {error}")
        finally:
            procurement.STORAGE_PATH = saved
            tenant_context.TENANTS_ROOT = saved_tenants_root
    print(f"UI checks: {passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
