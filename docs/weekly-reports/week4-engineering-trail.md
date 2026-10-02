# Week 4 Engineering Trail — what was done, in order, and why

**Author:** Mwesigwa Arnold Mugahi (23/U/244738/PS), AI Engineering Lead, with Claude Code as coding partner
**Date:** 2026-10-02 · **Starting point:** commit `13cbf52` (tag `week2-complete`)
**Purpose:** a complete, reviewable record so groupmates (and DeepSeek/ChatGPT when asked for help) know
exactly what exists, why it was built that way, and how to check it.

---

## 0. Why Week 4 before Week 3

The brief's weeks are a teaching order; our only hard deadline is the end of October. Week 2 left one
serious open defect, **F-04**: a fallback model computed wrong reorder quantities (Erasers 70 instead
of 63, Printing Paper 50 instead of 53, Stapler 114 instead of 88) and drafted 10 items when one was
asked for. RAG (Week 3) cannot fix arithmetic; tools can. The Week 5 agent also needs tools. So the
team order is **Week 4 → Week 5 → Week 3**.

## 1. Reviewing the DeepSeek Week 4 guide before coding

The guide was a good outline (3 tools, a tool loop, offline/live tests). Reviewing it against our
code and the brief found these problems, which were changed **before** writing code:

| Guide | Problem | What we did |
|:---|:---|:---|
| `tool_agent.py` made its own Gemini client | Bypassed our 6-model fallback → would fail as soon as 3.8's 20/day quota ran out | Uses `llm_client.call_with_fallback()` |
| `qty = max(ceil(raw), 1)` | A well-stocked item would be ordered 1 unit — the TC-06 over-ordering problem | Not low → 0 with a reason (F-09) |
| Only 3 tools, no totals | The model would still add up line totals and budget = F-04 again | 4th tool `draft_requisition` does all totals |
| 200 % cap missing from tools | User Story 12 would be lost | Cap computed in Python (`safety_cap`, `requires_override`) |
| No authorization or argument checks | Brief requires testing missing parameters, unauthorized requests, unavailable services, unexpected responses | `tools/registry.py` gatekeeper |
| No human approval mechanism | Brief: "Add human approval before any higher-impact action" | `src/approvals.py` (human-only CLI) |
| Tools needed `ITM001` IDs | Users say "Bic Pens"; "pens" is ambiguous | Item resolver: ID or name; ambiguity → `AMBIGUOUS_ITEM` |
| Weak test checks (`qty > 0`, `"draft" in text`) | Would pass wrong answers (like Week 2's F-05) | Exact expected values computed independently |
| Prompt "v1.3.0" | Our own rule: moving maths to tools = architecture change = major | Prompt **v2.0.0** |
| `fn(**fc.args)` | `args` can be `None` → crash | `dict(args or {})` in the executor |

## 2. Step-by-step build log

| # | Step | Files | Check performed |
|:---:|:---|:---|:---|
| 1 | Saved user profile and the "comment everything" rule to project memory | — | — |
| 2 | Refactored the fallback loop out of `ChatSession` into a reusable `call_with_fallback(request, label, unusable, order)` so the tool loop gets the same protection; added heavy comments | `src/llm_client.py` (v0.4.0) | Offline fake-client regression 7/7 (503, daily quota, network, 404 skip, all down, bad key, order) |
| 3 | Checked how google-genai 2.25 accepts tool schemas | — | `FunctionDeclaration(parameters_json_schema=...)` accepts standard JSON Schema → same schema reused for validation |
| 4 | Wrote the 4 deterministic tools, CSV validation, item resolver, exact `Fraction` arithmetic | `src/tools/procurement.py` | Smoke test: Erasers 63, Paper 53, Stapler 88, Bic Pens 65, draft total UGX 84,406 = Week 2 verified figure |
| 5 | Wrote the gatekeeper: allow-list, roles, argument validation, context injection, crash wrapping, trace | `src/tools/registry.py`, `src/tools/__init__.py` | Blocked `approve_requisition`, viewer drafting, missing `item`, model-supplied `created_by` |
| 6 | Wrote the human approval CLI with typed confirmation and audit log; fixed a bug in the confirmation word (F-11) | `src/approvals.py` | Cancelled approval leaves the draft unchanged |
| 7 | Added `order` to `call_with_fallback` so one agent run prefers one model (Gemini 3 thought signatures) | `src/llm_client.py` | Regression test "order param" |
| 8 | Wrote the bounded agent loop: role-filtered tools, automatic function calling OFF, max 6 turns / 12 tool calls, named stop reasons, hand-off messages, run trace | `src/tool_agent.py` | Imports OK; live tests |
| 9 | Wrote prompt v2.0.0 (tool mode): no arithmetic, refusal rules, "draft exactly what was asked", error handling, answer format | `prompts/procurement_assistant_v2.0.0.md` | Live tests |
| 10 | Wrote 22 offline + 6 live tests with independent expectations, sandboxed temp folders | `tests/test_week4_tools.py` | **22/22 offline** |
| 11 | Git-ignored runtime drafts; added agent limits to `.env` / `.env.example` | `.gitignore`, `.env.example` | `.env` still ignored |
| 12 | Ran live tests | `evidence/week4/*` | **6/6 live**; found F-07 (model tried a tool it was not given — blocked) |
| 13 | Verified every number in live answers against tool results | — | L-02 57 / UGX 938; L-03 30,940, range 27,846–34,034 |
| 14 | Demonstrated `approvals.py list/show` on the real draft; **did not approve it** (that is a human decision) | `evidence/week4/sample_draft_…json` | Status still DRAFT |
| 15 | Exported tool schemas from code; wrote catalogue, architecture, evaluation, report, AI log, this trail; updated README, handoff, prompt history, Week 2 docs (name, AI tools) | `docs/…` | — |
| 16 | Committed, tagged `week4-complete`, pushed | git | `git ls-remote` matches local |

## 3. How the pieces fit (read in this order when reviewing)

1. `src/tools/procurement.py` — **what** is computed. Start with `_reorder_calculation()`; it is the business rule.
2. `src/tools/registry.py` — **who may** call what, and how arguments are checked (`execute_tool()`).
3. `src/tool_agent.py` — the **loop**: model → tool request → registry → result → model, with limits.
4. `prompts/procurement_assistant_v2.0.0.md` — **how the model is told** to behave.
5. `src/approvals.py` — the **human** step the AI cannot reach.
6. `tests/test_week4_tools.py` — **proof**; each test's docstring says what it proves.

## 4. How to run and check it yourself (PowerShell, repo root, venv active)

```powershell
py tests\test_week4_tools.py --offline        # 22 tests, free, ~1 second
py src\tool_agent.py "Which items are low on stock?"
py src\tool_agent.py "Draft a requisition for Bic Pens and Rulers" --role staff --user "Your Name"
py src\tool_agent.py "Draft a requisition for Rulers" --role viewer        # should be refused
py src\approvals.py list
py src\approvals.py show <draft_id>
py src\approvals.py approve <draft_id> --by "Your Name"                    # type APPROVE
type evidence\week4\tool_traces.jsonl                                      # every tool call
py tests\test_week4_tools.py --live           # 6 cases, uses ~12 model requests
```

## 5. Results

- Offline **22/22**, live **6/6** (`docs/evaluation/week4-tool-evaluation.md`).
- **F-04 closed.** Same injection prompt as Week 2 TC-08 → one line, ITM001, qty 65, from Python.
- New findings: **F-07** (model attempted an ungranted tool, blocked in code), F-08 (thought-signature
  risk, mitigated), F-09 and F-11 (bugs caught in review), F-10 (200 % cap only reachable via MOQ).

## 6. Concepts covered this week (for the report and viva)

- **Function calling:** the model returns a structured request (name + JSON arguments) instead of an
  answer; our code executes it and returns the result for the model to explain.
- **Tool contract:** purpose, input schema, output schema, permission, side effects, failure behaviour.
- **Deterministic core, probabilistic shell:** Python owns facts and maths; the model owns language and
  choosing the next step.
- **Least privilege + defence in depth:** show only allowed tools *and* re-check every call (F-07 proves why).
- **Untrusted model output:** validate the model's arguments exactly like user input.
- **Context injection:** identity (`created_by`) comes from the session, never from the model.
- **Bounded loop:** turn and tool-call budgets with named stop reasons and human hand-off messages.
- **Human-in-the-loop:** the higher-impact action (approval) is outside the AI's reach and audited.
- **Observability:** per-call and per-run traces make the agent inspectable for the demo.

## 7. Known limitations / next steps

- Live evaluation is small (6 cases); Week 7 needs 30+ scenarios on the primary model.
- Drafts are local JSON files; Week 6 can move them to SQLite as persistent state.
- Week 5: Agent Task Contract, a multi-step "prepare this week's requisition" goal, three traces
  (one failure/recovery). Then Week 3 RAG.
