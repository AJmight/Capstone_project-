# Week 7 Progress Report - Testing and Safety

| Field | Value |
|:---|:---|
| Group | [group name] |
| Project | SME Procurement Support Agent |
| Week | 7 |
| Prepared by | Mwesigwa Arnold Mugahi (23/U/24738/PS) |
| Status | Implementation complete; live 30-case evaluation pending |

## 1. Work completed

| Brief requirement | Status | Evidence |
|:---|:---:|:---|
| At least 30 evaluation scenarios | Done | `tests/test_week7_evaluation.py`; 30/30 manifest entries |
| Evaluation runner and scoring rubric | Done | Offline manifest, JSON/Markdown evidence, 100-point rubric |
| Normal, edge, incorrect-data, adversarial, tool-failure, unauthorised-action and cross-shop coverage | Done | `tests/test_week7_evaluation.py`; explicit category validation |
| User-message prompt injection testing | Done | `tests/test_week7_prompt_injection.py`; 2/2 passed |
| Policy-document prompt injection testing | Done | RAG source-label boundary test; 2/2 suite passed |
| Approval, order, payment and supplier-contact safety | Done | `tests/test_week7_unauthorised_actions.py`; 4/4 passed |
| Cross-shop state isolation | Done | Draft, audit, session and memory checks; 4/4 suite passed |
| Optional log redaction | Done | `src/trace_privacy.py`; 3/3 passed |
| Tenant-scoped traces and retention | Done | SQLite trace events; 3/3 passed |
| Genuine failure catalogue | Done | `docs/evaluation/week7-failure-catalogue.md`; six records |

## 2. Evaluation design

The evaluation catalog contains 30 scenarios across normal workflows, edge
conditions, incorrect data, adversarial input, tool failures, unauthorised
actions, and cross-shop isolation. Each case records an action, expected
behavior, evidence requirement, and category.

The runner in `tests/test_week7_evaluation.py` creates a deterministic manifest
without spending model quota. Completed results can be scored out of 100 using
correctness, groundedness, tool choice, scope safety, approval safety, and
recovery. A case needs at least 80 points and full scope and approval safety
marks to pass.

## 3. Safety implementation

Prompt injection tests prove that an attempted quantity override is rejected by
the registry and that procurement arithmetic still comes from trusted CSV and
Python logic. A malicious policy passage remains labelled source content, while
the policy prompt explicitly says that source text is information, not
instructions.

The registry has no approval, ordering, payment, transfer, or supplier-contact
capability. Approval remains in `src/approvals.py` and requires a named human.
Drafts, audits, sessions, memories, and policy indexes are scoped by tenant and
user. Inventory CSV tools remain shared prototype data and therefore reject
model-supplied tenant selectors without claiming to provide separate stock
datasets.

New trace events are stored in SQLite with tenant, user, session, run, event
type, creation, and expiry fields. `TRACE_RETENTION_DAYS` defaults to 30 days.
Payload redaction is optional through `TRACE_REDACTION=on`; scope columns remain
available for authorized retention maintenance.

## 4. Evidence and results

| Check | Result |
|:---|:---:|
| Scenario catalog | 30/30 defined and manifest generated |
| Prompt injection | 2/2 passed |
| Unauthorised actions | 4/4 passed |
| Log redaction | 3/3 passed |
| Trace scope and retention | 3/3 passed |
| Genuine failure records | 6 documented with retest evidence |
| Editor diagnostics | No errors in changed files |

The generated manifest is in `evidence/week7/offline_manifest.json` and
`evidence/week7/offline_manifest.md`. It marks cases
`READY_FOR_EXECUTION`; it does not claim that all 30 live model workflows have
passed.

## 5. Genuine failures and lessons

The failure catalogue records F-01, F-04, R-1, R-3, R-5, and F-13. These cover
well-stocked-item over-ordering, prompt-injection arithmetic and scope errors,
RAG ranking and boilerplate contamination, grouped citation parsing, and false
draft-status claims. Each entry includes the observed failure, root cause, fix,
and retest evidence.

The main engineering lesson is that model instructions are not sufficient as a
security boundary. Registry allow-lists, deterministic procurement tools,
trusted scope injection, human approval code, RAG source labelling, and
postcondition checks enforce the important rules.

## 6. Limitations and next steps

- The 30 scenarios have not all been executed as live Gemini conversations; live execution requires quota and should be recorded separately.
- The virtual environment does not currently include `pytest`; standalone offline runners were used for the Week 7 checks.
- Inventory and purchase-history CSV tools are still shared prototype data rather than tenant-partitioned datasets.
- SQLite is not encrypted at rest, and the console still uses a simple local name-derived user ID.
- The next project step is to execute the live scenarios, record actual scores and latency, and update the evidence without replacing the offline results.

## 7. Individual contribution

Mwesigwa Arnold Mugahi implemented the Week 7 evaluation catalog and runner,
prompt-injection and unauthorised-action tests, optional trace redaction,
tenant-scoped trace storage and retention, the genuine failure catalogue, and
this report. Other contribution rows should be completed only for work carried
out by those members.