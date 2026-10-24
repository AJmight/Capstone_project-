"""Offline regression for the interactive agent's bounded provider attempts."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import llm_client


def test_call_stops_after_configured_model_attempts():
    saved = (llm_client.MODELS, llm_client.MAX_MODEL_ATTEMPTS,
             llm_client.MAX_ROUNDS, llm_client.TRACE_PATH, llm_client.time.sleep)
    calls = []
    with tempfile.TemporaryDirectory() as folder:
        trace = Path(folder) / "llm.jsonl"
        try:
            llm_client.MODELS = ["primary", "fallback-a", "fallback-b"]
            llm_client.MAX_MODEL_ATTEMPTS = 2
            llm_client.MAX_ROUNDS = 3
            llm_client.TRACE_PATH = trace
            llm_client.time.sleep = lambda seconds: (_ for _ in ()).throw(
                AssertionError("interactive failure should not wait for a second round"))

            def unavailable(model):
                calls.append(model)
                raise TimeoutError("test timeout")

            try:
                llm_client.call_with_fallback(unavailable, "test-latency-limit")
            except llm_client.AllModelsFailedError:
                pass
            else:
                raise AssertionError("unavailable models should produce a fast hand-off")
            assert calls == ["primary", "fallback-a"], calls
            record = json.loads(trace.read_text(encoding="utf-8").splitlines()[-1])
            assert len(record["attempts"]) == 2
            print("PASS  call_with_fallback stops at the attempt cap without retry sleeps")
        finally:
            (llm_client.MODELS, llm_client.MAX_MODEL_ATTEMPTS,
             llm_client.MAX_ROUNDS, llm_client.TRACE_PATH, llm_client.time.sleep) = saved


if __name__ == "__main__":
    test_call_stops_after_configured_model_attempts()
