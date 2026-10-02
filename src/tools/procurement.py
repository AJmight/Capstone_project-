"""
Deterministic procurement tools (Week 4).
=========================================

WHAT THIS FILE IS
-----------------
Plain Python functions that do the procurement maths EXACTLY. The AI model
never calculates numbers any more: it asks for one of these tools by name,
src/tools/registry.py checks the request and runs the function, and the
result (a dictionary) is sent back to the model to explain to the user.

This fixes failure F-04 from Week 2, where gemini-3.5-flash-lite computed
three wrong reorder quantities (e.g. Erasers 70 instead of 63).

THE FOUR TOOLS
--------------
  1. get_low_stock()                     -> which items are at/below reorder point
  2. compare_supplier_quotes(item)       -> all quotes for one item, cheapest first
  3. estimate_reorder_quantity(item)     -> reorder quantity + full working + 200% cap
  4. draft_requisition(items)            -> builds a DRAFT requisition, saves it to
                                            data/drafts/ (the only "side effect"),
                                            status always "DRAFT - AWAITING HUMAN APPROVAL"

There is deliberately NO approve / order / pay tool. Approval is done by a
human with src/approvals.py, which the model cannot reach.

WHERE THE DATA COMES FROM
-------------------------
  data/current_stock.csv    item_id, item_name, category, current_stock, reorder_point, unit_cost_ugx
  data/past_purchases.csv   date, item_id, quantity_purchased, historical_unit_price_ugx
  data/supplier_quotes.csv  supplier_name, item_id, offered_unit_price_ugx, min_order_qty, lead_time_days
The CSVs are re-read on every call, so edits to the files are picked up immediately.

ERROR CONVENTION
----------------
Tools never crash the agent. Any problem is returned as {"error": "CODE: message"}:
  INVALID_DATA    a CSV is missing, has wrong columns, or a number cannot be read
  UNKNOWN_ITEM    no item matches what was asked for
  AMBIGUOUS_ITEM  several items match (e.g. "pens" -> Bic Pens and Marker Pens)
  INVALID_PARAMETER  a bad argument reached the function

The business rules here are the same ones written in prompts/procurement_assistant_v1.2.0.md
(Section 4); the prompt v2.0.0 now tells the model to use these tools instead.

Owner: Mwesigwa Arnold Mugahi (AI Engineering Lead)
Version: 1.0.0 (Week 4)
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
import csv                                    # read the CSV files row by row
import json                                   # save draft requisitions as JSON files
import math                                   # math.ceil() for "round UP"
import uuid                                   # random suffix so draft IDs are unique
from datetime import datetime, timezone       # timestamps for draft IDs and records
from fractions import Fraction                # exact arithmetic (no 0.1 + 0.2 float surprises)
from functools import wraps                   # keeps function names when we wrap them
from pathlib import Path                      # file paths that work on Windows and Linux

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Folder with the three CSVs. Tests replace this with a temporary folder
# (procurement.DATA_DIR = ...) to simulate missing or broken data.
DATA_DIR = Path("data")

# Where draft requisitions are written. This is git-ignored: drafts are runtime records.
DRAFTS_DIR = Path("data/drafts")

# Business-rule constants, named so a reviewer can find and question them.
SAFETY_MULTIPLIER = Fraction(3, 2)   # order enough for 1.5 months of average demand
CAP_MULTIPLIER = 2                   # User Story 12: flag orders above 200% of the largest past purchase
MAX_ITEMS_PER_DRAFT = 20             # keeps one draft a reasonable size

DRAFT_STATUS = "DRAFT - AWAITING HUMAN APPROVAL"   # the only status a tool may ever set

# The columns each CSV must have. Checked on every read (TC-05 style "missing column" protection).
REQUIRED_COLUMNS = {
    "current_stock.csv": ["item_id", "item_name", "category", "current_stock",
                          "reorder_point", "unit_cost_ugx"],
    "past_purchases.csv": ["date", "item_id", "quantity_purchased", "historical_unit_price_ugx"],
    "supplier_quotes.csv": ["supplier_name", "item_id", "offered_unit_price_ugx",
                            "min_order_qty", "lead_time_days"],
}


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
class ToolError(Exception):
    """A predictable problem (bad data, unknown item). Becomes {"error": "CODE: message"}."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def as_result(self) -> dict:
        return {"error": f"{self.code}: {self.message}"}


