"""
Screen: Weekly restock (bounded agent). Same as app.py menu option 2.
Calls restock_agent.run_restock() after the deterministic budget guardrail.
The agent only DRAFTS; approving happens on the Review & approve screen.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # make "src" importable

import streamlit as st

import ui_common
from guardrails import GuardrailViolation, InputGuardrail

user = ui_common.setup_page("Weekly restock", "🔄",
                            "Give a budget. A bounded agent plans what fits and drafts one requisition.")

budget = st.number_input("Weekly budget (UGX)", min_value=0, value=300000, step=10000)
if st.button("Plan restock", type="primary"):
    try:
        budget_ugx = InputGuardrail.validate_budget(int(budget))    # hard ceiling, validated in code
    except GuardrailViolation as exc:
        st.error(f"Budget refused by the guardrail: {exc}")
        st.stop()
    try:
        from restock_agent import run_restock                       # needs GEMINI_API_KEY
        with st.spinner("Planning..."):
            rec = run_restock(budget_ugx, user_name=user)
    except Exception as exc:
        st.error(f"The restock agent could not run: {type(exc).__name__}: {exc}")
        st.stop()
    st.subheader(f"Outcome: {rec['outcome']}")
    st.markdown(rec["final_text"])
    with st.expander("Agent timeline"):
        for e in rec["state"]["timeline"]:
            st.write(f"**{e['phase']}** {e['detail'][:200]}")
    if rec["state"]["handoffs"]:
        st.warning("Needs a human decision:\n\n" + "\n".join(f"- {h}" for h in rec["state"]["handoffs"]))
    st.page_link("pages/4_Review_and_approve.py", label="Review the draft", icon="✅")
