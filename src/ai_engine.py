"""
AI Engine for SME Procurement Support Agent.

Loads the versioned system prompt, reads synthetic CSV data,
calls Gemini (primary model with automatic fallback, see llm_client.py)
via a chat session with structured JSON output, and returns results.

Owner: AI Engineering Lead
Version: 0.3.0 (primary/fallback models via llm_client)
"""

import json
from pathlib import Path

import pandas as pd

from llm_client import MODELS, generate

PROMPT_PATH = Path("prompts/procurement_assistant_v1.2.0.md")
DATA_DIR = Path("data")

PROMPT_BEGIN = "<!-- BEGIN SYSTEM PROMPT -->"
PROMPT_END = "<!-- END SYSTEM PROMPT -->"


# ---- Helpers ----

def load_system_prompt(path: Path = PROMPT_PATH) -> str:
    """
    Read the versioned prompt file and return only the model-facing part
    (between the BEGIN/END SYSTEM PROMPT markers). Metadata, design notes
    and version history stay out of the model's context.
    """
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if PROMPT_BEGIN not in text or PROMPT_END not in text:
        raise ValueError(f"Prompt markers missing in {path}")
    return text.split(PROMPT_BEGIN, 1)[1].split(PROMPT_END, 1)[0].strip()


def load_csv(name: str) -> str:
    """Load a CSV as a string for injecting into the prompt."""
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    df = pd.read_csv(path)
    return df.to_csv(index=False)


def parse_json(text: str) -> dict:
    """
    Parse model output as JSON. Tolerates a surrounding ```json fence,
    which some models add even when told not to.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""
        cleaned = cleaned.rsplit("```", 1)[0]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON parse failed: {e}") from e


# ---- Core capability ----

def analyze_inventory() -> dict:
    """
    Full pipeline:
    load prompt + inventory CSV -> model (with fallback) -> parse JSON -> dict.
    """
    system_prompt = load_system_prompt()
    inventory_csv = load_csv("current_stock.csv")

    user_prompt = (
        "Analyze the inventory below.\n"
        "Identify all items at or below their reorder point.\n"
        "Return ONLY valid JSON per the schema in your system instructions.\n\n"
        "[INVENTORY_CSV]\n"
        f"{inventory_csv}"
    )

    llm = generate(system_prompt, user_prompt, json_mode=True,
                   label="analyze_inventory")
    print(f"[INFO] Answered by {llm.model} in {llm.latency_s}s "
          f"({len(llm.attempts)} attempt(s))")

    try:
        return parse_json(llm.text)
    except ValueError:
        print("[ERROR] Model returned non-JSON text:")
        print(llm.text)
        raise


# ---- Local smoke test ----

if __name__ == "__main__":
    print(f"Models: {' -> '.join(MODELS)}")
    print(f"Prompt: {PROMPT_PATH}")
    print("Running analyze_inventory() via Chat session...\n")

    result = analyze_inventory()

    print("--- Parsed Result ---")
    print(json.dumps(result, indent=2))

    # Quick validation
    required_keys = {"summary", "alerts", "draft_requisition",
                     "estimated_budget_ugx", "approval_status"}
    missing = required_keys - result.keys()
    if missing:
        print(f"\n[WARN] Missing keys in response: {missing}")
    else:
        print(f"\n[OK] All required keys present.")
        print(f"     Alerts: {len(result.get('alerts', []))}")
        print(f"     Draft items: {len(result.get('draft_requisition', []))}")
