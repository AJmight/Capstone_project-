# Week 5 Engineering Trail — what was done, in order, and why

**Author:** Mwesigwa Arnold Mugahi (23/U/244738/PS), AI Engineering Lead, with Claude Code as coding partner
**Dates:** 2026-10-02/03 · **Starting point:** commit `6624dda` (tag `week4-complete`)
**Purpose:** a complete record so groupmates, DeepSeek or ChatGPT can see exactly what exists, why, and how to check it.

---

## 0. Starting state

- Week 4's draft `REQ-20261002-060953-D014` (65 Bic Pens, UGX 30,940) was approved by Mwesigwa Arnold
  Mugahi through `src/approvals.py` — the human gate used for real (`data/drafts/audit_log.jsonl`).
- Week 4 already had a bounded tool loop (`tool_agent.py`), so Week 5 focused on a **goal** that needs
  several decisions, explicit **state**, a written **contract**, and **traces**.

## 1. Choosing the task

The brief asks for one task that *genuinely* benefits from multi-step decision making. Candidates:

| Candidate | Verdict |
|:---|:---|
| "Draft a requisition for X" | One tool call — not multi-step |
| "Weekly restock within a budget" | **Chosen.** Needs: what is low → what fits the budget → what to defer → what cannot be priced → whether to draft → what to tell the human; plus failure handling |

## 2. Design decisions

| Decision | Why | Alternative rejected |
|:---|:---|:---|
| New deterministic tool `plan_within_budget` | Budget choice is maths; the model must not do it (F-04 lesson) | Letting the model pick items to fit the budget |
| Urgency = stock / reorder point, greedy skip-and-continue | Simple, explainable, predictable by a reviewer | Optimal knapsack — harder to explain, little benefit at this size |
| SENSE done by code | Saves one model turn; "nothing low" exits without spending quota | Letting the model call `get_low_stock` |
| Task allow-list (3 tools) | Least privilege per task, tighter than the role | Using every tool the role allows |
| Repeat guard + exactly one retry for `SERVICE_UNAVAILABLE` | Stops loops; allows recovery from temporary faults | Unlimited retries / no retries |
| Post-conditions + outcome decided by code | The model's words cannot declare success | Trusting the model's summary |
| Explicit `AgentState` updated by an observer hook | State is inspectable and drives the trace and hand-offs | State hidden inside the conversation |
| Fault injection for the failure trace, marked `injected: true` | A repeatable, honest failure/recovery case | Waiting for a random real outage |
| Scripted fake model for offline tests | Prove guards work when the model misbehaves, at zero quota | Only live tests |

## 3. Step-by-step build log

| # | Step | Files | Check performed |
|:---:|:---|:---|:---|
| 1 | Confirmed the Week 4 approval in the audit log | `data/drafts/audit_log.jsonl` | APPROVED by Mwesigwa Arnold Mugahi |
| 2 | Added tool 5 `plan_within_budget` | `src/tools/procurement.py` v1.1.0 | 2,000,000 → 6 items 1,619,289; 300,000 → 4 items 294,130 (defers ITM007, ITM006); 10,000 → none — matches hand calculation |
| 3 | Registered it; whole floats → int (Gemini sends 300000.0); `minimum` check; `RETRYABLE_ERRORS`; fault injection (`inject_fault`, `AGENT_FAULTS`) | `src/tools/registry.py` v1.1.0 | 300000.0 accepted; 2.5, 0 rejected; injected fault then success |
| 4 | Loop upgrades: per-turn `steps` with model text, repeated-call guard, observer hook, `trace_label` | `src/tool_agent.py` v1.1.0 | Imports, offline tests |
| 5 | Prompt v2.1.0: planner in tool table + Section 7 "Weekly Restock Task" | `prompts/…v2.1.0.md` (now archived) | Live traces |
| 6 | Task allow-list (`allowed_tools`, `NOT_IN_TASK_CONTRACT`) and richer observer arguments | `src/tool_agent.py` | A-09 |
| 7 | Wrote the restock agent: contract constants, `AgentState`, preconditions, SENSE, loop, post-conditions, code-decided outcome, `agent_checks` in the draft file, hand-offs, JSONL + Markdown traces, CLI | `src/restock_agent.py` | Offline + live |
| 8 | Wrote 15 offline tests with a scripted fake Gemini (ideal, greedy, double-draft, looping, off-contract, unavailable, forgetful) + 4 live traces; fixed a crash in my own fake model | `tests/test_week5_agent.py` | **15/15**, Week 4 offline 22/22 |
| 9 | Ran live traces T1–T4 on v2.1.0 | `evidence/week5/runs_prompt_v2.1.0/` | 4/4; T3 shows fail → retry → RECOVERED |
| 10 | Re-ran Week 4 live tests on v2.1.0 (regression) | same folder | **5/6 — L-05 FAIL → F-13** (viewer shown a fake "awaiting approval" draft) |
| 11 | Fixed F-13 in code: `check_output()` removes false draft claims and adds a system notice; `output_warnings` recorded | `src/tool_agent.py` v1.2.0 | Unit check; A-16 |
| 12 | Prompt v2.2.0: hard rule 3 (only real drafts; "information only" without the tool) | `prompts/…v2.2.0.md` (archived) | Week 4 live **6/6**; traces 4/4 |
| 13 | Found the output check had corrected live T4 on v2.2.0 → traced to a contradiction in Section 7 (F-14) | `evidence/week5/runs_prompt_v2.2.0/` | — |
| 14 | Prompt v2.2.1: status line only when a draft exists; re-ran T4 | `prompts/procurement_assistant_v2.2.1.md` | T4 ends "No requisition was created.", no warnings |
| 15 | Recorded `output_warnings` in restock traces; regenerated tool schemas (5 tools) | `src/restock_agent.py`, `docs/requirements/tool-schemas.json` | offline 16/16 |
| 16 | Wrote the contract, architecture, evaluation, report, AI log and this trail; updated tool catalogue, prompt history, README, handoff | `docs/…` | — |
| 17 | Committed, tagged `week5-complete`, pushed | git | `git ls-remote` matches local |

