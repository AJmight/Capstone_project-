"""Offline tests for Gemini-first Groq fallback and tool-history handoff."""

from __future__ import annotations

import sys
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
    gemini_attempts = []

    def create_gemini_chat(**kwargs):
        gemini_attempts.append(kwargs["model"])
        raise TimeoutError("simulated Gemini outage")

    def fake_groq_post(url, headers, json, timeout):
        sent.append(json)
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"choices": [{"message": {"content": "Here is the answer."}}]},
        )

    with (patch.object(llm_client, "GROQ_API_KEY", "test-only-key"),
          patch.object(llm_client, "MODELS", ["gemini-test", "groq:llama-test"]),
          patch.object(llm_client, "MAX_MODEL_ATTEMPTS", 2),
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


if __name__ == "__main__":
    test_chat_session_hands_compacted_history_to_groq()
    test_groq_tool_response_is_normalized_for_agent_loop()
    print("PASS  Gemini quota handoff preserves chat history")
    print("PASS  Groq function calls use the Gemini agent response contract")
