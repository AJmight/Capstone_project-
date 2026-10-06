# Project Handoff — SME Procurement Support Agent

**Last updated:** 2026-10-06 (MVP: Weeks 1–5 complete; next Week 6). AI assistants: also read `/AGENTS.md`. Team: `docs/ONBOARDING.md`. Read this before changing anything.
This replaces an earlier handoff draft that contained outdated facts (listed in §9).

## 1. Identity

- **Course:** BSE4104 Emerging Trends in Software Engineering, Makerere University, Year IV Sem I
- **Brief:** `C:\Users\user\OneDrive\Desktop\year4 sem1\emerging trends\BSE4104 AI Agentic Capstone Assignment.docx`
- **Dates:** 31 Aug – 23 Oct 2026; presentations 27/29/30 Oct 2026
- **Repo:** https://github.com/AJmight/Capstone_project- (`main`); local `C:\Users\user\Capstone_project-`
- **AI Engineering Lead:** Mwesigwa Arnold Mugahi (23/U/244738/PS), GitHub AJmight. Other roles: TBD.
- **AI tools used:** Gemini (product model + proof-reading), Claude Code (coding partner), DeepSeek (supervisor/teacher), ChatGPT (concept explanations), GitHub Copilot (inline fixes).
- **Code style rule:** comment every module, section and significant line (groupmates review the code).
- Weekly deadlines are not graded separately; everything is handed in at the end of October. Order chosen: Week 2 → 4 → 5 → 3 (all done) → 6–8. Week 1 docs consolidated into `docs/requirements/` on 2026-10-06.

## 2. Problem and boundaries

A Ugandan stationery/office-supplies shop tracks stock in an exercise book that can be lost or
water-damaged; suppliers pressure junior staff to over-order. The system reads synthetic CSVs, flags
low stock, compares quotes, estimates reorder quantities, drafts requisitions and answers history
questions. **AI supports, never decides.** It may not approve, order, pay, contact suppliers or connect
to banks/mobile money. A human approves every draft.

## 3. Environment

Windows 11, PowerShell, VS Code, Python 3.13 in `venv\`, run with `py`. `google-genai` 2.25.0.
Git push works from PowerShell (Git Credential Manager opens the browser). Do not use PATs in chat.

## 4. Models (verified 2026-10-02 with `src/test_models.py` and live calls)

| Model | Status for our key |
|:---|:---|
| `gemini-3.8-flash` | Works; **20 requests/day** free tier; primary |
| `gemini-3.7-flash`, `3.6-flash`, `3.5-flash`, `3.5-flash-lite`, `3.1-flash-lite` | Work; separate daily quotas; fallback chain in this order |
| `gemini-2.5-flash` | **404 "no longer available to new users"** — do not use |

`src/llm_client.py` switches model immediately on 503/429/5xx/timeout/network/404, runs up to 3 rounds,
skips models out of daily quota or 404, and logs every call to `evidence/traces/llm_calls.jsonl`.
Chat sessions are used for multi-turn memory; they do not avoid 503s.

## 5. Current files

| File | Purpose |
|:---|:---|
| `.env` (git-ignored) / `.env.example` | `GEMINI_API_KEY`, `GEMINI_PRIMARY_MODEL`, `GEMINI_FALLBACK_MODELS`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_ROUNDS` |
| `src/llm_client.py` | `generate()` one-shot and `ChatSession` multi-turn, both with fallback |
| `src/ai_engine.py` | `load_system_prompt()` (only BEGIN/END section), `load_csv()`, `parse_json()`, `analyze_inventory()` |
| `src/test_models.py` | Lists usable models (`--probe` sends 1 request each) |
| `prompts/procurement_assistant_v1.2.0.md` | **Current prompt.** History in `prompts/prompt_history.md`; old versions in `prompts/archive/` |
| `tests/test_week2_cases.py` | 10 live test cases; expectations computed from CSVs; `--prompt`, `--only` |
| `docs/evaluation/week2-prompt-evaluation.md` | Results (v1.1.0 7/10 → v1.2.0 9/10) and failure catalogue F-01…F-06 |
| `docs/requirements/model-selection.md` | Model Selection Note |
| `docs/weekly-reports/week2-report.md`, `week2-ai-log.md` | Weekly report (team names TBD) and AI Engineering Log |

