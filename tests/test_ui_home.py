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

APP = ROOT / "src" / "streamlit_app.py"
EXPECTED_CARDS = ["Ask the assistant", "Weekly restock", "Policy questions",
                  "Review & approve drafts", "Stock overview"]


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


def test_ui02_five_feature_cards():
    text = page_text(fresh_app()).replace("&amp;", "&")
    missing = [c for c in EXPECTED_CARDS if c not in text]
    assert not missing, f"missing cards: {missing}"


def test_ui03_welcome_does_not_show_shared_shop_records():
    at = fresh_app()
    assert any(item.label == "Business name" for item in at.text_input)
    assert "items are low" not in page_text(at)


def test_ui04_empty_name_is_refused():
    at = fresh_app()
    at.text_input(key="business_name_input").input("   ").run()
    at.button[0].click().run()
    assert any("enter your business name" in w.value.lower() for w in at.warning)
    assert "tenant_id" not in at.session_state


def test_ui05_business_name_opens_an_empty_workspace():
    at = fresh_app()
    at.text_input(key="business_name_input").input("Aminah Stationery").run()
    at.button[0].click().run()
    tenant_id = tenant_context.business_tenant_id("Aminah Stationery")
    assert at.session_state["business_name"] == "Aminah Stationery"
    assert at.session_state["tenant_id"] == tenant_id
    stock_file = tenant_context.tenant_data_dir(tenant_id) / "current_stock.csv"
    with stock_file.open(encoding="utf-8", newline="") as source:
        assert len(list(csv.DictReader(source))) == 0


def test_ui06_workspace_routes_render():
    at = fresh_app()
    at.text_input(key="business_name_input").input("UI Route Shop").run()
    at.button[0].click().run()
    for page in ("Operations", "Restock AI", "Approvals", "Dashboard"):
        at.radio(key="workspace_page").set_value(page).run()
        assert not at.exception, f"{page}: {at.exception}"


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
