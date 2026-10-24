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
  list                      show the drafts saved in data/state.sqlite3 and their status
  show <draft_id>           print one draft's lines and totals
  edit <draft_id> --item ITM001 --qty 50 --by "Name" --reason "..."
                            change one line's quantity BEFORE deciding (User Story 9): the AI's
                            original suggestion and the reason are kept, totals and the 200% cap
                            are recalculated in Python, and the edit is written to the audit log
  approve <draft_id> --by "Name" [--reason "..."]
  reject  <draft_id> --by "Name"  --reason "..."     (a reason is mandatory, AC 10.3)

Rules enforced:
  - only a draft whose status is "DRAFT - AWAITING HUMAN APPROVAL" can be decided (no double decisions)
  - rejecting needs a reason (User Story 10, AC 10.3)
  - approving a draft with a line over the 200% cap needs an override reason (User Story 12)
  - every decision is appended to the audit_events table in data/state.sqlite3
    (User Story 11, AC 11.3)

Approving here does NOT order or pay anything: it only records the human decision.
Placing the order with the supplier stays a manual, offline step.

Usage (PowerShell, from the repo root):
  py src\\approvals.py list
  py src\\approvals.py show REQ-20261002-060439-887D
  py src\\approvals.py approve REQ-20261002-060439-887D --by "Shop Owner"

WHERE THE DRAFTS LIVE (v1.2.0, failure F-26)
----------------------------------------------
draft_requisition() saves every draft through storage.SQLiteStorage into
data/state.sqlite3, scoped to one shop (tenant_id) and one user (user_id).
Until v1.2.0 this file still read data/drafts/REQ-*.json, so after the Week 6
merge the human could not see any draft the agent created. This file now reads
and writes the same SQLite store as the tool, so the two can never drift apart.

Owner: Mwesigwa Arnold Mugahi (AI Engineering Lead); storage port: Boonabaana Bronia
Version: 1.2.0 (F-26: drafts and audit events read from SQLite storage)
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
import argparse                               # command-line arguments (list/show/approve/reject)
from datetime import datetime, timezone       # decision timestamps

from guardrails import (BudgetCeilingGuardrail, GuardrailViolation,   # Week 7 guardrails
                        HumanInTheLoopGuardrail)
from storage import DEFAULT_TENANT_ID, DEFAULT_USER_ID, SQLiteStorage   # Week 6 scoped store
from tools import procurement                 # reuse STORAGE_PATH and DRAFT_STATUS so they never drift apart

# Shown in CLI messages so the person knows where their decision was recorded.
AUDIT_LOG_NAME = "the audit_events table (data/state.sqlite3)"


class ApprovalError(Exception):
    """A decision that is not allowed (unknown draft, already decided, missing reason)."""


# ---------------------------------------------------------------------------
# Storage helpers (F-26: the same SQLite store that draft_requisition writes to)
# ---------------------------------------------------------------------------
def _storage() -> SQLiteStorage:
    # Read procurement.STORAGE_PATH at call time so tests can point it at a temporary database.
    return SQLiteStorage(procurement.STORAGE_PATH)


def load_draft(draft_id: str, tenant_id: str = DEFAULT_TENANT_ID,
               user_id: str = DEFAULT_USER_ID) -> dict:
    """Read one draft of this shop and user from SQLite, or raise ApprovalError if there is none."""
    # load_draft filters on draft_id AND tenant_id AND user_id, so another shop's draft
    # is reported as "not found" rather than shown (Week 6 tenant isolation).
    draft = _storage().load_draft(draft_id, tenant_id, user_id)
    if draft is None:
        raise ApprovalError(f"No draft named {draft_id} for this shop in {procurement.STORAGE_PATH}")
    return draft


