"""
Check which Gemini models this API key can use.

  py src\\test_models.py           list models that support generateContent (free, no quota used)
  py src\\test_models.py --probe   also send one tiny JSON request to each model in the
                                   configured chain (uses 1 request of each model's daily quota)

Being listed is not enough: on 2026-10-01 gemini-2.5-flash was listed but
returned 404 "no longer available to new users" when called.
"""
import argparse

from google.genai import types

from llm_client import MODELS, client


def list_models() -> list[str]:
    names = []
    for m in client.models.list():
        if "generateContent" in (getattr(m, "supported_actions", None) or []):
            names.append(m.name.removeprefix("models/"))
    return names


def probe(model: str) -> str:
    try:
        r = client.models.generate_content(
            model=model,
            contents='Return {"ok": true}',
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return f"OK   {r.text.strip()[:30]}"
    except Exception as e:
        return f"{getattr(e, 'code', type(e).__name__)}  {str(getattr(e, 'message', e))[:90]}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()

    listed = list_models()
    flash = [n for n in listed if "flash" in n and "tts" not in n and "image" not in n]
    print(f"{len(listed)} models support generateContent. Flash text models:")
    for n in flash:
        print(f"  {n}")

    print(f"\nConfigured chain: {' -> '.join(MODELS)}")
    for m in MODELS:
        status = probe(m) if args.probe else ("listed" if m in listed else "NOT LISTED")
        print(f"  {m:<24} {status}")
