# SME Procurement Support Agent

BSE4104 Emerging Trends in Software Engineering — AI-Native & Agentic Engineering Capstone
(Makerere University, 2026/2027).

**Our system helps** a small Ugandan stationery/office-supplies shop owner and their junior staff
**prepare purchase requisitions**. AI is used to read stock, purchase history and supplier quotes,
explain findings and draft requisitions. Deterministic software remains responsible for data,
validation and (from Week 4) all calculations. The AI **may draft and explain** but **may not approve,
order, pay or contact suppliers** — a human approves every requisition. We build and evaluate it on
synthetic CSV data.

> AI supports, never decides.

**New to the project? Start with [`docs/ONBOARDING.md`](docs/ONBOARDING.md), then find your role in
[Team roles and what to do next](#team-roles-and-what-to-do-next).** AI assistants: read [`AGENTS.md`](AGENTS.md).
Quick start after setup: `py src\app.py`

## Status

| Week | Focus | Status |
|:---:|:---|:---|
| 1 | Problem framing, user stories, AI Boundary Matrix | Done — charter, 12 user stories (11 implemented), boundary matrix, context diagram in `docs/` |
| 2 | Model integration and prompting | Done — prompt v1.2.0, 10-case evaluation 9/10 (`docs/evaluation/week2-prompt-evaluation.md`) |
| 3 | Context / RAG | Done — 12-document corpus, BM25 retrieval, cited answers 15/15, `search_policy` tool (`docs/evaluation/week3-rag-evaluation.md`) |
| 4 | Tools and function calling | Done — 4 deterministic tools, registry, human approval gate; offline 22/22, live 6/6 (`docs/evaluation/week4-tool-evaluation.md`) |
| 5 | Bounded agent | Done — Weekly Restock Agent with task contract, explicit state, pre/post-conditions; 4 live traces incl. failure/recovery; offline 16/16 (`docs/evaluation/week5-agent-evaluation.md`) |
| MVP | Console app over Weeks 1–5 | `src/app.py`; all suites in `docs/evaluation/mvp-evaluation.md` |
| 6–8 | Memory, evaluation & guardrails, release | Not started — owners in `docs/ONBOARDING.md` §6 |

## Setup (Windows PowerShell)

```powershell
git clone https://github.com/AJmight/Capstone_project-.git
cd Capstone_project-
py -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then put your own key from aistudio.google.com in .env
```

## Run

```powershell
py src\test_models.py             # which Gemini models your key can use (no quota used)
py src\test_connection.py         # one short request through the fallback chain
py src\ai_engine.py               # analyse current inventory -> JSON
py tests\test_week2_cases.py      # 10 prompt test cases -> evidence\week2\

# Week 4: tool-calling agent
py src\tool_agent.py "Which items are low on stock?"
py src\tool_agent.py "Draft a requisition for Bic Pens" --role staff --user "Your Name"
py src\approvals.py list                       # HUMAN approval gate (the AI cannot approve)
py src\approvals.py approve REQ-... --by "Your Name"
py tests\test_week4_tools.py --offline         # 22 tool tests, no model quota used
py tests\test_week4_tools.py --live            # 6 live agent tests

# Week 5: bounded weekly restock agent
py src\restock_agent.py --budget 300000 --user "Your Name"        # prints the Sense->...->Stop timeline
py src\restock_agent.py --budget 300000 --save-trace my_run       # writes evidence\week5\trace_my_run.md
py tests\test_week5_agent.py --offline        # 16 agent tests with a scripted fake model (no quota)
py tests\test_week5_agent.py --live           # the 4 execution traces
# Week 3: RAG over the policy documents
py src\rag\policy_qa.py "Who can approve a requisition of UGX 800,000?"
py tests\test_week3_rag.py --offline          # retrieval metrics (free)
py tests\test_week3_rag.py --live             # 15 grounded answers

# MVP additions
py src\app.py                                 # menu: ask, restock, policy, review drafts, stock
py src\approvals.py edit REQ-... --item ITM001 --qty 50 --by "Name" --reason "..."
py tests\test_mvp_tools.py --offline
py src\generate_synthetic_data.py # regenerate the CSVs (seed 42)
```

## Repository layout

| Path | Contents |
|:---|:---|
| `src/llm_client.py` | Shared Gemini client: primary model + automatic fallback chain, timeouts, call traces |
| `src/ai_engine.py` | Week 2 context mode: loads the versioned prompt and CSVs, calls the model, parses JSON |
| `src/tools/procurement.py` | Week 4: four deterministic tools (all maths happens here) |
| `src/tools/registry.py` | Week 4: allow-list, role permissions, argument validation, tool traces |
| `src/tool_agent.py` | Week 4: bounded tool-calling loop (model decides, Python computes) |
| `src/approvals.py` | Week 4: human-only approve/reject of drafts, with audit log |
| `src/restock_agent.py` | Week 5: bounded goal-directed agent (weekly restock within a budget) |
| `src/rag/` | Week 3: corpus ingestion, chunking, BM25 index (`index.py`), grounded cited answers (`policy_qa.py`) |
| `src/tools/knowledge.py` | `search_policy` tool (RAG for the agent) |
| `src/app.py` | MVP console app over all of the above |
| `knowledge/` | Synthetic policy corpus (`corpus/`) and its source register |
| `src/test_models.py`, `src/test_connection.py` | Model availability and connection checks |
| `src/generate_synthetic_data.py` | Creates `data/*.csv` (synthetic, reproducible) |
| `prompts/` | Versioned prompts (`v2.4.0` agents, `policy_qa_v1.0.0` RAG, `v1.2.0` context mode), `prompt_history.md`, `archive/` |
| `tests/` | Evaluation runners |
| `data/` | Synthetic inventory, purchase history and supplier quotes; `data/drafts/` holds runtime drafts (git-ignored) |
| `docs/` | Onboarding, notes (concepts, RAG), requirements, architecture, evaluation, weekly reports + trails + AI logs, handoff |
| `evidence/` | Evaluation outputs and model-call traces |

## Models

`gemini-3.8-flash` with automatic fallback to 3.7 → 3.6 → 3.5 → 3.5-lite → 3.1-lite Flash, configured in
`.env`. Rationale: `docs/requirements/model-selection.md`.

## Data and secrets

All data is synthetic. Never commit `.env`; only `.env.example` (placeholders) is in git.

## Team roles and what to do next

Where we are (13 Oct 2026): **Weeks 1–5 are done (MVP).** Remaining: Week 6 (memory, state,
interoperability), Week 7 (30+ scenario evaluation, guardrails), Week 8 (release and final report,
**hand-in 23 Oct**), presentations **27/29/30 Oct**. Every task below is a card on the team board —
full checklists in [`docs/team/task-board.md`](docs/team/task-board.md) (importable:
[`docs/team/task-board.csv`](docs/team/task-board.csv)).

| Role | Person | What this role is responsible for |
|:---|:---|:---|
| Project / Requirements Lead | [name] | Board, weekly reports, requirements, final report assembly, presentation |
| Application / Integration Lead | [name] | Web UI over the existing functions, approval page, demo deployment |
| AI Engineering Lead | Mwesigwa Arnold Mugahi (23/U/244738/PS) | Model, prompts, RAG, tools, agents; Week 6 state/memory/interface; guardrails |
| Quality / Security Lead | [name] | Tests, 30+ scenario evaluation, red-teaming, failure catalogue |
| DevOps / Documentation Lead | [name] | Setup on clean machines, CI, dependencies, release, evidence appendix |

### Everyone — first (by 14 Oct)
- [ ] Set up the project and get **your own** Gemini key (README "Setup"); never commit `.env`
- [ ] Run the four offline test suites (README "Run")
- [ ] Run `py src\app.py` and try the five scenarios in `docs/ONBOARDING.md` §4
- [ ] Read `docs/notes/agentic-ai-notes.md` (20 min) and `docs/ONBOARDING.md` §5
- [ ] Find your cards on the board and put your name on them

### Project / Requirements Lead
- [ ] PR-1 Set up the board with all cards and names (14 Oct)
- [ ] PR-2 Review charter, user stories, boundary matrix; decide on User Story 3 (15 Oct)
- [ ] PR-3 Fill the contribution rows in the Week 1–5 reports with what each person really did (15 Oct)
- [ ] PR-4 / PR-5 Week 6 and Week 7 reports (16 and 20 Oct)
- [ ] PR-6 Final engineering report, 8–12 pages, brief §9 (skeleton 17 Oct, final 22 Oct)
- [ ] PR-7 Presentation deck and demo script, brief §10 (25 Oct)

### Application / Integration Lead
- [ ] AP-1 Review `src/app.py`, `src/tool_agent.py`, `src/approvals.py`; choose a UI framework (14 Oct)
- [ ] AP-2 Web UI: login, chat, weekly restock, policy Q&A, stock pages (18 Oct)
- [ ] AP-3 Pending-approval page: owner-only edit / approve / reject (19 Oct)
- [ ] AP-4 Evidence view showing a run's trace, for the demo (21 Oct)
- [ ] AP-5 Demo runbook with an offline fallback (22 Oct)

### AI Engineering Lead
- [ ] AI-1 Study RAG notes; answer DeepSeek's check questions (14 Oct)
- [ ] AI-2 SQLite persistent state with tenant/user scoping (16 Oct)
- [ ] AI-3 One justified memory + Memory Design and Data Handling Note (16 Oct)
- [ ] AI-4 MCP-style interface spec for the tools (16 Oct)
- [ ] AI-5 Guardrails: isolation, log redaction, fixes from evaluation (20 Oct)
- [ ] AI-6 Final regression, report sections 4–7, handoff update (22 Oct)

### Quality / Security Lead
- [ ] QA-1 Run and review all existing tests; log gaps as issues (15 Oct)
- [ ] QA-2 30+ evaluation scenarios incl. leakage and unauthorised-action cases (18 Oct)
- [ ] QA-3 Evaluation runner with metrics and a scoring rubric (19 Oct)
- [ ] QA-4 Red-team session: prompt injection, role abuse (19 Oct)
- [ ] QA-5 Failure catalogue: ≥ 5 genuine failures with re-tests (20 Oct)

### DevOps / Documentation Lead
- [ ] DO-1 Test the README setup on a clean machine; fix gaps (14 Oct)
- [ ] DO-2 GitHub Actions running the offline suites on every push (16 Oct)
- [ ] DO-3 Trim and pin `requirements.txt`, state the Python version (16 Oct)
- [ ] DO-4 Release `v1.0` with notes and known limitations (22 Oct)
- [ ] DO-5 Evidence appendix index and demo screenshots (22 Oct)

**Contribution rule:** record only work you did yourself; reviewing existing work counts when you leave
evidence (an issue, a commit, or notes in `docs/reviews/<your-name>.md`).

**Key reading for everyone:** what was built and where — [`docs/notes/week3-week5-reference.md`](docs/notes/week3-week5-reference.md);
data leakage and multi-user plan — [`docs/requirements/data-protection-and-multi-user.md`](docs/requirements/data-protection-and-multi-user.md).
