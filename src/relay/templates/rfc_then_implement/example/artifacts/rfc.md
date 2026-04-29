# RFC: Cursor-based pagination for `GET /v1/items`

## Problem

`GET /v1/items` returns the full result set. Two production incidents in
the last quarter were caused by a customer catalogue growing past 100k
rows; response payload exceeded the gateway limit and the endpoint 500'd.

## Goals

- Bounded response size, regardless of catalogue size.
- Existing clients continue to work without code changes during a
  deprecation window.

## Non-goals

- Server-side filtering. Clients already filter via query params.
- Server-side sorting. The result order is fixed by `created_at`.

## Proposed design

Cursor-based pagination, opaque cursor encoding `(created_at, id)`.

- New query params: `?limit=N` (default 50, max 200), `?cursor=<opaque>`.
- New response schema: `{ "items": [...], "next_cursor": "..." | null }`.
- For backwards compatibility, when no `limit` and no `cursor` are
  provided, the legacy unpaginated response is returned with a
  `Sunset: <date>` header. The flag `feature_flags.paginated_items_v2`
  controls whether the legacy response is served at all (default: on for
  v0; off after the deprecation window).

## Alternatives considered

- **Offset pagination (`?offset=N`).** Why not: O(N) seek cost on the
  index, doesn't survive concurrent inserts (skipped/duplicated rows).
- **Page-token field on every row.** Why not: forces a schema migration
  in production for a problem the cursor solves at the API layer.

## Risks

- Cursor opacity is a contract; if the encoding changes we break clients.
  Mitigation: encoding is versioned (`v1:<base64>`), and a v2 reader
  rejects v1 cursors with a clear error rather than silent misbehaviour.
- A client with `limit=200` and an aggressive polling loop can still
  scrape O(N) data quickly. Out of scope for this RFC; covered by
  separate rate-limit work.

## Test and rollout plan

- New integration test: paginate through a 5k-item dataset, assert all
  items returned exactly once and the cursor terminates with `null`.
- Regression test: pre-existing client (no `limit`/`cursor` params)
  receives the legacy response with the `Sunset` header.
- Rollout: ship behind `feature_flags.paginated_items_v2`, leave OFF in
  production for one week of staging soak.
- Rollback: flip the flag back to legacy mode; no data migration to
  unwind.
