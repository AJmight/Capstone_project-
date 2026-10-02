# Prompt Version History — SME Procurement Assistant

Current prompt: `prompts/procurement_assistant_v1.2.0.md` (loaded by `src/ai_engine.py`).
Older versions are kept unchanged in `prompts/archive/`.

| Version | File | Evaluation |
|:---:|:---|:---|
| 1.0.0 | `archive/procurement_assistant_v1.0.0_draft.md` | Not run (failed review: see below) |
| 1.1.0 | `archive/procurement_assistant_v1.1.0.md` | 7/10 — `evidence/week2/evaluation_v1.1.0.md` |
| 1.2.0 | `procurement_assistant_v1.2.0.md` | 10/10, then 9/10 after TC-08 checker was tightened — `docs/evaluation/week2-prompt-evaluation.md` |

---

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
