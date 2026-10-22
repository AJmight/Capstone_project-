"""
Explicit procurement memory for Week 6.
=======================================

The assistant remembers one useful preference: the owner's usual weekly
restock budget. It is a convenience default only. The person can replace or
delete it, and the person still confirms the budget before a restock runs.

Memory is deliberately allow-listed here rather than accepting arbitrary
facts from the model. Values are stored through the central scoped SQLite
repository and are never used to approve, order or pay.
"""

from datetime import datetime, timedelta, timezone

from storage import SQLiteStorage


MEMORY_KEY = "usual_weekly_budget_ugx"
MEMORY_RETENTION_DAYS = 90


class MemoryError(Exception):
    """Raised when the allowed weekly-budget memory is invalid."""


def _validate_budget(budget_ugx: int) -> int:
    if not isinstance(budget_ugx, int) or isinstance(budget_ugx, bool) or budget_ugx <= 0:
        raise MemoryError("usual weekly budget must be a positive whole number of UGX")
    return budget_ugx


def remember_usual_weekly_budget(storage: SQLiteStorage, tenant_id: str, user_id: str,
                                 budget_ugx: int) -> None:
    """Save the owner's explicit budget preference with a 90-day retention period."""
    budget = _validate_budget(budget_ugx)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=MEMORY_RETENTION_DAYS)).isoformat(
        timespec="seconds"
    )
    storage.remember(tenant_id, user_id, MEMORY_KEY, budget, expires_at)


def recall_usual_weekly_budget(storage: SQLiteStorage, tenant_id: str, user_id: str) -> int | None:
    """Return the remembered budget, or None when no current preference exists."""
    value = storage.recall(tenant_id, user_id, MEMORY_KEY)
    if value is None:
        return None
    return _validate_budget(value)


def forget_usual_weekly_budget(storage: SQLiteStorage, tenant_id: str, user_id: str) -> None:
    """Delete the remembered preference on the owner's request."""
    storage.delete_memory(tenant_id, user_id, MEMORY_KEY)