"""
MVP tests - the additions that complete User Stories 1, 6 and 9 and connect RAG to the agent.
=============================================================================================

OFFLINE (free): get_inventory, query_purchase_history (totals recomputed independently),
search_policy as an agent tool, and the human edit-before-approval feature (approvals.py edit).

LIVE (real Gemini through src/tool_agent.py with prompt v2.3.0):
    M-01 inventory by category          M-04 policy question answered via search_policy (RAG)
    M-02 purchase total for a period    M-05 period with no data -> says so, no invented numbers
    M-03 vague question -> clarifies    M-06 unknown category -> lists the real categories

Usage (PowerShell, repo root):
    py tests\\test_mvp_tools.py --offline
    py tests\\test_mvp_tools.py --live

Owner: Mwesigwa Arnold Mugahi (AI Engineering Lead)
Version: 1.0.0 (MVP)
"""

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

import approvals                                          # noqa: E402
from test_week4_tools import sandbox                      # noqa: E402
from tools import procurement, registry                   # noqa: E402

OUT_DIR = Path("evidence/mvp")


def _hist(item_id, start, end):
    """Independent recomputation of a purchase total from past_purchases.csv."""
    with Path("data/past_purchases.csv").open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["item_id"] == item_id and start <= r["date"][:7] <= end]
    return (sum(int(r["quantity_purchased"]) for r in rows),
            sum(int(r["quantity_purchased"]) * int(r["historical_unit_price_ugx"]) for r in rows))


EXPECTED_QTY, EXPECTED_SPEND = _hist("ITM001", "2025-03", "2025-05")


# ---------------------------------------------------------------------------
# OFFLINE
# ---------------------------------------------------------------------------
def test_offline_01_inventory_by_category():
    """get_inventory('office') returns only Office items, with is_low flags; no category = all 15."""
    with sandbox():
        r = procurement.get_inventory("office")
        assert r["category"] == "Office" and {i["category"] for i in r["items"]} == {"Office"}
        assert procurement.get_inventory()["count"] == 15


def test_offline_02_unknown_category():
    """An unknown category (the old 'dairy' story) gives UNKNOWN_CATEGORY listing real categories."""
    with sandbox():
        err = procurement.get_inventory("dairy")["error"]
        assert err.startswith("UNKNOWN_CATEGORY") and "Stationery" in err


def test_offline_03_history_totals_exact():
    """query_purchase_history totals match an independent recomputation (March-May 2025, Bic Pens)."""
    with sandbox():
        r = procurement.query_purchase_history("Bic Pens (Blue)", "2025-03", "2025-05")
        assert (r["total_quantity"], r["total_spend_ugx"]) == (EXPECTED_QTY, EXPECTED_SPEND) == (170, 79295)
        assert r["records_found"] == 3 and r["data_range"] == {"first_month": "2025-01", "last_month": "2025-12"}


def test_offline_04_history_empty_and_invalid():
    """No data for Nov 2024 -> note + data_range; bad month and reversed range -> INVALID_PARAMETER."""
    with sandbox():
        r = procurement.query_purchase_history("rulers", "2024-11", "2024-11")
        assert r["records_found"] == 0 and "note" in r and r["data_range"]["first_month"] == "2025-01"
        assert procurement.query_purchase_history("ITM001", "2025-13")["error"].startswith("INVALID_PARAMETER")
        assert procurement.query_purchase_history("ITM001", "2025-06", "2025-01")["error"].startswith("INVALID_PARAMETER")
        assert "no purchase history" in procurement.query_purchase_history("calculator")["note"]


def test_offline_05_search_policy_tool():
    """search_policy via the registry returns source IDs; viewers may use it; bad top_k rejected."""
    with sandbox():
        r, status = registry.execute_tool("search_policy", {"query": "minimum order Nakawa"}, "viewer")
        assert status == "ok" and r["results"][0]["source_id"] == "SUP-02#ordering-and-minimum-order"
        r, status = registry.execute_tool("search_policy", {"query": "x", "top_k": 9}, "viewer")
        assert status == "invalid"


def test_offline_06_edit_quantity_logged():
    """US 9: editing a line keeps the AI suggestion, recomputes totals, and is audited."""
    with sandbox() as tmp:
        d = procurement.draft_requisition(["ITM001", "ITM003"], created_by="Staff")
        e = approvals.edit_quantity(d["draft_id"], "ITM001", 50, "Owner", "shelf space limited")
        line = next(l for l in e["lines"] if l["item_id"] == "ITM001")
        assert line["recommended_qty"] == 50 and line["ai_suggested_qty"] == 65
        assert line["total_cost_ugx"] == 50 * 476 and e["estimated_budget_ugx"] == 50 * 476 + 53466
        assert e["budget_range_ugx"]["low"] == (e["estimated_budget_ugx"] * 9 + 5) // 10
        log = [json.loads(l) for l in (tmp / "drafts" / "audit_log.jsonl").read_text().splitlines()]
        assert log[-1]["decision"] == "EDITED" and log[-1]["ai_suggested_qty"] == 65


def test_offline_07_edit_rules():
    """Edit needs a reason, only on undecided drafts, only existing lines; >cap sets requires_override."""
    with sandbox():
        d = procurement.draft_requisition(["ITM001"], created_by="Staff")
        for bad in [("ITM001", 50, "Owner", ""), ("ITM999", 50, "Owner", "x"), ("ITM001", -1, "Owner", "x")]:
            try:
                approvals.edit_quantity(d["draft_id"], *bad)
                raise AssertionError(f"edit allowed: {bad}")
            except approvals.ApprovalError:
                pass
        e = approvals.edit_quantity(d["draft_id"], "ITM001", 500, "Owner", "bulk deal")   # cap is 158
        assert e["requires_override_any"] is True
        approvals.decide(d["draft_id"], "APPROVED", "Owner", "bulk deal agreed")
        try:
            approvals.edit_quantity(d["draft_id"], "ITM001", 10, "Owner", "late change")
            raise AssertionError("edited an approved draft")
        except approvals.ApprovalError:
            pass


