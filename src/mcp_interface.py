"""
src/mcp_interface.py
=============================================================================
Model Context Protocol (MCP) Interface Specification (Week 6 Deliverable)
=============================================================================

ACADEMIC CONTEXT:
  BSE4104 Emerging Trends in Software Engineering (Makerere University)
  Capstone Project: SME Procurement Preparation Agent
  Author: Mwesigwa Arnold Mugahi (Reg No: 23/U/24738/PS, GitHub: AJmight)

PURPOSE:
  The Model Context Protocol (MCP), created by Anthropic, is an open standard
  for bidirectional JSON-RPC 2.0 communication between foundation models and
  tool/data providers.
  
  Rather than writing bespoke, brittle tool wrappers for every individual LLM,
  MCP decouples tool capability providers (servers) from tool consumers (clients).
  This module implements the MCP server interface for the SME Procurement System:
    1. Declares standard tool definitions with JSON Schema parameter contracts.
    2. Exposes URI-based read-only resources (procurement://stock/levels).
    3. Enforces an explicit permission and security boundary:
       - 'read_only': Safe query tools (stock, quotes, reorder estimation).
       - 'draft_write': Creates draft purchase orders (NO financial side effects).
       - 'admin_approval': Strictly RESERVED for the human owner (CLI only;
                           explicitly forbidden to LLM tool calls).

KEY DATA FLOWS:
  - INPUT: JSON-RPC 2.0 request payloads received from an MCP-compatible client.
  - DISPATCH: Routed through tools.registry.execute_tool and memory.py.
  - OUTPUT: Standard MCP JSON-RPC response with content blocks and error structures.
=============================================================================
"""

import json
from typing import Any, Dict, List, Optional

from guardrails import GuardrailViolation, HumanInTheLoopGuardrail, InputGuardrail
from memory import MemoryManager, MemoryType
from tools import procurement
from tools.registry import TOOL_REGISTRY, execute_tool

# MCP Protocol Version supported
MCP_PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "sme-procurement-mcp-server"
SERVER_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# MCP Permission Boundaries
# ---------------------------------------------------------------------------
PERMISSION_READ_ONLY = "read_only"
PERMISSION_DRAFT_WRITE = "draft_write"
PERMISSION_ADMIN_APPROVAL = "admin_approval"

TOOL_PERMISSIONS: Dict[str, str] = {
    "get_restock_options": PERMISSION_READ_ONLY,
    "get_low_stock": PERMISSION_READ_ONLY,
    "compare_supplier_quotes": PERMISSION_READ_ONLY,
    "estimate_reorder_quantity": PERMISSION_READ_ONLY,
    "plan_within_budget": PERMISSION_READ_ONLY,
    "draft_requisition": PERMISSION_DRAFT_WRITE,
    "query_memory": PERMISSION_READ_ONLY,
    "store_memory": PERMISSION_DRAFT_WRITE,
}


