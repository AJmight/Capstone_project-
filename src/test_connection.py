"""
Connection smoke test: one short request through the shared client,
so it uses the same primary -> fallback model policy as the engine.
"""
from llm_client import MODELS, generate

SYSTEM_PROMPT = (
    "You are the AI Procurement Assistant for a Ugandan SME shop. "
    "You support, never decide. You never approve orders or invent data. "
    "Always cite the CSV source for any number you state."
)

print(f"Models: {' -> '.join(MODELS)}")

result = generate(
    SYSTEM_PROMPT,
    "In one sentence, explain why digital inventory tracking beats an exercise book that could get water-damaged.",
    label="test_connection",
)

print(f"--- Model Response ({result.model}, {result.latency_s}s) ---")
print(result.text)
