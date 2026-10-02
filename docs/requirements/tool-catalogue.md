# Tool Catalogue — SME Procurement Assistant

| Field | Value |
|:---|:---|
| **Version** | 1.1 (Week 5: tool 5 `plan_within_budget`, task allow-list, repeat guard, output check) |
| **Owner** | Mwesigwa Arnold Mugahi (AI Engineering Lead) |
| **Code** | `src/tools/procurement.py` (functions), `src/tools/registry.py` (allow-list, permissions, executor) |
| **Machine-readable schemas** | `docs/requirements/tool-schemas.json` (exported from the code) |
| **Tests** | `tests/test_week4_tools.py` (22 offline + 6 live), `tests/test_week5_agent.py` (16 offline + 4 live traces) |

## How a tool call works

1. `src/tool_agent.py` sends the user's question and the **declarations of the tools the user's role may use** to Gemini.
2. Gemini replies with a function call, e.g. `estimate_reorder_quantity(item="Rulers 30cm")`.
3. `registry.execute_tool()` checks **allow-list → role permission → arguments**, injects trusted context (`created_by`), runs the Python function, catches crashes, and writes a trace line.
4. The result dictionary goes back to Gemini, which explains it. **Every number comes from Python.**

## Roles and permissions

| Role | Permissions | Tools shown to the model |
|:---|:---|:---|
| `viewer` | read | `get_low_stock`, `compare_supplier_quotes`, `estimate_reorder_quantity`, `plan_within_budget` |
| `staff` | read, draft | all five |
| `owner` | read, draft | all five |
| any other | none | none |

**No role can approve, order or pay through the AI**: those tools do not exist. Approval is a human
action in `src/approvals.py` (see the end of this document).

## Tool 1 — `get_low_stock`

| Field | Value |
|:---|:---|
| **Purpose** | List every item with `current_stock <= reorder_point` |
| **Input** | none |
| **Output** | `{"count": 10, "items": [{"item_id", "item_name", "current_stock", "reorder_point"}], "total_items_in_inventory": 15, "source"}` |
| **Reads** | `data/current_stock.csv` |
| **Permission / side effects** | read / none |
| **Failure behaviour** | missing file, missing column or non-numeric cell → `{"error": "INVALID_DATA: ..."}` |

## Tool 2 — `compare_supplier_quotes`

| Field | Value |
|:---|:---|
| **Purpose** | All quotes for one item, cheapest first (tie → shorter lead time) |
| **Input** | `item: string` — ID (`ITM001`) or name (`"Bic Pens (Blue)"`, `"calculator"`) |
| **Output** | `{"item_id", "item_name", "quote_count", "cheapest": {supplier_name, unit_price_ugx, min_order_qty, lead_time_days} or null, "all_quotes": [...], "source"}` |
| **Reads** | `current_stock.csv` (to resolve the item), `supplier_quotes.csv` |
| **Permission / side effects** | read / none |
| **Failure behaviour** | `UNKNOWN_ITEM`, `AMBIGUOUS_ITEM` (lists candidates, e.g. "pens"), `INVALID_DATA`; no quotes → `cheapest: null` + note |

## Tool 3 — `estimate_reorder_quantity`

| Field | Value |
|:---|:---|
| **Purpose** | Exact reorder quantity for one item — **the fix for F-04** |
| **Input** | `item: string` (ID or name) |
| **Output** | `{"item_id", "item_name", "current_stock", "reorder_point", "is_low", "months_of_history", "avg_monthly_purchases", "recommended_qty", "basis", "selected_supplier", "min_order_qty", "safety_cap", "requires_override", "override_reason", "source"}` |
| **Rules** | not low → 0 ("no reorder needed"); no history → 0 ("human must set quantity"); else `ceil(avg_monthly × 1.5 − stock)` with exact fractions, raised to the cheapest supplier's MOQ; `safety_cap = 2 × largest past purchase`; `requires_override = qty > cap` |
| **Reads** | all three CSVs |
| **Permission / side effects** | read / none |
| **Failure behaviour** | as Tool 2 |

## Tool 4 — `draft_requisition`

