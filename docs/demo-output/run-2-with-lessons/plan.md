# plan.md

## Objective
The application incorrectly treats the feature-flag value `enable_metrics: "false"` (quoted) as truthy, leading to the wrong behavior where metrics are enabled instead of disabled.

## Root cause
The issue arises because the `yaml.safe_load` function in `src/myapp/config.py` returns the string `"false"` as a string type, which is inherently truthy in Python. The `check_metrics_enabled` function in `src/myapp/router.py` retrieves this value and does not perform any type conversion to interpret the string `"false"` as a boolean `False`. As a result, the application treats the string `"false"` as truthy, causing the incorrect output.

## Change list
- **src/myapp/router.py**: Modify the `check_metrics_enabled` function to explicitly convert the `enable_metrics` value to a boolean by using `config.get('enable_metrics', 'false').lower() == 'true'`.

## Test plan
1. **New Test**: 
   - `test_check_metrics_enabled_with_quoted_false`: Verify that `check_metrics_enabled()` returns `False` when `enable_metrics` is set to `"false"` in the configuration.
2. **Regression Tests**:
   - `test_check_metrics_enabled_with_unquoted_false`: Ensure `check_metrics_enabled()` returns `False` when `enable_metrics` is set to `false` (unquoted).
   - `test_check_metrics_enabled_with_true`: Ensure `check_metrics_enabled()` returns `True` when `enable_metrics` is set to `"true"` or `true`.
   - Additional tests for other configuration flags that might be affected by similar issues, as mentioned in the hypothesis under "Adjacent paths."

## Risk and rollback
- **Risks**: The primary risk is that other parts of the application may rely on the current behavior of treating quoted strings as truthy. This change could inadvertently affect those areas if they are not properly tested.
- **Rollback**: Revert the commit that modifies `src/myapp/router.py` to restore the original behavior. Ensure that the commit hash is documented in the version control system for easy reference.