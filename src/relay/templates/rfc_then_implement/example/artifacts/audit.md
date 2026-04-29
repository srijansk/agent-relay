# Audit

## Verdict: REQUEST_CHANGES

## Summary

Implementation matches the RFC except for the `limit` default change.
The build log notes the deviation but did not amend the RFC; that's a
process bug, not a code bug, but it must be resolved before merge.

## Catches

- The default `limit` in `src/api/items.py` is `100`; the approved RFC
  says `50`. Either amend the RFC (preferred — the build_log.md
  rationale is sound) or revert to `50`. Don't ship a deviation without
  the RFC reflecting it; future readers will be confused.
- `src/api/cursors.py` is missing a test for malformed cursor input. A
  client passing `cursor="garbage"` should get a 400 with a clear error,
  not a 500.

## Confirmations

- Versioned cursor encoding `v1:<base64>` matches the RFC.
- `Sunset: 2026-09-30` header lands on legacy responses; verified with
  `tests/integration/test_items_api.py::test_legacy_unpaginated_response_emits_sunset_header`.
- Feature flag `paginated_items_v2` is wired and toggleable; verified
  by reading `src/app/feature_flags.py`.
- No existing test was disabled or skipped to make this build green.
