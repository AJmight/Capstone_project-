# BSE4104 AI Agentic Capstone: Week 8 Progress Report
**Topic:** Hardening, Final Release and Demonstration
**Student:** Mwesigwa Arnold Mugahi (Reg No: 23/U/24738/PS, GitHub: AJmight)
**Role:** AI Engineering Lead
**Date:** 20th October 2026
**Convener:** Dr. Kamulegeya Grace B (PhD)

---

## 1. Executive Summary

Week 8 was not a build week. It was the week in which the system was **proved**.
The work split into three parts:

1. **A hardening pass that found three real defects** in the Week 6 and Week 7 code
   that the existing unit tests had not covered: the MCP server could not execute a
   tool call at all (F-23), the human approval gate never advanced the state machine
   (F-24), and the MCP server let the model choose the tenant (F-25). All three are
   fixed and each fix has its own regression test.
2. **A documentation truth pass.** The failure catalogue was re-based onto one
   canonical id per failure so that the whole repository agrees on what "F-07"
   means, three unsupported claims were removed rather than kept, and the broken
   WSL links in the Week 6/7 documents were rewritten as relative links.
3. **The release.** The final engineering report, the final evaluation/evidence
   pack, the release tag `v1.0.0` and the demo script for the panel.

**Headline result:** every offline suite passes after the changes —
**Week 4 22/22 · Week 5 17/17 · MVP 7/7 · RAG hit@3 10/10 · Week 6 9/9 · Week 7 31/31 · Week 8 19/19**.

## 2. Key Accomplishments

### A. The hardening pass (three defects, three fixes)

| ID | Defect found | Fix | Regression test |
|:---|:---|:---|:---|
| **F-23** | `execute_tool()` was called with a keyword that does not exist and its `(result, status)` tuple was unpacked as a dict, so every real MCP `tools/call` failed with a `TypeError` reported as JSON-RPC `-32000` | Real signature, real unpacking, and the registry status is now reported to the client | `test_tools_call_executes_a_real_tool` |
| **F-24** | `approvals.decide()` recorded the human decision but never transitioned the Week 6 session, so a session could never leave `AWAITING_APPROVAL` | `StateManager.find_session_by_draft_id()` + a transition to `APPROVED`/`REJECTED` carrying the approver's name | `test_approval_moves_the_session_to_approved` |
| **F-25** | The MCP memory tools took `shop_id` from the **model's** arguments, which is the exact leak Week 6 set out to prevent | The server owns its tenant; a cross-shop request is refused with `TENANT_ISOLATION_VIOLATION` | `test_cross_shop_memory_request_is_refused` |

The common thread: **all three lived in code paths the tests had deliberately not
reached.** The Week 6 suite checked the MCP handshake and the tool list, but never
a tool call; the Week 7 suite checked the guardrail classes, but never the
approval gate that should have been calling one. See
[`week8-engineering-trail.md`](week8-engineering-trail.md) W8-1 to W8-3.

### B. The guardrails are now in the running system

`src/guardrails.py` was complete and tested, but only the tests called it. Week 8
wired it in where the product actually runs:

- `src/app.py` — the user's words are screened by `InputGuardrail.validate_user_prompt`
  before the model sees them, and the budget by `validate_budget` (F-18, F-21).
- `src/restock_agent.py` — `BudgetCeilingGuardrail` is consulted on the finished
  draft; a breach becomes the outcome `BUDGET_CEILING_EXCEEDED` and the session is
  terminated instead of handing a draft over for approval (F-12).
- `src/approvals.py` — the exact total above the allocated budget is refused
  outright, and the advisory ±10% estimate band above the budget needs an explicit
  override reason, which is written to the audit log next to the band and the
  allocated budget.

### C. The failure catalogue was re-based, not rewritten

The Week 7 draft numbered its findings `F-01…F-18` in a new order, so several ids
meant something different from what the Week 4 and Week 5 documents had always
meant by them, and three Week 2 entries had no supporting evidence at all. The
catalogue is now based on the numbering the weekly evaluation documents already
use (`F-01…F-16` keep their original meaning, the new Week 6–8 findings take
`F-17…F-25`), the unsupported entries were removed, and §3.2 of the catalogue
explains the change openly. Twenty-five failures are now documented; one (F-10) is
an open design note, one is mitigated by design (F-07) and one is monitored (F-08).

