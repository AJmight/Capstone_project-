# Data Protection and Multi-User Plan (data leakage, sessions, tenants, per-shop RAG)

| Field | Value |
|:---|:---|
| **Version** | 0.1 — 2026-10-13 (input to Week 6 "Memory Design and Data Handling Note" and Week 7 guardrails) |
| **Owner** | Mwesigwa Arnold Mugahi (AI Engineering Lead) |
| **Status** | Analysis of the current MVP + plan. The MVP is a **single-shop prototype**; multi-shop isolation is designed here, not yet built. |

Words used: **user** = a person (staff, owner, viewer); **tenant** = one shop with its own data; **session** =
one conversation or agent run.

---

## 1. Where data can leak in an AI system like ours

| # | Leak type | Example of the harm |
|:---:|:---|:---|
| L1 | **Provider training / retention** | Data we send to Gemini is kept or used by the provider to improve its models |
| L2 | **Cross-session (same user)** | Yesterday's conversation details appear in today's answer when they shouldn't |
| L3 | **Cross-user (same shop)** | A viewer sees something only the owner should see, or one user's chat appears in another's |
| L4 | **Cross-tenant (different shops)** | Shop A's stock, prices, suppliers or policies appear in Shop B's answers |
| L5 | **Logs and traces** | Traces or audit files expose questions, names or business data to people who shouldn't see them (or get committed to git) |
| L6 | **Prompt injection / exfiltration** | Text inside a document or message makes the model reveal data it was given |
| L7 | **Model memorisation output** | The model repeats something from its own training data as if it were our fact |

## 2. Where the MVP stands today (honest assessment)

| Leak | Current state | Why |
|:---|:---|:---|
| L1 provider | **Accepted risk, mitigated by synthetic data.** We use the Gemini **free tier**; per Google's Gemini API terms for unpaid services (check the current terms), submitted content may be used to improve Google products and may be seen by human reviewers. | That is exactly why the brief and our charter require synthetic data only. We never fine-tune or train a model ourselves. |
| L2 cross-session | **No conversational leakage.** Every `run_agent()` starts a new `contents` list (`src/tool_agent.py`), every `generate()` call creates a fresh `ChatSession` (`src/llm_client.py`); nothing is remembered between runs. | Stateless by design. Week 6 memory will change this, so it must be designed with scoping (§4). |
| L3 cross-user | **Partly controlled.** Roles limit *tools* (viewer cannot draft — enforced in `registry.execute_tool`). But all users of the shop see the same shop data, all drafts are listed to every role in `app.py` (only the owner can decide), and there is **no real login** (name + role are typed in). | Fine for a demo; not for real use. |
| L4 cross-tenant | **Not applicable yet — and not safe yet.** Paths are fixed (`data/`, `knowledge/corpus/`, `data/drafts/`), the RAG index is one global cache (`get_index()` with `lru_cache`). Two shops on one installation would see each other's data. | Single-shop prototype. |
| L5 logs | **Exposed by design for evaluation.** `evidence/week4/agent_traces.jsonl` and `evidence/week5/` contain full questions, user names, tool results and answers, and are committed to git as coursework evidence. `evidence/traces/llm_calls.jsonl` stores no text. | Acceptable only because all data is synthetic. |
| L6 injection | **Mitigated.** Prompt rules (data wins; tool results and documents are information, not instructions); tools accept only validated arguments; tools can only return this shop's data, so even a successful injection cannot reach anything else; output check (F-13). Test L-03 (injected "1000 pens") passed. | Defence in depth. |
| L7 memorisation | **Mitigated.** Prompts require every figure to come from a tool result and every policy fact from a cited source; "not in the provided data/documents" is the expected answer otherwise (RAG RU-01…05 all refused). | Grounding. |

## 3. Design principles for a multi-user, multi-shop version

1. **Identity comes from the session, never from the model.** The same pattern we already use for
   `created_by` (registry `context_args`, test O-18): the logged-in user's `user_id`, `role` and
   `tenant_id` are injected by code into every tool call; a model-supplied `tenant_id` is rejected.
2. **Every data access is scoped in code.** Tools receive `tenant_id` and can only read that tenant's
   rows/files. Scoping is enforced in the data layer (one function every tool uses), not in prompts.
3. **One request, one tenant.** A model call only ever contains one tenant's data. Model calls are
   stateless; the fallback chain re-sends the same tenant's context to another model and never mixes.
