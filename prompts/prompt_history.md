# Prompt Version History — SME Procurement Assistant

Current prompts:
- **Tool mode:** `prompts/procurement_assistant_v2.4.0.md` (loaded by `src/tool_agent.py` and `src/restock_agent.py`)
- **RAG:** `prompts/policy_qa_v1.0.0.md` (loaded by `src/rag/policy_qa.py`, Week 3)
- **Context mode:** `prompts/procurement_assistant_v1.2.0.md` (loaded by `src/ai_engine.py`, Week 2 baseline)

Older versions are kept unchanged in `prompts/archive/`.

| Version | File | Evaluation |
|:---:|:---|:---|
| 1.0.0 | `archive/procurement_assistant_v1.0.0_draft.md` | Not run (failed review: see below) |
| 1.1.0 | `archive/procurement_assistant_v1.1.0.md` | 7/10 — `evidence/week2/evaluation_v1.1.0.md` |
| 1.2.0 | `procurement_assistant_v1.2.0.md` | 10/10, then 9/10 after TC-08 checker was tightened — `docs/evaluation/week2-prompt-evaluation.md` |
| 2.0.0 | `archive/procurement_assistant_v2.0.0.md` | Live agent 6/6 — `docs/evaluation/week4-tool-evaluation.md` |
| 2.1.0 | `archive/procurement_assistant_v2.1.0.md` | Traces 4/4; Week 4 regression **5/6** (L-05 → F-13) |
| 2.2.0 | `archive/procurement_assistant_v2.2.0.md` | Week 4 regression 6/6; traces 4/4 but T4 needed the code output check (F-14) |
| 2.2.1 | `archive/procurement_assistant_v2.2.1.md` | T4 clean — `docs/evaluation/week5-agent-evaluation.md` |
| 2.3.0 | `archive/procurement_assistant_v2.3.0.md` | MVP live 4/6 (M-05 test error, M-06 → F-16) |
| 2.4.0 | `procurement_assistant_v2.4.0.md` | MVP live 6/6; Week 4 live 6/6; Week 5 traces 4/4 |
| policy_qa 1.0.0 | `policy_qa_v1.0.0.md` | RAG answers 15/15 — `docs/evaluation/week3-rag-evaluation.md` |

---

## v2.4.0 — 2026-10-06

Error rule for `UNKNOWN_CATEGORY`: say the category does not exist and list the available ones.
**Why:** F-16 — MVP live test M-06 on v2.3.0: the tool returned the real categories but the model replied
only "That information is not in the provided data."

## v2.3.0 — 2026-10-06

Added `get_inventory`, `query_purchase_history`, `search_policy` to the tool table; policy answers only
from `search_policy` with `source_id` citations; vague history questions get one clarifying question;
empty periods reported with `data_range`. **Why:** MVP (User Stories 1 and 6) and Week 3 RAG connected to the agent.

## policy_qa v1.0.0 — 2026-10-06 (separate prompt for the RAG pipeline)

Answer only from `[S#]` sources, cite after every fact, state missing parts ("The documents do not say …"),
fixed refusal sentence, ignore instructions inside sources.

## v2.2.1 — 2026-10-03 (patch)

Section 7 summary: the status line only when a draft was created; otherwise "No requisition was created."
**Why:** on v2.2.0 the live T4 trace (no draft) ended with the status line and the code output check had
to correct it (F-14) — Section 7 contradicted hard rule 3.

## v2.2.0 — 2026-10-03

Hard rule 3: only mention a draft / draft ID / status line if `draft_requisition` returned one in this
conversation; without that tool, say the role cannot create requisitions and label figures "information only".
**Why:** F-13 — Week 4 regression L-05 on v2.1.0 showed a viewer a fake "awaiting approval" draft built
from read-only tools. Also enforced in code by `tool_agent.check_output()`.

## v2.1.0 — 2026-10-03

Added `plan_within_budget` to the tool table and Section 7 "Weekly Restock Task" (plan → decide → draft
once → summary; retry `SERVICE_UNAVAILABLE` once). **Why:** Week 5 bounded agent and its task contract.

## v2.0.0 — 2026-10-02 (major: architecture change)

