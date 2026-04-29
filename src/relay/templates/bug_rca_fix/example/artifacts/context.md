# Context

## Bug report

`config.feature_flags.enable_new_router` is documented as a boolean. When
the YAML file sets it to the literal string `"false"`, the application
behaves as if the flag were ON — opposite of the intent. Production rolled
out the new router prematurely on Friday because of this.

## Codebase

- `src/app/config.py` — config loader (yaml.safe_load wrapper)
- `src/app/router.py` — reads `config.feature_flags.enable_new_router`
- `tests/unit/test_config.py` — existing config tests

## Constraints

- No backwards-incompatible config changes; the file is in production.
- Need a regression test that would have caught this case.
