# Team Catch-Up Guide — start here

Written 2026-10-06 by Mwesigwa Arnold Mugahi (AI Engineering Lead) for the rest of the group.
Goal: in about **two hours** you can run the system, explain how it works, and pick up your own tasks.

> The code so far was built by the AI Engineering Lead with AI assistance (declared in the AI logs).
> In our reports, only list work **you** did. From today, each of us owns the tasks in §6 — that is
> our individual accountability, and reviewing/explaining existing work counts (§6 says how to record it).

---

## 1. What we are building (one minute)

A shop assistant for a small Ugandan stationery shop. It finds low stock, works out how much to order,
compares suppliers, answers questions about past purchases and shop policy, and **drafts** purchase
requisitions. **AI supports, never decides:** a person approves every draft; the AI cannot order or pay.

## 2. Where we are (as of 2026-10-06)

| Week | Topic | Status | Read |
|:---:|:---|:---|:---|
| 1 | Problem, users, stories, boundaries | ✅ | `docs/requirements/project-charter.md`, `user-stories.md`, `ai-boundary-matrix.md` |
| 2 | Model + prompts | ✅ | `docs/requirements/model-selection.md`, `prompts/prompt_history.md` |
| 3 | RAG (policy documents) | ✅ | `docs/notes/rag-explained.md` |
| 4 | Tools + function calling | ✅ | `docs/requirements/tool-catalogue.md` |
| 5 | Bounded agent | ✅ | `docs/requirements/agent-task-contract.md` |
| 6 | Memory, state, interoperability | ⏳ next | brief §7 Week 6 |
| 7 | 30+ scenario evaluation, guardrails | ⏳ | brief §7 Week 7 |
| 8 | Release, report, demo (presentations 27/29/30 Oct) | ⏳ | brief §9–10 |

Test status: offline 22 + 16 + 7 tests and RAG retrieval 10/10 (free to run); live suites all passing
on prompt v2.4.0. Weekly evidence is in `evidence/`, decisions in `docs/weekly-reports/week*-engineering-trail.md`.

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

# The app (uses a few AI calls per question)
py src\app.py
```
In the app, log in as `staff` and try:
1. **Ask:** "Which items are low on stock?" then "How many Bic Pens did we buy from March to May 2025?"
2. **Weekly restock:** budget `300000` — watch the Sense → Plan → Act → Observe → Stop timeline.
3. **Policy question:** "Who can approve a requisition of UGX 800,000?" — note the `[S1]` citation.
4. Log out (0), log in as `viewer`, ask it to "Draft a requisition for Rulers" — it must refuse.
5. Log in as `owner`, **Review drafts**, open one, edit a quantity, then approve or reject it.

Then open one trace: `evidence\week5\trace_T3_failure_recovery.md` — every step the agent took.

## 5. How it works (45 minutes of reading)

```
you ──► app.py ──► tool_agent / restock_agent ──► Gemini (decides WHICH tool next)
                          │
                          ▼
                    registry.py  (is this tool allowed for your role? are the arguments valid?)
                          │
                          ▼
                 procurement.py / knowledge.py  (Python does ALL the maths and lookups)
                          │
                          ▼
            data/*.csv · knowledge/corpus/*.md · data/drafts/*.json  ──► approvals.py (a PERSON decides)
```

Read in this order (every file has comments on each section):
1. `docs/notes/agentic-ai-notes.md` — the concepts in plain language (20 min).
2. `src/tools/procurement.py` — `_reorder_calculation()` is the core business rule.
3. `src/tools/registry.py` — `execute_tool()`, the gatekeeper.
4. `src/tool_agent.py` — `run_agent()`, the loop and its limits.
5. `src/restock_agent.py` — the Week 5 agent; read `run_restock()` top to bottom.
6. `src/approvals.py` — the human gate.
7. `docs/notes/rag-explained.md` + `src/rag/` — the RAG part.

## 6. Who owns what from now (proposal — agree it in our next meeting and put it in ClickUp)

| Role | Your tasks (Weeks 6–8) | Review task for work already done (counts as your contribution when recorded) |
|:---|:---|:---|
| **Project/Requirements Lead** | ClickUp board and weekly tasks; weekly reports (fill the `[name]` rows); final report structure (brief §9); presentation plan (brief §10) | Review `project-charter.md` and `user-stories.md`; propose changes; decide with the team whether to attempt story 3 (PDF quotes) |
| **Application/Integration Lead** | Web UI (Streamlit or Flask) calling the same functions as `src/app.py`; drafts "Pending approval" page (AC 10.1); deployment for the demo | Review `app.py`, `tool_agent.py`; list UI requirements |
| **Quality/Security Lead** | Week 7: 30+ scenario evaluation set and runner (normal, edge, wrong information, adversarial, tool failure, unauthorised); failure catalogue with re-tests; real login/passwords plan | Run every offline suite, review test docstrings, try to break the agent (prompt injection, role abuse) and log findings |
| **DevOps/Documentation Lead** | GitHub Actions running the offline tests on every push; tagged release `v1.0`; reproducible run instructions; keep `docs/` tidy | Review README and setup on a clean machine; report every step that fails |
| **AI Engineering Lead** | Week 6: SQLite state for drafts/audit, one justified memory feature, MCP-style tool interface; support the Quality Lead's evaluation | Explain the system to the team (walk-through session) |

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
2. What stops a viewer from creating a draft, even if the model tries? (F-07)
3. What are the agent's limits and what happens when one is hit?
4. How does the restock agent decide which items fit the budget, and who decides the rest?
5. What happens in trace T3, step by step?
6. What is RAG, and why does an unanswerable question get "not in the provided documents"?
7. Where is the human in the loop, and what is recorded when they decide?
8. Name two real failures we found and how we fixed them.

## 9. Help

- Big picture for humans and AI assistants: `docs/PROJECT_HANDOFF.md`, `AGENTS.md`
- Why something was done: `docs/weekly-reports/week*-engineering-trail.md`
- Ask the AI Engineering Lead.
