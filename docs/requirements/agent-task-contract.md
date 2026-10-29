# Agent Task Contract — Weekly Restock Agent

| Field | Value |
|:---|:---|
| **Version** | 1.1 (AI-led restock refinement, 2026-10-27) |
| **Owner** | Mwesigwa Arnold Mugahi (AI Engineering Lead) |
| **Implementation** | `src/restock_agent.py`, `src/tool_agent.py`, `src/tools/` |
| **Model-facing part** | `prompts/procurement_assistant_v2.6.0.md`, Section 3 |
| **Tests** | `tests/test_week5_agent.py` (offline model simulation + live execution traces) |

> **Single trusted user:** the person using the shop's workspace reviews and approves drafts. There are no
> separate user roles; see `docs/requirements/decision-001-single-trusted-user.md`.

## 1. Goal and responsibility split

> Prepare one evidence-grounded draft restock requisition within the user's budget and report all
> unresolved choices or missing information.

The AI reviews current stock, demand history, quotes, minimum order quantities and lead times. It chooses
an item priority order and supplier trade-offs, then explains the recommendation. Python supplies the
evidence, calculates every quantity and cost, validates chosen suppliers, enforces the hard budget and
limits, and determines the final outcome. A human alone approves or rejects the saved draft.

No demand history or quote is invented. When some items lack evidence, the AI may prepare a partial
draft from costable items and must hand off the remaining items. If no item can be costed, no draft is
created. If the AI is unavailable, the run hands off and does not create a deterministic substitute draft.

## 2. Inputs and preconditions

| Input | Rule | If violated |
|:---|:---|:---|
| `budget_ugx` | Positive whole number of UGX | `PRECONDITION_FAILED` |
| `user_name` | Injected by application as `created_by`; never chosen by model | — |
| Inventory, purchase history and quote data | `get_restock_options` must succeed | `HANDOFF_SENSE_FAILED` |
| Low-stock items | At least one item at/below its reorder point | `NOTHING_TO_DO` without a model call |

## 3. Task tools

| Tool | Purpose | Side effect |
|:---|:---|:---|
| `get_restock_options` | Code-run SENSE; returns every low item, exact Python calculations and all supplier quote options | None |
| `plan_within_budget` | Validates the AI's complete priority order and supplier choices, then calculates budget fit | None |
| `draft_requisition` | Saves exactly the included items with the same validated supplier choices | Writes a tenant-scoped SQLite draft |

SENSE runs through `registry.execute_tool()` before the model loop. The model receives only the two
planning/draft tools under the task allow-list. The registry validates tool names, argument shapes and
trusted context. No approval, order, payment or supplier-contact tool exists.

The AI proposes all low item IDs in an explicit order, a quoted supplier for each costable item, brief
evidence-based reasons and a priority rationale. Python verifies every supplier is a current quote,
recomputes quote-specific quantity/cost, and applies the proposed order within the hard budget. The
deterministic planner does not silently replace the AI's priority or supplier choices with a fixed
cheapest-first/urgency-first policy. Calls omitting AI choices retain urgency-first behavior only for
backwards-compatible non-agent use; the bounded agent always requires choices and rationale.

## 4. State

| Field | Set by | Meaning |
|:---|:---|:---|
| `goal`, `budget_ugx`, `user_name` | Start | Task input and trusted requester |
| `low_items`, `restock_options` | SENSE | Low items, quote alternatives, Python-computed quantities/costs and missing-data reasons |
| `plan` | OBSERVE after `plan_within_budget` | Included/deferred/needs-human items, totals, selected suppliers and AI rationale |
| `draft`, `drafts_created` | OBSERVE after `draft_requisition` | Saved draft record and its ID(s) |
| `failures`, `recoveries` | OBSERVE | Tool errors and successful retry evidence |
| `postconditions`, `handoffs`, `outcome`, `timeline` | Agent/code | Auditable checks and stop result; not inferred from model wording |

