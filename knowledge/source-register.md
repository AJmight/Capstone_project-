# Corpus / Source Register — Week 3

The controlled corpus the RAG pipeline (`src/rag/`) and the agent's `search_policy` tool search.
Brief requirement: "Assemble a controlled corpus (recommended 10–50 documents or equivalent records)
and record provenance."

| Field | Value |
|:---|:---|
| **Location** | `knowledge/corpus/*.md` |
| **Documents** | 12 (about 1,900 words) → 61 searchable chunks (index v1.1.0) |
| **Provenance** | All documents are **synthetic and team-created** on 2026-10-06 for this capstone. They describe a fictional shop (Kiwatule Stationery & Office Supplies) and fictional suppliers. No real policy, company, person or personal data is included. |
| **Author** | Mwesigwa Arnold Mugahi (AI Engineering Lead), drafted with Claude Code; reviewed for consistency with `data/*.csv` |
| **Licence / permission** | Team-owned, free to use within the project. Safe to send to the Gemini free tier (no confidential data). |
| **Consistency rule** | Facts that also exist in the CSVs (suppliers, minimum order quantities, lead times) must match the CSVs exactly. |
| **Change control** | Edit a document → re-run `py tests\test_week3_rag.py --offline` (retrieval) and record the change below. |

## Documents

| Doc ID | File | Title | Topics (what questions it answers) | Matches CSV? |
|:---|:---|:---|:---|:---:|
| POL-01 | `POL-01_procurement-policy.md` | Procurement Policy | who may request, **approval thresholds** (≤500k supervisor/owner; >500k owner; >2M owner + justification), quotations, 200 % safeguard, record retention (5 years) | n/a |
| POL-02 | `POL-02_payments-and-budget-policy.md` | Payments and Budget Policy | only the owner pays; mobile money/bank; no cash > UGX 200,000; pay after delivery; weekly budget 300k–600k; ±10 % range | n/a |
| SUP-01 | `SUP-01_kampala-office-supplies.md` | Supplier: Kampala Office Supplies | MOQ 20, ~3 days, delivery fee rule, COD/14-day credit, 7-day returns | ✓ MOQ 20, lead 3 |
| SUP-02 | `SUP-02_nakawa-stationers.md` | Supplier: Nakawa Stationers | MOQ 10, ~2 days, COD only, 3-day returns, when to use for urgent orders | ✓ MOQ 10, lead 2 |
| SUP-03 | `SUP-03_entebbe-traders.md` | Supplier: Entebbe Traders Ltd | MOQ 15, ~5 days, Tue/Fri deliveries, 30-day credit, returns | ✓ MOQ 15, lead 5 |
| PRC-01 | `PRC-01_requisition-process.md` | Requisition and Approval Process | 6 steps from stock check to receiving goods; edit before approval; reasons for rejection | n/a |
| PRC-02 | `PRC-02_reorder-guidelines.md` | Reorder Guidelines | reorder point, the 1.5-month formula, items without history, urgency, **school-term +30 %** | ✓ same formula as tools |
| PRC-03 | `PRC-03_stock-counting-and-storage.md` | Stock Counting and Storage | Saturday counts, monthly count, 5 % discrepancy rule, storage against water damage, backups | n/a |
| GDE-01 | `GDE-01_handling-supplier-pressure.md` | Handling Supplier Pressure | what junior staff do when sales reps push; no gifts | n/a |
| GDE-02 | `GDE-02_ai-assistant-usage-rules.md` | Rules for Using the AI Assistant | what the assistant can/cannot do; roles; checking its numbers | ✓ same roles as registry |
| FAQ-01 | `FAQ-01_procurement-faq.md` | Procurement FAQ | owner away, deferred items, urgent supplier, retention, damaged delivery, cash | n/a |
| REF-01 | `REF-01_data-dictionary.md` | Data Dictionary | meaning of every CSV column; draft ID format | ✓ |

## Deliberately NOT in the corpus (used for "unanswerable" tests)

Supplier staff names and phone numbers, VAT and tax rates, competitor prices, staff salaries, weather,
bulk discounts, Entebbe Traders' delivery fee, this week's exact budget, last year's total spend.

## Change log

| Date | Change | By |
|:---|:---|:---|
| 2026-10-06 | Initial 12 documents | Mwesigwa Arnold Mugahi |
