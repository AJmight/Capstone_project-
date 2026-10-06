# MVP Live Agent Tests

Run at 2026-10-06T06:11:19 | **6/6 passed**

| id | question | expected | tools | models | passed |
|---|---|---|---|---|---|
| M-01 | Show me the stock levels for Office items. | get_inventory(Office); names Stapler Medium and Files (Box) | get_inventory | gemini-3.6-flash, gemini-3.6-flash | **PASS** |
| M-02 | How many Bic Pens did we buy from March to May 2025, and how much did we spend? | query_purchase_history; answer has 170 and 79,295 | query_purchase_history | gemini-3.6-flash, gemini-3.6-flash | **PASS** |
| M-03 | Tell me about our purchases. | no tool call; asks one clarifying question (AC 6.2) |  | gemini-3.6-flash | **PASS** |
| M-04 | Who is allowed to approve a requisition worth UGX 800,000? | search_policy; 'owner'; cites POL-01 | search_policy, search_policy | gemini-3.5-flash, gemini-3.5-flash, gemini-3.5-flash | **PASS** |
| M-05 | How many rulers did we buy in November 2024? | query_purchase_history; says no records for that period; no invented number | query_purchase_history | gemini-3.5-flash, gemini-3.5-flash | **PASS** |
| M-06 | Show me inventory for dairy products. | explains dairy is not a category and lists Electronics, Office, Stationery | get_inventory | gemini-3.5-flash, gemini-3.5-flash-lite | **PASS** |
