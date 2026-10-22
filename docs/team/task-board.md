# Team Task Board — remaining work (presentation + hand-in)

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

> **Status 20 Oct 2026 (evening): the build is finished and the release is cut.**
> Weeks 1–8 are implemented, all seven offline suites pass **105/105**, the final report is
> `docs/final-report.md`, the evidence pack is `evidence/final/` and the tag `v1.0.0` exists.
> **Every card below that is marked ☑ is done and committed.** The open cards are the ones
> that need a person: the deck, the screenshots, the upload and the contribution rows.

Rule for every card: **only record work you did yourself.** Review cards count when you leave evidence
(a GitHub issue, a commit, or notes in `docs/reviews/<your-name>.md`).

---

## Everyone

| Card | Due | Checklist |
|:---|:---:|:---|
| **ALL-1 Onboarding: run the MVP** | 14 Oct | ☑ clone repo, venv, `pip install -r requirements.txt` ☑ own Gemini key in `.env` (never commit it) ☐ run the 4 offline suites (README "Run") ☐ `py src\app.py`: try the 5 scenarios in `docs/ONBOARDING.md` §4 ☐ read `docs/notes/agentic-ai-notes.md` ☐ screenshot to `evidence/screenshots/onboarding-<name>.png` |
| **ALL-2 Viva practice** | 26 Oct | ☐ answer the 8 questions in `docs/ONBOARDING.md` §8 without notes ☐ explain one trace (`evidence/week5/trace_T3_failure_recovery.md`) to a teammate |
| **ALL-3 Check the release** `review-of-existing-work` | 22 Oct | ☐ clone fresh ☑ run `py tests\test_week8_release_checks.py` (19/19) ☐ paste the result into `evidence/final/clean-clone-<name>.md` |

## Project / Requirements Lead

| Card | Due | Checklist |
|:---|:---:|:---|
| **PR-1 Set up the board** | 14 Oct | ☐ create lists/labels above ☐ add all cards ☐ assign names ☐ share board link in the weekly reports |
| **PR-2 Review requirements** `review-of-existing-work` | 15 Oct | ☐ read `docs/requirements/project-charter.md`, `user-stories.md`, `ai-boundary-matrix.md` ☐ list corrections as GitHub issues ☐ team decision on User Story 3 (PDF quotes): attempt or keep descoped |
| **PR-3 Contribution tables** | 22 Oct | ☐ fill the `[name]` rows in `docs/weekly-reports/week1…8-report.md` with what each person actually did (e.g. reviews) — no invented work |
| **PR-4 Week 6 report** | 16 Oct | ☑ `docs/weekly-reports/week6-report.md` in the same format (brief §8) ☑ links to commits and cards |
| **PR-5 Week 7 report** | 20 Oct | ☑ `week7-report.md` (max 2 pages) |
| **PR-6 Final engineering report** | 20 Oct | ☑ skeleton with the 10 sections of brief §9 ☑ merged, 8–12 pages → `docs/final-report.md` ☑ appendices list ☑ references verified ☐ **team edits: wording, section ownership, contribution table** |
| **PR-7 Presentation** `presentation` | 25 Oct | ☐ build the 8-slide deck from `docs/final-report.md` Appendix G (outline + timings) ☐ demo script: success path, evidence view, real failure, human approval ☐ rehearse twice with timing |
| **PR-8 Hand-in** | 23 Oct | ☐ upload the report, the code and the evidence pack to MUELE ☐ check the submitted PDF opens and the page count is right ☐ screenshot the submission receipt |

## Application / Integration Lead

