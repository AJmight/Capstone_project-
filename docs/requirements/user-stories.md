# User Stories and Acceptance Criteria

**Revised:** 2026-10-24 to match the local Stitch exports and the current browser prototype.
The journey is: enter a business name → use Dashboard / AI Copilot → record the shop's
operations → plan a restock → review the automatically queued draft in Approvals. There is
no login screen. A name selects a tenant workspace; this demo has no identity verification.

**User:** one trusted shop owner/manager per workspace. The model may explain and prepare a
draft, but only the person using the app can edit, approve or reject it.

| # | Story | Acceptance criteria | Status / evidence |
|:--:|:--|:--|:--|
| 1 | **Open a business workspace** — as an owner, I enter my shop name and continue without login. | Blank names are refused; a stable tenant ID is shown; reopening the same name returns its ledger; a different name receives separate stock, policy, draft, sales and chat state. | ✅ App UI, `tenant_context.py`, UI tenant tests |
| 2 | **Dashboard / AI Copilot** — as an owner, I want to see this shop's status and ask about its records from the first screen. | Dashboard shows this tenant's product, low-stock, today's sales and pending-draft counts; prompt chips fill the question; answers include run/source context; errors are shown without breaking the page. | ✅ `render_dashboard`, `render_ask_page`; mocked UI flow tests |
| 3 | **Inventory management** — as an owner, I want to add, review, edit and remove products in my stock book. | New IDs do not collide; name/category and nonnegative values are validated; edits update only this tenant; delete removes that row; an empty shop starts with headers, not sample records. | ✅ Operations → Stock; UI flow/isolation tests |
| 4 | **Low-stock assessment** — as an owner, I want items at or below their reorder point highlighted. | `current_stock <= reorder_point` is the sole flag rule; dashboard and Operations show the same tenant-only results. | ✅ `get_low_stock`; offline procurement and UI tests |
| 5 | **Record incoming purchases** — as an owner, I want each delivery saved and on-hand stock increased. | Item, quantity, price, supplier, payment status and date are recorded; quantity received is positive; this tenant's stock rises by that quantity. | ✅ Operations → Purchases; UI integration test |
| 6 | **Record counter sales** — as an owner, I want sales recorded and shelf stock reduced. | Item, quantity, price, payment method and date are recorded; stock is reduced by the sale; an attempted oversell is refused and leaves both records unchanged. | ✅ Operations → Sales; UI integration test |
| 7 | **Keep supplier quotes** — as an owner, I want supplier prices, minimum quantities and lead times recorded for planning. | Quotes are attached to this tenant and its products; supplier is required; cheapest valid quote is used by existing procurement logic. | ✅ Operations → Supplier quotes; quote comparison offline tests |
| 8 | **Review business activity** — as an owner, I want to see my purchases, sales and reorder decisions together. | Activity rows come from the selected tenant; drafts show status, date, line count and estimated total. | ✅ Operations → Activity; UI flow test |
| 9 | **Plan restock within my cash budget** — as an owner, I want a fast, explainable list of what fits. | Default quick plan uses deterministic stock/history/quote calculations with no model call; budget is a hard ceiling; urgency, included/deferred items and missing information are shown with data sources. The optional AI-agent path remains bounded and has a short retry/turn budget. | ✅ Restock AI; procurement and UI workflow tests |
| 10 | **Send the saved draft to my review queue** — as an owner, I want the next action to be clear after planning. | A successfully saved draft automatically opens Approvals; the draft is tenant-scoped, carries a workflow session and allocated budget, and is still pending a human. No draft is created when nothing is eligible or priced. | ✅ Restock → Approvals handoff; session/workflow UI test |
| 11 | **Adjust a suggested quantity** — as an owner, I want to correct the AI's proposed quantity before deciding. | Only a pending draft can be edited; the reason and original suggestion are retained; line total and draft total are recalculated by Python; edits are audited. | ✅ Approvals; `approvals.edit_quantity`; UI integration test |
| 12 | **Approve or reject a draft myself** — as the owner, I want to make and record the final decision. | Confirmation must match the selected decision; a rejection needs a reason; the 200% safety cap and saved budget are enforced; the state machine, draft and audit trail record the decision; AI has no decision tool. | ✅ Approvals; Week 4/6/8 tests and UI integration test |
| 13 | **Ask and edit shop policies** — as an owner, I want cited policy answers and the ability to keep local rules current. | Q&A retrieves only the active tenant's policy corpus and shows sources; edits/additions save under that tenant and invalidate its retrieval index; other shops' answers do not include the custom document. | ✅ Dashboard → Policy Q&A / View & edit policies; tenant RAG and UI tests |
| 14 | **Continue a copilot conversation without an unbounded prompt** — as an owner, I want follow-up questions to retain useful context. | Context is held in the current browser session and tenant key; four recent turns are retained and older turns are compacted into a 1,400-character extract without another model request; current question takes priority; Clear conversation removes that shop's chat context; switching shops never carries it across. | ✅ bounded context helper and UI session tests |
| 15 | **Trace why a plan was made** — as an owner, I want to see the process and underlying records. | Restock shows Sense → Plan → Draft steps, its records and sources; AI runs retain tool names, stop reason, model latency and a trace; deterministic code owns all quantities and decisions. | ✅ trace modules and restock handoff details |
| 16 | **Use the prototype safely** — as an owner, I want clear limits and recoverable failures. | AI may draft/explain but cannot order/pay/contact suppliers/approve; provider outages return a handoff; retries, model attempts, turns and tool calls are bounded; no external order is made. | ✅ registry, guardrails, offline safety suites |
| 17 | **Upload a PDF supplier quote** — as an owner, I want to extract prices from a supplier document. | Parse product, price and totals or show a clear unreadable-file error. | ❌ Descoped from this prototype; quotes are entered manually in Operations. |

The original Week 1 stories used sugar, dairy and cooking oil examples. The prototype and synthetic
catalogue use stationery examples. Sales are recorded by the UI, while the existing reorder-demand
estimator continues to use purchase history until sales-based demand is separately evaluated.

**Prototype boundary:** tenant IDs separate records in storage, but entering a business name is not
authentication. Do not enter private or production business information. On Render's free plan,
local files can be reset when the service restarts; use persistent storage before relying on it for
durable business records.
