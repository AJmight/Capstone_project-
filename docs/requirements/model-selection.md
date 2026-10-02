# Model Selection Note — Week 2

| Field | Value |
|:---|:---|
| **Owner** | AI Engineering Lead |
| **Version** | 2.0 (replaces the v1 note previously in `README.md`) |
| **Date** | 2026-10-02 |
| **Evidence** | `src/test_models.py`, `evidence/traces/llm_calls.jsonl`, `evidence/week2/` |

## Decision

**Model family:** Google Gemini Flash, via Google AI Studio (free tier, no credit card).

| Role | Model | Why |
|:---|:---|:---|
| Primary | `gemini-3.8-flash` | Newest Flash model available to our key; Google's own 404 message for older models recommends it |
| Fallback 1–3 | `gemini-3.7-flash`, `gemini-3.6-flash`, `gemini-3.5-flash` | Same capabilities, separate daily quotas |
| Fallback 4–5 | `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite` | Fast and usually available; weaker at arithmetic (see Limitations) |

The chain is configured in `.env` (`GEMINI_PRIMARY_MODEL`, `GEMINI_FALLBACK_MODELS`) and enforced in
`src/llm_client.py`: on any availability failure (503, 429, 5xx, timeout, network drop, 404) the client
switches immediately to the next model. Every call is traced in `evidence/traces/llm_calls.jsonl`.

## Requirements and how Gemini Flash meets them

| Requirement | Evidence |
|:---|:---|
| Free, no payment card (Uganda-accessible) | AI Studio key on a free project |
| Structured JSON output | `response_mime_type="application/json"`; 10/10 Week 2 JSON cases parsed |
| Function calling (Week 4) | Supported by the Gemini API |
| Large context for CSVs and retrieved text (Week 3) | All three CSVs (~180 rows) fit in one request |
| Low latency on a mobile hotspot | Typical successful call 4–7 s (`evidence/week2/evaluation_v1.2.0.md`) |

## What we learned while integrating (verified, 2026-10-01/02)

| Finding | Evidence | Consequence |
|:---|:---|:---|
| `gemini-2.5-flash` returns **404 "no longer available to new users"** although it is listed | `src/test_models.py`; trace 2026-10-01T22:02 | Cannot be our fallback; earlier plans that named it were changed |
| Free tier allows **20 requests/day per model** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`) | 429 error text | One model alone cannot support testing; quotas are per model, so a chain multiplies capacity |
| 503 "high demand" is frequent and model-specific | v1.1.0 run: TC-08/TC-09 failed because every configured model was busy or out of quota | Retrying one model wastes time; switching models fixes most cases |
| Chat sessions do not avoid 503s | `chats.send_message` calls the same `generate_content` endpoint | Chat sessions are used for multi-turn memory only, not for reliability |
| `WinError 10060/10053` were local network drops, not Google errors | Windows tracebacks | 60 s request timeout + network errors trigger a model switch |

## Trade-offs accepted

| Trade-off | Consequence | Mitigation |
|:---|:---|:---|
| Free-tier data may be used by Google to improve products | Cannot send real SME data | Synthetic data only (project constraint) |
| 20 requests/day per model | Large test runs can exhaust the best models | Six-model fallback chain; small test sets; `test_models.py` lists without using quota |
| Fallback models differ in quality | Results depend on which model answered | Every result records `model_used`; final evaluation (Week 7) must be re-run on the primary model |
| The model does the arithmetic (Week 2 baseline) | `gemini-3.5-flash-lite` produced 3 wrong quantities in TC-08 | Week 4: reorder/cost/cap maths move to deterministic Python tools |

## Rejected alternatives

| Option | Reason |
|:---|:---|
| GPT-4o mini (OpenAI) | No sustainable free tier; needs a payment method |
| Groq (Llama 3.3 70B) | Fast and free, but smaller context and less mature structured output for our CSV-heavy workload. **Kept as a planned cross-provider fallback** (one more entry in `llm_client.py`) |
| Claude Haiku (Anthropic) | No free API tier |
| Local model (Ollama) | Needs a capable GPU; makes the live demo hardware-dependent |

## Re-checking this decision

Run `py src\test_models.py` (free) or `py src\test_models.py --probe` (1 request per model) and update
this note and `.env` if availability changes.
