"""Focused offline checks for the Week 6 central SQLite storage boundary."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from storage import SQLiteStorage, StorageError
from memory import (MemoryError, forget_usual_weekly_budget,
                     recall_usual_weekly_budget, remember_usual_weekly_budget)
from rag import index as rag_index
from tools.knowledge import search_policy
from tools import procurement, registry


def _draft(draft_id: str) -> dict:
    return {
        "draft_id": draft_id,
        "created_at": "2026-10-22T10:00:00+00:00",
        "created_by": "Arnold",
        "status": "DRAFT - AWAITING HUMAN APPROVAL",
        "lines": [{"item_id": "ITM001", "recommended_qty": 65}],
        "skipped": [],
        "estimated_budget_ugx": 30940,
        "budget_range_ugx": {"low": 27846, "high": 34034},
        "requires_override_any": False,
        "decision": None,
        "source": "synthetic test data",
    }


def test_schema_contains_week6_tables(tmp_path):
    store = SQLiteStorage(tmp_path / "state.sqlite3")
    tables = {
        row[0] for row in store._connect().execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert {"users", "sessions", "drafts", "draft_lines", "audit_events", "memories"} <= tables


def test_draft_and_audit_survive_new_storage_instance(tmp_path):
    database = tmp_path / "state.sqlite3"
    store = SQLiteStorage(database)
    store.save_draft(_draft("REQ-1"), "shop-a", "user-a")
    store.append_audit({"event_type": "CREATED", "timestamp": "2026-10-22T10:00:00+00:00"},
                       "shop-a", "user-a", "REQ-1")

    reopened = SQLiteStorage(database)
    assert reopened.load_draft("REQ-1", "shop-a", "user-a")["lines"][0]["recommended_qty"] == 65
    assert reopened.list_audit("shop-a", "user-a", "REQ-1")[0]["event_type"] == "CREATED"


def test_scope_prevents_cross_shop_draft_reads(tmp_path):
    store = SQLiteStorage(tmp_path / "state.sqlite3")
    store.save_draft(_draft("REQ-1"), "shop-a", "user-a")
    assert store.load_draft("REQ-1", "shop-b", "user-b") is None
    assert store.list_drafts("shop-b", "user-b") == []


def test_session_and_memory_are_scoped_and_deletable(tmp_path):
    store = SQLiteStorage(tmp_path / "state.sqlite3")
    store.start_session("session-a", "shop-a", "user-a")
    store.save_session_state("session-a", "shop-a", "user-a", {"budget": 300000})
    store.remember("shop-a", "user-a", "usual_weekly_budget", 300000)

    assert store.load_session_state("session-a", "shop-a", "user-a") == {"budget": 300000}
    assert store.recall("shop-b", "user-b", "usual_weekly_budget") is None
    assert store.recall("shop-a", "user-a", "usual_weekly_budget") == 300000
    store.delete_memory("shop-a", "user-a", "usual_weekly_budget")
    assert store.recall("shop-a", "user-a", "usual_weekly_budget") is None


def test_missing_scope_is_rejected(tmp_path):
    store = SQLiteStorage(tmp_path / "state.sqlite3")
    try:
        store.list_drafts("", "user-a")
    except StorageError as error:
        assert "tenant_id" in str(error)
    else:
        raise AssertionError("missing tenant scope should be rejected")


def test_registry_injects_scope_and_blocks_cross_shop_review(tmp_path):
    """The model cannot select scope; the trusted context owns draft isolation."""
    saved_data, saved_storage, saved_trace = procurement.DATA_DIR, procurement.STORAGE_PATH, registry.TRACE_PATH
    try:
        procurement.DATA_DIR = Path("data")
        procurement.STORAGE_PATH = tmp_path / "state.sqlite3"
        registry.TRACE_PATH = tmp_path / "tool-traces.jsonl"
        result, status = registry.execute_tool(
            "draft_requisition", {"items": ["ITM001"]},
            context={"created_by": "Alice", "tenant_id": "shop-a", "user_id": "alice"},
        )
        assert status == "ok"
        draft_id = result["draft_id"]
        store = SQLiteStorage(procurement.STORAGE_PATH)
        assert store.load_draft(draft_id, "shop-a", "alice") is not None
        assert store.load_draft(draft_id, "shop-b", "bob") is None
        assert "tenant_id" not in result
    finally:
        procurement.DATA_DIR, procurement.STORAGE_PATH, registry.TRACE_PATH = (
            saved_data, saved_storage, saved_trace
        )


def test_model_cannot_supply_shop_context(tmp_path):
    """Protected identity fields are rejected before a tool can run."""
    saved_trace = registry.TRACE_PATH
    try:
        registry.TRACE_PATH = tmp_path / "tool-traces.jsonl"
        result, status = registry.execute_tool(
            "draft_requisition",
            {"items": ["ITM001"], "tenant_id": "shop-b", "user_id": "bob"},
            context={"created_by": "Alice", "tenant_id": "shop-a", "user_id": "alice"},
        )
        assert status == "invalid"
        assert result["error"].startswith("INVALID_PARAMETER: trusted context")
    finally:
        registry.TRACE_PATH = saved_trace


def test_usual_weekly_budget_memory_is_explicit_scoped_and_deletable(tmp_path):
    """The one allowed memory helps choose a default but never makes a decision."""
    store = SQLiteStorage(tmp_path / "state.sqlite3")
    remember_usual_weekly_budget(store, "shop-a", "alice", 300000)
    assert recall_usual_weekly_budget(store, "shop-a", "alice") == 300000
    assert recall_usual_weekly_budget(store, "shop-b", "bob") is None
    try:
        remember_usual_weekly_budget(store, "shop-a", "alice", 0)
        raise AssertionError("invalid budget was remembered")
    except MemoryError:
        pass
    forget_usual_weekly_budget(store, "shop-a", "alice")
    assert recall_usual_weekly_budget(store, "shop-a", "alice") is None


def test_rag_index_isolated_by_tenant(tmp_path):
    """Distinct tenant corpora produce distinct cached indexes and results."""
    saved_root, saved_corpus = rag_index.TENANTS_ROOT, rag_index.CORPUS_DIR
    try:
        rag_index.TENANTS_ROOT = tmp_path / "tenants"
        rag_index.CORPUS_DIR = tmp_path / "fallback"
        policies = {
            "shop-a": {
                "POL-01_policy.md": "# Shop A\n## Approval\nShop A approves blue pens for stationery restocking and blue pen safety checks.",
                "POL-02_policy.md": "# Shop A\n## Returns\nShop A records ordinary stationery returns.",
                "POL-03_policy.md": "# Shop A\n## Delivery\nShop A checks supplier delivery dates.",
            },
            "shop-b": {
                "POL-01_policy.md": "# Shop B\n## Approval\nShop B approves red files for office archiving and red file safety checks.",
                "POL-02_policy.md": "# Shop B\n## Returns\nShop B records ordinary office returns.",
                "POL-03_policy.md": "# Shop B\n## Delivery\nShop B checks supplier delivery dates.",
            },
        }
        for tenant, files in policies.items():
            corpus = rag_index.TENANTS_ROOT / tenant / "knowledge" / "corpus"
            corpus.mkdir(parents=True)
            for filename, policy in files.items():
                (corpus / filename).write_text(policy, encoding="utf-8")
        rag_index.get_index.cache_clear()
        a = search_policy("blue pen stationery restocking", tenant_id="shop-a")
        b = search_policy("blue pen stationery restocking", tenant_id="shop-b")
        assert a["results"] and "blue pens" in a["results"][0]["text"]
        assert not b["results"]
        assert rag_index.get_index("shop-a") is not rag_index.get_index("shop-b")
    finally:
        rag_index.TENANTS_ROOT, rag_index.CORPUS_DIR = saved_root, saved_corpus
        rag_index.get_index.cache_clear()