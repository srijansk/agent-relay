## Files Changed
- `src/api/items.py` — Added cursor-based pagination logic to the `GET /v1/items` endpoint.
- `src/api/schemas.py` — Updated response schemas to include pagination fields.
- `src/app/feature_flags.py` — Implemented feature flag logic for pagination.
- `tests/integration/test_items_api.py` — Expanded integration tests to cover paginated responses.

## Tests Added
- `test_items_pagination_with_feature_flag_enabled` — Verifies paginated responses when the feature flag is enabled.
- `test_items_pagination_with_feature_flag_disabled` — Ensures the endpoint returns non-paginated responses when the feature flag is disabled.
- `test_items_pagination_next_cursor` — Checks the correctness of the `next_cursor` field in paginated responses.
- `test_items_pagination_cursor_format` — Validates the format and versioning of the cursor.

## Deviations from RFC
None. The implementation followed the RFC specifications closely, ensuring that all aspects of the proposed design, including cursor format, feature flag integration, and backwards compatibility, were adhered to.