# Week 3 Progress Report — Context Engineering and RAG

| Field | Value |
|:---|:---|
| **Group** | [group name] |
| **Project** | SME Procurement Support Agent |
| **Week** | 3 (completed 6 Oct 2026, after Weeks 4–5 by team decision) |
| **Prepared by** | [Project/Requirements Lead] |
| **Repository** | https://github.com/AJmight/Capstone_project- (tag `week3-complete`) |

## 1. Work completed against the Week 3 objectives

| Brief requirement | Status | Evidence |
|:---|:---:|:---|
| Controlled corpus (10–50 documents) with provenance | Done (12) | `knowledge/corpus/`, `knowledge/source-register.md` |
| Ingestion, chunking, indexing, retrieval | Done | `src/rag/index.py` (BM25) |
| Context built from retrieved evidence, sources shown | Done | `src/rag/policy_qa.py`, `prompts/policy_qa_v1.0.0.md` |
| ≥ 15 RAG questions: answerable, partial, unanswerable | Done (5/5/5) | `tests/test_week3_rag.py` |
| ≥ 3 retrieval/grounding failures documented | Done (5) | `docs/evaluation/week3-rag-evaluation.md` |
| RAG architecture diagram | Done | `docs/architecture/architecture-week3-rag.md` |
| Corpus/Source Register | Done | `knowledge/source-register.md` |

**Results:** retrieval hit@3 9/10 → 10/10 after fixes; answers 13/15 → 15/15 after a citation-parser fix
and one corrected test expectation.

## 2. Key engineering decisions

| Decision | Rationale |
|:---|:---|
| Synthetic team-written corpus | Brief requires authorised data; free-tier data policy |
| BM25 keyword retrieval, no embeddings yet | No new dependency or quota; deterministic; explainable; adequate at 61 chunks |
| Section-based chunking with readable chunk IDs | Citations a person can check (`POL-01#approval-thresholds`) |
| Next-section expansion | Fixes questions whose answer sits after the matching heading (R-2) |
| Score gate → refusal without a model call | Cheapest hallucination prevention |
| Citations verified in code | Same "never trust the model blindly" rule as Weeks 4–5 |
| Same search exposed to the agent as `search_policy` | Hybrid: tools for records, RAG for rules |

## 3. Failures, challenges and response

See the failure catalogue (R-1 … R-5). R-4 (numeric ranges with keyword search) remains open.

## 4. Individual contributions

| Member | Role | Tasks owned | Evidence |
|:---|:---|:---|:---|
| Mwesigwa Arnold Mugahi (23/U/244738/PS) | AI Engineering Lead | Corpus, RAG pipeline, tests, documentation | Commits on `main` |
| [to be added] | | | |

## 5. Plan for next week

Week 6: SQLite for drafts/audit (persistent state), one justified memory use, MCP-style interface for the
tools; groupmates take ownership per `docs/ONBOARDING.md`.
