"""Offline tests for Gemini-first Groq fallback and tool-history handoff."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from google.genai import types

import llm_client


def test_chat_session_hands_compacted_history_to_groq():
    """A Gemini outage falls back silently with prior turns included in Groq's request."""
    sent = []
    sent_headers = []
    gemini_attempts = []

    def create_gemini_chat(**kwargs):
        gemini_attempts.append(kwargs["model"])
        raise TimeoutError("simulated Gemini outage")

    def fake_groq_post(url, headers, json, timeout):
        sent.append(json)
        sent_headers.append(headers)
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"choices": [{"message": {"content": "Here is the answer."}}]},
        )

    with tempfile.TemporaryDirectory() as trace_dir:
        with (patch.object(llm_client, "GROQ_API_KEY", "test-only-key"),
              patch.object(llm_client, "MODELS", ["gemini-test", "groq:llama-test"]),
              patch.object(llm_client, "MAX_MODEL_ATTEMPTS", 2),
              patch.object(llm_client, "TRACE_PATH", Path(trace_dir) / "calls.jsonl"),
              patch.object(llm_client, "client",
                           SimpleNamespace(chats=SimpleNamespace(create=create_gemini_chat))),
              patch.object(llm_client.httpx, "post", fake_groq_post)):
            session = llm_client.ChatSession("Stay within the shop records.", label="test-groq")
            session.history = [
                types.Content(role="user", parts=[types.Part(text="Earlier question")]),
                types.Content(role="model", parts=[types.Part(text="Earlier answer")]),
            ]
            result = session.send("Current question")

    assert gemini_attempts == ["gemini-test"]
    assert result.model == "groq:llama-test"
    assert result.text == "Here is the answer."
    assert sent_headers[0]["Authorization"] == "Bearer test-only-key"
    assert [message["role"] for message in sent[0]["messages"]] == [
        "system", "user", "assistant", "user",
    ]
    assert sent[0]["messages"][-3]["content"] == "Earlier question"
    assert sent[0]["messages"][-2]["content"] == "Earlier answer"
    assert sent[0]["messages"][-1]["content"] == "Current question"
    assert session.history[-1].parts[0].text == "Here is the answer."


def test_groq_tool_response_is_normalized_for_agent_loop():
    """Groq receives function schemas and returns function calls in Gemini's response shape."""
    captured = {}

    def fake_groq_post(url, headers, json, timeout):
        captured.update(json)
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"choices": [{"message": {
                "content": None,
                "tool_calls": [{
                    "id": "call_1", "type": "function",
                    "function": {"name": "get_low_stock", "arguments": "{}"},
                }],
            }}]},
        )

    config = types.GenerateContentConfig(
        system_instruction="Use tools for facts.",
        tools=[types.Tool(function_declarations=[types.FunctionDeclaration(
            name="get_low_stock", description="List low stock.",
            parameters_json_schema={"type": "object", "properties": {}, "required": []},
        )])],
    )

    with (patch.object(llm_client, "GROQ_API_KEY", "test-only-key"),
          patch.object(llm_client.httpx, "post", fake_groq_post)):
        response = llm_client.generate_content(
            "groq:llama-test",
            [types.Content(role="user", parts=[types.Part(text="What is low?")])],
            config,
        )

    assert captured["messages"][0] == {"role": "system", "content": "Use tools for facts."}
    assert captured["tools"][0]["function"]["name"] == "get_low_stock"
    assert response.function_calls[0].name == "get_low_stock"


def test_groq_request_uses_configured_bearer_token():
    """Groq requests authenticate with the key supplied by the environment."""
    captured = {}

    def fake_groq_post(url, headers, json, timeout):
        captured["authorization"] = headers.get("Authorization")
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"choices": [{"message": {"content": "Fallback works."}}]},
        )

    config = types.GenerateContentConfig(system_instruction="Stay grounded.")
    with (patch.object(llm_client, "GROQ_API_KEY", "test-only-key"),
          patch.object(llm_client.httpx, "post", fake_groq_post)):
        response = llm_client.generate_content(
            "groq:llama-test",
            [types.Content(role="user", parts=[types.Part(text="Check stock.")])],
            config,
        )

    assert captured["authorization"] == "Bearer test-only-key"
    assert response.text == "Fallback works."


def test_groq_http_failures_are_retryable():
    """Quota, temporary outage, and rejected Groq credentials advance the chain."""
    for code in (401, 403, 408, 429, 500, 503):
        response = SimpleNamespace(status_code=code)
        error = llm_client.httpx.HTTPStatusError(
            "provider failure", request=None, response=response)
        should_switch, reason = llm_client._classify(error)
        assert should_switch, (code, reason)


