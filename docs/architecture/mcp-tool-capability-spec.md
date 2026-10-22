# MCP-Style Tool Capability Specification

| Field | Value |
|:---|:---|
| Week | 6 |
| Status | Implemented as an interoperability contract |
| Runtime gate | `src/tools/registry.py` |
| Machine-readable source | `docs/requirements/tool-schemas.json` |

This document describes the tool surface in an MCP-style way: each capability
has a name, purpose, inputs, outputs, side effects, permissions, and security
boundary. It is a project contract, not a claim that the application currently
hosts a network MCP server.

## Common security boundary

The model can request only declared tools. `execute_tool()` validates the
request, rejects unknown/protected arguments, injects trusted context, catches
tool failures, and writes a trace. `tenant_id`, `user_id`, and `created_by`
come from the application session and cannot be selected by the model.

No capability approves, orders, pays, contacts a supplier, or connects to a
bank/mobile-money service. Draft creation is the only write-like AI capability;
human approval remains outside the registry.

## Capabilities

| Capability | Inputs | Output | Side effect | Permission/security boundary |
|:---|:---|:---|:---|:---|
| `get_low_stock` | none | Low-stock item records | none | Read current shop inventory only |
| `compare_supplier_quotes` | `item` | Sorted supplier quotes | none | Read quotes for the current shop |
| `estimate_reorder_quantity` | `item` | Deterministic quantity and safety-cap working | none | Python performs all arithmetic |
| `draft_requisition` | `items` | Draft requisition or `NOT_CREATED` | Writes a scoped SQLite draft | `created_by`, `tenant_id`, `user_id` injected by code; never approval |
| `plan_within_budget` | `items`, optional `budget_ugx` | Included, deferred and human-review lists | none | Python enforces budget and urgency rules |
| `get_inventory` | optional `category` | Current stock records | none | Read current shop inventory only |
| `query_purchase_history` | `item`, optional month range | Purchases and exact totals | none | Read current shop history only |
| `search_policy` | `query`, optional `top_k` | Cited policy passages | none | `tenant_id` selects the tenant-specific RAG index |

## Human-only capability

`approvals.py` is intentionally not a tool capability. A person loads a draft,
edits it if necessary, and types `APPROVE` or `REJECT`. SQLite records the
decision and audit event under the same tenant/user scope.

## Interoperability mapping

An MCP adapter can expose each registry declaration as a tool with its JSON
schema. The adapter must pass the authenticated session context separately
from model arguments and call `execute_tool()` rather than calling functions
directly. This preserves allow-listing, validation, isolation and tracing.