## 5. Agent loop

```text
PRECONDITIONS (code) -> SENSE (code: get_restock_options)
  -> PLAN/DECIDE (AI chooses priorities and supplier trade-offs)
  -> ACT (registry validates and calculates plan_within_budget)
  -> OBSERVE (state updated; retry one temporary SERVICE_UNAVAILABLE failure)
  -> draft_requisition (only included IDs, with the same selected suppliers)
  -> POSTCONDITIONS (code) -> STOP (outcome decided by code)
```

The model may reconsider an evidence-based priority order once when a budget plan defers items. It must
not repeat the same plan indefinitely. Missing data remains a human hand-off rather than a guessed value.

## 6. Bounded execution

| Limit | Value | Enforced in |
|:---|:---|:---|
| Model turns per run | 5 | `restock_agent.MAX_TURNS` |
| Tool calls per run | 8 | `restock_agent.MAX_TOOL_CALLS` |
| Model-writable tools | 2; SENSE runs in code | `allowed_tools` in `run_agent` |
| Repeated identical call | Blocked; exactly one retry after `SERVICE_UNAVAILABLE` | `run_agent` |
| Drafts per run | At most 1 | Post-conditions |
| Model chain | Existing configured fallback chain; bounded rounds/attempts | `llm_client.call_with_fallback` |

## 7. Post-conditions

| Check | Applies when |
|:---|:---|
| At most one draft per run | Always |
| A validated plan was made before drafting | A draft exists |
| Draft item IDs exactly equal the plan's `included` IDs | A draft exists |
| Draft supplier names and total match the validated plan | A draft exists |
| AI supplier/priority rationale is preserved | A draft exists |
| Draft total does not exceed the budget | A draft exists |
| Draft status is `DRAFT - AWAITING HUMAN APPROVAL` and summary says so | A draft exists |
| No draft is created when no item is included | Plan has no included items |

If a post-condition fails, the outcome is `POSTCONDITION_FAILED` and the checks are recorded for the
human reviewer. `tool_agent.check_output()` also prevents false draft IDs or approval claims.

## 8. Stop conditions and outcomes

| Outcome | When | Human hand-off |
|:---|:---|:---|
| `DRAFT_READY` | Draft created and all post-conditions pass | Review and approve/reject; decide deferred and needs-human items |
| `NOTHING_FITS_BUDGET` | Costable items were proposed but none fit | Revisit budget or priorities |
| `NEEDS_HUMAN` | No items could be costed from available information | Add quotes/history or set quantities |
| `NOTHING_TO_DO` | No low-stock items | None |
| `PRECONDITION_FAILED` | Invalid budget | Correct the input |
| `POSTCONDITION_FAILED` | Model output or draft breaks a rule | Do not approve; inspect trace |
| `HANDOFF_ITERATION_LIMIT` / `HANDOFF_TOOL_CALL_LIMIT` | Bound reached | Review manually or retry |
| `HANDOFF_MODEL_UNAVAILABLE` | All configured models unavailable | Retry later; **no draft was created** |
| `HANDOFF_SENSE_FAILED` | Required records cannot be read | Correct the data |
| `HANDOFF_NO_DRAFT` | Model finished without drafting when it should have | Review trace |

## 9. Human approval and hand-off

- Every saved draft awaits an explicit human decision through the UI's **Approve draft** or **Reject draft**
  buttons, or the CLI (`py src\approvals.py approve|reject <id> --by "Name"`).
- Items with no purchase history require a human-set quantity; items with no quote need a quote.
- Deferred items need a human funding/prioritization decision.
- A line above the 200% cap requires a human override reason.
- Review the ±10% estimated range as well as the exact total.

## 10. Prohibited agent actions

The agent may never approve, order, pay, contact suppliers, connect to banks/mobile money, create more
than one draft per run, draft items/suppliers outside its validated plan, fabricate missing data, or
exceed the bounds above. Actions are absent from the tool registry or checked in code.
