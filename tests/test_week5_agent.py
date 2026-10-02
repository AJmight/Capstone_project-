"""
Week 5 tests - the bounded Weekly Restock Agent.
================================================

OFFLINE (free, deterministic): a SCRIPTED FAKE MODEL replaces Gemini, so we can make the
"model" behave well or badly on purpose and prove that the CODE (not the model's good
manners) enforces the contract:
    ideal model            -> DRAFT_READY, all post-conditions pass
    tool fails once        -> one retry, recovery recorded, DRAFT_READY
    budget too small       -> no draft, NOTHING_FITS_BUDGET
    greedy model           -> drafts items outside the plan -> POSTCONDITION_FAILED
    double-drafting model  -> second draft -> POSTCONDITION_FAILED (at most one draft)
    looping model          -> repeated calls blocked, then iteration limit -> HANDOFF
    off-contract model     -> compare_supplier_quotes blocked (NOT_IN_TASK_CONTRACT)
    model unavailable      -> HANDOFF_MODEL_UNAVAILABLE
    forgetful model        -> summary without the approval status line -> POSTCONDITION_FAILED
    false draft claim      -> viewer shown a fake "awaiting approval" summary -> corrected (F-13)
    viewer role / bad budget / nothing low -> stop before any model call

LIVE (real Gemini, about 3-4 requests per trace): the four Week 5 execution traces
    T1 happy path, T2 budget re-plan, T3 failure + recovery (fault injected), T4 safe stop.
Readable traces are saved as evidence/week5/trace_<name>.md (+ .json).

Usage (PowerShell, repo root):
    py tests\\test_week5_agent.py --offline
    py tests\\test_week5_agent.py --live
    py tests\\test_week5_agent.py              (both)

Owner: Mwesigwa Arnold Mugahi (AI Engineering Lead)
Version: 1.0.0 (Week 5)
"""

# ---------------------------------------------------------------------------
# Imports and path setup
# ---------------------------------------------------------------------------
import argparse
import json
import re
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

from google.genai import errors, types        # noqa: E402

import llm_client                             # noqa: E402
import restock_agent                          # noqa: E402
import tool_agent                             # noqa: E402
from test_week4_tools import sandbox          # noqa: E402  (temp data/drafts/trace folders)
from tools import registry                    # noqa: E402

OUT_DIR = Path("evidence/week5")


# ---------------------------------------------------------------------------
# A scripted fake Gemini
# ---------------------------------------------------------------------------
def _fc(*calls):
    """A fake model turn that requests tools: calls = (name, args) pairs."""
    parts = [types.Part(function_call=types.FunctionCall(name=n, args=a, id=f"call{i}"))
             for i, (n, a) in enumerate(calls)]
    content = types.Content(role="model", parts=parts)
    return SimpleNamespace(function_calls=[p.function_call for p in parts],
                           candidates=[SimpleNamespace(content=content)], text=None)


def _text(t):
    """A fake model turn that answers in text (no tool calls)."""
    content = types.Content(role="model", parts=[types.Part(text=t)])
    return SimpleNamespace(function_calls=None, candidates=[SimpleNamespace(content=content)], text=t)


def _last_tool_result(contents):
    """(tool name, result dict) of the newest function response in the conversation, or (None, None)."""
    for c in reversed(contents):
        for p in c.parts or []:
            if getattr(p, "function_response", None):
                return p.function_response.name, p.function_response.response
    return None, None


def _sense(contents):
    """Read the low item IDs and the budget back out of the [RESTOCK TASK] message."""
    first = contents[0].parts[0].text
    ids = re.findall(r'"item_id": "(ITM\d+)"', first)
    budget = int(re.search(r"budget_ugx=(\d+)", first).group(1))
    return ids, budget


STATUS_LINE = "Status: DRAFT - AWAITING HUMAN APPROVAL. A manager must review and approve it."


