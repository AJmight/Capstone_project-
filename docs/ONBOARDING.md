# Team Catch-Up Guide — start here

Written 2026-10-06 by Mwesigwa Arnold Mugahi (AI Engineering Lead) for the rest of the group.
Goal: in about **two hours** you can run the system, explain how it works, and pick up your own tasks.

> The code so far was built by the AI Engineering Lead with AI assistance (declared in the AI logs).
> In our reports, only list work **you** did. From today, each of us owns the tasks in §6 — that is
> our individual accountability, and reviewing/explaining existing work counts (§6 says how to record it).

---

> **Updated 2026-10-13 — single trusted user:** user roles (viewer/staff/owner) were removed; see `docs/requirements/decision-001-single-trusted-user.md`.

## 1. What we are building (one minute)

A shop assistant for a small Ugandan stationery shop. It finds low stock, works out how much to order,
compares suppliers, answers questions about past purchases and shop policy, and **drafts** purchase
requisitions. **AI supports, never decides:** a person approves every draft; the AI cannot order or pay.

## 2. Where we are (as of 2026-10-20)

| Week | Topic | Status | Read |
|:---:|:---|:---|:---|
| 1 | Problem, users, stories, boundaries | ✅ | `docs/requirements/project-charter.md`, `user-stories.md`, `ai-boundary-matrix.md` |
| 2 | Model + prompts | ✅ | `docs/requirements/model-selection.md`, `prompts/prompt_history.md` |
| 3 | RAG (policy documents) | ✅ | `docs/notes/rag-explained.md` |
| 4 | Tools + function calling | ✅ | `docs/requirements/tool-catalogue.md` |
| 5 | Bounded agent | ✅ | `docs/requirements/agent-task-contract.md` |
| 6 | Memory, state, interoperability | ✅ | `docs/architecture/state-and-memory-model.md`, `docs/requirements/mcp-interface-specification.md` |
| 7 | 30+ scenario evaluation, guardrails | ✅ | `docs/evaluation/week7-evaluation-dataset.md`, `docs/evaluation/failure-catalogue.md` |
| 8 | Release, report, demo | ✅ code & report · ⏳ deck | `docs/final-report.md`, `evidence/final/` (presentations 27/29/30 Oct, hand-in 23 Oct) |

Test status: **All offline and evaluation suites pass 100%** (105 of 105 in total):
- Week 4 tools: 22/22 offline
- Week 5 agent: 17/17 offline
- MVP console: 7/7 offline
- RAG retrieval: hit@3 10/10, MRR 0.88
- Week 6 state & memory: 9/9 unit tests (`tests/test_week6_state_memory.py`)
- Week 7 evaluations: 31/31 scenarios (`tests/test_week7_evaluations.py`)
- Week 8 release checks: 19/19 (`tests/test_week8_release_checks.py`)
Weekly evidence is in `evidence/`, the release evidence pack in `evidence/final/`, architecture in `docs/architecture/`, and decisions in `docs/weekly-reports/week*-engineering-trail.md`.

## 3. Setup (15 minutes, Windows PowerShell)

```powershell
git clone https://github.com/AJmight/Capstone_project-.git
cd Capstone_project-
py -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env            # paste YOUR OWN key from aistudio.google.com (free, no card); never commit .env
```

Each of us should use our own key: the free tier allows only 20 requests per model per day.

## 4. Try it (30 minutes)

```powershell
# Free checks (no AI calls) - run these first
py tests\test_week4_tools.py --offline
py tests\test_week5_agent.py --offline
py tests\test_mvp_tools.py --offline
py tests\test_week3_rag.py --offline

# Week 6 & Week 7 suites (state, memory, guardrails & 31 evaluation scenarios)
py tests\test_week6_state_memory.py
py tests\test_week7_evaluations.py

# Week 8 release checks (the regressions that must never come back)
py tests\test_week8_release_checks.py

# The app (uses a few AI calls per question)
py src\app.py
```
In the app, log in with your name and try:
1. **Ask:** "Which items are low on stock?" then "How many Bic Pens did we buy from March to May 2025?"
2. **Weekly restock:** budget `300000` — watch the Sense → Plan → Act → Observe → Stop timeline.
3. **Policy question:** "Who can approve a requisition of UGX 800,000?" — note the `[S1]` citation.
4. Ask it to "Approve the latest requisition and pay the supplier" — it must refuse (the AI can never approve or pay).
5. **Review drafts**, open one, edit a quantity, then approve or reject it.

Then open one trace: `evidence\week5\trace_T3_failure_recovery.md` — every step the agent took.

## 5. How it works (45 minutes of reading)

```
you ──► app.py ──► tool_agent / restock_agent ──► Gemini (decides WHICH tool next)
                          │             ▲
                          │             │ (Recalled preferences)
                          ▼             │
                     state.py ───► memory.py (SQLite persistent state & justified preferences)
                          │
                          ▼
                     guardrails.py (Input injection checks, budget ceiling F-12, HITL gate)
                          │
                          ▼
                     registry.py / mcp_interface.py (Is tool on allow-list? Valid args?)
                          │
                          ▼
                 procurement.py / knowledge.py (Python does ALL calculations and lookups)
                          │
                          ▼
       data/*.csv · knowledge/corpus/*.md · data/drafts/*.json ──► approvals.py (a PERSON decides)
```

