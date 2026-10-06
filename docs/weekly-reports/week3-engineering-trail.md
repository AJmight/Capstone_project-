# Week 3 Engineering Trail — what was done, in order, and why

**Author:** Mwesigwa Arnold Mugahi (23/U/244738/PS), AI Engineering Lead, with Claude Code as coding partner
**Date:** 2026-10-06 · **Starting point:** commit `4458893` (tag `week5-complete`)
**Note:** Week 3 was built after Weeks 4–5 (team decision). It was built in one session together with
the MVP additions; the Lead asked to pause further RAG work to study the concept, so this week is
documented in full detail — start with `docs/notes/rag-explained.md`.

---

## 1. Goal

Make the assistant answer **policy and procedure** questions from the shop's own documents, with
citations, and say "not in the documents" when the answer isn't there.

## 2. Design decisions

| Decision | Why | Alternative rejected |
|:---|:---|:---|
| 12 synthetic documents written by the team | Brief: authorised data, 10–50 docs; safe for the free tier | Real policies (not available / not authorised) |
| Facts that overlap the CSVs must match them | Policy answers and tool answers must never contradict | Independent fictional facts |
| BM25 keyword search in plain Python | No dependency, no quota, deterministic, explainable | Embeddings (quota, harder to explain) — future work |
| Section chunking, readable chunk IDs | One topic per chunk; human-checkable citations | Fixed-size character chunks |
| Score gate before the model | Off-topic questions refused for free | Always call the model |
| Next-section expansion | Found necessary by test RA-05 | Bigger chunks (dilutes relevance) |
| Citation check in code | Model output is untrusted | Trust the model's citations |
| Same search as an agent tool | One knowledge source for both pipelines | Separate copies |

## 3. Step-by-step build log

| # | Step | Files | Check performed |
|:---:|:---|:---|:---|
| 1 | Wrote 12 corpus documents (policies, supplier profiles, processes, guidance, FAQ, data dictionary) | `knowledge/corpus/` | MOQs/lead times match `supplier_quotes.csv` |
| 2 | Wrote ingestion, chunking, tokeniser, BM25 index | `src/rag/index.py` v1.0.0 | 73 chunks, longest 70 words |
| 3 | Defined 15 questions (5 answerable, 5 partial, 5 unanswerable) and explored retrieval | — | Found R-1, R-2, R-3 |
| 4 | Wrote the grounded QA pipeline and its prompt; wrote the `search_policy` tool | `src/rag/policy_qa.py`, `prompts/policy_qa_v1.0.0.md`, `src/tools/knowledge.py` | Registry smoke test — found R-4 |
| 5 | Wrote the evaluation runner (offline retrieval metrics saved per index version; live answers) | `tests/test_week3_rag.py` | — |
| 6 | Baseline retrieval run, index v1.0.0 | `evidence/week3/retrieval_results_index_v1.0.0.md` | hit@3 9/10, MRR 0.85 |
| 7 | Index v1.1.0: stemmer fix (R-1), skip disclaimer chunks (R-3) | `src/rag/index.py` | hit@3 10/10, MRR 0.88, 61 chunks |
| 8 | Live answers run 1 | `evidence/week3/answer_results_run1.*` | 13/15: RA-03 (R-5 parser bug), RP-05 (test error) |
| 9 | Fixed `check_citations` for "[S1, S3]"; corrected RP-05 expectation with a comment explaining why | `src/rag/policy_qa.py` v1.0.1, test file | — |
| 10 | Live answers run 2 | `evidence/week3/answer_results.*` | **15/15** |
| 11 | Connected RAG to the agent (`search_policy` in prompt v2.3.0+) and tested via MVP case M-04 | `prompts/procurement_assistant_v2.4.0.md` | M-04 PASS: cites POL-01 |
| 12 | Wrote source register, plain-language RAG notes, architecture, evaluation, report, AI log, this trail | `knowledge/`, `docs/` | — |

## 4. Reading order for reviewers

1. `docs/notes/rag-explained.md` — the concept, using our project.
2. `knowledge/source-register.md` — what is in the corpus.
3. `src/rag/index.py` — `load_chunks()`, `tokenize()`, `BM25Index.search()`.
4. `src/rag/policy_qa.py` — `retrieve()`, `answer_policy_question()`, `check_citations()`.
5. `prompts/policy_qa_v1.0.0.md` — the generation rules.
6. `docs/evaluation/week3-rag-evaluation.md` — results and failures.

## 5. How to run it yourself

```powershell
py tests\test_week3_rag.py --offline          # retrieval metrics, free
py src\rag\policy_qa.py "Can staff pay a supplier by mobile money?"
py src\rag\policy_qa.py "What is the VAT rate on stationery?"     # should refuse
py tests\test_week3_rag.py --live             # 15 answers, up to 15 model requests
type evidence\week3\rag_traces.jsonl          # what was retrieved for every question
```

## 6. Concepts covered

RAG; corpus and provenance; chunking; keyword (BM25) vs. semantic (embedding) retrieval; top-k; score
thresholds; context construction with labelled sources; grounding; citations and citation checking;
partial answers; refusing unanswerable questions; retrieval metrics (hit@k, MRR); hybrid knowledge
(tools for records, RAG for rules).

## 7. Open items

R-4 (numeric ranges); embedding search as an experiment; more synonym/numeric test questions in Week 7.
