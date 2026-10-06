"""
Week 3 tests - RAG over the shop's policy documents (15 questions).
===================================================================

The brief asks for at least 15 RAG questions: answerable, partially answerable and
deliberately unanswerable. We use 5 + 5 + 5.

OFFLINE (free, deterministic): RETRIEVAL quality only.
    hit@3        is the section that contains the answer among the top 3 search results?
    context hit  is it in the context actually given to the model (top 3 + next section)?
    rank / MRR   where the right section appeared (1 = best)
  Unanswerable questions have no "right section"; we only record what was retrieved.
  Saved to evidence/week3/retrieval_results_index_v<INDEX_VERSION>.md, so results before
  and after a retrieval fix are both kept.

LIVE (15 model requests at most; refusals with no retrieved chunk cost nothing): ANSWERS.
    answerable    must contain the key fact, cite valid sources, not refuse
    partial       must give the known part with citations AND say what the documents do not say
    unanswerable  must reply "That information is not in the provided documents."
  Saved to evidence/week3/answer_results.md/.json.

Usage (PowerShell, repo root):
    py tests\\test_week3_rag.py --offline
    py tests\\test_week3_rag.py --live

Owner: Mwesigwa Arnold Mugahi (AI Engineering Lead)
Version: 1.0.0 (Week 3)
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rag import policy_qa                     # noqa: E402
from rag.index import INDEX_VERSION, get_index, load_chunks   # noqa: E402

OUT_DIR = Path("evidence/week3")
MISSING = re.compile(r"documents? do(es)? not (say|mention|state|specify|include|cover)", re.I)

# id, type, question, chunk that contains the answer (None = unanswerable), key facts the answer must contain
QUESTIONS = [
    ("RA-01", "answerable", "Who can approve a requisition of UGX 800,000?",
     "POL-01#approval-thresholds", [r"owner"]),
    ("RA-02", "answerable", "What is the minimum order quantity at Nakawa Stationers?",
     "SUP-02#ordering-and-minimum-order", [r"\b10\b"]),
    ("RA-03", "answerable", "How long do we keep requisition records?",
     "FAQ-01#how-long-do-we-keep-requisition-records", [r"five years|5 years"]),
    ("RA-04", "answerable", "Can staff pay a supplier by mobile money?",
     "POL-02#who-pays-suppliers", [r"owner"]),
    ("RA-05", "answerable", "What should staff do when a sales rep pushes a today-only discount?",
     "GDE-01#what-staff-should-do", [r"written quot"]),
    ("RP-01", "partial", "What is Entebbe Traders' delivery fee and on which days do they deliver?",
     "SUP-03#delivery", [r"tuesday"]),
    ("RP-02", "partial", "What is our weekly restock budget this week and how is it set?",
     "POL-02#weekly-restock-budget", [r"300,000|owner"]),
    ("RP-03", "partial", "How many days does Kampala Office Supplies take to deliver, and what discount do "
                         "they give for bulk orders?", "SUP-01#delivery", [r"3 days|three days"]),
    ("RP-04", "partial", "Who approves requisitions above UGX 2,000,000 and how much did we spend on "
                         "approved requisitions last year?", "POL-01#approval-thresholds", [r"owner"]),
    ("RP-05", "partial", "When are reorder points raised for school terms, and by how much for calculators?",
     # Run 1 expected "30%", but the 30% rise covers exercise books/pens/pencils/rulers, NOT calculators;
     # the answerable part is WHEN reorder points are raised (test-design error, corrected after run 1).
     "PRC-02#school-terms-and-seasons", [r"school term|january|september"]),
    ("RU-01", "unanswerable", "What is the phone number of the Kampala Office Supplies manager?", None, []),
    ("RU-02", "unanswerable", "What is the VAT rate on stationery in Uganda?", None, []),
    ("RU-03", "unanswerable", "What prices does our competitor across the road charge?", None, []),
    ("RU-04", "unanswerable", "How much is the shop assistant's monthly salary?", None, []),
    ("RU-05", "unanswerable", "Will it rain in Kampala tomorrow?", None, []),
]


# ---------------------------------------------------------------------------
# OFFLINE: retrieval evaluation
# ---------------------------------------------------------------------------
def run_offline() -> list[dict]:
    chunks = load_chunks()
    index = get_index()
    print("=" * 70 + f"\nOFFLINE RETRIEVAL EVALUATION (index v{INDEX_VERSION}, {len(chunks)} chunks)\n" + "=" * 70)
    rows = []
    for qid, kind, q, expected, _ in QUESTIONS:
        top = index.search(q, top_k=3)
        ranked = [h["chunk_id"] for h in index.search(q, top_k=len(chunks), min_score=0)]
        context = [c["chunk_id"] for c in policy_qa.retrieve(q)]
        rank = ranked.index(expected) + 1 if expected in ranked else None
        row = {"id": qid, "type": kind, "question": q, "expected": expected or "-",
               "top3": ", ".join(f"{h['chunk_id']} ({h['score']})" for h in top) or "(nothing above MIN_SCORE)",
               "rank": rank or "-",
               "hit@3": (expected in [h["chunk_id"] for h in top]) if expected else None,
               "context_hit": (expected in context) if expected else None}
        rows.append(row)
        mark = "n/a " if expected is None else ("HIT " if row["hit@3"] else "MISS")
        print(f"[{qid}] {mark} rank={row['rank']:<3} ctx={row['context_hit']}  top: {row['top3'][:110]}")
    scored = [r for r in rows if r["hit@3"] is not None]
    hits = sum(r["hit@3"] for r in scored)
    ctx = sum(r["context_hit"] for r in scored)
    mrr = sum(1 / r["rank"] for r in scored if r["rank"] != "-") / len(scored)
    print(f"\nhit@3 {hits}/{len(scored)} | context hit {ctx}/{len(scored)} | MRR {mrr:.2f}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [f"# Week 3 Retrieval Results - index v{INDEX_VERSION}", "",
             f"Run at {datetime.now().isoformat(timespec='seconds')} | {len(chunks)} chunks | "
             f"**hit@3 {hits}/{len(scored)}**, context hit {ctx}/{len(scored)}, MRR {mrr:.2f}", "",
             "| ID | Type | Question | Expected chunk | Rank | hit@3 | Context hit | Top 3 (score) |",
             "|---|---|---|---|:---:|:---:|:---:|---|"]
    for r in rows:
        fmt = lambda v: "n/a" if v is None else ("yes" if v else "**no**")
        lines.append(f"| {r['id']} | {r['type']} | {r['question']} | {r['expected']} | {r['rank']} | "
                     f"{fmt(r['hit@3'])} | {fmt(r['context_hit'])} | {r['top3']} |")
    (OUT_DIR / f"retrieval_results_index_v{INDEX_VERSION}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


# ---------------------------------------------------------------------------
# LIVE: answer evaluation
# ---------------------------------------------------------------------------
def judge(kind: str, facts: list[str], rec: dict) -> tuple[bool, str]:
    """Pass/fail for one answer, with the reason."""
    ans, chk = rec["answer"], rec["check"]
    if kind == "unanswerable":
        return chk["is_refusal"], "refused" if chk["is_refusal"] else "answered something that is not in the documents"
    if chk["is_refusal"] and not chk["cited"]:
        return False, "refused although the documents contain the answer"
    if not chk["citations_ok"]:
        return False, f"citation problem: cited {chk['cited']}, invalid {chk['invalid']}"
    missing_facts = [f for f in facts if not re.search(f, ans, re.I)]
    if missing_facts:
        return False, f"key fact missing: {missing_facts}"
    if kind == "partial" and not MISSING.search(ans):
        return False, "did not say what the documents leave out"
    return True, "ok"


def run_live(delay_s: float = 2) -> list[dict]:
    print("\n" + "=" * 70 + "\nLIVE ANSWER EVALUATION (RAG pipeline)\n" + "=" * 70)
    results = []
    for qid, kind, q, _, facts in QUESTIONS:
        try:
            rec = policy_qa.answer_policy_question(q, label=f"rag:{qid}")
            ok, why = judge(kind, facts, rec)
        except Exception as e:
            rec, ok, why = {"answer": "", "model": None, "sources": [], "check": {}}, False, f"{type(e).__name__}: {e}"
        print(f"[{qid}] {'PASS' if ok else 'FAIL'} ({kind}, {rec.get('model')}) {why}\n        {rec['answer'][:150]!r}")
        results.append({"id": qid, "type": kind, "question": q, "passed": ok, "reason": why,
                        "model": rec.get("model"), "answer": rec["answer"],
                        "sources": [s["chunk_id"] for s in rec.get("sources", [])]})
        if rec.get("model"):
            time.sleep(delay_s)
    passed = sum(r["passed"] for r in results)
    print(f"\nLive: {passed}/{len(results)} passed")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "answer_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    lines = [f"# Week 3 RAG Answer Results (index v{INDEX_VERSION}, prompt policy_qa v1.0.0)", "",
             f"Run at {datetime.now().isoformat(timespec='seconds')} | **{passed}/{len(results)} passed**", "",
             "| ID | Type | Question | Result | Reason | Model | Sources given |", "|---|---|---|:---:|---|---|---|"]
    for r in results:
        lines.append(f"| {r['id']} | {r['type']} | {r['question']} | {'**PASS**' if r['passed'] else '**FAIL**'} | "
                     f"{r['reason']} | {r['model'] or 'none (no model call)'} | {', '.join(r['sources']) or '-'} |")
    (OUT_DIR / "answer_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()
    both = not (a.offline or a.live)
    if a.offline or both:
        run_offline()
    if a.live or both:
        run_live()