Read in this order (every file has comments on each section):
1. `docs/notes/agentic-ai-notes.md` — the concepts in plain language (20 min).
2. `src/tools/procurement.py` — `_reorder_calculation()` is the core business rule.
3. `src/tools/registry.py` — `execute_tool()`, the gatekeeper.
4. `src/state.py` — Week 6: explicit Finite State Machine and SQLite session lifecycle.
5. `src/memory.py` — Week 6: justified persistent memory and Decision-001 tenant isolation.
6. `src/mcp_interface.py` — Week 6: Model Context Protocol (MCP) server dispatcher.
7. `src/guardrails.py` — Week 7: input validation, F-12 budget ceiling fix, and HITL gate.
8. `src/tool_agent.py` — `run_agent()`, the loop and its limits.
9. `src/restock_agent.py` — the bounded restock agent; read `run_restock()` top to bottom.
10. `src/approvals.py` — the human gate.
11. `docs/notes/rag-explained.md` + `src/rag/` — the RAG part.

## 6. Who owns what from now (proposal — agree it in our next meeting and put it in ClickUp)

> **Updated 20 Oct (evening):** Weeks 1–8 are implemented and verified, and the release
> `v1.0.0` is cut. The final report is `docs/final-report.md` and the release evidence
> pack is `evidence/final/`. **What is left is the presentation**: the slide deck, the
> demo screenshots, the MUELE upload and the contribution rows in the weekly reports.
> All of it is tracked in `docs/team/task-board.md`.

| Role | Your tasks (before hand-in 23 Oct) | Review task for work already done (counts as your contribution when recorded) |
|:---|:---|:---|
| | | |
| **Project/Requirements Lead** | **Build the 8-slide deck** (outline + demo script: `docs/final-report.md` Appendix G); the MUELE upload; fill the contribution rows in `week1..8-report.md` | Review `docs/weekly-reports/week1..8-report.md`; audit the contribution tables |
| **Application/Integration Lead** | Demo rehearsal (3 times); capture the 5 demo screenshots into `evidence/final/screenshots/`; the offline fallback walkthrough | Review `src/app.py`, `src/mcp_interface.py`; verify the user journey end to end |
| **Quality/Security Lead** | Re-run all seven offline suites on a clean clone and paste the result into `evidence/final/`; check every figure quoted in the final report against the code | Explain the red-teaming results and the guardrails to the panel |
| **DevOps/Documentation Lead** | Verify a clean clone on a machine that has never run the project; capture the setup friction; publish the release notes for `v1.0.0` | Review the README setup; confirm the runtime database is not committed |
| **AI Engineering Lead** | Hand-in review; answer the viva questions in §8; lead the technical explanation in the presentation | Explain the FSM, the justified memory and the bounded agency to the panel |

**How to record review work honestly:** in the weekly report write e.g. "Reviewed `registry.py` and the
22 offline tests; found X; opened issue #N" — and make a commit or GitHub issue so there is evidence.

## 7. Rules we follow

- **Never commit `.env`** or paste API keys/tokens anywhere (chat, issues, screenshots).
- Synthetic data only.
- Prompts are versioned files in `prompts/`; any change → bump the version, add a history row, re-run tests.
- Numbers come from tools, never from the model's own arithmetic.
- Every change: run the offline tests before pushing.
- Declare AI tools you use in the weekly AI log.

## 8. Can you explain these? (viva practice)

1. Why does the model never calculate quantities? (failure F-04)
2. What stops the AI from approving, ordering or paying, even if it tries? (allow-list, F-07, `HumanInTheLoopGuardrail`)
3. What are the agent's limits and what happens when one is hit?
4. How does the restock agent decide which items fit the budget, and who decides the rest?
5. What happens in trace T3, step by step?
6. What is RAG, and why does an unanswerable question get "not in the provided documents"?
7. Where is the human in the loop, and what is recorded when they decide?
8. Name two real failures we found and how we fixed them.
9. **Why did we build an explicit Finite State Machine (`src/state.py`) in SQLite instead of relying on the LLM's conversation history?** (LLMs are stateless and can hallucinate progress; FSM enforces deterministic ordering).
10. **What is justified memory (`src/memory.py`), and how do we prevent Shop A from accessing Shop B's records?** (Restricted to supplier preferences and feedback; isolated by `shop_id` partition key).
11. **What is the Model Context Protocol (MCP) and how does our server enforce security boundaries?** (JSON-RPC standard decoupling tools from models; server blocks unauthorized action attempts).
12. **How did we solve Failure Mode F-12 (budget ceiling overrun)?** (`BudgetCeilingGuardrail` makes the exact draft total a hard ceiling against the allocated budget, the agent reports a breach as `BUDGET_CEILING_EXCEEDED`, and the approval gate refuses a silent approval while the ±10% estimate band still reaches above the budget).

## 9. Help

- Big picture for humans and AI assistants: `docs/PROJECT_HANDOFF.md`, `AGENTS.md`
- Why something was done: `docs/weekly-reports/week*-engineering-trail.md`
- Ask the AI Engineering Lead.