def list_drafts(tenant_id: str = DEFAULT_TENANT_ID, user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """All drafts of this shop and user, newest first, as short summaries."""
    storage = _storage()
    summaries = storage.list_drafts(tenant_id, user_id)       # already sorted newest first
    for summary in summaries:
        # The summary row has no lines; count them from the full draft for the CLI listing.
        draft = storage.load_draft(summary["draft_id"], tenant_id, user_id)
        summary["lines"] = len(draft["lines"]) if draft else 0
        summary["requires_override_any"] = bool(summary["requires_override_any"])
    return summaries


# ---------------------------------------------------------------------------
# The decision itself
# ---------------------------------------------------------------------------
def decide(draft_id: str, decision: str, decided_by: str, reason: str = "",
           actor_role: str = "HUMAN_OWNER", tenant_id: str = DEFAULT_TENANT_ID,
           user_id: str = DEFAULT_USER_ID) -> dict:
    """
    Record a human decision on a draft. decision is "APPROVED" or "REJECTED".

    Returns the updated draft. Raises ApprovalError if a rule is broken.
    This function is called by the command line below (and by tests), never by the AI.

    Week 8 hardening (Failure Modes F-19, F-24 and the F-12 closure):
      - actor_role is checked against the human-only guardrail, so the function
        itself refuses to record a decision for an AI actor;
      - the allocated budget of the originating session is a HARD ceiling: a
        draft that is over budget cannot be approved (F-12);
      - the decision also advances the Week 6 state machine, so the session
        moves AWAITING_APPROVAL -> APPROVED / REJECTED and the audit trail
        records the human's signature (F-24).
    """
    # --- the human-only boundary, checked before anything is written ---
    HumanInTheLoopGuardrail.verify_action_permitted("approve_requisition", actor_role)

    if decision not in ("APPROVED", "REJECTED"):
        raise ApprovalError("decision must be APPROVED or REJECTED")
    if not decided_by.strip():
        raise ApprovalError("the approver's name is required (--by)")

    draft = load_draft(draft_id, tenant_id, user_id)
    if draft["status"] != procurement.DRAFT_STATUS:
        raise ApprovalError(f"{draft_id} is already {draft['status']}; decisions cannot be changed")
    if decision == "REJECTED" and not reason.strip():
        raise ApprovalError("a reason is required to reject a draft (AC 10.3)")
    if decision == "APPROVED" and draft.get("requires_override_any") and not reason.strip():
        raise ApprovalError("this draft has a line above the 200% safety cap; "
                            "an override reason is required to approve it (US 12)")

    # --- F-12: the allocated budget is a hard ceiling, not a range ---
    # The session is the link between the draft file and the Week 6 state
    # machine (it stores the draft_id and the budget the owner allocated).
    state_mgr, session = None, None
    try:
        from state import StateManager            # Week 6 state machine (imported lazily)
        state_mgr = StateManager()
        session = state_mgr.find_session_by_draft_id(draft_id)
    except Exception:
        state_mgr, session = None, None
    if session is not None and decision == "APPROVED":
        try:
            BudgetCeilingGuardrail.verify_draft_within_budget(
                draft_total_ugx=int(draft.get("estimated_budget_ugx", 0)),
                allocated_budget_ugx=int(session.budget_ugx),
            )
        except GuardrailViolation as exc:
            raise ApprovalError(
                f"{exc} Edit the quantity first (py src\\approvals.py edit {draft_id} "
                f"--item ITMxxx --qty N --by \"Name\" --reason \"...\")."
            ) from exc
        # F-12, second half: the draft also carries an ADVISORY estimate band
        # (User Story 8, about +/-10%). That band may reach above the money the
        # owner allocated even when the exact total fits. The approver must see
        # it and say so, so a band above the budget needs an explicit reason.
        band_high = int((draft.get("budget_range_ugx") or {}).get("high", 0))
        if band_high > int(session.budget_ugx) and not reason.strip():
            raise ApprovalError(
                f"the estimate band reaches UGX {band_high:,}, above the allocated budget "
                f"UGX {int(session.budget_ugx):,}. Approve with a --reason that says the extra "
                f"headroom is accepted, or edit a quantity first."
            )

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    draft["status"] = decision
    draft["decision"] = {"decision": decision, "decided_by": decided_by, "decided_at": now,
                         "reason": reason}
    storage = _storage()
    storage.update_draft(draft, tenant_id, user_id)                          # update the draft
    storage.append_audit({"timestamp": now, "draft_id": draft_id, "decision": decision,   # audit trail
                          "event_type": decision, "decided_by": decided_by, "reason": reason,
                          "estimated_budget_ugx": draft["estimated_budget_ugx"],
                          "estimate_band_high_ugx": (draft.get("budget_range_ugx") or {}).get("high"),
                          "allocated_budget_ugx": (session.budget_ugx if session else None),
                          "session_id": (session.session_id if session else None)},
                         tenant_id, user_id, draft_id)

    # Record feedback into persistent SQLite memory (Week 6 justified memory use case)
    try:
        from memory import MemoryManager, MemoryType
        mem_mgr = MemoryManager()
        mem_mgr.store_memory(
            # Keep learned approval preferences inside the same business boundary.
            shop_id=("default_shop" if tenant_id == DEFAULT_TENANT_ID else tenant_id),
            memory_type=MemoryType.APPROVAL_FEEDBACK,
            target_key=draft_id,
            summary=f"Owner {decision} {draft_id}: {reason or 'Approved as suggested'}",
            details=(f"Requisition total: UGX {draft.get('estimated_budget_ugx', 0):,}. "
                     f"Decided by {decided_by}. Reason: {reason or 'No override required'}."),
            source_session_id=draft.get("session_id"),
            created_by=decided_by
        )
    except Exception:
        pass

    # --- F-24: the human decision also advances the Week 6 workflow state ---
    if state_mgr is not None and session is not None:
        try:
            from state import WorkflowStage
            target = (WorkflowStage.APPROVED if decision == "APPROVED"
                      else WorkflowStage.REJECTED)
            state_mgr.update_session(session.session_id, approval_status=decision)
            state_mgr.transition_to(
                session.session_id, target,
                reason=f"Human decision by {decided_by}",
                metadata={"draft_id": draft_id, "decided_by": decided_by, "reason": reason},
            )
        except Exception:
            # The decision is already recorded on the draft and in the audit log;
            # a state-machine problem must not lose the human's decision.
            pass
        finally:
            try:
                state_mgr.close()
            except Exception:
                pass

    return draft


# ---------------------------------------------------------------------------
# Editing a quantity before the decision (User Story 9)
# ---------------------------------------------------------------------------
def edit_quantity(draft_id: str, item_id: str, new_qty: int, edited_by: str, reason: str,
                  tenant_id: str = DEFAULT_TENANT_ID, user_id: str = DEFAULT_USER_ID) -> dict:
    """
    Change the quantity of one line in a draft that is still awaiting approval.

    AC 9.1: the requisition quantity is updated.
    AC 9.2: the override and the original AI suggestion are logged (in the line and the audit log).
    Totals, the +/-10% range and the 200% cap flag are recalculated here, never by the AI.
    """
    if not isinstance(new_qty, int) or isinstance(new_qty, bool) or new_qty < 0:
        raise ApprovalError("the new quantity must be a whole number of 0 or more")
    if not edited_by.strip() or not reason.strip():
        raise ApprovalError("both --by and --reason are required to change a quantity (AC 9.2)")

    draft = load_draft(draft_id, tenant_id, user_id)
    if draft["status"] != procurement.DRAFT_STATUS:
        raise ApprovalError(f"{draft_id} is already {draft['status']}; it can no longer be edited")
    line = next((l for l in draft["lines"] if l["item_id"].upper() == item_id.upper()), None)
    if line is None:
        raise ApprovalError(f"{item_id} is not a line in {draft_id}")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    old_qty = line["recommended_qty"]
    line.setdefault("ai_suggested_qty", old_qty)                     # the AI's original, kept forever
    line.setdefault("edits", []).append({"from": old_qty, "to": new_qty, "by": edited_by,
                                         "at": now, "reason": reason})
    line["recommended_qty"] = new_qty
    line["total_cost_ugx"] = new_qty * line["unit_price_ugx"]       # exact integer maths
    cap = line.get("safety_cap")
    if cap is not None:                                              # re-check the 200% cap
        line["requires_override"] = new_qty > cap
        line["override_reason"] = (f"{new_qty} exceeds 200% cap of {cap}; human must justify"
                                   if new_qty > cap else "")

    total = sum(l["total_cost_ugx"] for l in draft["lines"])
    draft["estimated_budget_ugx"] = total
    draft["budget_range_ugx"] = {"low": (total * 9 + 5) // 10, "high": (total * 11 + 5) // 10}
    draft["requires_override_any"] = any(l.get("requires_override") for l in draft["lines"])
    if draft.get("agent_checks"):
        draft["agent_checks"]["note"] = "draft edited by a human after the agent's checks"

    storage = _storage()
    storage.update_draft(draft, tenant_id, user_id)
    storage.append_audit({"timestamp": now, "draft_id": draft_id, "decision": "EDITED",
                          "event_type": "EDITED", "item_id": line["item_id"],
                          "from": old_qty, "to": new_qty,
                          "ai_suggested_qty": line["ai_suggested_qty"], "decided_by": edited_by,
                          "reason": reason, "estimated_budget_ugx": total},
                         tenant_id, user_id, draft_id)
    return draft


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------
def _print_draft(d: dict) -> None:
    print(f"{d['draft_id']}  status: {d['status']}  created by {d['created_by']} at {d['created_at']}")
    for line in d["lines"]:
        flag = "  [OVER 200% CAP]" if line["requires_override"] else ""
        if "ai_suggested_qty" in line:
            flag += f"  [edited; AI suggested {line['ai_suggested_qty']}]"
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
    edit = sub.add_parser("edit")
    edit.add_argument("draft_id")
    edit.add_argument("--item", required=True, help="item ID of the line, e.g. ITM001")
    edit.add_argument("--qty", required=True, type=int, help="new quantity")
    edit.add_argument("--by", required=True)
    edit.add_argument("--reason", required=True)
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
        elif args.command == "edit":
            d = edit_quantity(args.draft_id, args.item, args.qty, args.by, args.reason)
            _print_draft(d)
            print(f"Edited {args.item} (recorded in {AUDIT_LOG_NAME}). The draft still needs a decision.")
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
