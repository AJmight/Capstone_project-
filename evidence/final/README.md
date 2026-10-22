# Final evidence pack — index

**Project:** SME Procurement Preparation Agent (BSE4104 capstone)
**Release:** `v1.0.0` · **Assembled:** 20 October 2026, Week 8

Everything a marker needs to check the project's claims without trusting the
narrative, in one folder. Start with the one-page summary, then open whichever
claim you want to test.

| File | What it is | Read it when |
|:---|:---|:---|
| [`evaluation_summary.md`](evaluation_summary.md) | The one-page result summary: every suite, every figure, every safety claim with the test that proves it | First. This is the page to read. |
| [`regression_run_2026-10-20.md`](regression_run_2026-10-20.md) | The **verbatim** output of the final offline regression, all seven suites, as it ran on the release commit | You want to see the raw output rather than a summary of it |
| [`failure_catalogue_final.md`](failure_catalogue_final.md) | The 25 documented failures in one table, with the test that proves each fix | You want to know what went wrong and what was done about it |
| [`git_history.txt`](git_history.txt) | `git log --oneline --all --graph --decorate` at the release | You want to see the development progression |
| [`git_tags.txt`](git_tags.txt) | The release tags, one per completed week | You want to see which week produced what |
| `traces/tool_traces_sample.jsonl` | 10 real tool calls from `evidence/week4/tool_traces.jsonl` (run id, args, status, latency, result) | You want to see what the agent actually called |
| `traces/llm_calls_sample.jsonl` | 10 real model calls from `evidence/traces/llm_calls.jsonl` (model, round, latency, outcome) | You want to see the model layer |
| `traces/agent_traces_sample.jsonl` | The last 3 weekly restock runs (state, loop, outcome, limits) | You want to see the bounded agent's reasoning |
| `traces/rag_traces_sample.jsonl` | 10 real retrieval traces (query, scores, chunks, answer) | You want to see the grounded answers |

## The rest of the evidence lives where the week produced it

| Week | Evidence | Result document |
|:---:|:---|:---|
| 2 | `evidence/week2/evaluation_v1.*.json` (raw model outputs) | `docs/evaluation/week2-prompt-evaluation.md` |
| 3 | `evidence/week3/answer_results*.json`, `rag_traces.jsonl` | `docs/evaluation/week3-rag-evaluation.md` |
| 4 | `evidence/week4/tool_traces.jsonl`, `agent_traces.jsonl`, `live_results.*` | `docs/evaluation/week4-tool-evaluation.md` |
| 5 | `evidence/week5/trace_T1…T4.md` (readable agent traces) | `docs/evaluation/week5-agent-evaluation.md` |
| 6 | `tests/test_week6_state_memory.py` (9 tests) | `docs/architecture/state-and-memory-model.md` |
| 7 | `tests/test_week7_evaluations.py` (31 scenarios) | `docs/evaluation/week7-evaluation-dataset.md` |
| 8 | `tests/test_week8_release_checks.py` (19 tests) | `docs/weekly-reports/week8-report.md` |
| all | `data/drafts/audit_log.jsonl` — every human decision | `docs/evaluation/failure-catalogue.md` |

## Reproducing the offline regression

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
py tests\test_week3_rag.py --offline
py tests\test_week4_tools.py --offline
py tests\test_week5_agent.py --offline
py tests\test_mvp_tools.py --offline
py tests\test_week6_state_memory.py
py tests\test_week7_evaluations.py
py tests\test_week8_release_checks.py
```

No API key and no network are needed: 105 of 105 assertions, zero model calls.

**Or rebuild this whole pack in one command** (it re-runs the seven suites, writes
`regression_run_2026-10-20.md` with their verbatim output, re-samples the traces and
refreshes the git history):

```powershell
py scripts\build_evidence_final.py
```

## A note on the live results

The live results in `evidence/` were recorded on the days shown in each file, with
the prompt version named in that file's header. They were **not** re-run in Week 8,
because the free tier allows 20 requests per model per day and the Week 8 changes
are all in the deterministic layer. The live evidence therefore dates from the
weeks that produced it, and each file says which prompt version it belongs to.
