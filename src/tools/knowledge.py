"""
Knowledge tool for the agent: search_policy (Week 3 + agent integration).
=========================================================================

Gives the Week 4/5 agents the same policy search as the RAG pipeline
(src/rag/index.py), as a read-only tool. The agent can then answer questions
like "who approves UGX 800,000?" from the shop's documents and cite the
source IDs (e.g. POL-01#approval-thresholds) instead of guessing.

Registered in src/tools/registry.py with permission "read".

Owner: Mwesigwa Arnold Mugahi (AI Engineering Lead)
Version: 1.0.0
"""

from rag.index import get_index               # BM25 index over knowledge/corpus/*.md


def search_policy(query: str, top_k: int = 3) -> dict:
    """
    Search the shop's policy and procedure documents.

    query   the question or keywords, e.g. "approval threshold 800000"
    top_k   how many passages to return (1-5)
    Returns {"query", "results": [{"source_id", "title", "section", "text", "score"}], "note"?}
    An empty result means nothing relevant was found: the agent must then say the
    information is not in the documents.
    """
    if not isinstance(query, str) or not query.strip():
        return {"error": "INVALID_PARAMETER: query must be a non-empty string"}
    top_k = max(1, min(int(top_k), 5))                  # keep the context small
    hits = get_index().search(query, top_k=top_k)
    result = {"query": query,
              "results": [{"source_id": h["chunk_id"], "title": h["title"], "section": h["section"],
                           "text": h["text"], "score": h["score"]} for h in hits],
              "source": "knowledge/corpus/"}
    if not hits:
        result["note"] = "No relevant passage found in the shop documents."
    return result
