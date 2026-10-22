# Week 6 AI Engineering Log

**Project:** SME Procurement Preparation Agent (BSE4104 Capstone)  
**Author:** Mwesigwa Arnold Mugahi (Reg No: 23/U/24738/PS, GitHub: AJmight)  
**Lead Academic Convener:** Dr. Kamulegeya Grace B (PhD)  
**Dates:** 5th October – 9th October 2026 (Logged: 20th October 2026)  

---

## 1. AI Tools Utilized & Roles

In compliance with BSE4104 coursework transparency guidelines, the following AI systems contributed to this week's deliverables:

1. **Google Antigravity CLI (`agy`):**
   - **Role:** Primary pair programming and agentic coding partner for Week 6 and Week 7.
   - **Tasks:** Designed the SQLite workflow state machine (`src/state.py`), engineered the justified multi-tenant memory architecture (`src/memory.py`), drafted the Model Context Protocol (MCP) server dispatcher (`src/mcp_interface.py`), and authored the test suite [`tests/test_week6_state_memory.py`](../../tests/test_week6_state_memory.py).
2. **Claude Code:**
   - **Role:** Prior coding partner for Weeks 1 through 5.
   - **Tasks:** Built the initial deterministic tool catalogue (`src/tools/procurement.py`), bounded loop agent contract (`src/restock_agent.py`), prompt engineering v1.1.0–v2.4.0, and synthetic CSV corpus.
3. **Google Gemini Flash (`gemini-3.8-flash` via `google-genai`):**
   - **Role:** Runtime foundation model.
   - **Tasks:** Executes inventory interpretation, tool selection, and plain-language summary drafting.
4. **DeepSeek (DeepSeek-V3 / R1):**
   - **Role:** Academic supervisor / second opinion.
   - **Tasks:** Reviewed the theoretical separation between working context and persistent memory; advised on FSM state transition validation patterns.
5. **ChatGPT (GPT-4o):**
   - **Role:** Educational tutor.
   - **Tasks:** Clarified the Anthropic Model Context Protocol (MCP) JSON-RPC 2.0 protocol specifications.
6. **GitHub Copilot:**
   - **Role:** Inline IDE code completion.
   - **Tasks:** Auto-completed standard docstrings and type annotations.

---

## 2. Prompting Strategy & Engineering Observations

### Context Compression vs Structured Memory
When testing prompt length with 10 low-stock items, injecting raw previous session logs increased token consumption by 340%. Switching to structured SQLite memory queries (`retrieve_relevant_memories`) reduced injected context to under 120 tokens per turn, drastically cutting latency and avoiding free-tier rate limits.

### Preventing Silent Autonomy
Early prompt experiments showed that if memory records included phrases like *"Owner wants 50 pens"*, the model occasionally stated *"Order confirmed"*. We resolved this by wrapping injected memory in an explicit `[!IMPORTANT] NON-SILENT AUTHORITY NOTICE`, instructing the model that memory provides context for draft proposals, but human signature in `approvals.py` remains mandatory.
