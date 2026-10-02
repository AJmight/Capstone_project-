"""
Shared Gemini client with automatic model fallback.
===================================================

WHY THIS FILE EXISTS
--------------------
Every part of the project that talks to the AI model goes through this file.
That way the rules for "what to do when the model fails" live in ONE place
instead of being copy-pasted into every script.

THE FALLBACK POLICY
-------------------
  1. Try the primary model (GEMINI_PRIMARY_MODEL in .env, default gemini-3.8-flash).
  2. On ANY availability failure (503 busy, 429 quota, 5xx, timeout, network
     drop, 404 model not found) switch IMMEDIATELY to the next model listed in
     GEMINI_FALLBACK_MODELS (comma-separated in .env). All models share the same
     GEMINI_API_KEY, but Google counts the free-tier quota (20 requests/day)
     separately for each model, so a chain of models multiplies our capacity.
     (gemini-2.5-flash is NOT used: Google returns 404 "no longer available to
     new users" for our key.)
  3. If every model fails, wait a few seconds and run the whole chain again,
     up to LLM_MAX_ROUNDS times. A model whose DAILY quota is exhausted, or that
     returned 404, is skipped in later rounds because retrying cannot help.
  4. Errors that a different model cannot fix (bad API key, malformed request)
     are raised straight away so the developer sees them.

WHO CALLS WHAT
--------------
  - generate()            one-shot question -> text   (used by ai_engine.py, tests)
  - ChatSession.send()    multi-turn chat that remembers earlier turns
  - call_with_fallback()  low-level helper; tool_agent.py (Week 4) uses it
                          directly because the tool loop builds its own
                          conversation "contents" list.

OBSERVABILITY
-------------
Every call appends one JSON line to evidence/traces/llm_calls.jsonl with the
time, the models tried, each error and the latency. Prompt and response text
are deliberately NOT logged here (tool_agent.py keeps its own richer trace).

Owner: Mwesigwa Arnold Mugahi (AI Engineering Lead)
Version: 0.4.0 (Week 4: generic call_with_fallback for the tool loop)
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
import json                                   # write trace records as JSON lines
import os                                     # read settings from environment variables
import time                                   # measure latency and wait between rounds
from dataclasses import dataclass, field      # simple result container (LLMResult)
from datetime import datetime, timezone       # timestamps for the trace file
from pathlib import Path                      # file paths that work on Windows and Linux
from typing import Any, Callable              # type hints for the generic helper

import httpx                                  # the HTTP library the Gemini SDK uses (network errors)
from dotenv import load_dotenv                # loads key=value pairs from the .env file
from google import genai                      # official Google Gemini SDK (google-genai)
from google.genai import errors, types        # SDK error classes and request/response types

# Read .env into environment variables so os.getenv() below can see them.
load_dotenv()

# ---------------------------------------------------------------------------
# Settings (all come from .env; see .env.example for the full list)
# ---------------------------------------------------------------------------
API_KEY = os.getenv("GEMINI_API_KEY")

# Primary model. MODEL_NAME is the old Week 2 variable name, kept so old .env files still work.
PRIMARY_MODEL = os.getenv("GEMINI_PRIMARY_MODEL") or os.getenv("MODEL_NAME") or "gemini-3.8-flash"

# Fallback models, tried in this order. ".split(',')" turns "a,b,c" into ["a","b","c"];
# ".strip()" removes stray spaces; empty entries are dropped.
FALLBACK_MODELS = [m.strip() for m in (
    os.getenv("GEMINI_FALLBACK_MODELS")
    or os.getenv("GEMINI_FALLBACK_MODEL")      # old singular name, still accepted
    or "gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite"
).split(",") if m.strip()]

REQUEST_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))  # give up on one request after this
MAX_ROUNDS = int(os.getenv("LLM_MAX_ROUNDS", "3"))                 # how many times to walk the whole chain
TRACE_PATH = Path("evidence/traces/llm_calls.jsonl")               # where call records are appended

# The full ordered chain. dict.fromkeys() removes duplicates while keeping order,
# e.g. if someone lists the primary model in the fallback list too.
MODELS = list(dict.fromkeys([PRIMARY_MODEL, *FALLBACK_MODELS]))

# Fail early with a clear message instead of a confusing SDK error later.
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not set in .env")

# One shared SDK client for the whole program.
# - timeout is in milliseconds, so seconds * 1000.
# - retry_options is deliberately NOT set, so the SDK does not retry on its own;
#   this module decides when to retry or switch model.
client = genai.Client(
    api_key=API_KEY,
    http_options=types.HttpOptions(timeout=int(REQUEST_TIMEOUT_S * 1000)),
)

# HTTP status codes where another model (or a later retry) may succeed:
# 404 model not found, 408 timeout, 429 quota/rate limit, 5xx server problems.
SWITCH_CODES = {404, 408, 429, 500, 502, 503, 504}


# ---------------------------------------------------------------------------
# Error types and the result container
# ---------------------------------------------------------------------------
class EmptyResponseError(RuntimeError):
    """Raised when the model answers with no text at all (treated like a failure)."""


class AllModelsFailedError(RuntimeError):
    """Raised when every configured model failed in every round."""


@dataclass
class LLMResult:
    """What generate() / ChatSession.send() hand back to the caller."""
    text: str                                     # the model's answer
    model: str                                    # which model actually answered
    latency_s: float                              # total seconds including failed attempts
    attempts: list = field(default_factory=list)  # one dict per model tried (for traces/reports)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _classify(exc: Exception) -> tuple[bool, str]:
    """
    Decide what to do with an exception.

    Returns (switch_model, short_reason):
      switch_model = True  -> try the next model
      switch_model = False -> stop and raise (another model would not help)
    """
    # Errors returned by Google's API carry an HTTP code (e.g. 503) and a status name.
    if isinstance(exc, errors.APIError):
        code = getattr(exc, "code", None)
        status = getattr(exc, "status", "") or ""
        if code in SWITCH_CODES:
            # The 429 body names the quota that ran out; "PerDay" means the daily limit.
            if code == 429 and "PerDay" in str(exc):
                return True, f"{code} {status} (daily quota exhausted)"
            if code == 404:
                return True, f"{code} {status} (model not available to this key)"
            return True, f"{code} {status}".strip()
        # e.g. 400 bad request, 401/403 bad key: switching model will not fix these.
        return False, f"{code} {status}".strip()
    # Network problems on our side (WinError 10060/10053 on Windows show up as these).
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException, TimeoutError, ConnectionError)):
        return True, f"network: {type(exc).__name__}"
    if isinstance(exc, EmptyResponseError):
        return True, "empty response"
    # Anything else is probably a bug in our code: raise it.
    return False, f"{type(exc).__name__}: {exc}"


def _write_trace(record: dict) -> None:
    """Append one JSON line to the call trace. Never crash the program over logging."""
    try:
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)   # create evidence/traces/ if missing
        with TRACE_PATH.open("a", encoding="utf-8") as f:      # "a" = append, keep old lines
            f.write(json.dumps(record) + "\n")
    except OSError as e:
        print(f"[WARN] Could not write trace: {e}")


def _trace_record(label: str, model: str | None, attempts: list, outcome: str) -> dict:
    """Build the dictionary that becomes one line of llm_calls.jsonl."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "label": label,                  # who made the call, e.g. "TC-03" or "agent_turn_2"
        "outcome": outcome,              # success | fatal_error | all_models_failed
        "model_used": model,             # None if nothing succeeded
        "models_configured": MODELS,
        "attempts": attempts,
    }


