# Week 5 Progress Report — Agent Architecture and Bounded Autonomy

| Field | Value |
|:---|:---|
| **Group** | [group name] |
| **Project** | SME Procurement Support Agent |
| **Week** | 5 (completed 3 Oct 2026; order chosen: Week 2 → 4 → **5** → 3) |
| **Prepared by** | [Project/Requirements Lead] |
| **Repository** | https://github.com/AJmight/Capstone_project- (tag `week5-complete`) |

## 1. Work completed against the Week 5 objectives

| Brief requirement | Status | Evidence |
|:---|:---:|:---|
| One task that genuinely benefits from multi-step decisions | Done | Weekly restock within a budget — `docs/requirements/agent-task-contract.md` §1 |
| Sense → Plan/Decide → Act/Tool → Observe → Stop/Re-plan design | Done | `docs/architecture/architecture-week5.md` |
| Max iterations, approved tools, stop conditions, hand-off/approval conditions | Done | Contract §3, §6, §8, §9 |
| Implemented with direct orchestration | Done | `src/restock_agent.py` + `src/tool_agent.py` |
| ≥ 3 execution traces incl. one failure/recovery | Done (4) | `evidence/week5/trace_T1…T4.md` (T3 = failure → recovery) |
| Agent Task Contract | Done | `docs/requirements/agent-task-contract.md` |

**Results:** offline 16/16 (Week 4 regression 22/22), live traces 4/4, Week 4 live regression 6/6 after
fixing F-13.

## 2. Key engineering decisions

| Decision | Rationale |
|:---|:---|
| Deterministic `plan_within_budget` (urgency = stock/reorder point, skip-and-continue) | The budget decision must be exact and explainable; the model chooses *when* to plan and how to act on it |
| SENSE done by code before the first model call | Saves a model turn; nothing-low exits with no quota used |
| Task allow-list of 3 tools | Least privilege for this task, below the role's permissions |
| Repeat guard with exactly one retry after `SERVICE_UNAVAILABLE` | Recovers from temporary faults without loops |
| Post-conditions and outcome decided in code | The model's wording cannot declare success |
| Output check against false draft claims | F-13: prompt rules alone did not stop it |
| Fault injection (off by default, marked `injected` in traces) | A repeatable, honest failure/recovery trace |
| Scripted fake model for offline tests | Proves the guards work even when the model misbehaves, at zero quota |

## 3. Failures, challenges and response

| Issue | Response |
|:---|:---|
| F-13: a viewer was shown a fake "awaiting approval" draft (regression after adding the planner tool) | Code output check + prompt v2.2.0; regression 6/6 |
| F-14: the prompt told the model to always print the status line | Prompt v2.2.1; T4 re-run clean |
| F-12: the ±10 % range can exceed the budget | Documented for the approver; revisit in Week 7 |
| F-15: Gemini sends integers as floats | Registry converts whole floats |
| Frequent 503s mid-run | Fallback chain switched models mid-run with no state loss |

## 4. Individual contributions

| Member | Role | Tasks owned | Evidence |
|:---|:---|:---|:---|
| Mwesigwa Arnold Mugahi (23/U/244738/PS) | AI Engineering Lead | Restock agent, planner tool, guards, prompt v2.1–v2.2.1, tests, traces, documentation | Commits on `main`, tag `week5-complete` |
| [to be added] | | | |

## 5. Plan for next week

1. **Week 3 RAG:** procurement-policy corpus with a source register, retrieval with citations, 15 RAG
   questions, three retrieval failures. Then wire policy retrieval into the agent as a read tool.
2. **Week 6:** move drafts/audit to SQLite as persistent state; one justified memory use; MCP-style
   interface for the tools.

## 6. Links

- Repository: https://github.com/AJmight/Capstone_project-
- Commit / tag: [paste hash] / `week5-complete`
- ClickUp board: [link]
