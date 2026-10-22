# Week 6 Engineering Trail: Memory, State & Interoperability

**Project:** SME Procurement Preparation Agent  
**Author:** Mwesigwa Arnold Mugahi (23/U/24738/PS)  
**Deliverable:** Week 6 Engineering Trail  

---

## 1. Decision Log: Why SQLite Over Transient Memory?

In Week 5, the agent relied on an in-memory Python `dataclass` called `AgentState`. While sufficient for a single execution trace, it lost all memory once the script terminated:
- Previous approval justifications were forgotten.
- If a script crashed mid-execution, the human had no record of which tools were invoked.
- Multi-session continuity across weeks was impossible.

We evaluated three persistence backends:
1. **JSON file dumps:** Simple, but prone to concurrent write race conditions and poor indexing.
2. **PostgreSQL / MySQL:** Excessive infrastructure overhead for a lightweight SME duuka deployment on Windows.
3. **SQLite (Chosen):** Zero configuration, ACID-compliant, natively supported in standard Python library (`sqlite3`), and fast.

**Outcome:** Created `data/procurement.db` managed by `StateManager` and `MemoryManager`.

---

## 2. Finite State Machine (FSM) Implementation

To ensure that the procurement workflow is strictly bounded and reproducible, we mapped all permissible state transitions in `src/state.py`:

```python
VALID_TRANSITIONS = {
    WorkflowStage.INITIALIZED: [WorkflowStage.SENSING_INVENTORY, WorkflowStage.TERMINATED],
    WorkflowStage.SENSING_INVENTORY: [WorkflowStage.PLANNING_RESTOCK, WorkflowStage.TERMINATED],
    WorkflowStage.PLANNING_RESTOCK: [WorkflowStage.DRAFTING_ORDER, WorkflowStage.TERMINATED],
    WorkflowStage.DRAFTING_ORDER: [WorkflowStage.AWAITING_APPROVAL, WorkflowStage.TERMINATED],
    WorkflowStage.AWAITING_APPROVAL: [WorkflowStage.APPROVED, WorkflowStage.REJECTED, WorkflowStage.TERMINATED],
    WorkflowStage.APPROVED: [],
    WorkflowStage.REJECTED: [],
    WorkflowStage.TERMINATED: []
}
```

Whenever `transition_to()` is invoked:
- The system checks if `target_stage` is in the allowed list for `current_stage`.
- If valid, the session is updated and a permanent audit record is inserted into `state_transitions`.
- If invalid, a `ValueError` is raised, preventing rogue agent executions.

---

## 3. Persistent Memory & Multi-Tenant Isolation

Under **Decision-001**, the user clarified that in Ugandan SME duukas, trust is vested in the single business owner. However, different shops must remain strictly isolated:
- Table `shop_memories` includes `shop_id` on every row.
- Retrieval queries filter by `WHERE shop_id = ? AND target_key IN (...)`.
- Tested in [`tests/test_week6_state_memory.py`](../../tests/test_week6_state_memory.py) (`test_multi_tenant_isolation`), confirming Shop B receives 0 results when querying Shop A's items.

---

## 4. MCP Interface Integration

We built `MCPServer` in `src/mcp_interface.py` to decouple tool execution from foundation models. The server exposes:
- Protocol handshake (`initialize`).
- Tool catalogue with JSON Schema validation (`tools/list`).
- Tool execution with active security interception (`tools/call`).
- Data resource URI streams (`resources/read` for `procurement://stock/current`).
