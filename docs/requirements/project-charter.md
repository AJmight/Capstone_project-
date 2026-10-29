# Project Charter — SME Procurement Support Agent

| Field | Value |
|:---|:---|
| **Course** | BSE4104 Emerging Trends in Software Engineering — 8-week AI-native & agentic capstone |
| **Version** | 1.3 — revised 2026-10-27 for AI-led restock planning and direct human approval controls |
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
| **A trusted person appointed by the owner** | Quick, defensible answers: what is low, how much to order, from whom |

In the system these are **one trusted user per shop** with no separate roles (decision-001, 2026-10-13).
The prototype starts by asking for a business name rather than showing a login; the name selects the
shop's tenant workspace, and the app keeps its stock, activity, policies, drafts and chat context
under that tenant. This is demo-level separation, not identity verification or production access control.

## 3. Proposal statement (brief §2 format)

> Our system helps **small-shop owners and staff** keep a tenant-scoped digital stock book and prepare
> **weekly procurement** (record deliveries and counter sales, find low stock, decide priorities and
> supplier trade-offs within a budget, compare quotes, ask shop-policy questions and draft a requisition).
> AI is used for **understanding requests, gathering evidence, prioritizing restock items, choosing
> supplier trade-offs, planning tool use, retrieving policy, and explaining recommendations**.
> Deterministic software remains responsible for **all calculations, business rules, selection
> validation, permissions, hard budget limits and bounded execution**. The agent may use **nine
> approved read/draft tools** but may **not approve,
> order, pay, contact suppliers or connect to banks or mobile money**. We build and evaluate the system
> using **synthetic CSV data (15 items, 12 months of purchases, 3 suppliers) and a 12-document synthetic
> policy corpus**.

## 4. Where AI adds value — and where it must not decide

| AI adds value | Deterministic software decides | Humans decide |
|:---|:---|:---|
| Understanding free-text questions; choosing tools; multi-step planning; choosing restock priorities and supplier trade-offs from evidence; explaining figures; grounded policy answers | Low-stock rule, reorder quantity, validating supplier selections, exact totals and quote-specific costs, enforcing the hard budget ceiling, 200 % cap, permissions, limits, outcome of agent runs | Approve/reject/edit requisitions; quantities for items without history; whether to fund deferred items; placing orders and paying |

Full matrix: `docs/requirements/ai-boundary-matrix.md`.

## 5. Scope

**In scope:** the existing tested procurement functions plus a browser prototype guided by local Stitch
exports. Restock AI is the normal planner: it receives full tool-computed evidence, chooses priorities
and supplier trade-offs, and requests Python validation before a draft can be saved. If the AI is
unavailable, no automatic restock draft is created. The browser journey is business name → Dashboard / AI Copilot → Operations (stock, sales,
purchases, quotes and activity) → Restock AI → Approvals. Policy Q&A/editing lives in the copilot. An
AI-planned restock draft opens Approvals automatically. The bounded AI agent makes priorities and
supplier trade-offs; deterministic tools calculate and validate every figure. Chat context is scoped to the
selected tenant and browser session, with four recent turns and a compact extract of older turns.

**Completed capstone layers:** persistent workflow state, justified memory, MCP-style tool interface,
30+ scenario evaluation, guardrail hardening and release checks.

**Out of scope:** real authentication/identity verification, production use of private records, real
purchasing or payments, supplier APIs, automated sales/POS integration and PDF/scanned quote parsing.
The browser prototype manually records sales and incoming purchases; it does not connect to a POS.

## 6. Assumptions

- The UI records new sales and purchase history per shop. The existing demand estimator uses purchase
  history; sales-based forecasting has not been evaluated and is not implied by recording sales.
- One shop, one currency (UGX), three suppliers; quotes are current.
- One trusted user per shop. Entering a business name selects a tenant but does not authenticate the person; production authentication remains future work.
- The Gemini free tier remains available (fallback across six Flash models).

## 7. Constraints

- Free tools only (Gemini AI Studio free tier: 20 requests/day per model).
- Synthetic data only (free-tier data may be used by the provider).
- Eight weeks, part-time student team; Windows laptops; mobile-hotspot internet.

## 8. Success criteria

| Criterion | Target | Status (2026-10-06) |
|:---|:---|:---|
| Correct figures | 100 % of quantities/totals match an independent calculation | Met — Week 4–8 deterministic suites |
| Bounded autonomy | No path for the AI to approve/order/pay; every draft needs a human | Met — no such tool; L-04 refusal; approval CLI |
| Grounded answers | Policy answers cite sources; unanswerable questions refused | Met — 15/15 RAG cases |
| Safe failure | Tool/model failures end in recovery or a clear hand-off | Met — T3, T4, offline A-03…A-13 |
| Evaluation | ≥ 30 scenarios by Week 7 | Met — Week 7/8 offline evaluations |
| Browser workflow | Each shop can record data, plan a restock and review it without session errors | Met — headless app flow tests; no live business data used |

## 9. Risks

| Risk | Mitigation |
|:---|:---|
| Model gives wrong numbers | All maths in Python tools (F-04 closed) |
| Model claims actions it did not take | Code output check (F-13) |
| Model tries tools that do not exist (e.g. approve) | Registry allow-list (F-07, O-16, L-05) |
| Free-tier quota/outages | Six-model fallback chain, offline test suites |
| Team members behind schedule | `docs/ONBOARDING.md` catch-up guide and owned tasks per role |
