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
| 3 | Context / RAG | Not started |
| 4 | Tools and function calling | Not started (next) |
| 5 | Bounded agent | Not started |
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
py src\generate_synthetic_data.py # regenerate the CSVs (seed 42)
```

## Repository layout

| Path | Contents |
|:---|:---|
| `src/llm_client.py` | Shared Gemini client: primary model + automatic fallback chain, timeouts, call traces |
| `src/ai_engine.py` | Loads the versioned prompt and CSVs, calls the model, parses JSON |
| `src/test_models.py`, `src/test_connection.py` | Model availability and connection checks |
| `src/generate_synthetic_data.py` | Creates `data/*.csv` (synthetic, reproducible) |
| `prompts/` | Versioned system prompts (`procurement_assistant_v1.2.0.md` is current), `prompt_history.md`, `archive/` |
| `tests/` | Evaluation runners |
| `data/` | Synthetic inventory, purchase history and supplier quotes |
| `docs/` | Requirements, model selection, evaluation, weekly reports, AI Engineering Log, handoff |
| `evidence/` | Evaluation outputs and model-call traces |

## Models

`gemini-3.8-flash` with automatic fallback to 3.7 → 3.6 → 3.5 → 3.5-lite → 3.1-lite Flash, configured in
`.env`. Rationale: `docs/requirements/model-selection.md`.

## Data and secrets

All data is synthetic. Never commit `.env`; only `.env.example` (placeholders) is in git.
