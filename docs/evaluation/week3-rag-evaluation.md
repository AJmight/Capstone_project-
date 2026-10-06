# Week 3 RAG Evaluation (15 questions)

**Runner:** `tests/test_week3_rag.py` · **Date:** 2026-10-06
**Evidence:** `evidence/week3/retrieval_results_index_v1.0.0.md`, `retrieval_results_index_v1.1.0.md`,
`answer_results_run1.md/.json`, `answer_results.md/.json`, `rag_traces.jsonl`

## Summary

| Run | What changed | Retrieval (offline) | Answers (live) |
|:---|:---|:---|:---|
| Index v1.0.0 | baseline | hit@3 **9/10**, context hit 10/10, MRR 0.85 | — |
| Index v1.1.0 | stemmer fix (R-1), disclaimer chunks removed (R-3) | hit@3 **10/10**, context hit 10/10, MRR 0.88 | run 1: **13/15** |
| Index v1.1.0 + checker/test fixes | citation parser fix (R-5, product code); RP-05 expectation corrected (test error) | unchanged | run 2: **15/15** |

hit@3 = the section containing the answer is among the top 3 results; context hit = it is in what the
model actually receives (top 3 + next section); MRR = mean of 1/rank (1.0 = always first). Unanswerable
questions have no correct section, so they are judged only on the answer.

## The 15 questions and results (run 2)

| ID | Type | Question | Answer chunk | Rank (v1.1) | Result |
|:---|:---|:---|:---|:---:|:---:|
| RA-01 | answerable | Who can approve a requisition of UGX 800,000? | POL-01#approval-thresholds | 1 | PASS — "only the owner" |
| RA-02 | answerable | Minimum order quantity at Nakawa Stationers? | SUP-02#ordering-and-minimum-order | 1 | PASS — 10 |
| RA-03 | answerable | How long do we keep requisition records? | FAQ-01#how-long… | 1 | PASS — five years (run 1 FAIL: R-5) |
| RA-04 | answerable | Can staff pay a supplier by mobile money? | POL-02#who-pays-suppliers | 1 | PASS — only the owner |
| RA-05 | answerable | What should staff do when a sales rep pushes a today-only discount? | GDE-01#what-staff-should-do | 3 | PASS (thanks to next-section expansion) |
| RP-01 | partial | Entebbe Traders' delivery fee and delivery days? | SUP-03#delivery | 1 | PASS — Tue/Fri; fee not stated |
| RP-02 | partial | This week's restock budget and how it is set? | POL-02#weekly-restock-budget | 1 | PASS — owner sets 300k–600k; this week's not stated |
| RP-03 | partial | Kampala Office Supplies delivery days and bulk discount? | SUP-01#delivery | 2 (v1.0: 5) | PASS — 3 days; discount not stated |
| RP-04 | partial | Who approves > UGX 2,000,000 and last year's spend? | POL-01#approval-thresholds | 1 | PASS — owner + justification; spend not stated |
| RP-05 | partial | When are reorder points raised for school terms, and by how much for calculators? | PRC-02#school-terms-and-seasons | 1 | PASS — term dates; calculators not covered (run 1 "FAIL" was a test error) |
| RU-01 | unanswerable | Phone number of the Kampala Office Supplies manager? | — | — | PASS — refused |
| RU-02 | unanswerable | VAT rate on stationery in Uganda? | — | — | PASS — refused |
| RU-03 | unanswerable | Competitor's prices? | — | — | PASS — refused |
| RU-04 | unanswerable | Shop assistant's monthly salary? | — | — | PASS — refused |
| RU-05 | unanswerable | Will it rain in Kampala tomorrow? | — | — | PASS — refused |

All unanswerable questions still retrieved *some* chunk above the minimum score (keyword overlap such as
"Kampala"), so the refusals came from the model following the prompt, not from the score gate. The gate
remains a cheap first defence for completely off-topic questions.

## Retrieval / grounding failure catalogue (brief: at least three)

| ID | Failure | Evidence | Root cause | Fix | Status |
|:---:|:---|:---|:---|:---|:---|
| R-1 | "How many days does Kampala Office Supplies take to **deliver**…" ranked the Delivery section 5th (miss) | `retrieval_results_index_v1.0.0.md` RP-03 | Stemmer kept "deliver" and "delivery" as different words | Strip "y"/"ies" (index v1.1.0) | **Fixed** — rank 2 |
| R-2 | "Sales rep pushes a today-only discount" → top hit "The problem"; the advice is in "What staff should do" (rank 3, score 2.54, just above the 2.0 gate) | RA-05 both versions | Section chunking separates the question's vocabulary from the answer | Next-section expansion in `policy_qa.retrieve()` | **Mitigated** — always in context |
| R-3 | Disclaimer lines ("Synthetic, team-created document… Kampala") became "Introduction" chunks retrieved for unrelated questions | v1.0.0 RU-01/02/04 top results | Boilerplate indexed as content | Skip disclaimer-only introductions (v1.1.0); provenance kept in the source register | **Fixed** (73 → 61 chunks) |
| R-4 | Short agent-style query "who approves 800,000" returns PRC-01 Step 4 instead of the thresholds section | manual check, 2026-10-06 | Keyword search cannot reason that 800,000 lies between 500,000 and 2,000,000 | Ideas: `approval_threshold(amount)` structured tool; query rewriting; embeddings | **Open** — full-sentence questions work (RA-01, M-04) |
| R-5 | A correct answer citing "[S1, S3]" was flagged as uncited | `answer_results_run1.md` RA-03 | Citation parser recognised only "[S1]" form | Parse grouped citations | **Fixed** (product code `check_citations`) |

Test-design error (not a system failure): RP-05 run 1 expected "30%", but the 30% rise does not apply to
calculators; the model correctly said the documents do not cover calculators. Expectation corrected and
documented in the test file.

## Limitations

- 15 questions on a 12-document corpus is a small evaluation; Week 7 should add synonym and numeric cases.
- Keyword checks for answers are brittle (third test-design error this project); a rubric or LLM-judge
  with human spot checks is planned for Week 7.