def run_offline():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_offline_")]
    results = []
    print("=" * 70 + "\nOFFLINE MVP TESTS\n" + "=" * 70)
    for name, fn in tests:
        try:
            fn()
            ok, detail = True, ""
        except Exception as e:
            ok, detail = False, f"{type(e).__name__}: {e}"
        tid = "M-O" + name.split("_")[2]
        results.append({"id": tid, "test": fn.__doc__.strip(), "passed": ok, "detail": detail})
        print(f"[{tid}] {'PASS' if ok else 'FAIL'}  {fn.__doc__.strip()}" + (f"\n        {detail}" if detail else ""))
    print(f"\nOffline: {sum(r['passed'] for r in results)}/{len(results)} passed")
    _save_md("offline_results.md", "MVP Offline Tests", results, ["id", "test", "passed", "detail"])
    return results


# ---------------------------------------------------------------------------
# LIVE
# ---------------------------------------------------------------------------
def _tools(run):
    return [c["name"] for c in run["tool_calls"]]


LIVE = [
    {"id": "M-01", "role": "viewer", "q": "Show me the stock levels for Office items.",
     "expected": "get_inventory(Office); names Stapler Medium and Files (Box)",
     "check": lambda r: "get_inventory" in _tools(r) and "Stapler" in r["final_text"] and "Files" in r["final_text"]},
    {"id": "M-02", "role": "viewer", "q": "How many Bic Pens did we buy from March to May 2025, and how much did we spend?",
     "expected": f"query_purchase_history; answer has {EXPECTED_QTY} and {EXPECTED_SPEND:,}",
     "check": lambda r: "query_purchase_history" in _tools(r) and str(EXPECTED_QTY) in r["final_text"]
                        and (f"{EXPECTED_SPEND:,}" in r["final_text"] or str(EXPECTED_SPEND) in r["final_text"])},
    {"id": "M-03", "role": "viewer", "q": "Tell me about our purchases.",
     "expected": "no tool call; asks one clarifying question (AC 6.2)",
     "check": lambda r: not r["tool_calls"] and "?" in r["final_text"]},
    {"id": "M-04", "role": "viewer", "q": "Who is allowed to approve a requisition worth UGX 800,000?",
     "expected": "search_policy; 'owner'; cites POL-01",
     "check": lambda r: "search_policy" in _tools(r) and "owner" in r["final_text"].lower() and "POL-01" in r["final_text"]},
    {"id": "M-05", "role": "viewer", "q": "How many rulers did we buy in November 2024?",
     "expected": "query_purchase_history; says no records for that period; no invented number",
     "check": lambda r: "query_purchase_history" in _tools(r)
                        # Run 1 answered correctly ("0 purchases recorded ... history covers 2025-01 to 2025-12")
                        # but the keyword list missed it; accept the data_range mention too (test fix).
                        and any(w in r["final_text"].lower() for w in ("no record", "no purchases", "not in",
                                                                       "no data", "0 purchases", "2025-01"))},
    {"id": "M-06", "role": "viewer", "q": "Show me inventory for dairy products.",
     "expected": "explains dairy is not a category and lists Electronics, Office, Stationery",
     "check": lambda r: all(c in r["final_text"] for c in ("Electronics", "Office", "Stationery"))},
]


def run_live(delay_s: float = 3):
    from tool_agent import run_agent
    print("\n" + "=" * 70 + "\nLIVE MVP AGENT TESTS (prompt v2.3.0)\n" + "=" * 70)
    results = []
    for case in LIVE:
        try:
            run = run_agent(case["q"], role=case["role"], user_name=f"test-{case['id']}")
            ok = bool(case["check"](run))
        except Exception as e:
            run, ok = {"final_text": f"{type(e).__name__}: {e}", "tool_calls": [], "models_used": [],
                       "stopped_reason": "test_error", "run_id": "-"}, False
        print(f"[{case['id']}] {'PASS' if ok else 'FAIL'}  tools={_tools(run)}  models={run['models_used']}\n"
              f"        {run['final_text'][:170].replace(chr(10), ' ')}")
        results.append({"id": case["id"], "question": case["q"], "expected": case["expected"], "passed": ok,
                        "tools": ", ".join(_tools(run)), "models": ", ".join(run["models_used"]),
                        "run_id": run["run_id"], "answer": run["final_text"]})
        if case is not LIVE[-1]:
            time.sleep(delay_s)
    print(f"\nLive: {sum(r['passed'] for r in results)}/{len(results)} passed")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "live_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    _save_md("live_results.md", "MVP Live Agent Tests", results, ["id", "question", "expected", "tools", "models", "passed"])
    return results


def _save_md(filename, title, rows, cols):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [f"# {title}", "", f"Run at {datetime.now().isoformat(timespec='seconds')} | "
             f"**{sum(r['passed'] for r in rows)}/{len(rows)} passed**", "",
             "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        lines.append("| " + " | ".join(("**PASS**" if r[c] else "**FAIL**") if c == "passed"
                                       else str(r[c]).replace("|", "/") for c in cols) + " |")
    (OUT_DIR / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")


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
