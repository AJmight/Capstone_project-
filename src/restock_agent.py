"""
Weekly Restock Agent - the AI-led Week 5 bounded, goal-directed agent.
===============================================================

THE GOAL (one task that genuinely needs several decisions)
----------------------------------------------------------
"Prepare this week's restock requisition within a budget of UGX X, and tell the
human everything that still needs their decision."

It needs decisions, not just one lookup: which of the low items fit the budget,
what to defer, what cannot be priced automatically (no purchase history), what to
do when a tool fails, and when to stop. The full contract is in
docs/requirements/agent-task-contract.md.

THE LOOP (Sense -> Plan/Decide -> Act -> Observe -> Stop/Re-plan)
-----------------------------------------------------------------
  0. PRECONDITIONS  (code)  budget a positive whole number?
  1. SENSE          (code)  get_restock_options through the registry -> evidence for AI choices
                            nothing low -> stop NOTHING_TO_DO (no model call needed)
  2. PLAN / DECIDE  (model) reads the goal + SENSE block, chooses the next tool
  3. ACT            (code)  registry runs the tool (allow-list, argument validation)
  4. OBSERVE        (code)  observe() updates the explicit AgentState after every result
     RE-PLAN                budget too small -> plan drops items (deferred); a temporary
                            failure -> one retry (recovery)
     ... back to 2 until the model writes its summary or a limit is hit ...
  5. POST-CONDITIONS (code) the draft must match the plan, stay within budget, be a DRAFT,
                            and the summary must say it awaits approval
  6. STOP           (code)  the OUTCOME is decided by code from the state, never by the
                            model's wording: DRAFT_READY, NOTHING_FITS_BUDGET, NOTHING_TO_DO,
                            PRECONDITION_FAILED, POSTCONDITION_FAILED, BUDGET_CEILING_EXCEEDED,
                            HANDOFF_<reason>

WHO DECIDES WHAT
----------------
  Python decides: what is low; every quantity, price and total; whether supplier/item choices
                  match real records; whether the budget is met; the limits and final outcome.
  The model decides: the priority order, supplier trade-offs, which approved tool to call next,
                  how to react to evidence/failures, and how to explain its recommendation.
  The human decides: approve or reject the draft (src/approvals.py), the quantities of
                  "needs_human" items, and whether to fund deferred items.

LIMITS: interactive defaults allow max 3 model turns, max 6 tool calls, 3 tools only (task allow-list), the same
call may not be repeated (one retry allowed after SERVICE_UNAVAILABLE).

EVIDENCE: every run is appended to evidence/week5/restock_runs.jsonl; with --save-trace
a readable Markdown trace (+ JSON) is written to evidence/week5/.

Usage (PowerShell, repo root):
  py src\\restock_agent.py --budget 300000 --user "Mwesigwa Arnold Mugahi"
  py src\\restock_agent.py --budget 300000 --save-trace T2_budget_replan

Owner: Mwesigwa Arnold Mugahi (AI Engineering Lead)
Version: 1.3.0 (F-26: agent_checks written to the SQLite draft; no crash when budget_ugx is omitted)
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
import argparse                               # command-line interface
import json                                   # traces
import os                                     # bounded interactive turn configuration
from dataclasses import asdict, dataclass, field   # the explicit AgentState
from datetime import datetime, timezone       # timestamps
from pathlib import Path                      # file paths

from guardrails import (BudgetCeilingGuardrail, GuardrailViolation)   # Week 7 guardrails
from storage import DEFAULT_TENANT_ID, DEFAULT_USER_ID, SQLiteStorage   # where drafts are saved (F-26)
from tools import procurement                 # DRAFT_STATUS, STORAGE_PATH
from tools.registry import execute_tool
from tool_agent import run_agent              # the bounded model <-> tool loop (Week 4, extended)

# ---------------------------------------------------------------------------
# The task contract in code (mirrors docs/requirements/agent-task-contract.md)
# ---------------------------------------------------------------------------
GOAL = ("Prepare ONE draft restock requisition within the budget and report everything that "
        "needs a human decision.")
CONTRACT_TOOLS = {"plan_within_budget", "draft_requisition"}   # read/plan/write allow-list
MAX_TURNS = int(os.getenv("RESTOCK_AGENT_MAX_TURNS", "5"))          # allows one recovery plus draft verification
MAX_TOOL_CALLS = int(os.getenv("RESTOCK_AGENT_MAX_TOOL_CALLS", "8"))  # bounded plan/retry/draft budget


def _close_run_managers(*managers) -> None:
    """Release per-run SQLite handles on success and failure (avoids stale sessions/locks)."""
    for manager in managers:
        if manager is not None:
            try:
                manager.close()
            except Exception:
                pass
OUT_DIR = Path("evidence/week5")
RUNS_LOG = OUT_DIR / "restock_runs.jsonl"


# ---------------------------------------------------------------------------
# Explicit state: everything the agent knows, updated after each observation
# ---------------------------------------------------------------------------
@dataclass
class AgentState:
    goal: str
    budget_ugx: int
    user_name: str
    phase: str = "START"                                  # START, SENSE, PLAN, DECIDE, ACT, OBSERVE, STOP
    low_items: list = field(default_factory=list)         # low items extracted from tool evidence
    restock_options: dict = field(default_factory=dict)   # exact per-supplier evidence for AI decisions
    plan: dict | None = None                              # last successful plan_within_budget result
    draft: dict | None = None                             # the draft_requisition result, if any
    drafts_created: list = field(default_factory=list)    # every draft ID (post-condition: at most 1)
    failures: list = field(default_factory=list)          # tool errors seen
    recoveries: list = field(default_factory=list)        # failures followed by a successful retry
    timeline: list = field(default_factory=list)          # human-readable steps for the trace
    postconditions: list = field(default_factory=list)    # [{check, passed, detail}]
    handoffs: list = field(default_factory=list)          # what the human must decide
    outcome: str = ""
    _last_turn: int = 0                                   # internal: to start a new DECIDE entry per turn

    def log(self, phase: str, detail: str) -> None:
        """Add one line to the timeline and remember the current phase."""
        self.phase = phase
        self.timeline.append({"t": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                              "phase": phase, "detail": detail})

    # ---- called by run_agent after EVERY tool call (the OBSERVE step) ----
    def observe(self, name: str, args: dict, result: dict, status: str,
                turn: int, model: str, model_text: str) -> None:
        if turn != self._last_turn:                       # first tool of a new model turn
            self._last_turn = turn
            note = f' - model said: "{model_text[:160]}"' if model_text else ""
            self.log("PLAN/DECIDE", f"turn {turn} ({model}) chose {name}{note}")
        self.log("ACT", f"{name}({_short_args(args)}) -> {status}")

        if "error" in result:
            self.failures.append({"tool": name, "args": args, "error": result["error"],
                                  "injected": result.get("injected", False)})
            self.log("OBSERVE", f"error: {result['error']}"
                     + (" [fault injected for testing]" if result.get("injected") else ""))
            if str(result["error"]).startswith("SERVICE_UNAVAILABLE"):
                self.log("RE-PLAN", "temporary failure -> the contract allows ONE retry of the same call")
            return

        # A success right after a failure of the same tool = a recovery.
        if self.failures and self.failures[-1]["tool"] == name:
            self.recoveries.append({"tool": name, "after_error": self.failures[-1]["error"]})
            self.log("RECOVERED", f"{name} succeeded on retry")

        if name == "plan_within_budget":
            self.plan = result
            inc = [i["item_id"] for i in result["included"]]
            # budget_ugx is None when the model called the tool without a budget ("no limit");
            # formatting None with :, would crash the whole run, so print it as words instead.
            limit = (f"UGX {result['budget_ugx']:,}" if result.get("budget_ugx") is not None
                     else "no budget limit")
            self.log("OBSERVE",             f"AI-proposed plan: include {inc} = UGX {result['planned_total_ugx']:,} of "
                                f"{limit}; deferred "
                                f"{[d['item_id'] for d in result['deferred']]}; needs human "
                                f"{[h['item_id'] for h in result['needs_human']]}")
            if result["deferred"]:
                self.log("RE-PLAN", f"budget too small for all priced items -> "
                                    f"{len(result['deferred'])} deferred, most urgent kept")
            if not result["included"]:
                self.log("RE-PLAN", "nothing fits the budget -> the contract says do NOT draft")
        elif name == "draft_requisition":
            self.draft = result
            if result.get("draft_id"):
                self.drafts_created.append(result["draft_id"])
            self.log("OBSERVE", f"draft {result.get('draft_id')} with "
                                f"{[l['item_id'] for l in result.get('lines', [])]} = "
                                f"UGX {result.get('estimated_budget_ugx', 0):,}, status {result.get('status')}")
        elif name == "get_low_stock":
            self.log("OBSERVE", f"{result['count']} low items")


def _short_args(args: dict) -> str:
    """Compact argument text for the timeline, e.g. items=[ITM003, ITM001], budget_ugx=300000."""
    parts = []
    for k, v in args.items():
        parts.append(f"{k}=[{', '.join(map(str, v))}]" if isinstance(v, list) else f"{k}={v}")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Post-conditions: deterministic checks on what the agent produced
# ---------------------------------------------------------------------------
def check_postconditions(state: AgentState, final_text: str) -> list[dict]:
    """Return [{check, passed, detail}]. Only meaningful checks are added for each case."""
    checks = []

    def add(check, passed, detail):
        checks.append({"check": check, "passed": bool(passed), "detail": detail})

    add("at most one draft per run", len(state.drafts_created) <= 1, f"drafts: {state.drafts_created}")
    if state.drafts_created:
        d = state.draft
        drafted = sorted(l["item_id"] for l in d["lines"])
        planned = sorted(i["item_id"] for i in (state.plan or {}).get("included", []))
        add("plan made before drafting", state.plan is not None, "plan_within_budget succeeded first")
        add("draft items == plan 'included' items", drafted == planned, f"draft {drafted} vs plan {planned}")
        add("draft total within budget", d["estimated_budget_ugx"] <= state.budget_ugx,
            f"UGX {d['estimated_budget_ugx']:,} <= UGX {state.budget_ugx:,}")
        planned_suppliers = {i["item_id"]: i["selected_supplier"]
                             for i in (state.plan or {}).get("included", [])}
        actual_suppliers = {i["item_id"]: i["selected_supplier"] for i in d["lines"]}
        add("draft suppliers match AI plan", actual_suppliers == planned_suppliers,
            f"draft {actual_suppliers} vs plan {planned_suppliers}")
        planned_total = (state.plan or {}).get("planned_total_ugx")
        add("draft total matches validated plan", d["estimated_budget_ugx"] == planned_total,
            f"draft UGX {d['estimated_budget_ugx']:,} vs plan UGX {planned_total:,}")
        planned_reasons = {i["item_id"]: i.get("selection_reason", "")
                           for i in (state.plan or {}).get("included", [])}
        draft_reasons = {i["item_id"]: i.get("ai_supplier_rationale", "") for i in d["lines"]}
        add("AI supplier rationales match validated plan", draft_reasons == planned_reasons,
            f"draft rationale keys {sorted(draft_reasons)} vs plan {sorted(planned_reasons)}")
        planned_rationale = (state.plan or {}).get("priority_rationale", "")
        add("AI priority rationale preserved", d.get("ai_selection_rationale") == planned_rationale,
            "draft and validated plan carry the same rationale")
        add("draft status is DRAFT", d["status"] == procurement.DRAFT_STATUS, d["status"])
        add("summary says it awaits human approval", "AWAITING HUMAN APPROVAL" in final_text.upper(),
            "status line present" if "AWAITING HUMAN APPROVAL" in final_text.upper() else "status line missing")
    elif state.plan is not None and not state.plan["included"]:
        add("no draft when nothing fits the budget", not state.drafts_created, "correctly did not draft")
    return checks


def _handoffs(state: AgentState) -> list[str]:
    """Everything a human must decide, built from the STATE (not from the model's text)."""
    out = []
    plan = state.plan or {}
    for h in plan.get("needs_human", []):
        out.append(f"{h['item_id']} {h['item_name']}: {h['reason']}")
    for d in plan.get("deferred", []):
        out.append(f"{d['item_id']} {d['item_name']}: deferred - {d['reason']}")
    for line in (state.draft or {}).get("lines", []):
        if line.get("requires_override"):
            out.append(f"{line['item_id']}: {line['override_reason']}")
    if state.drafts_created:
        out.append(f"Approve or reject {state.drafts_created[0]} with src/approvals.py")
    return out


# ---------------------------------------------------------------------------
# Deterministic fallback (no model call) - used when every model is out of quota
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# The agent run
# ---------------------------------------------------------------------------
def run_restock(budget_ugx: int, user_name: str = "shop user",
                save_trace_as: str | None = None, shop_id: str = "default_shop",
                tenant_id: str = "default-shop", user_id: str = DEFAULT_USER_ID) -> dict:
    """Run the weekly restock task once. Returns the full run record (also logged)."""
    state = AgentState(goal=GOAL, budget_ugx=budget_ugx, user_name=user_name)
    run, final_text = None, ""
    recalled_memories = []

    # Initialize Week 6 State and Memory Managers (graceful fallback if unavailable)
    state_mgr, mem_mgr, session = None, None, None
    try:
        from state import StateManager, WorkflowStage
        from memory import MemoryManager
        state_mgr = StateManager()
        mem_mgr = MemoryManager()
        session = state_mgr.create_session(shop_id=shop_id, user_name=user_name, budget_ugx=budget_ugx)
    except Exception:
        pass

    # ---- 0. PRECONDITIONS (code) ----
    problems = []
    if not isinstance(budget_ugx, int) or isinstance(budget_ugx, bool) or budget_ugx <= 0:
        problems.append("budget must be a positive whole number of UGX")
    state.log("PRECONDITIONS", "ok" if not problems else "; ".join(problems))

    if problems:
        state.outcome = "PRECONDITION_FAILED"
        final_text = "Cannot start the restock task: " + "; ".join(problems) + "."
        if state_mgr and session:
            try:
                state_mgr.transition_to(session.session_id, WorkflowStage.TERMINATED, "Preconditions failed")
            except Exception:
                pass
    else:
        # ---- 1. SENSE (code, through the registry so it is traced and validated) ----
        if state_mgr and session:
            try:
                state_mgr.transition_to(session.session_id, WorkflowStage.SENSING_INVENTORY, "Querying low stock")
            except Exception:
                pass

        sense, status = execute_tool("get_restock_options", {},
                                     context={"tenant_id": tenant_id}, run_id="sense")
        if "error" in sense:
            state.log("SENSE", f"failed: {sense['error']}")
            state.outcome = "HANDOFF_SENSE_FAILED"
            final_text = f"Could not read the inventory ({sense['error']}). No action taken."
            if state_mgr and session:
                try:
                    state_mgr.transition_to(session.session_id, WorkflowStage.TERMINATED, "Sense failed")
                except Exception:
                    pass
        else:
            state.restock_options = sense
            state.low_items = [
                {"item_id": item["item_id"], "item_name": item["item_name"],
                 "current_stock": item["current_stock"], "reorder_point": item["reorder_point"]}
                for item in sense["items"]
            ]
            state.log("SENSE", f"{sense['count']} low items with full quote/history options: "
                               f"{[i['item_id'] for i in state.low_items]}")
            if state_mgr and session:
                try:
                    state_mgr.update_session(session.session_id, low_stock_count=len(state.low_items))
                except Exception:
                    pass

            if not state.low_items:
                state.outcome = "NOTHING_TO_DO"
                final_text = "No items are at or below their reorder point. Nothing to restock."
                if state_mgr and session:
                    try:
                        state_mgr.transition_to(session.session_id, WorkflowStage.TERMINATED, "No items low")
                    except Exception:
                        pass

    if not state.outcome:
        # Retrieve relevant persistent memories for the low stock items (Week 6)
        mem_prompt = ""
        if mem_mgr:
            try:
                target_keys = [i["item_id"] for i in state.low_items]
                recalled_memories = mem_mgr.retrieve_relevant_memories(shop_id=shop_id, target_keys=target_keys)
                mem_prompt = mem_mgr.format_memories_for_prompt(recalled_memories)
                if recalled_memories:
                    state.log("MEMORY", f"Retrieved {len(recalled_memories)} preferences for items: {target_keys}")
            except Exception:
                pass

        if state_mgr and session:
            try:
                state_mgr.transition_to(session.session_id, WorkflowStage.PLANNING_RESTOCK, "Optimizing plan within budget")
            except Exception:
                pass

        # ---- 2-4. PLAN/DECIDE -> ACT -> OBSERVE loop (model + registry) ----
        # The model receives complete, tool-computed options, then chooses
        # priorities and supplier trade-offs. Python validates the choices and
        # recomputes quantities, prices and budget fit before any draft is saved.
        message = (f"[RESTOCK TASK]\nGoal: {GOAL}\nBudget: UGX {budget_ugx:,} (budget_ugx={budget_ugx})\n"
                   f"Requested by: {user_name}\n\n[SENSE]\n" +
                   json.dumps(state.restock_options, indent=1))
        if mem_prompt:
            message += f"\n\n{mem_prompt}"

        try:
            run = run_agent(message, user_name=user_name, max_turns=MAX_TURNS,
                            max_tool_calls=MAX_TOOL_CALLS, on_tool_result=state.observe,
                            trace_label="restock_agent", allowed_tools=CONTRACT_TOOLS,
                            tenant_id=tenant_id)
        except Exception:
            _close_run_managers(state_mgr, mem_mgr)
            raise

        final_text = run["final_text"]
        if run["steps"] and not run["steps"][-1]["tool_requests"]:
            state.log("PLAN/DECIDE", f"turn {run['steps'][-1]['turn']} ({run['steps'][-1]['model']}) "
                                     f"wrote the final summary (no more tools)")

        # ---- 5. POST-CONDITIONS (code) ----
        state.postconditions = check_postconditions(state, final_text)
        for c in state.postconditions:
            state.log("POSTCONDITION", f"{'PASS' if c['passed'] else 'FAIL'} - {c['check']}: {c['detail']}")

        # ---- 5b. WEEK 8 HARDENING: the budget ceiling is a HARD limit (F-12) ----
        # The exact total must never exceed the money the owner allocated. The
        # post-conditions above already test that; this guardrail is the named,
        # independent gate that makes the rule explicit and auditable, and it is
        # what the Week 7 catalogue points at. It is applied when the
        # post-conditions pass, so a misbehaving model is reported as
        # POSTCONDITION_FAILED (the more specific diagnosis) and a drifted rule
        # is reported as BUDGET_CEILING_EXCEEDED.
        budget_blocked = False
        if state.drafts_created and all(c["passed"] for c in state.postconditions):
            draft_total = int((state.draft or {}).get("estimated_budget_ugx", 0))
            try:
                BudgetCeilingGuardrail.verify_draft_within_budget(
                    draft_total_ugx=draft_total, allocated_budget_ugx=int(budget_ugx))
            except GuardrailViolation as exc:
                budget_blocked = True
                state.log("GUARDRAIL", str(exc))
                final_text = (f"The requisition was stopped by the budget guardrail: {exc} "
                              f"Nothing was sent to any supplier; a human must decide.")

        # ---- 6. OUTCOME decided by code ----
        if budget_blocked:
            state.outcome = "BUDGET_CEILING_EXCEEDED"
            if state_mgr and session:
                try:
                    state_mgr.transition_to(session.session_id, WorkflowStage.TERMINATED,
                                            "Budget ceiling exceeded (F-12 guardrail)")
                except Exception:
                    pass
        elif run["stopped_reason"] != "model_finished":
            state.outcome = f"HANDOFF_{run['stopped_reason'].upper()}"
        elif not all(c["passed"] for c in state.postconditions):
            state.outcome = "POSTCONDITION_FAILED"
        elif state.drafts_created:
            state.outcome = "DRAFT_READY"
            if state_mgr and session:
                try:
                    state_mgr.transition_to(session.session_id, WorkflowStage.DRAFTING_ORDER, "Draft created")
                    draft_tot = (state.draft or {}).get("estimated_budget_ugx", 0)
                    state_mgr.update_session(session.session_id, draft_id=state.drafts_created[0],
                                             draft_total_ugx=draft_tot, approval_status="AWAITING_APPROVAL")
                    state_mgr.transition_to(session.session_id, WorkflowStage.AWAITING_APPROVAL, "Waiting for human owner signature")
                except Exception:
                    pass
        elif state.plan is not None and not state.plan["included"]:
            state.outcome = ("NOTHING_FITS_BUDGET" if state.plan.get("deferred")
                             else "NEEDS_HUMAN" if state.plan.get("needs_human")
                             else "NOTHING_FITS_BUDGET")
            if state_mgr and session:
                try:
                    state_mgr.transition_to(
                        session.session_id, WorkflowStage.TERMINATED,
                        "Budget insufficient" if state.plan.get("deferred")
                        else "Human input required" if state.plan.get("needs_human")
                        else "Budget insufficient")
                except Exception:
                    pass
        else:
            state.outcome = "HANDOFF_NO_DRAFT"
            if state_mgr and session:
                try:
                    state_mgr.transition_to(session.session_id, WorkflowStage.TERMINATED, "Handoff to human")
                except Exception:
                    pass

        # Tell the approver if the agent's own checks failed on a draft it created.
        # F-26: drafts live in SQLite (storage.SQLiteStorage), not data/drafts/*.json any more.
        # run_agent() above uses the default shop/user scope, so the draft is read back with
        # the same scope; approvals.py then shows these agent_checks next to the draft.
        if state.drafts_created:
            storage = SQLiteStorage(procurement.STORAGE_PATH)
            record = storage.load_draft(state.drafts_created[0], tenant_id, user_id)
            if record is not None:
                record["agent_checks"] = {"outcome": state.outcome, "postconditions": state.postconditions,
                                          "budget_ugx": budget_ugx}
                storage.update_draft(record, tenant_id, user_id)

    state.handoffs = _handoffs(state)
    state.log("STOP", f"outcome {state.outcome}"
              + (f" (loop stop reason: {run['stopped_reason']})" if run else ""))

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "trace_name": save_trace_as,
        "outcome": state.outcome,
        "final_text": final_text,
        "state": {k: v for k, v in asdict(state).items() if not k.startswith("_")},
        "loop": ({k: run[k] for k in ("run_id", "stopped_reason", "turns_used", "models_used",
                                       "latency_s", "steps", "tool_calls", "output_warnings")}
                 if run else None),
        "limits": {"max_turns": MAX_TURNS, "max_tool_calls": MAX_TOOL_CALLS,
                   "tools": sorted(CONTRACT_TOOLS)},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with RUNS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")
    if save_trace_as:
        (OUT_DIR / f"trace_{save_trace_as}.json").write_text(json.dumps(record, indent=2, default=str),
                                                             encoding="utf-8")
        (OUT_DIR / f"trace_{save_trace_as}.md").write_text(render_trace_md(record), encoding="utf-8")
    _close_run_managers(state_mgr, mem_mgr)
    return record


# ---------------------------------------------------------------------------
# Readable trace (Markdown) for the report and the demo
# ---------------------------------------------------------------------------
def render_trace_md(record: dict) -> str:
    s, loop = record["state"], record["loop"] or {}
    lines = [
        f"# Execution trace - {record['trace_name']}",
        "",
        "| Field | Value |", "|:---|:---|",
        f"| Time (UTC) | {record['timestamp']} |",
        f"| Goal | {s['goal']} |",
        f"| Budget | UGX {s['budget_ugx']:,} |",
        f"| User | {s['user_name']} |",
        f"| Limits | {record['limits']['max_turns']} turns, {record['limits']['max_tool_calls']} tool calls, "
        f"tools {', '.join(record['limits']['tools'])} |",
        f"| Models used per turn | {', '.join(loop.get('models_used', [])) or '-'} |",
        f"| Turns / tool calls / latency | {loop.get('turns_used', 0)} / {len(loop.get('tool_calls', []))} / "
        f"{loop.get('latency_s', 0)} s |",
        f"| Loop stop reason | {loop.get('stopped_reason', '-')} |",
        f"| Output check warnings | {'; '.join(loop.get('output_warnings') or []) or 'none'} |",
        f"| **Outcome (decided by code)** | **{record['outcome']}** |",
        "",
        "## Timeline (Sense -> Plan/Decide -> Act -> Observe -> Re-plan -> Stop)", "",
        "| # | Time | Phase | Detail |", "|:---:|:---:|:---|:---|",
    ]
    for i, e in enumerate(s["timeline"], 1):
        lines.append(f"| {i} | {e['t']} | {e['phase']} | {e['detail'].replace('|', '/')} |")
    lines += ["", "## Hand-offs to the human", ""]
    lines += [f"- {h}" for h in s["handoffs"]] or ["- none"]
    lines += ["", "## Final answer shown to the user", "", "```text", record["final_text"], "```", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Weekly restock agent (Week 5)")
    ap.add_argument("--budget", type=int, required=True, help="budget in UGX, e.g. 300000")
    ap.add_argument("--user", default="shop user")
    ap.add_argument("--save-trace", default=None, help="name for evidence/week5/trace_<name>.md")
    a = ap.parse_args()

    rec = run_restock(a.budget, user_name=a.user, save_trace_as=a.save_trace)
    for e in rec["state"]["timeline"]:
        print(f"{e['t']}  {e['phase']:<14} {e['detail']}")
    print(f"\nOUTCOME: {rec['outcome']}\n")
    print(rec["final_text"])
    if rec["state"]["handoffs"]:
        print("\nNeeds a human:")
        for h in rec["state"]["handoffs"]:
            print(f"  - {h}")
