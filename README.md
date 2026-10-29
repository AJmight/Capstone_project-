# SME Procurement Support Agent

BSE4104 Emerging Trends in Software Engineering — AI-Native & Agentic Engineering Capstone
(Makerere University, 2026/2027).

**Our system helps** a small Ugandan stationery/office-supplies shop owner and their junior staff
**prepare purchase requisitions**. The AI reads tool-provided stock, purchase history and supplier
quotes, chooses restock priorities and supplier trade-offs, explains its recommendations and may
prepare drafts. Deterministic software remains responsible for data validation, every calculation
and hard safety limits. The AI **may recommend and draft** but **may not approve,
order, pay or contact suppliers** — a human approves every requisition. We build and evaluate it on
synthetic CSV data.

> AI plans and recommends; Python calculates and guards; a human approves.
>
> One trusted user per shop (no user roles): the person using the system reviews and approves the AI's drafts.

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
| 5 | Bounded agent | Done — Weekly Restock Agent with task contract, explicit state, pre/post-conditions; 4 live traces incl. failure/recovery; offline 17/17 (`docs/evaluation/week5-agent-evaluation.md`) |
| 6 | Memory, state, interoperability | Done — SQLite FSM (`src/state.py`), persistent memory with shop isolation (`src/memory.py`), MCP server (`src/mcp_interface.py`), 9/9 tests passed (`tests/test_week6_state_memory.py`) |
| 7 | 30+ scenario evaluation, guardrails | Done — Deterministic guardrails (`src/guardrails.py`, F-12 fix), 31-scenario evaluation dataset (`tests/test_week7_evaluations.py`, 31/31 passed), Failure Catalogue F-01..F-25 |
| 8 | Release, final report, presentation | Done — hardening pass fixed F-23/F-24/F-25, guardrails wired into the running app, 19 release checks (`tests/test_week8_release_checks.py`), final report `docs/final-report.md`, evidence pack `evidence/final/`, tag `v1.0.0`. **Still open: the slide deck, the demo screenshots and the MUELE upload (hand-in 23 Oct)** |

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
py src\tool_agent.py "Draft a requisition for Bic Pens" --user "Your Name"
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

# Week 6: State model, persistent memory & MCP
py tests\test_week6_state_memory.py      # 9 tests verifying FSM, memory isolation and MCP

# Week 7: Evaluation suite (31 scenarios) & guardrails
py tests\test_week7_evaluations.py       # 31 scenarios: normal, edge, corrupted, adversarial, failures, HITL

# Week 8: release checks (the regressions that must never come back)
py tests\test_week8_release_checks.py    # 19 tests: MCP contract, approval->FSM, tenant binding, guardrails in the runtime path

