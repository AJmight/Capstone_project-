"""
Central SQLite persistence for Week 6.
======================================

This module is the single storage boundary for state that must survive a
process restart.  Business rules remain in the procurement and approval
modules; this module only stores and retrieves validated records.

Every shop-scoped record carries tenant_id and user_id.  The caller supplies
those values from trusted application context.  The model must never choose
them.

The first migration slice covers drafts, audit events, sessions, users and
the small memory store planned for Week 6.  Existing JSON files remain the
compatibility path until the callers are migrated and their regression tests
have passed.
"""

# ---------------------------------------------------------------------------
# Imports and configuration
# ---------------------------------------------------------------------------
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path("data/state.sqlite3")
DEFAULT_TENANT_ID = "default-shop"
DEFAULT_USER_ID = "default-user"


class StorageError(Exception):
    """Raised when a storage operation receives an invalid record or scope."""


def _now() -> str:
    """Return a stable UTC timestamp for persisted records."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SQLiteStorage:
    """Small, explicit SQLite repository shared by tools and approvals."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        """Open a connection with row dictionaries and foreign keys enabled."""
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialise(self) -> None:
        """Create the Week 6 schema safely when the database is first used."""
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    state_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (tenant_id, user_id)
                        REFERENCES users (tenant_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS drafts (
                    draft_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    status TEXT NOT NULL,
                    estimated_budget_ugx INTEGER NOT NULL,
                    budget_range_json TEXT NOT NULL,
                    requires_override_any INTEGER NOT NULL DEFAULT 0,
                    decision_json TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (tenant_id, user_id)
                        REFERENCES users (tenant_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS draft_lines (
                    draft_id TEXT NOT NULL,
                    line_number INTEGER NOT NULL,
                    line_json TEXT NOT NULL,
                    PRIMARY KEY (draft_id, line_number),
                    FOREIGN KEY (draft_id) REFERENCES drafts (draft_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    draft_id TEXT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    FOREIGN KEY (tenant_id, user_id)
                        REFERENCES users (tenant_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS memories (
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    memory_key TEXT NOT NULL,
                    memory_value_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT,
                    PRIMARY KEY (tenant_id, user_id, memory_key),
                    FOREIGN KEY (tenant_id, user_id)
                        REFERENCES users (tenant_id, user_id)
                );
                """
            )

    @staticmethod
    def _require_scope(tenant_id: str, user_id: str) -> None:
        """Reject missing scope rather than accidentally using global state."""
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise StorageError("tenant_id is required")
        if not isinstance(user_id, str) or not user_id.strip():
            raise StorageError("user_id is required")

    def ensure_user(self, tenant_id: str, user_id: str, display_name: str) -> None:
        """Register the trusted application user for a shop."""
        self._require_scope(tenant_id, user_id)
        if not display_name.strip():
            raise StorageError("display_name is required")
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO users (tenant_id, user_id, display_name, created_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT (tenant_id, user_id) DO UPDATE SET display_name = excluded.display_name""",
                (tenant_id, user_id, display_name, _now()),
            )

    def save_draft(self, draft: dict[str, Any], tenant_id: str, user_id: str) -> None:
        """Insert or replace a draft and its line records atomically."""
        self._require_scope(tenant_id, user_id)
        required = {"draft_id", "created_at", "created_by", "status", "lines",
                    "estimated_budget_ugx", "budget_range_ugx"}
        missing = required.difference(draft)
        if missing:
            raise StorageError(f"draft is missing fields: {', '.join(sorted(missing))}")
        self.ensure_user(tenant_id, user_id, draft["created_by"])
        with self._connect() as connection:
            connection.execute("DELETE FROM drafts WHERE draft_id = ?", (draft["draft_id"],))
            connection.execute(
                """INSERT INTO drafts
                   (draft_id, tenant_id, user_id, created_at, created_by, status,
                    estimated_budget_ugx, budget_range_json, requires_override_any,
                    decision_json, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (draft["draft_id"], tenant_id, user_id, draft["created_at"],
                 draft["created_by"], draft["status"], draft["estimated_budget_ugx"],
                 json.dumps(draft["budget_range_ugx"]),
                 int(bool(draft.get("requires_override_any", False))),
                 json.dumps(draft.get("decision")) if draft.get("decision") is not None else None,
                 json.dumps({key: value for key, value in draft.items()
                             if key not in required and key not in {"decision", "requires_override_any"}})),
            )
            connection.executemany(
                "INSERT INTO draft_lines (draft_id, line_number, line_json) VALUES (?, ?, ?)",
                [(draft["draft_id"], number, json.dumps(line))
                 for number, line in enumerate(draft["lines"])]
            )

    def load_draft(self, draft_id: str, tenant_id: str, user_id: str) -> dict[str, Any] | None:
        """Load one draft only when it belongs to the supplied shop and user."""
        self._require_scope(tenant_id, user_id)
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM drafts
                   WHERE draft_id = ? AND tenant_id = ? AND user_id = ?""",
                (draft_id, tenant_id, user_id),
            ).fetchone()
            if row is None:
                return None
            lines = connection.execute(
                "SELECT line_json FROM draft_lines WHERE draft_id = ? ORDER BY line_number",
                (draft_id,),
            ).fetchall()
        draft = json.loads(row["metadata_json"])
        draft.update({
            "draft_id": row["draft_id"], "created_at": row["created_at"],
            "created_by": row["created_by"], "status": row["status"],
            "lines": [json.loads(line["line_json"]) for line in lines],
            "estimated_budget_ugx": row["estimated_budget_ugx"],
            "budget_range_ugx": json.loads(row["budget_range_json"]),
            "requires_override_any": bool(row["requires_override_any"]),
            "decision": json.loads(row["decision_json"]) if row["decision_json"] else None,
        })
        return draft

    def list_drafts(self, tenant_id: str, user_id: str) -> list[dict[str, Any]]:
        """Return summaries for only the current shop and user."""
        self._require_scope(tenant_id, user_id)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT draft_id, created_at, created_by, status,
                          estimated_budget_ugx, requires_override_any
                   FROM drafts WHERE tenant_id = ? AND user_id = ?
                   ORDER BY created_at DESC""",
                (tenant_id, user_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_draft(self, draft: dict[str, Any], tenant_id: str, user_id: str) -> None:
        """Persist an edited or human-decided draft using the same scoped record."""
        self.save_draft(draft, tenant_id, user_id)

    def append_audit(self, event: dict[str, Any], tenant_id: str, user_id: str,
                     draft_id: str | None = None) -> int:
        """Append one scoped audit event and return its database identifier."""
        self._require_scope(tenant_id, user_id)
        event_type = event.get("event_type", "UNKNOWN")
        timestamp = event.get("timestamp", _now())
        self.ensure_user(tenant_id, user_id, event.get("decided_by", user_id))
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO audit_events
                   (tenant_id, user_id, draft_id, timestamp, event_type, event_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (tenant_id, user_id, draft_id, timestamp, event_type, json.dumps(event)),
            )
            return int(cursor.lastrowid)

    def list_audit(self, tenant_id: str, user_id: str, draft_id: str | None = None) -> list[dict[str, Any]]:
        """Return audit events scoped to the current shop and user."""
        self._require_scope(tenant_id, user_id)
        query = """SELECT event_json FROM audit_events
                   WHERE tenant_id = ? AND user_id = ?"""
        parameters: list[Any] = [tenant_id, user_id]
        if draft_id is not None:
            query += " AND draft_id = ?"
            parameters.append(draft_id)
        query += " ORDER BY event_id"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [json.loads(row["event_json"]) for row in rows]

    def start_session(self, session_id: str, tenant_id: str, user_id: str) -> None:
        """Create a scoped session with empty state."""
        self._require_scope(tenant_id, user_id)
        self.ensure_user(tenant_id, user_id, user_id)
        with self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO sessions
                   (session_id, tenant_id, user_id, started_at, state_json)
                   VALUES (?, ?, ?, ?, '{}')""",
                (session_id, tenant_id, user_id, _now()),
            )

    def save_session_state(self, session_id: str, tenant_id: str, user_id: str,
                           state: dict[str, Any]) -> None:
        """Replace state only for a session in the supplied scope."""
        self._require_scope(tenant_id, user_id)
        with self._connect() as connection:
            updated = connection.execute(
                """UPDATE sessions SET state_json = ?
                   WHERE session_id = ? AND tenant_id = ? AND user_id = ?""",
                (json.dumps(state), session_id, tenant_id, user_id),
            ).rowcount
        if updated != 1:
            raise StorageError("session not found in the supplied scope")

    def load_session_state(self, session_id: str, tenant_id: str, user_id: str) -> dict[str, Any] | None:
        """Read session state only for the supplied scope."""
        self._require_scope(tenant_id, user_id)
        with self._connect() as connection:
            row = connection.execute(
                """SELECT state_json FROM sessions
                   WHERE session_id = ? AND tenant_id = ? AND user_id = ?""",
                (session_id, tenant_id, user_id),
            ).fetchone()
        return json.loads(row["state_json"]) if row else None

    def remember(self, tenant_id: str, user_id: str, memory_key: str, value: Any,
                 expires_at: str | None = None) -> None:
        """Store one explicit, replaceable memory value in a user/shop scope."""
        self._require_scope(tenant_id, user_id)
        if not memory_key.strip():
            raise StorageError("memory_key is required")
        self.ensure_user(tenant_id, user_id, user_id)
        now = _now()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO memories
                   (tenant_id, user_id, memory_key, memory_value_json, created_at, updated_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (tenant_id, user_id, memory_key) DO UPDATE SET
                     memory_value_json = excluded.memory_value_json,
                     updated_at = excluded.updated_at,
                     expires_at = excluded.expires_at""",
                (tenant_id, user_id, memory_key, json.dumps(value), now, now, expires_at),
            )

    def recall(self, tenant_id: str, user_id: str, memory_key: str) -> Any | None:
        """Return a non-expired memory value from the exact scope, if present."""
        self._require_scope(tenant_id, user_id)
        with self._connect() as connection:
            row = connection.execute(
                """SELECT memory_value_json, expires_at FROM memories
                   WHERE tenant_id = ? AND user_id = ? AND memory_key = ?""",
                (tenant_id, user_id, memory_key),
            ).fetchone()
        if row is None:
            return None
        if row["expires_at"] and row["expires_at"] <= _now():
            self.delete_memory(tenant_id, user_id, memory_key)
            return None
        return json.loads(row["memory_value_json"])

    def delete_memory(self, tenant_id: str, user_id: str, memory_key: str) -> None:
        """Delete one memory value, supporting the Week 6 deletion requirement."""
        self._require_scope(tenant_id, user_id)
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM memories WHERE tenant_id = ? AND user_id = ? AND memory_key = ?",
                (tenant_id, user_id, memory_key),
            )