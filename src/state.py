"""
src/state.py
=============================================================================
Explicit Workflow and Session State Model (Week 6 Deliverable)
=============================================================================

ACADEMIC CONTEXT:
  BSE4104 Emerging Trends in Software Engineering (Makerere University)
  Capstone Project: SME Procurement Preparation Agent
  Author: Mwesigwa Arnold Mugahi (Reg No: 23/U/24738/PS, GitHub: AJmight)

PURPOSE:
  Foundation models are fundamentally stateless: each API call is independent.
  To build a dependable, multi-step agentic system, workflow state MUST be
  modeled explicitly outside the LLM in deterministic software.

  This module implements a persistent Finite State Machine (FSM) using SQLite
  to track procurement workflow lifecycles from initialization, through stock
  sensing, planning, drafting, and explicit human approval.

KEY DATA FLOWS:
  - INPUT: Initialized by restock_agent.py or tool_agent.py with shop_id,
           user_name, and allocated budget.
  - STORAGE: Persisted to SQLite database at data/procurement.db.
  - TRANSITIONS: Validated against permissible transition graph before updates.
  - OUTPUT: Provides audited state snapshots to restock_agent.py, approvals.py,
            and evaluation traces in evidence/.
=============================================================================
"""

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Default Database Location
# ---------------------------------------------------------------------------
# Stored in the project's data/ directory to ensure persistent storage across runs.
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "procurement.db"


class WorkflowStage(str, Enum):
    """
    Permissible lifecycle stages of the SME procurement preparation workflow.
    Each stage represents a bounded milestone in the Restock Agent loop.
    """
    INITIALIZED = "INITIALIZED"                    # Session created, preconditions checked
    SENSING_INVENTORY = "SENSING_INVENTORY"        # Querying stock levels and reorder thresholds
    PLANNING_RESTOCK = "PLANNING_RESTOCK"          # Ranking urgency and optimizing within budget
    DRAFTING_ORDER = "DRAFTING_ORDER"              # Generating formal requisition draft
    AWAITING_APPROVAL = "AWAITING_APPROVAL"        # Requisition draft ready; waiting for human owner
    APPROVED = "APPROVED"                          # Explicitly approved by SME owner in approvals.py
    REJECTED = "REJECTED"                          # Rejected or cancelled by SME owner with reason
    TERMINATED = "TERMINATED"                      # Stopped safely (e.g. nothing low, budget failure)


# ---------------------------------------------------------------------------
# Permissible State Transition Graph
# ---------------------------------------------------------------------------
# Enforces that the agent cannot jump stages or skip human approval.
# E.g., it is IMPOSSIBLE to transition directly from SENSING to APPROVED.
VALID_TRANSITIONS: Dict[WorkflowStage, List[WorkflowStage]] = {
    WorkflowStage.INITIALIZED: [
        WorkflowStage.SENSING_INVENTORY,
        WorkflowStage.TERMINATED,
    ],
    WorkflowStage.SENSING_INVENTORY: [
        WorkflowStage.PLANNING_RESTOCK,
        WorkflowStage.TERMINATED,                  # If nothing is low stock (NOTHING_TO_DO)
    ],
    WorkflowStage.PLANNING_RESTOCK: [
        WorkflowStage.DRAFTING_ORDER,
        WorkflowStage.TERMINATED,                  # If budget too small to buy anything
    ],
    WorkflowStage.DRAFTING_ORDER: [
        WorkflowStage.AWAITING_APPROVAL,
        WorkflowStage.TERMINATED,                  # If tool failure or validation error
    ],
    WorkflowStage.AWAITING_APPROVAL: [
        WorkflowStage.APPROVED,                    # Can ONLY be triggered by human in approvals.py
        WorkflowStage.REJECTED,                    # Triggered by human rejection
        WorkflowStage.TERMINATED,
    ],
    WorkflowStage.APPROVED: [],                    # Terminal state
    WorkflowStage.REJECTED: [],                    # Terminal state
    WorkflowStage.TERMINATED: [],                  # Terminal state
}


