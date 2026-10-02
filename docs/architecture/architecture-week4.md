# Architecture — Week 4 (Tools and Function Calling)

Owner: Mwesigwa Arnold Mugahi (AI Engineering Lead) · Updated 2026-10-02

The diagrams use Mermaid; GitHub renders them automatically.

## Component view

```mermaid
flowchart TB
    U[Shop staff / owner<br/>question + role] --> A

    subgraph CORE["Application (Python, src/)"]
        A["tool_agent.py<br/>bounded loop<br/>max 6 turns, 12 tool calls"]
        R["tools/registry.py<br/>allow-list, role permission,<br/>argument validation, trace"]
        T["tools/procurement.py<br/>4 deterministic tools<br/>(all maths)"]
        L["llm_client.py<br/>6-model fallback chain"]
        P["prompts/procurement_assistant_v2.0.0.md"]
    end

    subgraph AI["Google Gemini API (external)"]
        G["gemini-3.8-flash → 3.7 → 3.6 → 3.5 → 3.5-lite → 3.1-lite"]
    end

    subgraph DATA["Data (synthetic)"]
        D1[(current_stock.csv)]
        D2[(past_purchases.csv)]
        D3[(supplier_quotes.csv)]
        DR[(data/drafts/*.json)]
    end

    H["approvals.py<br/>HUMAN approval gate<br/>(not callable by the AI)"]
    X["Banks, mobile money,<br/>supplier ordering"]

    P --> A
    A <--> L <--> G
    A -- "function call" --> R -- "checked call" --> T
    T --> D1 & D2 & D3
    T -- "draft_requisition writes" --> DR
    H -- "approve / reject + audit log" --> DR
    U -. "owner decides" .-> H
    A -. "BLOCKED: no tool exists" .-x X
```

## Sequence: "Draft a requisition for Bic Pens"

```mermaid
sequenceDiagram
    participant User
    participant Agent as tool_agent.py
    participant Gemini
    participant Registry as registry.py
    participant Tools as procurement.py
    participant Owner as Owner (approvals.py)

    User->>Agent: question, role=staff, user=Arnold
    Agent->>Gemini: prompt v2.0.0 + 4 tool declarations + question
    Gemini-->>Agent: call draft_requisition(items=["Bic Pens"])
    Agent->>Registry: execute_tool(name, args, role, created_by=Arnold)
    Registry->>Registry: allow-list ✓ permission ✓ args ✓
    Registry->>Tools: draft_requisition(["Bic Pens"], created_by="Arnold")
    Tools->>Tools: qty 65, Kampala @ 476, total 30,940, range 27,846–34,034
    Tools-->>Registry: draft REQ-… saved, status DRAFT
    Registry-->>Agent: result (+ trace line)
    Agent->>Gemini: function response
    Gemini-->>Agent: explanation (numbers copied from result)
    Agent-->>User: answer + "awaiting human approval"
    Owner->>Owner: py src\approvals.py approve REQ-… --by "Owner"
```

## What changed since Week 2

| Week 2 (context mode) | Week 4 (tool mode) |
|:---|:---|
| CSV text pasted into the prompt | Model sees no CSV text; tools read the files |
| Model computed quantities and totals (F-04: wrong numbers) | Python computes everything; model explains |
| Business rules only in the prompt | Business rules in `procurement.py`; prompt says when to use tools |
| Safety relied on the prompt | Allow-list + role permissions + validation in code; prompt is a second layer |
| No approval mechanism | `approvals.py` human gate with audit log |

`src/ai_engine.py` + prompt v1.2.0 (context mode) still work and remain the Week 2 baseline.
