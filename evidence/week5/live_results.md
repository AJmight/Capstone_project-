# Week 5 Live Execution Traces

Run at 2026-10-03T02:20:34 | **4/4 passed**

| id | budget | expected | outcome | models | postconditions | trace | passed |
|---|---|---|---|---|---|---|---|
| T1_happy_path | UGX 2,000,000 | DRAFT_READY; 6 priced items, UGX 1,619,289; 4 needs-human items handed off | DRAFT_READY | gemini-3.6-flash, gemini-3.6-flash, gemini-3.5-flash-lite | 6/6 | trace_T1_happy_path.md | **PASS** |
| T2_budget_replan | UGX 300,000 | DRAFT_READY; re-plan keeps 4 most urgent (UGX 294,130), defers ITM007/ITM006 | DRAFT_READY | gemini-3.7-flash, gemini-3.7-flash, gemini-3.5-flash | 6/6 | trace_T2_budget_replan.md | **PASS** |
| T3_failure_recovery | UGX 300,000 | plan tool fails once (injected) -> one retry -> RECOVERED -> DRAFT_READY | DRAFT_READY | gemini-3.6-flash, gemini-3.6-flash, gemini-3.6-flash, gemini-3.6-flash | 6/6 | trace_T3_failure_recovery.md | **PASS** |
| T4_safe_stop | UGX 10,000 | NOTHING_FITS_BUDGET; no draft; human told why | NOTHING_FITS_BUDGET | gemini-3.6-flash, gemini-3.5-flash | 2/2 | trace_T4_safe_stop.md | **PASS** |
