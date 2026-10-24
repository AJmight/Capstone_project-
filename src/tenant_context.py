"""Resolve a business name to a safe, persistent data workspace.

The browser supplies a display name once at the welcome screen. This module derives a
stable opaque tenant ID, validates it before using it in a path, and creates an
independent copy of the starter CSVs so one business's edits never affect another.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

from guardrails import InputGuardrail


DATA_ROOT = Path("data")
TENANTS_ROOT = DATA_ROOT / "tenants"
TENANT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,40}$")
CSV_FILES = ("current_stock.csv", "past_purchases.csv", "supplier_quotes.csv", "sales.csv")
TENANT_ONLY_HEADERS = {
    # Extra purchase details for the UI; procurement tools continue to consume the
    # original four required fields and safely ignore these optional columns.
    "past_purchases.csv": ("date", "item_id", "quantity_purchased",
                           "historical_unit_price_ugx", "supplier_name", "payment_status"),
    "sales.csv": ("date", "item_id", "quantity_sold", "unit_price_ugx", "payment_method"),
}


def business_tenant_id(business_name: str) -> str:
    """Return a stable path-safe ID while keeping the entered name for display."""
    name = " ".join(str(business_name).split())
    if not name:
        raise ValueError("Enter a business name to continue.")
    normalized = unicodedata.normalize("NFKD", name.casefold())
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-") or "business"
    # A short digest prevents unrelated names that normalize to the same slug colliding.
    tenant_id = f"{slug[:24].rstrip('-')}-{hashlib.sha256(name.casefold().encode()).hexdigest()[:10]}"
    return validate_tenant_id(tenant_id)


def validate_tenant_id(value: str) -> str:
    """Validate a derived or trusted ID before it becomes a directory component."""
    InputGuardrail.validate_shop_id(value)
    if not TENANT_ID_PATTERN.fullmatch(value):
        raise ValueError("Business workspace ID is invalid.")
    return value


def tenant_data_dir(tenant_id: str) -> Path:
    """Return the validated workspace path for one business."""
    return TENANTS_ROOT / validate_tenant_id(tenant_id)


def initialize_business_data(tenant_id: str) -> Path:
    """Create empty business CSVs from the shared schema, never copy sample records."""
    destination = tenant_data_dir(tenant_id)
    destination.mkdir(parents=True, exist_ok=True)
    for filename in CSV_FILES:
        target = destination / filename
        if not target.exists():
            if filename in TENANT_ONLY_HEADERS:
                target.write_text(",".join(TENANT_ONLY_HEADERS[filename]) + "\n", encoding="utf-8")
                continue
            source = DATA_ROOT / filename
            if not source.is_file():
                raise FileNotFoundError(f"Starter data file is missing: {source}")
            # Only the header is shared. Demo/training rows must never appear as a
            # new business's real stock, quotes or purchase history.
            with source.open("r", encoding="utf-8-sig", newline="") as template:
                header = template.readline()
            with target.open("w", encoding="utf-8", newline="") as business_file:
                business_file.write(header)
    return destination
