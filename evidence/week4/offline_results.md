# Week 4 Offline Tool Tests

Run at 2026-10-03T02:26:00 | **22/22 passed**

| id | test | passed | detail |
|---|---|---|---|
| O-01 | get_low_stock returns exactly the items with stock <= reorder point. | **PASS** |  |
| O-02 | estimate_reorder_quantity matches the independent formula for every low item (F-04). | **PASS** |  |
| O-03 | The three quantities gemini-3.5-flash-lite got wrong in Week 2 are now exact. | **PASS** |  |
| O-04 | A4 Exercise Books (stock 45 > 10) is never recommended (Week 2 TC-06 problem). | **PASS** |  |
| O-05 | Items without purchase history get 0 and a human-must-decide basis (no invented default). | **PASS** |  |
| O-06 | compare_supplier_quotes lists quotes cheapest first. | **PASS** |  |
| O-07 | Items can be named the way users talk ('bic pens (blue)', 'calculator'). | **PASS** |  |
| O-08 | 'pens' matches two items -> AMBIGUOUS_ITEM; 'ITM999' -> UNKNOWN_ITEM. No guessing. | **PASS** |  |
| O-09 | draft_requisition computes lines, totals, +/-10% range and saves a DRAFT record. | **PASS** |  |
| O-10 | Well-stocked items are skipped with a reason; only low items get lines. | **PASS** |  |
| O-11 | If no requested item is low, no draft file is written. | **PASS** |  |
| O-12 | MOQ can push a quantity over 200% of the largest past purchase -> requires_override. | **PASS** |  |
| O-13 | A missing CSV gives INVALID_DATA, not a crash (simulated unavailable service). | **PASS** |  |
| O-14 | A CSV without reorder_point, or with a non-number, gives INVALID_DATA naming the problem. | **PASS** |  |
| O-15 | Asking for a tool that is not on the allow-list (e.g. approve_requisition) is blocked. | **PASS** |  |
| O-16 | A viewer cannot draft (blocked), and is not even shown the draft tool. | **PASS** |  |
| O-17 | Missing, extra, wrong-type and empty arguments are rejected before the tool runs. | **PASS** |  |
| O-18 | created_by comes from the session; the model trying to set it is rejected. | **PASS** |  |
| O-19 | A crashing tool -> TOOL_ERROR; a tool returning a non-dict -> UNEXPECTED_RESPONSE. | **PASS** |  |
| O-20 | Allowed and blocked calls are both written to the tool trace. | **PASS** |  |
| O-21 | Humans approve/reject in approvals.py: reasons required, no double decisions, audit log. | **PASS** |  |
| O-22 | Approving a draft with a line over the 200% cap requires a reason (US 12). | **PASS** |  |