def ideal_policy(contents):
    """What a well-behaved model does under prompt v2.1.0 Section 7."""
    name, result = _last_tool_result(contents)
    ids, budget = _sense(contents)
    if name is None:
        return _fc(("plan_within_budget", {"items": ids, "budget_ugx": float(budget)}))  # floats, like Gemini
    if "error" in result and result["error"].startswith("SERVICE_UNAVAILABLE"):
        return _fc((name, {"items": ids, "budget_ugx": float(budget)}))                  # one retry
    if "error" in result:                                                                # give up honestly
        return _text(f"I could not complete the restock: {result['error']}. No draft was created.")
    if name == "plan_within_budget":
        inc = [i["item_id"] for i in result["included"]]
        return _fc(("draft_requisition", {"items": inc})) if inc else _text("Nothing fits the budget.")
    return _text(f"Draft {result.get('draft_id')} created.\n{STATUS_LINE}")


def greedy_policy(contents):
    """Ignores the plan and drafts every low item (should be caught by post-conditions)."""
    name, result = _last_tool_result(contents)
    ids, budget = _sense(contents)
    if name is None:
        return _fc(("plan_within_budget", {"items": ids, "budget_ugx": budget}))
    if name == "plan_within_budget":
        return _fc(("draft_requisition", {"items": ids}))
    return _text(STATUS_LINE)


def double_draft_policy(contents):
    """Drafts, then drafts again with a different list (second draft must be caught)."""
    name, result = _last_tool_result(contents)
    ids, budget = _sense(contents)
    if name is None:
        return _fc(("plan_within_budget", {"items": ids, "budget_ugx": budget}))
    drafts = sum(1 for c in contents for p in (c.parts or [])
                 if getattr(p, "function_response", None) and p.function_response.name == "draft_requisition")
    if drafts == 0:
        return _fc(("draft_requisition", {"items": ["ITM001"]}))
    if drafts == 1:
        return _fc(("draft_requisition", {"items": ["ITM003"]}))
    return _text(STATUS_LINE)


def looping_policy(contents):
    """Calls get_low_stock forever (repeat guard + iteration limit must stop it)."""
    return _fc(("get_low_stock", {}))


def off_contract_policy(contents):
    """Tries a tool that exists but is not in this task's contract, then gives up."""
    name, _ = _last_tool_result(contents)
    if name is None:
        return _fc(("compare_supplier_quotes", {"item": "ITM001"}))
    return _text("I could not complete the task.")


def forgetful_policy(contents):
    """Like ideal, but the summary forgets the approval status line."""
    r = ideal_policy(contents)
    return _text("Draft created.") if r.text and "Status:" in r.text else r


@contextmanager
def fake_model(policy=None, unavailable=False):
    """Swap Gemini for the scripted policy; also send agent traces to a temp folder."""
    saved = (tool_agent.client, tool_agent.TRACE_PATH, llm_client.TRACE_PATH, llm_client.time.sleep,
             restock_agent.OUT_DIR, restock_agent.RUNS_LOG)
    tmp = Path(tempfile.mkdtemp())

    def generate_content(model, contents, config):
        if unavailable:
            raise errors.ServerError(503, {"error": {"code": 503, "status": "UNAVAILABLE", "message": "busy"}})
        return policy(contents)

    try:
        tool_agent.client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
        tool_agent.TRACE_PATH = tmp / "agent.jsonl"
        llm_client.TRACE_PATH = tmp / "llm.jsonl"
        llm_client.time.sleep = lambda s: None                    # do not wait between rounds
        restock_agent.OUT_DIR, restock_agent.RUNS_LOG = tmp, tmp / "runs.jsonl"
        yield
    finally:
        (tool_agent.client, tool_agent.TRACE_PATH, llm_client.TRACE_PATH, llm_client.time.sleep,
         restock_agent.OUT_DIR, restock_agent.RUNS_LOG) = saved
        registry.clear_faults()


def _all_pass(rec):
    return all(c["passed"] for c in rec["state"]["postconditions"])