# MVP additions
py src\app.py                                 # menu: ask, restock, policy, review drafts, stock
py src\approvals.py edit REQ-... --item ITM001 --qty 50 --by "Name" --reason "..."
py tests\test_mvp_tools.py --offline
py src\generate_synthetic_data.py # regenerate the CSVs (seed 42)
```

> **All offline suites: 105 of 105 passing** (Week 4 22/22 · Week 5 17/17 · MVP 7/7 ·
> RAG hit@3 10/10 · Week 6 9/9 · Week 7 31/31 · Week 8 19/19). None of them needs an
> API key or the network. The verbatim output of the release run is in
> [`evidence/final/regression_run_2026-10-20.md`](evidence/final/regression_run_2026-10-20.md).

## Final deliverables (report and slides)

| File | What |
|:---|:---|
| `docs/final-report.md` | The final report (source) |
| `docs/ai-led-restock-change-report.md` | Detailed post-release report of the AI-led restock and UI changes |
| `docs/final/final-report.docx`, `.pdf` | The report for hand-in, generated by `py scripts\export_report.py` (needs Microsoft Word) |
| `docs/final/presentation.pptx` | The presentation deck with speaker notes, generated by `py scripts\build_slides.py` |
| `docs/final/PLACEHOLDERS.md` | **Team checklist:** the images and names still to add, and how to add them |

Install the document tools once with `pip install -r requirements-docs.txt`.

## Web UI (Streamlit)

The browser prototype starts with a business name (no login screen) and opens a separate
tenant workspace. Dashboard is the AI Copilot; Operations manages stock, sales, purchases,
supplier quotes and activity; Restock AI asks the bounded agent to plan; Approvals records the
human decision through direct Approve/Reject buttons. Python supplies the full evidence and checks
the AI's priorities, quoted suppliers, figures and hard budget before saving a draft. If the AI is
unavailable, no non-AI draft is silently created. Policy Q&A and editing are inside the Copilot.
Copilot context is tenant-local, keeps four recent turns, and compacts older turns without an
extra model call. Assistant replies can expand to show checked tool results and record evidence.
Gemini receives every new request first; when configured, retryable Gemini failures pass the same
bounded chat/tool context to Groq Llama without displaying the provider switch in the chat. Agent
and model-attempt limits bound failures and keep each workflow auditable;
they are not permission to skip evidence, Python validation or human review. Thoroughness takes
precedence over latency, and no performance improvement is claimed until it is measured without
weakening those controls. Each business has its own data.

```powershell
pip install -r requirements.txt               # includes streamlit
py -m streamlit run src\streamlit_app.py      # run from the repo root; opens http://localhost:8501
py tests\test_ui_home.py                      # end-to-end UI workflows, no live model calls
py tests\test_groq_fallback.py                # simulated Gemini -> Groq handoff, no API call or key
py tests\test_llm_limits.py                   # provider attempt cap and fast outage hand-off
```

The welcome screen and data-entry flows work without model keys. AI answers require
`GEMINI_API_KEY`; set `GROQ_API_KEY` in the ignored local `.env` and in Render's service
Environment settings to enable provider fallback. A Render blueprint's `sync: false` key must be
entered in the Render dashboard; adding it to this repository does not configure the running service.

## Repository layout

| Path | Contents |
|:---|:---|
| `src/llm_client.py` | Shared Gemini-first client with optional Groq Llama handoff, preserved context, timeouts and call traces |
| `src/ai_engine.py` | Week 2 context mode: loads the versioned prompt and CSVs, calls the model, parses JSON |
| `src/tools/procurement.py` | Deterministic procurement tools: all quantities, prices, totals and budget checks |
| `src/tools/registry.py` | Allow-list, argument validation, trusted context and tool traces — 9 tools in total |
| `src/tool_agent.py` | Week 4: bounded tool-calling loop (model decides, Python computes) |
| `src/approvals.py` | Week 4: human-only approve/reject of drafts, with audit log; Week 8: the approval also moves the state machine |
| `src/restock_agent.py` | Week 5: bounded goal-directed agent (weekly restock within a budget); Week 8: hard budget ceiling |
| `src/state.py` | Week 6: explicit Finite State Machine & SQLite session persistence |
| `src/memory.py` | Week 6: justified persistent memory with multi-tenant shop isolation |
| `src/mcp_interface.py` | Week 6: Model Context Protocol (MCP) server dispatcher & security boundary |
| `src/guardrails.py` | Week 7: input validation, F-12 budget ceiling enforcement, and HITL gate |
| `src/rag/` | Week 3: corpus ingestion, chunking, BM25 index (`index.py`), grounded cited answers (`policy_qa.py`) |
| `src/tools/knowledge.py` | `search_policy` tool (RAG for the agent) — the 8th tool |
| `src/app.py` | MVP console app over all of the above; Week 8: the input guardrail screens the user |
| `knowledge/` | Synthetic policy corpus (`corpus/`) and its source register |
| `src/test_models.py`, `src/test_connection.py` | Model availability and connection checks |
| `src/generate_synthetic_data.py` | Creates `data/*.csv` (synthetic, reproducible) |
| `prompts/` | Versioned prompts (`v2.5.0` agents, `policy_qa_v1.0.0` RAG, `v1.2.0` context mode), `prompt_history.md`, `archive/` |
| `tests/` | Evaluation runners |
| `scripts/build_evidence_final.py` | Week 8: rebuilds the release evidence pack (`evidence/final/`) by re-running all seven offline suites |
| `data/` | Synthetic inventory, purchase history and supplier quotes; `data/drafts/` holds runtime drafts (git-ignored); `data/procurement.db` is the runtime store (git-ignored) |
| `docs/` | Onboarding, notes (concepts, RAG), requirements, architecture, evaluation, weekly reports + trails + AI logs, handoff, **final report (`final-report.md`)** |
| `evidence/` | Evaluation outputs and model-call traces; **`evidence/final/` is the release evidence pack** |

## Models

`gemini-3.8-flash` is tried first. If it hits a retryable availability/quota error and `GROQ_API_KEY`
is configured, the same request and tool history move to Groq Llama; other configured Gemini models
remain in the fallback chain. The next user question always starts with Gemini again. Set provider keys
in `.env` locally and as Render environment secrets; never put API keys in source code or Git.
Rationale: `docs/requirements/model-selection.md`.

## Data and secrets

All data is synthetic. Never commit `.env`; only `.env.example` (placeholders) is in git.

## Team roles and what to do next

Where we are (20 Oct 2026): **Weeks 1–8 are complete and the release is cut (`v1.0.0`).**
The final offline regression is **105 of 105** (Week 4 22/22 · Week 5 17/17 · MVP 7/7 ·
RAG hit@3 10/10 · Week 6 9/9 · Week 7 31/31 · Week 8 19/19), the final engineering report is
[`docs/final-report.md`](docs/final-report.md), and the release evidence pack is
[`evidence/final/`](evidence/final/).

**What is still open (hand-in 23 Oct, presentations 27/29/30 Oct):**
the **slide deck** (8 slides — the outline and the demo script are in the final report,
Appendix G), the **demo screenshots** into `evidence/final/screenshots/`, the **MUELE
upload**, the **contribution rows** in the weekly reports, and anyone who still has
cards open on the board. Every task below is a card on the team board — full checklists
in [`docs/team/task-board.md`](docs/team/task-board.md) (importable:
[`docs/team/task-board.csv`](docs/team/task-board.csv)).

| Role | Person | What this role is responsible for |
|:---|:---|:---|
| Project / Requirements Lead | [name] | Board, weekly reports, requirements, final report assembly, presentation |
| Application / Integration Lead | [name] | Web UI over the existing functions, approval page, demo deployment |
| AI Engineering Lead | Mwesigwa Arnold Mugahi (23/U/24738/PS) | Model, prompts, RAG, tools, agents; Week 6 state/memory/interface; guardrails |
| Quality / Security Lead | [name] | Tests, 30+ scenario evaluation, red-teaming, failure catalogue |
| DevOps / Documentation Lead | [name] | Setup on clean machines, CI, dependencies, release, evidence appendix |

### Everyone — first (by 14 Oct)
- [x] Set up the project and get **your own** Gemini key (README "Setup"); never commit `.env`
- [x] Run the four offline test suites (README "Run")
- [x] Run `py src\app.py` and try the five scenarios in `docs/ONBOARDING.md` §4
- [x] Read `docs/notes/agentic-ai-notes.md` (20 min) and `docs/ONBOARDING.md` §5
- [ ] Find your cards on the board and put your name on them

### Project / Requirements Lead
- [x] PR-1 Set up the board with all cards and names (14 Oct)
- [x] PR-2 Review charter, user stories, boundary matrix; decide on User Story 3 (15 Oct)
- [ ] PR-3 Fill the contribution rows in the Week 1–8 reports with what each person really did (22 Oct)
- [x] PR-4 / PR-5 Week 6 and Week 7 reports (16 and 20 Oct)
- [x] PR-6 Final engineering report → `docs/final-report.md` (20 Oct; still needs the team's own edits and the contribution table)
- [ ] PR-7 Presentation deck, 8 slides, brief §10 — outline and demo script are in `docs/final-report.md` Appendix G (25 Oct)
- [ ] PR-8 MUELE upload of the report, the code and the evidence pack (23 Oct)

### Application / Integration Lead
- [x] AP-1 Review `src/app.py`, `src/tool_agent.py`, `src/approvals.py`; choose a UI framework (14 Oct)
- [ ] AP-2 Web UI: login, chat, weekly restock, policy Q&A, stock pages (optional; the console app is the release)
- [ ] AP-3 Pending-approval page: owner-only edit / approve / reject (optional)
- [ ] AP-4 Evidence view showing a run's trace, for the demo (21 Oct)
- [x] AP-5 Demo runbook with an offline fallback → `docs/final-report.md` Appendix G

### AI Engineering Lead
- [x] AI-1 Study RAG notes; answer DeepSeek's check questions (14 Oct)
- [x] AI-2 SQLite persistent state with tenant scoping → `src/state.py` (16 Oct)
- [x] AI-3 One justified memory + the data-handling note → `src/memory.py`, `docs/architecture/state-and-memory-model.md` (16 Oct)
- [x] AI-4 MCP-style interface spec for the tools → `docs/requirements/mcp-interface-specification.md` (16 Oct)
- [x] AI-5 Guardrails: injection screening, budget ceiling, HITL gate → `src/guardrails.py`, wired into the runtime in Week 8 (20 Oct)
- [x] AI-6 Final regression (105/105), report sections 4–7, handoff update (20 Oct)

### Quality / Security Lead
- [x] QA-1 Run and review all existing tests; log the gaps (15 Oct)
- [x] QA-2 30+ evaluation scenarios incl. leakage and unauthorised-action cases → 31 scenarios (18 Oct)
- [x] QA-3 Evaluation runner with metrics and a scoring rubric (19 Oct)
- [x] QA-4 Red-team session: prompt injection, AI attempts to approve/order/pay, cross-shop data requests (19 Oct)
- [x] QA-5 Failure catalogue: 25 failures with re-tests → `docs/evaluation/failure-catalogue.md` (20 Oct)

### DevOps / Documentation Lead
- [x] DO-1 Test the README setup on a clean machine; fix the gaps (14 Oct)
- [ ] DO-2 GitHub Actions running the offline suites on every push (not started — no CI exists)
- [x] DO-3 Trim and pin `requirements.txt`, state the Python version (16 Oct)
- [x] DO-4 Release `v1.0.0` with notes and known limitations (20 Oct)
- [x] DO-5 Evidence appendix index → `evidence/final/README.md`; **screenshots still to be captured** (22 Oct)

**Contribution rule:** record only work you did yourself; reviewing existing work counts when you leave
evidence (an issue, a commit, or notes in `docs/reviews/<your-name>.md`).

**Key reading for everyone:** what was built and where — [`docs/notes/week3-week5-reference.md`](docs/notes/week3-week5-reference.md);
data leakage and multi-user plan — [`docs/requirements/data-protection-and-multi-user.md`](docs/requirements/data-protection-and-multi-user.md).
