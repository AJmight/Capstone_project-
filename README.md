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

## Status

| Week | Focus | Status |
|:---:|:---|:---|
| 1 | Problem framing, user stories, AI Boundary Matrix | Done (documents in `.docx`; to be copied into `docs/requirements/`) |
| 2 | Model integration and prompting | Done — prompt v1.2.0, 10-case evaluation 9/10 (`docs/evaluation/week2-prompt-evaluation.md`) |
| 3 | Context / RAG | Planned after Week 5 (team decision) |
| 4 | Tools and function calling | Done — 4 deterministic tools, registry, human approval gate; offline 22/22, live 6/6 (`docs/evaluation/week4-tool-evaluation.md`) |
| 5 | Bounded agent | Next (loop already in `src/tool_agent.py`) |
| 6–8 | Memory, evaluation & guardrails, release | Not started |

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
| `src/test_models.py`, `src/test_connection.py` | Model availability and connection checks |
| `src/generate_synthetic_data.py` | Creates `data/*.csv` (synthetic, reproducible) |
| `prompts/` | Versioned system prompts (`v2.0.0` tool mode, `v1.2.0` context mode), `prompt_history.md`, `archive/` |
| `tests/` | Evaluation runners |
| `data/` | Synthetic inventory, purchase history and supplier quotes; `data/drafts/` holds runtime drafts (git-ignored) |
| `docs/` | Requirements, model selection, evaluation, weekly reports, AI Engineering Log, handoff |
| `evidence/` | Evaluation outputs and model-call traces |

## Models

`gemini-3.8-flash` with automatic fallback to 3.7 → 3.6 → 3.5 → 3.5-lite → 3.1-lite Flash, configured in
`.env`. Rationale: `docs/requirements/model-selection.md`.

## Data and secrets

All data is synthetic. Never commit `.env`; only `.env.example` (placeholders) is in git.

## Team

AI Engineering Lead: Mwesigwa Arnold Mugahi (23/U/244738/PS). Other roles: see `docs/weekly-reports/`.
