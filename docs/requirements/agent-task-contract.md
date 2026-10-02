# Agent Task Contract — Weekly Restock Agent

| Field | Value |
|:---|:---|
| **Version** | 1.0 (Week 5) |
| **Owner** | Mwesigwa Arnold Mugahi (AI Engineering Lead) |
| **Implementation** | `src/restock_agent.py` (contract, state, pre/post-conditions, outcome), `src/tool_agent.py` (bounded loop), `src/tools/` (tools, registry) |
| **Model-facing part** | `prompts/procurement_assistant_v2.2.1.md`, Section 7 |
| **Tests / traces** | `tests/test_week5_agent.py` (16 offline + 4 live), `evidence/week5/trace_T*.md` |

## 1. Goal

> Prepare **one** draft restock requisition for this week that stays **within the budget**, and report
> everything that still needs a **human decision**.

**Why this task needs an agent (multi-step decisions):** the right action depends on what each step
returns — which low items fit the budget, which must be deferred, which cannot be priced (no purchase
history), whether a failed tool should be retried, and whether a draft should be created at all. A
single prompt or a single tool call cannot handle all of these branches.

## 2. Inputs and preconditions (checked in code before any model call)

| Input | Rule | If violated |
|:---|:---|:---|
| `budget_ugx` | positive whole number of UGX | `PRECONDITION_FAILED` |
| `role` | must have the `draft` permission (staff, owner) | `PRECONDITION_FAILED` |
| `user_name` | recorded as `created_by` on the draft (from the session, never from the model) | — |
| Inventory data | `get_low_stock` must succeed | `HANDOFF_SENSE_FAILED` |
| Something to do | at least one low item | `NOTHING_TO_DO` (no model call) |

## 3. Approved tools (task allow-list)

| Tool | Purpose in this task | Side effect |
|:---|:---|:---|
| `get_low_stock` | SENSE: run by code before the loop; result given to the model | none |
| `plan_within_budget` | PLAN: which low items fit the budget (most urgent first) | none |
| `draft_requisition` | ACT: create the draft from the plan's `included` items | writes `data/drafts/<id>.json` |

Any other tool — even one the role could normally use, like `compare_supplier_quotes` — is blocked with
`NOT_IN_TASK_CONTRACT`. There is no approve/order/pay tool anywhere in the system.

## 4. State (explicit, `AgentState` in `restock_agent.py`)

| Field | Set by | Meaning |
|:---|:---|:---|
| `goal`, `budget_ugx`, `role`, `user_name` | start | the task |
| `phase` | every step | PRECONDITIONS, SENSE, PLAN/DECIDE, ACT, OBSERVE, RE-PLAN, RECOVERED, POSTCONDITION, STOP |
| `low_items` | SENSE | items at/below reorder point |
| `plan` | OBSERVE after `plan_within_budget` | included / deferred / needs_human / totals |
| `draft`, `drafts_created` | OBSERVE after `draft_requisition` | the draft record and its ID(s) |
| `failures`, `recoveries` | OBSERVE | tool errors; failures followed by a successful retry |
| `postconditions` | after the loop | deterministic checks (section 7) |
| `handoffs` | STOP | what the human must decide (built from state, not from the model's text) |
| `outcome` | STOP | decided by code (section 8) |
| `timeline` | every step | the human-readable trace |

## 5. The loop

```
PRECONDITIONS (code) -> SENSE (code: get_low_stock)
   -> PLAN/DECIDE (model chooses a tool) -> ACT (registry runs it) -> OBSERVE (state updated)
        RE-PLAN: budget too small -> items deferred; temporary failure -> one retry
   -> ... until the model writes its summary or a limit is hit ...
-> POSTCONDITIONS (code) -> STOP (outcome decided by code)
```

Expected path: `plan_within_budget(all low IDs, budget)` → `draft_requisition(included IDs)` → summary.

## 6. Limits (bounded autonomy)

| Limit | Value | Enforced in |
|:---|:---|:---|
| Model turns per run | 5 | `restock_agent.MAX_TURNS` → `run_agent` |
| Tool calls per run | 6 | `restock_agent.MAX_TOOL_CALLS` → `run_agent` |
| Tools | 3 (section 3) | `allowed_tools` in `run_agent` |
| Repeated identical call | blocked (`REPEATED_CALL`); exactly one retry after `SERVICE_UNAVAILABLE` | `run_agent` |
| Drafts per run | 1 (post-condition) | `check_postconditions` |
| Model availability | 6-model fallback chain, 3 rounds | `llm_client.call_with_fallback` |

## 7. Post-conditions (checked in code after the loop)

| Check | Applies when |
|:---|:---|
| At most one draft per run | always |
| A plan was made before drafting | a draft exists |
| Draft items == plan `included` items (exactly) | a draft exists |
| Draft total ≤ budget | a draft exists |
| Draft status is `DRAFT - AWAITING HUMAN APPROVAL` | a draft exists |
| The summary says it awaits human approval | a draft exists |
| No draft when nothing fits the budget | plan has no included items |

If a check fails on a run that produced a draft, the outcome is `POSTCONDITION_FAILED` and the result is
written into the draft file (`agent_checks`) so the human approver sees it.

Separately, every answer passes the **output check** (`tool_agent.check_output`): an answer may not
claim a draft or draft ID that was not created in the run (failure F-13).

## 8. Stop conditions and outcomes (decided by code)

| Outcome | When | Human hand-off |
|:---|:---|:---|
| `DRAFT_READY` | draft created and all post-conditions pass | approve/reject in `approvals.py`; decide `needs_human` and deferred items |
| `NOTHING_FITS_BUDGET` | plan included nothing; no draft | raise the budget or buy manually |
| `NOTHING_TO_DO` | no low items | none |
| `PRECONDITION_FAILED` | bad budget or role | fix input / use a permitted account |
| `POSTCONDITION_FAILED` | the agent's output broke a rule | reject the draft; investigate the trace |
| `HANDOFF_ITERATION_LIMIT` / `HANDOFF_TOOL_CALL_LIMIT` | limits reached | do it manually or retry |
| `HANDOFF_MODEL_UNAVAILABLE` | every model failed | retry later |
| `HANDOFF_SENSE_FAILED` | inventory unreadable | fix the data |
| `HANDOFF_NO_DRAFT` | model finished without drafting when it should have | review the trace |

## 9. Human approval and hand-off conditions

- Every draft requires a human decision (`py src\approvals.py approve|reject <id> --by "Name"`).
- Items with no purchase history (`needs_human`): a human sets the quantity.
- Deferred items: a human decides whether to fund them later.
- Lines with `requires_override` (over the 200 % cap): approval needs an override reason.
- Note: the ±10 % estimate range can exceed the budget even when the exact total does not (F-12);
  the approver should look at the range.

## 10. What the agent may never do

Approve, order, pay, contact suppliers, connect to banks or mobile money, create more than one draft per
run, draft items outside the plan, or exceed the limits above. Each is either impossible (no tool) or
detected in code.
