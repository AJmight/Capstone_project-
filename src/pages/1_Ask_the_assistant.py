"""
Screen: Ask the assistant (AI + tools). Same as app.py menu option 1.
Calls tool_agent.run_agent() after the deterministic input guardrail.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # make "src" importable

import streamlit as st

import ui_common
from guardrails import GuardrailViolation, InputGuardrail

user = ui_common.setup_page("Ask the assistant", "💬",
                            "Ask about stock, suppliers or history. The AI picks a tool; Python does the maths.")

question = st.text_area("Your question", placeholder="Which items are low on stock?", max_chars=500)
if st.button("Ask", type="primary"):
    if not question.strip():
        st.warning("Please type a question first.")
    else:
        try:
            clean = InputGuardrail.validate_user_prompt(question)   # screen the user's own words first
        except GuardrailViolation as exc:
            st.error(f"Request refused by the input guardrail: {exc}")
            st.stop()
        try:
            from tool_agent import run_agent                        # needs GEMINI_API_KEY
            with st.spinner("Thinking..."):
                out = run_agent(clean, user_name=user)
        except Exception as exc:                                    # e.g. missing key or quota
            st.error(f"The assistant could not answer: {type(exc).__name__}: {exc}")
            st.stop()
        st.markdown(out["final_text"])
        with st.expander("Tools used"):
            for c in out["tool_calls"]:
                st.write(f"`{c['name']}({c['args']})` → {c['status']}")
        st.caption(f"models: {', '.join(out['models_used'])} | stop: {out['stopped_reason']} | run {out['run_id']}")
