# System Context Diagram (Week 1, updated for the MVP)

Consolidated 2026-10-06 from the Week 1 architecture description (layered: user layer → human approval
gate → core execution → data, with a blocked boundary to payments and supplier ordering).

```mermaid
flowchart TB
    subgraph USERS["People"]
        O[Shop owner / trusted user<br/>asks, reviews, approves]
    end

    subgraph SYS["SME Procurement Support Agent (this project)"]
        UI["User layer<br/>src/app.py console (web UI planned)"]
        GATE["Human approval gate<br/>src/approvals.py"]
        CORE["Core execution<br/>tool_agent / restock_agent (bounded agents)<br/>registry (allow-list) · tools (all maths) · RAG"]
        DATA[("Synthetic data<br/>data/*.csv · knowledge/corpus · data/drafts")]
    end

    G["Google Gemini API<br/>(external, 6-model fallback)"]
    X["Payments, mobile money,<br/>banks, supplier ordering"]

    O --> UI
    O --> GATE
    UI --> CORE
    CORE <--> G
    CORE <--> DATA
    GATE <--> DATA
    CORE -. "BLOCKED: no integration, agent refuses" .-x X
```

One trusted user per shop, no user roles (decision-001). When several shops use the system, each shop is
isolated from the others (planned, `data-protection-and-multi-user.md`).

| Boundary | Rule |
|:---|:---|
| Gemini API | Receives only synthetic data and tool results; no keys or personal data |
| Approval gate | Only people decide; the AI has no route to it |
| Payments / ordering | Out of scope; nothing in the system can reach them |

Detailed views: `architecture-week3-rag.md`, `architecture-week4.md`, `architecture-week5.md`.