# ---------------------------------------------------------------------------
# The core: run ONE request with the fallback policy
# ---------------------------------------------------------------------------
def call_with_fallback(request: Callable[[str], Any], label: str,
                       unusable_models: set[str] | None = None,
                       order: list[str] | None = None) -> tuple[Any, str, list]:
    """
    Run `request(model_name)` against each model in the chain until one succeeds.

    Parameters
    ----------
    request : a function that takes a model name, makes ONE API call with it,
              and returns the response. It should raise on failure.
              Example: lambda model: client.models.generate_content(model=model, ...)
    label   : short name written to the trace file.
    unusable_models : a set shared across several calls (e.g. all turns of one
              agent run) so a model that ran out of daily quota is not retried.
    order   : optional model order for THIS call (default: MODELS). tool_agent.py
              passes the model that answered turn 1 first, so one agent run
              stays on one model whenever possible.

    Returns (response, model_that_answered, attempts_list).
    Raises the original exception for non-switchable errors, or
    AllModelsFailedError if nothing worked after MAX_ROUNDS.
    """
    unusable = unusable_models if unusable_models is not None else set()
    chain = order or MODELS
    attempts: list[dict] = []

    for round_no in range(1, MAX_ROUNDS + 1):
        # Models still worth trying in this round.
        models = [m for m in chain if m not in unusable]
        if not models:
            break                                   # every model is out of quota / 404
        for model in models:
            t0 = time.monotonic()
            try:
                response = request(model)           # <-- the actual API call happens here
                attempts.append({"round": round_no, "model": model, "ok": True,
                                 "latency_s": round(time.monotonic() - t0, 2)})
                _write_trace(_trace_record(label, model, attempts, "success"))
                return response, model, attempts
            except Exception as exc:
                switch, reason = _classify(exc)
                attempts.append({"round": round_no, "model": model, "ok": False,
                                 "error": reason,
                                 "latency_s": round(time.monotonic() - t0, 2)})
                if not switch:
                    # Bad key, bad request or a bug: record it and stop immediately.
                    _write_trace(_trace_record(label, None, attempts, "fatal_error"))
                    raise
                if "daily quota" in reason or "not available" in reason:
                    unusable.add(model)             # do not waste time on it again
                nxt = "next model" if model != models[-1] else "end of round"
                print(f"[WARN] {model} failed ({reason}) -> {nxt}")
        # Whole chain failed this round. Wait a little before the next round,
        # but only if at least one model could still recover (e.g. a busy 503).
        if round_no < MAX_ROUNDS and any(m not in unusable for m in chain):
            wait = 5 * round_no                     # 5 s, then 10 s
            print(f"[WARN] All models failed in round {round_no}. "
                  f"Waiting {wait}s before round {round_no + 1}/{MAX_ROUNDS}...")
            time.sleep(wait)

    _write_trace(_trace_record(label, None, attempts, "all_models_failed"))
    summary = "; ".join(f"{a['model']}: {a['error']}" for a in attempts if not a["ok"])
    raise AllModelsFailedError(f"All models failed. {summary}")


