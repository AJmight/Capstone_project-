"""Week 7 tests for optional trace redaction."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src")]

from trace_privacy import redact_record  # noqa: E402
from tools import registry  # noqa: E402


def test_redaction_is_off_by_default():
    with patch.dict(os.environ, {"TRACE_REDACTION": "off"}, clear=False):
        record = {"user_message": "sentinel message", "status": "ok"}
        assert redact_record(record) == record


def test_redaction_removes_nested_sensitive_values_but_keeps_metadata():
    with patch.dict(os.environ, {"TRACE_REDACTION": "on"}, clear=False):
        record = {
            "tool": "get_inventory",
            "status": "ok",
            "latency_ms": 1.2,
            "tenant_id": "tenant-secret",
            "user_id": "user-secret",
            "steps": [{"model_text": "model-secret", "tool_calls": [{"args": {"secret": "payload"}}]}],
        }
        redacted = redact_record(record)
        encoded = json.dumps(redacted)
        assert "tenant-secret" not in encoded
        assert "user-secret" not in encoded
        assert "model-secret" not in encoded
        assert "payload" not in encoded
        assert redacted["tool"] == "get_inventory"
        assert redacted["status"] == "ok"
        assert redacted["latency_ms"] == 1.2


def test_registry_trace_redacts_identity_arguments_and_result():
    with tempfile.TemporaryDirectory() as directory:
        trace_path = Path(directory) / "tool-traces.jsonl"
        saved_trace = registry.TRACE_PATH
        try:
            registry.TRACE_PATH = trace_path
            with patch.dict(os.environ, {"TRACE_REDACTION": "true"}, clear=False):
                registry.execute_tool(
                    "get_inventory", {},
                    context={"created_by": "Alice Secret", "tenant_id": "tenant-secret", "user_id": "user-secret"},
                    run_id="run-visible",
                )
            record = json.loads(trace_path.read_text(encoding="utf-8"))
            encoded = json.dumps(record)
            assert "Alice Secret" not in encoded
            assert "tenant-secret" not in encoded
            assert "user-secret" not in encoded
            assert record["run_id"] == "run-visible"
            assert record["tool"] == "get_inventory"
            assert record["status"] == "ok"
            assert "latency_ms" in record
        finally:
            registry.TRACE_PATH = saved_trace


def main():
    test_redaction_is_off_by_default()
    test_redaction_removes_nested_sensitive_values_but_keeps_metadata()
    test_registry_trace_redacts_identity_arguments_and_result()
    print("Week 7 log redaction checks: 3/3 passed")


if __name__ == "__main__":
    main()