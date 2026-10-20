# Week 7 Engineering Trail: Evaluation, Observability & Guardrails

**Project:** SME Procurement Preparation Agent  
**Author:** Mwesigwa Arnold Mugahi (23/U/24738/PS)  
**Deliverable:** Week 7 Engineering Trail  

---

## 1. Remediation of Failure Mode F-12 (Budget Ceiling Overrun)

### Problem Description
In Week 5, the restock planner permitted a $\pm 10\%$ budget range based on user story 8. However, empirical testing revealed that when a shop owner had a hard bank balance of UGX 300,000, recommending an order of UGX 318,000 caused the SME to overdraw or face bounced supplier mobile money payments.

### Root Cause
The tool logic conflated *planning leeway* with *financial authorization limit*. The agent allowed the draft total to exceed the initial budget if it fell within the $+10\%$ window.

### Solution
We implemented `BudgetCeilingGuardrail` in `src/guardrails.py`:
```python
class BudgetCeilingGuardrail:
    @classmethod
    def verify_draft_within_budget(cls, draft_total_ugx: int, allocated_budget_ugx: int) -> bool:
        if draft_total_ugx > allocated_budget_ugx:
            overage = draft_total_ugx - allocated_budget_ugx
            raise GuardrailViolation("BUDGET_CEILING_EXCEEDED", f"Draft total exceeds budget by UGX {overage:,}")
        return True
```
This is verified in `test_scen_22` of `tests/test_week7_evaluations.py`.

---

## 2. Designing the 31-Scenario Benchmark

To move from "vibe coding" to formal software engineering, we constructed a test matrix asserting quantifiable criteria:
- **Normal (5):** Baseline functional correctness across stock sensing, quote sorting, and reorder math.
- **Edge (6):** Boundary values ($0$, negative numbers, budgets below any MOQ, massive budgets).
- **Corrupted Data (5):** Resilient degradation when data files or arguments contain invalid values.
- **Adversarial (5):** Jailbreaks, prompt injections, and cross-tenant memory snooping.
- **Tool Failures (5):** Database disconnects, missing sessions, and FSM transition violations.
- **Unauthorized Actions (5):** Direct verification that the AI cannot approve, sign, or pay for purchase requisitions.

All 31 scenarios run in 13.99 seconds with zero external dependencies.

---

## 3. Human-in-the-Loop (HITL) Gatekeeper

In `HumanInTheLoopGuardrail`, we established an explicit boundary separating AI recommendation privileges from human execution privileges:
- AI privileges: Query inventory, rank quotes, estimate reorder points, prepare drafts.
- Human privileges: Edit draft quantities, approve draft, reject draft, execute external payments.

Any tool call attempting to bypass this boundary triggers `GuardrailViolation('UNAUTHORIZED_AUTONOMY_ATTEMPT')`.
