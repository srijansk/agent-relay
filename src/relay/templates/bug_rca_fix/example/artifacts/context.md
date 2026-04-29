# Context

## Bug report

We have a Python CLI tool `myapp` whose feature flags are loaded from
`config.yaml`. The flag `feature_flags.enable_new_router` is documented
as a boolean. When operators set it to the literal string `"false"`
(quoted), the application behaves as if the flag is ON — the opposite
of what the operator intended. Production rolled out the new router
prematurely on Friday because of this.

## Codebase pointers

- `src/myapp/config.py` — the loader, which calls `yaml.safe_load` and
  returns the resulting dict directly with no schema or type coercion.
- `src/myapp/router.py:42` — this is the consumer:
  `if config.feature_flags.enable_new_router: use_new_router() else: use_legacy_router()`
- `tests/unit/test_config.py` — existing tests parse a few well-formed
  YAML files but never cover the quoted-string-vs-bool case.
- Two adjacent flags consumed via the same loader pattern are
  potentially vulnerable: `feature_flags.enable_metrics` and
  `feature_flags.enable_audit`.

## Constraints

- The config file format is in production at multiple customers; we
  cannot break loading of currently valid files.
- We need a regression test that would have caught the original
  incident (a quoted string being silently truthy).
- Python truthiness on a non-empty string is `True`, including for the
  literal string `"false"` — that is the path that bit us.
