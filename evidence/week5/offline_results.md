# Week 5 Offline Agent Tests

Run at 2026-10-06T06:21:03 | **16/16 passed**

| id | test | passed | detail |
|---|---|---|---|
| A-01 | Ideal model, UGX 300,000: plan -> draft of exactly the 4 included items (UGX 294,130). | **PASS** |  |
| A-02 | Deferred items, needs-human items and the approval step are listed for the human. | **PASS** |  |
| A-03 | plan_within_budget fails once (injected) -> retried once -> recovery recorded -> DRAFT_READY. | **PASS** |  |
| A-04 | Fails twice: the second retry is blocked by the repeat guard; no draft is made. | **PASS** |  |
| A-05 | UGX 10,000: nothing fits -> no draft -> NOTHING_FITS_BUDGET. | **PASS** |  |
| A-06 | A model that drafts items outside the plan is caught: POSTCONDITION_FAILED, flagged on the draft. | **PASS** |  |
| A-07 | Two drafts in one run break 'at most one draft' -> POSTCONDITION_FAILED. | **PASS** |  |
| A-08 | A model repeating the same call is blocked (REPEATED_CALL) and stopped by the turn limit. | **PASS** |  |
| A-09 | compare_supplier_quotes is a real tool but not in this task's contract -> blocked. | **PASS** |  |
| A-10 | Every model 503 -> HANDOFF_MODEL_UNAVAILABLE with a clear message; no draft. | **PASS** |  |
| A-11 | If the summary omits 'AWAITING HUMAN APPROVAL', the run is not reported as ready. | **PASS** |  |
| A-12 | Viewer role or a bad budget stops before any model call (fake would crash if called). | **PASS** |  |
| A-13 | If nothing is low, SENSE stops the run (NOTHING_TO_DO) without spending model quota. | **PASS** |  |
| A-14 | plan_within_budget: urgency order, skip-and-continue, needs_human, budget validation. | **PASS** |  |
| A-15 | The Markdown trace has the phases a marker looks for. | **PASS** |  |
| A-16 | F-13: a viewer's model writes a fake 'awaiting approval' summary -> code corrects and flags it. | **PASS** |  |
