# Team Task Board — remaining work (Weeks 6–8 + presentation)

Created 2026-10-13. Copy these cards into **Trello** (or ClickUp — the brief names ClickUp as evidence;
`docs/team/task-board.csv` can be imported there). Put the person's name on each card once roles are
agreed, attach the commit/PR link when done, and move the card through the lists:

**Lists:** `Backlog` → `This week` → `In progress` → `Review (another member checks)` → `Done`
**Labels:** `week-6`, `week-7`, `week-8`, `presentation`, `review-of-existing-work`, `blocked`

**Timeline (working back from the deadlines):**

| Window | Focus |
|:---|:---|
| Tue 13 – Wed 14 Oct | Everyone onboarded; board set up; reviews of existing work start |
| Wed 14 – Fri 16 Oct | Week 6: persistent state, memory, interoperability; CI |
| Fri 16 – Tue 20 Oct | Week 7: 30+ scenario evaluation, guardrails, failure catalogue; web UI |
| Tue 20 – Fri 23 Oct | Week 8: hardening, release `v1.0`, final report (**hand-in 23 Oct**) |
| Fri 23 – Mon 26 Oct | Presentation deck, demo rehearsal (**presentations 27/29/30 Oct**) |

Rule for every card: **only record work you did yourself.** Review cards count when you leave evidence
(a GitHub issue, a commit, or notes in `docs/reviews/<your-name>.md`).

---

## Everyone

| Card | Due | Checklist |
|:---|:---:|:---|
| **ALL-1 Onboarding: run the MVP** | 14 Oct | ☐ clone repo, venv, `pip install -r requirements.txt` ☐ own Gemini key in `.env` (never commit it) ☐ run the 4 offline suites (README "Run") ☐ `py src\app.py`: try the 5 scenarios in `docs/ONBOARDING.md` §4 ☐ read `docs/notes/agentic-ai-notes.md` ☐ screenshot to `evidence/screenshots/onboarding-<name>.png` |
| **ALL-2 Viva practice** | 26 Oct | ☐ answer the 8 questions in `docs/ONBOARDING.md` §8 without notes ☐ explain one trace (`evidence/week5/trace_T3_failure_recovery.md`) to a teammate |

## Project / Requirements Lead

| Card | Due | Checklist |
|:---|:---:|:---|
| **PR-1 Set up the board** | 14 Oct | ☐ create lists/labels above ☐ add all cards ☐ assign names ☐ share board link in the weekly reports |
| **PR-2 Review requirements** `review-of-existing-work` | 15 Oct | ☐ read `docs/requirements/project-charter.md`, `user-stories.md`, `ai-boundary-matrix.md` ☐ list corrections as GitHub issues ☐ team decision on User Story 3 (PDF quotes): attempt or keep descoped |
| **PR-3 Contribution tables** | 15 Oct | ☐ fill the `[name]` rows in `docs/weekly-reports/week1…5-report.md` with what each person actually did (e.g. reviews) — no invented work |
| **PR-4 Week 6 report** | 16 Oct | ☐ `docs/weekly-reports/week6-report.md` in the same format (brief §8) ☐ links to commits and cards |
| **PR-5 Week 7 report** | 20 Oct | ☐ `week7-report.md` (max 2 pages) |
| **PR-6 Final engineering report** | 22 Oct | ☐ skeleton with the 10 sections of brief §9 by 17 Oct ☐ assign sections to owners ☐ merge, 8–12 pages ☐ appendices list ☐ references verified |
| **PR-7 Presentation** `presentation` | 25 Oct | ☐ deck following brief §10 timings ☐ demo script: success path, evidence view, real failure, human approval ☐ rehearse twice with timing |

## Application / Integration Lead

