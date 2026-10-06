# Project Charter — SME Procurement Support Agent

| Field | Value |
|:---|:---|
| **Course** | BSE4104 Emerging Trends in Software Engineering — 8-week AI-native & agentic capstone |
| **Version** | 1.1 — consolidated in markdown on 2026-10-06 from the team's Week 1 document `User stories and acceptance criteria (2).docx` and the capstone brief; aligned with the system as built |
| **Prepared by** | Mwesigwa Arnold Mugahi (AI Engineering Lead); team review pending |

## 1. Problem

Small Ugandan retail shops (stationery, office supplies, hardware) usually record stock and purchases in a
paper exercise book. When the book is lost, stolen or water-damaged, the shop loses its stock history,
supplier prices and purchase records. Without reliable records, junior staff cannot check whether an item
is really running out, and visiting suppliers can pressure them into over-ordering. Money gets tied up in
stock that does not sell.

## 2. Target users

| User | Need |
|:---|:---|
| **Shop owner / manager** | Reliable oversight; approves every purchase; protects cash flow |
| **Junior staff (procurement officer role)** | Quick, defensible answers: what is low, how much to order, from whom |
| **Viewer** (e.g. new staff) | Look up stock, history and policy without being able to create requisitions |

## 3. Proposal statement (brief §2 format)

> Our system helps **small-shop owners and staff** complete **weekly procurement preparation** (find low
> stock, decide quantities within a budget, choose suppliers and draft a requisition). AI is used for
> **understanding requests, planning which tools to use, retrieving policy, and explaining results**.
> Deterministic software remains responsible for **all calculations, business rules, validation,
> permissions and limits**. The agent may use **eight approved read/draft tools** but may **not approve,
> order, pay, contact suppliers or connect to banks or mobile money**. We build and evaluate the system
> using **synthetic CSV data (15 items, 12 months of purchases, 3 suppliers) and a 12-document synthetic
> policy corpus**.

## 4. Where AI adds value — and where it must not decide

| AI adds value | Deterministic software decides | Humans decide |
|:---|:---|:---|
| Understanding free-text questions; choosing tools; multi-step planning; explaining figures; grounded policy answers | Low-stock rule, reorder quantity, supplier choice, totals, budget fit, 200 % cap, permissions, limits, outcome of agent runs | Approve/reject/edit requisitions; quantities for items without history; whether to fund deferred items; placing orders and paying |

Full matrix: `docs/requirements/ai-boundary-matrix.md`.

## 5. Scope

**In scope (MVP, Weeks 1–5):** stock overview; low-stock detection; supplier quote comparison; reorder
quantity with working; purchase-history questions; policy questions with citations (RAG); draft
requisitions; bounded weekly-restock agent within a budget; human approval with edit and audit trail;
traces and tests.

**Planned (Weeks 6–8):** persistent state (database), justified memory, MCP-style tool interface, 30+
scenario evaluation, guardrail hardening, web UI, release.

**Out of scope:** real purchasing or payments; supplier APIs; real customer or business data; PDF/scanned
quote parsing (User Story 3 — descoped, see user stories); sales/POS integration.

## 6. Assumptions

- Purchase history is used as the demand estimate because the data has no sales records.
- One shop, one currency (UGX), three suppliers; quotes are current.
- Users are identified by name and role at login; real authentication comes later.
- The Gemini free tier remains available (fallback across six Flash models).

## 7. Constraints

- Free tools only (Gemini AI Studio free tier: 20 requests/day per model).
- Synthetic data only (free-tier data may be used by the provider).
- Eight weeks, part-time student team; Windows laptops; mobile-hotspot internet.

## 8. Success criteria

| Criterion | Target | Status (2026-10-06) |
|:---|:---|:---|
| Correct figures | 100 % of quantities/totals match an independent calculation | Met — offline tests (22 + 16 + 7) |
| Bounded autonomy | No path for the AI to approve/order/pay; every draft needs a human | Met — no such tool; L-04 refusal; approval CLI |
| Grounded answers | Policy answers cite sources; unanswerable questions refused | Met — 15/15 RAG cases |
| Safe failure | Tool/model failures end in recovery or a clear hand-off | Met — T3, T4, offline A-03…A-13 |
| Evaluation | ≥ 30 scenarios by Week 7 | In progress (≈ 50 automated cases already, mixed live/offline) |

## 9. Risks

| Risk | Mitigation |
|:---|:---|
| Model gives wrong numbers | All maths in Python tools (F-04 closed) |
| Model claims actions it did not take | Code output check (F-13) |
| Model tries tools it lacks | Registry permission checks (F-07) |
| Free-tier quota/outages | Six-model fallback chain, offline test suites |
| Team members behind schedule | `docs/ONBOARDING.md` catch-up guide and owned tasks per role |
