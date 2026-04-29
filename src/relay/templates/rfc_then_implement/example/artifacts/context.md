# Context

## Goal

Add cursor-based pagination to `GET /v1/items` in the `catalogue`
service. Currently the endpoint returns the entire result set in one
response. We have had two production incidents in the last quarter
where a customer's catalogue grew past 100k rows; the response payload
exceeded the gateway limit and the endpoint 500'd.

## Constraints

- The endpoint is public; we cannot break existing clients without a
  deprecation window.
- The API team owns the spec; engineering owns the implementation.
- Any new behaviour must be controllable via a feature flag so we can
  ship dark and roll out incrementally.
- The result order is fixed by `created_at` ASC. We do not need
  server-side filtering or sorting in this RFC.

## Files of interest

- `src/api/items.py` — the existing handler (no pagination today).
- `src/api/schemas.py` — Pydantic response schemas.
- `tests/integration/test_items_api.py` — existing integration tests
  that hit the endpoint with small fixture data.
- `src/app/feature_flags.py` — pattern used for previous flag-gated
  rollouts.

## Things to decide in the RFC

- Cursor format and versioning (we have been bitten by unversioned
  opaque payloads before).
- Backwards compatibility approach during deprecation.
- Test plan and rollback plan.