| Card | Due | Checklist |
|:---|:---:|:---|
| **AP-1 Review the app layer** `review-of-existing-work` | 14 Oct | ☐ read `src/app.py`, `src/tool_agent.py`, `src/approvals.py` ☐ write UI requirements (pages, roles) ☐ choose framework (Streamlit is simplest) |
| **AP-2 Web UI: core pages** | 18 Oct | ☐ login screen (name + password, linked to the user's shop — coordinate with AI-2) ☐ Chat page → `run_agent()` ☐ Weekly restock page → `run_restock()` with timeline ☐ Policy Q&A page → `answer_policy_question()` with sources ☐ Stock page → `get_inventory()` |
| **AP-3 Pending-approval page (US 10, AC 10.1)** | 19 Oct | ☐ list drafts awaiting approval ☐ edit / approve / reject (typed confirmation) using `approvals.edit_quantity()` and `approvals.decide()` ☐ reason required for reject and over-cap lines |
| **AP-4 Evidence view for the demo** | 21 Oct | ☐ page showing the last run's trace (tools, models, stop reason) — brief §10 "engineering evidence view" |
| **AP-5 Demo deployment / runbook** | 22 Oct | ☐ one command to start the UI ☐ fallback plan if the internet/quota fails (recorded run + offline tests) |

## AI Engineering Lead (Mwesigwa Arnold Mugahi)

| Card | Due | Checklist |
|:---|:---:|:---|
| **AI-1 Study RAG and answer DeepSeek's check questions** | 14 Oct | ☐ `docs/notes/rag-explained.md` ☐ `docs/notes/week3-week5-reference.md` Part C in own words |
| **AI-2 Week 6 persistent state (SQLite)** | 16 Oct | ☐ tables for drafts, audit, sessions, users with `tenant_id`/`user_id` ☐ tools/approvals read and write through one storage module ☐ tests: existing suites still pass |
| **AI-3 Week 6 memory + data-handling note** | 16 Oct | ☐ one justified memory (e.g. owner's usual weekly budget) scoped by tenant/user ☐ "Memory Design and Data Handling Note": what is stored, why, who can access it, retention, deletion (start from `docs/requirements/data-protection-and-multi-user.md`) ☐ demo that memory helps without deciding |
| **AI-4 Week 6 MCP-style interface spec** | 16 Oct | ☐ document each tool as capability / inputs / outputs / permissions / security boundary (from `docs/requirements/tool-schemas.json`) |
| **AI-5 Week 7 guardrails** | 20 Oct | ☐ tenant/user isolation in tools and RAG index ☐ log redaction option ☐ support Quality Lead's evaluation runs ☐ fix failures found, with re-tests |
| **AI-6 Week 8 hardening + report sections** | 22 Oct | ☐ final regression of all suites ☐ write report sections 4–7 ☐ update `docs/PROJECT_HANDOFF.md`, `AGENTS.md` |

## Quality / Security Lead

| Card | Due | Checklist |
|:---|:---:|:---|
| **QA-1 Review existing tests** `review-of-existing-work` | 15 Oct | ☐ run all offline suites ☐ read every test docstring ☐ list gaps as GitHub issues |
| **QA-2 Week 7 evaluation set (30+ scenarios)** | 18 Oct | ☐ categories from the brief: normal, edge, incorrect information, adversarial, tool failure, unauthorised action ☐ include cross-user / cross-tenant leakage cases (see the data-protection doc §4) ☐ expected behaviour per scenario |
| **QA-3 Evaluation runner + metrics** | 19 Oct | ☐ runner in `tests/` (reuse the style of `tests/test_week4_tools.py`) ☐ metrics: task completion, groundedness, correct tool choice, instruction following, latency, safety violations ☐ rubric instead of brittle keyword checks |
| **QA-4 Red-team session** | 19 Oct | ☐ prompt injection (in messages and in documents) ☐ attempts to make the AI approve, order or pay; requests for another shop's data ☐ log every finding |
| **QA-5 Failure catalogue (≥ 5 genuine failures)** | 20 Oct | ☐ add to `docs/evaluation/` with root cause, fix and re-test evidence (format of `week3-rag-evaluation.md`) |

## DevOps / Documentation Lead

| Card | Due | Checklist |
|:---|:---:|:---|
| **DO-1 Clean-machine setup test** `review-of-existing-work` | 14 Oct | ☐ follow README setup on a machine that never ran the project ☐ fix or report every step that fails |
| **DO-2 Continuous integration** | 16 Oct | ☐ GitHub Actions workflow running the 4 offline suites on every push (no API key needed) ☐ badge in README |
| **DO-3 Dependencies** | 16 Oct | ☐ trim `requirements.txt` to what is imported ☐ state the Python version ☐ verify install from scratch |
| **DO-4 Release v1.0** | 22 Oct | ☐ tag `v1.0` + GitHub release notes ☐ run instructions tested ☐ known limitations listed |
| **DO-5 Evidence appendix** | 22 Oct | ☐ index of `evidence/` and `docs/evaluation/` for the report appendices ☐ screenshots for the demo |
