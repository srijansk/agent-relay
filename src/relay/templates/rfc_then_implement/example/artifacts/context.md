# Context

## Goal

Add pagination to `GET /v1/items`. Currently the endpoint returns the full
result set in one response, which has caused two outages when a customer's
catalogue grew past 100k rows.

## Constraints

- The endpoint is public; we cannot break existing clients.
- API team owns the spec; engineering owns the implementation.
- New behaviour must roll out behind a flag.

## Files of interest

- `src/api/items.py` — the handler
- `src/api/schemas.py` — Pydantic response schemas
- `tests/integration/test_items_api.py` — existing integration tests
