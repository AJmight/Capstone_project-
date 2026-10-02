"""
Weekly Restock Agent - the Week 5 bounded, goal-directed agent.
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
  0. PRECONDITIONS  (code)  role may draft? budget a positive whole number?
  1. SENSE          (code)  get_low_stock through the registry -> state.low_items
                            nothing low -> stop NOTHING_TO_DO (no model call needed)
  2. PLAN / DECIDE  (model) reads the goal + SENSE block, chooses the next tool
  3. ACT            (code)  registry runs the tool (allow-list, permissions, validation)
  4. OBSERVE        (code)  observe() updates the explicit AgentState after every result
     RE-PLAN                budget too small -> plan drops items (deferred); a temporary
                            failure -> one retry (recovery)
     ... back to 2 until the model writes its summary or a limit is hit ...
  5. POST-CONDITIONS (code) the draft must match the plan, stay within budget, be a DRAFT,
                            and the summary must say it awaits approval
  6. STOP           (code)  the OUTCOME is decided by code from the state, never by the
                            model's wording: DRAFT_READY, NOTHING_FITS_BUDGET, NOTHING_TO_DO,
                            PRECONDITION_FAILED, POSTCONDITION_FAILED, HANDOFF_<reason>

WHO DECIDES WHAT
----------------
  Python decides: what is low, every quantity/price/total, which items fit the budget
                  (plan_within_budget), the limits, and the final outcome.
  The model decides: which approved tool to call next, how to react to failures, and how
                  to explain the result to the human.
  The human decides: approve or reject the draft (src/approvals.py), the quantities of
                  "needs_human" items, and whether to fund deferred items.

LIMITS: max 5 model turns, max 6 tool calls, 3 tools only (task allow-list), the same
call may not be repeated (one retry allowed after SERVICE_UNAVAILABLE).

EVIDENCE: every run is appended to evidence/week5/restock_runs.jsonl; with --save-trace
a readable Markdown trace (+ JSON) is written to evidence/week5/.

Usage (PowerShell, repo root):
  py src\\restock_agent.py --budget 300000 --user "Mwesigwa Arnold Mugahi"
  py src\\restock_agent.py --budget 300000 --save-trace T2_budget_replan

Owner: Mwesigwa Arnold Mugahi (AI Engineering Lead)
Version: 1.0.0 (Week 5)
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
import argparse                               # command-line interface
import json                                   # traces
from dataclasses import asdict, dataclass, field   # the explicit AgentState
from datetime import datetime, timezone       # timestamps
from pathlib import Path                      # file paths

from tools import procurement                 # DRAFT_STATUS, DRAFTS_DIR
from tools.registry import ROLE_PERMISSIONS, execute_tool
from tool_agent import run_agent              # the bounded model <-> tool loop (Week 4, extended)

# ---------------------------------------------------------------------------
# The task contract in code (mirrors docs/requirements/agent-task-contract.md)
# ---------------------------------------------------------------------------
GOAL = ("Prepare ONE draft restock requisition within the budget and report everything that "
        "needs a human decision.")
CONTRACT_TOOLS = {"get_low_stock", "plan_within_budget", "draft_requisition"}   # task allow-list
MAX_TURNS = 5             # model calls per run
MAX_TOOL_CALLS = 6        # tool executions per run (plan, retry, draft, plus slack)
OUT_DIR = Path("evidence/week5")
RUNS_LOG = OUT_DIR / "restock_runs.jsonl"


# ---------------------------------------------------------------------------
# Explicit state: everything the agent knows, updated after each observation
# ---------------------------------------------------------------------------
@dataclass
class AgentState:
    goal: str
    budget_ugx: int
    role: str
    user_name: str
    phase: str = "START"                                  # START, SENSE, PLAN, DECIDE, ACT, OBSERVE, STOP
    low_items: list = field(default_factory=list)         # from SENSE (get_low_stock)
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
            self.log("OBSERVE", f"plan: include {inc} = UGX {result['planned_total_ugx']:,} of "
                                f"UGX {result['budget_ugx']:,}; deferred "
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
# The agent run
# ---------------------------------------------------------------------------
def run_restock(budget_ugx: int, user_name: str = "staff user", role: str = "staff",
                save_trace_as: str | None = None) -> dict:
    """Run the weekly restock task once. Returns the full run record (also logged)."""
    state = AgentState(goal=GOAL, budget_ugx=budget_ugx, role=role, user_name=user_name)
    run, final_text = None, ""

    # ---- 0. PRECONDITIONS (code) ----
    problems = []
    if "draft" not in ROLE_PERMISSIONS.get(role, set()):
        problems.append(f"role '{role}' may not create drafts")
    if not isinstance(budget_ugx, int) or isinstance(budget_ugx, bool) or budget_ugx <= 0:
        problems.append("budget must be a positive whole number of UGX")
    state.log("PRECONDITIONS", "ok" if not problems else "; ".join(problems))

    if problems:
        state.outcome = "PRECONDITION_FAILED"
        final_text = "Cannot start the restock task: " + "; ".join(problems) + "."
    else:
        # ---- 1. SENSE (code, through the registry so it is traced and permission-checked) ----
        sense, status = execute_tool("get_low_stock", {}, role, run_id="sense")
        if "error" in sense:
            state.log("SENSE", f"failed: {sense['error']}")
            state.outcome = "HANDOFF_SENSE_FAILED"
            final_text = f"Could not read the inventory ({sense['error']}). No action taken."
        else:
            state.low_items = sense["items"]
            state.log("SENSE", f"{sense['count']} low items: {[i['item_id'] for i in sense['items']]}")
            if not state.low_items:
                state.outcome = "NOTHING_TO_DO"
                final_text = "No items are at or below their reorder point. Nothing to restock."

    if not state.outcome:
        # ---- 2-4. PLAN/DECIDE -> ACT -> OBSERVE loop (model + registry) ----
        message = (f"[RESTOCK TASK]\nGoal: {GOAL}\nBudget: UGX {budget_ugx:,} (budget_ugx={budget_ugx})\n"
                   f"Requested by: {user_name}\n\n[SENSE]\n" + json.dumps(state.low_items, indent=1))
        run = run_agent(message, role=role, user_name=user_name, max_turns=MAX_TURNS,
                        max_tool_calls=MAX_TOOL_CALLS, on_tool_result=state.observe,
                        trace_label="restock_agent", allowed_tools=CONTRACT_TOOLS)
        final_text = run["final_text"]
        if run["steps"] and not run["steps"][-1]["tool_requests"]:
            state.log("PLAN/DECIDE", f"turn {run['steps'][-1]['turn']} ({run['steps'][-1]['model']}) "
                                     f"wrote the final summary (no more tools)")

        # ---- 5. POST-CONDITIONS (code) ----
        state.postconditions = check_postconditions(state, final_text)
        for c in state.postconditions:
            state.log("POSTCONDITION", f"{'PASS' if c['passed'] else 'FAIL'} - {c['check']}: {c['detail']}")

        # ---- 6. OUTCOME decided by code ----
        if run["stopped_reason"] != "model_finished":
            state.outcome = f"HANDOFF_{run['stopped_reason'].upper()}"
        elif not all(c["passed"] for c in state.postconditions):
            state.outcome = "POSTCONDITION_FAILED"
        elif state.drafts_created:
            state.outcome = "DRAFT_READY"
        elif state.plan is not None and not state.plan["included"]:
            state.outcome = "NOTHING_FITS_BUDGET"
        else:
            state.outcome = "HANDOFF_NO_DRAFT"

        # Tell the approver if the agent's own checks failed on a draft it created.
        if state.drafts_created:
            path = procurement.DRAFTS_DIR / f"{state.drafts_created[0]}.json"
            if path.exists():
                record = json.loads(path.read_text(encoding="utf-8"))
                record["agent_checks"] = {"outcome": state.outcome, "postconditions": state.postconditions,
                                          "budget_ugx": budget_ugx}
                path.write_text(json.dumps(record, indent=2), encoding="utf-8")

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
        f"| Role / user | {s['role']} / {s['user_name']} |",
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
    ap.add_argument("--user", default="staff user")
    ap.add_argument("--role", default="staff", choices=["viewer", "staff", "owner"])
    ap.add_argument("--save-trace", default=None, help="name for evidence/week5/trace_<name>.md")
    a = ap.parse_args()

    rec = run_restock(a.budget, user_name=a.user, role=a.role, save_trace_as=a.save_trace)
    for e in rec["state"]["timeline"]:
        print(f"{e['t']}  {e['phase']:<14} {e['detail']}")
    print(f"\nOUTCOME: {rec['outcome']}\n")
    print(rec["final_text"])
    if rec["state"]["handoffs"]:
        print("\nNeeds a human:")
        for h in rec["state"]["handoffs"]:
            print(f"  - {h}")
