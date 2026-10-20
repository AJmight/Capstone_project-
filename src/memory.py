"""
src/memory.py
=============================================================================
Justified Persistent Memory Architecture (Week 6 Deliverable)
=============================================================================

ACADEMIC CONTEXT:
  BSE4104 Emerging Trends in Software Engineering (Makerere University)
  Capstone Project: SME Procurement Preparation Agent
  Author: Mwesigwa Arnold Mugahi (Reg No: 23/U/24738/PS, GitHub: AJmight)

PURPOSE:
  In agentic AI engineering, unconstrained memory leads to prompt bloat,
  hallucinations, and privacy violations. The assignment brief explicitly
  demands:
    1. Retain ONLY justified memory that serves a legitimate business task.
    2. Document what is stored, why, who can access it, retention and deletion.
    3. Demonstrate that memory improves recommendations WITHOUT silently
       controlling critical decisions (Human-in-the-Loop remains authoritative).

JUSTIFIED USE CASES IMPLEMENTED:
  A. SUPPLIER_PREFERENCE:
     SME owner records trusted supplier choices (e.g., "Prefer Kampala Office
     Supplies for A4 paper if delivery time is under 3 days").
  B. APPROVAL_FEEDBACK:
     Records why prior draft purchase orders were approved or rejected by the
     human owner (e.g., "Owner rejected high stapler quantity due to tight cashflow").
  C. SEASONAL_POLICY:
     Captures business cycle adjustments (e.g., "Term 1 exam period: prioritize
     exercise books over non-urgent desk organizers").

DATA PROTECTION & PRIVACY RULES (Decision-001):
  - Cross-Shop Isolation: All records are strictly indexed and queried by `shop_id`.
    Shop A can NEVER retrieve or infer Shop B's preferences or purchase patterns.
  - Right to Erasure (GDPR / Data Protection):
    SME owners can view, export, delete individual memories, or purge all data.
  - Non-Silent Authority:
    Memories are explicitly labelled when passed to the model and output in the final
    summary so the human owner sees exactly why an item was suggested.

KEY DATA FLOWS:
  - INPUT: Stored via approvals.py (post-approval feedback) or restock_agent.py.
  - STORAGE: SQLite database table `shop_memories` in data/procurement.db.
  - RETRIEVAL: Queried by restock_agent.py during SENSE/PLAN stage based on low-stock item IDs.
  - OUTPUT: Injected into prompt as informational context; human confirms final draft.
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


# Stored in the project's data/ directory to guarantee persistent state.
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "procurement.db"


class MemoryType(str, Enum):
    """
    Categories of justified procurement memory.
    Ensures that only business-relevant operational facts are retained.
    """
    SUPPLIER_PREFERENCE = "SUPPLIER_PREFERENCE"   # Preferred supplier relationships or trade terms
    APPROVAL_FEEDBACK = "APPROVAL_FEEDBACK"       # Owner's rejection/approval reasoning on prior drafts
    SEASONAL_POLICY = "SEASONAL_POLICY"           # Seasonal demand spikes or stock priority rules


@dataclass
class MemoryRecord:
    """
    Represents an atomic, audited memory unit for an SME shop.
    """
    memory_id: str
    shop_id: str
    memory_type: MemoryType
    target_key: str                               # Specific item_id (e.g. ITM001), category, or 'GLOBAL'
    summary: str                                  # Short human-readable takeaway
    details: str                                  # Full explanation and rationale
    source_session_id: Optional[str] = None       # Traceability link to session where memory was created
    created_by: str = "Owner"                     # User who authored or authorized this preference
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_recalled_at: Optional[str] = None        # Audit tracking for memory usefulness
    recall_count: int = 0                         # Number of times this memory assisted planning

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to standard dictionary format."""
        data = asdict(self)
        data["memory_type"] = self.memory_type.value if isinstance(self.memory_type, MemoryType) else str(self.memory_type)
        return data


