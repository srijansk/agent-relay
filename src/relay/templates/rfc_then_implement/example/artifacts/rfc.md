```markdown
# RFC: Implement Cursor-Based Pagination for `GET /v1/items` Endpoint

## Problem
The `GET /v1/items` endpoint in the `catalogue` service currently returns the entire result set in one response. This has led to production incidents where large catalogues (over 100k rows) caused the response payload to exceed gateway limits, resulting in server errors (500 status code).

## Goals / Non-goals

### Goals
- Implement cursor-based pagination for the `GET /v1/items` endpoint.
- Ensure backwards compatibility with existing clients by providing a deprecation window.
- Control new pagination behavior via a feature flag for incremental rollout.
- Maintain fixed result order by `created_at` ASC.

### Non-goals
- Implement server-side filtering or sorting beyond the existing `created_at` ASC order.
- Change the existing data model or introduce new database indices.

## Proposed Design

### Data Model
- Introduce a cursor-based pagination mechanism using base64-encoded cursors.
- Each cursor will include a version number and the `created_at` timestamp of the last item in the current page.

### API Changes
- Add `cursor` and `limit` query parameters to the `GET /v1/items` endpoint.
- Return a `next_cursor` field in the response to indicate the cursor for the next page of results.

### File Layout
- Modify `src/api/items.py` to handle pagination logic.
- Update `src/api/schemas.py` to include pagination fields in response schemas.
- Add feature flag logic in `src/app/feature_flags.py` to toggle pagination feature.

### Trade-offs
- Using base64-encoded cursors allows for opaque cursor values but requires careful management of cursor versioning.
- Introducing pagination may increase complexity in client-side handling of paginated data.

## Alternatives Considered

1. **Offset-based Pagination**
   - **Why not**: Offset-based pagination can lead to performance issues with large datasets and does not handle data consistency well when items are added or removed.

2. **Keyset Pagination without Encoding**
   - **Why not**: While simpler, it exposes internal data structure details and lacks the flexibility of versioned cursors for future changes.

## Risks

- **Backward Compatibility**: Existing clients may not handle paginated responses correctly. Mitigation: Provide a deprecation window and clear communication to clients.
- **Data Consistency**: Items may be added or removed between paginated requests. Mitigation: Use `created_at` timestamps to ensure consistent ordering.
- **Security**: Base64-encoded cursors could expose sensitive data if not handled properly. Mitigation: Ensure cursors only include non-sensitive data and are securely encoded.

## Test and Rollout Plan

### Testing
- Develop unit tests for pagination logic to ensure correctness in isolation.
- Expand integration tests in `tests/integration/test_items_api.py` to cover paginated responses.

### Rollout
- Deploy the feature under a dark launch using feature flags.
- Gradually enable pagination for a subset of users, monitoring for issues.

### Rollback
- Monitor logs and metrics for anomalies during rollout.
- If issues arise, disable the feature flag to revert to non-paginated responses.
- Communicate with clients about any changes or rollbacks promptly.

### Deprecation Window
- Announce the deprecation of non-paginated responses with a clear timeline.
- Provide documentation and examples for clients to transition to paginated requests.

## Cursor Format and Versioning
- Cursors will include a version number to allow for future changes without breaking existing clients.
- Document the cursor format and versioning strategy to ensure clarity and consistency in future updates.
```
