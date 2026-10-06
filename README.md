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

**New to the project? Start with [`docs/ONBOARDING.md`](docs/ONBOARDING.md).** AI assistants: read [`AGENTS.md`](AGENTS.md).
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

## Team

AI Engineering Lead: Mwesigwa Arnold Mugahi (23/U/244738/PS). Other roles: see `docs/weekly-reports/`.
