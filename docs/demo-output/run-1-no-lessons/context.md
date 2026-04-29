# Context

Customers say a date filter on `/v1/orders?since=...` returns
yesterday's orders even when they pass today's date. Suspect timezone
handling.

- `src/api/orders.py` parses the `since` query param and queries the DB.
