"""
Tool-calling agent loop (Week 4, the base for the Week 5 bounded agent).
========================================================================

WHAT HAPPENS WHEN YOU ASK A QUESTION
------------------------------------
    user question
        |
        v
    [1] model reads the question + the tool list it is allowed to use
        |
        +--> answers in text?  -> STOP (stopped_reason = "model_finished")
        |
        +--> asks for tool(s), e.g. estimate_reorder_quantity(item="ITM001")
                 |
                 v
    [2] tools/registry.py execute_tool(): allow-list -> permission -> argument check
        -> runs the Python function -> returns a result dict (or an error dict)
                 |
                 v
    [3] the result is added to the conversation and we go back to [1]

The model DECIDES which tool to use; Python DOES the work. The model only
explains results, so the numbers it reports come from Python, not from the
model's own arithmetic (this is the fix for failure F-04).

LIMITS (bounded autonomy - the agent cannot run forever)
--------------------------------------------------------
  AGENT_MAX_TURNS       max model calls in one run              (default 6)
  AGENT_MAX_TOOL_CALLS  max tool executions in one run          (default 12)
  repeated-call guard   (Week 5) the same tool with the same arguments is blocked if it
                        already succeeded; a retryable failure (SERVICE_UNAVAILABLE) may be
                        retried exactly once
  model unavailable     every model in the fallback chain failed -> stop and tell the human
Each stop has a named reason in the result: model_finished | iteration_limit |
tool_call_limit | model_unavailable | empty_answer.

OUTPUT CHECK (Week 5, failure F-13)
-----------------------------------
After the model's final answer, code checks it does not CLAIM a draft that does not
exist (the "Status: DRAFT - AWAITING HUMAN APPROVAL" line, or a REQ-... ID that was not
created in this run). If it does, the claim is corrected and the run is flagged in
"output_warnings". This was added after a viewer (who cannot draft) was shown a
draft-like summary built from read-only tools.

TRACES
------
Every run is appended to evidence/week4/agent_traces.jsonl (question, role,
each turn's model, every tool call with arguments and result, final answer,
stop reason). Each tool call is also in evidence/week4/tool_traces.jsonl.

Usage (PowerShell, from the repo root):
  py src\\tool_agent.py "Which items are low on stock?"
  py src\\tool_agent.py "Draft a requisition for Bic Pens" --role staff --user "Arnold"

Owner: Mwesigwa Arnold Mugahi (AI Engineering Lead)
Version: 1.2.0 (Week 5: per-turn steps, repeated-call guard, observer hook, output check)
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
import argparse                               # command-line interface at the bottom
import json                                   # write the agent trace
import os                                     # read limits from .env
import re                                     # output check: find draft IDs in the answer
import time                                   # run latency
import uuid                                   # unique ID per run (links agent + tool traces)
from datetime import datetime, timezone       # trace timestamps
from pathlib import Path                      # file paths

from google.genai import types                # SDK request/response types

from ai_engine import load_system_prompt      # reads only the BEGIN/END part of a prompt file
from llm_client import AllModelsFailedError, MODELS, call_with_fallback, client
from tools.registry import RETRYABLE_ERRORS, execute_tool, tool_declarations_for

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROMPT_PATH = Path("prompts/procurement_assistant_v2.4.0.md")       # tool-mode prompt
MAX_TURNS = int(os.getenv("AGENT_MAX_TURNS", "6"))
MAX_TOOL_CALLS = int(os.getenv("AGENT_MAX_TOOL_CALLS", "12"))
TRACE_PATH = Path("evidence/week4/agent_traces.jsonl")

# Shown to the user when the agent has to stop without an answer (human hand-off).
HANDOFF_MESSAGES = {
    "iteration_limit": "I could not finish within the step limit, so I stopped. No requisition "
                       "was approved or sent. Please ask a more specific question or check manually.",
    "tool_call_limit": "I stopped because the request needed too many tool calls. Nothing was "
                       "approved or sent. Please narrow the request.",
    "model_unavailable": "The AI service is unavailable right now (all models busy or out of quota). "
                         "No action was taken. Please try again later.",
    "empty_answer": "The model returned no answer. No action was taken; please try again.",
}


def _call_key(name: str, args: dict) -> str:
    """A stable text key for 'this tool with these arguments' (dict order does not matter)."""
    return name + json.dumps(args, sort_keys=True, default=str)


def _model_text(response) -> str:
    """
    Any normal text the model wrote in this turn (e.g. 'I will check the budget first').
    Read from the parts directly: response.text warns when the turn also has tool calls.
    Hidden 'thought' parts are skipped.
    """
    try:
        parts = response.candidates[0].content.parts or []
    except (AttributeError, IndexError, TypeError):
        return ""
    return "".join(p.text for p in parts if getattr(p, "text", None) and not getattr(p, "thought", False)).strip()


DRAFT_ID_PATTERN = re.compile(r"REQ-\d{8}-\d{6}-[0-9A-F]{4}")
DRAFT_CLAIM_TEXT = "AWAITING HUMAN APPROVAL"
NO_DRAFT_NOTICE = ("\n\n**Note from the system:** no requisition was saved in this conversation. "
                   "The figures above are information only and are NOT waiting for approval.")


def check_output(final_text: str, drafts_created: list[str]) -> tuple[str, list[str]]:
    """
    Deterministic check of the model's final answer (does it claim a draft that does not exist?).
    Returns (possibly corrected text, list of warnings). Used by run_agent; unit-tested offline.
    """
    warnings = []
    unknown_ids = [i for i in DRAFT_ID_PATTERN.findall(final_text) if i not in drafts_created]
    if unknown_ids:
        warnings.append(f"answer mentions draft IDs not created in this run: {unknown_ids}")
    if DRAFT_CLAIM_TEXT in final_text.upper() and not drafts_created:
        warnings.append("answer claims a draft awaiting approval, but no draft was created")
    if warnings:
        # Remove the false status line and add a clear system notice.
        final_text = re.sub(r"(?im)^.*status:\s*draft\s*-\s*awaiting human approval.*$", "", final_text).rstrip()
        final_text += NO_DRAFT_NOTICE
    return final_text, warnings


def _write_trace(record: dict) -> None:
    """Append one run to evidence/week4/agent_traces.jsonl."""
    try:
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except OSError as e:
        print(f"[WARN] Could not write agent trace: {e}")


# ---------------------------------------------------------------------------
# The agent loop
# ---------------------------------------------------------------------------
def run_agent(user_message: str, role: str = "staff", user_name: str = "staff user",
              system_prompt: str | None = None, max_turns: int = MAX_TURNS,
              max_tool_calls: int = MAX_TOOL_CALLS, on_tool_result=None,
              trace_label: str = "tool_agent", allowed_tools: set[str] | None = None) -> dict:
    """
    Answer one user message, letting the model call tools, within strict limits.

    user_message  the question/request typed by the user
    role          viewer | staff | owner  (decides which tools the model may use)
    user_name     recorded as created_by on drafts (taken from the session, not the model)
    on_tool_result  optional function(name, args, result, status, turn, model, model_text)
                  called after every tool call; the Week 5 restock agent uses it to update
                  its explicit state and build its trace timeline
    allowed_tools optional TASK allow-list (Week 5). Only these tools are shown to the model,
                  and any other tool request is blocked with NOT_IN_TASK_CONTRACT, even if the
                  user's role would normally allow it
    trace_label   written into the run trace so different agents can be told apart
    Returns a dict: run_id, final_text, stopped_reason, turns_used, steps, tool_calls,
                    models_used, drafts_created, latency_s
    """
    run_id = uuid.uuid4().hex[:8]                       # short ID to find this run in the traces
    started = time.monotonic()
    system_prompt = system_prompt or load_system_prompt(PROMPT_PATH)

    # The tools this role may use, converted into the SDK's declaration objects.
    declarations = [types.FunctionDeclaration(**d) for d in tool_declarations_for(role)
                    if allowed_tools is None or d["name"] in allowed_tools]
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.1,
        tools=[types.Tool(function_declarations=declarations)] if declarations else None,
        # We run the tools ourselves (through the registry checks), so the SDK's
        # "automatic function calling" must be OFF.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    # The conversation so far. It starts with the user's message and grows with
    # each model turn (its tool requests) and each batch of tool results.
    contents: list[types.Content] = [types.Content(role="user", parts=[types.Part(text=user_message)])]

    tool_calls: list[dict] = []          # everything executed, for the result and the trace
    steps: list[dict] = []               # one entry per model turn: what it said and asked for
    call_history: dict[str, list[dict]] = {}   # results so far per (tool, args) - repeated-call guard
    models_used: list[str] = []          # which model answered each turn
    unusable: set[str] = set()           # models out of quota during THIS run
    final_text, stopped_reason, turn = "", "iteration_limit", 0

    for turn in range(1, max_turns + 1):
        # Prefer the model that answered the previous turn (see module docstring of llm_client).
        order = ([models_used[-1]] + [m for m in MODELS if m != models_used[-1]]) if models_used else None

        def request(model: str):
            return client.models.generate_content(model=model, contents=contents, config=config)

        try:
            response, model, _ = call_with_fallback(request, f"agent:{run_id}:turn{turn}", unusable, order)
        except AllModelsFailedError:
            stopped_reason = "model_unavailable"
            break
        models_used.append(model)

        calls = response.function_calls or []        # the tool requests in this turn (may be empty)
        steps.append({"turn": turn, "model": model, "model_text": _model_text(response),
                      "tool_requests": [{"name": c.name, "args": dict(c.args or {})} for c in calls]})
        if not calls:
            # No tool requested -> the model has written its answer.
            final_text = (response.text or "").strip()
            stopped_reason = "model_finished" if final_text else "empty_answer"
            break

        # Keep the model's turn EXACTLY as returned (it carries hidden "thought signatures"
        # that Gemini 3 needs to see again on the next turn).
        contents.append(response.candidates[0].content)

        result_parts = []
        for call in calls:
            args = dict(call.args or {})
            key = _call_key(call.name, args)
            previous = call_history.get(key, [])
            retry_allowed = (len(previous) == 1 and
                             str(previous[0].get("error", "")).startswith(RETRYABLE_ERRORS))
            if allowed_tools is not None and call.name not in allowed_tools:
                # Outside this task's contract (checked before the registry's role check).
                result, status = {"error": f"NOT_IN_TASK_CONTRACT: {call.name} is not allowed "
                                           f"for this task"}, "blocked"
            elif len(tool_calls) >= max_tool_calls:
                # Over budget: refuse to run more tools and tell the model why.
                result, status = {"error": "LIMIT: tool call budget for this request is used up"}, "blocked"
            elif previous and not retry_allowed:
                # Same tool, same arguments again: it would only waste budget (or loop forever).
                result, status = {"error": "REPEATED_CALL: you already called this tool with these "
                                           "arguments; use the earlier result"}, "blocked"
            else:
                result, status = execute_tool(call.name, args, role,
                                              context={"created_by": user_name}, run_id=run_id)
                call_history.setdefault(key, []).append(result)
            if on_tool_result:
                on_tool_result(call.name, args, result, status, turn, model, steps[-1]["model_text"])
            tool_calls.append({"turn": turn, "name": call.name, "args": args,
                               "status": status, "result": result})
            # Send the result back, matched to the request by id and name.
            result_parts.append(types.Part(function_response=types.FunctionResponse(
                id=call.id, name=call.name, response=result)))
        contents.append(types.Content(role="user", parts=result_parts))

        if len(tool_calls) >= max_tool_calls and turn < max_turns:
            # Give the model one last chance to answer with what it has, without tools.
            stopped_reason = "tool_call_limit"

    # If we stopped without an answer, give the user a clear hand-off message.
    if not final_text:
        final_text = HANDOFF_MESSAGES.get(stopped_reason, HANDOFF_MESSAGES["empty_answer"])

    drafts = [c["result"]["draft_id"] for c in tool_calls
              if c["name"] == "draft_requisition" and c["result"].get("draft_id")]

    # Output check: never let the answer claim a draft that does not exist (F-13).
    final_text, output_warnings = check_output(final_text, drafts)
    result = {
        "run_id": run_id,
        "final_text": final_text,
        "stopped_reason": stopped_reason,
        "turns_used": turn,
        "steps": steps,
        "tool_calls": tool_calls,
        "models_used": models_used,
        "drafts_created": drafts,
        "output_warnings": output_warnings,
        "latency_s": round(time.monotonic() - started, 2),
    }
    _write_trace({"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "agent": trace_label, "user_message": user_message, "role": role, "user_name": user_name,
                  "limits": {"max_turns": max_turns, "max_tool_calls": max_tool_calls}, **result})
    return result


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Ask the procurement agent a question")
    ap.add_argument("question", nargs="?", default="Which items are low on stock?")
    ap.add_argument("--role", default="staff", choices=["viewer", "staff", "owner"])
    ap.add_argument("--user", default="staff user", help="name recorded on drafts")
    args = ap.parse_args()

    out = run_agent(args.question, role=args.role, user_name=args.user)
    print(f"Run {out['run_id']} | models {out['models_used']} | {out['turns_used']} turn(s) | "
          f"stopped: {out['stopped_reason']} | {out['latency_s']}s")
    for c in out["tool_calls"]:
        print(f"  tool {c['name']}({c['args']}) -> {c['status']}")
    if out["drafts_created"]:
        print(f"  drafts saved: {out['drafts_created']}  (review with: py src\\approvals.py list)")
    print("\n" + out["final_text"])
