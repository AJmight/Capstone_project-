# BSE4104 AI Agentic Capstone: Week 7 Progress Report
**Topic:** Evaluation, Observability, and Guardrails  
**Student:** Mwesigwa Arnold Mugahi (Reg No: 23/U/24738/PS, GitHub: AJmight)  
**Role:** AI Engineering Lead  
**Dates:** 12th October – 16th October 2026 (Consolidated: 20th October 2026)  
**Convener:** Dr. Kamulegeya Grace B (PhD)  

---

## 1. Executive Summary & Goals
In Week 7, the SME Procurement Preparation Agent underwent comprehensive hardening, empirical evaluation, and safety verification. The focus shifted from feature construction to producing verifiable, scientific evidence that the system operates safely and reliably within its bounded domain. Key outcomes:
1. **31-Scenario Evaluation Dataset:** Designed, implemented, and executed a formal test suite covering normal, edge, corrupted, adversarial, infrastructure-failure, and unauthorized-action cases.
2. **Deterministic Safety Guardrails:** Implemented pre-model input sanitization, financial budget ceiling enforcement (resolving failure mode F-12), and an untransferable Human-in-the-Loop (HITL) approval gate.
3. **Failure Catalogue:** Analyzed the failure modes found across the project (F-01 to F-16 in the weekly records, extended to F-25 by the Week 8 hardening pass) with documented root causes, code fixes, and automated regression test evidence.

---

## 2. Key Accomplishments

### A. 31-Scenario Evaluation Dataset ([`tests/test_week7_evaluations.py`](../../tests/test_week7_evaluations.py))
We structured 31 automated test scenarios across six required categories:
- **Normal Operations (5):** Verified stock sensing, quote sorting, MOQ calculation, budget planning, and session FSM progression.
- **Edge Conditions (6):** Verified zero/negative budget rejection, budget smaller than MOQ handling, multi-billion budget rejection, zero-history item flagging, and blank prompt handling.
- **Corrupted / Missing Data (5):** Verified handling of non-existent item IDs, SQL injection in shop IDs, non-numeric budgets, and empty requisition payloads.
- **Adversarial / Injections (5):** Verified defense against prompt injections, jailbreak auto-approval commands, unauthorized fund disbursements, and cross-shop memory spoofing.
- **Tool / Infrastructure Failures (5):** Verified budget ceiling overrun detection (F-12 fix), missing session handling, closed DB resilience, and illegal state transitions.
- **Unauthorized Actions (5):** Verified that AI calls to approve orders, sign POs, or execute mobile money payments are actively blocked.

### B. Deterministic Guardrails Engine ([`src/guardrails.py`](../../src/guardrails.py))
To avoid relying on LLM good behaviour, we implemented deterministic code guardrails:
- `InputGuardrail`: Scans user prompts for injection and adversarial keywords.
- `BudgetCeilingGuardrail`: Enforces that `draft_total <= allocated_budget` strictly, closing failure mode F-12.
- `HumanInTheLoopGuardrail`: Enforces that high-impact operations (`approve_requisition`, `make_payment`) can only be executed by actor `HUMAN_OWNER`.

### C. Comprehensive Failure Catalogue ([`docs/evaluation/failure-catalogue.md`](../evaluation/failure-catalogue.md))
Compiled an exhaustive audit of the failure modes encountered across the project lifecycle, documenting symptoms, root causes, remediations, and re-test proof. The catalogue was **finalised in the Week 8 hardening pass**: the ids were re-based onto the canonical numbering used by the weekly evaluation documents (F-01…F-16 keep their original meaning, the Week 6–8 findings take F-17…F-25), and three earlier entries that had no supporting evidence were removed rather than kept. See §3.2 of the catalogue for the reasoning.

---

## 3. Empirical Results & Pass Rates

| Category | Total Scenarios | Passed | Failed | Pass Rate |
| :--- | :--- | :--- | :--- | :--- |
| Normal Cases | 5 | 5 | 0 | 100% |
| Edge Cases | 6 | 6 | 0 | 100% |
| Corrupted / Missing Info | 5 | 5 | 0 | 100% |
| Adversarial / Injection | 5 | 5 | 0 | 100% |
| Infrastructure Failures | 5 | 5 | 0 | 100% |
| Unauthorized Actions | 5 | 5 | 0 | 100% |
| **Total** | **31** | **31** | **0** | **100%** |

*Overall test run execution time: 13.99 seconds.*

---

## 4. Engineering Reflections & Next Steps for Week 8
With evaluation and guardrails completed, the system is fully hardened against adversarial inputs and financial overreach. For Week 8 (Final Hardening, Release & Presentations):
1. Review documentation against the 8–12 page Capstone Report brief.
2. Tag the repository release `v1.0.0-final`.
3. Rehearse live demonstration walkthrough (T1–T4 traces + approvals CLI).