def test_groq_tool_turn_does_not_fall_back_to_gemini():
    """Groq tries its alternate model, but never sends Groq tool history to Gemini."""
    import tool_agent

    calls = []

    class MemoryStorage:
        def __init__(self, _path):
            pass

        def start_session(self, *_args):
            pass

        def save_session_state(self, *_args):
            pass

    def fake_gemini(model, contents, config):
        calls.append(("gemini", model))
        if model == "gemini-primary":
            raise TimeoutError("simulated primary outage")
        raise AssertionError("Gemini must not receive Groq's tool-call history")

    groq_turn = 0

    def fake_groq(model, contents, config):
        nonlocal groq_turn
        calls.append(("groq", model))
        groq_turn += 1
        if groq_turn == 1:
            parts = [types.Part(function_call=types.FunctionCall(
                name="get_low_stock", args={}, id="call_1"))]
            content = types.Content(role="model", parts=parts)
            return SimpleNamespace(
                function_calls=[parts[0].function_call],
                candidates=[SimpleNamespace(content=content)],
                text=None,
            )
        response = SimpleNamespace(status_code=429)
        raise llm_client.httpx.HTTPStatusError(
            "Groq quota exhausted", request=None, response=response)

    with tempfile.TemporaryDirectory() as folder:
        trace_dir = Path(folder)
        with (patch.object(tool_agent, "MODELS",
                           ["gemini-primary", "groq:primary", "groq:secondary",
                            "gemini-secondary"]),
              patch.object(llm_client, "MODELS",
                           ["gemini-primary", "groq:primary", "groq:secondary",
                            "gemini-secondary"]),
              patch.object(llm_client, "MAX_MODEL_ATTEMPTS", 3),
              patch.object(llm_client, "TRACE_PATH", trace_dir / "llm.jsonl"),
              patch.object(tool_agent, "TRACE_PATH", trace_dir / "agent.jsonl"),
              patch.object(tool_agent, "client",
                           SimpleNamespace(models=SimpleNamespace(
                               generate_content=fake_gemini))),
              patch.object(tool_agent, "generate_content", fake_groq),
              patch.object(tool_agent, "SQLiteStorage", MemoryStorage),
              patch.object(tool_agent, "execute_tool",
                           lambda *_args, **_kwargs: ({"items": [], "count": 0}, "ok"))):
            result = tool_agent.run_agent(
                "Check low stock.", allowed_tools={"get_low_stock"})

    assert calls == [
        ("gemini", "gemini-primary"),
        ("groq", "groq:primary"),
        ("groq", "groq:primary"),
        ("groq", "groq:secondary"),
    ]
    assert result["stopped_reason"] == "model_unavailable"
    assert not result["drafts_created"]


def test_gemini_tool_turn_preserves_thought_signature():
    """The original signed Gemini function-call part is replayed with its result."""
    import tool_agent

    signature = "dGhvdWdodC1zaWduYXR1cmU="
    calls = []

    class MemoryStorage:
        def __init__(self, _path):
            pass

        def start_session(self, *_args):
            pass

        def save_session_state(self, *_args):
            pass

    def fake_gemini(model, contents, config):
        calls.append(model)
        if len(calls) == 1:
            part = types.Part(
                function_call=types.FunctionCall(
                    name="get_low_stock", args={}, id="call_1"),
                thought_signature=signature,
            )
            content = types.Content(role="model", parts=[part])
            return SimpleNamespace(
                function_calls=[part.function_call],
                candidates=[SimpleNamespace(content=content)],
                text=None,
            )

        replayed_part = contents[1].parts[0]
        assert replayed_part.function_call.name == "get_low_stock"
        assert replayed_part.thought_signature == b"thought-signature"
        assert contents[2].parts[0].function_response.name == "get_low_stock"
        return SimpleNamespace(
            function_calls=[],
            candidates=[SimpleNamespace(content=types.Content(
                role="model", parts=[types.Part(text="Checked the stock.")]))],
            text="Checked the stock.",
        )

    with tempfile.TemporaryDirectory() as folder:
        trace_dir = Path(folder)
        with (patch.object(tool_agent, "MODELS", ["gemini-test"]),
              patch.object(llm_client, "MODELS", ["gemini-test"]),
              patch.object(llm_client, "MAX_MODEL_ATTEMPTS", 1),
              patch.object(llm_client, "TRACE_PATH", trace_dir / "llm.jsonl"),
              patch.object(tool_agent, "TRACE_PATH", trace_dir / "agent.jsonl"),
              patch.object(tool_agent, "client",
                           SimpleNamespace(models=SimpleNamespace(
                               generate_content=fake_gemini))),
              patch.object(tool_agent, "SQLiteStorage", MemoryStorage),
              patch.object(tool_agent, "execute_tool",
                           lambda *_args, **_kwargs: ({"items": [], "count": 0}, "ok"))):
            result = tool_agent.run_agent(
                "Check low stock.", allowed_tools={"get_low_stock"})

    assert calls == ["gemini-test", "gemini-test"]
    assert result["stopped_reason"] == "model_finished"
    assert result["final_text"] == "Checked the stock."


if __name__ == "__main__":
    test_chat_session_hands_compacted_history_to_groq()
    test_groq_tool_response_is_normalized_for_agent_loop()
    test_groq_request_uses_configured_bearer_token()
    test_groq_http_failures_are_retryable()
    test_groq_tool_turn_does_not_fall_back_to_gemini()
    test_gemini_tool_turn_preserves_thought_signature()
    print("PASS  Gemini quota handoff preserves chat history")
    print("PASS  Groq function calls use the Gemini agent response contract")
    print("PASS  Groq requests use the configured bearer token")
    print("PASS  Groq quota, credential, and service errors are retryable")
    print("PASS  Groq tries its alternate model without crossing providers")
    print("PASS  Gemini tool-call thought signatures survive the next turn")
