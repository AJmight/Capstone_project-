# Week 3 and Week 5 — complete reference (what we built, where it is, how it was tested)

Checked against the repository on 2026-10-13. Line numbers refer to that version; if code moves, search
for the function name. Concepts in plain language: `docs/notes/rag-explained.md`, `docs/notes/agentic-ai-notes.md`.

---

## Part A — Week 3: RAG

### A1. Did we do everything the course (and DeepSeek's lesson) describes?

| Item | Done? | Where | Note |
|:---|:---:|:---|:---|
| Corpus of 10–50 documents | ✅ 12 | `knowledge/corpus/*.md` | synthetic, team-written |
| Source register / provenance | ✅ | `knowledge/source-register.md` | |
| Chunking | ✅ | `src/rag/index.py` `load_chunks()` line 114 | by `## ` section; 120-word windows, 30 overlap (lines 59–60) |
| Embedding + vector database | ⚠️ **different choice** | — | we use **BM25 keyword search** (`BM25Index`, line 153), not embeddings. Reasons: no extra library or API quota, deterministic, explainable, 10/10 hit@3 at this size. Embeddings = future work. *Know this for the viva: DeepSeek's lesson describes embeddings; ours is term-based retrieval (Huyen Ch. 6 covers both).* |
| Retrieval of top-k | ✅ | `BM25Index.search()` line 176; `retrieve()` in `src/rag/policy_qa.py` line 51 | top 3 + next section |
| Augmentation with labelled sources | ✅ | `policy_qa.py` lines 106–109 | see A2 |
| Generation with citations | ✅ | `prompts/policy_qa_v1.0.0.md` rules 1–6 (lines 21–29) | |
| Citations checked | ✅ (beyond the lesson) | `check_citations()` `policy_qa.py` line 81 | |
| Unanswerable handled | ✅ | score gate `if not sources:` line 101 + prompt rule 4 | |
| 15 questions (5/5/5) | ✅ | `tests/test_week3_rag.py` `QUESTIONS` lines 47–74 | see A3 |
| ≥ 3 retrieval failures | ✅ 5 | `docs/evaluation/week3-rag-evaluation.md` | R-1 … R-5 |
| RAG architecture diagram | ✅ | `docs/architecture/architecture-week3-rag.md` | |
| Hybrid RAG (text + tables) | ✅ | CSV tools (Week 4) + `search_policy` tool `src/tools/knowledge.py` line 19 | |
| Week 3 report | ✅ | `docs/weekly-reports/week3-report.md` | + trail + AI log |

### A2. What our RAG "context window" contains

Every RAG answer is ONE model call made of two parts:

| Part | Content | Size (question RA-01) |
|:---|:---|:---|
| **System instruction** | The text between `BEGIN/END SYSTEM PROMPT` in `prompts/policy_qa_v1.0.0.md` (6 rules) | 147 words |
| **User message** | `[SOURCES]` block with up to 6 labelled passages (top 3 by BM25 score + the section after each), then `[QUESTION]` | 284 words, 6 sources |

Built in `src/rag/policy_qa.py`:
- line 51 `retrieve()` — chooses the passages (top 3 above `MIN_SCORE` 2.0, plus neighbours)
- line 106 — formats each one as `[S#] (chunk_id | document title - section)` + passage text
- line 109 — joins them as `"[SOURCES]\n" + context + "\n\n[QUESTION]\n" + question`

The real message for RA-01 (*"Who can approve a requisition of UGX 800,000?"*):