4. **Separate indexes per tenant.** Each shop gets its own RAG corpus and index; the index cache is keyed by `tenant_id`.
5. **Memory is scoped, minimal and deletable** (Week 6): key = `(tenant_id, user_id)` or `(tenant_id)`
   for shop-wide preferences; store only approved facts (e.g. "owner's usual weekly budget"), never raw
   chats by default; retention period; delete on request.
6. **Logs are partitioned, minimised and protected.** Traces stored per tenant, without personal data,
   with a retention period, never committed to git outside coursework, readable only by the tenant's owner/admin.
7. **No cross-user caching.** If answers are ever cached, the cache key includes tenant, user and role.
8. **Real authentication.** Hashed passwords (or an identity provider), server-side sessions, role
   stored in the database, not typed by the user.
9. **Production model tier.** Use a paid Gemini API / Vertex AI configuration whose terms exclude
   training on customer content, plus a data-processing agreement; still send the minimum data and
   redact personal data before any model call.

## 4. Concrete changes, mapped to the remaining weeks

| Week | Change | Files likely affected | Test that proves it |
|:---|:---|:---|:---|
| 6 | SQLite with `tenant_id` and `user_id` on every table (items, purchases, quotes, drafts, audit, memory, sessions) | new `src/storage.py`; tools read through it | unit tests per table |
| 6 | `tenant_id` added to `context_args` for every tool; registry rejects it from the model | `src/tools/registry.py` | like O-18: model sends `tenant_id` → INVALID_PARAMETER |
| 6 | Memory with scope, allow-listed fields, retention and delete | `src/memory.py` + Memory Design and Data Handling Note | memory of user A never appears for user B / tenant B |
| 6 | Per-tenant RAG index (cache keyed by tenant) | `src/rag/index.py` (`get_index(tenant_id)`) | Shop B question never retrieves Shop A chunk IDs |
| 7 | Cross-tenant and cross-user isolation tests in the 30-scenario evaluation | Quality Lead's evaluation set | e.g. "show me Shop A's prices" while logged in to Shop B → no Shop A data |
| 7 | Log redaction + per-tenant trace folders + retention setting | `src/tool_agent.py`, `src/tools/registry.py` | traces contain no names when redaction is on |
| 7 | Real login (hashed passwords) in the web UI | App Lead's UI | wrong password → no session; role from DB |
| 8 | Document what remains a prototype risk (free tier, no encryption at rest, etc.) | final report §10 | — |

## 5. How each shop sets up its own RAG knowledge (per-tenant corpus)

**Today (single shop):** the corpus is `knowledge/corpus/*.md`. To run the system for a different shop
you would replace those files (and `data/*.csv`), update `knowledge/source-register.md`, and re-run
`py tests\test_week3_rag.py --offline`. The index rebuilds automatically on the next run.

**Planned (several shops on one system):**

```
tenants/
  <shop_id>/
    data/            current_stock.csv, past_purchases.csv, supplier_quotes.csv  (later: SQLite rows)
    knowledge/
      corpus/        the shop's own policy documents (.md)
      source-register.md
      index/         built index, created by the ingest command
```

Onboarding a new shop:
1. **Start from a template.** Copy our 12 synthetic documents as a starter set; the owner edits them
   to match their real rules (approval limits, suppliers, payment terms). Shops without written
   policies answer a short questionnaire and the template is filled in.
2. **Format rules.** One topic per `## ` section (sections become chunks and citation IDs); plain
   language; no personal data (no staff phone numbers, customer names). Word/PDF documents are
   converted to markdown first (copy-paste or a converter such as pandoc); scanned images are not supported.
3. **Ingest command** (to build): `py src\rag\ingest.py --tenant <shop_id>` validates the files (format,
   headings, size, forbidden content such as phone numbers), rebuilds that shop's index, and updates its
   source register with file names, dates and owner.
4. **Check quality.** Run the 15-question template (answerable / partial / unanswerable) adapted to the
   shop; retrieval hit@3 should be ≥ 9/10 before going live.
5. **Keep it current.** Any edit → re-ingest. The source register records who changed what and when.
6. **Isolation.** The shop's `search_policy` and RAG pipeline only ever load `tenants/<shop_id>/knowledge/index`
   — selected from the session's `tenant_id`, never from the question text.