| Field | Value |
|:---|:---|
| **Purpose** | Build and save a **draft** purchase requisition |
| **Input** | `items: array of string` (1–20 IDs or names). `created_by` is **injected by the system** from the session user; the model sending it is rejected (`INVALID_PARAMETER`) |
| **Output** | `{"draft_id": "REQ-YYYYMMDD-HHMMSS-XXXX", "created_at", "created_by", "status": "DRAFT - AWAITING HUMAN APPROVAL", "lines": [...], "skipped": [...], "estimated_budget_ugx", "budget_range_ugx": {low, high}, "requires_override_any", "decision": null, "saved_to"}`; or `{"status": "NOT_CREATED", ...}` if nothing is low |
| **Rules** | only low items get lines; well-stocked items go to `skipped` with the reason; totals and ±10 % range computed in integers |
| **Reads / writes** | reads all CSVs; **writes** `data/drafts/<draft_id>.json` (git-ignored) |
| **Permission / side effects** | draft / **low-risk simulated side effect**: a file is saved; nothing is sent, ordered or paid |
| **Failure behaviour** | `INVALID_PARAMETER` (empty/too many items), `UNKNOWN_ITEM`, `AMBIGUOUS_ITEM`, `INVALID_DATA` |

Covers User Stories 2, 4, 5 (unique ID, date, creator), 7 (reasoning trail), 8 (budget range), 12 (200 % cap flag).

## Tool 5 — `plan_within_budget` (Week 5)

| Field | Value |
|:---|:---|
| **Purpose** | Decide which low items fit a budget, most urgent first |
| **Input** | `items: array of string` (1–50), `budget_ugx: integer ≥ 1` (optional; whole floats like `300000.0` are converted, `2.5` rejected) |
| **Output** | `{"budget_ugx", "planned_total_ugx", "remaining_budget_ugx", "all_priced_items_fit", "included": [{item_id, item_name, recommended_qty, selected_supplier, cost_ugx, urgency, requires_override}], "deferred": [... + reason], "needs_human": [{item_id, item_name, reason}], "not_low": [...], "rule"}` |
| **Rules** | costs as in `draft_requisition`; urgency = stock / reorder point (lower first); greedy skip-and-continue within the budget; no-history or no-quote items → `needs_human` |
| **Permission / side effects** | read / none |
| **Used by** | the Weekly Restock Agent (`src/restock_agent.py`) before drafting |

## Executor errors (from `registry.execute_tool`)

| Code | When | Status in trace |
|:---|:---|:---|
| `UNAUTHORIZED_TOOL` | tool name not on the allow-list (e.g. `approve_requisition`) | blocked |
| `UNAUTHORIZED` | role lacks the tool's permission | blocked |
| `MISSING_PARAMETER` | required argument absent | invalid |
| `INVALID_PARAMETER` | unknown argument, wrong type, empty string/list, too many items | invalid |
| `TOOL_ERROR` | the Python function crashed | crashed |
| `UNEXPECTED_RESPONSE` | the function returned something other than a dict | crashed |
| `LIMIT` | the run's tool-call budget (`AGENT_MAX_TOOL_CALLS`) is used up | blocked |
| `NOT_IN_TASK_CONTRACT` | (Week 5, `tool_agent`) tool not in the current task's allow-list | blocked |
| `REPEATED_CALL` | (Week 5, `tool_agent`) same tool + same arguments again; one retry allowed only after `SERVICE_UNAVAILABLE` | blocked |
| `SERVICE_UNAVAILABLE` | temporary failure (used by fault injection for testing; marked `injected: true`) | tool_error |

**Output check (Week 5):** after every agent answer, `tool_agent.check_output()` removes any claim of a
draft or draft ID that was not created in that run and adds a system notice (failure F-13).

## Human approval gate — `src/approvals.py` (not a tool)

| Command | Effect |
|:---|:---|
| `py src\approvals.py list` | show drafts and status |
| `py src\approvals.py show <draft_id>` | show lines, totals, skipped items |
| `py src\approvals.py approve <draft_id> --by "Name" [--reason "..."]` | after typing `APPROVE`, status → `APPROVED` |
| `py src\approvals.py reject <draft_id> --by "Name" --reason "..."` | after typing `REJECT`, status → `REJECTED` |

Rules: only drafts still awaiting approval can be decided; rejection needs a reason (AC 10.3);
approving a draft with a capped line needs an override reason (US 12); every decision is appended to
`data/drafts/audit_log.jsonl` (AC 11.3). Approval records a decision only — ordering and payment stay
manual and outside the system.

## Observability

| File | One line per | Contents |
|:---|:---|:---|
| `evidence/week4/tool_traces.jsonl` | tool call | time, run_id, tool, role, args, status, latency, result |
| `evidence/week4/agent_traces.jsonl` | agent run | question, role, limits, models per turn, all tool calls, final answer, stop reason |
| `evidence/traces/llm_calls.jsonl` | model call | models tried, errors, latency (no text) |