class MemoryManager:
    """
    Database-backed Persistent Memory Manager.
    Enforces multi-tenant shop isolation, memory CRUD operations, and context formatting.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize connection to SQLite memory store.
        
        Args:
            db_path: Path to SQLite database file. Defaults to data/procurement.db.
        """
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Create `shop_memories` table and multi-tenant performance indices."""
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS shop_memories (
                    memory_id TEXT PRIMARY KEY,
                    shop_id TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    target_key TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    details TEXT NOT NULL,
                    source_session_id TEXT,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_recalled_at TEXT,
                    recall_count INTEGER DEFAULT 0
                )
            """)

            # Multi-tenant compound index: guarantees fast and isolated lookups per shop
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_shop_target ON shop_memories(shop_id, target_key)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_type ON shop_memories(shop_id, memory_type)")

    def store_memory(
        self,
        shop_id: str,
        memory_type: MemoryType,
        target_key: str,
        summary: str,
        details: str,
        source_session_id: Optional[str] = None,
        created_by: str = "Owner",
        memory_id: Optional[str] = None
    ) -> MemoryRecord:
        """
        Store a new justified memory record for an SME shop.

        Args:
            shop_id: Strict tenant isolation identifier.
            memory_type: Enum category (SUPPLIER_PREFERENCE, APPROVAL_FEEDBACK, SEASONAL_POLICY).
            target_key: Target item_id (e.g. 'ITM006'), category ('Stationery'), or 'GLOBAL'.
            summary: Brief synopsis of the preference or feedback.
            details: In-depth rationale.
            source_session_id: Session ID where preference was expressed.
            created_by: Human author.
            memory_id: Optional custom ID; auto-generated if omitted.

        Returns:
            Newly created MemoryRecord.
        """
        mid = memory_id or f"mem_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        record = MemoryRecord(
            memory_id=mid,
            shop_id=shop_id,
            memory_type=memory_type,
            target_key=target_key,
            summary=summary,
            details=details,
            source_session_id=source_session_id,
            created_by=created_by,
            created_at=now,
        )

        with self.conn:
            self.conn.execute("""
                INSERT OR REPLACE INTO shop_memories (
                    memory_id, shop_id, memory_type, target_key, summary,
                    details, source_session_id, created_by, created_at,
                    last_recalled_at, recall_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.memory_id, record.shop_id, record.memory_type.value,
                record.target_key, record.summary, record.details,
                record.source_session_id, record.created_by, record.created_at,
                record.last_recalled_at, record.recall_count,
            ))

        return record

    def retrieve_relevant_memories(
        self,
        shop_id: str,
        target_keys: Optional[List[str]] = None,
        memory_type: Optional[MemoryType] = None
    ) -> List[MemoryRecord]:
        """
        Retrieve relevant memories strictly isolated to the specified shop.

        Args:
            shop_id: SME shop identifier.
            target_keys: List of item_ids or categories to match (automatically includes 'GLOBAL').
            memory_type: Optional filter by MemoryType.

        Returns:
            List of matching MemoryRecord objects.
        """
        keys_to_match = ["GLOBAL"]
        if target_keys:
            keys_to_match.extend(target_keys)

        placeholders = ",".join("?" for _ in keys_to_match)
        sql = f"""
            SELECT memory_id, shop_id, memory_type, target_key, summary,
                   details, source_session_id, created_by, created_at,
                   last_recalled_at, recall_count
            FROM shop_memories
            WHERE shop_id = ? AND target_key IN ({placeholders})
        """
        params: List[Any] = [shop_id] + keys_to_match

        if memory_type:
            sql += " AND memory_type = ?"
            params.append(memory_type.value)

        sql += " ORDER BY created_at DESC"

        cursor = self.conn.execute(sql, params)
        rows = cursor.fetchall()

        results: List[MemoryRecord] = []
        now = datetime.now(timezone.utc).isoformat()
        memory_ids_recalled = []

        for r in rows:
            record = MemoryRecord(
                memory_id=r["memory_id"],
                shop_id=r["shop_id"],
                memory_type=MemoryType(r["memory_type"]),
                target_key=r["target_key"],
                summary=r["summary"],
                details=r["details"],
                source_session_id=r["source_session_id"],
                created_by=r["created_by"],
                created_at=r["created_at"],
                last_recalled_at=r["last_recalled_at"],
                recall_count=r["recall_count"],
            )
            record.recall_count += 1
            record.last_recalled_at = now
            results.append(record)
            memory_ids_recalled.append(record.memory_id)

        # Update last_recalled_at and recall_count in background
        if memory_ids_recalled:
            m_placeholders = ",".join("?" for _ in memory_ids_recalled)
            with self.conn:
                self.conn.execute(f"""
                    UPDATE shop_memories
                    SET last_recalled_at = ?, recall_count = recall_count + 1
                    WHERE memory_id IN ({m_placeholders})
                """, [now] + memory_ids_recalled)

        return results

    def format_memories_for_prompt(self, memories: List[MemoryRecord]) -> str:
        """
        Format retrieved memories into a transparent, explainable markdown block
        ready for injection into the agent's prompt context.

        Crucially includes non-silent guidance: reminds the model that memories
        are informative advice, NEVER autonomous approval authority.
        """
        if not memories:
            return ""

        lines = [
            "### RECALLED SME PROCUREMENT PREFERENCES (Persistent Memory)",
            "> [!IMPORTANT] NON-SILENT AUTHORITY NOTICE:",
            "> These memories reflect verified owner preferences and historical decisions.",
            "> They MUST guide recommended quantities and supplier choices, but they DO NOT",
            "> constitute autonomous approval. All purchase requisitions still require",
            "> explicit human verification and signature in approvals.py.",
            ""
        ]

        for mem in memories:
            lines.append(
                f"- **[{mem.memory_type.value}] ({mem.target_key})**: {mem.summary}\n"
                f"  *Rationale:* {mem.details} *(Recorded: {mem.created_at[:10]} by {mem.created_by})*"
            )

        return "\n".join(lines)

    def delete_memory(self, shop_id: str, memory_id: str) -> bool:
        """
        Delete a single memory record, strictly verifying shop_id ownership.
        Ensures compliance with GDPR / right to erasure.

        Returns:
            True if a row was deleted, False otherwise.
        """
        with self.conn:
            cursor = self.conn.execute("""
                DELETE FROM shop_memories
                WHERE shop_id = ? AND memory_id = ?
            """, (shop_id, memory_id))
            return cursor.rowcount > 0

    def clear_shop_memories(self, shop_id: str) -> int:
        """
        Purge all memory records associated with a shop.
        
        Returns:
            Total count of deleted memory records.
        """
        with self.conn:
            cursor = self.conn.execute("""
                DELETE FROM shop_memories
                WHERE shop_id = ?
            """, (shop_id,))
            return cursor.rowcount

    def list_all_shop_memories(self, shop_id: str) -> List[MemoryRecord]:
        """
        Retrieve complete catalogue of stored memories for an SME shop owner to audit.
        """
        cursor = self.conn.execute("""
            SELECT memory_id, shop_id, memory_type, target_key, summary,
                   details, source_session_id, created_by, created_at,
                   last_recalled_at, recall_count
            FROM shop_memories
            WHERE shop_id = ?
            ORDER BY created_at DESC
        """, (shop_id,))
        rows = cursor.fetchall()
        return [
            MemoryRecord(
                memory_id=r["memory_id"],
                shop_id=r["shop_id"],
                memory_type=MemoryType(r["memory_type"]),
                target_key=r["target_key"],
                summary=r["summary"],
                details=r["details"],
                source_session_id=r["source_session_id"],
                created_by=r["created_by"],
                created_at=r["created_at"],
                last_recalled_at=r["last_recalled_at"],
                recall_count=r["recall_count"],
            )
            for r in rows
        ]

    def close(self) -> None:
        """Safely close database connection."""
        try:
            self.conn.close()
        except Exception:
            pass
