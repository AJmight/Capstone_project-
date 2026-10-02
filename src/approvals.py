"""
Human approval gate for draft requisitions (Week 4).
====================================================

WHY THIS FILE EXISTS
--------------------
The AI may only CREATE drafts (tools/procurement.py: draft_requisition). Turning a
draft into an approved or rejected requisition is a higher-impact action, so the
brief requires a human to do it. This script is that human step.

It is deliberately NOT a tool:
  - it is not in tools/registry.py TOOL_REGISTRY, so the model can never call it
    (asking for it returns UNAUTHORIZED_TOOL);
  - from the command line it asks the person to type the decision word
    (APPROVE / REJECT) before anything changes.

WHAT IT DOES
------------
  list                      show drafts in data/drafts/ and their status
  show <draft_id>           print one draft's lines and totals
  approve <draft_id> --by "Name" [--reason "..."]
  reject  <draft_id> --by "Name"  --reason "..."     (a reason is mandatory, AC 10.3)

Rules enforced:
  - only a draft whose status is "DRAFT - AWAITING HUMAN APPROVAL" can be decided (no double decisions)
  - rejecting needs a reason (User Story 10, AC 10.3)
  - approving a draft with a line over the 200% cap needs an override reason (User Story 12)
  - every decision is appended to data/drafts/audit_log.jsonl (User Story 11, AC 11.3)

Approving here does NOT order or pay anything: it only records the human decision.
Placing the order with the supplier stays a manual, offline step.

Usage (PowerShell, from the repo root):
  py src\\approvals.py list
  py src\\approvals.py show REQ-20261002-060439-887D
  py src\\approvals.py approve REQ-20261002-060439-887D --by "Shop Owner"

Owner: Mwesigwa Arnold Mugahi (AI Engineering Lead)
Version: 1.0.0 (Week 4)
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
import argparse                               # command-line arguments (list/show/approve/reject)
import json                                   # drafts and the audit log are JSON
from datetime import datetime, timezone       # decision timestamps
from pathlib import Path                      # file paths

from tools import procurement                 # reuse DRAFTS_DIR and DRAFT_STATUS so they never drift apart

AUDIT_LOG_NAME = "audit_log.jsonl"


class ApprovalError(Exception):
    """A decision that is not allowed (unknown draft, already decided, missing reason)."""


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------
def _drafts_dir() -> Path:
    # Read at call time so tests can point procurement.DRAFTS_DIR at a temporary folder.
    return procurement.DRAFTS_DIR


def load_draft(draft_id: str) -> dict:
    """Read data/drafts/<draft_id>.json, or raise ApprovalError if it does not exist."""
    path = _drafts_dir() / f"{draft_id}.json"
    if not path.exists():
        raise ApprovalError(f"No draft named {draft_id} in {_drafts_dir()}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_drafts() -> list[dict]:
    """All drafts, newest first, as short summaries."""
    folder = _drafts_dir()
    if not folder.exists():
        return []
    drafts = [json.loads(p.read_text(encoding="utf-8")) for p in folder.glob("REQ-*.json")]
    drafts.sort(key=lambda d: d["created_at"], reverse=True)
    return [{"draft_id": d["draft_id"], "created_at": d["created_at"], "created_by": d["created_by"],
             "status": d["status"], "lines": len(d["lines"]),
             "estimated_budget_ugx": d["estimated_budget_ugx"],
             "requires_override_any": d.get("requires_override_any", False)} for d in drafts]


# ---------------------------------------------------------------------------
# The decision itself
# ---------------------------------------------------------------------------
def decide(draft_id: str, decision: str, decided_by: str, reason: str = "") -> dict:
    """
    Record a human decision on a draft. decision is "APPROVED" or "REJECTED".

    Returns the updated draft. Raises ApprovalError if a rule is broken.
    This function is called by the command line below (and by tests), never by the AI.
    """
    if decision not in ("APPROVED", "REJECTED"):
        raise ApprovalError("decision must be APPROVED or REJECTED")
    if not decided_by.strip():
        raise ApprovalError("the approver's name is required (--by)")

    draft = load_draft(draft_id)
    if draft["status"] != procurement.DRAFT_STATUS:
        raise ApprovalError(f"{draft_id} is already {draft['status']}; decisions cannot be changed")
    if decision == "REJECTED" and not reason.strip():
        raise ApprovalError("a reason is required to reject a draft (AC 10.3)")
    if decision == "APPROVED" and draft.get("requires_override_any") and not reason.strip():
        raise ApprovalError("this draft has a line above the 200% safety cap; "
                            "an override reason is required to approve it (US 12)")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    draft["status"] = decision
    draft["decision"] = {"decision": decision, "decided_by": decided_by, "decided_at": now,
                         "reason": reason}
    path = _drafts_dir() / f"{draft_id}.json"
    path.write_text(json.dumps(draft, indent=2), encoding="utf-8")          # update the draft

    with (_drafts_dir() / AUDIT_LOG_NAME).open("a", encoding="utf-8") as f:  # audit trail
        f.write(json.dumps({"timestamp": now, "draft_id": draft_id, "decision": decision,
                            "decided_by": decided_by, "reason": reason,
                            "estimated_budget_ugx": draft["estimated_budget_ugx"]}) + "\n")
    return draft


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------
def _print_draft(d: dict) -> None:
    print(f"{d['draft_id']}  status: {d['status']}  created by {d['created_by']} at {d['created_at']}")
    for line in d["lines"]:
        flag = "  [OVER 200% CAP]" if line["requires_override"] else ""
        print(f"  {line['item_id']} {line['item_name']:<24} qty {line['recommended_qty']:>4} "
              f"x UGX {line['unit_price_ugx']:,} = UGX {line['total_cost_ugx']:,} "
              f"({line['selected_supplier']}){flag}")
    for s in d.get("skipped", []):
        print(f"  skipped {s['item_id']} {s['item_name']}: {s['reason']}")
    print(f"  Estimated budget: UGX {d['estimated_budget_ugx']:,} "
          f"(range {d['budget_range_ugx']['low']:,} - {d['budget_range_ugx']['high']:,})")


def main() -> None:
    ap = argparse.ArgumentParser(description="Human approval of AI-drafted requisitions")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    show = sub.add_parser("show")
    show.add_argument("draft_id")
    for name in ("approve", "reject"):
        p = sub.add_parser(name)
        p.add_argument("draft_id")
        p.add_argument("--by", required=True, help="name of the person deciding")
        p.add_argument("--reason", default="")
    args = ap.parse_args()

    try:
        if args.command == "list":
            for d in list_drafts():
                print(f"{d['draft_id']}  {d['status']:<32} {d['lines']} line(s)  "
                      f"UGX {d['estimated_budget_ugx']:,}  by {d['created_by']}"
                      + ("  [needs override reason]" if d["requires_override_any"] else ""))
        elif args.command == "show":
            _print_draft(load_draft(args.draft_id))
        else:
            decision = "APPROVED" if args.command == "approve" else "REJECTED"
            _print_draft(load_draft(args.draft_id))
            # The human must type the word: protects against a slip of the keyboard or a script.
            word = "APPROVE" if decision == "APPROVED" else "REJECT"
            typed = input(f"\nType {word} to confirm: ").strip()
            if typed != word:
                print("Cancelled - nothing changed.")
                return
            d = decide(args.draft_id, decision, args.by, args.reason)
            print(f"{d['draft_id']} is now {d['status']} (recorded in {AUDIT_LOG_NAME})")
    except ApprovalError as e:
        print(f"Not allowed: {e}")


if __name__ == "__main__":
    main()
