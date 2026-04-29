## Files Changed
- `src/myapp/config.py`: Modified `load_config` function to include type coercion for boolean values.
- `tests/unit/test_config.py`: Added new test cases to verify correct interpretation of quoted boolean strings.

## Test Added
```python
def test_enable_new_router_quoted_false():
    config_data = """
    feature_flags:
      enable_new_router: "false"
    """
    config = load_config(config_data)
    assert config['feature_flags']['enable_new_router'] is False

def test_enable_new_router_quoted_true():
    config_data = """
    feature_flags:
      enable_new_router: "true"
    """
    config = load_config(config_data)
    assert config['feature_flags']['enable_new_router'] is True

def test_enable_metrics_quoted_false():
    config_data = """
    feature_flags:
      enable_metrics: "false"
    """
    config = load_config(config_data)
    assert config['feature_flags']['enable_metrics'] is False

def test_enable_metrics_quoted_true():
    config_data = """
    feature_flags:
      enable_metrics: "true"
    """
    config = load_config(config_data)
    assert config['feature_flags']['enable_metrics'] is True

def test_enable_audit_quoted_false():
    config_data = """
    feature_flags:
      enable_audit: "false"
    """
    config = load_config(config_data)
    assert config['feature_flags']['enable_audit'] is False

def test_enable_audit_quoted_true():
    config_data = """
    feature_flags:
      enable_audit: "true"
    """
    config = load_config(config_data)
    assert config['feature_flags']['enable_audit'] is True
```

## Test Output (Before / After)

### Before
- `test_enable_new_router_quoted_false`: FAILED
- `test_enable_new_router_quoted_true`: FAILED
- `test_enable_metrics_quoted_false`: FAILED
- `test_enable_metrics_quoted_true`: FAILED
- `test_enable_audit_quoted_false`: FAILED
- `test_enable_audit_quoted_true`: FAILED

### After
- `test_enable_new_router_quoted_false`: PASSED
- `test_enable_new_router_quoted_true`: PASSED
- `test_enable_metrics_quoted_false`: PASSED
- `test_enable_metrics_quoted_true`: PASSED
- `test_enable_audit_quoted_false`: PASSED
- `test_enable_audit_quoted_true`: PASSED

## Deviations from Plan
None. The implementation followed the plan precisely, and all tests were added and verified as intended.