| Card | Due | Checklist |
|:---|:---:|:---|
| **AP-1 Review the app layer** `review-of-existing-work` | 14 Oct | ☐ read `src/app.py`, `src/tool_agent.py`, `src/approvals.py` ☐ write UI requirements (pages, roles) ☐ choose framework (Streamlit is simplest) |
| **AP-2 Web UI: core pages** | 23 Oct | ☐ login screen (name + password, linked to the user's shop — coordinate with AI-2) ☐ Chat page → `run_agent()` ☐ Weekly restock page → `run_restock()` with timeline ☐ Policy Q&A page → `answer_policy_question()` with sources ☐ Stock page → `get_inventory()` — *optional: the console app is the release; the deck can demo the console* |
| **AP-3 Pending-approval page (US 10, AC 10.1)** | 23 Oct | ☐ list drafts awaiting approval ☐ edit / approve / reject (typed confirmation) using `approvals.edit_quantity()` and `approvals.decide()` ☐ reason required for reject and over-cap lines — *optional: the console app already does this* |
| **AP-4 Evidence view for the demo** | 21 Oct | ☐ capture the 5 demo screenshots into `evidence/final/screenshots/` (approval queue, restock timeline, policy answer with sources, evidence trace, red-team refusal) ☐ put them in the deck |
| **AP-5 Demo deployment / runbook** | 22 Oct | ☑ one command to start the console app (`py src\app.py`) ☑ fallback plan if the internet/quota fails (recorded run + offline tests) → `docs/final-report.md` Appendix G |

## AI Engineering Lead (Mwesigwa Arnold Mugahi)

| Card | Due | Checklist |
|:---|:---:|:---|
| **AI-1 Study RAG and answer DeepSeek's check questions** | 14 Oct | ☑ `docs/notes/rag-explained.md` ☑ `docs/notes/week3-week5-reference.md` Part C in own words |
| **AI-2 Week 6 persistent state (SQLite)** | 16 Oct | ☑ tables for drafts, audit, sessions (`src/state.py`) ☑ transition validation graph ☑ tests: `test_week6_state_memory.py` passes (9/9) |
| **AI-3 Week 6 memory + data-handling note** | 16 Oct | ☑ justified memory (`src/memory.py`) scoped by `shop_id` ☑ "Memory Design and Data Handling Note" in `docs/architecture/state-and-memory-model.md` ☑ demo that memory helps without deciding |
| **AI-4 Week 6 MCP-style interface spec** | 16 Oct | ☑ document each tool as capability / inputs / outputs / permissions / security boundary (`docs/requirements/mcp-interface-specification.md` & `src/mcp_interface.py`) |
| **AI-5 Week 7 guardrails** | 20 Oct | ☑ tenant isolation in tools and memory ☑ input injection detection ☑ budget ceiling guardrail (F-12 fix) in `src/guardrails.py` ☑ fix failures found, with re-tests |
| **AI-6 Week 8 hardening + report sections** | 20 Oct | ☑ final regression of all suites (105/105) ☑ report sections 4–7 ☑ update `docs/PROJECT_HANDOFF.md`, `AGENTS.md` ☑ fix F-23/F-24/F-25 and re-test ☑ `tests/test_week8_release_checks.py` (19/19) |

## Quality / Security Lead

| Card | Due | Checklist |
|:---|:---:|:---|
| **QA-1 Review existing tests** `review-of-existing-work` | 15 Oct | ☑ run all offline suites ☑ read every test docstring ☑ list gaps as GitHub issues |
| **QA-2 Week 7 evaluation set (30+ scenarios)** | 18 Oct | ☑ categories from the brief: normal, edge, incorrect information, adversarial, tool failure, unauthorised action (`docs/evaluation/week7-evaluation-dataset.md`) — 31 scenarios |
| **QA-3 Evaluation runner + metrics** | 19 Oct | ☑ runner in `tests/test_week7_evaluations.py` (31/31 passing) ☑ metrics: task completion, groundedness, correct tool choice, instruction following, latency, safety violations |
| **QA-4 Red-team session** | 19 Oct | ☑ prompt injection (in messages and in documents) ☑ attempts to make the AI approve, order or pay; requests for another shop's data ☑ log every finding |
| **QA-5 Failure catalogue (≥ 5 genuine failures)** | 20 Oct | ☑ add to `docs/evaluation/failure-catalogue.md` with 25 failures, root causes, fixes and re-test evidence |
| **QA-6 Independent release verification** `review-of-existing-work` | 22 Oct | ☐ read `docs/final-report.md` and check **every number** in it against the code ☑ re-run the 7 suites (105/105) ☐ sign-off note in `docs/reviews/qa-lead-release-signoff.md` |

## DevOps / Documentation Lead

| Card | Due | Checklist |
|:---|:---:|:---|
| **DO-1 Clean-machine setup test** `review-of-existing-work` | 22 Oct | ☐ follow README setup on a machine that never ran the project ☐ fix or report every step that fails ☐ record the result in `evidence/final/` |
| **DO-2 Continuous integration** | 23 Oct | ☐ GitHub Actions workflow running the 7 offline suites on every push (no API key needed) ☐ badge in README — *still open: no CI exists* |
| **DO-3 Dependencies** | 16 Oct | ☑ trim `requirements.txt` to what is imported ☑ state the Python version ☑ verify install from scratch |
| **DO-4 Release v1.0** | 20 Oct | ☑ tag `v1.0.0` + release notes (final report §9) ☑ run instructions tested ☑ known limitations listed ☑ `evidence/final/README.md` index |
| **DO-5 Evidence appendix** | 22 Oct | ☑ index of `evidence/` and `docs/evaluation/` → `evidence/final/README.md` ☐ screenshots for the demo (with AP-4) |