## 6. Prompt rules that code and tests depend on (v1.2.0)

- Low stock: `current_stock <= reorder_point` (10 of 15 items in the current data).
- Only low items are drafted, even if a well-stocked item is named.
- Supplier = lowest price (tie → shorter lead time). In the current data that is always Kampala Office Supplies.
- `recommended_qty = ceil(avg_monthly_purchases * 1.5 - current_stock)`, raised to supplier MOQ. Purchase history is the demand proxy (there is no sales data).
- No history (ITM011–ITM015) → `recommended_qty = 0`, a human sets it. **Do not invent a default.**
- 200% cap → line kept with `requires_override: true` and `override_reason`.
- `budget_range_ugx` is intentional (User Story 8), not an extra field.
- `draft_requisition: []` is correct for analysis-only requests such as `analyze_inventory()`.
- Refusals return `{"error": "REFUSAL: ..."}` — there is no `[STATUS: ...]` tag any more.

## 6b. Week 4 (tool mode) — what exists

| File | Purpose |
|:---|:---|
| `src/tools/procurement.py` | 4 deterministic tools: `get_low_stock`, `compare_supplier_quotes`, `estimate_reorder_quantity`, `draft_requisition` (saves `data/drafts/REQ-*.json`, git-ignored) |
| `src/tools/registry.py` | `execute_tool()`: allow-list → role (viewer/staff/owner) → argument validation → `created_by` injected → safe run → `evidence/week4/tool_traces.jsonl` |
| `src/tool_agent.py` | `run_agent(question, role, user_name)`: bounded loop (6 turns, 12 tool calls), AFC off, role-filtered tools, fallback via `call_with_fallback`, run trace `evidence/week4/agent_traces.jsonl` |
| `src/approvals.py` | Human-only approve/reject CLI with typed confirmation and `data/drafts/audit_log.jsonl`; NOT a tool |
| `prompts/procurement_assistant_v2.4.0.md` | Tool-mode prompt (v1.2.0 stays for `ai_engine.py`; v2.0.0–v2.3.0 in `archive/`) |
| `tests/test_week4_tools.py` | 22 offline (no model) + 6 live tests |
| `docs/requirements/tool-catalogue.md`, `tool-schemas.json`, `docs/architecture/architecture-week4.md`, `docs/evaluation/week4-tool-evaluation.md`, `docs/weekly-reports/week4-*.md` | Week 4 deliverables and trail |

Results: offline 22/22, live 6/6. **F-04 closed.** New: F-07 (model requested a tool it was not given — blocked by the registry).

## 6c. Week 5 (bounded agent) — what exists

| File | Purpose |
|:---|:---|
| `src/restock_agent.py` | `run_restock(budget, user_name, role, save_trace_as)`: preconditions → SENSE (code) → bounded loop (5 turns, 6 tool calls, 3-tool task allow-list) → post-conditions → outcome decided by code (DRAFT_READY, NOTHING_FITS_BUDGET, NOTHING_TO_DO, PRECONDITION_FAILED, POSTCONDITION_FAILED, HANDOFF_*) |
| `src/tools/procurement.py` `plan_within_budget` | Tool 5: urgency order (stock/reorder point), greedy skip-and-continue within budget; included / deferred / needs_human |
| `src/tool_agent.py` v1.2.0 | + per-turn steps, repeated-call guard (one retry after SERVICE_UNAVAILABLE), `allowed_tools`, observer hook, `check_output()` against false draft claims |
| `src/tools/registry.py` v1.1.0 | + whole-float → int, `minimum`, fault injection (`inject_fault`, `AGENT_FAULTS`, marked `injected`) |
| `tests/test_week5_agent.py` | 16 offline (scripted fake model) + 4 live traces |
| `docs/requirements/agent-task-contract.md`, `docs/architecture/architecture-week5.md`, `docs/evaluation/week5-agent-evaluation.md`, `docs/weekly-reports/week5-*.md`, `evidence/week5/trace_T1…T4.md` | Week 5 deliverables and trail |

