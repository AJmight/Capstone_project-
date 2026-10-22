# Memory Design and Data Handling Note

| Field | Value |
|:---|:---|
| Week | 6 |
| Feature | Owner's usual weekly restock budget |
| Status | Implemented |
| Storage | `data/state.sqlite3`, `memories` table |

## Why this memory is justified

The shop commonly restocks on a weekly budget. Remembering the owner's usual
budget removes repeated typing during normal use, while keeping the choice
visible and changeable. It does not decide which items to buy, calculate
quantities, create approval decisions, place orders or make payments.

## What is stored

Only the allow-listed key `usual_weekly_budget_ugx` and one positive whole
number of Uganda shillings are stored. The value is scoped by the trusted pair
`(tenant_id, user_id)`. Raw conversations, prompts, API keys and supplier
communications are not stored as memory.

## How it is used

When the console starts a weekly restock, it recalls the value for the logged-in
shop/user and displays it as the budget default. The person can replace the
value before the restock starts. The deterministic planner still receives the
explicit numeric budget and enforces all budget rules.

## Access and isolation

The application supplies `tenant_id` and `user_id` from trusted session
context. The model cannot supply or change either field. A lookup for another
shop/user returns no value. The storage layer also rejects missing scope.

## Retention and deletion

The preference expires after 90 days unless the owner replaces it. The console
memory option supports explicit deletion, and `forget_usual_weekly_budget()`
deletes the scoped record immediately.

## Data handling limits

The current prototype uses synthetic data and SQLite without encryption at
rest. The database is local runtime state and must remain ignored by version
control. A production deployment would add authenticated accounts, encrypted
storage, backup deletion procedures and a paid model/data-processing tier.

## Evidence

- `src/memory.py` restricts the feature to one allow-listed preference.
- `src/app.py` recalls it only as a restock default and exposes deletion.
- `tests/test_week6_storage.py` proves scope isolation, validation and deletion.