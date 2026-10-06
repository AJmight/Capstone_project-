# Guide for AI coding assistants (Claude, DeepSeek, ChatGPT, Copilot, Gemini)

Read this file, then `docs/PROJECT_HANDOFF.md`, before suggesting or changing anything.

## Project in one paragraph
BSE4104 (Makerere) 8-week agentic capstone: an SME procurement assistant for a Ugandan stationery shop.
Python 3.13, Google Gemini via `google-genai`, synthetic CSV data and a synthetic policy corpus.
**AI supports, never decides:** the model chooses tools and explains; Python does all maths and enforces
rules; a human approves every requisition. Status (2026-10-06): Weeks 1–5 complete (MVP); next Week 6.

## Ground truth — check these before trusting any summary (including older AI handoffs)
- Models: `gemini-3.8-flash` primary + fallback chain in `.env`. **`gemini-2.5-flash` returns 404 for this key — do not suggest it.** Free tier = 20 requests/day per model.
- Current prompts: `prompts/procurement_assistant_v2.4.0.md` (agents), `prompts/policy_qa_v1.0.0.md` (RAG), `prompts/procurement_assistant_v1.2.0.md` (Week 2 context mode). Older versions in `prompts/archive/`.
- 8 tools: `src/tools/registry.py` `TOOL_REGISTRY`; schemas exported to `docs/requirements/tool-schemas.json`.
- Expected figures (verified): 10 of 15 items low; Bic Pens reorder 65; Rulers 57; draft Bic Pens + Rulers = UGX 84,406; budget 300,000 plan = 4 items, UGX 294,130.

## Rules
1. **Never put arithmetic in prompts or let the model compute figures.** Add or change a tool in `src/tools/procurement.py`.
2. **Never add a tool that approves, orders, pays, contacts suppliers or connects to banks/mobile money.** Approval lives only in `src/approvals.py` (human).
3. Every model call goes through `src/llm_client.py` (fallback chain) — never create a separate Gemini client.
4. Every tool call goes through `registry.execute_tool()` (allow-list, role permission, argument validation, trace).
5. Prompts are versioned files: change → new version file, old one to `prompts/archive/`, row in the file's Version History and in `prompts/prompt_history.md`, re-run the live tests.
6. **Comment heavily**: module header, a comment per section, and explanations of significant lines and data flow — teammates must be able to explain every line in the viva.
7. Tests: run all offline suites before committing (`tests/test_week4_tools.py --offline`, `test_week5_agent.py --offline`, `test_mvp_tools.py --offline`, `test_week3_rag.py --offline`). Never re-run live tests until they pass; keep failing runs as evidence, fix with a new version, document in `docs/evaluation/`.
8. Expected values in tests are computed from the CSVs, not typed in.
9. Never commit `.env`, keys or tokens; synthetic data only.
10. Windows/PowerShell commands (`py`, not `python`); the user is a student — explain the *why*.
11. Each week gets: report, AI log, engineering trail in `docs/weekly-reports/`; update `docs/PROJECT_HANDOFF.md` and `README.md`.
12. Do not record work as a teammate's contribution unless they did it.

## Where things are
| Need | File |
|:---|:---|
| Full handoff (state, decisions, known issues) | `docs/PROJECT_HANDOFF.md` |
| Team onboarding | `docs/ONBOARDING.md` |
| Concepts | `docs/notes/agentic-ai-notes.md`, `docs/notes/rag-explained.md` |
| Requirements | `docs/requirements/` |
| Architecture | `docs/architecture/` |
| Evaluations + failure catalogues | `docs/evaluation/` |
| Why each change was made | `docs/weekly-reports/week*-engineering-trail.md` |
| Brief (outside repo) | `C:\Users\user\OneDrive\Desktop\year4 sem1\emerging trends\BSE4104 AI Agentic Capstone Assignment.docx` |
