"""
Screen: Policy questions (RAG with citations). Same as app.py menu option 3.
Calls rag.policy_qa.answer_policy_question() after the input guardrail.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # make "src" importable

import streamlit as st

import ui_common
from guardrails import GuardrailViolation, InputGuardrail

ui_common.setup_page("Policy questions", "📘",
                     "Answers from the shop's own policy documents, with sources cited.", need_user=False)

question = st.text_area("Policy question", placeholder="Who approves a UGX 800,000 requisition?", max_chars=500)
if st.button("Ask", type="primary"):
    if not question.strip():
        st.warning("Please type a question first.")
    else:
        try:
            clean = InputGuardrail.validate_user_prompt(question)
        except GuardrailViolation as exc:
            st.error(f"Request refused by the input guardrail: {exc}")
            st.stop()
        try:
            from rag.policy_qa import answer_policy_question        # needs GEMINI_API_KEY
            with st.spinner("Searching the policies..."):
                r = answer_policy_question(clean)
        except Exception as exc:
            st.error(f"The policy assistant could not answer: {type(exc).__name__}: {exc}")
            st.stop()
        st.markdown(r["answer"])
        if r["sources"]:
            with st.expander("Sources"):
                for s in r["sources"]:
                    st.write(f"[{s['label']}] {s['chunk_id']}")
        st.caption(f"model: {r['model'] or 'none - nothing relevant found'} | "
                   f"citations ok: {r['check']['citations_ok']}")
