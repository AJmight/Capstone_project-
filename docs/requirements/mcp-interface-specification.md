# Interface Specification: Model Context Protocol (MCP) Server

**Project:** SME Procurement Preparation Agent (BSE4104 Capstone)  
**Author:** Mwesigwa Arnold Mugahi (Reg No: 23/U/24738/PS, GitHub: AJmight)  
**Deliverable:** Week 6 Interoperability Note  
**Protocol Version:** MCP `2024-11-05`  
**Server Name:** `sme-procurement-mcp-server` (v1.0.0)  

---

## 1. Overview & Standard Alignment

The **Model Context Protocol (MCP)**, open-sourced by Anthropic in late 2024, establishes an open JSON-RPC 2.0 communication standard between AI host applications (clients) and external data/tool providers (servers).

In traditional AI applications, tool wrappers are tightly coupled to a single vendor's SDK (e.g. Google GenAI function declarations or OpenAI tool formats). MCP solves this by providing:
1. Standardized JSON Schema parameter contracts.
2. Capability discovery (`tools/list`, `resources/list`).
3. Explicit permission and security boundaries.

Our system implements the MCP server interface in [`src/mcp_interface.py`](../../src/mcp_interface.py), exposing procurement tools, persistent memory, and live inventory resources.

---

## 2. Server Capabilities & Tool Catalogue

### A. Procurement Tools (`tools/list`)

| Tool Name | Permission Level | Human Approval Required? | Purpose |
| :--- | :--- | :--- | :--- |
| `get_low_stock` | `read_only` | No | Lists items where `current_stock <= reorder_point`. |
| `compare_supplier_quotes` | `read_only` | No | Retrieves quotes for an item sorted by unit price and lead time. |
| `estimate_reorder_quantity`| `read_only` | No | Calculates recommended reorder quantity based on demand proxy and MOQ. |
| `plan_within_budget` | `read_only` | No | Solves budget allocation across items by stock urgency. |
| `draft_requisition` | `draft_write` | **Yes** | Generates formal purchase requisition draft (`data/drafts/REQ-*.json`). |
| `query_memory` | `read_only` | No | Retrieves shop-specific preferences and past approval feedback. |
| `store_memory` | `draft_write` | **Yes** | Records verified owner preferences into persistent SQLite storage. |

### B. Read-Only Resources (`resources/list`)

MCP Resources allow clients to inspect live context without invoking tools:
- `procurement://stock/current`: Real-time stock counts and thresholds from `data/current_stock.csv`.
- `procurement://suppliers/quotes`: Active supplier catalog quotes and MOQs from `data/supplier_quotes.csv`.

---

## 3. Security Boundary & Autonomous Action Rejection

A cornerstone requirement of the Capstone Brief is that high-impact financial actions **must remain strictly behind human approval**.

The MCP Server implements an active security boundary interceptor:
```json
{
  "jsonrpc": "2.0",
  "id": 101,
  "method": "tools/call",
  "params": {
    "name": "approve_requisition",
    "arguments": {"draft_id": "REQ-20261020-001"}
  }
}
```

**MCP Server Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 101,
  "result": {
    "isError": true,
    "content": [
      {
        "type": "text",
        "text": "SECURITY_VIOLATION: Tool 'approve_requisition' requires 'admin_approval' authority. AI models are strictly forbidden from approving or funding orders. This action must be performed by the human owner in approvals.py."
      }
    ]
  }
}
```

This ensures that even if a compromised model attempts to issue an approval or payment tool call, the server deterministically rejects the operation.
