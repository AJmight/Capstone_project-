"""Optional redaction for persisted traces."""

import os
from typing import Any


REDACTED = "[REDACTED]"
REDACT_KEYS = {
    "answer", "args", "created_by", "decided_by", "detail", "final_text",
    "handoffs", "model_text", "question", "reason", "result", "state",
    "tenant_id", "text", "timeline", "user", "user_id", "user_message",
}


def redaction_enabled() -> bool:
    """Read the setting at write time so tests can toggle it safely."""
    return os.getenv("TRACE_REDACTION", "off").strip().lower() in {"1", "true", "yes", "on"}


def redact_record(value: Any) -> Any:
    """Recursively redact sensitive fields while preserving trace structure."""
    if not redaction_enabled():
        return value
    if isinstance(value, dict):
        return {key: REDACTED if key.lower() in REDACT_KEYS else redact_record(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact_record(item) for item in value]
    if isinstance(value, tuple):
        return [redact_record(item) for item in value]
    return value