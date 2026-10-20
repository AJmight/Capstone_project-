"""
tests/test_week6_state_memory.py
=============================================================================
Week 6 Test Suite: State Model, Persistent Memory, and MCP Interface
=============================================================================

ACADEMIC CONTEXT:
  BSE4104 Emerging Trends in Software Engineering (Makerere University)
  Capstone Project: SME Procurement Preparation Agent
  Author: Mwesigwa Arnold Mugahi (Reg No: 23/U/24738/PS, GitHub: AJmight)

PURPOSE:
  Validates Week 6 core capabilities:
    1. Explicit Finite State Machine (FSM) transitions and persistence.
    2. Multi-tenant persistent memory isolation (Decision-001).
    3. Memory recall and right-to-erasure (GDPR compliance).
    4. Model Context Protocol (MCP) tool and resource dispatching.
    5. Security boundaries (rejection of autonomous approval attempts).

EXECUTION:
  Run offline in Windows PowerShell:
      py tests\\test_week6_state_memory.py
  Or via Linux python3:
      python3 tests/test_week6_state_memory.py
=============================================================================
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Setup module import search path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

from state import StateManager, WorkflowStage, SessionState
from memory import MemoryManager, MemoryType, MemoryRecord
from mcp_interface import MCPServer, PERMISSION_ADMIN_APPROVAL


class TestWorkflowStateMachine(unittest.TestCase):
    """Verifies state machine transitions, validation, and SQLite persistence."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_procurement.db"
        self.state_mgr = StateManager(db_path=self.db_path)

    def tearDown(self):
        self.state_mgr.close()
        self.temp_dir.cleanup()

    def test_session_creation(self):
        """Verify new session initializes in INITIALIZED stage and persists to DB."""
        session = self.state_mgr.create_session(
            shop_id="shop_mukono_01",
            user_name="Arnold",
            budget_ugx=250000
        )
        self.assertIsNotNone(session.session_id)
        self.assertEqual(session.stage, WorkflowStage.INITIALIZED)
        self.assertEqual(session.budget_ugx, 250000)

        # Retrieve fresh from SQLite
        persisted = self.state_mgr.get_session(session.session_id)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.shop_id, "shop_mukono_01")
        self.assertEqual(persisted.stage, WorkflowStage.INITIALIZED)

    def test_valid_state_transitions(self):
        """Verify lawful progression through the procurement lifecycle."""
        session = self.state_mgr.create_session("shop_01", "Arnold", 300000)
        sid = session.session_id

        # INITIALIZED -> SENSING_INVENTORY
        s1 = self.state_mgr.transition_to(sid, WorkflowStage.SENSING_INVENTORY, "Checking low stock")
        self.assertEqual(s1.stage, WorkflowStage.SENSING_INVENTORY)

        # SENSING_INVENTORY -> PLANNING_RESTOCK
        s2 = self.state_mgr.transition_to(sid, WorkflowStage.PLANNING_RESTOCK, "Found 4 low items")
        self.assertEqual(s2.stage, WorkflowStage.PLANNING_RESTOCK)

        # PLANNING_RESTOCK -> DRAFTING_ORDER
        s3 = self.state_mgr.transition_to(sid, WorkflowStage.DRAFTING_ORDER, "Budget optimized")
        self.assertEqual(s3.stage, WorkflowStage.DRAFTING_ORDER)

        # DRAFTING_ORDER -> AWAITING_APPROVAL
        s4 = self.state_mgr.transition_to(sid, WorkflowStage.AWAITING_APPROVAL, "Draft REQ-001 created")
        self.assertEqual(s4.stage, WorkflowStage.AWAITING_APPROVAL)

        # AWAITING_APPROVAL -> APPROVED (Human owner action)
        s5 = self.state_mgr.transition_to(sid, WorkflowStage.APPROVED, "Owner approved in approvals.py")
        self.assertEqual(s5.stage, WorkflowStage.APPROVED)

        # Verify audit trail logs all transitions
        trail = self.state_mgr.get_audit_trail(sid)
        self.assertEqual(len(trail), 6) # Initial creation + 5 transitions

    def test_invalid_state_transition_blocked(self):
        """Verify that FSM blocks illegal transitions (e.g. skipping straight to APPROVED)."""
        session = self.state_mgr.create_session("shop_01", "Arnold", 150000)
        sid = session.session_id

        # Attempt illegal jump: INITIALIZED -> APPROVED without drafting or human review
        with self.assertRaises(ValueError) as ctx:
            self.state_mgr.transition_to(sid, WorkflowStage.APPROVED, "Attempting bypass")
        self.assertIn("Invalid state transition", str(ctx.exception))


