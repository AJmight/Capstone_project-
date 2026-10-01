"""
Generates synthetic inventory, purchase history, and supplier quotes
for the SME Procurement Support Agent.
All data is fictional — safe to commit to the repo.
"""
import csv
import os
import random
from datetime import date, timedelta

random.seed(42)  # reproducible

os.makedirs("data", exist_ok=True)

# ---------- 1. Inventory ----------
inventory = [
    # item_id, item_name, category, current_stock, reorder_point, unit_cost_ugx
    ("ITM001", "Bic Pens (Blue)",       "Stationery", 5,   20,  500),
    ("ITM002", "A4 Exercise Books",     "Stationery", 45,  10,  2500),
    ("ITM003", "Rulers 30cm",           "Stationery", 2,   15,  1000),
    ("ITM004", "Pencils HB",            "Stationery", 60,  25,  300),
    ("ITM005", "Erasers",               "Stationery", 8,   20,  200),
    ("ITM006", "A4 Printing Paper (Rim)","Stationery", 12,  15,  12000),
    ("ITM007", "Stapler Medium",        "Office",     3,   5,   8500),
    ("ITM008", "Staple Pins (Box)",     "Office",     40,  20,  1500),
    ("ITM009", "Files (Box)",           "Office",     6,   10,  3500),
    ("ITM010", "Envelopes A4 (Pack)",   "Office",     25,  15,  2000),
    ("ITM011", "Cellotape (Roll)",      "Office",     4,   10,  800),
    ("ITM012", "Glue Stick",            "Stationery", 18,  20,  1200),
    ("ITM013", "Marker Pens (Black)",   "Stationery", 7,   15,  900),
    ("ITM014", "Notebooks A5",          "Stationery", 30,  20,  1500),
    ("ITM015", "Calculator (Basic)",    "Electronics",2,   5,   15000),
]

with open("data/current_stock.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["item_id", "item_name", "category", "current_stock", "reorder_point", "unit_cost_ugx"])
    w.writerows(inventory)

# ---------- 2. Purchase History ----------
# 12 months of monthly purchases for the first 10 items
purchases = []
start = date(2025, 1, 1)
for item_id, name, cat, stock, reorder, cost in inventory[:10]:
    for month_offset in range(12):
        month = start.month + month_offset
        year = start.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        qty = random.randint(10, 80)
        price = int(cost * random.uniform(0.9, 1.1))
        purchases.append((f"{year}-{month:02d}-15", item_id, qty, price))

with open("data/past_purchases.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["date", "item_id", "quantity_purchased", "historical_unit_price_ugx"])
    w.writerows(purchases)

# ---------- 3. Supplier Quotes ----------
suppliers = [
    ("Kampala Office Supplies", 0.95, 20, 3),   # cheapest, longer lead time
    ("Nakawa Stationers",       1.00, 10, 2),   # mid price, fast
    ("Entebbe Traders Ltd",     1.08, 15, 5),   # priciest, slowest
]

quotes = []
for item_id, name, cat, stock, reorder, cost in inventory:
    for supplier, markup, moq, lead in suppliers:
        quoted = int(cost * markup * random.uniform(0.98, 1.02))
        quotes.append((supplier, item_id, quoted, moq, lead))

with open("data/supplier_quotes.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["supplier_name", "item_id", "offered_unit_price_ugx", "min_order_qty", "lead_time_days"])
    w.writerows(quotes)

print(" Created:")
print("   data/current_stock.csv")
print("   data/past_purchases.csv")
print("   data/supplier_quotes.csv")