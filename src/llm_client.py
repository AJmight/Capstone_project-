"""
Shared Gemini client with automatic model fallback.

Every module that talks to the model goes through this file, so the
fallback policy lives in one place:

  1. Try the primary model (GEMINI_PRIMARY_MODEL, default gemini-3.8-flash).
  2. On ANY availability failure (503 busy, 429 quota, 5xx, timeout,
     network drop, model not found) switch IMMEDIATELY to the next model in
     GEMINI_FALLBACK_MODELS (comma-separated, default
     gemini-3.7-flash ... gemini-3.1-flash-lite). All models use the same
     GEMINI_API_KEY; free-tier quotas are counted per model.
     (gemini-2.5-flash cannot be used: Google returns 404 "no longer
     available to new users" for new free-tier keys.)
  3. If every model fails, wait and run the whole chain again, up to
     LLM_MAX_ROUNDS times. A model whose DAILY quota is exhausted, or that
     returned 404, is skipped in later rounds (retrying cannot help).
  4. Errors that a different model cannot fix (bad API key, bad request)
     are raised straight away.

Every call is appended to evidence/traces/llm_calls.jsonl
(timestamp, models tried, errors, latency) for observability evidence.
Prompt and response text are NOT logged.

Owner: AI Engineering Lead
Version: 0.3.0 (primary/fallback models)
"""

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
PRIMARY_MODEL = os.getenv("GEMINI_PRIMARY_MODEL") or os.getenv("MODEL_NAME") or "gemini-3.8-flash"
FALLBACK_MODELS = [m.strip() for m in (
    os.getenv("GEMINI_FALLBACK_MODELS")
    or os.getenv("GEMINI_FALLBACK_MODEL")
    or "gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite"
).split(",") if m.strip()]
REQUEST_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
MAX_ROUNDS = int(os.getenv("LLM_MAX_ROUNDS", "3"))
TRACE_PATH = Path("evidence/traces/llm_calls.jsonl")

MODELS = list(dict.fromkeys([PRIMARY_MODEL, *FALLBACK_MODELS]))

if not API_KEY:
    raise ValueError("GEMINI_API_KEY not set in .env")

# retry_options is left unset so the SDK does NOT retry on its own:
# this module decides when to retry or switch model.
client = genai.Client(
    api_key=API_KEY,
    http_options=types.HttpOptions(timeout=int(REQUEST_TIMEOUT_S * 1000)),
)

# HTTP codes where another model (or a later retry) may succeed.
SWITCH_CODES = {404, 408, 429, 500, 502, 503, 504}


class EmptyResponseError(RuntimeError):
    """Raised when the model returns no text."""


class AllModelsFailedError(RuntimeError):
    """Raised when every configured model failed in every round."""


@dataclass
class LLMResult:
    text: str
    model: str
    latency_s: float
    attempts: list = field(default_factory=list)


def _classify(exc: Exception) -> tuple[bool, str]:
    """Return (switch_model, short_reason) for an exception."""
    if isinstance(exc, errors.APIError):
        code = getattr(exc, "code", None)
        status = getattr(exc, "status", "") or ""
        if code in SWITCH_CODES:
            if code == 429 and "PerDay" in str(exc):
                return True, f"{code} {status} (daily quota exhausted)"
            if code == 404:
                return True, f"{code} {status} (model not available to this key)"
            return True, f"{code} {status}".strip()
        return False, f"{code} {status}".strip()
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException, TimeoutError, ConnectionError)):
        return True, f"network: {type(exc).__name__}"
    if isinstance(exc, EmptyResponseError):
        return True, "empty response"
    return False, f"{type(exc).__name__}: {exc}"



def _write_trace(record: dict) -> None:
    try:
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError as e:
        print(f"[WARN] Could not write trace: {e}")


class ChatSession:
    """
    A multi-turn chat that survives model fallback.

    The conversation history is kept here, so if the primary model fails
    mid-conversation the fallback model continues with the same history.
    """

    def __init__(self, system_prompt: str, json_mode: bool = False,
                 temperature: float = 0.1, label: str = "chat"):
        self.label = label
        self.history: list[types.Content] = []
        self.config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            response_mime_type="application/json" if json_mode else None,
        )
        self.unusable_models: set[str] = set()

    def send(self, message: str) -> LLMResult:
        attempts = []
        start = time.monotonic()
        for round_no in range(1, MAX_ROUNDS + 1):
            models = [m for m in MODELS if m not in self.unusable_models]
            if not models:
                break
            for model in models:
                t0 = time.monotonic()
                try:
                    chat = client.chats.create(model=model, config=self.config,
                                               history=self.history)
                    response = chat.send_message(message)
                    if not response.text:
                        raise EmptyResponseError("Model returned an empty response.")
                    self.history = chat.get_history()
                    attempts.append({"round": round_no, "model": model, "ok": True,
                                     "latency_s": round(time.monotonic() - t0, 2)})
                    result = LLMResult(response.text, model,
                                       round(time.monotonic() - start, 2), attempts)
                    _write_trace(self._trace(result.model, attempts, "success"))
                    return result
                except Exception as exc:
                    switch, reason = _classify(exc)
                    attempts.append({"round": round_no, "model": model, "ok": False,
                                     "error": reason,
                                     "latency_s": round(time.monotonic() - t0, 2)})
                    if not switch:
                        _write_trace(self._trace(None, attempts, "fatal_error"))
                        raise
                    if "daily quota" in reason or "not available" in reason:
                        self.unusable_models.add(model)
                    nxt = "next model" if model != models[-1] else "end of round"
                    print(f"[WARN] {model} failed ({reason}) -> {nxt}")
            if round_no < MAX_ROUNDS and any(m not in self.unusable_models for m in MODELS):
                wait = 5 * round_no
                print(f"[WARN] All models failed in round {round_no}. "
                      f"Waiting {wait}s before round {round_no + 1}/{MAX_ROUNDS}...")
                time.sleep(wait)
        _write_trace(self._trace(None, attempts, "all_models_failed"))
        summary = "; ".join(f"{a['model']}: {a['error']}" for a in attempts if not a["ok"])
        raise AllModelsFailedError(f"All models failed. {summary}")

    def _trace(self, model, attempts, outcome) -> dict:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "label": self.label,
            "outcome": outcome,
            "model_used": model,
            "models_configured": MODELS,
            "attempts": attempts,
        }


def generate(system_prompt: str, user_prompt: str, json_mode: bool = False,
             label: str = "single") -> LLMResult:
    """One-shot request (a fresh chat session with no history)."""
    return ChatSession(system_prompt, json_mode=json_mode, label=label).send(user_prompt)
