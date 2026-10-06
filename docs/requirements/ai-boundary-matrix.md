# AI Boundary Matrix

Week 1 deliverable, consolidated 2026-10-06 from the team's Week 1 document and updated to match the
system as built. Columns: what the **AI** does, what **code** enforces, what a **human** decides.

| Function | AI does | Code / system does | Human does | Where enforced |
|:---|:---|:---|:---|:---|
| Inventory viewing | Understands the request, picks `get_inventory`, explains | Reads CSV, filters category, flags low items | — | `procurement.get_inventory` |
| Low-stock flagging | Chooses `get_low_stock`, summarises | Applies `stock <= reorder_point` | Sets reorder points (per term) | `procurement.get_low_stock` |
| Quote comparison | Explains options | Sorts by price, tie → lead time | Chooses a dearer supplier with a written reason | `compare_supplier_quotes` |
| Reorder quantity | Explains the working | `ceil(avg × 1.5 − stock)`, MOQ, exact fractions | Sets quantity for items without history | `estimate_reorder_quantity` |
| Budget planning | Decides to plan, explains deferred items | Urgency order, greedy fit within budget | Funds deferred items or not | `plan_within_budget` |
| Draft requisition | Decides which items to request (named/planned) | Builds lines, totals, ±10 %, ID, date, creator; skips well-stocked items | — | `draft_requisition` |
| Historical questions | Interprets period, asks to clarify vague questions | Exact totals, data range | — | `query_purchase_history` |
| Policy questions | Answers only from retrieved passages, cites them | BM25 retrieval, score gate, citation check | Maintains the policy documents | `rag/`, `search_policy` |
| Manual override | — | Recalculates totals and cap; logs original + reason | Changes the quantity, gives a reason | `approvals.edit_quantity` |
| Approval | **Never** (no tool exists; refuses) | Requires typed confirmation; reasons for reject/over-cap; audit log | **Approves or rejects** | `approvals.decide` |
| Ordering / payment | **Never** (refuses) | No integration exists | Places order and pays outside the system | — |
| Safety cap 200 % | Points out flagged lines | Flags `requires_override` | Justifies or rejects | `_reorder_calculation`, `approvals` |
| Permissions | — | Role allow-list per tool; task allow-list; parameter validation | Assigns roles | `registry.execute_tool`, `tool_agent` |
| Limits & stopping | Chooses next step within limits | Max turns/tool calls, repeat guard, post-conditions, outcome | Takes over on hand-off | `tool_agent`, `restock_agent` |
| Audit | — | Tool, agent, model-call and approval traces | Reviews traces | `evidence/`, `data/drafts/audit_log.jsonl` |