# ---------------------------------------------------------------------------
# OFFLINE TESTS
# ---------------------------------------------------------------------------
def test_offline_01_ideal_run_draft_ready():
    """Ideal model, UGX 300,000: plan -> draft of exactly the 4 included items (UGX 294,130)."""
    with sandbox(), fake_model(ideal_policy):
        rec = restock_agent.run_restock(300000, user_name="T")
        lines = [l["item_id"] for l in rec["state"]["draft"]["lines"]]
        assert rec["outcome"] == "DRAFT_READY" and _all_pass(rec), rec["outcome"]
        assert sorted(lines) == ["ITM001", "ITM003", "ITM005", "ITM009"]
        assert rec["state"]["draft"]["estimated_budget_ugx"] == 294130


def test_offline_02_handoffs_built_from_state():
    """Deferred items, needs-human items and the approval step are listed for the human."""
    with sandbox(), fake_model(ideal_policy):
        h = " ".join(restock_agent.run_restock(300000)["state"]["handoffs"])
        for item in ("ITM006", "ITM007", "ITM011", "ITM012", "ITM013", "ITM015", "approvals.py"):
            assert item in h, item


def test_offline_03_failure_then_recovery():
    """plan_within_budget fails once (injected) -> retried once -> recovery recorded -> DRAFT_READY."""
    with sandbox(), fake_model(ideal_policy):
        registry.inject_fault("plan_within_budget", 1)
        rec = restock_agent.run_restock(300000)
        assert rec["outcome"] == "DRAFT_READY" and rec["state"]["recoveries"], rec["outcome"]
        assert rec["state"]["failures"][0]["injected"] is True


def test_offline_04_two_failures_stop_safely():
    """Fails twice: the second retry is blocked by the repeat guard; no draft is made."""
    with sandbox(), fake_model(ideal_policy):
        registry.inject_fault("plan_within_budget", 2)
        rec = restock_agent.run_restock(300000)
        assert not rec["state"]["drafts_created"] and rec["outcome"] != "DRAFT_READY", rec["outcome"]


def test_offline_05_nothing_fits_budget():
    """UGX 10,000: nothing fits -> no draft -> NOTHING_FITS_BUDGET."""
    with sandbox(), fake_model(ideal_policy):
        rec = restock_agent.run_restock(10000)
        assert rec["outcome"] == "NOTHING_FITS_BUDGET" and not rec["state"]["drafts_created"]


def test_offline_06_greedy_model_caught():
    """A model that drafts items outside the plan is caught: POSTCONDITION_FAILED, flagged on the draft."""
    with sandbox() as tmp, fake_model(greedy_policy):
        rec = restock_agent.run_restock(300000)
        assert rec["outcome"] == "POSTCONDITION_FAILED", rec["outcome"]
        draft_file = tmp / "drafts" / f"{rec['state']['drafts_created'][0]}.json"
        assert json.loads(draft_file.read_text())["agent_checks"]["outcome"] == "POSTCONDITION_FAILED"


def test_offline_07_double_draft_caught():
    """Two drafts in one run break 'at most one draft' -> POSTCONDITION_FAILED."""
    with sandbox(), fake_model(double_draft_policy):
        rec = restock_agent.run_restock(300000)
        assert len(rec["state"]["drafts_created"]) == 2 and rec["outcome"] == "POSTCONDITION_FAILED"


def test_offline_08_looping_model_bounded():
    """A model repeating the same call is blocked (REPEATED_CALL) and stopped by the turn limit."""
    with sandbox(), fake_model(looping_policy):
        rec = restock_agent.run_restock(300000)
        statuses = [c["status"] for c in rec["loop"]["tool_calls"]]
        assert rec["outcome"] == "HANDOFF_ITERATION_LIMIT", rec["outcome"]
        assert rec["loop"]["turns_used"] == restock_agent.MAX_TURNS and statuses.count("blocked") >= 1


def test_offline_09_off_contract_tool_blocked():
    """compare_supplier_quotes is a real tool but not in this task's contract -> blocked."""
    with sandbox(), fake_model(off_contract_policy):
        rec = restock_agent.run_restock(300000)
        err = rec["loop"]["tool_calls"][0]["result"]["error"]
        assert err.startswith("NOT_IN_TASK_CONTRACT") and not rec["state"]["drafts_created"]


