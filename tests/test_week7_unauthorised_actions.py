"""Week 7 tests for unauthorised actions and cross-shop access."""

import gc
import tempfile
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src")]

import approvals  # noqa: E402
from storage import SQLiteStorage, StorageError  # noqa: E402
from tools import procurement, registry  # noqa: E402


def _draft(draft_id="REQ-W7-UNAUTH"):
    return {
        "draft_id": draft_id,
        "created_at": "2026-10-23T10:00:00+00:00",
        "created_by": "alice",
        "status": "DRAFT - AWAITING HUMAN APPROVAL",
        "lines": [{"item_id": "ITM001", "recommended_qty": 65, "unit_price_ugx": 476,
                   "total_cost_ugx": 30940}],
        "skipped": [],
        "estimated_budget_ugx": 30940,
        "budget_range_ugx": {"low": 27846, "high": 34034},
        "requires_override_any": False,
        "decision": None,
        "source": "synthetic test data",
    }


def test_approve_order_pay_and_contact_are_unavailable():
    """The model cannot turn a draft into an external action."""
    with tempfile.TemporaryDirectory() as directory:
        saved_trace = registry.TRACE_PATH
        try:
            registry.TRACE_PATH = Path(directory) / "tool-traces.jsonl"
            for name in ("approve_requisition", "order_purchase", "pay_supplier", "contact_supplier"):
                result, status = registry.execute_tool(name, {"draft_id": "REQ-W7-UNAUTH"})
                assert status == "blocked"
                assert result["error"].startswith("UNAUTHORIZED_TOOL")

            names = {declaration["name"] for declaration in registry.tool_declarations()}
            assert not names.intersection({"approve_requisition", "order_purchase", "pay_supplier", "contact_supplier"})
        finally:
            registry.TRACE_PATH = saved_trace


def test_only_human_approval_path_can_decide():
    """Approval is explicit, named, and cannot be changed by a later request."""
    with tempfile.TemporaryDirectory() as directory:
        saved_storage = procurement.STORAGE_PATH
        try:
            procurement.STORAGE_PATH = Path(directory) / "state.sqlite3"
            store = SQLiteStorage(procurement.STORAGE_PATH)
            store.save_draft(_draft(), "shop-a", "alice")
            approved = approvals.decide("REQ-W7-UNAUTH", "APPROVED", "Alice", tenant_id="shop-a", user_id="alice")
            assert approved["status"] == "APPROVED"
            try:
                approvals.decide("REQ-W7-UNAUTH", "REJECTED", "Alice", "changed mind",
                                 tenant_id="shop-a", user_id="alice")
                raise AssertionError("a second decision was allowed")
            except approvals.ApprovalError:
                pass
        finally:
            procurement.STORAGE_PATH = saved_storage
            gc.collect()


def test_cross_shop_draft_audit_session_and_memory_access_is_empty():
    """A shop cannot read another shop's persisted state."""
    with tempfile.TemporaryDirectory() as directory:
        store = SQLiteStorage(Path(directory) / "state.sqlite3")
        store.save_draft(_draft(), "shop-a", "alice")
        store.append_audit({"event_type": "CREATED"}, "shop-a", "alice", "REQ-W7-UNAUTH")
        store.start_session("session-a", "shop-a", "alice")
        store.save_session_state("session-a", "shop-a", "alice", {"secret": "shop-a-only"})
        store.remember("shop-a", "alice", "usual_weekly_budget", 300000)

        assert store.load_draft("REQ-W7-UNAUTH", "shop-b", "bob") is None
        assert store.list_drafts("shop-b", "bob") == []
        assert store.list_audit("shop-b", "bob") == []
        assert store.load_session_state("session-a", "shop-b", "bob") is None
        assert store.recall("shop-b", "bob", "usual_weekly_budget") is None
        try:
            store.save_session_state("session-a", "shop-b", "bob", {"secret": "leak"})
            raise AssertionError("cross-shop session update was allowed")
        except StorageError:
            pass
        del store
        gc.collect()


def test_model_cannot_choose_another_shop_for_draft_or_inventory():
    """Trusted scope is application-owned; shared CSV tools reject scope arguments."""
    with tempfile.TemporaryDirectory() as directory:
        saved_trace = registry.TRACE_PATH
        try:
            registry.TRACE_PATH = Path(directory) / "tool-traces.jsonl"
            result, status = registry.execute_tool(
                "draft_requisition",
                {"items": ["ITM001"], "tenant_id": "shop-b", "user_id": "bob"},
                context={"created_by": "Alice", "tenant_id": "shop-a", "user_id": "alice"},
            )
            assert status == "invalid"
            assert result["error"].startswith("INVALID_PARAMETER: trusted context")

            result, status = registry.execute_tool(
                "get_inventory", {"tenant_id": "shop-b"},
                context={"created_by": "Alice", "tenant_id": "shop-a", "user_id": "alice"},
            )
            assert status == "invalid"
            assert "tenant_id" in result["error"]
        finally:
            registry.TRACE_PATH = saved_trace


def main():
    test_approve_order_pay_and_contact_are_unavailable()
    test_only_human_approval_path_can_decide()
    test_cross_shop_draft_audit_session_and_memory_access_is_empty()
    test_model_cannot_choose_another_shop_for_draft_or_inventory()
    print("Week 7 unauthorised-action checks: 4/4 passed")


if __name__ == "__main__":
    main()