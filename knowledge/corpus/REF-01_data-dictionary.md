# Data Dictionary

Synthetic, team-created reference describing the shop's data files used by the assistant's tools.

## current_stock.csv
One row per item: item_id (for example ITM001), item_name, category (Stationery, Office or Electronics), current_stock (units on hand), reorder_point (units), unit_cost_ugx (typical cost per unit).

## past_purchases.csv
One row per item per month of purchases during 2025: date (the 15th of the month), item_id, quantity_purchased, historical_unit_price_ugx. Only ten items have purchase history; newer items have none.

## supplier_quotes.csv
One row per supplier per item: supplier_name, item_id, offered_unit_price_ugx, min_order_qty, lead_time_days. There are three suppliers: Kampala Office Supplies, Nakawa Stationers and Entebbe Traders Ltd.

## Draft requisitions
Drafts are saved as files with an ID such as REQ-20261002-231943-F28E, the creation time, the creator, the lines, the estimated budget and the status.