### D. The release

- `docs/final-report.md` — the final engineering report (10 sections, the brief's
  template).
- `evidence/final/` — the final evidence pack: one-page evaluation summary, the
  per-week results, the final failure catalogue, sampled traces, and the git
  history and tags.
- `v1.0.0` — the release tag, plus a tag per week so the progression is visible.
- `docs/ONBOARDING.md` and `docs/team/task-board.md` — updated so the group knows
  exactly what is left and who owns it.

## 3. Empirical Results — the final regression

| Suite | Command | Result |
|:---|:---|:---|
| Week 2 prompt cases (live, quota) | `py tests\test_week2_cases.py --live` | 9/10 on prompt v1.2.0 (recorded in `docs/evaluation/week2-prompt-evaluation.md`) |
| Week 3 RAG retrieval | `py tests\test_week3_rag.py --offline` | hit@3 **10/10**, context hit **10/10**, MRR **0.88** |
| Week 4 tools | `py tests\test_week4_tools.py --offline` | **22/22** (live 6/6 recorded) |
| Week 5 agent | `py tests\test_week5_agent.py --offline` | **17/17** |
| MVP console | `py tests\test_mvp_tools.py --offline` | **7/7** |
| Week 6 state & memory | `py tests\test_week6_state_memory.py` | **9/9** |
| Week 7 evaluation | `py tests\test_week7_evaluations.py` | **31/31** |
| Week 8 release checks | `py tests\test_week8_release_checks.py` | **19/19** |

All of them are offline: the release can be verified on a laptop with no model
quota left, which matters when the free tier allows 20 requests per model per day.

The evidence files in `evidence/` were regenerated by this run, so the numbers in
the report are the numbers in the repository.

## 4. Deliverables status (brief §9–10)

| # | Deliverable | Status | Where |
|:---:|:---|:---|:---|
| 1 | Final tagged release + run instructions | Done | tag `v1.0.0`, `README.md` §Quick Start |
| 2 | Final engineering report (8–12 pages) | Done | `docs/final-report.md` |
| 3 | Final evaluation / evidence pack | Done | `evidence/final/` |
| 4 | Presentation deck + live demonstration | Deck outline and demo script ready; **the deck file itself is still to be built by the Project/Requirements Lead** | `docs/final-report.md` §11, `evidence/final/README.md` |
| 5 | Completed board + final repository evidence | Board updated; git history and tags exported | `docs/team/task-board.md`, `evidence/final/git_history.txt`, `evidence/final/git_tags.txt` |

## 5. Honest limitations at the end of Week 8

- **F-10 stays open.** The 200% safety cap cannot be reached by the reorder formula
  itself; it only guards supplier MOQs and manual edits. Documented, not hidden.
- **R-4 stays open.** Keyword retrieval cannot reason that "800,000" lies between
  two approval thresholds. Full-sentence questions work; short numeric ones do not.
- **No live model call was made in Week 8.** Every change is deterministic code and
  every suite is offline, so the live traces in `evidence/week2…week5` remain the
  evidence for the model-facing behaviour.
- **The presentation deck is not built.** The content outline, timings and the live
  demo script are in the report; the slide file is the Project Lead's task before
  the 27th.
- **Single trusted user.** There are no user roles and no login; protecting the
  machine protects the shop's data (`docs/requirements/decision-001-single-trusted-user.md`).

## 6. AI tool usage this week

See [`week8-ai-log.md`](week8-ai-log.md). In short: Kilo for the hardening pass and
the release, Google Antigravity CLI for Weeks 6–7, Claude Code for Weeks 1–5,
`gemini-3.8-flash` as the runtime model, and DeepSeek/ChatGPT/Copilot for review
and completion. **No prompt was changed in Week 8** — the defects were in the
deterministic layer, and a prompt is not a fix for a function call.