def test_offline_10_model_unavailable_handoff():
    """Every model 503 -> HANDOFF_MODEL_UNAVAILABLE with a clear message; no draft."""
    with sandbox(), fake_model(unavailable=True):
        rec = restock_agent.run_restock(300000)
        assert rec["outcome"] == "HANDOFF_MODEL_UNAVAILABLE" and "unavailable" in rec["final_text"]


def test_offline_11_summary_must_mention_approval():
    """If the summary omits 'AWAITING HUMAN APPROVAL', the run is not reported as ready."""
    with sandbox(), fake_model(forgetful_policy):
        assert restock_agent.run_restock(300000)["outcome"] == "POSTCONDITION_FAILED"


def test_offline_12_preconditions_no_model_call():
    """Viewer role or a bad budget stops before any model call (fake would crash if called)."""
    def must_not_be_called(contents):
        raise AssertionError("model was called")
    with sandbox(), fake_model(must_not_be_called):
        assert restock_agent.run_restock(300000, role="viewer")["outcome"] == "PRECONDITION_FAILED"
        assert restock_agent.run_restock(0)["outcome"] == "PRECONDITION_FAILED"


def test_offline_13_nothing_low_no_model_call():
    """If nothing is low, SENSE stops the run (NOTHING_TO_DO) without spending model quota."""
    files = {
        "current_stock.csv": "item_id,item_name,category,current_stock,reorder_point,unit_cost_ugx\n"
                             "ITM001,Bic Pens (Blue),Stationery,50,20,500\n",
        "past_purchases.csv": "date,item_id,quantity_purchased,historical_unit_price_ugx\n",
        "supplier_quotes.csv": "supplier_name,item_id,offered_unit_price_ugx,min_order_qty,lead_time_days\n",
    }
    with sandbox(files), fake_model(lambda c: (_ for _ in ()).throw(AssertionError("model called"))):
        assert restock_agent.run_restock(300000)["outcome"] == "NOTHING_TO_DO"


def test_offline_14_plan_tool_rules():
    """plan_within_budget: urgency order, skip-and-continue, needs_human, budget validation."""
    from tools import procurement
    with sandbox():
        low = [i["item_id"] for i in procurement.get_low_stock()["items"]]
        p = procurement.plan_within_budget(low, 300000)
        assert [i["item_id"] for i in p["included"]] == ["ITM003", "ITM001", "ITM005", "ITM009"]
        assert [d["item_id"] for d in p["deferred"]] == ["ITM007", "ITM006"]
        assert p["planned_total_ugx"] == 294130 and p["remaining_budget_ugx"] == 5870
        assert len(p["needs_human"]) == 4
        assert procurement.plan_within_budget(low, None)["planned_total_ugx"] == 1619289
        assert procurement.plan_within_budget(low, -5)["error"].startswith("INVALID_PARAMETER")


def test_offline_15_trace_renders():
    """The Markdown trace has the phases a marker looks for."""
    with sandbox(), fake_model(ideal_policy):
        md = restock_agent.render_trace_md(dict(restock_agent.run_restock(300000), trace_name="x"))
        for phase in ("PRECONDITIONS", "SENSE", "PLAN/DECIDE", "ACT", "OBSERVE", "RE-PLAN", "POSTCONDITION", "STOP"):
            assert phase in md, phase


def test_offline_16_false_draft_claim_corrected():
    """F-13: a viewer's model writes a fake 'awaiting approval' summary -> code corrects and flags it."""
    def fake_draft_claim(contents):
        name, _ = _last_tool_result(contents)
        if name is None:
            return _fc(("estimate_reorder_quantity", {"item": "Rulers 30cm"}))
        return _text("Proposed draft: Rulers 57 units.\n" + STATUS_LINE)
    with sandbox(), fake_model(fake_draft_claim):
        run = tool_agent.run_agent("Draft a requisition for Rulers 30cm.", role="viewer")
        assert run["output_warnings"] and "AWAITING HUMAN APPROVAL" not in run["final_text"].upper()
        assert "information only" in run["final_text"] and not run["drafts_created"]


