# User Stories and Acceptance Criteria

Consolidated on 2026-10-06 from the Week 1 document `User stories and acceptance criteria (2).docx`
(repository root). The original stories used examples such as sugar, dairy and cooking oil; our synthetic
data is a stationery shop, so examples are aligned with the data. Status shows what the MVP implements.

**Roles:** Procurement Officer = staff; Shop Owner/Manager = owner; Viewer = read-only staff.

| # | Story | Acceptance criteria (aligned) | Status | Implemented by / evidence |
|:---:|:---|:---|:---:|:---|
| 1 | **Inventory viewing** — as staff, I want to view current inventory levels | AC 1.1 list all items with quantities. AC 1.2 "show inventory for Office items" shows only that category; an unknown category (e.g. "dairy") lists the real categories | ✅ (console; dashboard in Week 8) | `get_inventory`; tests M-O01, M-O02, M-01, M-06 |
| 2 | **Low-stock flagging** | AC 2.1 items at/below reorder point are flagged. AC 2.2 "What is low?" lists them with a suggested quantity | ✅ | `get_low_stock`, `estimate_reorder_quantity`; O-01, L-01 |
| 3 | **Quote upload & parsing** (PDF) | AC 3.1 extract item, price, total from a PDF quote. AC 3.2 unreadable format → clear error | ❌ descoped for MVP | Quotes come from `supplier_quotes.csv`; candidate for Week 6–8 if time allows |
| 4 | **Quote comparison** | AC 4.1 compare suppliers' prices and lead times for an item. AC 4.2 best offer by lowest price (tie → faster delivery). Delivery fees are not in the data (policy docs describe them) | ✅ | `compare_supplier_quotes`; O-06, L-02 |
| 5 | **Draft requisition** | AC 5.1 draft lists items, quantities, total. AC 5.2 unique ID, date, creator | ✅ | `draft_requisition`; O-09 |
| 6 | **Historical query** | AC 6.1 "How many Bic Pens did we buy from March to May 2025?" returns the exact total. AC 6.2 a vague question gets a clarifying question | ✅ | `query_purchase_history`; M-O03, M-02, M-03 |
| 7 | **Trend-based reorder estimate** | AC 7.1 based on average monthly purchases (demand proxy). AC 7.2 shows the reasoning trail | ✅ | `estimate_reorder_quantity` `basis`; O-02, L-02 |
| 8 | **Budget range** | AC 8.1 low/high estimate (±10 %) | ✅ | `draft_requisition` `budget_range_ugx`; O-09 (note F-12) |
| 9 | **Manual override** | AC 9.1 change a quantity before approval. AC 9.2 log the override and the original suggestion | ✅ | `approvals.py edit`; M-O06, M-O07 |
| 10 | **Manager approval** | AC 10.1 pending drafts visible. AC 10.2 approve → "APPROVED" + audit. AC 10.3 reject needs a reason | ✅ (CLI/console) | `approvals.py`, `app.py` option 4; O-21 |
| 11 | **Audit lineage** | AC 11.1 interactions logged with time and user. AC 11.2 agent decisions in a trace. AC 11.3 requisition changes logged | ✅ | `evidence/week4/*traces.jsonl`, `evidence/week5/`, `data/drafts/audit_log.jsonl` |
| 12 | **Safety guardrail (200 %)** | AC 12.1 a quantity > 200 % of the largest past purchase is flagged and needs an override reason to approve | ✅ | `safety_cap`, `requires_override`; O-12, O-22, M-O07 |

**Coverage:** 11 of 12 stories implemented in the MVP; story 3 descoped with reason.
