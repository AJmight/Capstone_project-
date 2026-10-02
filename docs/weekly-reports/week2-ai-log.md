# AI Engineering Log — Week 2

Required by the brief (§6): declare AI tools, record material AI-assisted decisions, and show that
generated work was reviewed and tested before it was accepted.

## AI tools used

**AI Engineering Lead:** Mwesigwa Arnold Mugahi (23/U/244738/PS)

| Tool | Used for |
|:---|:---|
| Google Gemini (AI Studio API) | The model under evaluation; also used to proof-read code when it fails |
| Claude Code (Anthropic, Claude Opus 5.5) | Coding partner: prompt review and rewrite, `llm_client.py`, test runner, documentation, git operations |
| DeepSeek | Supervisor/teacher: planning, step-by-step guides, early code drafts (`ai_engine.py` v0.1, test-case list), peer review |
| ChatGPT (OpenAI) | Explaining concepts not clear from DeepSeek |
| GitHub Copilot | Fixing inline errors in the editor |

## Material AI-assisted decisions

| # | Date | Decision / artefact | AI source | Human review & verification |
|:---:|:---|:---|:---|:---|
| 1 | 2026-10-01 | Prompt v1.1.0 rewrite | Claude | Every example number re-computed from the CSVs by script; AI-suggested figures from another tool were found wrong (2 low items vs actual 10; wrong total) and rejected |
| 2 | 2026-10-01 | Model fallback client (`llm_client.py`) | Claude | 8 offline scenarios with a fake client (503, 429, timeout, 404, bad key); live run |
| 3 | 2026-10-01 | Rejected `gemini-2.5-flash` as fallback | Suggested by DeepSeek and the user; tested by Claude | Live call returned 404 "no longer available to new users" |
| 4 | 2026-10-02 | 200% cap: flag instead of drop | DeepSeek | Accepted: keeps capped items visible to the human approver (US 12) |
| 5 | 2026-10-02 | 10-case test runner | DeepSeek draft, revised by Claude | Revised because the draft had a precedence bug in TC-01 (`a and b or c`), weak checks (TC-03 did not check the number), and expected a status tag v1.1.0 had removed (TC-09) |
| 6 | 2026-10-02 | TC-08 checker tightened | Claude | The lenient checker passed an output with wrong scope and 3 wrong quantities; strict re-run recorded as FAIL |

## Things the AI got wrong (and how we caught them)

- Invented example figures that did not match our data — caught by recomputing from CSVs.
- A handoff document claimed `gemini-2.5-flash` had ~1,500 requests/day and should be primary — disproved by a live 404.
- A suggested fix would default quantity to 20 for items with no history — rejected because it invents data and breaks the factuality rule.
- `gemini-3.5-flash-lite` computed 3 wrong reorder quantities — evidence for moving maths into tools (Week 4).

## Data handling

Only synthetic data (`src/generate_synthetic_data.py`, seed 42) was sent to Gemini. API keys live only in
`.env` (git-ignored); `.env.example` holds placeholders. Traces store models, errors and timings, not prompt
or response text.
