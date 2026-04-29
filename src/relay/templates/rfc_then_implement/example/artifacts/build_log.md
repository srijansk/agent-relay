# Build log

## Files Changed

- `src/api/schemas.py` — added `PaginatedItemsResponse` (Pydantic), kept
  legacy `ItemsResponse` intact.
- `src/api/items.py` — branched on presence of `limit`/`cursor`; legacy
  branch returns `ItemsResponse` with a `Sunset: 2026-09-30` header.
- `src/api/cursors.py` (new) — versioned cursor encoder/decoder.
  Cursor format `v1:<base64-of-(created_at|id)>`.
- `tests/integration/test_items_api.py` — added the two tests below.
- `src/app/feature_flags.py` — added `paginated_items_v2` flag (default
  `True` for v0, will flip to `False` after soak).

## Tests Added

- `test_paginated_items_returns_all_items_once`: seeds 5k items,
  paginates with `limit=200`, asserts every id appears exactly once and
  final cursor is `null`.
- `test_legacy_unpaginated_response_emits_sunset_header`: sends a request
  with no pagination params, asserts response shape matches
  `ItemsResponse` and `Sunset` header is present.

Both tests fail on `main` (paginated endpoint doesn't exist), pass on
this branch.

## Deviations from RFC

- The RFC said `limit` default is 50; the implementation makes it 100,
  matching the existing internal `/v2/items` endpoint to avoid two
  surprising defaults in the same service. Author of the RFC notified;
  RFC will be amended in a follow-up.
