# Agent Architecture — Week 5 (Bounded Weekly Restock Agent)

Owner: Mwesigwa Arnold Mugahi (AI Engineering Lead) · Updated 2026-10-03 · Builds on `architecture-week4.md`.

## Agent loop as a state machine

```mermaid
stateDiagram-v2
    [*] --> PRECONDITIONS
    PRECONDITIONS --> STOP: bad budget or role<br/>PRECONDITION_FAILED
    PRECONDITIONS --> SENSE: ok
    SENSE --> STOP: nothing low<br/>NOTHING_TO_DO
    SENSE --> PLAN_DECIDE: low items in [SENSE] block
    PLAN_DECIDE --> ACT: model requests an allowed tool
    PLAN_DECIDE --> POSTCONDITIONS: model writes summary
    ACT --> OBSERVE: registry runs tool (allow-list, role, args)
    OBSERVE --> REPLAN: deferred items / nothing fits / SERVICE_UNAVAILABLE
    REPLAN --> PLAN_DECIDE
    OBSERVE --> PLAN_DECIDE: next step
    PLAN_DECIDE --> STOP: turn or tool limit / all models down<br/>HANDOFF_*
    POSTCONDITIONS --> STOP: DRAFT_READY / NOTHING_FITS_BUDGET /<br/>POSTCONDITION_FAILED
    STOP --> [*]
```

## Components and responsibilities

```mermaid
flowchart LR
    H[Staff / owner<br/>budget + role] --> RA

    subgraph RA["restock_agent.py (contract)"]
        PRE[Preconditions] --> SEN[SENSE<br/>get_low_stock]
        SEN --> LOOP
        ST[(AgentState)]
        POST[Post-conditions<br/>+ outcome]
    end

    subgraph LOOP["tool_agent.run_agent (bounded loop)"]
        M[Gemini via llm_client<br/>fallback chain]
        G[Guards: task allow-list,<br/>repeat guard, turn/tool limits]
        OC[Output check<br/>no false draft claims]
    end

    LOOP -- "observe()" --> ST
    G --> REG[registry.execute_tool<br/>role + argument checks]
    REG --> T1[plan_within_budget]
    REG --> T2[draft_requisition]
    T2 --> D[(data/drafts)]
    LOOP --> POST
    POST --> TR[(evidence/week5 traces)]
    D --> AP[approvals.py<br/>HUMAN decision]
```

## Division of responsibility

| Concern | Owner | Where |
|:---|:---|:---|
| What is low, every quantity/price/total, which items fit the budget | Python (deterministic) | `procurement.py` |
| Which approved tool to call next; reacting to failures; explaining | Model | prompt v2.2.1 §7, `run_agent` |
| Limits, allow-list, repeat guard, false-claim correction | Python | `tool_agent.py` |
| Preconditions, post-conditions, final outcome, hand-off list | Python | `restock_agent.py` |
| Approve/reject; quantities for needs-human items; funding deferred items | Human | `approvals.py` |

## Changes from Week 4

| Week 4 | Week 5 |
|:---|:---|
| One question → tools → answer | One goal → plan → draft → summary, with re-planning |
| Limits: turns, tool calls | + task allow-list, repeat guard with one retry, pre/post-conditions |
| Stop = model finished | Outcome decided by code from explicit state |
| Traces: JSON lines | + readable Sense→…→Stop Markdown traces |
| — | Output check against false draft claims (F-13) |
