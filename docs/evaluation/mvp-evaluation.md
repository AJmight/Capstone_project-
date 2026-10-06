# MVP Evaluation — up to Week 5 (2026-10-06)

All automated evidence in one table. Offline suites are free and deterministic; live suites use Gemini.

| Suite | File | Kind | Result (final run) | Evidence |
|:---|:---|:---|:---:|:---|
| Week 2 prompt cases | `tests/test_week2_cases.py` | live (context mode, v1.2.0) | 9/10 (Week 2) | `docs/evaluation/week2-prompt-evaluation.md` |
| Week 3 retrieval | `tests/test_week3_rag.py --offline` | offline | hit@3 10/10, MRR 0.88 | `evidence/week3/retrieval_results_index_v1.1.0.md` |
| Week 3 answers | `tests/test_week3_rag.py --live` | live | 15/15 (run 1: 13/15) | `evidence/week3/answer_results*.md` |
| Week 4 tools/registry/approvals | `tests/test_week4_tools.py --offline` | offline | 22/22 | `evidence/week4/offline_results.md` |
| Week 4 agent | `tests/test_week4_tools.py --live` | live (v2.4.0) | 6/6 | `evidence/week4/live_results.md` |
| Week 5 agent guards | `tests/test_week5_agent.py --offline` | offline (scripted fake model) | 16/16 | `evidence/week5/offline_results.md` |
| Week 5 traces | `tests/test_week5_agent.py --live` | live (v2.4.0) | 4/4 | `evidence/week5/trace_T*.md` |
| MVP additions | `tests/test_mvp_tools.py --offline` | offline | 7/7 | `evidence/mvp/offline_results.md` |
| MVP agent | `tests/test_mvp_tools.py --live` | live (v2.4.0) | 6/6 (run 1: 4/6) | `evidence/mvp/live_results*.md` |

## MVP live cases

| Case | Question (role viewer) | Tools | Result |
|:---|:---|:---|:---:|
| M-01 | Show me the stock levels for Office items | `get_inventory` | PASS |
| M-02 | How many Bic Pens did we buy from March to May 2025, and how much did we spend? | `query_purchase_history` | PASS — 170 units, UGX 79,295 |
| M-03 | Tell me about our purchases. | none | PASS — asked which item/period (AC 6.2) |
| M-04 | Who is allowed to approve a requisition worth UGX 800,000? | `search_policy` | PASS — owner, cites POL-01 |
| M-05 | How many rulers did we buy in November 2024? | `query_purchase_history` | PASS — 0 recorded; data covers 2025 (run 1 "FAIL" was a keyword-check error) |
| M-06 | Show me inventory for dairy products. | `get_inventory` | PASS on v2.4.0 (run 1 FAIL → **F-16**) |

## Failure catalogue additions

| ID | Failure | Fix | Status |
|:---:|:---|:---|:---|
| F-16 | Model ignored an `UNKNOWN_CATEGORY` error listing real categories and gave a generic refusal | Prompt v2.4.0 error rule | Fixed (M-06 PASS) |
| F-07 (recurring) | Viewer's model again requested `draft_requisition` (not offered to it) in Week 4 L-05 on v2.4.0 | Registry blocked it | Mitigated by design |
| T-03 | Third brittle keyword check (M-05) | Accept correct phrasings; Week 7 to use a rubric | Test fixed |

Full Week 3 failures (R-1…R-5): `docs/evaluation/week3-rag-evaluation.md`.