def run_offline():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_offline_")]
    results = []
    print("=" * 70 + "\nOFFLINE AGENT TESTS (scripted fake model, no quota)\n" + "=" * 70)
    for name, fn in tests:
        try:
            fn()
            ok, detail = True, ""
        except Exception as e:
            ok, detail = False, f"{type(e).__name__}: {e}"
        tid = "A-" + name.split("_")[2]
        results.append({"id": tid, "test": fn.__doc__.strip(), "passed": ok, "detail": detail})
        print(f"[{tid}] {'PASS' if ok else 'FAIL'}  {fn.__doc__.strip()}" + (f"\n        {detail}" if detail else ""))
    print(f"\nOffline: {sum(r['passed'] for r in results)}/{len(results)} passed")
    _save_md("offline_results.md", "Week 5 Offline Agent Tests", results, ["id", "test", "passed", "detail"])
    return results


# ---------------------------------------------------------------------------
# LIVE TRACES (real Gemini)
# ---------------------------------------------------------------------------
LIVE_TRACES = [
    {"name": "T1_happy_path", "budget": 2_000_000, "fault": None,
     "expected": "DRAFT_READY; 6 priced items, UGX 1,619,289; 4 needs-human items handed off",
     "check": lambda r: r["outcome"] == "DRAFT_READY" and r["state"]["draft"]["estimated_budget_ugx"] == 1619289},
    {"name": "T2_budget_replan", "budget": 300_000, "fault": None,
     "expected": "DRAFT_READY; re-plan keeps 4 most urgent (UGX 294,130), defers ITM007/ITM006",
     "check": lambda r: r["outcome"] == "DRAFT_READY" and r["state"]["draft"]["estimated_budget_ugx"] == 294130},
    {"name": "T3_failure_recovery", "budget": 300_000, "fault": "plan_within_budget",
     "expected": "plan tool fails once (injected) -> one retry -> RECOVERED -> DRAFT_READY",
     "check": lambda r: r["outcome"] == "DRAFT_READY" and bool(r["state"]["recoveries"])},
    {"name": "T4_safe_stop", "budget": 10_000, "fault": None,
     "expected": "NOTHING_FITS_BUDGET; no draft; human told why",
     "check": lambda r: r["outcome"] == "NOTHING_FITS_BUDGET" and not r["state"]["drafts_created"]},
]


def run_live(delay_s: float = 3):
    print("\n" + "=" * 70 + "\nLIVE EXECUTION TRACES (real Gemini)\n" + "=" * 70)
    results = []
    for t in LIVE_TRACES:
        registry.clear_faults()
        if t["fault"]:
            registry.inject_fault(t["fault"], 1)
        try:
            rec = restock_agent.run_restock(t["budget"], user_name="Mwesigwa Arnold Mugahi",
                                            save_trace_as=t["name"])
            ok = bool(t["check"](rec))
        except Exception as e:
            rec, ok = {"outcome": f"TEST_ERROR {type(e).__name__}: {e}", "loop": None,
                       "state": {"postconditions": []}}, False
        registry.clear_faults()
        loop = rec.get("loop") or {}
        print(f"[{t['name']}] {'PASS' if ok else 'FAIL'}  outcome={rec['outcome']}  "
              f"models={loop.get('models_used')}  turns={loop.get('turns_used')}  "
              f"tools={[c['name'] + ':' + c['status'] for c in loop.get('tool_calls', [])]}")
        results.append({"id": t["name"], "budget": f"UGX {t['budget']:,}", "expected": t["expected"],
                        "outcome": rec["outcome"], "models": ", ".join(loop.get("models_used", [])),
                        "postconditions": f"{sum(c['passed'] for c in rec['state']['postconditions'])}/"
                                          f"{len(rec['state']['postconditions'])}",
                        "trace": f"trace_{t['name']}.md", "passed": ok})
        if t is not LIVE_TRACES[-1]:
            time.sleep(delay_s)
    print(f"\nLive: {sum(r['passed'] for r in results)}/{len(results)} passed")
    _save_md("live_results.md", "Week 5 Live Execution Traces", results,
             ["id", "budget", "expected", "outcome", "models", "postconditions", "trace", "passed"])
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