```text
[SOURCES]
[S1] (POL-01#approval-thresholds | Procurement Policy - Approval thresholds)
Every requisition needs human approval before any order is placed. - Up to UGX 500,000: the shop
supervisor or the owner may approve. - Above UGX 500,000 and up to UGX 2,000,000: only the owner may
approve. - Above UGX 2,000,000: only the owner may approve, and a written justification must be
attached. Nobody may approve a requisition they created themselves.

[S2] (POL-01#quotations | Procurement Policy - Quotations)            <- next section after S1
For any item costing more than UGX 100,000 in one requisition, compare at least two written supplier
quotations. ...

[S3] (FAQ-01#can-the-ai-assistant-approve-an-order-if-the-owner-is-away | Procurement FAQ - ...)
No. Approval always needs a person with approval authority. If the owner is away, the supervisor may
approve requisitions up to UGX 500,000; larger ones wait for the owner.

[S4] (FAQ-01#what-happens-to-items-that-do-not-fit-the-weekly-budget | ...)   <- next section after S3
[S5] (PRC-01#step-4-approve-or-reject | Requisition and Approval Process - Step 4: Approve or reject)
[S6] (PRC-01#step-5-order-and-pay | ...)                                      <- next section after S5

[QUESTION]
Who can approve a requisition of UGX 800,000?
```
Scores: S1 7.60, S3 5.96, S5 4.32 (S2, S4, S6 are neighbours, no score). Answer given: *"only the owner
may approve it [S1]"*. Every run's retrieved IDs and scores are logged in `evidence/week3/rag_traces.jsonl`.

What is **not** in the context: no CSV data, no conversation history, no other user's questions, no
documents outside `knowledge/corpus/`.

When the agent uses RAG instead (`search_policy` tool), the passages arrive as a tool result inside the
agent's conversation (see B4), with `source_id` instead of `[S#]`.

### A3. The 15 test questions (`tests/test_week3_rag.py` lines 47–74)

| ID | Type | Question | Correct section | Must contain |
|:---|:---|:---|:---|:---|
| RA-01 | answerable | Who can approve a requisition of UGX 800,000? | POL-01#approval-thresholds | owner |
| RA-02 | answerable | What is the minimum order quantity at Nakawa Stationers? | SUP-02#ordering-and-minimum-order | 10 |
| RA-03 | answerable | How long do we keep requisition records? | FAQ-01#how-long-do-we-keep-requisition-records | five years |
| RA-04 | answerable | Can staff pay a supplier by mobile money? | POL-02#who-pays-suppliers | owner |
| RA-05 | answerable | What should staff do when a sales rep pushes a today-only discount? | GDE-01#what-staff-should-do | written quotation |
| RP-01 | partial | What is Entebbe Traders' delivery fee and on which days do they deliver? | SUP-03#delivery | Tuesday + "documents do not say" |
| RP-02 | partial | What is our weekly restock budget this week and how is it set? | POL-02#weekly-restock-budget | 300,000/owner + missing part |
| RP-03 | partial | How many days does Kampala Office Supplies take to deliver, and what discount do they give for bulk orders? | SUP-01#delivery | 3 days + missing part |
| RP-04 | partial | Who approves requisitions above UGX 2,000,000 and how much did we spend on approved requisitions last year? | POL-01#approval-thresholds | owner + missing part |
| RP-05 | partial | When are reorder points raised for school terms, and by how much for calculators? | PRC-02#school-terms-and-seasons | term timing + missing part |
| RU-01 | unanswerable | What is the phone number of the Kampala Office Supplies manager? | — | refusal |
| RU-02 | unanswerable | What is the VAT rate on stationery in Uganda? | — | refusal |
| RU-03 | unanswerable | What prices does our competitor across the road charge? | — | refusal |
| RU-04 | unanswerable | How much is the shop assistant's monthly salary? | — | refusal |
| RU-05 | unanswerable | Will it rain in Kampala tomorrow? | — | refusal |

How they are judged: `run_offline()` line 81 (retrieval: hit@3, context hit, rank/MRR), `judge()` line 121
(answers), `run_live()` line 138. Partial answers must match `MISSING` (line 44): "documents do not say/mention…".

### A4. Week 3 results and documentation

| What | File |
|:---|:---|
| Retrieval before fixes (hit@3 9/10, MRR 0.85) | `evidence/week3/retrieval_results_index_v1.0.0.md` |
| Retrieval after fixes (hit@3 10/10, MRR 0.88) | `evidence/week3/retrieval_results_index_v1.1.0.md` |
| Answers run 1 (13/15) and run 2 (15/15) | `evidence/week3/answer_results_run1.md`, `answer_results.md` (+ `.json`) |
| Every retrieval + answer | `evidence/week3/rag_traces.jsonl` |
| Evaluation + failure catalogue R-1…R-5 | `docs/evaluation/week3-rag-evaluation.md` |
| Architecture | `docs/architecture/architecture-week3-rag.md` |
| Report, trail, AI log | `docs/weekly-reports/week3-report.md`, `week3-engineering-trail.md`, `week3-ai-log.md` |
| Plain-language explanation | `docs/notes/rag-explained.md` |

