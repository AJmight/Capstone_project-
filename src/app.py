"""
SME Procurement Assistant - MVP console app (Weeks 1-5 in one place).
=====================================================================

ONE entry point for the whole system so far. It adds NO new business logic: every
menu option calls a function that already exists and is tested:

  1. Ask the assistant        -> tool_agent.run_agent()        (Week 4: tools + function calling)
  2. Weekly restock           -> restock_agent.run_restock()   (Week 5: bounded goal-directed agent)
  3. Policy question (RAG)    -> rag.policy_qa.answer_policy_question()   (Week 3: grounded answers)
  4. Review drafts            -> approvals.list_drafts / edit_quantity / decide   (human approval gate)
  5. Stock overview           -> tools.procurement.get_inventory()   (no AI, instant)

WHO YOU ARE
-----------
At start you type your name and pick a role (viewer / staff / owner). This is a demo
"login" only - there are no passwords yet (a known limitation for Week 7/8). The role
decides which tools the AI may use, and only the owner can approve or reject drafts here.

For the App/Integration Lead: a web UI (e.g. Streamlit or Flask) should call the same five
functions; nothing in this file needs to be copied except the menu flow.

Usage (PowerShell, repo root, venv active):
  py src\\app.py

Owner: Mwesigwa Arnold Mugahi (AI Engineering Lead)
Version: 0.5.0 (MVP up to Week 5)
"""

# ---------------------------------------------------------------------------
# Imports (heavy modules that need the API key are imported only when used)
# ---------------------------------------------------------------------------
import approvals                               # human approval gate (no AI)
from tools import procurement                  # deterministic tools (no AI)

ROLES = ("viewer", "staff", "owner")


def ask(prompt: str, default: str = "") -> str:
    """input() with a default value shown in brackets."""
    value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return value or default


# ---------------------------------------------------------------------------
# Menu actions
# ---------------------------------------------------------------------------
def action_ask(user: str, role: str) -> None:
    from tool_agent import run_agent           # needs GEMINI_API_KEY
    question = ask("Your question (e.g. 'Which items are low on stock?')")
    if not question:
        return
    out = run_agent(question, role=role, user_name=user)
    for c in out["tool_calls"]:
        print(f"  [tool] {c['name']}({c['args']}) -> {c['status']}")
    print("\n" + out["final_text"])
    print(f"\n(models: {', '.join(out['models_used'])} | stop: {out['stopped_reason']} | run {out['run_id']})")


def action_restock(user: str, role: str) -> None:
    from restock_agent import run_restock      # needs GEMINI_API_KEY
    budget = ask("Weekly budget in UGX", "300000").replace(",", "")
    if not budget.isdigit():
        print("Budget must be a whole number, e.g. 300000.")
        return
    rec = run_restock(int(budget), user_name=user, role=role)
    for e in rec["state"]["timeline"]:
        print(f"  {e['phase']:<14} {e['detail'][:110]}")
    print(f"\nOUTCOME: {rec['outcome']}\n\n{rec['final_text']}")
    if rec["state"]["handoffs"]:
        print("\nNeeds a human decision:")
        for h in rec["state"]["handoffs"]:
            print(f"  - {h}")


def action_policy(user: str, role: str) -> None:
    from rag.policy_qa import answer_policy_question   # needs GEMINI_API_KEY
    question = ask("Policy question (e.g. 'Who approves a UGX 800,000 requisition?')")
    if not question:
        return
    r = answer_policy_question(question)
    print("\n" + r["answer"])
    for s in r["sources"]:
        print(f"  [{s['label']}] {s['chunk_id']}")
    print(f"(model: {r['model'] or 'none - nothing relevant found'} | citations ok: {r['check']['citations_ok']})")


def action_review(user: str, role: str) -> None:
    drafts = approvals.list_drafts()
    if not drafts:
        print("No drafts yet.")
        return
    for n, d in enumerate(drafts, 1):
        print(f"  {n}. {d['draft_id']}  {d['status']:<32} UGX {d['estimated_budget_ugx']:,}  by {d['created_by']}")
    pick = ask("Number to open (Enter to go back)")
    if not pick.isdigit() or not 1 <= int(pick) <= len(drafts):
        return
    draft_id = drafts[int(pick) - 1]["draft_id"]
    approvals._print_draft(approvals.load_draft(draft_id))
    if role != "owner":
        print("\nOnly the owner can edit, approve or reject drafts.")
        return
    choice = ask("e = edit a quantity, a = approve, r = reject, Enter = back").lower()
    try:
        if choice == "e":
            item = ask("Item ID (e.g. ITM001)")
            qty = int(ask("New quantity"))
            approvals._print_draft(approvals.edit_quantity(draft_id, item, qty, user, ask("Reason")))
        elif choice in ("a", "r"):
            decision = "APPROVED" if choice == "a" else "REJECTED"
            word = "APPROVE" if choice == "a" else "REJECT"
            reason = ask("Reason (required to reject, or for over-cap lines)")
            if ask(f"Type {word} to confirm") != word:
                print("Cancelled - nothing changed.")
                return
            d = approvals.decide(draft_id, decision, user, reason)
            print(f"{d['draft_id']} is now {d['status']}.")
    except (approvals.ApprovalError, ValueError) as e:
        print(f"Not allowed: {e}")


def action_stock(user: str, role: str) -> None:
    category = ask("Category (Stationery / Office / Electronics, Enter for all)") or None
    r = procurement.get_inventory(category)
    if "error" in r:
        print(r["error"])
        return
    for i in r["items"]:
        flag = "  LOW" if i["is_low"] else ""
        print(f"  {i['item_id']} {i['item_name']:<26} stock {i['current_stock']:>3} / reorder {i['reorder_point']:>3}{flag}")


MENU = [("Ask the assistant (AI + tools)", action_ask),
        ("Weekly restock (bounded agent)", action_restock),
        ("Policy question (RAG with citations)", action_policy),
        ("Review drafts (human approval)", action_review),
        ("Stock overview (no AI)", action_stock)]


def main() -> None:
    print("SME Procurement Assistant - MVP (AI supports, never decides)\n")
    user = ask("Your name", "staff user")
    role = ask("Role: viewer / staff / owner", "staff").lower()
    if role not in ROLES:
        print("Unknown role; using viewer (read-only).")
        role = "viewer"
    while True:
        print(f"\nLogged in as {user} ({role})")
        for n, (label, _) in enumerate(MENU, 1):
            print(f"  {n}. {label}")
        print("  0. Exit")
        choice = ask("Choose")
        if choice == "0":
            break
        if choice.isdigit() and 1 <= int(choice) <= len(MENU):
            try:
                MENU[int(choice) - 1][1](user, role)
            except KeyboardInterrupt:
                print("\n(cancelled)")
            except Exception as e:                # keep the app running; show the problem
                print(f"Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
