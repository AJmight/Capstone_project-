# Week 4 Progress Report — Tools and Function Calling

| Field | Value |
|:---|:---|
| **Group** | [group name] |
| **Project** | SME Procurement Support Agent |
| **Week** | 4 (completed 2 Oct 2026; done before Week 3 by team decision — tools fix the open F-04 defect and the Week 5 agent needs them) |
| **Prepared by** | [Project/Requirements Lead] |
| **Repository** | https://github.com/AJmight/Capstone_project- (tag `week4-complete`) |

## 1. Work completed against the Week 4 objectives

| Brief requirement | Status | Evidence |
|:---|:---:|:---|
| ≥ 2 tools with purpose, input/output schema, authorization, failure behaviour | Done (4 tools) | `docs/requirements/tool-catalogue.md`, `tool-schemas.json` |
| Tool/function calling through the orchestration layer | Done | `src/tool_agent.py`, `src/tools/registry.py` |
| One tool retrieves current data or makes a low-risk simulated side effect | Done (both) | `get_low_stock` reads live CSV; `draft_requisition` saves a draft file |
| Test missing parameters, unauthorized requests, unavailable services, unexpected responses | Done | 22 offline tests, `docs/evaluation/week4-tool-evaluation.md` |
| Human approval before any higher-impact action | Done | `src/approvals.py` (not callable by the AI) |
| Updated architecture diagram | Done | `docs/architecture/architecture-week4.md` |

**Results:** offline 22/22, live 6/6. Week 2 defect **F-04 closed** (exact quantities; L-03 drafts only
the requested item with qty 65).

## 2. Key engineering decisions

| Decision | Rationale |
|:---|:---|
| All maths in Python (`procurement.py`), exact fractions/integers | LLM arithmetic was wrong in Week 2 (F-04) |
| A 4th tool, `draft_requisition`, computes totals and budget | Otherwise the model would still add up costs |
| Gatekeeper `execute_tool()`: allow-list → role → argument validation → safe run → trace | Brief's authorization and failure testing; the model is untrusted input |
| Model is shown only the tools its role allows, and permissions are re-checked | Defence in depth — proven necessary by F-07 |
| `created_by` injected from the session | The AI cannot claim to be the owner |
| No approve/order/pay tool; human `approvals.py` with typed confirmation and audit log | Bounded autonomy; User Stories 10–12 |
| Agent uses the shared fallback client and prefers one model per run | Quota resilience; Gemini 3 thought signatures |
| Prompt bumped to **2.0.0** (not 1.3.0) | Our change discipline classes "maths moved to tools" as an architecture change |

## 3. Failures, challenges and response

| Issue | Response |
|:---|:---|
| Model requested a tool its role was never given (F-07) | Blocked by the registry; documented as evidence for code-level authorization |
| Guide code would order 1 unit of well-stocked items (F-09) | Fixed in review before merge |
| 200 % cap cannot trigger from the SMA formula alone (F-10) | Kept for MOQ-driven orders; tested with synthetic data (O-12) |
| Free-tier quota | Offline suite needs no model; live suite ≈ 12 requests |

## 4. Individual contributions

| Member | Role | Tasks owned | Evidence |
|:---|:---|:---|:---|
| Mwesigwa Arnold Mugahi (23/U/244738/PS) | AI Engineering Lead | Tools, registry, agent loop, approval gate, prompt v2.0.0, tests, documentation | Commits on `main`, tag `week4-complete` |
| [name] | Project/Requirements Lead | [this report] | [link] |
| [name] | Application/Integration Lead | [review of `tool_agent.py` / UI plan] | [link] |
| [name] | Quality/Security Lead | [review of the 22 offline tests] | [link] |
| [name] | DevOps/Documentation Lead | [...] | [link] |

## 5. Plan for next week

1. **Week 5 bounded agent:** formalise `tool_agent.py` with an Agent Task Contract (goal, tools, state,
   limits, stop conditions, hand-off), a multi-step "prepare this week's requisition" workflow, and
   three execution traces including one failure/recovery.
2. **Week 3 RAG** afterwards: procurement-policy corpus, source register, 15 questions.

## 6. Links

- Repository: https://github.com/AJmight/Capstone_project-
- Commit / tag: [paste hash] / `week4-complete`
- ClickUp board: [link]
