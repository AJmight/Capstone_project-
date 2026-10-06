# AI Engineering Log — Week 3 (and MVP additions, 2026-10-06)

**AI Engineering Lead:** Mwesigwa Arnold Mugahi (23/U/244738/PS)

**AI tools used:** Google Gemini (product model; proof-reading failing code), Claude Code (coding partner),
DeepSeek (supervisor/teacher), ChatGPT (concept explanations), GitHub Copilot (inline error fixes).

## Material AI-assisted decisions

| # | Decision / artefact | AI source | Human review & verification |
|:---:|:---|:---|:---|
| 1 | 12 synthetic corpus documents | Claude (drafted) | Overlapping facts checked against `supplier_quotes.csv`; marked synthetic in the source register |
| 2 | BM25 retrieval instead of embeddings | Claude | Retrieval metrics 10/10 hit@3; trade-off documented |
| 3 | Next-section expansion, stemmer and boilerplate fixes | Claude, from failing tests | Before/after metrics saved per index version |
| 4 | Citation checker and its grouped-citation fix | Claude | Run 1 vs run 2 evidence kept |
| 5 | MVP tools `get_inventory`, `query_purchase_history`; approval edit (US 9) | Claude | 7 offline MVP tests with independently recomputed totals |
| 6 | Prompt v2.3.0 → v2.4.0 | Claude | v2.4.0 fixed F-16 found in live test M-06 |
| 7 | Console app `src/app.py` | Claude | Scripted smoke test (stock overview, drafts list) |

## Things AI got wrong (caught by tests or review)

- Claude's citation parser rejected a valid "[S1, S3]" citation (R-5).
- Claude wrote two test expectations that were wrong (RP-05 "30%", M-05 keyword list) — corrected with
  comments, earlier runs kept as evidence.
- gemini-3.5-flash ignored a helpful `UNKNOWN_CATEGORY` error and gave a generic refusal (F-16).
- A viewer's model again tried an ungranted tool (F-07 recurring) — blocked by the registry.

## Data handling

Corpus and CSVs are synthetic; nothing confidential is sent to Gemini. Traces contain questions,
retrieved chunk IDs and answers only.
