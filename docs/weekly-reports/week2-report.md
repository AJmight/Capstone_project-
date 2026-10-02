# Week 2 Progress Report — Foundation-Model Engineering and Prompting

| Field | Value |
|:---|:---|
| **Group** | [group name] |
| **Project** | SME Procurement Support Agent |
| **Week** | 2 (7–11 Sept 2026; completed late, 2 Oct 2026) |
| **Prepared by** | [Project/Requirements Lead] |
| **Repository** | https://github.com/AJmight/Capstone_project- (tag `week2-complete`) |

## 1. Work completed against the Week 2 objectives

| Brief requirement | Status | Evidence |
|:---|:---:|:---|
| Choose an accessible model; document capability, cost, latency, privacy, access | Done | `docs/requirements/model-selection.md` |
| Integrate the model into the application | Done | `src/llm_client.py` (6-model fallback), `src/ai_engine.py` |
| Prompt Specification v1.0: role, task, context, constraints, output format, failure behaviour | Done | `prompts/procurement_assistant_v1.2.0.md` |
| At least two meaningful prompt iterations | Done (3 versions) | `prompts/prompt_history.md`, `prompts/archive/` |
| At least 10 test cases, expected vs actual | Done | `tests/test_week2_cases.py`, `docs/evaluation/week2-prompt-evaluation.md` |

**Result:** v1.1.0 7/10 → v1.2.0 9/10 (strict checker). Remaining failure documented as F-04.

## 2. Key engineering decisions

| Decision | Rationale |
|:---|:---|
| Gemini Flash family, `gemini-3.8-flash` primary | Free without a card; JSON output; function calling for Week 4 |
| Automatic fallback across 6 models in one shared client | Free tier is 20 requests/day **per model** and 503s are frequent; switching is faster than retrying |
| `gemini-2.5-flash` dropped | Returns 404 "no longer available to new users" |
| Prompts as versioned `.md` files with BEGIN/END markers | Brief requires versioned prompts; only the marked section is sent to the model |
| Temperature 0.1, JSON mode for analysis/requisitions | Procurement figures must be stable and machine-checkable |
| Test expectations computed from the CSVs | Hand-typed expected numbers were wrong in early drafts |
| Synthetic data only | Google free-tier data may be used for product improvement |

## 3. Failures, challenges and response

| Issue | Response |
|:---|:---|
| v1.0.0 prompt example showed the AI approving a purchase order | Rewritten as a refusal (v1.1.0) |
| AI drafted a requisition for a well-stocked item (TC-06) | New rule in v1.2.0; re-test PASS |
| 429 daily quota and 503 high demand stopped test runs | Fallback chain + 60 s timeout; every call traced in `evidence/traces/llm_calls.jsonl` |
| VS Code Prettier silently changed a formula in the prompt | Formulas in code spans; `.prettierignore` |
| Lite model made scope and arithmetic errors (TC-08) | Open: v1.3.0 wording and Week 4 deterministic tools |
| Week 2 completed late | Weeks 3–5 work planned immediately (see §5) |

## 4. Individual contributions

| Member | Role | Tasks owned | Evidence |
|:---|:---|:---|:---|
| Mwesigwa Arnold Mugahi (23/U/244738/PS) | AI Engineering Lead | Prompt spec v1.0–v1.2, `llm_client.py`, `ai_engine.py`, 10-case evaluation | Commits on `main` |
| [name] | Project/Requirements Lead | [this report, ...] | [link] |
| [name] | Application/Integration Lead | [...] | [link] |
| [name] | Quality/Security Lead | [review of test cases, ...] | [link] |
| [name] | DevOps/Documentation Lead | [...] | [link] |

## 5. Plan for next week (catch-up: Weeks 3–5)

1. **Week 4 tools first** — `get_low_stock()`, `compare_quotes()`, `estimate_reorder()`, `draft_requisition()` as deterministic Python, with schemas and failure tests (fixes F-04).
2. **Week 5 agent** — bounded plan → act → observe loop over those tools, iteration limit, human approval gate, 3 traces.
3. **Week 3 RAG** — small procurement-policy corpus with source register and 15 RAG questions.
4. Re-run the 10 Week 2 cases on `gemini-3.8-flash` when its quota resets.

## 6. Links

- Repository: https://github.com/AJmight/Capstone_project-
- Commit / tag: [paste hash] / `week2-complete`
- ClickUp board: [link]
