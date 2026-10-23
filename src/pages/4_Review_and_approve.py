"""
Screen: Review & approve drafts (human approval gate). Same as app.py menu option 4.
Uses approvals.list_drafts / load_draft / edit_quantity / decide. No AI here: only a
person can approve or reject, and must type the confirmation word (as in the console).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # make "src" importable

import streamlit as st

import approvals
import ui_common

user = ui_common.setup_page("Review & approve drafts", "✅",
                            "You edit, approve or reject every draft. The AI can never approve.")

drafts = approvals.list_drafts()
if not drafts:
    st.info("No drafts yet. Create one with Weekly restock or Ask the assistant.")
    st.stop()

labels = {f"{d['draft_id']} · {d['status']} · UGX {d['estimated_budget_ugx']:,} · by {d['created_by']}": d["draft_id"]
          for d in drafts}
draft_id = labels[st.selectbox("Draft", list(labels))]
d = approvals.load_draft(draft_id)

st.write(f"**Status:** {d['status']}  ·  created by {d['created_by']} at {d['created_at']}")
st.dataframe([{"Item ID": l["item_id"], "Item": l["item_name"], "Qty": l["recommended_qty"],
               "Unit price (UGX)": l["unit_price_ugx"], "Total (UGX)": l["total_cost_ugx"],
               "Supplier": l["selected_supplier"],
               "Note": ("OVER 200% CAP " if l["requires_override"] else "")
                       + (f"edited; AI suggested {l['ai_suggested_qty']}" if "ai_suggested_qty" in l else "")}
              for l in d["lines"]], hide_index=True, width="stretch")
for s in d.get("skipped", []):
    st.caption(f"Skipped {s['item_id']} {s['item_name']}: {s['reason']}")
st.write(f"**Estimated budget:** UGX {d['estimated_budget_ugx']:,} "
         f"(range {d['budget_range_ugx']['low']:,} – {d['budget_range_ugx']['high']:,})")

# ---- Edit a quantity ----
st.subheader("Edit a quantity")
c1, c2, c3 = st.columns([1, 1, 2])
item_id = c1.selectbox("Item", [l["item_id"] for l in d["lines"]])
qty = c2.number_input("New quantity", min_value=1, value=1, step=1)
edit_reason = c3.text_input("Reason for edit")
if st.button("Save edit"):
    try:
        approvals.edit_quantity(draft_id, item_id, int(qty), user, edit_reason)
        st.success("Edit saved and logged.")
        st.rerun()
    except (approvals.ApprovalError, ValueError) as e:
        st.error(f"Not allowed: {e}")

# ---- Approve / reject (typed confirmation, like the console) ----
st.subheader("Decide")
decision = st.radio("Decision", ["APPROVE", "REJECT"], horizontal=True)
reason = st.text_input("Reason (required to reject, or for over-cap lines)")
typed = st.text_input(f"Type {decision} to confirm")
if st.button("Submit decision", type="primary"):
    if typed != decision:
        st.warning("Confirmation word does not match. Nothing changed.")
    else:
        try:
            res = approvals.decide(draft_id, "APPROVED" if decision == "APPROVE" else "REJECTED", user, reason)
            st.success(f"{res['draft_id']} is now {res['status']}.")
        except approvals.ApprovalError as e:
            st.error(f"Not allowed: {e}")
