# Final Evaluation Summary — SME Procurement Preparation Agent

**Project:** BSE4104 capstone · **Release:** `v1.0.0` · **Date:** 20 October 2026
**One page.** If a marker reads only one page of this project, it should be this one.

---

## 1. All-week test results

| Week | Suite | Command | Result | Model calls |
|:---:|:---|:---|:---:|:---:|
| 2 | Prompt cases (live) | `py tests\test_week2_cases.py --live` | 9/10 on prompt v1.2.0 | ~15 |
| 3 | RAG retrieval + answers | `py tests\test_week3_rag.py --offline` | hit@3 **10/10**, context hit 10/10, MRR 0.88; answers 15/15 (live) | 0 offline |
| 4 | Tools | `py tests\test_week4_tools.py --offline` | **22/22** (live 6/6) | 0 offline |
| 5 | Bounded agent | `py tests\test_week5_agent.py --offline` | **17/17** (4 live traces) | 0 offline |
| MVP | Console behaviours | `py tests\test_mvp_tools.py --offline` | **7/7** (live 6/6) | 0 offline |
| 6 | State, memory, MCP | `py tests\test_week6_state_memory.py` | **9/9** | 0 |
| 7 | 31-scenario evaluation | `py tests\test_week7_evaluations.py` | **31/31** | 0 |
| 8 | Release checks | `py tests\test_week8_release_checks.py` | **19/19** | 0 |
| | **Total offline** | | **105 / 105** | **0** |

The full offline regression is 105 of 105. Verbatim output of the release run:
[`regression_run_2026-10-20.md`](regression_run_2026-10-20.md).

**Why "0 model calls" matters.** The free tier allows 20 requests per model per
day. A release that can only be verified with quota left is a release nobody can
check. Every suite in this table runs with no network and no API key.

## 2. Week 7 category breakdown

| Category | Scenarios | Passed | Note |
|:---|:---:|:---:|:---|
| Normal operations | 5 | 5 | stock sensing, quote sorting, MOQ arithmetic, budget planning, session progression |
| Edge conditions | 6 | 6 | zero/negative budget, budget below MOQ, absurd budget, no history, empty prompt |
| Corrupted / missing data | 5 | 5 | unknown ids, SQL injection in `shop_id`, non-numeric budgets, empty payloads |
| Adversarial | 5 | 5 | prompt injection, auto-approval commands, disbursement requests, cross-shop spoofing, script payloads |
| Tool / infrastructure failure | 5 | 5 | budget overrun, missing session, corrupted memory, closed database, unauthorised transition |
| Unauthorised action | 5 | 5 | the AI attempting to approve, pay, sign a PO or bind a supplier |
| **Total** | **31** | **31** | |

## 3. Failure catalogue summary

**25 failures** documented (F-01 … F-25) across Weeks 2–8:
**21 closed · 1 mitigated by design (F-07) · 1 monitored (F-08) · 1 open design note (F-10).**

| Week | Failures | Highlights |
|:---:|:---:|:---|
| 2 | F-01…F-06 | scope and arithmetic errors under injection (F-04, later fixed by moving the maths into tools), quota exhaustion, a 404 model, a broken test checker, a formatter that ate a formula |
| 4 | F-07…F-11 | the model calling a tool it was never given (the allow-list blocked it), a cap that cannot trigger from the formula alone (still open), a wrongly computed confirmation word |
| 5 | F-12…F-15 | the estimate band reaching above the budget (F-12, closed by a hard ceiling), a false draft claim, a self-contradictory prompt, Gemini's floats |
| 6 | F-17, F-20, F-22 | cross-shop memory leakage, a workflow state bypass, a counter drift |
| 7 | F-18, F-19, F-21 | prompt injection, autonomous financial authority, a hostile `shop_id` |
| 8 | F-23, F-24, F-25 | the MCP server could not call a tool at all, the approval gate never moved the state machine, the MCP server let the model choose the tenant |

Full detail with root causes, fixes and the test that proves each one:
[`../../docs/evaluation/failure-catalogue.md`](../../docs/evaluation/failure-catalogue.md).

**The three Week 8 failures are the most interesting ones**, because all three
survived a passing test suite. They were found by asking, for each deliverable,
*which production code path does this actually use, and does a test reach it?*

## 4. The system's core safety claims, and how each is proven

| Claim | How it is enforced | The test |
|:---|:---|:---|
| The model never computes a business figure | all arithmetic in `src/tools/procurement.py` | O-02, O-03, O-09 |
| The model cannot approve, order or pay | **no such tool exists**; the registry allow-list refuses it | O-15, O-16, SCEN_27…SCEN_31 |
| A human approves every requisition | `src/approvals.py`, typed confirmation, reasons, audit log | O-21, O-22, M-O06, M-O07 |
| The agent is bounded and always stops | 5 turns / 6 tool calls / 3 tools, repeat guard, code-decided outcome | A-04, A-08, A-10, A-12, A-13 |
| The workflow cannot skip the human | `VALID_TRANSITIONS` graph; `APPROVED` only from `AWAITING_APPROVAL` | `test_invalid_state_transition_blocked`, `test_approval_moves_the_session_to_approved` |
| One shop cannot read another's data | `shop_id` partition in SQL; the MCP server owns its tenant | `test_multi_tenant_isolation`, `test_cross_shop_memory_request_is_refused` |
| Policy answers come from the documents | BM25 retrieval, score gate, citation check | RA-01…RA-10, answers 15/15 |
| The budget is a ceiling, not a suggestion | `BudgetCeilingGuardrail` in the agent **and** in the approval gate | SCEN_22, `test_over_budget_draft_cannot_be_approved` |

## 5. Reproducibility

```powershell
git clone https://github.com/AJmight/Capstone_project-
cd Capstone_project-
py -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env     # your own GEMINI_API_KEY (only needed for the live suites)
py tests\test_week8_release_checks.py
```

The runtime SQLite store is created on first run and is git-ignored, so a clean
clone behaves exactly like the development machine. The synthetic data is
generated with a fixed seed, and the expected values in the tests are computed
from those CSVs rather than typed in by hand.

## 6. The honest summary

The system works as an **assistant**: it senses stock, computes quantities, compares
quotes, plans within a budget, drafts requisitions, answers policy questions with
citations, and stops. It cannot approve, order or pay, by construction rather
than by instruction, and every one of those statements above has a test.

It is not an autonomous purchasing system and was never meant to be. The value is
in the draft, the explanation and the audit trail; the decision stays with a
person who can edit a quantity, ask for a reason, and walk away.
