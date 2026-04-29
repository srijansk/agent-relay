# Hypothesis

## Where the failure happens

`src/app/config.py`, in the `_load_yaml` helper around lines 18–32. The
helper calls `yaml.safe_load` and returns the resulting dict directly,
without any schema validation or type coercion.

The downstream consumer `src/app/router.py:42` does a Python truthiness
check on the value:

```python
if config.feature_flags.enable_new_router:
    use_new_router()
else:
    use_legacy_router()
```

## Why the current code fails this case

`yaml.safe_load("\"false\"")` returns the Python string `"false"`. Any
non-empty string is truthy in Python, so the check succeeds and the new
router runs. The bug is not in the router check; it is in the loader's
willingness to accept a string where the schema says boolean.

## Smallest possible change

Add a Pydantic model for `FeatureFlags` with `bool` fields and validate the
loaded dict against it inside `_load_yaml`. Pydantic will reject the string
`"false"` (or, with `BeforeValidator`, coerce it) deterministically.

## Adjacent code paths

Two other flags consumed via the same loader pattern:

- `feature_flags.enable_metrics` (router.py:55)
- `feature_flags.enable_audit` (audit.py:12)

Both are vulnerable to the same string-vs-bool drift if a config author
quotes the value.

## What tests would catch a regression

- A unit test parameterised over `["true", "True", "false", "False", true, false]`
  asserting that the loader returns booleans, not strings.
- A regression test that wires the loader output into the router and
  asserts both branches given a quoted-string config.