---

## Part B — Week 5: Bounded agent

### B1. Did we do everything the course (and DeepSeek's lesson) describes?

| Item | Done? | Where | Note |
|:---|:---:|:---|:---|
| Written Agent Task Contract | ✅ | `docs/requirements/agent-task-contract.md` (sections 1–10) | goal, tools, state, limits, stop conditions, hand-off |
| Genuinely multi-step task | ✅ | weekly restock within a budget — `src/restock_agent.py` `run_restock()` line 208 | |
| Budget re-planning | ✅ **better than the lesson** | `plan_within_budget()` `src/tools/procurement.py` line 446 | The lesson has the model drop items until the total fits; ours has **Python** decide (urgency sort line 503, deferral line 512) because budget maths must be exact (F-04 lesson). The model decides *when* to plan, retry, draft or stop. |
| Sense → Plan → Act → Observe → Re-plan → Stop | ✅ | `run_restock()` phases marked at lines 214, 226, 240, 251, 256; `AgentState.observe()` line 109 | |
| Max turns / max tool calls | ✅ | restock: `MAX_TURNS` 5, `MAX_TOOL_CALLS` 6 (lines 74–75); question agent: 6 / 12 (`tool_agent.py` lines 82–83) | lesson said 6/12 |
| Approved tools | ✅ | `CONTRACT_TOOLS` line 73; enforced `NOT_IN_TASK_CONTRACT` `tool_agent.py` line 236 | |
| Stop conditions | ✅ | outcome decided by code, lines 256–266 | DRAFT_READY, NOTHING_FITS_BUDGET, NOTHING_TO_DO, PRECONDITION_FAILED, POSTCONDITION_FAILED, HANDOFF_* |
| Hand-off conditions | ✅ | `_handoffs()` line 189 | needs-human items, deferred items, over-cap lines, approval step |
| ≥ 3 traces incl. failure/recovery | ✅ 4 | `evidence/week5/trace_T1…T4.md` | see B3 |
| Iteration-limit test | ✅ | `test_offline_08_looping_model_bounded` (`tests/test_week5_agent.py` line 250) | |
| Tool-limit test | ✅ (added 2026-10-13) | `test_offline_17_tool_call_limit` | limit code: `tool_agent.py` line 240 |
| Hand-off test | ✅ | A-02 (hand-off list), A-05 (nothing fits), A-10 (model unavailable), A-12/13 (stop before model); MVP M-03 (asks a clarifying question) | |
| Pre/post-conditions | ✅ (beyond the lesson) | `check_postconditions()` line 165 | |
| Agent architecture diagram | ✅ | `docs/architecture/architecture-week5.md` | state machine |
| Week 5 report | ✅ | `docs/weekly-reports/week5-report.md` | + trail + AI log |

### B2. The Agent Task Contract

`docs/requirements/agent-task-contract.md`: 1 Goal (line 11) · 2 Inputs and preconditions (21) · 3 Approved
tools (31) · 4 State (42) · 5 The loop (57) · 6 Limits (69) · 7 Post-conditions (80) · 8 Stop conditions and
outcomes (98) · 9 Human approval and hand-off (112) · 10 What the agent may never do (121).
The model-facing part of the contract is Section 7 "Weekly Restock Task" of
`prompts/procurement_assistant_v2.4.0.md` (line 136).

### B3. The four execution traces (`tests/test_week5_agent.py` `LIVE_TRACES` lines 357–369)