def _returns_errors_as_results(func):
    """
    Decorator: if the wrapped tool raises ToolError, return {"error": ...} instead.

    This means every tool below can simply `raise ToolError(...)` when something
    is wrong, and the agent always receives a dictionary it can explain.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ToolError as e:
            return e.as_result()
    return wrapper


# ---------------------------------------------------------------------------
# Data access helpers (read + validate the CSVs)
# ---------------------------------------------------------------------------
def _read_csv(name: str) -> list[dict]:
    """
    Read one CSV from DATA_DIR and return a list of row dictionaries.

    Raises ToolError("INVALID_DATA") if the file is missing or a required column is absent.
    Example row: {"item_id": "ITM001", "item_name": "Bic Pens (Blue)", "current_stock": "5", ...}
    Note: every value is still a STRING here; _int() converts numbers.
    """
    path = DATA_DIR / name
    if not path.exists():
        raise ToolError("INVALID_DATA", f"{name} not found in {DATA_DIR}")
    # utf-8-sig also accepts files saved by Excel with a hidden BOM at the start.
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []
        missing = [c for c in REQUIRED_COLUMNS.get(name, []) if c not in columns]
        if missing:
            raise ToolError("INVALID_DATA", f"{name} is missing columns: {', '.join(missing)}")
        return list(reader)


def _int(row: dict, column: str, file: str) -> int:
    """Convert one CSV cell to int, with a clear error if it is blank or not a number."""
    try:
        return int(row[column])
    except (TypeError, ValueError):
        raise ToolError("INVALID_DATA",
                        f"{file}: {column}={row.get(column)!r} is not a whole number "
                        f"(item {row.get('item_id')})")


def _resolve_item(ref, inventory: list[dict]) -> dict:
    """
    Find the inventory row the user/model means. Accepts an item ID or a name.

    Matching order (first rule that finds something wins):
      1. exact item_id, ignoring case        "itm001"            -> ITM001
      2. exact item_name, ignoring case      "bic pens (blue)"   -> ITM001
      3. the text appears inside one name    "calculator"        -> ITM015
    If step 3 finds several items we refuse to guess: AMBIGUOUS_ITEM lists them.
    """
    if not isinstance(ref, str) or not ref.strip():
        raise ToolError("INVALID_PARAMETER", "item must be a non-empty item ID or item name")
    text = ref.strip().casefold()            # casefold() = lower-case that also handles accents

    for row in inventory:                    # rule 1: exact ID
        if row["item_id"].casefold() == text:
            return row
    for row in inventory:                    # rule 2: exact name
        if row["item_name"].casefold() == text:
            return row
    partial = [row for row in inventory if text in row["item_name"].casefold()]   # rule 3
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        options = ", ".join(f"{r['item_id']} {r['item_name']}" for r in partial)
        raise ToolError("AMBIGUOUS_ITEM", f"'{ref}' matches several items: {options}. Ask the user which one.")
    raise ToolError("UNKNOWN_ITEM", f"'{ref}' is not in current_stock.csv")


def _quotes_for(item_id: str, quote_rows: list[dict]) -> list[dict]:
    """All quotes for one item as clean dicts, sorted cheapest first (tie -> faster delivery)."""
    quotes = [
        {
            "supplier_name": r["supplier_name"],
            "unit_price_ugx": _int(r, "offered_unit_price_ugx", "supplier_quotes.csv"),
            "min_order_qty": _int(r, "min_order_qty", "supplier_quotes.csv"),
            "lead_time_days": _int(r, "lead_time_days", "supplier_quotes.csv"),
        }
        for r in quote_rows if r["item_id"] == item_id
    ]
    # Sort by a tuple: first by price, and only if prices are equal, by lead time.
    quotes.sort(key=lambda q: (q["unit_price_ugx"], q["lead_time_days"]))
    return quotes


def _history_for(item_id: str, history_rows: list[dict]) -> list[int]:
    """Monthly purchase quantities for one item, e.g. [24, 45, 27, ...]."""
    return [_int(r, "quantity_purchased", "past_purchases.csv")
            for r in history_rows if r["item_id"] == item_id]


def _reorder_calculation(item: dict, history: list[int], best_quote: dict | None) -> dict:
    """
    The reorder formula from the prompt spec, done exactly in Python.

        avg_monthly     = sum(history) / months
        raw_qty         = avg_monthly * 1.5 - current_stock
        recommended_qty = ceil(raw_qty), never below 0
        if 0 < recommended_qty < supplier MOQ  -> raise to MOQ
        cap             = 2 * largest single past purchase
        requires_override = recommended_qty > cap

    Fraction keeps the numbers exact: 555/12 * 3/2 - 5 is exactly 515/8 = 64.375,
    so ceil() gives 65 every time (floats can drift, e.g. 64.99999999).
    Returns a dict with the quantity AND a human-readable "basis" (User Story 7, AC 7.2).
    """
    stock = _int(item, "current_stock", "current_stock.csv")
    reorder_point = _int(item, "reorder_point", "current_stock.csv")
    base = {
        "item_id": item["item_id"],
        "item_name": item["item_name"],
        "current_stock": stock,
        "reorder_point": reorder_point,
        "is_low": stock <= reorder_point,
        "months_of_history": len(history),
        "selected_supplier": best_quote["supplier_name"] if best_quote else "UNKNOWN - Quote Required",
        "min_order_qty": best_quote["min_order_qty"] if best_quote else 0,
        "requires_override": False,
        "override_reason": "",
    }

    # Case 1: enough stock -> never recommend buying (the TC-06 over-ordering problem).
    if not base["is_low"]:
        return {**base, "avg_monthly_purchases": None, "recommended_qty": 0, "safety_cap": None,
                "basis": f"stock {stock} is above reorder point {reorder_point}; no reorder needed"}

    # Case 2: no history -> we refuse to invent a number; a human decides.
    if not history:
        return {**base, "avg_monthly_purchases": None, "recommended_qty": 0, "safety_cap": None,
                "basis": "No purchase history - human must set quantity"}

    # Case 3: the normal calculation.
    total = sum(history)
    avg = Fraction(total, len(history))                  # exact average, e.g. 555/12
    raw = avg * SAFETY_MULTIPLIER - stock                # exact, e.g. 515/8
    qty = max(math.ceil(raw), 0)                          # round UP; never negative
    basis = (f"{total} purchased over {len(history)} months = {float(avg):.2f}/month; "
             f"{float(avg):.2f} x 1.5 = {float(avg * SAFETY_MULTIPLIER):.3f}; "
             f"minus stock {stock} = {float(raw):.3f}; rounded up to {qty}")
    if qty == 0:
        basis += "; average demand is already covered by current stock - human to decide"
    elif best_quote and qty < best_quote["min_order_qty"]:
        basis += f"; raised to supplier minimum order quantity {best_quote['min_order_qty']}"
        qty = best_quote["min_order_qty"]

    cap = CAP_MULTIPLIER * max(history)                   # e.g. 2 x 79 = 158 for Bic Pens
    over_cap = qty > cap
    return {
        **base,
        "avg_monthly_purchases": round(float(avg), 2),
        "recommended_qty": qty,
        "basis": basis,
        "safety_cap": cap,
        "requires_override": over_cap,
        "override_reason": (f"{qty} exceeds 200% cap of {cap}; human must justify" if over_cap else ""),
    }


# ---------------------------------------------------------------------------
# Tool 1: get_low_stock
# ---------------------------------------------------------------------------
@_returns_errors_as_results
def get_low_stock() -> dict:
    """
    List every item where current_stock <= reorder_point.

    Reads: current_stock.csv
    Returns: {"count": 10, "items": [{"item_id", "item_name", "current_stock", "reorder_point"}, ...]}
    """
    inventory = _read_csv("current_stock.csv")
    low = []
    for row in inventory:
        stock = _int(row, "current_stock", "current_stock.csv")
        reorder_point = _int(row, "reorder_point", "current_stock.csv")
        if stock <= reorder_point:                       # the low-stock rule
            low.append({"item_id": row["item_id"], "item_name": row["item_name"],
                        "current_stock": stock, "reorder_point": reorder_point})
    return {"count": len(low), "items": low, "total_items_in_inventory": len(inventory),
            "source": "current_stock.csv"}


# ---------------------------------------------------------------------------
# Tool 2: compare_supplier_quotes
# ---------------------------------------------------------------------------
@_returns_errors_as_results
def compare_supplier_quotes(item: str) -> dict:
    """
    All supplier quotes for one item, cheapest first.

    Reads: current_stock.csv (to resolve the item), supplier_quotes.csv
    Returns: {"item_id", "item_name", "quote_count", "cheapest": {...} or None, "all_quotes": [...]}
    """
    inventory = _read_csv("current_stock.csv")
    row = _resolve_item(item, inventory)                  # "Bic Pens" -> the ITM001 row
    quotes = _quotes_for(row["item_id"], _read_csv("supplier_quotes.csv"))
    result = {"item_id": row["item_id"], "item_name": row["item_name"],
              "quote_count": len(quotes), "cheapest": quotes[0] if quotes else None,
              "all_quotes": quotes, "source": "supplier_quotes.csv"}
    if not quotes:
        result["note"] = "No quotes found for this item - a quote must be requested"
    return result


# ---------------------------------------------------------------------------
# Tool 3: estimate_reorder_quantity
# ---------------------------------------------------------------------------
@_returns_errors_as_results
def estimate_reorder_quantity(item: str) -> dict:
    """
    Deterministic reorder quantity for one item (fixes F-04).

    Reads: all three CSVs
    Returns: the dict built by _reorder_calculation(), e.g. for ITM001:
      {"recommended_qty": 65, "basis": "555 purchased over 12 months = 46.25/month; ...",
       "selected_supplier": "Kampala Office Supplies", "safety_cap": 158, "requires_override": False, ...}
    """
    inventory = _read_csv("current_stock.csv")
    row = _resolve_item(item, inventory)
    quotes = _quotes_for(row["item_id"], _read_csv("supplier_quotes.csv"))
    history = _history_for(row["item_id"], _read_csv("past_purchases.csv"))
    result = _reorder_calculation(row, history, quotes[0] if quotes else None)
    result["source"] = "current_stock.csv, past_purchases.csv, supplier_quotes.csv"
    return result


# ---------------------------------------------------------------------------
# Tool 4: draft_requisition  (the only tool with a side effect: it saves a file)
# ---------------------------------------------------------------------------
@_returns_errors_as_results
def draft_requisition(items: list[str], created_by: str = "unknown") -> dict:
    """
    Build a DRAFT purchase requisition for the given items and save it.

    items       list of item IDs or names chosen by the model, e.g. ["ITM001", "Rulers 30cm"]
    created_by  the logged-in user. Filled in by registry.py from the session,
                NEVER by the model (so the AI cannot pretend to be the owner).

    Rules applied:
      - only LOW items get a line; well-stocked items go to "skipped" with the reason
      - quantity, supplier, line totals, budget and the +/-10% range are all computed here
      - the draft is saved to data/drafts/<draft_id>.json with status
        "DRAFT - AWAITING HUMAN APPROVAL"; nothing is sent to any supplier
    Returns the full draft record (or status NOT_CREATED if nothing qualified).
    """
    # --- validate the argument shape (registry.py also checks this; defence in depth) ---
    if not isinstance(items, list) or not items:
        raise ToolError("INVALID_PARAMETER", "items must be a non-empty list of item IDs or names")
    if len(items) > MAX_ITEMS_PER_DRAFT:
        raise ToolError("INVALID_PARAMETER", f"at most {MAX_ITEMS_PER_DRAFT} items per draft")

    # --- read all data once ---
    inventory = _read_csv("current_stock.csv")
    quote_rows = _read_csv("supplier_quotes.csv")
    history_rows = _read_csv("past_purchases.csv")

    # --- resolve names to rows, removing duplicates but keeping the user's order ---
    rows, seen = [], set()
    for ref in items:
        row = _resolve_item(ref, inventory)      # raises UNKNOWN_ITEM / AMBIGUOUS_ITEM
        if row["item_id"] not in seen:
            seen.add(row["item_id"])
            rows.append(row)

    # --- build one line per low item ---
    lines, skipped = [], []
    for row in rows:
        quotes = _quotes_for(row["item_id"], quote_rows)
        best = quotes[0] if quotes else None
        calc = _reorder_calculation(row, _history_for(row["item_id"], history_rows), best)
        if not calc["is_low"]:
            skipped.append({"item_id": row["item_id"], "item_name": row["item_name"],
                            "reason": calc["basis"]})
            continue
        unit_price = best["unit_price_ugx"] if best else 0
        lines.append({
            "item_id": calc["item_id"],
            "item_name": calc["item_name"],
            "current_stock": calc["current_stock"],
            "reorder_point": calc["reorder_point"],
            "recommended_qty": calc["recommended_qty"],
            "quantity_basis": calc["basis"],
            "selected_supplier": calc["selected_supplier"],
            "unit_price_ugx": unit_price,
            "min_order_qty": best["min_order_qty"] if best else 0,
            "lead_time_days": best["lead_time_days"] if best else 0,
            "total_cost_ugx": calc["recommended_qty"] * unit_price,   # exact integer maths
            "requires_override": calc["requires_override"],
            "override_reason": calc["override_reason"],
        })

    if not lines:
        # Nothing to buy -> do NOT create a file (no empty drafts cluttering the approval queue).
        return {"draft_id": None, "status": "NOT_CREATED", "lines": [], "skipped": skipped,
                "estimated_budget_ugx": 0, "budget_range_ugx": {"low": 0, "high": 0},
                "note": "None of the requested items is low on stock; nothing was drafted."}

    total = sum(line["total_cost_ugx"] for line in lines)
    # +/-10% budget range (User Story 8), rounded half-up to the nearest shilling using
    # integers only: (total*9 + 5) // 10 is total*0.9 rounded, without float error.
    budget_range = {"low": (total * 9 + 5) // 10, "high": (total * 11 + 5) // 10}

    now = datetime.now(timezone.utc)
    draft_id = f"REQ-{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4].upper()}"   # unique ID (AC 5.2)
    record = {
        "draft_id": draft_id,
        "created_at": now.isoformat(timespec="seconds"),          # the date (AC 5.2)
        "created_by": created_by,                                  # the creator (AC 5.2)
        "status": DRAFT_STATUS,
        "lines": lines,
        "skipped": skipped,
        "estimated_budget_ugx": total,
        "budget_range_ugx": budget_range,
        "requires_override_any": any(line["requires_override"] for line in lines),
        "decision": None,       # filled in later ONLY by a human via src/approvals.py
        "source": "current_stock.csv, past_purchases.csv, supplier_quotes.csv",
    }

    # The side effect: write the draft to disk so a human can review it.
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    path = DRAFTS_DIR / f"{draft_id}.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return {**record, "saved_to": path.as_posix()}