## 4. Reading order for reviewers

1. `docs/requirements/agent-task-contract.md` — what the agent must do and must never do.
2. `src/tools/procurement.py` → `plan_within_budget()` — how the budget decision is made.
3. `src/restock_agent.py` → `run_restock()` — the phases in order; then `AgentState.observe()` and `check_postconditions()`.
4. `src/tool_agent.py` → `run_agent()` (guards) and `check_output()`.
5. `evidence/week5/trace_T3_failure_recovery.md` — one run, every phase visible.
6. `tests/test_week5_agent.py` — each test's docstring states what it proves.

## 5. How to run it yourself (PowerShell, repo root, venv active)

```powershell
py tests\test_week5_agent.py --offline                            # 16 tests, free
py src\restock_agent.py --budget 300000 --user "Your Name"        # live run, prints the timeline
py src\restock_agent.py --budget 300000 --save-trace my_run       # also writes evidence\week5\trace_my_run.md
py src\restock_agent.py --budget 300000 --role viewer             # PRECONDITION_FAILED, no model call
$env:AGENT_FAULTS="plan_within_budget:1"; py src\restock_agent.py --budget 300000; Remove-Item Env:AGENT_FAULTS
py src\approvals.py list                                          # the drafts the agent created
py tests\test_week5_agent.py --live                               # the 4 traces (~14 model requests)
```

## 6. Results

- Offline **16/16**, Week 4 offline **22/22**, live traces **4/4**, Week 4 live regression **6/6** (after F-13 fix).
- Findings: **F-12** (range can exceed budget), **F-13** (false draft claim — fixed in code and prompt),
  **F-14** (prompt contradiction — fixed), **F-15** (floats from Gemini — fixed).
- Drafts created by the live runs are waiting in `data/drafts/` for a human decision.

## 7. Concepts covered this week

- **Goal-directed agent vs. chatbot:** the agent pursues a goal across several steps and decides what to do next from what it observes.
- **Sense → Plan → Act → Observe → Re-plan → Stop:** made explicit in the timeline of every trace.
- **Explicit state:** everything the agent knows is in one inspectable object, not hidden in the conversation.
- **Bounded autonomy:** turn and tool budgets, task allow-list, repeat guard, one retry.
- **Preconditions / post-conditions:** design-by-contract applied to an AI agent; the outcome is decided by code.
- **Failure and recovery:** a temporary fault, one retry, recovery recorded — and safe stops when recovery is impossible.
- **Human hand-off:** the agent always ends by listing what a person must decide.
- **Defence in depth:** F-07 (Week 4) and F-13/F-14 (Week 5) each showed a prompt rule failing and code catching it.
- **Fault injection / chaos testing:** deliberately breaking a dependency to prove the agent recovers.
- **Testing agents with a scripted fake model:** deterministic tests of agent control flow without the real model.

## 8. Known limitations / next steps

- Four live scenarios; Week 7 needs 30+ on the primary model.
- Greedy budget planning is explainable but not always cost-optimal.
- Next: Week 3 RAG (policy corpus, citations, 15 questions), then Week 6 (SQLite state, memory, MCP-style interface).

---

## 9. Update — 2026-10-06 (MVP session)

What changed around the Week 5 agent, and proof that it still works:

| Change | Effect on the restock agent |
|:---|:---|
| Prompt v2.2.1 → v2.3.0 → **v2.4.0** (new tools `get_inventory`, `query_purchase_history`, `search_policy`; policy-citation and clarifying-question rules; `UNKNOWN_CATEGORY` rule) | Section 7 (restock task) unchanged. The task allow-list still exposes only `get_low_stock`, `plan_within_budget`, `draft_requisition`, so the new tools cannot be used inside a restock run |
| Draft lines now store `safety_cap` | Lets a human edit (`approvals.py edit`) re-check the 200 % cap |
| `approvals.py edit` (User Story 9) | Owners can change a quantity on an agent-created draft before deciding; the AI suggestion is kept and the edit audited; `agent_checks` gets a note that the draft changed after the checks |
| `src/app.py` console menu, option 2 | Runs `run_restock()` interactively |

**Regression on prompt v2.4.0 (2026-10-06):** Week 5 traces **4/4** (T1 DRAFT_READY 1,619,289; T2 DRAFT_READY
294,130; T3 fail → retry → RECOVERED → DRAFT_READY; T4 NOTHING_FITS_BUDGET), Week 5 offline **16/16**,
Week 4 live **6/6**, Week 4 offline **22/22**. The traces in `evidence/week5/trace_T*.md` are from this run
(models 3.5-flash and 3.5-flash-lite, because 3.8/3.7 had used their daily quota — the fallback chain
carried the run). In Week 4 L-05 the viewer's model again tried `draft_requisition` and was blocked (F-07).