# ---------------------------------------------------------------------------
# Multi-turn chat (Week 2 API, unchanged behaviour)
# ---------------------------------------------------------------------------
class ChatSession:
    """
    A multi-turn chat that survives model fallback.

    The conversation history is stored HERE (not inside one model's chat object),
    so if the primary model fails mid-conversation the fallback model continues
    with exactly the same history.
    """

    def __init__(self, system_prompt: str, json_mode: bool = False,
                 temperature: float = 0.1, label: str = "chat"):
        self.label = label
        self.history: list[types.Content] = []          # grows by 2 entries per turn (user + model)
        self.config = types.GenerateContentConfig(
            system_instruction=system_prompt,           # the versioned prompt from prompts/
            temperature=temperature,                    # 0.1 = very consistent answers
            # JSON mode makes Gemini return raw JSON only (used for analysis/requisitions).
            response_mime_type="application/json" if json_mode else None,
        )
        self.unusable_models: set[str] = set()          # shared across all turns of this chat

    def send(self, message: str) -> LLMResult:
        """Send one user message and return the model's reply (with fallback)."""
        start = time.monotonic()

        def request(model: str):
            # A fresh SDK chat object for whichever model we are trying, seeded with our history.
            chat = client.chats.create(model=model, config=self.config, history=self.history)
            response = chat.send_message(message)
            if not response.text:
                raise EmptyResponseError("Model returned an empty response.")
            return response, chat

        (response, chat), model, attempts = call_with_fallback(
            request, self.label, self.unusable_models)
        self.history = chat.get_history()               # save the new turn for next time
        return LLMResult(response.text, model, round(time.monotonic() - start, 2), attempts)


def generate(system_prompt: str, user_prompt: str, json_mode: bool = False,
             label: str = "single") -> LLMResult:
    """One-shot request: a fresh chat with no history. Used by ai_engine.py and tests."""
    return ChatSession(system_prompt, json_mode=json_mode, label=label).send(user_prompt)
