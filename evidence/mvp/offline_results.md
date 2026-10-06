# MVP Offline Tests

Run at 2026-10-06T06:21:09 | **7/7 passed**

| id | test | passed | detail |
|---|---|---|---|
| M-O01 | get_inventory('office') returns only Office items, with is_low flags; no category = all 15. | **PASS** |  |
| M-O02 | An unknown category (the old 'dairy' story) gives UNKNOWN_CATEGORY listing real categories. | **PASS** |  |
| M-O03 | query_purchase_history totals match an independent recomputation (March-May 2025, Bic Pens). | **PASS** |  |
| M-O04 | No data for Nov 2024 -> note + data_range; bad month and reversed range -> INVALID_PARAMETER. | **PASS** |  |
| M-O05 | search_policy via the registry returns source IDs; viewers may use it; bad top_k rejected. | **PASS** |  |
| M-O06 | US 9: editing a line keeps the AI suggestion, recomputes totals, and is audited. | **PASS** |  |
| M-O07 | Edit needs a reason, only on undecided drafts, only existing lines; >cap sets requires_override. | **PASS** |  |
