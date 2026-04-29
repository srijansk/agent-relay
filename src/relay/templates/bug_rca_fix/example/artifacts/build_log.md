# Build log

## Files Changed

- `src/app/config.py` — added `AppConfig` and `FeatureFlags` Pydantic
  models. `_load_yaml` now validates the loaded dict against `AppConfig`
  before returning. On validation failure, raises `ConfigError` with the
  invalid field name + the offending value.
- `tests/unit/test_config.py` — added parametrised
  `test_config_rejects_string_for_boolean_flag` covering all three flags
  with values `"true"`, `"false"`, `True`, `False`.
- `tests/integration/test_router.py` — added
  `test_router_uses_legacy_when_flag_is_quoted_false`.

## Test added

```python
@pytest.mark.parametrize(
    "flag", ["enable_new_router", "enable_metrics", "enable_audit"]
)
@pytest.mark.parametrize(
    "raw, valid",
    [("true", True), ("false", True), (True, True), (False, True),
     ("yes", False), ("nope", False)],
)
def test_config_rejects_string_for_boolean_flag(flag, raw, valid, tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(f"feature_flags:\n  {flag}: \"{raw}\"\n")
    if valid:
        loaded = load_config(cfg)
        assert isinstance(getattr(loaded.feature_flags, flag), bool)
    else:
        with pytest.raises(ConfigError):
            load_config(cfg)
```

## Test output (before / after)

Before the fix:

```
$ pytest tests/unit/test_config.py::test_config_rejects_string_for_boolean_flag
FAILED tests/unit/test_config.py::test_config_rejects_string_for_boolean_flag
  AssertionError: expected bool, got str
```

After:

```
$ pytest tests/unit/test_config.py::test_config_rejects_string_for_boolean_flag
PASSED [18 cases]
```

## Deviations from plan

None. All four tasks landed; no scope creep.
