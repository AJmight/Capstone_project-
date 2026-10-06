"""
rag package - Week 3 Context Engineering and RAG.

  index.py      ingest knowledge/corpus/*.md, chunk by section, BM25 search index
  policy_qa.py  retrieve -> build a [S1]..[Sn] context -> model answers with citations
                -> code checks the citations; CLI: py src\\rag\\policy_qa.py "question"

The same search is also exposed to the agent as the read-only tool `search_policy`
(src/tools/procurement.py), so the Week 4/5 agents can ground policy answers too.
"""
