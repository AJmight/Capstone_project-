"""
RAG step 4-6: grounded policy question answering (Week 3).
==========================================================

    question
       |
       v
  [4] RETRIEVE   rag/index.py BM25 search -> best chunks above MIN_SCORE
       |         (+ the next section of the same document, see EXPAND_NEIGHBOURS)
       |         nothing relevant -> answer "not in the provided documents" WITHOUT a model call
       v
  [5] GENERATE   build a context of labelled sources [S1], [S2], ... and ask Gemini
       |         (prompt: prompts/policy_qa_v1.0.0.md) to answer ONLY from them and cite labels
       v
  [6] CHECK      code verifies every cited label exists and that a factual answer cites
                 at least one source; the result says which sources were used

Every run is appended to evidence/week3/rag_traces.jsonl (question, retrieved chunk
IDs and scores, model, answer, citation check).

Usage (PowerShell, repo root):
  py src\\rag\\policy_qa.py "Who can approve a requisition of UGX 800,000?"

Owner: Mwesigwa Arnold Mugahi (AI Engineering Lead)
Version: 1.0.1 (Week 3: grouped citations accepted)
"""

# ---------------------------------------------------------------------------
# Imports and path setup (works both as "python src/rag/policy_qa.py" and as an import)
# ---------------------------------------------------------------------------
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):                       # run directly: make src/ importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai_engine import load_system_prompt            # reads the BEGIN/END part of a prompt file
from llm_client import generate                     # Gemini with the fallback chain
from rag.index import get_index

PROMPT_PATH = Path("prompts/policy_qa_v1.0.0.md")
TRACE_PATH = Path("evidence/week3/rag_traces.jsonl")
TOP_K = 3
EXPAND_NEIGHBOURS = True        # also give the model the next section of each retrieved document
NOT_FOUND = "That information is not in the provided documents."


def retrieve(question: str, top_k: int = TOP_K, expand: bool = EXPAND_NEIGHBOURS) -> list[dict]:
    """
    Best chunks for the question. With expand=True, each hit is followed by the NEXT
    chunk of the same document ("small-to-big" retrieval). Fixes the Week 3 failure where
    the question matched a section heading ("The problem") but the answer was in the
    following section ("What staff should do").
    """
    index = get_index()
    hits = index.search(question, top_k=top_k)
    if not expand:
        return hits
    by_id = {c.chunk_id: n for n, c in enumerate(index.chunks)}
    out, seen = [], set()
    for h in hits:
        for chunk in (h, _neighbour(index, by_id[h["chunk_id"]])):
            if chunk and chunk["chunk_id"] not in seen:
                seen.add(chunk["chunk_id"])
                out.append(chunk)
    return out


def _neighbour(index, n: int) -> dict | None:
    """The chunk right after chunk n, if it belongs to the same document."""
    if n + 1 < len(index.chunks) and index.chunks[n + 1].doc_id == index.chunks[n].doc_id:
        c = index.chunks[n + 1]
        return {"chunk_id": c.chunk_id, "doc_id": c.doc_id, "title": c.title, "section": c.section,
                "score": None, "text": c.text, "source": c.source, "neighbour_of": index.chunks[n].chunk_id}
    return None


def check_citations(answer: str, n_sources: int) -> dict:
    """Which [S#] labels were cited, are they all real, and does a factual answer cite anything?"""
    # Accept "[S1]", "[S1][S3]" and grouped "[S1, S3]" (run 1 of the Week 3 tests flagged a correct
    # answer citing "[S1, S3]" as uncited because only the first form was recognised: failure R-5).
    cited = sorted({int(n) for group in re.findall(r"\[([^\]]*)\]", answer)
                    for n in re.findall(r"S(\d+)", group)})
    invalid = [c for c in cited if not 1 <= c <= n_sources]
    refusal = NOT_FOUND.lower() in answer.lower()
    ok = not invalid and (bool(cited) or (refusal and not cited))
    return {"cited": cited, "invalid": invalid, "is_refusal": refusal, "citations_ok": ok}


def answer_policy_question(question: str, label: str = "policy_qa") -> dict:
    """Full RAG pipeline for one question. Returns answer, sources, citation check, model."""
    sources = retrieve(question)
    record = {"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "question": question,
              "retrieved": [{"label": f"S{i}", "chunk_id": s["chunk_id"], "score": s["score"]}
                            for i, s in enumerate(sources, 1)]}

    if not sources:
        # Nothing relevant: refuse deterministically, no model call, no chance to hallucinate.
        record.update(model=None, answer=NOT_FOUND,
                      check={"cited": [], "invalid": [], "is_refusal": True, "citations_ok": True})
    else:
        context = "\n\n".join(f"[S{i}] ({s['chunk_id']} | {s['title']} - {s['section']})\n{s['text']}"
                              for i, s in enumerate(sources, 1))
        llm = generate(load_system_prompt(PROMPT_PATH),
                       f"[SOURCES]\n{context}\n\n[QUESTION]\n{question}", label=label)
        record.update(model=llm.model, answer=llm.text.strip(),
                      check=check_citations(llm.text, len(sources)))

    record["sources"] = [{"label": f"S{i}", "chunk_id": s["chunk_id"], "title": s["title"],
                          "section": s["section"], "source": s["source"]} for i, s in enumerate(sources, 1)]
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRACE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "Who can approve a requisition of UGX 800,000?"
    r = answer_policy_question(q)
    print(r["answer"])
    print("\nSources:")
    for s in r["sources"]:
        print(f"  [{s['label']}] {s['chunk_id']}  ({s['source']})")
    print(f"\nModel: {r['model']} | citations ok: {r['check']['citations_ok']}")
