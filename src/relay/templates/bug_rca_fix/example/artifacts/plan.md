# Plan — fix string-vs-bool drift in feature flag loader

## Objective

Reject (or coerce) string values where the config schema says boolean, so
`feature_flags.enable_new_router: "false"` cannot silently flip behaviour.

## Root cause

`src/app/config.py:_load_yaml` returns the raw dict from `yaml.safe_load`
without validating types. The router does a Python truthiness check on
the resulting string, which is always truthy for non-empty strings.

## Change list

| File | Symbol | Change |
|---|---|---|
| `src/app/config.py` | `_load_yaml` | Validate dict against a new `AppConfig` Pydantic model before returning |
| `src/app/config.py` | `AppConfig`, `FeatureFlags` (new) | Pydantic models with explicit `bool` fields |
| `tests/unit/test_config.py` | (new test) | Parametrised over `"true"`, `"false"`, `True`, `False` — assert `bool` type |
| `tests/integration/test_router.py` | (new test) | Boot the app with a string-typed flag and assert the router is `legacy` |

## Test plan

1. Write `test_config_rejects_string_for_boolean_flag` first; expect it to
   fail on current `main`.
2. Add the Pydantic models, re-run; expect new test to pass.
3. Re-run the full suite; no regressions allowed.
4. The integration test in `tests/integration/test_router.py` is the
   end-to-end regression that would have caught the original prod incident.

## Risk and rollback

- Risk: an existing config file in production sets one of the flags to a
  string by accident; with strict validation, the app would now fail to
  start instead of silently misbehaving.
- Mitigation: log a clear, actionable error when validation fails (the
  field name and the invalid value).
- Rollback: revert the `config.py` changes; keep the new tests but mark
  them xfail so the suite stays green during rollback.