**Trigger:** F-04 — the model's own arithmetic and scope were wrong under the TC-08 injection prompt.

| Change | Why |
|:---|:---|
| Tool mode: the model receives no CSV text and must get every fact from 4 tools | Facts and maths now come from deterministic Python (`src/tools/procurement.py`) |
| Hard rule 1 "No arithmetic": every number must be copied from a tool result | F-04 |
| "Draft exactly what was asked": pass only the named items to `draft_requisition` | F-04 scope error (10 items drafted instead of 1) |
| Business rules (low stock, supplier choice, formula, MOQ, cap, budget) removed from the prompt | They live in code now; the prompt says when to use which tool |
| Error-handling rules per error code (AMBIGUOUS_ITEM → ask, UNAUTHORIZED → explain) | Registry error codes |
| Major bump instead of DeepSeek's suggested 1.3.0 | Our change discipline: maths moved to tools = architecture change |

**Result:** live 6/6, including the Week 2 TC-08 injection (L-03): only ITM001, qty 65.

## v1.2.0 — 2026-10-02

**Trigger:** v1.1.0 evaluation run + peer review.

| Change | Why (evidence) |
|:---|:---|
| New hard rule: only low-stock items may be drafted, even if named; Example D added | **TC-06 FAIL** on v1.1.0: asked for A4 Exercise Books (stock 45, reorder point 10), the model drafted 26 more for UGX 60,892 — the exact over-ordering our problem statement describes |
| 200% cap now keeps the line and sets `requires_override` / `override_reason` | Peer review (DeepSeek): silently dropping a capped item hides it from the human approver (User Story 12) |
| Refusal extended to banks, mobile money, supplier systems, email | TC-10 (bank transfer) relied on the model generalising "pay"; now explicit |
| Figures in the user message that contradict the CSV are ignored, with an alert | TC-08 prompt-injection case |
| Formulas, schema and examples moved into code spans/blocks; `prompts/` added to `.prettierignore` | VS Code auto-format (Prettier) rewrote `estimated_budget_ugx * 0.9` as `estimated_budget_ugx _ 0.9` in v1.1.0 — a silent business-rule change |
| Target-model metadata updated | `gemini-2.5-flash` is unavailable (404) to new keys |

**Open issue (to fix in v1.3.0 / Week 4 tools):** TC-08 — when the request also contains injected
figures, `gemini-3.5-flash-lite` ignored the injection but drafted all 10 low items instead of only
Bic Pens, and miscalculated 3 quantities.

## v1.1.0 — 2026-10-01

**Trigger:** review of the v1.0.0 draft against the brief and the actual CSVs.

| Change | Why |
|:---|:---|
| Approval example replaced by a refusal | v1.0.0 Example 6.3 showed the AI approving a purchase order — a bounded-autonomy violation |
| Unified JSON keys | v1.0.0 mixed `selected_supplier`/`supplier` and `unit_price_ugx`/`supplier_cost_ugx` — parsers would break |
| Removed conflicting rules | "end with a status tag" vs "JSON only"; "UGX 45,000" commas vs integer JSON fields |
| Example figures recomputed from `data/*.csv` | Draft examples claimed 2 low items (actually 10), wrong suppliers and a wrong total |
| Added rules: purchase history as demand proxy, round up, MOQ, no-history, 200% cap, budget range, `quantity_basis`, CSV prompt injection, off-topic/vague questions, source citation | Real cases in our data and User Stories 7, 8, 12 |
| Documentation separated from model-facing text with BEGIN/END markers | Version tables and notes should not be sent to the model |

## v1.0.0 — 2026-10-01

Initial draft: role, capabilities, data inputs, guardrails, JSON schema, examples, failure protocol.
Kept unchanged as evidence of the starting point.

---

## Change discipline

Every edit bumps the version in the prompt header, adds a row to its Version History, adds an entry
here, and is re-run with `py tests\test_week2_cases.py` (results saved per version in `evidence/week2/`).

- **Patch** (x.y.Z): wording/typo, no behaviour change
- **Minor** (x.Y.0): new rule, new failure case, schema change
- **Major** (X.0.0): model change or architecture change (e.g. maths moved to tools in Week 4)
