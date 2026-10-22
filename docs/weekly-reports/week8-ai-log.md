# Week 8 AI Engineering Log

**Project:** SME Procurement Preparation Agent (BSE4104 Capstone)
**Author:** Mwesigwa Arnold Mugahi (Reg No: 23/U/24738/PS, GitHub: AJmight)
**Lead Academic Convener:** Dr. Kamulegeya Grace B (PhD)
**Dates:** 20th October 2026

---

## 1. AI Tools Utilized & Roles

In compliance with the BSE4104 academic integrity guidelines, the following AI systems contributed to this week's deliverables:

1. **Kilo (AI coding assistant, running on the local checkout):**
   - **Role:** Primary pair-programming partner for the Week 8 hardening pass and the final release.
   - **Tasks:** Re-read every Week 6 and Week 7 module and ran the code paths the unit tests had not exercised; found and fixed **F-23** (the MCP `tools/call` contract), **F-24** (the approval gate never advanced the state machine) and **F-25** (the MCP server took the tenant from the model); wired the Week 7 guardrails into the running system (`src/app.py`, `src/restock_agent.py`, `src/approvals.py`); wrote `tests/test_week8_release_checks.py` (19 tests); re-based the failure catalogue onto the canonical failure ids and wrote the Week 8 report pack.
2. **Google Antigravity CLI (`agy`):**
   - **Role:** Coding partner for Weeks 6 and 7; it stopped mid-task on 20 October with an exhausted quota while the Week 6/7 documents were being finalised.
   - **Tasks:** `src/state.py`, `src/memory.py`, `src/mcp_interface.py`, `src/guardrails.py`, the 9 Week 6 tests and the 31 Week 7 scenarios, the Week 6/7 reports and the first draft of the failure catalogue. The Week 8 pass corrected and extended that work.
3. **Claude Code (Anthropic):**
   - **Role:** Coding partner for Weeks 1 through 5.
   - **Tasks:** The tool layer, the function-calling loop, the human approval gate, the bounded restock agent, the prompt iterations and the `evidence/` trace infrastructure.
4. **Google Gemini Flash (`gemini-3.8-flash` via `google-genai`):**
   - **Role:** Runtime foundation model.
   - **Tasks:** Served every model call in the system through `src/llm_client.py` with the fallback chain. No live model call was made during the Week 8 hardening pass, because every change in Week 8 is deterministic code and every offline suite is model-free.
5. **DeepSeek (DeepSeek-V3 / R1):**
   - **Role:** Security reviewer / academic tutor.
   - **Tasks:** Guidance on prompt-injection classification and on the deterministic pre-execution interceptors that became `InputGuardrail`.
6. **ChatGPT (GPT-4o):**
   - **Role:** Conceptual tutor.
   - **Tasks:** Help with the evaluation-criteria tables for the Week 7 readings.
7. **GitHub Copilot:**
   - **Role:** Inline code completion.
   - **Tasks:** Repetitive test assertions.

## 2. What the AI was asked to do in Week 8, and what it was not allowed to do

The Week 8 instruction was: *"ensure all weeks up to 7 are committed, do week 8 and finish it, commit it, then look at the tests, make sure the product works perfectly, after which proceed to correct documentation."* The AI was explicitly **not** allowed to:

- change any business rule, quantity, price or threshold (all arithmetic stays in `src/tools/procurement.py`);
- add a tool that approves, orders, pays or contacts a supplier (approval lives only in `src/approvals.py`, and it is a human);
- change a prompt without bumping its version and re-running the tests (no prompt was changed at all in Week 8);
- weaken a test to make a suite pass.

Every change made in Week 8 is in the deterministic layer. **The model was not part of any of it** — which is exactly the architecture this project argues for.

## 3. The three defects the AI found, and how a human checks them

| Failure | What was wrong | How it was found | The check a marker can run |
|:---|:---|:---|:---|
| **F-23** | Every real MCP `tools/call` failed (`TypeError` hidden as JSON-RPC `-32000`) | Reading the call against the registry's real signature; the Week 6 tests stopped one line short of it | `py tests\test_week8_release_checks.py` → `test_tools_call_executes_a_real_tool` |
| **F-24** | The human approval never moved the state machine | Reading `approvals.decide()` against the Week 6 FSM and noticing the two never met | `test_approval_moves_the_session_to_approved` |
| **F-25** | The MCP server let the model choose the tenant | Reading the memory tools against the Week 6 isolation work | `test_cross_shop_memory_request_is_refused` |

None of the three was found by a "does the test pass?" check. All three were found by asking a question the tests were not asking: *which code path does this deliverable actually use in production, and is it covered?*

## 4. Prompting strategy in Week 8

None — and that is the finding. The Week 8 bugs were not prompt bugs, so no prompt was
touched. `prompts/procurement_assistant_v2.5.0.md` and `prompts/policy_qa_v1.0.0.md`
are unchanged since 13 October 2026, which is why the prompt version history has no
Week 8 row. A prompt change would have been the wrong fix: a prompt cannot repair
a function call, and it would have hidden the defect from the next reader.

## 5. Models used in Week 8

| Purpose | Model | Calls |
|:---|:---|---:|
| Week 8 hardening, documentation, release | Kilo (hosted assistant) | n/a (not a Gemini call) |
| Runtime model exercised by the system | `gemini-3.8-flash` with the 5-model fallback chain | 0 during Week 8 (all suites offline) |

The free tier allows 20 requests per model per day, so the Week 8 suites were
designed to run with **zero** model calls. That was a deliberate choice: a release
must be verifiable on a laptop with no quota left.