| Trace | Budget | Shows | Outcome | File |
|:---|:---:|:---|:---|:---|
| T1 happy path | 2,000,000 | plan → draft 6 priced items (UGX 1,619,289); 4 no-history items handed off | DRAFT_READY | `evidence/week5/trace_T1_happy_path.md` |
| T2 budget re-plan | 300,000 | over budget → keep 4 most urgent (UGX 294,130), defer Staplers + Printing Paper | DRAFT_READY | `trace_T2_budget_replan.md` |
| T3 failure + recovery | 300,000 | `plan_within_budget` fails (injected `SERVICE_UNAVAILABLE`, `registry.inject_fault` line 200) → one retry → RECOVERED → draft | DRAFT_READY | `trace_T3_failure_recovery.md` |
| T4 safe stop | 10,000 | nothing fits → contract says do not draft → explains | NOTHING_FITS_BUDGET | `trace_T4_safe_stop.md` |

Earlier runs on older prompts are kept in `evidence/week5/runs_prompt_v2.1.0/` and `runs_prompt_v2.2.0/`.

### B4. What the agent's context window contains (one restock run)

| Part | Content |
|:---|:---|
| System instruction | `prompts/procurement_assistant_v2.5.0.md` between the markers (role of the assistant, tools, hard rules, Section 7) |
| Tool declarations | only the 3 contract tools (`allowed_tools`), as JSON schemas |
| Turn 1 user message | `[RESTOCK TASK]` goal + budget + requested-by + `[SENSE]` JSON of the 10 low items (built in `run_restock()` line 240 onwards) |
| Following turns | the model's tool requests and the **tool results** (plan, draft) appended one by one |

No other user's runs, no CSV text, no RAG documents (`search_policy` is not in this task's contract).

### B5. Offline agent tests (`tests/test_week5_agent.py`) — scripted fake model, no quota

A-01 ideal (line 192) · A-02 hand-offs (202) · A-03 failure → recovery (210) · A-04 two failures → safe stop (219) ·
A-05 nothing fits (227) · A-06 greedy model caught (234) · A-07 double draft caught (243) · A-08 iteration limit (250) ·
A-09 off-contract tool blocked (259) · A-10 model unavailable (267) · A-11 missing approval line (274) ·
A-12 preconditions (280) · A-13 nothing low (289) · A-14 planner rules (301) · A-15 trace phases (315) ·
A-16 false draft claim corrected (323) · A-17 tool-call limit (added 2026-10-13).
The fake model's behaviours: `ideal_policy` (line 99), `greedy_policy` (115), `looping_policy` (141), fixture `fake_model` (161).

### B6. Week 5 results and documentation

| What | File |
|:---|:---|
| Offline results (17/17) | `evidence/week5/offline_results.md` |
| Live trace results (4/4) | `evidence/week5/live_results.md` |
| All runs | `evidence/week5/restock_runs.jsonl` |
| Evaluation + failures F-12…F-15 + regression | `docs/evaluation/week5-agent-evaluation.md` |
| Contract | `docs/requirements/agent-task-contract.md` |
| Architecture | `docs/architecture/architecture-week5.md` |
| Report, trail, AI log | `docs/weekly-reports/week5-report.md`, `week5-engineering-trail.md`, `week5-ai-log.md` |

---

## Part C — Answering DeepSeek's three check questions (suggested points, put them in your own words)

1. **Why is `tool_agent.py` already an agent, and what does Week 5 add?** It chooses its next action from
   what it observes (which tool, whether to call another, when to answer). Week 5 adds a goal that needs
   several dependent decisions, an explicit state, a written contract, code-enforced limits and
   pre/post-conditions, an outcome decided by code, and recorded traces including failure and recovery.
2. **"What's our policy on new suppliers?" in the Week 4 system?** Before Week 3 it had no policy source,
   so the prompt rule made it say the information is not available — or, without that rule, it would
   have invented a plausible policy (hallucination). Now `search_policy` retrieves the actual document
   section and the answer cites it. (Our corpus covers quotations and supplier pressure; a "new supplier"
   rule is not in the documents, so the correct answer is a partial/"not in the documents" reply — a good
   example for the viva.)
3. **Why is correctness the right reason for tools before RAG?** RAG supplies text; it cannot do
   arithmetic. The open defect F-04 was wrong quantities, which only deterministic tools fix, and the
   agent needs correct tools to be trustworthy at all. Breadth (more knowledge) is worth little if the
   numbers are wrong.
