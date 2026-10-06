# Week 3 Retrieval Results - index v1.0.0

Run at 2026-10-06T05:57:48 | 73 chunks | **hit@3 9/10**, context hit 10/10, MRR 0.85

| ID | Type | Question | Expected chunk | Rank | hit@3 | Context hit | Top 3 (score) |
|---|---|---|---|:---:|:---:|:---:|---|
| RA-01 | answerable | Who can approve a requisition of UGX 800,000? | POL-01#approval-thresholds | 1 | yes | yes | POL-01#approval-thresholds (8.11), FAQ-01#can-the-ai-assistant-approve-an-order-if-the-owner-is-away (6.32), PRC-01#step-4-approve-or-reject (4.58) |
| RA-02 | answerable | What is the minimum order quantity at Nakawa Stationers? | SUP-02#ordering-and-minimum-order | 1 | yes | yes | SUP-02#ordering-and-minimum-order (13.79), SUP-03#ordering-and-minimum-order (9.26), FAQ-01#which-supplier-do-we-use-for-an-urgent-small-order (8.88) |
| RA-03 | answerable | How long do we keep requisition records? | FAQ-01#how-long-do-we-keep-requisition-records | 1 | yes | yes | FAQ-01#how-long-do-we-keep-requisition-records (18.42), POL-01#records (4.74), PRC-03#record-backups (3.31) |
| RA-04 | answerable | Can staff pay a supplier by mobile money? | POL-02#who-pays-suppliers | 1 | yes | yes | POL-02#who-pays-suppliers (8.78), POL-02#payment-methods (6.28), GDE-02#what-the-assistant-cannot-do (6.28) |
| RA-05 | answerable | What should staff do when a sales rep pushes a today-only discount? | GDE-01#what-staff-should-do | 3 | yes | yes | GDE-01#the-problem (16.44), SUP-01#ordering-and-minimum-order (3.21), GDE-01#what-staff-should-do (2.57) |
| RP-01 | partial | What is Entebbe Traders' delivery fee and on which days do they deliver? | SUP-03#delivery | 1 | yes | yes | SUP-03#delivery (10.92), SUP-03#payment-terms (10.19), SUP-01#delivery (8.75) |
| RP-02 | partial | What is our weekly restock budget this week and how is it set? | POL-02#weekly-restock-budget | 1 | yes | yes | POL-02#weekly-restock-budget (14.95), FAQ-01#what-happens-to-items-that-do-not-fit-the-weekly-budget (13.73), PRC-02#urgency (5.21) |
| RP-03 | partial | How many days does Kampala Office Supplies take to deliver, and what discount do they give for bulk orders? | SUP-01#delivery | 5 | **no** | yes | SUP-01#payment-terms (9.95), SUP-01#overview (8.95), SUP-01#ordering-and-minimum-order (8.77) |
| RP-04 | partial | Who approves requisitions above UGX 2,000,000 and how much did we spend on approved requisitions last year? | POL-01#approval-thresholds | 1 | yes | yes | POL-01#approval-thresholds (17.27), FAQ-01#how-long-do-we-keep-requisition-records (8.42), POL-01#who-may-request-a-purchase (7.92) |
| RP-05 | partial | When are reorder points raised for school terms, and by how much for calculators? | PRC-02#school-terms-and-seasons | 1 | yes | yes | PRC-02#school-terms-and-seasons (17.54), FAQ-01#who-sets-reorder-points (13.91), PRC-02#reorder-point (7.96) |
| RU-01 | unanswerable | What is the phone number of the Kampala Office Supplies manager? | - | - | n/a | n/a | SUP-01#overview (8.95), SUP-01#introduction (6.92), SUP-02#overview (6.45) |
| RU-02 | unanswerable | What is the VAT rate on stationery in Uganda? | - | - | n/a | n/a | POL-02#introduction (3.04), SUP-03#returns (2.97), SUP-01#overview (2.72) |
| RU-03 | unanswerable | What prices does our competitor across the road charge? | - | - | n/a | n/a | SUP-02#overview (3.41), SUP-01#overview (3.19), POL-02#budget-estimates (2.68) |
| RU-04 | unanswerable | How much is the shop assistant's monthly salary? | - | - | n/a | n/a | PRC-02#how-much-to-order (7.39), GDE-02#data (6.93), REF-01#introduction (6.86) |
| RU-05 | unanswerable | Will it rain in Kampala tomorrow? | - | - | n/a | n/a | SUP-01#overview (2.88), SUP-01#introduction (2.34), SUP-03#delivery (2.23) |