@dataclass
class SessionState:
    """
    Represents an active or historic procurement session snapshot.
    """
    session_id: str
    shop_id: str
    user_name: str
    budget_ugx: int
    stage: WorkflowStage = WorkflowStage.INITIALIZED
    low_stock_count: int = 0
    draft_id: Optional[str] = None
    draft_total_ugx: int = 0
    approval_status: str = "NONE"                  # NONE, PENDING, APPROVED, REJECTED
    turn_count: int = 0
    tool_call_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to serializable dictionary format."""
        data = asdict(self)
        data["stage"] = self.stage.value if isinstance(self.stage, WorkflowStage) else str(self.stage)
        return data


class StateManager:
    """
    Database-backed State Manager implementing workflow persistence and audit trails.
    Guarantees thread-safe SQLite operations and validates transition safety.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize connection to SQLite state database.
        
        Args:
            db_path: Path to SQLite database file. Defaults to data/procurement.db.
        """
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        # Ensure parent directory exists (data/)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Create database tables and indices if they do not already exist."""
        with self.conn:
            # 1. Main sessions table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS procurement_sessions (
                    session_id TEXT PRIMARY KEY,
                    shop_id TEXT NOT NULL,
                    user_name TEXT NOT NULL,
                    budget_ugx INTEGER NOT NULL,
                    stage TEXT NOT NULL,
                    low_stock_count INTEGER DEFAULT 0,
                    draft_id TEXT,
                    draft_total_ugx INTEGER DEFAULT 0,
                    approval_status TEXT DEFAULT 'NONE',
                    turn_count INTEGER DEFAULT 0,
                    tool_call_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT DEFAULT '{}'
                )
            """)

            # 2. Audit log of all state transitions
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS state_transitions (
                    transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    from_stage TEXT NOT NULL,
                    to_stage TEXT NOT NULL,
                    reason TEXT,
                    transitioned_at TEXT NOT NULL,
                    metadata_json TEXT DEFAULT '{}',
                    FOREIGN KEY (session_id) REFERENCES procurement_sessions(session_id)
                )
            """)

            # Indices for rapid querying by shop_id and session_id
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_shop ON procurement_sessions(shop_id)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_transitions_session ON state_transitions(session_id)")

    def create_session(self, shop_id: str, user_name: str, budget_ugx: int, session_id: Optional[str] = None) -> SessionState:
        """
        Create and record a new procurement workflow session.

        Args:
            shop_id: Identifier of the SME shop (multi-tenancy isolation).
            user_name: Human user running the session.
            budget_ugx: Whole integer budget allocated for restock in UGX.
            session_id: Optional UUID string; auto-generated if omitted.

        Returns:
            Newly created SessionState instance.
        """
        sid = session_id or f"sess_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        state = SessionState(
            session_id=sid,
            shop_id=shop_id,
            user_name=user_name,
            budget_ugx=budget_ugx,
            stage=WorkflowStage.INITIALIZED,
            created_at=now,
            updated_at=now,
        )

        with self.conn:
            self.conn.execute("""
                INSERT INTO procurement_sessions (
                    session_id, shop_id, user_name, budget_ugx, stage,
                    low_stock_count, draft_id, draft_total_ugx, approval_status,
                    turn_count, tool_call_count, created_at, updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                state.session_id, state.shop_id, state.user_name, state.budget_ugx,
                state.stage.value, state.low_stock_count, state.draft_id,
                state.draft_total_ugx, state.approval_status, state.turn_count,
                state.tool_call_count, state.created_at, state.updated_at,
                json.dumps(state.metadata),
            ))

            # Record initial state transition in audit table
            self.conn.execute("""
                INSERT INTO state_transitions (
                    session_id, from_stage, to_stage, reason, transitioned_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (sid, "NONE", WorkflowStage.INITIALIZED.value, "Session created", now, "{}"))

        return state

    def transition_to(self, session_id: str, new_stage: WorkflowStage, reason: str = "", metadata: Optional[Dict[str, Any]] = None) -> SessionState:
        """
        Transition session to a new stage if the transition is permissible.

        Args:
            session_id: Active session ID.
            new_stage: Target WorkflowStage enum.
            reason: Human-readable explanation of why transition occurred.
            metadata: Optional additional context dict to persist with transition.

        Raises:
            KeyError: If session_id is not found.
            ValueError: If the requested transition violates the FSM transition graph.

        Returns:
            Updated SessionState instance.
        """
        current_state = self.get_session(session_id)
        if not current_state:
            raise KeyError(f"Session '{session_id}' not found in database.")

        # Validate transition against graph
        allowed = VALID_TRANSITIONS.get(current_state.stage, [])
        if new_stage not in allowed:
            raise ValueError(
                f"Invalid state transition: Cannot move from '{current_state.stage.value}' "
                f"to '{new_stage.value}'. Permissible targets: {[s.value for s in allowed]}"
            )

        now = datetime.now(timezone.utc).isoformat()
        meta_dict = metadata or {}

        with self.conn:
            # Update session row
            self.conn.execute("""
                UPDATE procurement_sessions
                SET stage = ?, updated_at = ?
                WHERE session_id = ?
            """, (new_stage.value, now, session_id))

            # Log audit transition
            self.conn.execute("""
                INSERT INTO state_transitions (
                    session_id, from_stage, to_stage, reason, transitioned_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, current_state.stage.value, new_stage.value, reason, now, json.dumps(meta_dict)))

        current_state.stage = new_stage
        current_state.updated_at = now
        return current_state

    def update_session(self, session_id: str, **kwargs: Any) -> SessionState:
        """
        Update arbitrary session fields (e.g. low_stock_count, draft_id, counters).

        Args:
            session_id: Target session ID.
            **kwargs: Field names and values to update.

        Returns:
            Updated SessionState instance.
        """
        state = self.get_session(session_id)
        if not state:
            raise KeyError(f"Session '{session_id}' not found in database.")

        allowed_fields = {
            "low_stock_count", "draft_id", "draft_total_ugx",
            "approval_status", "turn_count", "tool_call_count", "metadata"
        }

        updates = []
        params = []
        now = datetime.now(timezone.utc).isoformat()

        for key, val in kwargs.items():
            if key not in allowed_fields:
                raise ValueError(f"Field '{key}' cannot be updated directly via update_session.")
            if key == "metadata":
                updates.append("metadata_json = ?")
                params.append(json.dumps(val))
                state.metadata = val
            else:
                updates.append(f"{key} = ?")
                params.append(val)
                setattr(state, key, val)

        updates.append("updated_at = ?")
        params.append(now)
        params.append(session_id)

        sql = f"UPDATE procurement_sessions SET {', '.join(updates)} WHERE session_id = ?"
        with self.conn:
            self.conn.execute(sql, params)

        state.updated_at = now
        return state

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """
        Retrieve a session snapshot by its session_id.
        """
        cursor = self.conn.execute("""
            SELECT session_id, shop_id, user_name, budget_ugx, stage,
                   low_stock_count, draft_id, draft_total_ugx, approval_status,
                   turn_count, tool_call_count, created_at, updated_at, metadata_json
            FROM procurement_sessions
            WHERE session_id = ?
        """, (session_id,))
        row = cursor.fetchone()
        if not row:
            return None

        return SessionState(
            session_id=row["session_id"],
            shop_id=row["shop_id"],
            user_name=row["user_name"],
            budget_ugx=row["budget_ugx"],
            stage=WorkflowStage(row["stage"]),
            low_stock_count=row["low_stock_count"],
            draft_id=row["draft_id"],
            draft_total_ugx=row["draft_total_ugx"],
            approval_status=row["approval_status"],
            turn_count=row["turn_count"],
            tool_call_count=row["tool_call_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def list_sessions(self, shop_id: Optional[str] = None) -> List[SessionState]:
        """
        List all sessions, optionally filtered by shop_id for multi-tenant isolation.
        """
        sql = "SELECT session_id FROM procurement_sessions"
        params = ()
        if shop_id:
            sql += " WHERE shop_id = ?"
            params = (shop_id,)
        sql += " ORDER BY created_at DESC"

        cursor = self.conn.execute(sql, params)
        rows = cursor.fetchall()
        return [self.get_session(r["session_id"]) for r in rows if r]

    def find_session_by_draft_id(self, draft_id: str) -> Optional[SessionState]:
        """
        Find the session that produced a given draft requisition.

        WHY THIS EXISTS (Week 8 hardening, Failure Mode F-24):
          The human approval gate in src/approvals.py must be able to move the
          workflow session from AWAITING_APPROVAL to APPROVED or REJECTED. The
          draft file is the only artefact the two components share, so the link
          is made by looking the session up from the draft_id the restock agent
          stored on the session row. If no session owns the draft (for example a
          draft made by the plain tool agent), None is returned and the approval
          still works - the FSM simply has no session to advance.

        The newest matching session wins, so a re-run of the same task is
        tracked by its most recent session.
        """
        if not draft_id:
            return None
        cursor = self.conn.execute("""
            SELECT session_id FROM procurement_sessions
            WHERE draft_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (draft_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self.get_session(row["session_id"])

    def get_audit_trail(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve chronological history of state transitions for a session.
        """
        cursor = self.conn.execute("""
            SELECT transition_id, session_id, from_stage, to_stage, reason,
                   transitioned_at, metadata_json
            FROM state_transitions
            WHERE session_id = ?
            ORDER BY transition_id ASC
        """, (session_id,))
        rows = cursor.fetchall()
        return [
            {
                "transition_id": r["transition_id"],
                "session_id": r["session_id"],
                "from_stage": r["from_stage"],
                "to_stage": r["to_stage"],
                "reason": r["reason"],
                "transitioned_at": r["transitioned_at"],
                "metadata": json.loads(r["metadata_json"] or "{}"),
            }
            for r in rows
        ]

    def close(self) -> None:
        """Close SQLite database connection safely."""
        try:
            self.conn.close()
        except Exception:
            pass