class TestPersistentMemory(unittest.TestCase):
    """Verifies justified memory persistence, tenant isolation, and privacy controls."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_procurement.db"
        self.mem_mgr = MemoryManager(db_path=self.db_path)

    def tearDown(self):
        self.mem_mgr.close()
        self.temp_dir.cleanup()

    def test_store_and_retrieve_preference(self):
        """Verify storing owner preference and retrieving by item/category."""
        self.mem_mgr.store_memory(
            shop_id="shop_kampala_01",
            memory_type=MemoryType.SUPPLIER_PREFERENCE,
            target_key="ITM006",
            summary="Prefer Kampala Office Supplies for paper",
            details="Delivery is consistently within 24 hours.",
            created_by="Arnold"
        )

        recalled = self.mem_mgr.retrieve_relevant_memories("shop_kampala_01", ["ITM006"])
        self.assertEqual(len(recalled), 1)
        self.assertEqual(recalled[0].target_key, "ITM006")
        self.assertEqual(recalled[0].summary, "Prefer Kampala Office Supplies for paper")
        self.assertEqual(recalled[0].recall_count, 1)

    def test_multi_tenant_isolation(self):
        """Verify strict Decision-001 tenant isolation: Shop A cannot view Shop B memories."""
        # Store memory for Shop A
        self.mem_mgr.store_memory(
            shop_id="shop_A",
            memory_type=MemoryType.SUPPLIER_PREFERENCE,
            target_key="ITM001",
            summary="Shop A exclusive supplier discount",
            details="5% volume rebate with Nakawa Stationers",
            created_by="Owner A"
        )

        # Shop B queries the same item
        shop_b_recalled = self.mem_mgr.retrieve_relevant_memories("shop_B", ["ITM001"])
        self.assertEqual(len(shop_b_recalled), 0, "Cross-shop data leakage detected! Shop B read Shop A memory.")

    def test_right_to_erasure_deletion(self):
        """Verify owner can audit and delete memories (GDPR compliance)."""
        rec = self.mem_mgr.store_memory(
            shop_id="shop_jinja_02",
            memory_type=MemoryType.SEASONAL_POLICY,
            target_key="Stationery",
            summary="Double stock in January",
            details="Back to school peak",
            created_by="Owner"
        )

        # Delete single record
        deleted = self.mem_mgr.delete_memory("shop_jinja_02", rec.memory_id)
        self.assertTrue(deleted)

        remaining = self.mem_mgr.retrieve_relevant_memories("shop_jinja_02", ["Stationery"])
        self.assertEqual(len(remaining), 0)


class TestMCPInterface(unittest.TestCase):
    """Verifies MCP JSON-RPC protocol compliance and security boundaries."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_procurement.db"
        self.mem_mgr = MemoryManager(db_path=self.db_path)
        self.server = MCPServer(memory_manager=self.mem_mgr)

    def tearDown(self):
        self.mem_mgr.close()
        self.temp_dir.cleanup()

    def test_mcp_initialize(self):
        """Verify MCP handshake negotiation."""
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"}
        }
        res = self.server.handle_request(req)
        self.assertEqual(res["jsonrpc"], "2.0")
        self.assertEqual(res["id"], 1)
        self.assertIn("tools", res["result"]["capabilities"])
        self.assertEqual(res["result"]["serverInfo"]["name"], "sme-procurement-mcp-server")

    def test_mcp_tools_list(self):
        """Verify list of tools exposed conforms to procurement capabilities."""
        req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }
        res = self.server.handle_request(req)
        tool_names = [t["name"] for t in res["result"]["tools"]]
        self.assertIn("get_low_stock", tool_names)
        self.assertIn("plan_within_budget", tool_names)
        self.assertIn("draft_requisition", tool_names)
        self.assertIn("query_memory", tool_names)

    def test_security_boundary_blocks_autonomous_approval(self):
        """Verify MCP server actively blocks attempts to autonomously approve or pay."""
        req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "approve_requisition",
                "arguments": {"draft_id": "REQ-2026-001"}
            }
        }
        res = self.server.handle_request(req)
        self.assertTrue(res["result"]["isError"])
        self.assertIn("SECURITY_VIOLATION", res["result"]["content"][0]["text"])
        self.assertIn("strictly forbidden", res["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