Results: offline 16/16 (+ Week 4 22/22), traces 4/4, Week 4 live regression 6/6 after F-13 fix.
New findings: F-12 (±10 % range can exceed budget — open), F-13 (false draft claim — fixed in code + prompt),
F-14 (prompt contradiction — fixed v2.2.1), F-15 (floats from Gemini — fixed).

## 6d. Week 3 (RAG) and MVP additions — 2026-10-06

| File | Purpose |
|:---|:---|
| `knowledge/corpus/*.md` (12), `knowledge/source-register.md` | Synthetic policy corpus and provenance |
| `src/rag/index.py` v1.1.0 | Ingest, section chunking, tokeniser (light stemmer), BM25, `MIN_SCORE` 2.0 |
| `src/rag/policy_qa.py` v1.0.1 | retrieve (+ next section) → `[S#]` context → Gemini (`prompts/policy_qa_v1.0.0.md`) → `check_citations` |
| `src/tools/knowledge.py` | `search_policy` agent tool |
| `src/tools/procurement.py` v1.2.0 | + `get_inventory` (US 1), `query_purchase_history` (US 6); draft lines store `safety_cap` |
| `src/approvals.py` v1.1.0 | + `edit` (US 9) with AI suggestion kept and audit entry |
| `src/app.py` | Console MVP: ask / restock / policy / review drafts / stock |
| `tests/test_week3_rag.py`, `tests/test_mvp_tools.py` | RAG (offline retrieval + 15 live) and MVP (7 offline + 6 live) |
| `docs/requirements/project-charter.md`, `user-stories.md`, `ai-boundary-matrix.md`, `docs/architecture/context-diagram.md` | Week 1 deliverables |

Results: retrieval hit@3 10/10; RAG answers 15/15; MVP 7/7 + 6/6; regressions on v2.4.0 all pass.
Failures: R-1…R-5 (R-4 open: numeric ranges in keyword search), F-16 fixed. Summary: `docs/evaluation/mvp-evaluation.md`.

## 7. Known issues

- F-04 closed in Week 4. F-10: the 200 % cap can only trigger through a large supplier MOQ (document in final report).
- v1.2.0 has not yet been evaluated on `gemini-3.8-flash` (quota exhausted during runs).
- Week 1 documents exist only as `.docx`; `docs/requirements/` should hold the charter, user stories and AI Boundary Matrix.
- User stories mention sugar/dairy/cooking oil sales; the data is stationery purchases. Align stories with data.

## 8. Next steps (priority order)

1. ~~Week 4 tools~~ — done.
2. ~~Week 5~~ — done.
3. ~~Week 3~~ — done (the Lead is studying the concept: `docs/notes/rag-explained.md`; pause further RAG changes until they ask).
4. Week 6 (AI Lead): SQLite state for drafts/audit, one justified memory, MCP-style interface. Weeks 7–8 per the brief; role owners in `docs/ONBOARDING.md` §6.
5. Weeks 6–8 per the brief. Groq can be added as a cross-provider fallback in `llm_client.py`.

## 9. Corrections to the earlier handoff draft

| Earlier claim | Correct fact |
|:---|:---|
| Primary `gemini-2.5-flash`, ~1,500 req/day | 2.5 returns 404 for this key |
| "No model fallback yet" | Fallback chain implemented and tested |
| Empty `draft_requisition` is a bug | Correct for analysis-only requests |
| Remove `budget_range_ugx` | Required for User Story 8 |
| Default quantity 20 when no history | Rejected: invents data |
| TC-09 expects `[STATUS: DRAFT...]` | Refusal JSON `REFUSAL: ...` |
| `docs/requirements` holds the charter | It did not; Week 1 docs are `.docx` only |

## 10. Working with AJ

Explain the why before the what; one step at a time; Windows/PowerShell commands; be direct about
mistakes and trade-offs; connect work to the graded deliverables; never paste secrets in chat.
