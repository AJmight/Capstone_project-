# AI-Led Restock and UI Change Report

**Status:** Implemented; offline suites pass. A live Gemini smoke test was attempted but the
provider returned transient service errors, so a live AI restock run is not yet verified.

## What changed

### Restock is model-led again

The Restock page routes restock questions through the bounded agent in
[`src/restock_agent.py`](../src/restock_agent.py). Before the model is asked to plan, the agent
uses the allow-listed `get_restock_options` tool to gather the current shop's low-stock items,
purchase-history-based quantities and all available supplier price, minimum-order and lead-time
options. The model chooses the priority order and supplier trade-offs, then explains its
recommendation. It does not get to invent the supporting figures.

If records are incomplete, the agent identifies which items need human input and can create a
grounded partial draft from the items that can be costed. If all configured models are unavailable,
the agent hands the work back without making a non-AI draft.

### Python remains the calculation and safety boundary

[`src/tools/procurement.py`](../src/tools/procurement.py) calculates quantities, prices, line totals
and budget fit. It verifies the model's priority list and supplier names against the available
records, rejects unquoted suppliers, and recomputes the final draft. The bounded agent checks that
the draft agrees with the validated plan and enforces the hard budget ceiling.

The AI can prepare a draft only. It cannot approve, place or pay for an order, or contact a supplier.
Those actions remain outside the AI tool allow-list; a person must review each draft.

### Approval review explains the recommendation

The Approvals page in [`src/streamlit_app.py`](../src/streamlit_app.py) presents the AI's short
decision brief, the reason for each supplier choice, the Python-calculated quantity and line total,
and alternative supplier quotes. It provides direct **Approve draft** and **Reject draft** actions.
Rejection and safety-cap overrides still require a human comment.

### Tenant data boundaries were preserved

No tenant-selection, tenant-ID injection, storage, or runtime data-source logic was changed for this
work. The agent receives the active tenant from the application as trusted context; the model does
not choose it. Procurement reads and writes remain scoped to that tenant.

When a business workspace is first opened, the existing initialization code creates its own
workspace from CSV headers and does not copy sample stock, quote, or purchase rows into it. Runtime
restock decisions use that business's records. Offline tests use their own explicit fixtures and
temporary storage; they do not justify changing the app's tenant data flow. A business name is a
workspace selector, not authentication.

### Prompt, tool contract and documentation

The tool-mode prompt is now versioned as
[`prompts/procurement_assistant_v2.6.0.md`](../prompts/procurement_assistant_v2.6.0.md); v2.5.0
was archived and the prompt history updated. The restock contract and project guidance were updated
to describe AI-selected priorities and suppliers, evidence-grounded explanations, missing-data
handoffs and the continued human-approval boundary.

[`docs/requirements/tool-schemas.json`](requirements/tool-schemas.json) was regenerated from
`TOOL_REGISTRY`. Its parameter schemas, side effects and system-injected trusted context now match
the implementation, including the supplier-selection and rationale fields.

## Why these changes were made

The prior Restock page could use deterministic planning as the main path, which made the system feel
like a rules-based planner with AI layered on top. The revised flow puts the model at the center of
the decision that is appropriately its own—prioritizing and weighing supplier trade-offs—while
keeping exact arithmetic, record validation, budget limits and approval under deterministic
controls. This preserves the project's AI-centered purpose without giving the model financial
authority or weakening tenant separation.

The detailed approval brief makes the recommendation inspectable so the person approving it can see
what evidence and trade-offs produced the draft, rather than being asked to trust an unexplained
total.

No latency shortcut was introduced. Evidence gathering, validation, audit traces and human review
were retained; no performance improvement is claimed or measured.

## Verification and current limitation

The offline regression and UI run completed with exit code 0:

| Suite | Result |
|---|---:|
| Week 4 tools | 24/24 |
| Week 5 bounded agent | 20/20 |
| MVP tools | 7/7 |
| Week 3 RAG | Completed successfully |
| Week 6 state and memory | 9/9 |
| Week 7 evaluations | 31/31 |
| Week 8 release checks | 19/19 |
| Streamlit UI workflows | 17/17 |

The changed AI behavior is exercised offline with scripted model responses, including valid
supplier trade-offs, invalid supplier rejection, model outage handoff, and checks that no draft is
created without an AI decision. Those tests verify the agent and its safeguards, but do not prove
that a live provider is currently responding.

The one-request connection smoke test through the shared client was attempted after the offline
suites passed. Gemini returned `503 UNAVAILABLE` for `gemini-3.8-flash` and
`504 DEADLINE_EXCEEDED` for `gemini-3.7-flash`; the configured attempt limit stopped the request.
Therefore, a live Gemini response and live AI restock run remain unverified. No credentials were
printed, and the smoke test did not read or modify a tenant's business records. The failed
provider attempt remains in the normal model-call trace at
[`evidence/traces/llm_calls.jsonl`](../evidence/traces/llm_calls.jsonl).

The Week 8 release checks were rerun after the schema export and passed 19/19, including the
tenant-binding and human-only approval regressions.

The local Streamlit app is already running at [http://localhost:8501](http://localhost:8501);
its health endpoint returned HTTP 200. It can be opened to inspect the UI, but live AI answers
depend on the model provider recovering.
