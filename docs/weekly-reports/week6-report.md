# BSE4104 AI Agentic Capstone: Week 6 Progress Report
**Topic:** Memory, State, and Interoperability  
**Student:** Mwesigwa Arnold Mugahi (Reg No: 23/U/24738/PS, GitHub: AJmight)  
**Role:** AI Engineering Lead  
**Dates:** 5th October – 9th October 2026 (Consolidated: 20th October 2026)  
**Convener:** Dr. Kamulegeya Grace B (PhD)  

---

## 1. Executive Summary & Goals
During Week 6, the SME Procurement Preparation Agent progressed from a stateless, bounded tool loop into an explicit, state-aware, and interoperable system. In accordance with the project syllabus, we achieved three primary milestones:
1. **Explicit Workflow State Machine:** Replaced transient conversational context with a persistent Finite State Machine (FSM) backed by SQLite (`data/procurement.db`).
2. **Justified Persistent Memory:** Implemented an audited, multi-tenant memory store capturing verified owner supplier preferences and historical approval feedback without permitting silent decision control.
3. **Model Context Protocol (MCP) Interface:** Built an MCP JSON-RPC 2.0 server exposing procurement tools and resources across a standardized, permission-bounded security boundary.

---

## 2. Key Accomplishments

### A. SQLite Workflow State Engine (`src/state.py`)
Foundation models cannot be trusted to self-regulate business process lifecycles. We engineered `StateManager`, enforcing seven valid workflow stages:
$$\text{INITIALIZED} \rightarrow \text{SENSING\_INVENTORY} \rightarrow \text{PLANNING\_RESTOCK} \rightarrow \text{DRAFTING\_ORDER} \rightarrow \text{AWAITING\_APPROVAL} \rightarrow \text{APPROVED / REJECTED}$$
- **State Transition Graph:** Illegal transitions (e.g. attempting to jump from `INITIALIZED` straight to `APPROVED`) are blocked at runtime with descriptive errors.
- **Auditability:** Every transition records timestamp, triggering user, from/to states, and rationale in table `state_transitions`.

### B. Justified Persistent Memory (`src/memory.py`)
To prevent memory pollution and hallucination, storage is strictly restricted to justified procurement facts:
- `SUPPLIER_PREFERENCE`: SME owner relationships and preferred delivery terms.
- `APPROVAL_FEEDBACK`: Records owner justifications when rejecting or modifying drafts in `approvals.py`.
- `SEASONAL_POLICY`: Contextual demand spikes (e.g. Back-to-School exam periods).
- **Tenant Isolation (Decision-001):** Indexed by `shop_id`. Shop A's records are completely inaccessible to Shop B.
- **Non-Silent Authority:** Recalled memories are explicitly cited in prompt context and final summaries. The human owner retains untransferable approval rights.

### C. Model Context Protocol Interface (`src/mcp_interface.py`)
Aligned with the Anthropic MCP specification (`2024-11-05`), we implemented a compliant JSON-RPC 2.0 dispatcher:
- Declares standard tool definitions with JSON Schema parameter validation.
- Exposes live resources (`procurement://stock/current`, `procurement://suppliers/quotes`).
- Enforces permission tiers (`read_only` vs `draft_write`) and actively rejects autonomous approval/payment tool invocations.

---

## 3. Verification & Evidence
- **Automated Test Suite:** Created [`tests/test_week6_state_memory.py`](../../tests/test_week6_state_memory.py), executing 9 rigorous unit tests covering session lifecycle, transition violations, tenant isolation, GDPR deletion, and MCP protocol handshakes.
- **Test Result:** 9/9 passed (100% pass rate).

---

## 4. Challenges & Engineering Reflections
1. **In-Memory vs Database Drift:** During initial memory retrieval tests, in-memory recall counters did not reflect database increments immediately. Resolved by updating the returned object state synchronously upon query completion.
2. **MCP Compatibility in Python:** Standardizing tool schemas to adhere to JSON Schema draft-07 ensured interoperability with standard MCP client inspectors without requiring vendor-specific wrappers.

---

## 5. Individual contributions

Only work that each person did is recorded here (AGENTS.md rule 12). Evidence is the commit history.

| Member | Role | Week 6 work | Evidence |
|:---|:---|:---|:---|
| Mwesigwa Arnold Mugahi (23/U/24738/PS) | AI Engineering Lead | Workflow state machine `src/state.py`, justified memory `src/memory.py`, MCP interface `src/mcp_interface.py`, `tests/test_week6_state_memory.py`, this report | Commit `d096ee6` on `main` |
| Boonabaana Bronia ([reg no]) | [role] | Central scoped SQLite storage `src/storage.py` (drafts, audit events, sessions, memories, all keyed by `tenant_id` + `user_id`); trusted shop/user context injected by `src/tools/registry.py` (`PROTECTED_CONTEXT_ARGS`: the model cannot choose its shop); drafts saved to SQLite in `draft_requisition`; tenant-scoped RAG index (`rag/index.py`, `tools/knowledge.py`, `rag/policy_qa.py`); `tests/test_week6_storage.py`; `docs/requirements/memory-design-and-data-handling.md`, `docs/architecture/mcp-tool-capability-spec.md`. Merged through PR #1. On 23 Oct found and fixed the merge regression F-26 (see Week 8 report §7) | Commit `741a29e`, PR #1, branch `fix-draft-storage` |
| [name] | [role] | [to be filled in by the member] | [link] |

> **Integration note (added 23 Oct 2026).** The two Week 6 implementations above were built in
> parallel and merged afterwards. Both now share one draft store (`data/state.sqlite3`, via
> `storage.SQLiteStorage`); the state machine and the shop memories remain in
> `data/procurement.db`. See failure F-26 in `docs/evaluation/failure-catalogue.md`.
