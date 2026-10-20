# Architecture Specification: Workflow State & Justified Persistent Memory

**Project:** SME Procurement Preparation Agent (BSE4104 Capstone)  
**Author:** Mwesigwa Arnold Mugahi (Reg No: 23/U/24738/PS, GitHub: AJmight)  
**Lead Academic Convener:** Dr. Kamulegeya Grace B (PhD)  
**Deliverable:** Week 6 Architecture Note  

---

## 1. Problem Statement & Motivation

Foundation models (LLMs) are fundamentally stateless computation engines: each turn receives input tokens and emits output tokens without native memory of past actions or commitments. In multi-step agentic software, relying on LLM conversational context alone leads to three critical failure modes:
1. **Workflow State Hallucination:** The model jumps ahead in the business process (e.g., claiming a purchase order is approved before generating a draft).
2. **Context Bloat & Token Inefficiency:** Re-sending entire conversational histories quickly exhausts model token limits and increases API latency.
3. **Cross-Shop Data Leakage:** In multi-tenant systems, storing unstructured text in a shared prompt context risks leaking Shop A's supplier discounts to Shop B (violating Decision-001).

To guarantee robustness, safety, and strict business boundaries, the SME Procurement System enforces **deterministic state machines and justified persistent memory** implemented in SQLite outside the model.

---

## 2. Explicit Workflow State Model

The procurement process follows a deterministic Finite State Machine (FSM) implemented in `src/state.py`.

```
                       [INITIALIZED]
                             │
                             ▼
                    [SENSING_INVENTORY] ──────────────┐
                             │                        │ (Nothing Low)
                             ▼                        ▼
                    [PLANNING_RESTOCK]  ──────> [TERMINATED]
                             │                        ▲
                             ▼                        │ (Budget Zero/Failed)
                    [DRAFTING_ORDER]    ──────────────┘
                             │
                             ▼
                  [AWAITING_APPROVAL] (Human Gate)
                       │          │
        (Human Reject) │          │ (Human Approve in approvals.py)
                       ▼          ▼
                  [REJECTED]  [APPROVED]
```

### State Definitions & Enforced Transitions

| Stage | Triggering Component | Permissible Transitions | Enforced Rule |
| :--- | :--- | :--- | :--- |
| `INITIALIZED` | `run_restock` | `SENSING_INVENTORY`, `TERMINATED` | Budget must be a positive integer $\le 500\text{M UGX}$. |
| `SENSING_INVENTORY` | `get_low_stock` tool | `PLANNING_RESTOCK`, `TERMINATED` | Checks stock against reorder point. If 0 items low $\rightarrow$ terminates gracefully. |
| `PLANNING_RESTOCK` | `plan_within_budget` tool | `DRAFTING_ORDER`, `TERMINATED` | Ranks urgency and packs items within budget. |
| `DRAFTING_ORDER` | `draft_requisition` tool | `AWAITING_APPROVAL`, `TERMINATED` | Creates JSON draft in `data/drafts/`. Max 1 draft per run. |
| `AWAITING_APPROVAL` | Agent completion | `APPROVED`, `REJECTED`, `TERMINATED` | **STRICT HUMAN GATE.** Only human owner in `approvals.py` can transition. |
| `APPROVED` | Human owner | Terminal | Draft accepted. Orders placed manually offline. |
| `REJECTED` | Human owner | Terminal | Draft cancelled. Mandatory reason recorded. |

### SQLite Persistence Schema (`data/procurement.db`)

Workflow sessions and all state transitions are persisted in two relational tables:
1. `procurement_sessions`: Stores `session_id`, `shop_id`, `budget_ugx`, `stage`, `draft_id`, `draft_total_ugx`, `turn_count`, `tool_call_count`, and audit timestamps.
2. `state_transitions`: Immutable append-only audit log recording every transition: `session_id`, `from_stage`, `to_stage`, `reason`, `transitioned_at`, and `metadata_json`.

---

## 3. Justified Persistent Memory Architecture

In accordance with course guidelines, the system rejects unconstrained, open-ended vector storage in favour of **strictly justified structured memory** (`src/memory.py`).

### The Three Justified Memory Use Cases

1. **`SUPPLIER_PREFERENCE`:**
   - *What is stored:* Preferred vendor relationships per SKU or category (e.g., *"For A4 Printing Paper, prefer Kampala Office Supplies if lead time is $\le 3$ days"*).
   - *Why:* Ugandan SME duuka owners build trust with specific distributors over years; the agent must reflect this operational reality rather than purely selecting arbitrary suppliers.
2. **`APPROVAL_FEEDBACK`:**
   - *What is stored:* Owner's recorded rationale when approving or rejecting prior draft requisitions (e.g., *"Rejected draft REQ-004: Exercise book order deferred due to mid-month cashflow squeeze"*).
   - *Why:* Prevents the agent from repeatedly proposing rejected purchase orders in subsequent weeks.
3. **`SEASONAL_POLICY`:**
   - *What is stored:* Verified demand shifts (e.g., *"January Back-to-School season: double reorder point for notebooks"*).
   - *Why:* Accommodates predictable macroeconomic cycles without hallucinating false demand proxies.

### The Non-Silent Authority Rule

A critical requirement of Dr. Kamulegeya's specification is that memory must **never silently control critical decisions**.
When memories are recalled:
1. They are formatted as an explicit markdown notice injected into the model prompt.
2. The agent's generated summary must explicitly cite the memory:
   > *"Notice: Selected Kampala Office Supplies for A4 Paper based on recorded owner preference from 2026-10-02."*
3. The human owner retains exclusive, untransferable authority to approve, edit, or reject the resulting requisition in `src/approvals.py`.

### Multi-Tenant Isolation & Privacy (Decision-001)

- All queries in `MemoryManager` require an explicit `shop_id`.
- The database enforces a compound index on `(shop_id, target_key)`.
- Verification: Scenario `SCEN_20` in `tests/test_week7_evaluations.py` proves that queries from `shop_B` return zero records when querying data stored by `shop_A`.
- **Right to Erasure:** Complete GDPR compliance via `delete_memory(shop_id, memory_id)` and `clear_shop_memories(shop_id)`.
