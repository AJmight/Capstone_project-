"""Week 7 tests for tenant-scoped traces and retention."""

import json
import gc
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src")]

from storage import SQLiteStorage  # noqa: E402
from tools import registry, procurement  # noqa: E402


def _draft():
    return {
        "draft_id": "REQ-TRACE-1", "created_at": "2026-10-23T10:00:00+00:00",
        "created_by": "alice", "status": "DRAFT - AWAITING HUMAN APPROVAL",
        "lines": [], "skipped": [], "estimated_budget_ugx": 0,
        "budget_range_ugx": {"low": 0, "high": 0}, "requires_override_any": False,
        "decision": None, "source": "test",
    }


def test_trace_scope_is_queryable_but_payload_is_redacted():
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "state.sqlite3"
        with patch.dict(os.environ, {"TRACE_REDACTION": "on"}, clear=False):
            store = SQLiteStorage(database)
            store.append_trace(
                {"user_message": "secret question", "answer": "secret answer", "status": "ok"},
                "shop-a", "alice", session_id="session-a", run_id="run-a", event_type="agent",
            )
            store.append_trace({"status": "other"}, "shop-b", "bob", event_type="tool")
            own = store.list_traces("shop-a", "alice")
            other = store.list_traces("shop-b", "bob")
            assert len(own) == 1 and len(other) == 1
            assert own[0]["tenant_id"] == "shop-a"
            assert own[0]["user_id"] == "alice"
            assert own[0]["session_id"] == "session-a"
            assert own[0]["payload"]["user_message"] == "[REDACTED]"
            assert own[0]["payload"]["answer"] == "[REDACTED]"
            assert store.list_traces("shop-a", "bob") == []
            del store
            gc.collect()


def test_expired_traces_are_deleted_without_deleting_drafts():
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "state.sqlite3"
        store = SQLiteStorage(database)
        store.save_draft(_draft(), "shop-a", "alice")
        store.append_trace({"status": "old"}, "shop-a", "alice", retention_days=1,
                            created_at="2020-01-01T00:00:00+00:00")
        assert store.delete_expired_traces("2026-10-23T00:00:00+00:00") == 1
        store.append_trace({"status": "new"}, "shop-a", "alice", retention_days=30,
                    created_at="2026-10-23T00:00:00+00:00")
        traces = store.list_traces("shop-a", "alice", include_expired=True)
        assert [trace["payload"]["status"] for trace in traces] == ["new"]
        assert store.load_draft("REQ-TRACE-1", "shop-a", "alice") is not None
        del store
        gc.collect()


def test_registry_writes_a_scoped_trace_event():
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "state.sqlite3"
        saved_storage, saved_trace = procurement.STORAGE_PATH, registry.TRACE_PATH
        try:
            procurement.STORAGE_PATH = database
            registry.TRACE_PATH = Path(directory) / "tool.jsonl"
            with patch.dict(os.environ, {"TRACE_REDACTION": "on"}, clear=False):
                result, status = registry.execute_tool(
                    "get_inventory", {},
                    context={"created_by": "Alice", "tenant_id": "shop-a",
                             "user_id": "alice", "session_id": "session-a"},
                    run_id="run-a",
                )
            assert status == "ok" and "items" in result
            traces = SQLiteStorage(database).list_traces("shop-a", "alice", session_id="session-a")
            assert len(traces) == 1
            assert traces[0]["run_id"] == "run-a"
            assert traces[0]["event_type"] == "tool"
            assert traces[0]["payload"]["status"] == "ok"
            gc.collect()
        finally:
            procurement.STORAGE_PATH, registry.TRACE_PATH = saved_storage, saved_trace


def main():
    test_trace_scope_is_queryable_but_payload_is_redacted()
    test_expired_traces_are_deleted_without_deleting_drafts()
    test_registry_writes_a_scoped_trace_event()
    print("Week 7 trace scope and retention checks: 3/3 passed")


if __name__ == "__main__":
    main()