class MCPServer:
    """
    Lightweight, compliant Model Context Protocol (MCP) server dispatcher.
    Handles 'initialize', 'tools/list', 'tools/call', 'resources/list', and 'resources/read'.
    """

    def __init__(self, memory_manager: Optional[MemoryManager] = None,
                 shop_id: str = "default_shop"):
        """
        Initialize the MCP Server with access to procurement tools and memory store.

        shop_id is the TENANT this server instance speaks for. It is TRUSTED
        configuration, never something the model may choose: the model is a guest
        inside this shop and must not be able to read or write another shop's
        memory (see Decision-001 and Failure Mode F-25, Week 8 hardening).
        """
        # Validate the shop id FIRST, so an invalid tenant can never even open
        # the memory database (defence in depth, Failure Mode F-18).
        self.shop_id = InputGuardrail.validate_shop_id(shop_id)
        self.memory_manager = memory_manager or MemoryManager()

    def handle_request(self, request_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an incoming JSON-RPC 2.0 request.

        Args:
            request_payload: Dict containing 'jsonrpc', 'id', 'method', and optional 'params'.

        Returns:
            JSON-RPC 2.0 compliant response dict with either 'result' or 'error'.
        """
        req_id = request_payload.get("id")
        method = request_payload.get("method")
        params = request_payload.get("params", {})

        if request_payload.get("jsonrpc") != "2.0":
            return self._error_response(req_id, -32600, "Invalid Request: 'jsonrpc' must be '2.0'")

        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "tools/list":
                result = self._handle_tools_list()
            elif method == "tools/call":
                result = self._handle_tools_call(params)
            elif method == "resources/list":
                result = self._handle_resources_list()
            elif method == "resources/read":
                result = self._handle_resources_read(params)
            else:
                return self._error_response(req_id, -32601, f"Method not found: '{method}'")

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result
            }

        except Exception as e:
            return self._error_response(req_id, -32000, f"Internal Server Error: {str(e)}")

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handshake negotiation declaring server info and capabilities."""
        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False}
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION
            }
        }

    def _handle_tools_list(self) -> Dict[str, Any]:
        """
        Return formal tool definitions with input schema and security annotations.
        """
        mcp_tools = []
        for name, entry in TOOL_REGISTRY.items():
            decl = entry.get("declaration", {})
            mcp_tools.append({
                "name": name,
                "description": decl.get("description", ""),
                "inputSchema": decl.get("parameters_json_schema", {}),
                "security": {
                    "permission": TOOL_PERMISSIONS.get(name, PERMISSION_READ_ONLY),
                    "humanApprovalRequired": name == "draft_requisition"
                }
            })

        # Add memory tools
        mcp_tools.append({
            "name": "query_memory",
            "description": "Query persistent SME procurement preferences and past approval feedback for a shop.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "shop_id": {"type": "string", "description": "SME shop identifier for isolation"},
                    "target_keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Item IDs or categories to query"
                    }
                },
                "required": ["shop_id"]
            },
            "security": {
                "permission": PERMISSION_READ_ONLY,
                "humanApprovalRequired": False
            }
        })

        mcp_tools.append({
            "name": "store_memory",
            "description": "Store verified owner preference or feedback into persistent SQLite memory.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "shop_id": {"type": "string", "description": "SME shop identifier for isolation"},
                    "memory_type": {
                        "type": "string",
                        "enum": ["SUPPLIER_PREFERENCE", "APPROVAL_FEEDBACK", "SEASONAL_POLICY"],
                        "description": "Type of memory"
                    },
                    "target_key": {"type": "string", "description": "Item ID or category"},
                    "summary": {"type": "string", "description": "Concise rule summary"},
                    "details": {"type": "string", "description": "Detailed rationale"}
                },
                "required": ["shop_id", "memory_type", "target_key", "summary", "details"]
            },
            "security": {
                "permission": PERMISSION_DRAFT_WRITE,
                "humanApprovalRequired": True
            }
        })

        return {"tools": mcp_tools}

    def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an approved tool call through the safe registry and return MCP content blocks.
        """
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            raise ValueError("Tool name is required in 'params.name'")

        # Enforce security boundary: Reject autonomous attempts to execute approvals.
        # The guardrail is the single source of truth for "a human-only action"
        # (Week 7 guardrails.py, Failure Mode F-19).
        try:
            HumanInTheLoopGuardrail.verify_action_permitted(tool_name, "AI_AGENT")
        except GuardrailViolation as exc:
            return {
                "isError": True,
                "content": [{
                    "type": "text",
                    "text": (
                        f"SECURITY_VIOLATION: Tool '{tool_name}' requires "
                        f"'{PERMISSION_ADMIN_APPROVAL}' authority. {exc} "
                        f"AI models are strictly forbidden from approving or funding orders. "
                        f"This action must be performed by the human owner in approvals.py."
                    )
                }]
            }

        # Handle custom memory tools.
        # The shop_id is taken from THIS SERVER (trusted), never from the model's
        # arguments: otherwise a model could read another shop's memory (F-25).
        if tool_name in ("query_memory", "store_memory"):
            requested_shop = arguments.get("shop_id", self.shop_id)
            if requested_shop != self.shop_id:
                return {
                    "isError": True,
                    "content": [{
                        "type": "text",
                        "text": (f"TENANT_ISOLATION_VIOLATION: this server is bound to shop "
                                 f"'{self.shop_id}'. Cross-shop access is refused (F-25).")
                    }]
                }

        if tool_name == "query_memory":
            keys = arguments.get("target_keys")
            records = self.memory_manager.retrieve_relevant_memories(shop_id=self.shop_id,
                                                                      target_keys=keys)
            return {
                "isError": False,
                "content": [{
                    "type": "text",
                    "text": json.dumps([r.to_dict() for r in records], indent=2)
                }]
            }

        if tool_name == "store_memory":
            try:
                rec = self.memory_manager.store_memory(
                    shop_id=self.shop_id,
                    memory_type=MemoryType(arguments["memory_type"]),
                    target_key=arguments["target_key"],
                    summary=arguments["summary"],
                    details=arguments["details"],
                    created_by="Owner via MCP"
                )
            except KeyError as exc:
                return {
                    "isError": True,
                    "content": [{"type": "text", "text": f"INVALID_ARGUMENTS: missing {exc}"}]
                }
            return {
                "isError": False,
                "content": [{
                    "type": "text",
                    "text": json.dumps({"status": "SUCCESS", "memory": rec.to_dict()}, indent=2)
                }]
            }

        # Dispatch regular procurement tools through the deterministic registry.
        # execute_tool() returns (result, status); the status is what tells us
        # whether the call was allowed, invalid, blocked or crashed (F-23 fix:
        # this call used the wrong keyword and unpacked a tuple as a dict).
        result, status = execute_tool(tool_name, arguments,
                                      context={"created_by": "MCP_Client"},
                                      run_id="mcp")
        is_error = status != "ok" or (isinstance(result, dict) and "error" in result)

        return {
            "isError": is_error,
            "content": [{
                "type": "text",
                "text": json.dumps({"status": status, "result": result}, indent=2)
            }]
        }

    def _handle_resources_list(self) -> Dict[str, Any]:
        """Expose available URI-based procurement data resources."""
        return {
            "resources": [
                {
                    "uri": "procurement://stock/current",
                    "name": "Current Stock Inventory",
                    "description": "Real-time stock on hand and reorder points from current_stock.csv",
                    "mimeType": "application/json"
                },
                {
                    "uri": "procurement://suppliers/quotes",
                    "name": "Supplier Catalog Quotes",
                    "description": "Active supplier price quotes, lead times, and MOQs from supplier_quotes.csv",
                    "mimeType": "application/json"
                }
            ]
        }

    def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Read resource data given its URI."""
        uri = params.get("uri")
        if uri == "procurement://stock/current":
            stock = procurement.get_low_stock()
            return {
                "contents": [{
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(stock, indent=2)
                }]
            }
        elif uri == "procurement://suppliers/quotes":
            quotes = procurement.compare_supplier_quotes()
            return {
                "contents": [{
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(quotes, indent=2)
                }]
            }
        else:
            raise ValueError(f"Unknown resource URI: '{uri}'")

    def _error_response(self, req_id: Any, code: int, message: str) -> Dict[str, Any]:
        """Format standard JSON-RPC 2.0 error."""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": code,
                "message": message
            }
        }
